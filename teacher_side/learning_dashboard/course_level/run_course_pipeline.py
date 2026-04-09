"""
End-to-End Course-Level Pipeline

Runs all course-level layers in sequence:
- Layer 0: Normalization & Segmentation
- Layer 1: Cross-Lesson Aggregation
- Layer 2: Rank & Package
- Layer 3: LLM Narrative Generation

Outputs: Complete course dashboard with JSON, Markdown, and HTML
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.course_level.layer0_normalize import CourseLayer0Pipeline
from teacher_side.learning_dashboard.course_level.layer1_aggregate import CourseLayer1Pipeline
from teacher_side.learning_dashboard.course_level.layer2_ranking import CourseLayer2Pipeline
from teacher_side.learning_dashboard.course_level.layer3_narrative import CourseLayer3Pipeline


def run_complete_course_pipeline(
    queries_csv: str,
    quiz_csv: str,
    eval_csv: str,
    correct_csv: str,
    roster_json: str,
    lecture_sequence_json: str,
    class_reports_dir: str,
    output_dir: str,
    run_number: int,
    run_date: str,
    lectures_to_include: int = None,
    verbose: bool = True,
):
    """
    Run the complete course-level pipeline from start to finish.

    Args:
        queries_csv: Path to queries.csv
        quiz_csv: Path to quiz.csv
        eval_csv: Path to eval.csv
        correct_csv: Path to correct.csv
        roster_json: Path to student_roster.json
        lecture_sequence_json: Path to lecture_sequence.json
        class_reports_dir: Directory containing class-level Layer 2 reports
        output_dir: Output directory for all results
        run_number: Run number for this course analysis (1, 2, or 3)
        run_date: Date of this run (YYYY-MM-DD)
        lectures_to_include: Optional - number of lectures to include (for mid-semester runs)
        verbose: Print verbose output

    Returns:
        Dict with all layer outputs
    """
    # Create config (concepts_json and output_txt not needed for course-level)
    config = LearningDashboardConfig.from_files(
        queries_csv=queries_csv,
        quiz_csv=quiz_csv,
        eval_csv=eval_csv,
        correct_csv=correct_csv,
        output_dir=output_dir,
        lecture_id="",  # Not needed for course-level
    )

    config.verbose = verbose

    if verbose:
        print("\n" + "=" * 80)
        print("COURSE-LEVEL PIPELINE: End-to-End Execution")
        print("=" * 80)
        print(f"\nRun #{run_number} | Date: {run_date}")
        if lectures_to_include:
            print(f"Analyzing first {lectures_to_include} lectures")
        print(f"Output Directory: {output_dir}")

    # Layer 0: Normalization & Segmentation
    if verbose:
        print("\n" + "=" * 80)
        print("LAYER 0: Normalization & Segmentation")
        print("=" * 80)

    layer0_pipeline = CourseLayer0Pipeline(config)
    layer0_output = layer0_pipeline.run(
        roster_path=Path(roster_json),
        lecture_sequence_path=Path(lecture_sequence_json),
        quiz_csv_path=Path(quiz_csv),
        eval_csv_path=Path(eval_csv),
        queries_csv_path=Path(queries_csv),
        class_reports_dir=Path(class_reports_dir),
        run_number=run_number,
        run_date=run_date,
        lectures_to_include=lectures_to_include,
    )

    if verbose:
        print(f"\n✅ Layer 0 Complete!")
        print(f"   • {layer0_output.lectures_covered} lectures covered")
        print(f"   • {layer0_output.engagement.engaged_n} engaged students")

    # Layer 1: Cross-Lesson Aggregation
    if verbose:
        print("\n" + "=" * 80)
        print("LAYER 1: Cross-Lesson Aggregation")
        print("=" * 80)

    layer1_pipeline = CourseLayer1Pipeline(config)
    layer1_output = layer1_pipeline.run(
        layer0_output=layer0_output,
        quiz_csv_path=Path(quiz_csv),
        eval_csv_path=Path(eval_csv),
        queries_csv_path=Path(queries_csv),
        correct_csv_path=Path(correct_csv),
    )

    if verbose:
        print(f"\n✅ Layer 1 Complete!")
        print(f"   • {len(layer1_output.recurring_concepts)} recurring concepts")
        print(f"   • {len(layer1_output.problematic_lessons)} problematic lessons")
        print(f"   • {len(layer1_output.consistent_successes)} consistent successes")

    # Layer 2: Rank & Package
    if verbose:
        print("\n" + "=" * 80)
        print("LAYER 2: Rank & Package")
        print("=" * 80)

    layer2_pipeline = CourseLayer2Pipeline(config)
    layer2_output = layer2_pipeline.run(
        layer1_output=layer1_output,
        layer0_output=layer0_output,  # Pass layer0 for engagement data
    )

    if verbose:
        print(f"\n✅ Layer 2 Complete!")
        print(f"   • {len(layer2_output.top_recurring_concepts)} top recurring concepts")
        print(f"   • {len(layer2_output.top_problematic_lessons)} top problematic lessons")
        print(f"   • {len(layer2_output.top_consistent_successes)} top successes")

    # Layer 3: LLM Narrative Generation
    if verbose:
        print("\n" + "=" * 80)
        print("LAYER 3: LLM Narrative Generation")
        print("=" * 80)
        print("\n⚠️  Calling OpenRouter API - this may take 30-60 seconds...")

    layer3_pipeline = CourseLayer3Pipeline(config)
    layer3_result = layer3_pipeline.run(layer2_output=layer2_output)

    if verbose:
        print(f"\n✅ Layer 3 Complete!")
        print(f"   • Generated 5-panel course dashboard")
        print(f"   • Outputs: JSON, Markdown, HTML")

    # Final Summary
    if verbose:
        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE!")
        print("=" * 80)

        output_base = Path(output_dir) / "learning_dashboard" / "course_level"

        print(f"\n📊 Course Dashboard Generated!")
        print(f"\n📁 Output Locations:")
        print(f"   Layer 0: {output_base / 'layer0'}")
        print(f"   Layer 1: {output_base / 'layer1'}")
        print(f"   Layer 2: {output_base / 'layer2'}")
        print(f"   Layer 3: {output_base / 'layer3'}")

        print(f"\n🎯 Key Outputs:")
        print(f"   • HTML Dashboard: {output_base / 'layer3' / 'course_dashboard.html'}")
        print(f"   • Markdown Report: {output_base / 'layer3' / 'course_dashboard.md'}")
        print(f"   • Complete JSON: {output_base / 'layer3' / 'complete_course_dashboard.json'}")

        print(f"\n💡 Next Steps:")
        print(f"   1. Open course_dashboard.html in your browser")
        print(f"   2. Review the 5-panel narrative")
        print(f"   3. Share with instructors for actionable insights")

    return {
        'layer0': layer0_output,
        'layer1': layer1_output,
        'layer2': layer2_output,
        'layer3': layer3_result,
    }


def main():
    """Run the complete course pipeline with default paths."""

    print("=" * 80)
    print("COURSE-LEVEL PIPELINE: End-to-End Test")
    print("=" * 80)

    # Configure paths (using defaults from test scripts)
    base_dir = Path("/home/roy/Downloads/attachments")

    try:
        results = run_complete_course_pipeline(
            queries_csv=str(base_dir / "queries.csv"),
            quiz_csv=str(base_dir / "quiz.csv"),
            eval_csv=str(base_dir / "eval.csv"),
            correct_csv=str(base_dir / "correct.csv"),
            roster_json=str(base_dir / "student_roster.json"),
            lecture_sequence_json=str(base_dir / "lecture_sequence.json"),
            class_reports_dir=str(base_dir / "output" / "learning_dashboard"),
            output_dir=str(base_dir / "output"),
            run_number=1,
            run_date="2025-11-15",  # Update with actual date
            lectures_to_include=None,  # None = all lectures
            verbose=True,
        )

        print("\n" + "=" * 80)
        print("SUCCESS! All layers completed successfully.")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())