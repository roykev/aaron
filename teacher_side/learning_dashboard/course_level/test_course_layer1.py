"""
Test script for Course-Level Layer 1: Cross-Lesson Aggregation

Tests the aggregation of class-level signals into course-level patterns:
- Recurring concepts (≥2 lectures)
- Problematic lessons (≥2 independent signals)
- Consistent successes (≥2 lectures)
- Systemic gaps (≥2 lectures, same direction)
- Prerequisite gaps (aggregated out-of-scope clusters)

Expects Course Layer 0 output to already exist from a previous run.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.course_level.layer1_aggregate import CourseLayer1Pipeline
from teacher_side.learning_dashboard.common.models import CourseLayer0Output


def load_layer0_output(config: LearningDashboardConfig) -> CourseLayer0Output:
    """Load Course Layer 0 output from JSON."""
    import json

    layer0_dir = Path(config.paths.output_dir) / "course_level" / "layer0"
    layer0_path = layer0_dir / "course_layer0_output.json"

    if not layer0_path.exists():
        raise FileNotFoundError(
            f"Course Layer 0 output not found at {layer0_path}. "
            "Please run test_course_layer0.py first."
        )

    print(f"Loading Layer 0 output from: {layer0_path}")

    with open(layer0_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Reconstruct CourseLayer0Output from dict
    # For now, use a simple dict-based approach
    # TODO: implement proper deserialization method
    layer0_output = CourseLayer0Output.from_dict(data)

    return layer0_output


def display_results(output):
    """Display Course Layer 1 results."""
    print("\n" + "=" * 80)
    print("COURSE LAYER 1 - RESULTS")
    print("=" * 80)

    print(f"\n📚 Course Overview:")
    print(f"  • Run number: {output.run_number}")
    print(f"  • Run date: {output.run_date}")
    print(f"  • Lectures covered: {output.lectures_covered}/{output.total_lectures}")
    print(f"  • Engaged students: {output.engaged_n}")
    print(f"  • Course eval average: {output.course_eval_avg:.1f}")
    print(f"  • Course quiz average: {output.course_quiz_avg:.1f}")

    # Recurring Concepts
    print(f"\n🔄 Recurring Concepts ({len(output.recurring_concepts)}):")
    if output.recurring_concepts:
        for i, concept in enumerate(output.recurring_concepts[:5], 1):
            print(f"\n  {i}. {concept.concept}")
            print(f"     • Appears in: {concept.appearance_count} lectures ({', '.join(concept.lectures)})")
            print(f"     • Total failures: {concept.total_failure_n}")
            print(f"     • Total queries: {concept.total_query_n}")
            print(f"     • Revisit students: {concept.revisit_student_n}")
            print(f"     • Recurrence score: {concept.recurrence_score:.2f}")
            if concept.is_struggles_dominant:
                print(f"     • ⚠️  Struggles-dominant")
    else:
        print("  No recurring concepts detected")

    # Problematic Lessons
    print(f"\n⚠️  Problematic Lessons ({len(output.problematic_lessons)}):")
    if output.problematic_lessons:
        for i, lesson in enumerate(output.problematic_lessons, 1):
            print(f"\n  {i}. {lesson.lecture_name}")
            print(f"     • Lesson eval: {lesson.lesson_eval_avg:.1f} (course: {lesson.course_eval_avg:.1f})")
            print(f"     • Issue count: {lesson.issue_count}")
            print(f"     • Revisit students: {lesson.revisit_student_n}")
            print(f"     • Signals ({lesson.problem_signal_count}): {', '.join(lesson.signals)}")
            print(f"     • Problem score: {lesson.lesson_problem_score:.2f}")
    else:
        print("  No problematic lessons detected")

    # Good Lessons
    print(f"\n✅ Good Lessons ({len(output.good_lessons)}):")
    if output.good_lessons:
        for i, lesson in enumerate(output.good_lessons, 1):
            print(f"\n  {i}. {lesson['lecture_name']}")
            print(f"     • Lesson eval: {lesson['lesson_eval_avg']:.1f} (course: {lesson['course_eval_avg']:.1f})")
            print(f"     • Query count: {lesson['query_count']} (low confusion)")
            print(f"     • Revisit count: {lesson['revisit_count']} (low revisit needs)")
            print(f"     • Signals ({lesson['positive_signal_count']}): {', '.join(lesson['signals'])}")
            print(f"     • Success score: {lesson['lesson_success_score']:.2f}")
    else:
        print("  No good lessons detected")

    # Consistent Successes
    print(f"\n✅ Consistent Successes ({len(output.consistent_successes)}):")
    if output.consistent_successes:
        for i, success in enumerate(output.consistent_successes[:5], 1):
            print(f"\n  {i}. {success.concept}")
            print(f"     • Similar questions: {success.success_count}")
            print(f"     • Appears in: {len(success.lectures)} lectures")
            print(f"     • Average success rate: {success.avg_success_rate:.1f}%")
            print(f"     • Lectures: {', '.join(success.lectures)}")

            patterns = []
            if success.teaching_pattern.get('example_used'):
                patterns.append("example used")
            if success.teaching_pattern.get('inclass_quiet'):
                patterns.append("in-class quiet")
            if success.teaching_pattern.get('assessed'):
                patterns.append("assessed")

            if patterns:
                print(f"     • Teaching pattern: {', '.join(patterns)}")
    else:
        print("  No consistent successes detected")

    # Systemic Gaps
    print(f"\n📉 Systemic Gaps ({len(output.systemic_gaps)}):")
    if output.systemic_gaps:
        for i, gap in enumerate(output.systemic_gaps, 1):
            print(f"\n  {i}. {gap.concept}")
            print(f"     • Direction: {gap.direction.value}")
            print(f"     • Appearances: {gap.gap_appearances} lectures")
            print(f"     • Lectures: {', '.join(gap.lectures)}")
            if gap.interpretation:
                print(f"     • Interpretation: {gap.interpretation}")
    else:
        print("  No systemic gaps detected")

    # Prerequisite Gaps
    print(f"\n📚 Prerequisite Gaps ({len(output.prerequisite_gaps)}):")
    if output.prerequisite_gaps:
        for i, prereq in enumerate(output.prerequisite_gaps[:5], 1):
            print(f"\n  {i}. {prereq.topic}")
            print(f"     • Unique students: {prereq.unique_students}")
            print(f"     • Appears in: {prereq.appearing_in_lectures} lectures ({', '.join(prereq.lecture_names)})")
            print(f"     • Type: {prereq.out_of_scope_type}")
            if prereq.example_queries:
                print(f"     • Example queries:")
                for query in prereq.example_queries[:2]:
                    print(f"       - {query}")
    else:
        print("  No prerequisite gaps detected")


def main():
    """Run Course Layer 1 test."""

    print("=" * 80)
    print("COURSE-LEVEL LAYER 1: Test Script")
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

    # Load Layer 0 output
    print("\n[Loading Course Layer 0 output...]")
    try:
        layer0_output = load_layer0_output(config)
        print(f"✅ Loaded Layer 0 output (Run {layer0_output.run_number}, {layer0_output.lectures_covered} lectures)")
    except Exception as e:
        print(f"\n❌ Failed to load Layer 0 output: {e}")
        print("\n⚠️  Please run test_course_layer0.py first to generate Layer 0 output.")
        return

    # Run Layer 1 pipeline
    print("\n" + "=" * 80)
    print("RUNNING COURSE LAYER 1 PIPELINE")
    print("=" * 80)

    pipeline = CourseLayer1Pipeline(config)

    try:
        # Pass CSV paths to pipeline for direct data access
        output = pipeline.run(
            layer0_output=layer0_output,
            quiz_csv_path=Path(config.paths.quiz_csv),
            eval_csv_path=Path(config.paths.eval_csv),
            queries_csv_path=Path(config.paths.queries_csv),
            correct_csv_path=Path(config.paths.correct_csv),
        )

        # Display results
        display_results(output)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        print(f"""
✅ Course Layer 1 Complete!

📁 Output saved to: {config.paths.output_dir}/course_level/layer1/

📊 Patterns Detected:
   • {len(output.recurring_concepts)} recurring concepts
   • {len(output.problematic_lessons)} problematic lessons
   • {len(output.good_lessons)} good lessons
   • {len(output.consistent_successes)} consistent successes
   • {len(output.systemic_gaps)} systemic gaps
   • {len(output.prerequisite_gaps)} prerequisite gap clusters

Next steps:
1. Review the aggregated patterns for quality
2. Check concept grouping via sentence transformers
3. Validate scoring formulas
4. Implement TODO items for segment tracking
5. Proceed to Course Layer 2 (Rank & Package)
        """)

    except Exception as e:
        print(f"\n❌ Layer 1 pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()