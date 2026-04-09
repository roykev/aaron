"""
Layer 2: Ranking & Evidence Packaging
Ranks clusters by significance and packages evidence for the LLM.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd

from ..common.models import (
    SignalCluster,
    Concept,
    Section,
    TeachingInvestment,
    IssueEvidenceBundle,
    WorkedWellEvidenceBundle,
    GapEvidenceBundle,
    OutOfScopeCluster,
    LessonReliability,
    LessonShape,
    Layer2Output,
    SignalType,
    EvidenceStrength,
    ReliabilityFlag,
    GapDirection,
)
from ..common.config import LearningDashboardConfig


class IssueRanker:
    """Ranks clusters as issues with significance gates."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def rank_issues(
        self,
        clusters: List[SignalCluster],
        eval_participants: int,
    ) -> List[IssueEvidenceBundle]:
        """
        Rank clusters as issues with significance gate.

        Gate: corroboration_score >= 3 AND evidence_strength in {moderate, sufficient}

        Args:
            clusters: List of signal clusters
            eval_participants: Number of students who took evaluation

        Returns:
            List of up to 3 issue evidence bundles
        """
        # Apply significance gate
        passing_clusters = [
            c for c in clusters
            if c.corroboration_score >= self.config.significance.min_corroboration_score
            and c.evidence_strength in (EvidenceStrength.MODERATE, EvidenceStrength.SUFFICIENT)
            and c.matched_section is not None  # Must have been mapped to lesson content
        ]

        # Sort by corroboration score descending
        passing_clusters.sort(key=lambda c: c.corroboration_score, reverse=True)

        # Take top 3
        top_clusters = passing_clusters[:self.config.ranking.max_issues]

        # Build evidence bundles
        issues = []
        for cluster in top_clusters:
            # Count signal types
            eval_failure_n = sum(
                1 for s in cluster.signals
                if s.signal_type == SignalType.EVAL_FAILURE
            )
            query_student_count = len(set(
                s.student_id for s in cluster.signals
                if s.signal_type == SignalType.QUERY and s.student_id
            ))

            # Compute eval failure rate (only if N >= 5)
            eval_failure_rate = None
            if eval_participants >= 5 and eval_failure_n > 0:
                eval_failure_rate = eval_failure_n / eval_participants

            # Check if in-class question was raised
            inclass_raised = SignalType.INCLASS_QUESTION in cluster.signal_types_present

            # Extract difficult eval questions (from EvalFailureSignal)
            difficult_eval_questions = []
            for signal in cluster.signals:
                if signal.signal_type == SignalType.EVAL_FAILURE:
                    # Get question_text if it's an EvalFailureSignal
                    if hasattr(signal, 'question_text') and signal.question_text:
                        difficult_eval_questions.append(signal.question_text)
            # Deduplicate and take up to 3 examples
            difficult_eval_questions = list(dict.fromkeys(difficult_eval_questions))[:3]

            # Generate better issue title (use section or concept, not question text)
            issue_title = cluster.matched_section or cluster.matched_concept or cluster.cluster_label
            # Clean up title - remove long question marks or explanations
            if len(issue_title) > 80:
                issue_title = issue_title[:77] + "..."

            # Build evidence bundle
            issue = IssueEvidenceBundle(
                cluster_label=cluster.cluster_label,
                matched_concept=cluster.matched_concept,
                matched_section=cluster.matched_section,
                corroboration_score=cluster.corroboration_score,
                unique_students=cluster.unique_students,
                signal_types=[str(t) for t in cluster.signal_types_present],
                eval_failure_n=eval_failure_n,
                eval_failure_rate=eval_failure_rate,
                query_student_count=query_student_count,
                query_types={},  # TODO: implement query type classification
                evidence_strength=str(cluster.evidence_strength),
                top_signal_examples=cluster.example_texts[:3],
                inclass_question_raised=inclass_raised,
                difficult_eval_questions=difficult_eval_questions,
                issue_title=issue_title,
            )

            issues.append(issue)

        return issues


