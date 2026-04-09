"""
Test script for Course-Level Layer 0: Normalization & Segmentation

Tests engagement normalization, student segmentation (EXCEL/MIDDLE/STRUGGLES),
and revisit signal extraction (queries >14 days after lecture).

Simulates 2 runs: mid-semester (lectures 1-7) and end-semester (all lectures).
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.course_level.layer0_normalize import CourseLayer0Pipeline


def display_run_results(output, run_name):
    """Display results for a single run."""
    print("\n" + "=" * 80)
    print(f"{run_name} - RESULTS")
    print("=" * 80)

    print(f"\n📚 Course Overview:")
    print(f"  • Run number: {output.run_number}")
    print(f"  • Run date: {output.run_date}")
    print(f"  • Lectures analyzed: {len(output.lecture_sequence)}/{output.total_lectures}")
    print(f"  • Lectures with reports: {output.lectures_covered}")

    print(f"\n👥 Engagement Metrics:")
    print(f"  • Enrolled students: {output.engagement.enrolled_n}")
    print(f"  • Engaged students: {output.engagement.engaged_n}")
    print(f"  • Engagement rate: {output.engagement.engagement_rate*100:.1f}%")

    print(f"\n📊 Student Segmentation:")
    print(f"  • EXCEL (≥75%): {output.engagement.excel_n} students ({output.engagement.excel_pct*100:.1f}%)")
    print(f"  • MIDDLE (45-75%): {output.engagement.middle_n} students ({output.engagement.middle_pct*100:.1f}%)")
    print(f"  • STRUGGLES (<45%): {output.engagement.struggles_n} students ({output.engagement.struggles_pct*100:.1f}%)")
    print(f"  • UNKNOWN (<2 evals): {output.engagement.unknown_n} students")

    if not output.engagement.min_data_for_segments:
        print(f"  ⚠️  Warning: Only {output.engagement.engaged_n} engaged students — segments may be unreliable")

    print(f"\n🔄 Revisit Signals (queries >14 days after lecture):")
    print(f"  • Total revisit queries: {output.revisit_metrics.total_revisit_count}")
    print(f"  • Unique students revisiting: {output.revisit_metrics.unique_students_revisiting}")


def main():
    """Run Course Layer 0 with 2 runs: mid-semester and end-semester."""

    print("=" * 80)
    print("COURSE-LEVEL LAYER 0: Two-Run Simulation")
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

    # Course-specific paths
    roster_path = base_dir / "student_roster.json"
    lecture_sequence_path = base_dir / "lecture_sequence.json"
    class_reports_dir = base_dir / "output" / "learning_dashboard" / "class_level"

    print("\n[Configuration]")
    print(f"  Student roster: {roster_path}")
    print(f"  Lecture sequence: {lecture_sequence_path}")
    print(f"  Quiz data: {config.paths.quiz_csv}")
    print(f"  Eval data: {config.paths.eval_csv}")
    print(f"  Queries data: {config.paths.queries_csv}")
    print(f"  Class reports directory: {class_reports_dir}")

    # Check if required files exist
    print("\n[Checking required files...]")
    missing_files = []

    if not roster_path.exists():
        missing_files.append(f"Student roster: {roster_path}")
    if not lecture_sequence_path.exists():
        missing_files.append(f"Lecture sequence: {lecture_sequence_path}")
    if not Path(config.paths.quiz_csv).exists():
        missing_files.append(f"Quiz CSV: {config.paths.quiz_csv}")
    if not Path(config.paths.eval_csv).exists():
        missing_files.append(f"Eval CSV: {config.paths.eval_csv}")
    if not Path(config.paths.queries_csv).exists():
        missing_files.append(f"Queries CSV: {config.paths.queries_csv}")

    if missing_files:
        print("\n❌ Missing required files:")
        for file in missing_files:
            print(f"   • {file}")
        print("\n⚠️  Please create these files or adjust paths in the script.")
        print("\nExpected formats:")
        print("\n1. student_roster.json:")
        print('   [{"email": "student@ono.ac.il", "name": "Student Name"}, ...]')
        print("\n2. lecture_sequence.json:")
        print('   [{"lecture_id": "abc...", "name": "שיעור 1"}, ...]')
        print("\n3. quiz.csv, eval.csv, queries.csv: Same format as class-level")
        return

    print("✅ All required files found")

    # Load lecture sequence to determine runs
    import json
    with open(lecture_sequence_path, 'r', encoding='utf-8') as f:
        lecture_sequence = json.load(f)

    total_lectures = len(lecture_sequence)
    mid_semester_lectures = total_lectures // 2  # ~7 lectures for mid-semester

    print(f"\n📅 Simulation Plan:")
    print(f"  • Total lectures: {total_lectures}")
    print(f"  • Run 1 (Mid-Semester): Lectures 1-{mid_semester_lectures}")
    print(f"  • Run 2 (End-Semester): All {total_lectures} lectures")

    pipeline = CourseLayer0Pipeline(config)

    # =========================================================================
    # RUN 1: Mid-Semester Analysis (lectures 1-7)
    # =========================================================================
    print("\n" + "=" * 80)
    print(f"RUN 1: MID-SEMESTER ANALYSIS")
    print("=" * 80)

    try:
        output_run1 = pipeline.run(
            roster_path=roster_path,
            lecture_sequence_path=lecture_sequence_path,
            quiz_csv_path=Path(config.paths.quiz_csv),
            eval_csv_path=Path(config.paths.eval_csv),
            queries_csv_path=Path(config.paths.queries_csv),
            class_reports_dir=class_reports_dir,
            run_number=1,
            run_date="2026-04-15",  # Mid-semester
            lectures_to_include=mid_semester_lectures,
        )

        display_run_results(output_run1, "RUN 1: MID-SEMESTER")

    except Exception as e:
        print(f"\n❌ Run 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # =========================================================================
    # RUN 2: End-Semester Analysis (all lectures)
    # =========================================================================
    print("\n\n" + "=" * 80)
    print(f"RUN 2: END-SEMESTER ANALYSIS")
    print("=" * 80)

    try:
        output_run2 = pipeline.run(
            roster_path=roster_path,
            lecture_sequence_path=lecture_sequence_path,
            quiz_csv_path=Path(config.paths.quiz_csv),
            eval_csv_path=Path(config.paths.eval_csv),
            queries_csv_path=Path(config.paths.queries_csv),
            class_reports_dir=class_reports_dir,
            run_number=2,
            run_date="2026-06-15",  # End-semester
        )

        display_run_results(output_run2, "RUN 2: END-SEMESTER")

    except Exception as e:
        print(f"\n❌ Run 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # =========================================================================
    # Compare Runs
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("COMPARISON: Mid-Semester vs End-Semester")
    print("=" * 80)

    print(f"\n📈 Engagement Growth:")
    engagement_change = output_run2.engagement.engaged_n - output_run1.engagement.engaged_n
    print(f"  • Engaged students: {output_run1.engagement.engaged_n} → {output_run2.engagement.engaged_n} ({engagement_change:+d})")

    print(f"\n📊 Segment Changes:")
    excel_change = output_run2.engagement.excel_n - output_run1.engagement.excel_n
    middle_change = output_run2.engagement.middle_n - output_run1.engagement.middle_n
    struggles_change = output_run2.engagement.struggles_n - output_run1.engagement.struggles_n
    print(f"  • EXCEL: {output_run1.engagement.excel_n} → {output_run2.engagement.excel_n} ({excel_change:+d})")
    print(f"  • MIDDLE: {output_run1.engagement.middle_n} → {output_run2.engagement.middle_n} ({middle_change:+d})")
    print(f"  • STRUGGLES: {output_run1.engagement.struggles_n} → {output_run2.engagement.struggles_n} ({struggles_change:+d})")

    print(f"\n🔄 Revisit Activity:")
    revisit_change = output_run2.revisit_metrics.total_revisit_count - output_run1.revisit_metrics.total_revisit_count
    print(f"  • Revisit queries: {output_run1.revisit_metrics.total_revisit_count} → {output_run2.revisit_metrics.total_revisit_count} ({revisit_change:+d})")
    print(f"  • Students revisiting: {output_run1.revisit_metrics.unique_students_revisiting} → {output_run2.revisit_metrics.unique_students_revisiting}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"""
✅ Course Layer 0 Complete! Two runs simulated successfully.

📁 Output saved to: {config.paths.output_dir}/course_level/layer0/
   • Run 1: course_layer0_output.json (mid-semester)
   • Run 2: course_layer0_output.json (end-semester)

📊 Final Metrics (End-Semester):
   • {output_run2.engagement.engaged_n}/{output_run2.engagement.enrolled_n} students engaged ({output_run2.engagement.engagement_rate*100:.1f}%)
   • {output_run2.engagement.excel_n} excel, {output_run2.engagement.middle_n} middle, {output_run2.engagement.struggles_n} struggles
   • {output_run2.revisit_metrics.total_revisit_count} revisit queries from {output_run2.revisit_metrics.unique_students_revisiting} students

Next steps:
1. Review both run outputs for data quality
2. Analyze how segments evolved from mid to end of semester
3. Check revisit patterns across the semester
4. Proceed to Course Layer 1 (recurring issues, consistent successes)
    """)


if __name__ == "__main__":
    main()