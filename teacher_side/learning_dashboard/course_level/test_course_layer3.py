

"""
Test script for Course-Level Layer 3: LLM Narrative Generation

Tests the LLM-based narrative generation for course-level dashboard:
- Loads Course Layer 2 output (ranked patterns)
- Calls OpenRouter API to generate 5-panel narrative
- Parses markdown output into structured panels
- Generates JSON, Markdown, and HTML outputs

Expects Course Layer 2 output to already exist from a previous run.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.course_level.layer3_narrative import CourseLayer3Pipeline
from teacher_side.learning_dashboard.course_level.layer2_ranking import CourseLayer2Output
from teacher_side.learning_dashboard.common.models import (
    RecurringConcept, ProblematicLesson, ConsistentSuccess,
    SystemicGap, PrerequisiteGapCluster, GapDirection
)


def load_layer2_output(config: LearningDashboardConfig):
    """Load Course Layer 2 output from JSON."""
    import json

    layer2_dir = Path(config.paths.output_dir) / "course_level" / "layer2"
    layer2_path = layer2_dir / "course_layer2_output.json"

    if not layer2_path.exists():
        raise FileNotFoundError(
            f"Course Layer 2 output not found at {layer2_path}. "
            "Please run test_course_layer2.py first."
        )

    print(f"Loading Layer 2 output from: {layer2_path}")

    with open(layer2_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Reconstruct CourseLayer2Output from dict
    layer2_output = CourseLayer2Output(
        run_number=data['run_number'],
        run_date=data['run_date'],
        lectures_covered=data['lectures_covered'],
        total_lectures=data['total_lectures'],
        engaged_n=data['engaged_n'],
        course_eval_avg=data['course_eval_avg'],
        course_quiz_avg=data['course_quiz_avg'],
        top_recurring_concepts=[
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
            for rc in data.get('top_recurring_concepts', [])
        ],
        top_problematic_lessons=[
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
            for pl in data.get('top_problematic_lessons', [])
        ],
        top_good_lessons=data.get('top_good_lessons', []),
        top_consistent_successes=[
            ConsistentSuccess(
                concept=cs['concept'],
                success_count=cs['success_count'],
                avg_success_rate=cs['avg_success_rate'],
                teaching_pattern=cs.get('teaching_pattern', {}),
                segment_note=cs.get('segment_note', ''),
                lectures=cs['lectures'],
            )
            for cs in data.get('top_consistent_successes', [])
        ],
        top_systemic_gaps=[
            SystemicGap(
                concept=sg['concept'],
                direction=GapDirection(sg['direction']),
                gap_appearances=sg['gap_appearances'],
                segment_gap=sg.get('segment_gap', {}),
                interpretation=sg['interpretation'],
                lectures=sg['lectures'],
            )
            for sg in data.get('top_systemic_gaps', [])
        ],
        top_prerequisite_gaps=[
            PrerequisiteGapCluster(
                topic=pg['topic'],
                unique_students=pg['unique_students'],
                appearing_in_lectures=pg['appearing_in_lectures'],
                lecture_names=pg['lecture_names'],
                out_of_scope_type=pg['out_of_scope_type'],
                example_queries=pg['example_queries'],
            )
            for pg in data.get('top_prerequisite_gaps', [])
        ],
    )

    return layer2_output


def display_panels(panels: dict):
    """Display the generated panels."""
    print("\n" + "=" * 80)
    print("COURSE LAYER 3 - GENERATED PANELS")
    print("=" * 80)

    panel_titles = {
        'course_snapshot': '📸 Course Snapshot',
        'struggles': '⚠️  What Students Struggle With',
        'successes': '✅ What Consistently Worked',
        'gaps': '📉 Teaching vs Learning Gap (Systemic)',
        'prerequisites': '📚 Prerequisite & Knowledge Gaps',
    }

    for key, title in panel_titles.items():
        print(f"\n{title}")
        print("-" * 80)
        panel_content = panels.get(key, 'No data')
        # Truncate long content for display
        if len(panel_content) > 500:
            print(panel_content[:500] + "\n... (truncated)")
        else:
            print(panel_content)


def verify_outputs(output_dir: Path):
    """Verify all output files were created."""
    print("\n" + "=" * 80)
    print("VERIFYING OUTPUT FILES")
    print("=" * 80)

    expected_files = [
        "course_dashboard.md",
        "course_dashboard_panels.json",
        "complete_course_dashboard.json",
        "course_dashboard.html",
    ]

    all_exist = True
    for filename in expected_files:
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"✅ {filename} ({size:,} bytes)")
        else:
            print(f"❌ {filename} (missing)")
            all_exist = False

    return all_exist


def main():
    """Run Course Layer 3 test."""

    print("=" * 80)
    print("COURSE-LEVEL LAYER 3: Test Script")
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
    print(f"  LLM Model: {config.llm.model_name}")
    print(f"  Output Language: {config.llm.output_language}")

    # Load Layer 2 output
    print("\n[Loading Course Layer 2 output...]")
    try:
        layer2_output = load_layer2_output(config)
        print(f"✅ Loaded Layer 2 output (Run {layer2_output.run_number}, {layer2_output.lectures_covered} lectures)")
        print(f"   • {len(layer2_output.top_recurring_concepts)} recurring concepts")
        print(f"   • {len(layer2_output.top_problematic_lessons)} problematic lessons")
        print(f"   • {len(layer2_output.top_good_lessons)} good lessons")
        print(f"   • {len(layer2_output.top_consistent_successes)} consistent successes")
        print(f"   • {len(layer2_output.top_systemic_gaps)} systemic gaps")
        print(f"   • {len(layer2_output.top_prerequisite_gaps)} prerequisite gaps")
    except Exception as e:
        print(f"\n❌ Failed to load Layer 2 output: {e}")
        print("\n⚠️  Please run test_course_layer2.py first to generate Layer 2 output.")
        import traceback
        traceback.print_exc()
        return

    # Run Layer 3 pipeline
    print("\n" + "=" * 80)
    print("RUNNING COURSE LAYER 3 PIPELINE")
    print("=" * 80)
    print("\n⚠️  This will call OpenRouter API - may take 30-60 seconds...")

    pipeline = CourseLayer3Pipeline(config)

    try:
        output_dir = Path(config.paths.output_dir) / "course_level" / "layer3"
        panels = pipeline.run(layer2_output=layer2_output, output_dir=output_dir)

        # Display generated panels
        display_panels(panels)

        # Verify output files
        all_files_exist = verify_outputs(output_dir)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        if all_files_exist:
            print(f"""
✅ Course Layer 3 Complete!

📁 Output saved to: {output_dir}

📄 Generated Files:
   • course_dashboard.md - Full narrative in markdown
   • course_dashboard_panels.json - Parsed panels (5 sections)
   • complete_course_dashboard.json - Layer 2 + Layer 3 combined
   • course_dashboard.html - Visual dashboard with Hebrew RTL support

📊 5-Panel Dashboard:
   1. Course Snapshot - Overall engagement & performance
   2. What Students Struggle With - Recurring concepts + problematic lessons
   3. What Consistently Worked - Successful topics + good lessons
   4. Teaching vs Learning Gap - Systemic gaps
   5. Prerequisite & Knowledge Gaps - Foundational gaps

Next steps:
1. Open course_dashboard.html in a web browser to view the visual dashboard
2. Review the narrative quality and panel content
3. Adjust prompts in CoursePromptBuilder if needed
4. Integrate with full course reporting pipeline
            """)
        else:
            print("\n⚠️  Some output files are missing. Check the pipeline logs above.")

    except Exception as e:
        print(f"\n❌ Layer 3 pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()