class WorkedWellRanker:
    """Ranks concepts that worked well (requires both student AND teacher signals)."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def rank_worked_well(
        self,
        clusters: List[SignalCluster],
        teaching_investments: Dict[str, TeachingInvestment],
        eval_df: pd.DataFrame,
        concept_to_sections: Dict[str, List[str]],
    ) -> List[WorkedWellEvidenceBundle]:
        """
        Rank concepts that worked well.

        Requires BOTH:
        - Student side: low eval failure + no confusion queries
        - Teacher side: example used OR in-class quiet OR meaningful time

        Args:
            clusters: List of signal clusters
            teaching_investments: Teaching investment per concept
            eval_df: Evaluation dataframe
            concept_to_sections: Mapping of concepts to sections

        Returns:
            List of up to 2 worked-well evidence bundles
        """
        # Group clusters by concept
        clusters_by_concept: Dict[str, List[SignalCluster]] = {}
        for cluster in clusters:
            if cluster.matched_concept:
                if cluster.matched_concept not in clusters_by_concept:
                    clusters_by_concept[cluster.matched_concept] = []
                clusters_by_concept[cluster.matched_concept].append(cluster)

        # Evaluate each concept
        candidates = []

        for concept, concept_clusters in clusters_by_concept.items():
            investment = teaching_investments.get(concept)
            if not investment:
                continue

            # Student-side check: low eval failure
            # Count total eval failures for this concept
            total_eval_failures = sum(
                sum(1 for s in c.signals if s.signal_type == SignalType.EVAL_FAILURE)
                for c in concept_clusters
            )

            eval_participants = len(eval_df) if not eval_df.empty else 0
            if eval_participants == 0:
                continue

            eval_failure_rate = total_eval_failures / eval_participants
            eval_success_rate = 1.0 - eval_failure_rate
            eval_success_n = eval_participants - total_eval_failures

            # Student-side gate: low failure
            if eval_failure_rate >= self.config.significance.max_eval_failure_rate:
                continue

            # Student-side: check query signal
            query_count = sum(
                sum(1 for s in c.signals if s.signal_type == SignalType.QUERY)
                for c in concept_clusters
            )

            if query_count > 0:
                # Has queries - check if they're just curiosity (single word)
                # For now, skip if has queries
                # TODO: implement query type classification
                continue

            query_signal = "silent" if query_count == 0 else "curiosity_only"

            # Teacher-side gate: at least one of example / no friction / meaningful time
            teacher_signal_present = (
                investment.example_used
                or investment.inclass_questions_n == 0
                or investment.time_pct > 0.05
            )

            if not teacher_signal_present:
                continue

            # Confidence classification
            if (investment.example_used
                and investment.inclass_questions_n == 0
                and eval_failure_rate < 0.15
                and query_count == 0):
                confidence = "clear_win"
            else:
                confidence = "moderate"

            # Build why explanation
            why_parts = []
            if investment.example_used:
                why_parts.append("example used in class")
            if investment.inclass_questions_n == 0:
                why_parts.append("zero in-class friction")
            if query_count == 0:
                why_parts.append("zero post-class confusion")
            why_parts.append(f"{eval_success_rate*100:.0f}% eval success")

            why = " + ".join(why_parts)

            # Get section
            sections = concept_to_sections.get(concept, [])
            section = sections[0] if sections else "Unknown section"

            bundle = WorkedWellEvidenceBundle(
                concept=concept,
                eval_success_rate=eval_success_rate,
                eval_success_n=eval_success_n,
                query_signal=query_signal,
                example_used=investment.example_used,
                inclass_questions=investment.inclass_questions_n,
                teach_minutes=investment.time_minutes,
                confidence=confidence,
                why=why,
            )

            candidates.append((eval_success_rate, bundle))

        # Sort by eval success rate descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Take top 2
        return [bundle for _, bundle in candidates[:self.config.ranking.max_worked_well]]


class GapAnalyzer:
    """Analyzes teaching-learning gaps."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def analyze_gaps(
        self,
        clusters: List[SignalCluster],
        teaching_investments: Dict[str, TeachingInvestment],
        eval_df: pd.DataFrame,
        concept_to_sections: Dict[str, List[str]],
    ) -> List[GapEvidenceBundle]:
        """
        Analyze teaching-learning gaps.

        Gate: abs(raw_gap_score) > 0.15 AND evidence_strength >= moderate

        Args:
            clusters: List of signal clusters
            teaching_investments: Teaching investment per concept
            eval_df: Evaluation dataframe
            concept_to_sections: Mapping of concepts to sections

        Returns:
            List of up to 3 gap evidence bundles
        """
        # Group clusters by concept
        clusters_by_concept: Dict[str, List[SignalCluster]] = {}
        for cluster in clusters:
            if cluster.matched_concept:
                if cluster.matched_concept not in clusters_by_concept:
                    clusters_by_concept[cluster.matched_concept] = []
                clusters_by_concept[cluster.matched_concept].append(cluster)

        # Evaluate each concept
        candidates = []

        eval_participants = len(eval_df) if not eval_df.empty else 1  # Avoid division by zero

        for concept, concept_clusters in clusters_by_concept.items():
            investment = teaching_investments.get(concept)
            if not investment:
                continue

            # Compute learning outcome score (struggle)
            total_eval_failures = sum(
                sum(1 for s in c.signals if s.signal_type == SignalType.EVAL_FAILURE)
                for c in concept_clusters
            )
            query_student_count = len(set(
                s.student_id for s in sum([c.signals for c in concept_clusters], [])
                if s.signal_type == SignalType.QUERY and s.student_id
            ))

            eval_failure_rate = total_eval_failures / eval_participants
            learning_struggle_score = eval_failure_rate + (query_student_count / eval_participants) * 0.5

            # Compute gap score: investment - outcome
            # High investment + high struggle = over-invested
            # Low investment + high queries = under-taught
            raw_gap_score = investment.teaching_investment_score - learning_struggle_score

            # Apply significance gate
            if abs(raw_gap_score) <= self.config.significance.min_gap_score:
                continue

            # Check evidence strength from clusters
            max_evidence = max(
                (c.evidence_strength for c in concept_clusters),
                default=EvidenceStrength.WEAK
            )
            if max_evidence == EvidenceStrength.WEAK:
                continue

            # Classify direction
            if raw_gap_score > 0.15:
                # High investment, low success
                if investment.assessment_weight > 0.15 and eval_failure_rate > 0.50:
                    direction = GapDirection.ASSESSED_NOT_ABSORBED
                else:
                    direction = GapDirection.OVER_INVESTED
            elif raw_gap_score < -0.15:
                # Low investment, high curiosity
                direction = GapDirection.UNDER_TAUGHT
            else:
                direction = GapDirection.CALIBRATED

            # Skip calibrated
            if direction == GapDirection.CALIBRATED:
                continue

            # Build teaching investment dict
            teaching_inv_dict = {
                'time_minutes': investment.time_minutes,
                'time_pct': investment.time_pct,
                'example_used': investment.example_used,
                'inclass_questions': investment.inclass_questions_n,
                'assessment_pct': investment.assessment_weight,
            }

            # Build learning outcome dict
            learning_outcome_dict = {
                'eval_failure_rate': eval_failure_rate,
                'eval_failure_n': total_eval_failures,
                'query_student_count': query_student_count,
            }

            # Build interpretation hint
            if direction == GapDirection.OVER_INVESTED:
                hint = f"high teaching time ({investment.time_pct*100:.0f}%) + high confusion"
            elif direction == GapDirection.UNDER_TAUGHT:
                hint = f"low teaching time ({investment.time_pct*100:.0f}%) + high student curiosity"
            elif direction == GapDirection.ASSESSED_NOT_ABSORBED:
                hint = f"heavily assessed ({investment.assessment_weight*100:.0f}%) + high failure"
            else:
                hint = "calibrated"

            # Get section
            sections = concept_to_sections.get(concept, [])
            section = sections[0] if sections else "Unknown section"

            bundle = GapEvidenceBundle(
                concept=concept,
                direction=direction,
                teaching_investment=teaching_inv_dict,
                learning_outcome=learning_outcome_dict,
                raw_gap_score=raw_gap_score,
                interpretation_hint=hint,
            )

            candidates.append((abs(raw_gap_score), bundle))

        # Sort by absolute gap score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Take top 3
        return [bundle for _, bundle in candidates[:self.config.ranking.max_gaps]]


