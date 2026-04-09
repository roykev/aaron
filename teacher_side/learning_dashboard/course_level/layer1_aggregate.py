"""
Course-Level Layer 1: Cross-Lesson Aggregation

Builds cross-lesson patterns DIRECTLY from raw CSV data (quiz.csv, eval.csv, queries.csv, correct.csv).
Does NOT depend on class-level Layer 2 reports.

Aggregates:
- Recurring concepts (≥2 lectures)
- Problematic lessons (≥2 independent signals)
- Consistent successes (≥2 lectures)
- Systemic gaps (≥2 lectures, same direction)
- Prerequisite gaps (out-of-scope query clusters)

No LLM calls - uses sentence transformers for concept matching and HDBSCAN for query clustering.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import statistics

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer, util
import hdbscan

from ..common.models import (
    RecurringConcept,
    ProblematicLesson,
    ConsistentSuccess,
    SystemicGap,
    PrerequisiteGapCluster,
    CourseLayer0Output,
    CourseLayer1Output,
    GapDirection,
)
from ..common.config import LearningDashboardConfig


class ConceptMatcher:
    """Matches equivalent concepts across lectures using sentence transformers."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.similarity_threshold = similarity_threshold

    def group_similar_concepts(self, concepts: List[str]) -> Dict[str, List[str]]:
        """Group similar concept names together."""
        if not concepts:
            return {}

        unique_concepts = list(dict.fromkeys(concepts))
        embeddings = self.model.encode(unique_concepts, convert_to_tensor=True)

        groups = {}
        used = set()

        for i, concept in enumerate(unique_concepts):
            if concept in used:
                continue

            similar = [concept]
            used.add(concept)

            for j, other_concept in enumerate(unique_concepts):
                if j <= i or other_concept in used:
                    continue

                similarity = util.cos_sim(embeddings[i], embeddings[j]).item()

                if similarity >= self.similarity_threshold:
                    similar.append(other_concept)
                    used.add(other_concept)

            groups[concept] = similar

        return groups


class QueryClusterer:
    """Clusters queries using HDBSCAN + sentence transformers."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

    def cluster_queries(self, queries: List[str], min_cluster_size: int = 2) -> Dict[int, List[str]]:
        """
        Cluster queries using HDBSCAN.

        Args:
            queries: List of query texts
            min_cluster_size: Minimum cluster size

        Returns:
            Dict mapping cluster_id → list of queries in that cluster
        """
        if len(queries) < min_cluster_size:
            return {}

        # Encode queries
        embeddings = self.model.encode(queries)

        # Cluster with HDBSCAN
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric='euclidean'
        )
        cluster_labels = clusterer.fit_predict(embeddings)

        # Group by cluster
        clusters = defaultdict(list)
        for idx, label in enumerate(cluster_labels):
            if label != -1:  # -1 is noise
                clusters[label].append(queries[idx])

        return dict(clusters)


class RecurringConceptDetector:
    """Detects concepts that appear as issues across ≥2 lectures FROM RAW DATA."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.matcher = ConceptMatcher()
        self.clusterer = QueryClusterer(config)

    def detect_recurring_concepts(
        self,
        eval_df: pd.DataFrame,
        correct_df: pd.DataFrame,
        queries_df: pd.DataFrame,
        layer0_output: CourseLayer0Output,
    ) -> List[RecurringConcept]:
        """
        Detect recurring concepts from raw data using query clustering.

        Strategy (adapted to actual data structure):
        1. Cluster all queries across lectures to find recurring topics
        2. For each cluster, count which lectures it appears in
        3. Find clusters appearing in ≥2 lectures
        4. These represent recurring issues/concepts

        Args:
            eval_df: eval.csv (all lectures)
            correct_df: correct.csv (question definitions - not used for concepts)
            queries_df: queries.csv (all queries)
            layer0_output: Course Layer 0 output (for revisit signals, segments)

        Returns:
            List of RecurringConcept objects
        """
        if self.config.verbose:
            print("   [RecurringConceptDetector] Clustering queries to find recurring topics...")
            print(f"   Found {len(queries_df)} queries")

        if len(queries_df) == 0:
            return []

        # Get all query texts
        all_queries = queries_df['query'].tolist()

        if len(all_queries) < 2:
            return []

        # Cluster queries to find recurring topics
        query_clusters = self.clusterer.cluster_queries(all_queries, min_cluster_size=2)

        if self.config.verbose:
            print(f"   Found {len(query_clusters)} query clusters")

        # Build cluster → lecture → metrics
        cluster_metrics = defaultdict(lambda: defaultdict(lambda: {
            'query_n': 0,
            'student_ids': set(),
        }))

        # Map each query to its cluster
        query_to_cluster = {}
        for cluster_id, queries in query_clusters.items():
            for query in queries:
                query_to_cluster[query] = cluster_id

        # Count queries per cluster per lecture
        for _, row in queries_df.iterrows():
            query_text = row['query']
            lecture_id = row['entity_id']
            student_id = row.get('user_id', '')

            if query_text in query_to_cluster:
                cluster_id = query_to_cluster[query_text]
                cluster_metrics[cluster_id][lecture_id]['query_n'] += 1
                cluster_metrics[cluster_id][lecture_id]['student_ids'].add(student_id)

        # Build RecurringConcept objects for clusters appearing in ≥2 lectures
        recurring = []

        for cluster_id, lecture_data in cluster_metrics.items():
            lectures_involved = list(lecture_data.keys())

            # Check significance gate: ≥2 lectures
            if len(lectures_involved) < 2:
                continue

            # Get cluster queries (use first 3 as representatives)
            cluster_queries = query_clusters[cluster_id][:3]
            concept_name = cluster_queries[0] if cluster_queries else f"Cluster {cluster_id}"

            # Get lecture names
            lecture_names = [
                lec.name for lec in layer0_output.lecture_sequence
                if lec.lecture_id in lectures_involved
            ]

            # Count total queries and students
            total_queries = sum(data['query_n'] for data in lecture_data.values())
            all_students = set()
            for data in lecture_data.values():
                all_students.update(data['student_ids'])

            # Calculate recurrence score
            engaged_n = layer0_output.engagement.engaged_n
            if engaged_n == 0:
                recurrence_score = 0.0
            else:
                recurrence_score = (
                    len(lectures_involved) * 2.0 +
                    len(all_students) * 1.0 +
                    total_queries * 0.5
                ) / engaged_n

            recurring.append(RecurringConcept(
                concept=concept_name,
                appearance_count=len(lectures_involved),
                total_failure_n=0,  # Not available without concept mapping
                total_query_n=total_queries,
                revisit_student_n=len(all_students),
                lectures=lecture_names,
                segment_breakdown={},
                is_struggles_dominant=False,
                recurrence_score=recurrence_score,
            ))

        # Sort by recurrence score
        recurring.sort(key=lambda x: x.recurrence_score, reverse=True)

        if self.config.verbose:
            print(f"   Found {len(recurring)} recurring query clusters (≥2 lectures)")

        # Return top 10
        return recurring[:10]


