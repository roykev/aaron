"""
Course-Level Layer 2: Ranking & Packaging

Ranks aggregated course patterns by significance and packages evidence for LLM narrative generation.

Similar to class-level Layer 2, but operates on course-wide patterns from Layer 1:
- Ranks recurring concepts by recurrence score
- Ranks problematic lessons by problem score
- Ranks good lessons by success score
- Ranks consistent successes by success rate
- Packages systemic gaps and prerequisite gaps

Output: Ready-to-consume evidence bundles for Course Layer 3 (LLM narrative).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from ..common.models import (
    CourseLayer1Output,
    RecurringConcept,
    ProblematicLesson,
    ConsistentSuccess,
    SystemicGap,
    PrerequisiteGapCluster,
)
from ..common.config import LearningDashboardConfig


class CourseLayer2Output:
    """Packaged course-level evidence bundles ready for LLM."""

    def __init__(
        self,
        run_number: int,
        run_date: str,
        lectures_covered: int,
        total_lectures: int,
        engaged_n: int,
        course_eval_avg: float,
        course_quiz_avg: float,

        # Ranked patterns
        top_recurring_concepts: List[RecurringConcept],
        top_problematic_lessons: List[ProblematicLesson],
        top_good_lessons: List[Dict],
        top_consistent_successes: List[ConsistentSuccess],
        top_systemic_gaps: List[SystemicGap],
        top_prerequisite_gaps: List[PrerequisiteGapCluster],

        # Engagement breakdown (optional for backward compatibility)
        engagement: Optional[Dict] = None,
    ):
        self.run_number = run_number
        self.run_date = run_date
        self.lectures_covered = lectures_covered
        self.total_lectures = total_lectures
        self.engaged_n = engaged_n
        self.course_eval_avg = course_eval_avg
        self.course_quiz_avg = course_quiz_avg

        self.top_recurring_concepts = top_recurring_concepts
        self.top_problematic_lessons = top_problematic_lessons
        self.top_good_lessons = top_good_lessons
        self.top_consistent_successes = top_consistent_successes
        self.top_systemic_gaps = top_systemic_gaps
        self.top_prerequisite_gaps = top_prerequisite_gaps
        self.engagement = engagement

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'run_number': self.run_number,
            'run_date': self.run_date,
            'lectures_covered': self.lectures_covered,
            'total_lectures': self.total_lectures,
            'engaged_n': self.engaged_n,
            'course_eval_avg': self.course_eval_avg,
            'course_quiz_avg': self.course_quiz_avg,
            'engagement': self.engagement,
            'top_recurring_concepts': [
                {
                    'concept': rc.concept,
                    'appearance_count': rc.appearance_count,
                    'total_failure_n': rc.total_failure_n,
                    'total_query_n': rc.total_query_n,
                    'revisit_student_n': rc.revisit_student_n,
                    'lectures': rc.lectures,
                    'recurrence_score': rc.recurrence_score,
                    'is_struggles_dominant': rc.is_struggles_dominant,
                    'segment_breakdown': rc.segment_breakdown,
                }
                for rc in self.top_recurring_concepts
            ],
            'top_problematic_lessons': [
                {
                    'lecture_id': pl.lecture_id,
                    'lecture_name': pl.lecture_name,
                    'lesson_eval_avg': pl.lesson_eval_avg,
                    'course_eval_avg': pl.course_eval_avg,
                    'issue_count': pl.issue_count,
                    'revisit_student_n': pl.revisit_student_n,
                    'signals': pl.signals,
                    'problem_signal_count': pl.problem_signal_count,
                    'lesson_problem_score': pl.lesson_problem_score,
                }
                for pl in self.top_problematic_lessons
            ],
            'top_good_lessons': self.top_good_lessons,
            'top_consistent_successes': [
                {
                    'concept': cs.concept,
                    'success_count': cs.success_count,
                    'avg_success_rate': cs.avg_success_rate,
                    'lectures': cs.lectures,
                    'segment_note': cs.segment_note,
                }
                for cs in self.top_consistent_successes
            ],
            'top_systemic_gaps': [
                {
                    'concept': sg.concept,
                    'direction': sg.direction.value,
                    'gap_appearances': sg.gap_appearances,
                    'lectures': sg.lectures,
                    'interpretation': sg.interpretation,
                }
                for sg in self.top_systemic_gaps
            ],
            'top_prerequisite_gaps': [
                {
                    'topic': pg.topic,
                    'unique_students': pg.unique_students,
                    'appearing_in_lectures': pg.appearing_in_lectures,
                    'lecture_names': pg.lecture_names,
                    'out_of_scope_type': pg.out_of_scope_type,
                    'example_queries': pg.example_queries,
                }
                for pg in self.top_prerequisite_gaps
            ],
        }


class CourseLayer2Pipeline:
    """Main pipeline for Course Layer 2: ranking and packaging."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def run(
        self,
        layer1_output: CourseLayer1Output,
        layer0_output = None,  # Optional for backward compatibility
        output_dir: Optional[Path] = None,
    ) -> CourseLayer2Output:
        """
        Run Course Layer 2: rank and package aggregated patterns.

        Args:
            layer1_output: Course Layer 1 output
            layer0_output: Course Layer 0 output (for engagement data)
            output_dir: Output directory

        Returns:
            CourseLayer2Output ready for Layer 3 LLM
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "course_level" / "layer2"

        output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.verbose:
            print("=" * 80)
            print(f"COURSE-LEVEL LAYER 2: Rank & Package (Run {layer1_output.run_number})")
            print("=" * 80)

        # Rank recurring concepts (already sorted by recurrence_score in Layer 1)
        if self.config.verbose:
            print("\n[1/6] Ranking recurring concepts...")

        top_recurring = layer1_output.recurring_concepts[:5]  # Top 5

        if self.config.verbose:
            print(f"✅ Selected top {len(top_recurring)} recurring concepts")

        # Rank problematic lessons (already sorted by problem_score in Layer 1)
        if self.config.verbose:
            print("\n[2/6] Ranking problematic lessons...")

        top_problematic = layer1_output.problematic_lessons[:3]  # Top 3

        if self.config.verbose:
            print(f"✅ Selected top {len(top_problematic)} problematic lessons")

        # Rank good lessons (already sorted by success_score in Layer 1)
        if self.config.verbose:
            print("\n[3/6] Ranking good lessons...")

        top_good = layer1_output.good_lessons[:3]  # Top 3

        if self.config.verbose:
            print(f"✅ Selected top {len(top_good)} good lessons")

        # Rank consistent successes (already sorted by success_rate in Layer 1)
        if self.config.verbose:
            print("\n[4/6] Ranking consistent successes...")

        top_successes = layer1_output.consistent_successes[:5]  # Top 5

        if self.config.verbose:
            print(f"✅ Selected top {len(top_successes)} consistent successes")

        # Package systemic gaps (all of them, usually just 1-2)
        if self.config.verbose:
            print("\n[5/6] Packaging systemic gaps...")

        top_gaps = layer1_output.systemic_gaps  # All

        if self.config.verbose:
            print(f"✅ Packaged {len(top_gaps)} systemic gaps")

        # Package prerequisite gaps (already sorted by student count in Layer 1)
        if self.config.verbose:
            print("\n[6/6] Packaging prerequisite gaps...")

        top_prereqs = layer1_output.prerequisite_gaps[:5]  # Top 5

        if self.config.verbose:
            print(f"✅ Packaged {len(top_prereqs)} prerequisite gaps")

        # Extract engagement data if available
        engagement_data = None
        if layer0_output and hasattr(layer0_output, 'engagement') and layer0_output.engagement:
            engagement = layer0_output.engagement
            engagement_data = {
                'enrolled_n': engagement.enrolled_n,
                'engaged_n': engagement.engaged_n,
                'engagement_rate': engagement.engagement_rate,
                'excel_n': engagement.excel_n,
                'excel_pct': engagement.excel_pct,
                'middle_n': engagement.middle_n,
                'middle_pct': engagement.middle_pct,
                'struggles_n': engagement.struggles_n,
                'struggles_pct': engagement.struggles_pct,
                'unknown_n': engagement.unknown_n,
            }

        # Build output
        output = CourseLayer2Output(
            run_number=layer1_output.run_number,
            run_date=layer1_output.run_date,
            lectures_covered=layer1_output.lectures_covered,
            total_lectures=layer1_output.total_lectures,
            engaged_n=layer1_output.engaged_n,
            course_eval_avg=layer1_output.course_eval_avg,
            course_quiz_avg=layer1_output.course_quiz_avg,
            top_recurring_concepts=top_recurring,
            top_problematic_lessons=top_problematic,
            top_good_lessons=top_good,
            top_consistent_successes=top_successes,
            top_systemic_gaps=top_gaps,
            top_prerequisite_gaps=top_prereqs,
            engagement=engagement_data,
        )

        # Save output
        self._save_output(output, output_dir)

        if self.config.verbose:
            print(f"\n✅ Course Layer 2 complete!")
            print(f"   Output saved to: {output_dir}")

        return output

    def _save_output(self, output: CourseLayer2Output, output_dir: Path):
        """Save Layer 2 output to JSON."""
        output_path = output_dir / "course_layer2_output.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output.to_dict(), f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved course Layer 2 output to {output_path}")