class OutOfScopeDetector:
    """Detects out-of-scope queries (topics not covered in lesson)."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def detect_out_of_scope(
        self,
        clusters: List[SignalCluster],
    ) -> List[OutOfScopeCluster]:
        """
        Detect out-of-scope clusters.

        Gate: mapping_confidence == "none" AND unique_students >= 2

        Args:
            clusters: List of signal clusters

        Returns:
            List of out-of-scope clusters
        """
        out_of_scope = []

        for cluster in clusters:
            # Check if not mapped to lesson content
            if cluster.mapping_confidence != "none":
                continue

            # Check student count gate
            if cluster.unique_students < self.config.significance.min_students_out_of_scope:
                continue

            # Classify type (placeholder - would need more analysis)
            out_of_scope_type = "curiosity"

            # Get example queries
            example_queries = cluster.example_texts[:3]

            # Build note
            note = f"{cluster.unique_students} students searched for this topic not covered in lesson"

            out_of_scope_cluster = OutOfScopeCluster(
                cluster_label=cluster.cluster_label,
                out_of_scope_type=out_of_scope_type,
                unique_students=cluster.unique_students,
                example_queries=example_queries,
                note=note,
            )

            out_of_scope.append(out_of_scope_cluster)

        return out_of_scope


class Layer2Pipeline:
    """Main pipeline for Layer 2: ranking and evidence packaging."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.issue_ranker = IssueRanker(config)
        self.worked_well_ranker = WorkedWellRanker(config)
        self.gap_analyzer = GapAnalyzer(config)
        self.out_of_scope_detector = OutOfScopeDetector(config)

    def run(
        self,
        clusters: List[SignalCluster],
        teaching_investments: Dict[str, TeachingInvestment],
        concept_to_sections: Dict[str, List[str]],
        participation_metrics: Dict,
        quiz_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        lecture_id: str,
        lecture_name: str,
        total_lesson_minutes: float,
        concept_count: int,
        output_dir: Optional[Path] = None,
    ) -> Layer2Output:
        """
        Run the complete Layer 2 pipeline.

        Args:
            clusters: List of signal clusters from Layer 1
            teaching_investments: Teaching investment per concept from Layer 1.5
            concept_to_sections: Mapping of concepts to sections from Layer 1.5
            participation_metrics: Participation metrics from Layer 1
            quiz_df: Quiz dataframe
            eval_df: Evaluation dataframe
            lecture_id: Lecture ID
            lecture_name: Lecture name
            total_lesson_minutes: Total lesson duration
            concept_count: Number of concepts in lesson
            output_dir: Directory to save outputs

        Returns:
            Layer2Output object ready for Layer 3 LLM
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "layer2"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Build reliability metrics
        reliability = LessonReliability(
            eval_participants=participation_metrics['eval_participants'],
            query_participants=participation_metrics['query_participants'],
            flag=ReliabilityFlag(participation_metrics['reliability_flag']),
            flag_reason=participation_metrics['reliability_reason'],
        )

        # Build lesson shape
        lesson_quiz_avg = participation_metrics.get('lesson_quiz_avg', 0.0)
        lesson_eval_avg = participation_metrics.get('lesson_eval_avg', 0.0)
        lesson_gap = participation_metrics.get('lesson_gap', 0.0)
        lesson_gap_flag = participation_metrics.get('lesson_gap_flag', 'unknown')

        # Classify density
        if concept_count / total_lesson_minutes > 0.25:
            density = "high"
        elif concept_count / total_lesson_minutes > 0.15:
            density = "medium"
        else:
            density = "low"

        lesson_shape = LessonShape(
            total_minutes=total_lesson_minutes,
            concept_count=concept_count,
            density=density,
            lesson_quiz_avg=lesson_quiz_avg or 0.0,
            lesson_eval_avg=lesson_eval_avg or 0.0,
            lesson_gap=lesson_gap or 0.0,
            lesson_gap_flag=lesson_gap_flag,
        )

        # Rank issues
        if self.config.verbose:
            print("Ranking issues...")

        issues = self.issue_ranker.rank_issues(
            clusters,
            participation_metrics['eval_participants'],
        )

        if self.config.verbose:
            print(f"Found {len(issues)} significant issues")

        # Rank worked-well
        if self.config.verbose:
            print("Ranking worked-well concepts...")

        worked_well = self.worked_well_ranker.rank_worked_well(
            clusters,
            teaching_investments,
            eval_df,
            concept_to_sections,
        )

        if self.config.verbose:
            print(f"Found {len(worked_well)} worked-well concepts")

        # Analyze gaps
        if self.config.verbose:
            print("Analyzing teaching-learning gaps...")

        gaps = self.gap_analyzer.analyze_gaps(
            clusters,
            teaching_investments,
            eval_df,
            concept_to_sections,
        )

        if self.config.verbose:
            print(f"Found {len(gaps)} significant gaps")

        # Detect out-of-scope
        if self.config.verbose:
            print("Detecting out-of-scope queries...")

        out_of_scope = self.out_of_scope_detector.detect_out_of_scope(clusters)

        if self.config.verbose:
            print(f"Found {len(out_of_scope)} out-of-scope clusters")

        # Build output
        output = Layer2Output(
            lecture_id=lecture_id,
            lecture_name=lecture_name,
            reliability=reliability,
            lesson_shape=lesson_shape,
            issues=issues,
            worked_well=worked_well,
            gaps=gaps,
            out_of_scope=out_of_scope,
        )

        # Save output
        self._save_output(output, output_dir)

        return output

    def _save_output(self, output: Layer2Output, output_dir: Path):
        """Save Layer 2 output to JSON."""
        output_path = output_dir / "layer2_output.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved Layer 2 output to {output_path}")