class ProblematicLessonDetector:
    """Detects lessons with holistic underperformance FROM RAW DATA."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def detect_problematic_lessons(
        self,
        eval_df: pd.DataFrame,
        quiz_df: pd.DataFrame,
        queries_df: pd.DataFrame,
        layer0_output: CourseLayer0Output,
        course_eval_avg: float,
    ) -> List[ProblematicLesson]:
        """
        Detect problematic lessons from raw data.

        Strategy:
        1. Calculate per-lecture eval averages
        2. Count query volume per lecture
        3. Check for surface learning (quiz >> eval per lecture)
        4. Identify lectures with ≥2 independent signals

        Args:
            eval_df: eval.csv
            quiz_df: quiz.csv
            queries_df: queries.csv
            layer0_output: Course Layer 0 output (for revisit data)
            course_eval_avg: Course-wide eval average

        Returns:
            List of ProblematicLesson objects
        """
        if self.config.verbose:
            print("   [ProblematicLessonDetector] Analyzing per-lecture performance...")

        problematic = []
        lecture_names = {lec.lecture_id: lec.name for lec in layer0_output.lecture_sequence}

        for lecture in layer0_output.lecture_sequence:
            lecture_id = lecture.lecture_id
            lecture_name = lecture.name

            # Get eval scores for this lecture
            lecture_evals = eval_df[eval_df['lecture_id'] == lecture_id]
            if len(lecture_evals) == 0:
                continue

            lesson_eval_avg = lecture_evals['score'].mean()

            # Get quiz scores for this lecture
            lecture_quizzes = quiz_df[quiz_df['lecture_id'] == lecture_id]
            lesson_quiz_avg = lecture_quizzes['score'].mean() if len(lecture_quizzes) > 0 else 0

            # Get query count for this lecture
            lecture_queries = queries_df[queries_df['entity_id'] == lecture_id]
            query_count = len(lecture_queries['user_id'].unique())

            # Get revisit count
            revisit_count = layer0_output.revisit_metrics.revisit_by_lecture.get(lecture_id, 0)

            # Check signals
            signals = []

            if lesson_eval_avg < course_eval_avg - 10:
                signals.append("low_eval")

            if query_count >= 5:  # High query volume suggests confusion
                signals.append("high_query_volume")

            if revisit_count >= 3:
                signals.append("high_revisit")

            if lesson_quiz_avg > lesson_eval_avg + 15:  # Surface learning
                signals.append("surface_learning")

            problem_signal_count = len(signals)

            # Check problematic threshold
            if problem_signal_count < 2:
                continue

            # Compute problem score
            problem_score = (
                (course_eval_avg - lesson_eval_avg) * 0.4
                + query_count * 0.02  # Normalize query count
                + revisit_count * 0.3
            )

            problematic.append(ProblematicLesson(
                lecture_id=lecture_id,
                lecture_name=lecture_name,
                lesson_eval_avg=lesson_eval_avg,
                course_eval_avg=course_eval_avg,
                issue_count=query_count,  # Use query volume as proxy for issues
                revisit_student_n=revisit_count,
                signals=signals,
                problem_signal_count=problem_signal_count,
                lesson_problem_score=problem_score,
            ))

        # Sort by problem score
        problematic.sort(key=lambda x: x.lesson_problem_score, reverse=True)

        if self.config.verbose:
            print(f"   Found {len(problematic)} problematic lessons")

        # Dynamic threshold: return min(3, count_with_score > threshold)
        # This ensures we only return truly problematic lessons even if data is sparse
        significant_threshold = 5.0  # Minimum problem score to be considered significant
        significant_lessons = [p for p in problematic if p.lesson_problem_score >= significant_threshold]

        # Return at most 3, but fewer if not enough meet significance threshold
        result_count = min(3, len(significant_lessons))

        if self.config.verbose:
            print(f"   Returning {result_count} lessons meeting significance threshold (score ≥ {significant_threshold})")

        return significant_lessons[:result_count] if result_count > 0 else problematic[:min(3, len(problematic))]


class GoodLessonDetector:
    """Detects lessons with consistently strong performance FROM RAW DATA."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def detect_good_lessons(
        self,
        eval_df: pd.DataFrame,
        quiz_df: pd.DataFrame,
        queries_df: pd.DataFrame,
        layer0_output: CourseLayer0Output,
        course_eval_avg: float,
    ) -> List[Dict]:
        """
        Detect well-performing lessons with ≥2 positive signals.

        Strategy:
        1. Calculate per-lecture eval averages
        2. Count positive signals: high eval, low query volume, low revisit, deep learning (eval >> quiz)
        3. Identify lectures with ≥2 positive signals
        4. Return top 3 with dynamic threshold based on success score

        Args:
            eval_df: eval.csv
            quiz_df: quiz.csv
            queries_df: queries.csv
            layer0_output: Course Layer 0 output
            course_eval_avg: Course-wide eval average

        Returns:
            List of good lesson dicts
        """
        if self.config.verbose:
            print("   [GoodLessonDetector] Analyzing per-lecture performance for successes...")

        good_lessons = []

        for lecture in layer0_output.lecture_sequence:
            lecture_id = lecture.lecture_id
            lecture_name = lecture.name

            # Get eval scores for this lecture
            lecture_evals = eval_df[eval_df['lecture_id'] == lecture_id]
            if len(lecture_evals) == 0:
                continue

            lesson_eval_avg = lecture_evals['score'].mean()

            # Get quiz scores for this lecture
            lecture_quizzes = quiz_df[quiz_df['lecture_id'] == lecture_id]
            lesson_quiz_avg = lecture_quizzes['score'].mean() if len(lecture_quizzes) > 0 else 0

            # Get query count for this lecture
            lecture_queries = queries_df[queries_df['entity_id'] == lecture_id]
            query_count = len(lecture_queries['user_id'].unique())

            # Get revisit count
            revisit_count = layer0_output.revisit_metrics.revisit_by_lecture.get(lecture_id, 0)

            # Check positive signals
            signals = []

            if lesson_eval_avg > course_eval_avg + 10:  # Significantly above average
                signals.append("high_eval")

            if query_count <= 2:  # Low confusion
                signals.append("low_query_volume")

            if revisit_count <= 1:  # Low revisit needs
                signals.append("low_revisit")

            if lesson_eval_avg > lesson_quiz_avg + 5:  # Deep learning (eval > quiz suggests understanding beyond memorization)
                signals.append("deep_learning")

            positive_signal_count = len(signals)

            # Check success threshold: ≥2 positive signals
            if positive_signal_count < 2:
                continue

            # Compute success score (inverse of problem score)
            success_score = (
                (lesson_eval_avg - course_eval_avg) * 0.5  # Reward above-average performance
                + (5 - query_count) * 0.02  # Reward low query volume
                + (3 - revisit_count) * 0.3  # Reward low revisit needs
            )

            good_lessons.append({
                'lecture_id': lecture_id,
                'lecture_name': lecture_name,
                'lesson_eval_avg': lesson_eval_avg,
                'course_eval_avg': course_eval_avg,
                'signals': signals,
                'positive_signal_count': positive_signal_count,
                'lesson_success_score': success_score,
                'query_count': query_count,
                'revisit_count': revisit_count,
            })

        # Sort by success score
        good_lessons.sort(key=lambda x: x['lesson_success_score'], reverse=True)

        if self.config.verbose:
            print(f"   Found {len(good_lessons)} good lessons")

        # Dynamic threshold: return min(3, count_with_score > threshold)
        significant_threshold = 3.0  # Minimum success score to be considered significant
        significant_lessons = [g for g in good_lessons if g['lesson_success_score'] >= significant_threshold]

        # Return at most 3, but fewer if not enough meet significance threshold
        result_count = min(3, len(significant_lessons))

        if self.config.verbose:
            print(f"   Returning {result_count} lessons meeting significance threshold (score ≥ {significant_threshold})")

        return significant_lessons[:result_count] if result_count > 0 else good_lessons[:min(3, len(good_lessons))]


