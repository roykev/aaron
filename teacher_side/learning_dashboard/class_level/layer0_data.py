"""
Layer 0: Data Cleaning & Deduplication
Loads raw data and produces clean student signals.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

import pandas as pd

from ..common.models import (
    StudentSignal,
    QuerySignal,
    EvalFailureSignal,
    InClassQuestionSignal,
    Concept,
    Section,
    Example,
    InClassInteraction,
    TimeRange,
)
from ..common.config import LearningDashboardConfig


class DataLoader:
    """Loads and parses all input data files."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def load_queries(self, lecture_id: Optional[str] = None) -> pd.DataFrame:
        """
        Load queries.csv and filter to lecture-level queries.

        Args:
            lecture_id: If provided, filter to this specific lecture

        Returns:
            DataFrame with columns: time, query, name, entity_id, user_id, source_type
        """
        df = pd.read_csv(self.config.paths.queries_csv, encoding='utf-8')

        # Filter to lecture-level queries only
        df = df[df['source_type'] == 'lecture'].copy()

        # Filter to specific lecture if requested
        if lecture_id:
            df = df[df['entity_id'] == lecture_id].copy()

        return df.reset_index(drop=True)

    def load_quiz_or_eval(self, file_path: Path, lecture_id: Optional[str] = None) -> pd.DataFrame:
        """
        Load quiz.csv or eval.csv.

        Args:
            file_path: Path to quiz.csv or eval.csv
            lecture_id: If provided, filter to this specific lecture

        Returns:
            DataFrame with student assessment data
        """
        df = pd.read_csv(file_path, encoding='utf-8')

        # Filter to specific lecture if requested
        if lecture_id:
            df = df[df['lecture_id'] == lecture_id].copy()

        return df.reset_index(drop=True)

    def load_correct_csv(self) -> pd.DataFrame:
        """
        Load correct.csv (question bank).

        Returns:
            DataFrame with lecture_id, name, quiz (JSON), evaluation (JSON)
        """
        return pd.read_csv(self.config.paths.correct_csv, encoding='utf-8')

    def load_concepts(self) -> List[Concept]:
        """
        Load concepts from concepts.txt/json.

        Returns:
            List of Concept objects
        """
        with open(self.config.paths.concepts_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        concepts = []
        for c in data.get('concepts', []):
            times = [
                TimeRange(start=t['start'], end=t['end'])
                for t in c.get('times', [])
            ]
            concepts.append(Concept(concept=c['concept'], times=times))

        return concepts

    def load_output_txt(self) -> Dict[str, any]:
        """
        Load output.txt and parse sections, examples, interactions.

        Returns:
            Dict with 'sections', 'examples', 'interactions', 'difficult_topics'
        """
        content = self.config.paths.output_txt.read_text(encoding='utf-8')

        result = {
            'title': '',
            'sections': [],
            'examples': [],
            'interactions': [],
            'difficult_topics': []
        }

        # Parse title
        title_match = re.search(r'### title ###\s*\{"title":\s*"([^"]+)"\}', content)
        if title_match:
            result['title'] = title_match.group(1)

        # Parse sections (CSV format)
        sections_match = re.search(
            r'### sections ###\s*chapter_num,from,to,chapter_title,duration\s*(.*?)\s*###',
            content,
            re.DOTALL
        )
        if sections_match:
            section_lines = sections_match.group(1).strip().split('\n')
            for line in section_lines:
                parts = line.split(',')
                if len(parts) >= 5:
                    result['sections'].append(Section(
                        chapter_num=int(parts[0]),
                        start_time=parts[1],
                        end_time=parts[2],
                        title=parts[3].strip('"'),
                        duration=parts[4]
                    ))

        # Parse examples (CSV format)
        examples_match = re.search(
            r'### examples ###\s*נושא,דוגמה,מקור\s*(.*?)\s*###',
            content,
            re.DOTALL
        )
        if examples_match:
            example_lines = examples_match.group(1).strip().split('\n')
            for line in example_lines:
                parts = line.split(',', 2)
                if len(parts) >= 3:
                    result['examples'].append(Example(
                        topic=parts[0].strip(),
                        example=parts[1].strip(),
                        source=parts[2].strip()
                    ))

        # Parse interactions (CSV format)
        interactions_match = re.search(
            r'### interaction ###\s*זמן,סוג,תיאור\s*(.*?)\s*###',
            content,
            re.DOTALL
        )
        if interactions_match:
            interaction_lines = interactions_match.group(1).strip().split('\n')
            for line in interaction_lines:
                parts = line.split(',', 2)
                if len(parts) >= 3:
                    result['interactions'].append(InClassInteraction(
                        time=parts[0].strip(),
                        interaction_type=parts[1].strip(),
                        description=parts[2].strip()
                    ))

        return result


class SignalExtractor:
    """Extracts and cleans student signals from raw data."""

    def __init__(self, config: LearningDashboardConfig, loader: DataLoader):
        self.config = config
        self.loader = loader

    def extract_query_signals(
        self,
        queries_df: pd.DataFrame
    ) -> List[QuerySignal]:
        """
        Extract query signals from queries DataFrame.

        Args:
            queries_df: Queries DataFrame from DataLoader

        Returns:
            List of QuerySignal objects
        """
        signals = []

        for _, row in queries_df.iterrows():
            signal = QuerySignal(
                text=str(row['query']),
                normalized_query=self._normalize_query(str(row['query'])),
                student_id=str(row.get('user_id', '')),
                lecture_id=str(row.get('entity_id', '')),
                lecture_name=str(row.get('name', '')),
                timestamp=str(row.get('time', '')),
                source_type=str(row.get('source_type', 'lecture'))
            )

            # Apply noise filter
            if not self._is_noise_query(signal):
                signals.append(signal)

        return signals

    def extract_eval_failure_signals(
        self,
        eval_df: pd.DataFrame,
        correct_df: pd.DataFrame
    ) -> List[EvalFailureSignal]:
        """
        Extract eval failure signals from evaluation DataFrame.

        Args:
            eval_df: Evaluation DataFrame
            correct_df: Correct answers DataFrame (question bank)

        Returns:
            List of EvalFailureSignal objects
        """
        signals = []

        # Build question text map from correct_df
        question_map = self._build_question_map(correct_df, 'evaluation')

        for _, row in eval_df.iterrows():
            lecture_id = str(row['lecture_id'])
            student_email = str(row['email'])
            lecture_name = str(row['name'])

            # Parse answers JSON
            try:
                answers = json.loads(row['answers'])
            except (json.JSONDecodeError, TypeError):
                continue

            # Extract failed questions
            for q_num_str, q_data in answers.items():
                if not isinstance(q_data, dict):
                    continue

                is_correct = q_data.get('correct', True)

                if not is_correct:  # Failed question
                    q_num = int(q_num_str)
                    question_text = question_map.get((lecture_id, q_num), f"Question {q_num}")

                    signals.append(EvalFailureSignal(
                        text=question_text,
                        question_text=question_text,
                        question_number=q_num,
                        student_id=student_email,
                        lecture_id=lecture_id,
                        lecture_name=lecture_name,
                    ))

        return signals

    def extract_inclass_question_signals(
        self,
        interactions: List[InClassInteraction],
        lecture_id: str = "",
        lecture_name: str = ""
    ) -> List[InClassQuestionSignal]:
        """
        Extract in-class question signals from interactions.

        Args:
            interactions: List of InClassInteraction objects
            lecture_id: Lecture ID to attach to signals
            lecture_name: Lecture name to attach to signals

        Returns:
            List of InClassQuestionSignal objects
        """
        signals = []

        for interaction in interactions:
            # Filter to questions only
            if 'שאלת' in interaction.interaction_type or 'question' in interaction.interaction_type.lower():
                signals.append(InClassQuestionSignal(
                    text=interaction.description,
                    timestamp=interaction.time,
                    lecture_id=lecture_id,
                    lecture_name=lecture_name,
                ))

        return signals

    def _normalize_query(self, text: str) -> str:
        """
        Normalize query text for deduplication.

        Args:
            text: Raw query text

        Returns:
            Normalized query text
        """
        # Unicode normalization
        text = unicodedata.normalize('NFKC', text)

        # Lowercase
        text = text.lower()

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove punctuation (keep alphanumeric and Hebrew)
        text = re.sub(r'[^\w\s\u0590-\u05FF]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _is_noise_query(self, signal: QuerySignal) -> bool:
        """
        Check if query is noise (gibberish, session-close terms, etc.).

        Args:
            signal: QuerySignal to check

        Returns:
            True if query should be filtered out
        """
        normalized = signal.normalized_query

        # Empty or too short
        if len(normalized) < self.config.noise_filter.min_query_length:
            return True

        # Session-close terms
        for term in self.config.noise_filter.session_close_terms:
            if normalized == term.lower():
                return True

        # Keyboard gibberish (only English chars in Hebrew context)
        if re.match(self.config.noise_filter.keyboard_gibberish_pattern, normalized):
            # Check if text contains Hebrew - if not, might be gibberish
            if not re.search(r'[\u0590-\u05FF]', normalized):
                return True

        return False

    def _build_question_map(
        self,
        correct_df: pd.DataFrame,
        source: str  # 'quiz' or 'evaluation'
    ) -> Dict[Tuple[str, int], str]:
        """
        Build mapping of (lecture_id, question_number) -> question_text.

        Args:
            correct_df: DataFrame from correct.csv
            source: 'quiz' or 'evaluation'

        Returns:
            Dict mapping (lecture_id, question_num) to question text
        """
        question_map = {}

        for _, row in correct_df.iterrows():
            lecture_id = str(row['lecture_id'])

            try:
                source_data = json.loads(row[source])
            except (json.JSONDecodeError, TypeError):
                continue

            questions = source_data.get('questions', [])

            for i, q in enumerate(questions, start=1):
                question_text = q.get('question', f'Question {i}')
                question_map[(lecture_id, i)] = question_text

        return question_map


class SignalDeduplicator:
    """Deduplicates student signals per student."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def deduplicate_queries(
        self,
        signals: List[QuerySignal]
    ) -> List[QuerySignal]:
        """
        Deduplicate query signals per student.
        Keep only one signal per (student, normalized_query).

        Args:
            signals: List of QuerySignal objects

        Returns:
            Deduplicated list
        """
        seen: Set[Tuple[str, str]] = set()
        deduped = []

        for signal in signals:
            key = (signal.student_id, signal.normalized_query)

            if key not in seen:
                seen.add(key)
                deduped.append(signal)

        return deduped

    def deduplicate_eval_failures(
        self,
        signals: List[EvalFailureSignal]
    ) -> List[EvalFailureSignal]:
        """
        Deduplicate eval failure signals.
        Already unique per (student, question_number), but filter just in case.

        Args:
            signals: List of EvalFailureSignal objects

        Returns:
            Deduplicated list
        """
        seen: Set[Tuple[str, int]] = set()
        deduped = []

        for signal in signals:
            key = (signal.student_id, signal.question_number)

            if key not in seen:
                seen.add(key)
                deduped.append(signal)

        return deduped

    def deduplicate_inclass_questions(
        self,
        signals: List[InClassQuestionSignal]
    ) -> List[InClassQuestionSignal]:
        """
        In-class questions are already discrete events, no deduplication needed.

        Args:
            signals: List of InClassQuestionSignal objects

        Returns:
            Same list (no deduplication)
        """
        return signals


class Layer0Pipeline:
    """Main pipeline for Layer 0: data loading, cleaning, deduplication."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.loader = DataLoader(config)
        self.extractor = SignalExtractor(config, self.loader)
        self.deduplicator = SignalDeduplicator(config)

    def run(self, lecture_id: Optional[str] = None) -> Dict[str, any]:
        """
        Run the complete Layer 0 pipeline.

        Args:
            lecture_id: Specific lecture to analyze (optional)

        Returns:
            Dict with:
                - 'signals': List[StudentSignal] - all cleaned signals
                - 'concepts': List[Concept]
                - 'sections': List[Section]
                - 'examples': List[Example]
                - 'interactions': List[InClassInteraction]
                - 'metadata': Dict with counts and stats
        """
        # Use configured lecture_id if not provided
        if lecture_id is None:
            lecture_id = self.config.lecture_id

        # Load data
        queries_df = self.loader.load_queries(lecture_id)
        eval_df = self.loader.load_quiz_or_eval(self.config.paths.eval_csv, lecture_id)
        correct_df = self.loader.load_correct_csv()
        concepts = self.loader.load_concepts()
        output_data = self.loader.load_output_txt()

        # Extract signals
        query_signals = self.extractor.extract_query_signals(queries_df)
        eval_failure_signals = self.extractor.extract_eval_failure_signals(eval_df, correct_df)
        inclass_question_signals = self.extractor.extract_inclass_question_signals(
            output_data['interactions'],
            lecture_id=lecture_id or "",
            lecture_name=output_data.get('title', '')
        )

        # Deduplicate
        query_signals = self.deduplicator.deduplicate_queries(query_signals)
        eval_failure_signals = self.deduplicator.deduplicate_eval_failures(eval_failure_signals)
        inclass_question_signals = self.deduplicator.deduplicate_inclass_questions(inclass_question_signals)

        # Combine all signals
        all_signals: List[StudentSignal] = []
        all_signals.extend(query_signals)
        all_signals.extend(eval_failure_signals)
        all_signals.extend(inclass_question_signals)

        # Compute metadata
        metadata = {
            'total_signals': len(all_signals),
            'query_signals': len(query_signals),
            'eval_failure_signals': len(eval_failure_signals),
            'inclass_question_signals': len(inclass_question_signals),
            'unique_query_students': len(set(s.student_id for s in query_signals if s.student_id)),
            'unique_eval_students': len(set(s.student_id for s in eval_failure_signals if s.student_id)),
            'lecture_id': lecture_id,
            'lecture_name': output_data.get('title', ''),
        }

        return {
            'signals': all_signals,
            'concepts': concepts,
            'sections': output_data['sections'],
            'examples': output_data['examples'],
            'interactions': output_data['interactions'],
            'metadata': metadata,
        }