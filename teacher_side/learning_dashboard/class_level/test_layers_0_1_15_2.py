"""
Test script for Layers 0, 1, 1.5, and 2
Runs all layers up to Layer 2 and outputs results for analysis.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.class_level.layer0_data import Layer0Pipeline, DataLoader
from teacher_side.learning_dashboard.class_level.layer1_clustering import Layer1Pipeline
from teacher_side.learning_dashboard.class_level.layer15_mapping import Layer15Pipeline
from teacher_side.learning_dashboard.class_level.layer2_ranking import Layer2Pipeline


def main():
    """Run Layers 0, 1, 1.5, and 2 with real data."""

    print("=" * 80)
    print("LEARNING DASHBOARD - Testing Layers 0, 1, 1.5, 2")
    print("=" * 80)

    # Configure paths
    config = LearningDashboardConfig.from_files(
        queries_csv="/home/roy/Downloads/attachments/queries.csv",
        quiz_csv="/home/roy/Downloads/attachments/quiz.csv",
        eval_csv="/home/roy/Downloads/attachments/eval.csv",
        correct_csv="/home/roy/Downloads/attachments/correct.csv",
        concepts_json="/home/roy/Downloads/attachments/concepts.txt",
        output_txt="/home/roy/Downloads/attachments/output.txt",
        output_dir="/home/roy/Downloads/attachments/output/learning_dashboard",
        lecture_id="f867f9a3-3bab-41b3-9765-8a091544d13e",  # שיעור 1
    )

    # Enable verbose output
    config.verbose = True
    config.clustering.verbose = True

    # Validate configuration
    print("\n[1] Validating configuration...")
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  ❌ {error}")
        return

    print("✅ Configuration valid")

    # =========================================================================
    # LAYER 0: Data Cleaning & Deduplication
    # =========================================================================
    print("\n" + "=" * 80)
    print("LAYER 0: Data Cleaning & Deduplication")
    print("=" * 80)

    layer0 = Layer0Pipeline(config)
    layer0_output = layer0.run(lecture_id=config.lecture_id)

    print("\n📊 Layer 0 Results:")
    print(f"  • Total signals: {layer0_output['metadata']['total_signals']}")
    print(f"  • Query signals: {layer0_output['metadata']['query_signals']}")
    print(f"  • Eval failure signals: {layer0_output['metadata']['eval_failure_signals']}")
    print(f"  • In-class question signals: {layer0_output['metadata']['inclass_question_signals']}")

    # =========================================================================
    # LAYER 1: Student Signal Clustering
    # =========================================================================
    print("\n" + "=" * 80)
    print("LAYER 1: Student Signal Clustering")
    print("=" * 80)

    layer1 = Layer1Pipeline(config)

    # Load quiz and eval data for participation metrics
    loader = DataLoader(config)
    quiz_df = loader.load_quiz_or_eval(config.paths.quiz_csv, config.lecture_id)
    eval_df = loader.load_quiz_or_eval(config.paths.eval_csv, config.lecture_id)

    layer1_output = layer1.run(
        signals=layer0_output['signals'],
        quiz_df=quiz_df,
        eval_df=eval_df,
    )

    print("\n📊 Layer 1 Results:")
    print(f"  • Total clusters: {len(layer1_output['clusters'])}")
    print(f"  • Top cluster corroboration score: {max((c.corroboration_score for c in layer1_output['clusters']), default=0):.1f}")

    # =========================================================================
    # LAYER 1.5: Map Clusters to Lesson Content
    # =========================================================================
    print("\n" + "=" * 80)
    print("LAYER 1.5: Map Clusters to Lesson Content")
    print("=" * 80)

    # Extract question texts from eval
    question_texts = []
    correct_df = loader.load_correct_csv()
    for _, row in correct_df[correct_df['lecture_id'] == config.lecture_id].iterrows():
        import json
        eval_data = json.loads(row['evaluation'])
        for q in eval_data['questions']:
            question_texts.append(q['question'])

    layer15 = Layer15Pipeline(config)
    layer15_output = layer15.run(
        clusters=layer1_output['clusters'],
        concepts=layer0_output['concepts'],
        sections=layer0_output['sections'],
        examples=layer0_output['examples'],
        interactions=layer0_output['interactions'],
        question_texts=question_texts,
        inclass_signals=layer1_output.get('inclass_signals', []),
    )

    print("\n📊 Layer 1.5 Results:")
    mapped_clusters = sum(
        1 for c in layer15_output['clusters']
        if c.matched_section is not None
    )
    print(f"  • Mapped clusters to sections: {mapped_clusters}/{len(layer15_output['clusters'])}")

    # =========================================================================
    # LAYER 2: Ranking & Evidence Packaging
    # =========================================================================
    print("\n" + "=" * 80)
    print("LAYER 2: Ranking & Evidence Packaging")
    print("=" * 80)

    layer2 = Layer2Pipeline(config)

    # Calculate total lesson minutes
    total_lesson_minutes = sum(c.total_duration_minutes for c in layer0_output['concepts'])

    layer2_output = layer2.run(
        clusters=layer15_output['clusters'],
        teaching_investments=layer15_output['teaching_investments'],
        concept_to_sections=layer15_output['concept_to_sections'],
        participation_metrics=layer1_output['participation_metrics'],
        quiz_df=quiz_df,
        eval_df=eval_df,
        lecture_id=config.lecture_id,
        lecture_name=layer0_output['metadata']['lecture_name'],
        total_lesson_minutes=total_lesson_minutes,
        concept_count=len(layer0_output['concepts']),
    )

    print("\n📊 Layer 2 Results:")
    print(f"\n  Reliability:")
    print(f"    • Flag: {layer2_output.reliability.flag}")
    print(f"    • Reason: {layer2_output.reliability.flag_reason}")
    print(f"    • Eval participants: {layer2_output.reliability.eval_participants}")
    print(f"    • Query participants: {layer2_output.reliability.query_participants}")

    print(f"\n  Lesson Shape:")
    print(f"    • Total minutes: {layer2_output.lesson_shape.total_minutes:.1f}")
    print(f"    • Concept count: {layer2_output.lesson_shape.concept_count}")
    print(f"    • Density: {layer2_output.lesson_shape.density}")
    print(f"    • Quiz avg: {layer2_output.lesson_shape.lesson_quiz_avg:.1f}")
    print(f"    • Eval avg: {layer2_output.lesson_shape.lesson_eval_avg:.1f}")
    print(f"    • Gap: {layer2_output.lesson_shape.lesson_gap:.1f} ({layer2_output.lesson_shape.lesson_gap_flag})")

    print(f"\n  Issues ({len(layer2_output.issues)}):")
    if layer2_output.issues:
        for i, issue in enumerate(layer2_output.issues, 1):
            print(f"    {i}. {issue.cluster_label[:60]}")
            print(f"       → Section: {issue.matched_section}")
            print(f"       Students: {issue.unique_students}, Score: {issue.corroboration_score:.1f}")
            print(f"       Strength: {issue.evidence_strength}, Signals: {', '.join(issue.signal_types)}")
    else:
        print("    (No significant issues detected)")

    print(f"\n  Worked Well ({len(layer2_output.worked_well)}):")
    if layer2_output.worked_well:
        for i, ww in enumerate(layer2_output.worked_well, 1):
            print(f"    {i}. {ww.concept}")
            print(f"       Success: {ww.eval_success_rate*100:.0f}% ({ww.eval_success_n} students)")
            print(f"       Confidence: {ww.confidence}")
            print(f"       Why: {ww.why}")
    else:
        print("    (Insufficient data to confirm what worked)")

    print(f"\n  Gaps ({len(layer2_output.gaps)}):")
    if layer2_output.gaps:
        for i, gap in enumerate(layer2_output.gaps, 1):
            print(f"    {i}. {gap.concept} — {gap.direction}")
            print(f"       Gap score: {gap.raw_gap_score:.2f}")
            print(f"       {gap.interpretation_hint}")
    else:
        print("    (No significant gaps detected)")

    print(f"\n  Out-of-Scope ({len(layer2_output.out_of_scope)}):")
    if layer2_output.out_of_scope:
        for i, oos in enumerate(layer2_output.out_of_scope, 1):
            print(f"    {i}. {oos.cluster_label}")
            print(f"       {oos.unique_students} students, Type: {oos.out_of_scope_type}")
    else:
        print("    (No out-of-scope queries detected)")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"""
✅ Layer 0: Extracted {layer0_output['metadata']['total_signals']} signals
✅ Layer 1: Created {len(layer1_output['clusters'])} clusters
✅ Layer 1.5: Mapped {mapped_clusters} clusters to sections
✅ Layer 2: Generated evidence packages
   • {len(layer2_output.issues)} issues (significance gate applied)
   • {len(layer2_output.worked_well)} worked-well concepts
   • {len(layer2_output.gaps)} teaching-learning gaps
   • {len(layer2_output.out_of_scope)} out-of-scope topics

📁 Output saved to: {config.paths.output_dir}
    - layer0/: Cleaned signals and metadata
    - layer1/: Clusters, embeddings, participation metrics
    - layer15/: Section mappings, teaching investment
    - layer2/: Evidence bundles (layer2_output.json)

Next steps:
1. Review layer2/layer2_output.json for evidence quality
2. Check that significance gates are working correctly
3. If results look good, proceed to Layer 3 (LLM narrative generation)
    """)


if __name__ == "__main__":
    main()