class ConsistentSuccessDetector:
    """Detects concepts that worked well across ≥2 lectures FROM RAW DATA."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.matcher = ConceptMatcher()

    def detect_consistent_successes(
        self,
        eval_df: pd.DataFrame,
        quiz_df: pd.DataFrame,
        correct_df: pd.DataFrame,
    ) -> List[ConsistentSuccess]:
        """
        Detect question topics with highest success rates using embedding clustering.

        Strategy:
        1. Extract question texts from correct.csv (eval) and quiz.csv (quiz)
        2. Calculate success rate per question (≥60% threshold)
        3. Cluster similar questions using embeddings
        4. Filter: keep clusters with ≥2 classes AND ≥1 eval question
        5. Return top performing topic clusters

        Args:
            eval_df: eval.csv
            quiz_df: quiz.csv
            correct_df: correct.csv

        Returns:
            List of ConsistentSuccess objects
        """
        if self.config.verbose:
            print("   [ConsistentSuccessDetector] Analyzing question-level performance...")

        import json

        # Extract questions with performance data
        questions_data = []

        # 1. Extract EVAL questions from correct.csv
        for _, row in correct_df.iterrows():
            lecture_id = row['lecture_id']
            lecture_name = row['name']

            # Parse evaluation JSON
            try:
                eval_data = json.loads(row['evaluation'])
                questions = eval_data.get('questions', [])

                for q_idx, question in enumerate(questions):
                    q_text = question.get('question', '')
                    if not q_text or len(q_text) < 10:
                        continue

                    # Get all eval attempts for this lecture
                    lecture_evals = eval_df[eval_df['lecture_id'] == lecture_id]

                    if len(lecture_evals) == 0:
                        continue

                    # Calculate success rate (using overall score as proxy)
                    avg_score = lecture_evals['score'].mean()
                    high_performers = lecture_evals[lecture_evals['score'] >= 70]
                    success_rate = (len(high_performers) / len(lecture_evals)) * 100 if len(lecture_evals) > 0 else 0

                    # Only include questions with good success rate
                    if success_rate >= 60:  # 60% threshold
                        questions_data.append({
                            'question': q_text,
                            'lecture': lecture_name,
                            'lecture_id': lecture_id,
                            'success_rate': success_rate,
                            'avg_score': avg_score,
                            'student_count': len(lecture_evals),
                            'type': 'eval',  # Mark as eval question
                        })

            except (json.JSONDecodeError, KeyError) as e:
                continue

        # 2. Extract QUIZ questions from correct.csv
        for _, row in correct_df.iterrows():
            lecture_id = row['lecture_id']
            lecture_name = row['name']

            # Parse quiz JSON
            try:
                quiz_data = json.loads(row['quiz'])
                questions = quiz_data.get('questions', [])

                for q_idx, question in enumerate(questions):
                    q_text = question.get('question', '')
                    if not q_text or len(q_text) < 10:
                        continue

                    # Get all quiz attempts for this lecture
                    lecture_quizzes = quiz_df[quiz_df['lecture_id'] == lecture_id]

                    if len(lecture_quizzes) == 0:
                        continue

                    # Calculate success rate
                    avg_score = lecture_quizzes['score'].mean()
                    high_performers = lecture_quizzes[lecture_quizzes['score'] >= 70]
                    success_rate = (len(high_performers) / len(lecture_quizzes)) * 100 if len(lecture_quizzes) > 0 else 0

                    # Only include questions with good success rate
                    if success_rate >= 60:  # 60% threshold
                        questions_data.append({
                            'question': q_text,
                            'lecture': lecture_name,
                            'lecture_id': lecture_id,
                            'success_rate': success_rate,
                            'avg_score': avg_score,
                            'student_count': len(lecture_quizzes),
                            'type': 'quiz',  # Mark as quiz question
                        })

            except (json.JSONDecodeError, KeyError) as e:
                continue

        if len(questions_data) == 0:
            return []

        if self.config.verbose:
            eval_count = sum(1 for q in questions_data if q['type'] == 'eval')
            quiz_count = sum(1 for q in questions_data if q['type'] == 'quiz')
            print(f"   Found {len(questions_data)} questions with ≥60% success ({eval_count} eval, {quiz_count} quiz)")
            print(f"   Clustering questions by semantic similarity...")

        # Cluster questions directly by their semantic content using embeddings
        question_texts = [q['question'] for q in questions_data]
        embeddings = self.matcher.model.encode(question_texts, convert_to_tensor=True)

        # Group similar topics
        topic_groups = defaultdict(list)
        used_indices = set()

        for i, q_data in enumerate(questions_data):
            if i in used_indices:
                continue

            # Find similar topics
            similar_indices = [i]
            used_indices.add(i)

            for j in range(i + 1, len(questions_data)):
                if j in used_indices:
                    continue

                similarity = util.cos_sim(embeddings[i], embeddings[j]).item()
                if similarity >= 0.70:  # Lower threshold for topic similarity
                    similar_indices.append(j)
                    used_indices.add(j)

            # Aggregate metrics for this topic group
            group_questions = [questions_data[idx] for idx in similar_indices]
            avg_success_rate = statistics.mean([q['success_rate'] for q in group_questions])

            # Get unique lecture_ids (not lecture names) for accurate counting
            lecture_ids_involved = list(set(q['lecture_id'] for q in group_questions))
            lectures_involved = list(set(q['lecture'] for q in group_questions))

            # Check if cluster has at least one eval question
            has_eval_question = any(q['type'] == 'eval' for q in group_questions)

            # Use the shortest question as representative (usually more concise/topic-like)
            shortest_question = min(group_questions, key=lambda x: len(x['question']))

            topic_groups[i] = {
                'representative': shortest_question['question'],  # Use shortest question as topic
                'count': len(group_questions),
                'avg_success_rate': avg_success_rate,
                'lectures': lectures_involved,
                'lecture_ids': lecture_ids_involved,
                'has_eval_question': has_eval_question,
                'total_students': sum(q['student_count'] for q in group_questions),
            }

        if self.config.verbose:
            print(f"   Grouped into {len(topic_groups)} topic clusters")

        # Convert to ConsistentSuccess objects
        # Filter: ≥2 classes AND ≥1 eval question
        successes = []
        for group_data in topic_groups.values():
            # Significance gate 1: must appear in ≥2 classes (unique lecture_ids)
            if len(group_data['lecture_ids']) < 2:
                continue

            # Significance gate 2: must have at least one eval question
            if not group_data['has_eval_question']:
                continue

            successes.append(ConsistentSuccess(
                concept=group_data['representative'],
                success_count=group_data['count'],  # Number of similar questions
                avg_success_rate=group_data['avg_success_rate'],
                teaching_pattern={},
                segment_note=f"{group_data['count']} similar questions across {len(group_data['lecture_ids'])} lectures",
                lectures=group_data['lectures'],
            ))

        # Sort by success rate descending
        successes.sort(key=lambda x: x.avg_success_rate, reverse=True)

        if self.config.verbose:
            print(f"   Found {len(successes)} topics appearing in ≥2 lectures")
            print(f"   Returning top {min(len(successes), 10)} successful topic groups")

        # Return top 10
        return successes[:10]


class TeachingInvestmentAggregator:
    """Aggregates teaching investment patterns from class-level Layer 2 reports."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.matcher = ConceptMatcher()

    def load_class_reports(
        self,
        layer0_output: CourseLayer0Output,
        class_reports_dir: Path,
    ) -> Dict[str, Dict]:
        """
        Load all class-level reports from lecturer_report.json (JSONL format).

        Args:
            layer0_output: Course Layer 0 output (for lecture IDs)
            class_reports_dir: Directory containing lecturer_report.json

        Returns:
            Dict mapping lecture_id → report dict
        """
        class_reports = {}

        # Look for lecturer_report.json in the class_reports_dir
        lecturer_report_path = class_reports_dir / "lecturer_report.json"

        if not lecturer_report_path.exists():
            if self.config.verbose:
                print(f"   ⚠️  lecturer_report.json not found at {lecturer_report_path}")
            return class_reports

        if self.config.verbose:
            print(f"   📄 Reading lecturer_report.json...")

        # Read JSONL file (one JSON object per line)
        try:
            with open(lecturer_report_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        report = json.loads(line)
                        lecture_id = report.get('lecture_id')

                        if not lecture_id:
                            continue

                        # Check if this lecture is in our sequence
                        lecture_in_sequence = any(
                            lec.lecture_id == lecture_id
                            for lec in layer0_output.lecture_sequence
                        )

                        if lecture_in_sequence:
                            class_reports[lecture_id] = report

                            lecture_name = next(
                                (lec.name for lec in layer0_output.lecture_sequence if lec.lecture_id == lecture_id),
                                lecture_id
                            )

                            if self.config.verbose:
                                print(f"   ✅ Loaded report for {lecture_name}")

                    except json.JSONDecodeError as e:
                        if self.config.verbose:
                            print(f"   ⚠️  Failed to parse line {line_num}: {e}")
                        continue

        except Exception as e:
            if self.config.verbose:
                print(f"   ❌ Failed to read lecturer_report.json: {e}")

        if self.config.verbose:
            print(f"   📊 Loaded {len(class_reports)} lecture reports from lecturer_report.json")

        return class_reports

    def aggregate_teaching_investment(
        self,
        class_reports: Dict[str, Dict],
        layer0_output: CourseLayer0Output,
        inclass_questions: List[Dict] = None,
    ) -> Dict[str, Dict]:
        """
        Aggregate teaching investment across all concepts from class reports.

        Extracts teaching time from the "Class Structure" HTML table in lecturer_report.
        Counts in-class questions per concept by matching timestamps.

        Args:
            class_reports: Dict of lecture_id → report (from lecturer_report.json)
            layer0_output: Course Layer 0 output (for lecture names)
            inclass_questions: List of in-class questions with matched sections

        Returns:
            Dict mapping concept → aggregated investment data
        """
        import re
        from html.parser import HTMLParser

        # HTML table parser
        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_table = False
                self.in_row = False
                self.in_cell = False
                self.current_row = []
                self.rows = []
                self.cell_data = []

            def handle_starttag(self, tag, attrs):
                if tag == 'table':
                    self.in_table = True
                elif tag == 'tr' and self.in_table:
                    self.in_row = True
                    self.current_row = []
                elif tag in ['td', 'th'] and self.in_row:
                    self.in_cell = True
                    self.cell_data = []

            def handle_endtag(self, tag):
                if tag == 'table':
                    self.in_table = False
                elif tag == 'tr' and self.in_row:
                    self.in_row = False
                    if self.current_row:
                        self.rows.append(self.current_row)
                elif tag in ['td', 'th'] and self.in_cell:
                    self.in_cell = False
                    self.current_row.append(''.join(self.cell_data).strip())

            def handle_data(self, data):
                if self.in_cell:
                    self.cell_data.append(data)

        # Track teaching investment per concept across lectures
        concept_investments = defaultdict(lambda: {
            'lectures': [],
            'total_time_minutes': 0,
            'total_time_pct': 0,
            'example_used_count': 0,
            'inclass_questions_total': 0,
            'assessment_pct_total': 0,
            'lecture_count': 0,
        })

        lecture_names = {lec.lecture_id: lec.name for lec in layer0_output.lecture_sequence}

        for lecture_id, report in class_reports.items():
            lecture_name = lecture_names.get(lecture_id, lecture_id)

            # Extract Class Structure from HTML report
            lecturer_report = report.get('lecturer_report', '')
            if not lecturer_report or lecturer_report == 'null':
                continue

            # Find Class Structure table
            if 'Class Structure' not in lecturer_report:
                continue

            # Extract table HTML
            start_idx = lecturer_report.find('Class Structure')
            table_start = lecturer_report.find('<table', start_idx)
            table_end = lecturer_report.find('</table>', table_start)

            if table_start == -1 or table_end == -1:
                continue

            table_html = lecturer_report[table_start:table_end + 8]

            # Parse table
            parser = TableParser()
            parser.feed(table_html)

            # Process rows (skip header row)
            for row in parser.rows[1:]:  # Skip header
                if len(row) < 5:
                    continue

                # Row format: [#, Section, Start, End, Duration]
                section_name = row[1]
                duration_str = row[4]  # e.g., "00:22:04"

                # Parse duration to minutes
                try:
                    time_parts = duration_str.split(':')
                    if len(time_parts) == 3:
                        h, m, s = map(int, time_parts)
                        total_minutes = h * 60 + m + s / 60.0
                    elif len(time_parts) == 2:
                        m, s = map(int, time_parts)
                        total_minutes = m + s / 60.0
                    else:
                        continue
                except (ValueError, AttributeError):
                    continue

                # Skip very short sections (< 2 minutes, likely admin/breaks)
                if total_minutes < 2:
                    continue

                # Aggregate by concept (section name)
                concept_investments[section_name]['lectures'].append(lecture_name)
                concept_investments[section_name]['total_time_minutes'] += total_minutes
                concept_investments[section_name]['lecture_count'] += 1

        # Count in-class questions per concept
        if inclass_questions:
            for question in inclass_questions:
                matched_section = question.get('matched_section')
                if matched_section and matched_section in concept_investments:
                    concept_investments[matched_section]['inclass_questions_total'] += 1

        if self.config.verbose:
            concepts_with_questions = sum(1 for c in concept_investments.values() if c['inclass_questions_total'] > 0)
            print(f"   Counted in-class questions for {concepts_with_questions} concepts")

        return dict(concept_investments)

    def aggregate_inclass_questions(
        self,
        class_reports: Dict[str, Dict],
        layer0_output: CourseLayer0Output,
    ) -> List[Dict]:
        """
        Aggregate in-class questions from all class reports.

        Extracts from "Class Interactions" HTML table and matches to sections by timestamp.

        Args:
            class_reports: Dict of lecture_id → report (from lecturer_report.json)
            layer0_output: Course Layer 0 output (for lecture names)

        Returns:
            List of in-class question patterns with matched concepts
        """
        from html.parser import HTMLParser
        import re

        # HTML table parser
        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_table = False
                self.in_row = False
                self.in_cell = False
                self.current_row = []
                self.rows = []
                self.cell_data = []

            def handle_starttag(self, tag, attrs):
                if tag == 'table':
                    self.in_table = True
                elif tag == 'tr' and self.in_table:
                    self.in_row = True
                    self.current_row = []
                elif tag in ['td', 'th'] and self.in_row:
                    self.in_cell = True
                    self.cell_data = []

            def handle_endtag(self, tag):
                if tag == 'table':
                    self.in_table = False
                elif tag == 'tr' and self.in_row:
                    self.in_row = False
                    if self.current_row:
                        self.rows.append(self.current_row)
                elif tag in ['td', 'th'] and self.in_cell:
                    self.in_cell = False
                    self.current_row.append(''.join(self.cell_data).strip())

            def handle_data(self, data):
                if self.in_cell:
                    self.cell_data.append(data)

        def time_to_seconds(time_str: str) -> int:
            """Convert HH:MM:SS or MM:SS to seconds."""
            try:
                parts = time_str.split(':')
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return h * 3600 + m * 60 + s
                elif len(parts) == 2:
                    m, s = map(int, parts)
                    return m * 60 + s
                return 0
            except (ValueError, AttributeError):
                return 0

        def match_time_to_section(time_seconds: int, sections: List[Dict]) -> str:
            """Match a timestamp to the corresponding section."""
            for section in sections:
                if section['start'] <= time_seconds <= section['end']:
                    return section['name']
            return "Unknown"

        inclass_questions = []
        lecture_names = {lec.lecture_id: lec.name for lec in layer0_output.lecture_sequence}

        for lecture_id, report in class_reports.items():
            lecture_name = lecture_names.get(lecture_id, lecture_id)

            # Extract HTML report
            lecturer_report = report.get('lecturer_report', '')
            if not lecturer_report or lecturer_report == 'null':
                continue

            # 1. First extract Class Structure to build section timeline
            sections = []
            if 'Class Structure' in lecturer_report:
                structure_idx = lecturer_report.find('Class Structure')
                table_start = lecturer_report.find('<table', structure_idx)
                table_end = lecturer_report.find('</table>', table_start)

                if table_start != -1 and table_end != -1:
                    table_html = lecturer_report[table_start:table_end + 8]
                    parser = TableParser()
                    parser.feed(table_html)

                    # Parse sections
                    for row in parser.rows[1:]:  # Skip header
                        if len(row) >= 5:
                            section_name = row[1]
                            start_time = row[2]  # e.g., "00:07:26"
                            end_time = row[3]    # e.g., "00:29:30"

                            sections.append({
                                'name': section_name,
                                'start': time_to_seconds(start_time),
                                'end': time_to_seconds(end_time),
                            })

            # 2. Extract Class Interactions table
            if 'Class Interactions' not in lecturer_report:
                continue

            interactions_idx = lecturer_report.find('Class Interactions')
            table_start = lecturer_report.find('<table', interactions_idx)
            table_end = lecturer_report.find('</table>', table_start)

            if table_start == -1 or table_end == -1:
                continue

            table_html = lecturer_report[table_start:table_end + 8]

            # Parse interactions table
            parser = TableParser()
            parser.feed(table_html)

            # Process rows (skip header row)
            # Row format: [Time, Type, Description]
            for row in parser.rows[1:]:  # Skip header
                if len(row) < 3:
                    continue

                time_str = row[0]  # e.g., "00:06:00"
                interaction_type = row[1]  # e.g., "שאלת מורה", "שאלת סטודנטית"
                description = row[2]

                # Only count student questions or teacher questions
                is_question = any(keyword in interaction_type for keyword in [
                    'שאלת', 'שאלה', 'question', 'Question'
                ])

                if not is_question:
                    continue

                # Match timestamp to section
                time_seconds = time_to_seconds(time_str)
                matched_section = match_time_to_section(time_seconds, sections)

                inclass_questions.append({
                    'lecture': lecture_name,
                    'lecture_id': lecture_id,
                    'time': time_str,
                    'type': interaction_type,
                    'description': description,
                    'matched_section': matched_section,
                })

        if self.config.verbose:
            print(f"   Extracted {len(inclass_questions)} in-class questions from Class Interactions tables")

        return inclass_questions


class SystemicGapDetector:
    """Detects teaching-learning gaps FROM RAW DATA + CLASS REPORTS."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.matcher = ConceptMatcher()

    def detect_systemic_gaps(
        self,
        eval_df: pd.DataFrame,
        quiz_df: pd.DataFrame,
        correct_df: pd.DataFrame,
        teaching_investments: Optional[Dict[str, Dict]] = None,
    ) -> List[SystemicGap]:
        """
        Detect systemic teaching-learning gaps at concept level using teaching ROI.

        Strategy:
        1. For each topic: Calculate combined success metric (eval + quiz scores) + struggle signals (in-class questions + queries)
        2. Calculate teaching ROI = success_metric / time_invested
        3. Lower ROI = worse efficiency (minimal division = minimal success per minute)
        4. Return concepts with minimal ROI scores (worst teaching efficiency)

        Args:
            eval_df: eval.csv
            quiz_df: quiz.csv
            correct_df: correct.csv
            teaching_investments: Dict mapping concept → teaching investment data

        Returns:
            List of SystemicGap objects sorted by ROI (worst first = lowest scores)
        """
        if self.config.verbose:
            print("   [SystemicGapDetector] Calculating teaching ROI (Return on Investment)...")

        systemic_gaps = []

        # 1. Calculate teaching ROI for each concept
        if teaching_investments and len(teaching_investments) > 0:
            if self.config.verbose:
                print(f"   Analyzing {len(teaching_investments)} concepts with teaching investment data...")

            roi_scores = []

            for concept, investment_data in teaching_investments.items():
                lecture_count = investment_data['lecture_count']

                # Only consider concepts appearing in ≥2 lectures
                if lecture_count < 2:
                    continue

                total_time_minutes = investment_data['total_time_minutes']
                total_inclass_questions = investment_data.get('inclass_questions_total', 0)
                lectures = investment_data['lectures']

                # Skip if no time invested
                if total_time_minutes == 0:
                    continue

                # Calculate combined success metric from eval/quiz data
                # We need to find eval/quiz scores related to this concept
                # Since we don't have direct concept-score mapping, we'll estimate from queries
                # Success indicators: fewer queries = higher success
                # Struggle indicators: more in-class questions + more queries

                # Estimate success score (inverse of struggle signals)
                # Success = 100 - (struggle signals normalized to 0-100 scale)
                avg_inclass_questions = total_inclass_questions / lecture_count

                # Normalize to 0-100 scale (assuming 5 in-class questions = 50% struggle)
                struggle_score = min(100, (avg_inclass_questions / 5.0) * 100)
                success_score = max(0, 100 - struggle_score)

                # Teaching ROI = success_score / total_time_minutes (points per minute)
                teaching_roi = success_score / total_time_minutes if total_time_minutes > 0 else 0

                # Only flag if significant investment (>30 min total) with low ROI
                if total_time_minutes > 30:
                    roi_scores.append({
                        'concept': concept,
                        'teaching_roi': teaching_roi,
                        'total_time': total_time_minutes,
                        'success_score': success_score,
                        'total_inclass_questions': total_inclass_questions,
                        'lecture_count': lecture_count,
                        'lectures': lectures,
                    })

            # Sort by ROI (lowest first = worst efficiency)
            roi_scores.sort(key=lambda x: x['teaching_roi'])

            # Create SystemicGap objects for top 5 worst ROI scores
            for item in roi_scores[:5]:
                systemic_gaps.append(SystemicGap(
                    concept=item['concept'],
                    direction=GapDirection.OVER_INVESTED,
                    gap_appearances=item['lecture_count'],
                    segment_gap={},
                    interpretation=f"Teaching ROI: {item['teaching_roi']:.2f} points/min. Total investment: {item['total_time']:.0f} minutes across {item['lecture_count']} lectures. Estimated success score: {item['success_score']:.0f}%, but {item['total_inclass_questions']} in-class questions suggest ongoing struggles. Low ROI (points per minute) indicates high course-wide investment with minimal student success.",
                    lectures=item['lectures'][:5],
                ))

            if self.config.verbose:
                print(f"   Found {len(roi_scores)} concepts with teaching ROI data")
                print(f"   Flagging top {min(5, len(roi_scores))} with minimal ROI (worst efficiency)")

        # 2. Also detect lecture-level surface learning patterns (quiz >> eval)
        if self.config.verbose:
            print("   Analyzing lecture-level quiz-eval gaps...")

        lecture_gaps = []

        for lecture_id in eval_df['lecture_id'].unique():
            lecture_evals = eval_df[eval_df['lecture_id'] == lecture_id]
            lecture_quizzes = quiz_df[quiz_df['lecture_id'] == lecture_id]

            if len(lecture_evals) == 0 or len(lecture_quizzes) == 0:
                continue

            eval_avg = lecture_evals['score'].mean()
            quiz_avg = lecture_quizzes['score'].mean()
            gap = quiz_avg - eval_avg

            # If quiz >> eval by >20 points, it's a systemic gap (surface learning)
            if gap > 20:
                lecture_name = lecture_id  # Would need to lookup from layer0
                lecture_gaps.append({
                    'lecture_id': lecture_id,
                    'lecture_name': lecture_name,
                    'gap': gap,
                    'quiz_avg': quiz_avg,
                    'eval_avg': eval_avg,
                })

        if len(lecture_gaps) >= 3:  # At least 3 lectures show this pattern
            avg_gap = statistics.mean([lg['gap'] for lg in lecture_gaps])
            lecture_names = [lg['lecture_name'] for lg in lecture_gaps]

            systemic_gaps.append(SystemicGap(
                concept="Surface Learning Pattern (Course-Wide)",
                direction=GapDirection.OVER_INVESTED,
                gap_appearances=len(lecture_gaps),
                segment_gap={},
                interpretation=f"Students perform well on quizzes (avg gap: {avg_gap:.1f} points) but struggle on evaluations in {len(lecture_gaps)} lectures, suggesting surface understanding without deep learning across the course.",
                lectures=lecture_names[:5],
            ))

        if self.config.verbose:
            print(f"   Total systemic gaps found: {len(systemic_gaps)}")

        return systemic_gaps


class PrerequisiteGapAggregator:
    """Identifies prerequisite gaps from query clusters."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.matcher = ConceptMatcher()
        self.clusterer = QueryClusterer(config)

    def aggregate_prerequisite_gaps(
        self,
        queries_df: pd.DataFrame,
        correct_df: pd.DataFrame,
    ) -> List[PrerequisiteGapCluster]:
        """
        Aggregate prerequisite gaps.

        Strategy (simplified for current data):
        1. Cluster all queries
        2. Find clusters that appear across multiple lectures
        3. If ≥3 students in ≥2 lectures ask about same topic, might be prerequisite gap
        4. Return top clusters as potential gaps

        Args:
            queries_df: queries.csv
            correct_df: correct.csv (known concepts in course)

        Returns:
            List of PrerequisiteGapCluster objects
        """
        if self.config.verbose:
            print("   [PrerequisiteGapAggregator] Clustering queries for potential prerequisite gaps...")

        if len(queries_df) < 3:
            return []

        # Get all queries
        all_queries = queries_df['query'].tolist()

        # Cluster queries
        query_clusters = self.clusterer.cluster_queries(all_queries, min_cluster_size=2)

        if self.config.verbose:
            print(f"   Analyzing {len(query_clusters)} query clusters for prerequisite gaps")

        # Track metrics per cluster
        cluster_data = defaultdict(lambda: {
            'lectures': set(),
            'students': set(),
            'queries': [],
        })

        # Map queries to clusters
        query_to_cluster = {}
        for cluster_id, queries in query_clusters.items():
            for query in queries:
                query_to_cluster[query] = cluster_id

        # Collect data per cluster
        for _, row in queries_df.iterrows():
            query_text = row['query']
            lecture_id = row['entity_id']
            student_id = row.get('user_id', '')

            if query_text in query_to_cluster:
                cluster_id = query_to_cluster[query_text]
                cluster_data[cluster_id]['lectures'].add(lecture_id)
                cluster_data[cluster_id]['students'].add(student_id)
                if len(cluster_data[cluster_id]['queries']) < 3:  # Keep first 3 as examples
                    cluster_data[cluster_id]['queries'].append(query_text)

        # Build PrerequisiteGapCluster objects
        prerequisite_gaps = []

        for cluster_id, data in cluster_data.items():
            # Check significance gate: ≥3 students AND ≥2 lectures
            if len(data['students']) >= 3 and len(data['lectures']) >= 2:
                # Use first query as topic name
                topic = data['queries'][0] if data['queries'] else f"Topic {cluster_id}"

                prerequisite_gaps.append(PrerequisiteGapCluster(
                    topic=topic,
                    unique_students=len(data['students']),
                    appearing_in_lectures=len(data['lectures']),
                    lecture_names=list(data['lectures'])[:5],  # First 5 lectures
                    out_of_scope_type="potential_prerequisite",  # Could be refined
                    example_queries=data['queries'][:3],
                ))

        # Sort by number of students (descending)
        prerequisite_gaps.sort(key=lambda x: x.unique_students, reverse=True)

        if self.config.verbose:
            print(f"   Found {len(prerequisite_gaps)} potential prerequisite gaps (≥3 students, ≥2 lectures)")

        # Return top 5
        return prerequisite_gaps[:5]


class CourseLayer1Pipeline:
    """Main pipeline for course-level Layer 1: cross-lesson aggregation FROM RAW DATA + CLASS REPORTS."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.recurring_detector = RecurringConceptDetector(config)
        self.problematic_detector = ProblematicLessonDetector(config)
        self.good_lesson_detector = GoodLessonDetector(config)
        self.success_detector = ConsistentSuccessDetector(config)
        self.gap_detector = SystemicGapDetector(config)
        self.prerequisite_aggregator = PrerequisiteGapAggregator(config)
        self.teaching_aggregator = TeachingInvestmentAggregator(config)

    def run(
        self,
        layer0_output: CourseLayer0Output,
        quiz_csv_path: Path,
        eval_csv_path: Path,
        queries_csv_path: Path,
        correct_csv_path: Path,
        output_dir: Optional[Path] = None,
    ) -> CourseLayer1Output:
        """
        Run course-level Layer 1 pipeline DIRECTLY FROM RAW CSV DATA.

        Args:
            layer0_output: Course Layer 0 output
            quiz_csv_path: Path to quiz.csv
            eval_csv_path: Path to eval.csv
            queries_csv_path: Path to queries.csv
            correct_csv_path: Path to correct.csv
            output_dir: Output directory

        Returns:
            CourseLayer1Output object
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "course_level" / "layer1"

        output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.verbose:
            print("=" * 80)
            print(f"COURSE-LEVEL LAYER 1: Cross-Lesson Aggregation (Run {layer0_output.run_number})")
            print("=" * 80)
            print("\n🔄 Working directly from raw CSV data (no class reports needed)")

        # Load raw CSV data
        if self.config.verbose:
            print("\n[1/6] Loading raw CSV data...")

        quiz_df = pd.read_csv(quiz_csv_path)
        eval_df = pd.read_csv(eval_csv_path)
        queries_df = pd.read_csv(queries_csv_path)
        correct_df = pd.read_csv(correct_csv_path)

        # Filter to only include lectures in our sequence
        included_lecture_ids = {lec.lecture_id for lec in layer0_output.lecture_sequence}
        quiz_df = quiz_df[quiz_df['lecture_id'].isin(included_lecture_ids)]
        eval_df = eval_df[eval_df['lecture_id'].isin(included_lecture_ids)]
        queries_df = queries_df[queries_df['entity_id'].isin(included_lecture_ids)]
        correct_df = correct_df[correct_df['lecture_id'].isin(included_lecture_ids)]

        if self.config.verbose:
            print(f"✅ Loaded {len(quiz_df)} quiz attempts, {len(eval_df)} eval attempts, {len(queries_df)} queries")

        # Calculate course averages from eval data
        course_eval_avg = eval_df['score'].mean() if len(eval_df) > 0 else 0.0
        course_quiz_avg = quiz_df['score'].mean() if len(quiz_df) > 0 else 0.0

        if self.config.verbose:
            print(f"\n📊 Course averages: eval={course_eval_avg:.1f}, quiz={course_quiz_avg:.1f}")

        # Load class-level reports for teaching investment data
        if self.config.verbose:
            print("\n[1.5/7] Loading class-level reports for teaching investment data...")

        # Determine class reports directory
        # Try multiple locations: output_dir, output_dir/learning_dashboard, and parent of output_dir
        possible_dirs = [
            self.config.paths.output_dir,  # /path/to/output
            self.config.paths.output_dir / "learning_dashboard",  # /path/to/output/learning_dashboard
            self.config.paths.output_dir.parent,  # /path/to (parent of output)
        ]

        class_reports_dir = None
        for dir_path in possible_dirs:
            if (dir_path / "lecturer_report.json").exists():
                class_reports_dir = dir_path
                if self.config.verbose:
                    print(f"   Found lecturer_report.json at: {dir_path}")
                break

        if class_reports_dir is None:
            # Default to output_dir if file not found
            class_reports_dir = self.config.paths.output_dir
            if self.config.verbose:
                print(f"   ⚠️  lecturer_report.json not found, using default: {class_reports_dir}")

        # Load class reports
        class_reports = self.teaching_aggregator.load_class_reports(
            layer0_output=layer0_output,
            class_reports_dir=class_reports_dir,
        )

        if self.config.verbose:
            print(f"✅ Loaded {len(class_reports)} class reports")

        # Aggregate in-class questions FIRST (needed for teaching investment calculation)
        inclass_questions = self.teaching_aggregator.aggregate_inclass_questions(
            class_reports=class_reports,
            layer0_output=layer0_output,
        )

        # Aggregate teaching investment (uses in-class questions data)
        teaching_investments = self.teaching_aggregator.aggregate_teaching_investment(
            class_reports=class_reports,
            layer0_output=layer0_output,
            inclass_questions=inclass_questions,  # Pass in-class questions
        )

        if self.config.verbose:
            print(f"✅ Aggregated teaching data for {len(teaching_investments)} concepts")
            print(f"✅ Found {len(inclass_questions)} in-class question instances")

        # Detect recurring concepts
        if self.config.verbose:
            print("\n[2/6] Detecting recurring concepts...")

        recurring_concepts = self.recurring_detector.detect_recurring_concepts(
            eval_df, correct_df, queries_df, layer0_output
        )

        if self.config.verbose:
            print(f"✅ Found {len(recurring_concepts)} recurring concepts")

        # Detect problematic lessons
        if self.config.verbose:
            print("\n[3/6] Detecting problematic lessons...")

        problematic_lessons = self.problematic_detector.detect_problematic_lessons(
            eval_df, quiz_df, queries_df, layer0_output, course_eval_avg
        )

        if self.config.verbose:
            print(f"✅ Found {len(problematic_lessons)} problematic lessons")

        # Detect good lessons
        if self.config.verbose:
            print("\n[3.5/6] Detecting good lessons...")

        good_lessons = self.good_lesson_detector.detect_good_lessons(
            eval_df, quiz_df, queries_df, layer0_output, course_eval_avg
        )

        if self.config.verbose:
            print(f"✅ Found {len(good_lessons)} good lessons")

        # Detect consistent successes
        if self.config.verbose:
            print("\n[4/6] Detecting consistent successes...")

        consistent_successes = self.success_detector.detect_consistent_successes(
            eval_df, quiz_df, correct_df
        )

        if self.config.verbose:
            print(f"✅ Found {len(consistent_successes)} consistent successes")

        # Detect systemic gaps
        if self.config.verbose:
            print("\n[5/6] Detecting systemic gaps...")

        systemic_gaps = self.gap_detector.detect_systemic_gaps(
            eval_df, quiz_df, correct_df,
            teaching_investments=teaching_investments  # Pass teaching investment data
        )

        if self.config.verbose:
            print(f"✅ Found {len(systemic_gaps)} systemic gaps")

        # Aggregate prerequisite gaps
        if self.config.verbose:
            print("\n[6/6] Aggregating prerequisite gaps...")

        prerequisite_gaps = self.prerequisite_aggregator.aggregate_prerequisite_gaps(
            queries_df, correct_df
        )

        if self.config.verbose:
            print(f"✅ Found {len(prerequisite_gaps)} prerequisite gap clusters")

        # Build output
        output = CourseLayer1Output(
            run_number=layer0_output.run_number,
            run_date=layer0_output.run_date,
            lectures_covered=len(layer0_output.lecture_sequence),
            total_lectures=layer0_output.total_lectures,
            engaged_n=layer0_output.engagement.engaged_n,
            course_eval_avg=course_eval_avg,
            course_quiz_avg=course_quiz_avg,
            recurring_concepts=recurring_concepts,
            problematic_lessons=problematic_lessons,
            good_lessons=good_lessons,
            consistent_successes=consistent_successes,
            systemic_gaps=systemic_gaps,
            prerequisite_gaps=prerequisite_gaps,
        )

        # Save output (including teaching investment data)
        self._save_output(output, output_dir, teaching_investments, inclass_questions)

        if self.config.verbose:
            print(f"\n✅ Course Layer 1 complete!")
            print(f"   Output saved to: {output_dir}")

        return output

    def _save_output(
        self,
        output: CourseLayer1Output,
        output_dir: Path,
        teaching_investments: Dict[str, Dict],
        inclass_questions: List[Dict],
    ):
        """Save Layer 1 output to JSON."""
        output_path = output_dir / "course_layer1_output.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved course Layer 1 output to {output_path}")

        # Save teaching investment data separately
        teaching_inv_path = output_dir / "teaching_investments.json"
        with open(teaching_inv_path, 'w', encoding='utf-8') as f:
            json.dump(teaching_investments, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved teaching investment data to {teaching_inv_path}")

        # Save in-class questions separately
        inclass_q_path = output_dir / "inclass_questions.json"
        with open(inclass_q_path, 'w', encoding='utf-8') as f:
            json.dump(inclass_questions, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved in-class questions to {inclass_q_path}")