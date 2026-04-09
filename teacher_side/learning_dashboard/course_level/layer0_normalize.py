"""
Course-Level Layer 0: Normalization & Segmentation

Normalizes engagement, segments students, and extracts revisit signals.
No LLM calls - pure Python logic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

import pandas as pd

from ..common.models import (
    StudentSegment,
    StudentProfile,
    RevisitSignal,
    LectureMetadata,
    EngagementMetrics,
    RevisitMetrics,
    CourseLayer0Output,
)
from ..common.config import LearningDashboardConfig


class StudentRosterLoader:
    """Loads student roster from JSON."""

    def load_roster(self, roster_path: Path) -> List[Dict[str, str]]:
        """
        Load student roster.

        Expected format:
        [
          {"email": "student@ono.ac.il", "name": "..."}
        ]

        Returns:
            List of student dictionaries
        """
        if not roster_path.exists():
            raise FileNotFoundError(f"Student roster not found: {roster_path}")

        with open(roster_path, 'r', encoding='utf-8') as f:
            roster = json.load(f)

        return roster


class LectureSequenceLoader:
    """Loads lecture sequence metadata."""

    def load_sequence(self, sequence_path: Path, class_reports_dir: Path) -> List[LectureMetadata]:
        """
        Load lecture sequence with class report paths.

        Expected format:
        [
          {"lecture_id": "9b6096ef-...", "name": "שיעור 4"}
        ]

        Note: "date" field is optional. If not provided, revisit extraction will be skipped.

        Args:
            sequence_path: Path to lecture_sequence.json
            class_reports_dir: Directory containing class-level Layer 2 JSONs

        Returns:
            List of LectureMetadata objects
        """
        if not sequence_path.exists():
            raise FileNotFoundError(f"Lecture sequence not found: {sequence_path}")

        with open(sequence_path, 'r', encoding='utf-8') as f:
            sequence_data = json.load(f)

        lectures = []
        for idx, lecture_data in enumerate(sequence_data, start=1):
            lecture_id = lecture_data['lecture_id']

            # Check if class report exists
            class_report_path = class_reports_dir / lecture_id / "layer2" / "layer2_output.json"
            has_report = class_report_path.exists()

            lecture = LectureMetadata(
                lecture_id=lecture_id,
                name=lecture_data['name'],
                date=lecture_data.get('date', f"Lecture {idx}"),  # Use sequence number if date not provided
                sequence_number=idx,
                class_report_path=str(class_report_path) if has_report else None,
                has_class_report=has_report,
            )
            lectures.append(lecture)

        return lectures


class StudentSegmentationEngine:
    """Segments students based on performance."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def build_student_profiles(
        self,
        roster: List[Dict[str, str]],
        quiz_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        queries_df: pd.DataFrame,
    ) -> List[StudentProfile]:
        """
        Build student profiles with engagement and performance metrics.

        Args:
            roster: Student roster
            quiz_df: Quiz scores (all lectures)
            eval_df: Eval scores (all lectures)
            queries_df: All queries

        Returns:
            List of StudentProfile objects
        """
        profiles = []

        for student_data in roster:
            email = student_data['email']

            profile = StudentProfile(
                email=email,
                name=student_data.get('name'),
            )

            # Get student's quiz/eval data (by email)
            student_quizzes = quiz_df[quiz_df['email'] == email]
            student_evals = eval_df[eval_df['email'] == email]

            # Note: We'll count unique queries per student later after we deduplicate
            # queries.csv uses user_id, not email, so we can't match directly here

            # Engagement metrics
            profile.attempted_quizzes = len(student_quizzes)
            profile.attempted_evals = len(student_evals)
            profile.query_count = 0  # Will be populated after query deduplication
            profile.is_engaged = (
                profile.attempted_quizzes > 0
                or profile.attempted_evals > 0
            )

            # Performance metrics
            if not student_evals.empty:
                eval_scores = student_evals['score'].tolist()
                profile.avg_eval_score = statistics.mean(eval_scores)

                if len(eval_scores) >= 2:
                    profile.eval_consistency = statistics.stdev(eval_scores)

            if not student_quizzes.empty:
                profile.avg_quiz_score = student_quizzes['score'].mean()

            # Lectures attended
            profile.lectures_with_eval = student_evals['lecture_id'].unique().tolist()
            profile.lectures_with_quiz = student_quizzes['lecture_id'].unique().tolist()
            profile.lectures_with_queries = []  # Can't populate without user_id mapping

            # Segment classification
            profile.segment = self._classify_segment(profile)

            profiles.append(profile)

        return profiles

    def _classify_segment(self, profile: StudentProfile) -> StudentSegment:
        """
        Classify student into segment based on eval performance.

        Thresholds (configurable):
          EXCEL:     avg_eval_score ≥ 75
          STRUGGLES: avg_eval_score < 45
          MIDDLE:    everything else
          UNKNOWN:   < 2 eval attempts

        Args:
            profile: Student profile

        Returns:
            StudentSegment enum
        """
        if profile.attempted_evals < 2:
            return StudentSegment.UNKNOWN

        if profile.avg_eval_score >= 75:
            return StudentSegment.EXCEL

        if profile.avg_eval_score < 45:
            return StudentSegment.STRUGGLES

        return StudentSegment.MIDDLE


