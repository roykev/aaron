"""
Test script for Course-Level Layer 2: Rank & Package

Tests the ranking and packaging of course-level patterns:
- Ranks recurring concepts by recurrence score
- Ranks problematic lessons by problem score
- Ranks good lessons by success score
- Ranks consistent successes by success rate
- Packages systemic gaps and prerequisite gaps

Expects Course Layer 1 output to already exist from a previous run.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.course_level.layer2_ranking import CourseLayer2Pipeline
from teacher_side.learning_dashboard.common.models import CourseLayer1Output


def load_layer1_output(config: LearningDashboardConfig):
    """Load Course Layer 1 output from JSON."""
    import json

    layer1_dir = Path(config.paths.output_dir) / "course_level" / "layer1"
    layer1_path = layer1_dir / "course_layer1_output.json"

    if not layer1_path.exists():
        raise FileNotFoundError(
            f"Course Layer 1 output not found at {layer1_path}. "
            "Please run test_course_layer1.py first."
        )

    print(f"Loading Layer 1 output from: {layer1_path}")

    with open(layer1_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Reconstruct CourseLayer1Output from dict
    # Simple dict-based approach for now
    return data


def display_results(output):
    """Display Course Layer 2 results."""
    print("\n" + "=" * 80)
    print("COURSE LAYER 2 - RESULTS (RANKED & PACKAGED)")
    print("=" * 80)

    print(f"\n📚 Course Overview:")
    print(f"  • Run number: {output.run_number}")
    print(f"  • Run date: {output.run_date}")
    print(f"  • Lectures covered: {output.lectures_covered}/{output.total_lectures}")
    print(f"  • Engaged students: {output.engaged_n}")
    print(f"  • Course eval average: {output.course_eval_avg:.1f}")
    print(f"  • Course quiz average: {output.course_quiz_avg:.1f}")

    # Top Recurring Concepts
    print(f"\n🔄 Top Recurring Concepts ({len(output.top_recurring_concepts)}):")
    if output.top_recurring_concepts:
        for i, concept in enumerate(output.top_recurring_concepts, 1):
            print(f"\n  {i}. {concept.concept}")
            print(f"     • Appears in: {concept.appearance_count} lectures")
            print(f"     • Total queries: {concept.total_query_n}")
            print(f"     • Revisit students: {concept.revisit_student_n}")
            print(f"     • Recurrence score: {concept.recurrence_score:.2f}")
            print(f"     • Lectures: {', '.join(concept.lectures)}")
    else:
        print("  No recurring concepts")

    # Top Problematic Lessons
    print(f"\n⚠️  Top Problematic Lessons ({len(output.top_problematic_lessons)}):")
    if output.top_problematic_lessons:
        for i, lesson in enumerate(output.top_problematic_lessons, 1):
            print(f"\n  {i}. {lesson.lecture_name}")
            print(f"     • Lesson eval: {lesson.lesson_eval_avg:.1f} (course: {lesson.course_eval_avg:.1f})")
            print(f"     • Signals: {', '.join(lesson.signals)}")
            print(f"     • Problem score: {lesson.lesson_problem_score:.2f}")
    else:
        print("  No problematic lessons")

    # Top Good Lessons
    print(f"\n✅ Top Good Lessons ({len(output.top_good_lessons)}):")
    if output.top_good_lessons:
        for i, lesson in enumerate(output.top_good_lessons, 1):
            print(f"\n  {i}. {lesson['lecture_name']}")
            print(f"     • Lesson eval: {lesson['lesson_eval_avg']:.1f} (course: {lesson['course_eval_avg']:.1f})")
            print(f"     • Signals: {', '.join(lesson['signals'])}")
            print(f"     • Success score: {lesson['lesson_success_score']:.2f}")
    else:
        print("  No good lessons")

    # Top Consistent Successes
    print(f"\n✅ Top Consistent Successes ({len(output.top_consistent_successes)}):")
    if output.top_consistent_successes:
        for i, success in enumerate(output.top_consistent_successes, 1):
            print(f"\n  {i}. {success.concept}")
            print(f"     • Similar questions: {success.success_count}")
            print(f"     • Appears in: {len(success.lectures)} lectures")
            print(f"     • Average success rate: {success.avg_success_rate:.1f}%")
            print(f"     • Lectures: {', '.join(success.lectures)}")
    else:
        print("  No consistent successes")

    # Systemic Gaps
    print(f"\n📉 Systemic Gaps ({len(output.top_systemic_gaps)}):")
    if output.top_systemic_gaps:
        for i, gap in enumerate(output.top_systemic_gaps, 1):
            print(f"\n  {i}. {gap.concept}")
            print(f"     • Direction: {gap.direction.value}")
            print(f"     • Appearances: {gap.gap_appearances} lectures")
            print(f"     • Interpretation: {gap.interpretation}")
    else:
        print("  No systemic gaps")

    # Prerequisite Gaps
    print(f"\n📚 Top Prerequisite Gaps ({len(output.top_prerequisite_gaps)}):")
    if output.top_prerequisite_gaps:
        for i, prereq in enumerate(output.top_prerequisite_gaps, 1):
            print(f"\n  {i}. {prereq.topic}")
            print(f"     • Unique students: {prereq.unique_students}")
            print(f"     • Appears in: {prereq.appearing_in_lectures} lectures")
            if prereq.example_queries:
                print(f"     • Example queries: {', '.join(prereq.example_queries[:2])}")
    else:
        print("  No prerequisite gaps")


def main():
    """Run Course Layer 2 test."""

    print("=" * 80)
    print("COURSE-LEVEL LAYER 2: Test Script")
    print("=" * 80)

    # Configure paths
    base_dir = Path("/home/roy/Downloads/attachments")

    config = LearningDashboardConfig.from_files(
        queries_csv=str(base_dir / "queries.csv"),
        quiz_csv=str(base_dir / "quiz.csv"),
        eval_csv=str(base_dir / "eval.csv"),
        correct_csv=str(base_dir / "correct.csv"),
        concepts_json=str(base_dir / "concepts.txt"),
        output_txt=str(base_dir / "output.txt"),
        output_dir=str(base_dir / "output" / "learning_dashboard"),
        lecture_id="",  # Not needed for course-level
    )

    # Enable verbose output
    config.verbose = True

    print("\n[Configuration]")
    print(f"  Output directory: {config.paths.output_dir}")

    # Load Layer 1 output
    print("\n[Loading Course Layer 1 output...]")
    try:
        layer1_data = load_layer1_output(config)
        print(f"✅ Loaded Layer 1 output (Run {layer1_data['run_number']}, {layer1_data['lectures_covered']} lectures)")

        # Reconstruct Layer 1 output objects
        from teacher_side.learning_dashboard.common.models import (
            RecurringConcept, ProblematicLesson, ConsistentSuccess,
            SystemicGap, PrerequisiteGapCluster, GapDirection
        )

        # Build Layer1Output object
        layer1_output = CourseLayer1Output(
            run_number=layer1_data['run_number'],
            run_date=layer1_data['run_date'],
            lectures_covered=layer1_data['lectures_covered'],
            total_lectures=layer1_data['total_lectures'],
            engaged_n=layer1_data['engaged_n'],
            course_eval_avg=layer1_data['course_eval_avg'],
            course_quiz_avg=layer1_data['course_quiz_avg'],
            recurring_concepts=[
                RecurringConcept(
                    concept=rc['concept'],
                    appearance_count=rc['appearance_count'],
                    total_failure_n=rc['total_failure_n'],
                    total_query_n=rc['total_query_n'],
                    revisit_student_n=rc['revisit_student_n'],
                    lectures=rc['lectures'],
                    segment_breakdown=rc.get('segment_breakdown', {}),
                    is_struggles_dominant=rc.get('is_struggles_dominant', False),
                    recurrence_score=rc['recurrence_score'],
                )
                for rc in layer1_data.get('recurring_concepts', [])
            ],
            problematic_lessons=[
                ProblematicLesson(
                    lecture_id=pl['lecture_id'],
                    lecture_name=pl['lecture_name'],
                    lesson_eval_avg=pl['lesson_eval_avg'],
                    course_eval_avg=pl['course_eval_avg'],
                    issue_count=pl['issue_count'],
                    revisit_student_n=pl['revisit_student_n'],
                    signals=pl['signals'],
                    problem_signal_count=pl['problem_signal_count'],
                    lesson_problem_score=pl['lesson_problem_score'],
                )
                for pl in layer1_data.get('problematic_lessons', [])
            ],
            good_lessons=layer1_data.get('good_lessons', []),
            consistent_successes=[
                ConsistentSuccess(
                    concept=cs['concept'],
                    success_count=cs['success_count'],
                    avg_success_rate=cs['avg_success_rate'],
                    teaching_pattern=cs.get('teaching_pattern', {}),
                    segment_note=cs.get('segment_note', ''),
                    lectures=cs['lectures'],
                )
                for cs in layer1_data.get('consistent_successes', [])
            ],
            systemic_gaps=[
                SystemicGap(
                    concept=sg['concept'],
                    direction=GapDirection(sg['direction']),
                    gap_appearances=sg['gap_appearances'],
                    segment_gap=sg.get('segment_gap', {}),
                    interpretation=sg['interpretation'],
                    lectures=sg['lectures'],
                )
                for sg in layer1_data.get('systemic_gaps', [])
            ],
            prerequisite_gaps=[
                PrerequisiteGapCluster(
                    topic=pg['topic'],
                    unique_students=pg['unique_students'],
                    appearing_in_lectures=pg['appearing_in_lectures'],
                    lecture_names=pg['lecture_names'],
                    out_of_scope_type=pg['out_of_scope_type'],
                    example_queries=pg['example_queries'],
                )
                for pg in layer1_data.get('prerequisite_gaps', [])
            ],
        )

    except Exception as e:
        print(f"\n❌ Failed to load Layer 1 output: {e}")
        print("\n⚠️  Please run test_course_layer1.py first to generate Layer 1 output.")
        import traceback
        traceback.print_exc()
        return

    # Run Layer 2 pipeline
    print("\n" + "=" * 80)
    print("RUNNING COURSE LAYER 2 PIPELINE")
    print("=" * 80)

    pipeline = CourseLayer2Pipeline(config)

    try:
        output = pipeline.run(layer1_output=layer1_output)

        # Display results
        display_results(output)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        print(f"""
✅ Course Layer 2 Complete!

📁 Output saved to: {config.paths.output_dir}/course_level/layer2/

📊 Ranked Patterns:
   • {len(output.top_recurring_concepts)} top recurring concepts
   • {len(output.top_problematic_lessons)} top problematic lessons
   • {len(output.top_good_lessons)} top good lessons
   • {len(output.top_consistent_successes)} top consistent successes
   • {len(output.top_systemic_gaps)} systemic gaps
   • {len(output.top_prerequisite_gaps)} top prerequisite gaps

Next steps:
1. Review the ranked patterns for quality
2. Proceed to Course Layer 3 (LLM Narrative Generation)
3. Generate the final 5-panel course dashboard
        """)

    except Exception as e:
        print(f"\n❌ Layer 2 pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()