class EngagementCalculator:
    """Calculates course-level engagement metrics."""

    def calculate_engagement(
        self,
        student_profiles: List[StudentProfile],
        enrolled_n: int,
    ) -> EngagementMetrics:
        """
        Calculate engagement metrics from student profiles.

        Args:
            student_profiles: List of student profiles
            enrolled_n: Total enrolled students

        Returns:
            EngagementMetrics object
        """
        # Count engaged students
        engaged_students = [p for p in student_profiles if p.is_engaged]
        engaged_n = len(engaged_students)
        engagement_rate = engaged_n / enrolled_n if enrolled_n > 0 else 0.0

        # Count by segment
        excel_students = [p for p in engaged_students if p.segment == StudentSegment.EXCEL]
        middle_students = [p for p in engaged_students if p.segment == StudentSegment.MIDDLE]
        struggles_students = [p for p in engaged_students if p.segment == StudentSegment.STRUGGLES]
        unknown_students = [p for p in engaged_students if p.segment == StudentSegment.UNKNOWN]

        excel_n = len(excel_students)
        middle_n = len(middle_students)
        struggles_n = len(struggles_students)
        unknown_n = len(unknown_students)

        # Percentages
        excel_pct = excel_n / engaged_n if engaged_n > 0 else 0.0
        middle_pct = middle_n / engaged_n if engaged_n > 0 else 0.0
        struggles_pct = struggles_n / engaged_n if engaged_n > 0 else 0.0

        # Flag if segments are reliable
        min_data_for_segments = engaged_n >= 10

        return EngagementMetrics(
            enrolled_n=enrolled_n,
            engaged_n=engaged_n,
            engagement_rate=engagement_rate,
            excel_n=excel_n,
            excel_pct=excel_pct,
            middle_n=middle_n,
            middle_pct=middle_pct,
            struggles_n=struggles_n,
            struggles_pct=struggles_pct,
            unknown_n=unknown_n,
            min_data_for_segments=min_data_for_segments,
        )


class RevisitExtractor:
    """Extracts revisit signals (queries >14 days after lecture)."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.revisit_threshold_days = 14

    def extract_revisits(
        self,
        queries_df: pd.DataFrame,
        lecture_sequence: List[LectureMetadata],
        student_profiles: List[StudentProfile],
    ) -> Tuple[List[RevisitSignal], RevisitMetrics]:
        """
        Extract revisit signals from queries.

        A revisit occurs when a student accesses a lecture >14 days after it was taught.

        Args:
            queries_df: All queries with timestamps
            lecture_sequence: Lecture metadata with dates
            student_profiles: Student profiles with segments

        Returns:
            Tuple of (revisit_signals, revisit_metrics)
        """
        # Build lecture date lookup (skip lectures without valid dates)
        lecture_dates = {}
        for lec in lecture_sequence:
            try:
                lecture_dates[lec.lecture_id] = datetime.strptime(lec.date, "%Y-%m-%d")
            except (ValueError, TypeError):
                # Skip lectures without valid dates
                continue

        # Build lecture name lookup
        lecture_names = {lec.lecture_id: lec.name for lec in lecture_sequence}

        # Note: queries.csv uses user_id, not email
        # We track revisits by user_id since we can't map to email
        revisit_signals = []

        for _, row in queries_df.iterrows():
            lecture_id = row.get('entity_id')
            if not lecture_id or lecture_id not in lecture_dates:
                continue

            # Parse query timestamp
            query_time_str = row.get('time')
            if not query_time_str:
                continue

            try:
                query_date = datetime.strptime(query_time_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

            # Calculate days since lecture
            lecture_date = lecture_dates[lecture_id]
            days_since = (query_date - lecture_date).days

            # Check revisit threshold
            if days_since > self.revisit_threshold_days:
                user_id = row.get('user_id', '')

                # Revisit signals track by user_id (not email)
                # segment remains UNKNOWN since we can't map user_id to email
                revisit = RevisitSignal(
                    student_id=user_id,
                    student_email='',  # queries.csv doesn't have email
                    segment=StudentSegment.UNKNOWN,  # Can't determine without email mapping
                    lecture_id=lecture_id,
                    lecture_name=lecture_names.get(lecture_id, lecture_id),
                    lecture_date=lecture_date.strftime("%Y-%m-%d"),
                    query_text=row.get('query', ''),
                    query_date=query_date.strftime("%Y-%m-%d"),
                    days_since_lecture=days_since,
                )

                revisit_signals.append(revisit)

        # Calculate metrics
        metrics = self._calculate_revisit_metrics(revisit_signals)

        return revisit_signals, metrics

    def _calculate_revisit_metrics(self, revisit_signals: List[RevisitSignal]) -> RevisitMetrics:
        """Calculate aggregated revisit metrics."""
        total_revisit_count = len(revisit_signals)

        # Unique students (by user_id since we don't have email)
        unique_students = set(r.student_id for r in revisit_signals if r.student_id)
        unique_students_revisiting = len(unique_students)

        # Per-lecture counts (unique user_ids per lecture)
        revisit_by_lecture = defaultdict(set)
        for r in revisit_signals:
            if r.student_id:
                revisit_by_lecture[r.lecture_id].add(r.student_id)

        revisit_by_lecture_counts = {
            lec_id: len(students)
            for lec_id, students in revisit_by_lecture.items()
        }

        return RevisitMetrics(
            total_revisit_count=total_revisit_count,
            unique_students_revisiting=unique_students_revisiting,
            revisit_by_lecture=revisit_by_lecture_counts,
            revisit_by_concept={},  # Will be populated in Layer 1 after concept matching
        )


class CourseLayer0Pipeline:
    """Main pipeline for course-level Layer 0."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.roster_loader = StudentRosterLoader()
        self.sequence_loader = LectureSequenceLoader()
        self.segmentation_engine = StudentSegmentationEngine(config)
        self.engagement_calculator = EngagementCalculator()
        self.revisit_extractor = RevisitExtractor(config)

    def run(
        self,
        roster_path: Path,
        lecture_sequence_path: Path,
        quiz_csv_path: Path,
        eval_csv_path: Path,
        queries_csv_path: Path,
        class_reports_dir: Path,
        run_number: int,
        run_date: str,
        output_dir: Optional[Path] = None,
        lectures_to_include: Optional[int] = None,
    ) -> CourseLayer0Output:
        """
        Run course-level Layer 0 pipeline.

        Args:
            roster_path: Path to student_roster.json
            lecture_sequence_path: Path to lecture_sequence.json
            quiz_csv_path: Path to quiz.csv (all lectures)
            eval_csv_path: Path to eval.csv (all lectures)
            queries_csv_path: Path to queries.csv (all lectures)
            class_reports_dir: Directory containing class-level outputs
            run_number: Run number (1, 2, or 3)
            run_date: Date of this run (YYYY-MM-DD)
            output_dir: Output directory

        Returns:
            CourseLayer0Output object
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "course_level" / "layer0"

        output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.verbose:
            print("=" * 80)
            print(f"COURSE-LEVEL LAYER 0: Normalization & Segmentation (Run {run_number})")
            print("=" * 80)

        # Load roster
        if self.config.verbose:
            print("\n[1/6] Loading student roster...")

        roster = self.roster_loader.load_roster(roster_path)
        enrolled_n = len(roster)

        if self.config.verbose:
            print(f"✅ Loaded {enrolled_n} enrolled students")

        # Load lecture sequence
        if self.config.verbose:
            print("\n[2/6] Loading lecture sequence...")

        lecture_sequence = self.sequence_loader.load_sequence(lecture_sequence_path, class_reports_dir)
        total_lectures = len(lecture_sequence)

        # Filter lectures if needed (for mid-semester runs)
        if lectures_to_include and lectures_to_include < total_lectures:
            lecture_sequence = lecture_sequence[:lectures_to_include]
            if self.config.verbose:
                print(f"✅ Loaded {total_lectures} total lectures, analyzing first {lectures_to_include}")

        lectures_with_reports = sum(1 for lec in lecture_sequence if lec.has_class_report)

        if self.config.verbose:
            if not lectures_to_include or lectures_to_include >= total_lectures:
                print(f"✅ Loaded {total_lectures} lectures ({lectures_with_reports} with class reports)")

        # Load data
        if self.config.verbose:
            print("\n[3/6] Loading quiz/eval/query data...")

        quiz_df = pd.read_csv(quiz_csv_path)
        eval_df = pd.read_csv(eval_csv_path)
        queries_df = pd.read_csv(queries_csv_path)

        # Filter data to only include lectures in our sequence
        included_lecture_ids = {lec.lecture_id for lec in lecture_sequence}
        quiz_df = quiz_df[quiz_df['lecture_id'].isin(included_lecture_ids)]
        eval_df = eval_df[eval_df['lecture_id'].isin(included_lecture_ids)]
        queries_df = queries_df[queries_df['entity_id'].isin(included_lecture_ids)]

        if self.config.verbose:
            print(f"✅ Loaded {len(quiz_df)} quiz attempts, {len(eval_df)} eval attempts, {len(queries_df)} queries")

        # Build student profiles
        if self.config.verbose:
            print("\n[4/6] Building student profiles & segmentation...")

        student_profiles = self.segmentation_engine.build_student_profiles(
            roster, quiz_df, eval_df, queries_df
        )

        if self.config.verbose:
            engaged_count = sum(1 for p in student_profiles if p.is_engaged)
            print(f"✅ Profiled {len(student_profiles)} students ({engaged_count} engaged)")

        # Calculate engagement metrics
        if self.config.verbose:
            print("\n[5/6] Calculating engagement metrics...")

        engagement = self.engagement_calculator.calculate_engagement(student_profiles, enrolled_n)

        if self.config.verbose:
            print(f"✅ Engagement rate: {engagement.engagement_rate*100:.1f}%")
            print(f"   EXCEL: {engagement.excel_n} ({engagement.excel_pct*100:.1f}%)")
            print(f"   MIDDLE: {engagement.middle_n} ({engagement.middle_pct*100:.1f}%)")
            print(f"   STRUGGLES: {engagement.struggles_n} ({engagement.struggles_pct*100:.1f}%)")

        # Extract revisit signals
        if self.config.verbose:
            print("\n[6/6] Extracting revisit signals...")

        revisit_signals, revisit_metrics = self.revisit_extractor.extract_revisits(
            queries_df, lecture_sequence, student_profiles
        )

        if self.config.verbose:
            print(f"✅ Found {revisit_metrics.total_revisit_count} revisit queries")
            print(f"   {revisit_metrics.unique_students_revisiting} unique students revisiting")

        # Build output
        output = CourseLayer0Output(
            run_number=run_number,
            run_date=run_date,
            lectures_covered=lectures_with_reports,
            total_lectures=total_lectures,
            student_profiles=student_profiles,
            engagement=engagement,
            revisit_signals=revisit_signals,
            revisit_metrics=revisit_metrics,
            lecture_sequence=lecture_sequence,
        )

        # Save output
        self._save_output(output, output_dir)

        if self.config.verbose:
            print(f"\n✅ Course Layer 0 complete!")
            print(f"   Output saved to: {output_dir}")

        return output

    def _save_output(self, output: CourseLayer0Output, output_dir: Path):
        """Save Layer 0 output to JSON."""
        output_path = output_dir / "course_layer0_output.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved course Layer 0 output to {output_path}")
