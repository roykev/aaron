"""
Complete Pipeline Test - Layers 0 through 3
Runs the entire Learning Dashboard pipeline and generates the final markdown report.
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
from teacher_side.learning_dashboard.class_level.layer3_narrative import Layer3Pipeline


def print_separator(title: str):
    """Print a formatted section separator."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main():
    """Run the complete Learning Dashboard pipeline."""

    print_separator("LEARNING DASHBOARD - Complete Pipeline Test")

    # =========================================================================
    # Configuration
    # =========================================================================
    print("\n[1] Loading configuration...")

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
    config.clustering.verbose = False  # Reduce noise from embedding progress bars

    # Validate configuration
    errors = config.validate()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  • {error}")
        return

    print("✅ Configuration valid")

    # =========================================================================
    # LAYER 0: Data Cleaning & Deduplication
    # =========================================================================
    print_separator("LAYER 0: Data Cleaning & Deduplication")

    layer0 = Layer0Pipeline(config)
    layer0_output = layer0.run(lecture_id=config.lecture_id)

    print(f"\n✅ Extracted {layer0_output['metadata']['total_signals']} signals")
    print(f"   • {layer0_output['metadata']['query_signals']} queries")
    print(f"   • {layer0_output['metadata']['eval_failure_signals']} eval failures")
    print(f"   • {layer0_output['metadata']['inclass_question_signals']} in-class questions")

    # =========================================================================
    # LAYER 1: Student Signal Clustering
    # =========================================================================
    print_separator("LAYER 1: Student Signal Clustering")

    layer1 = Layer1Pipeline(config)

    # Load quiz and eval data
    loader = DataLoader(config)
    quiz_df = loader.load_quiz_or_eval(config.paths.quiz_csv, config.lecture_id)
    eval_df = loader.load_quiz_or_eval(config.paths.eval_csv, config.lecture_id)

    layer1_output = layer1.run(
        signals=layer0_output['signals'],
        quiz_df=quiz_df,
        eval_df=eval_df,
    )

    print(f"\n✅ Created {len(layer1_output['clusters'])} clusters")
    print(f"   • {len([c for c in layer1_output['clusters'] if c.evidence_strength.value == 'sufficient'])} sufficient evidence")
    print(f"   • {len([c for c in layer1_output['clusters'] if c.evidence_strength.value == 'moderate'])} moderate evidence")
    print(f"   • {len([c for c in layer1_output['clusters'] if c.evidence_strength.value == 'weak'])} weak evidence")

    # =========================================================================
    # LAYER 1.5: Map Clusters to Lesson Content
    # =========================================================================
    print_separator("LAYER 1.5: Map Clusters to Lesson Content")

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

    mapped_clusters = sum(1 for c in layer15_output['clusters'] if c.matched_section is not None)
    print(f"\n✅ Mapped {mapped_clusters}/{len(layer15_output['clusters'])} clusters to sections")
    print(f"   • {len(layer15_output['concept_to_sections'])} concepts mapped to sections")
    print(f"   • {len(layer15_output['teaching_investments'])} teaching investments computed")

    # =========================================================================
    # LAYER 2: Ranking & Evidence Packaging
    # =========================================================================
    print_separator("LAYER 2: Ranking & Evidence Packaging")

    layer2 = Layer2Pipeline(config)

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

    print(f"\n✅ Evidence packages created:")
    print(f"   • {len(layer2_output.issues)} issues (gate: corroboration≥3, evidence≥moderate)")
    print(f"   • {len(layer2_output.worked_well)} worked-well (gate: student+teacher signals)")
    print(f"   • {len(layer2_output.gaps)} gaps (gate: |gap_score|>0.15)")
    print(f"   • {len(layer2_output.out_of_scope)} out-of-scope topics")
    print(f"\n   Reliability: {layer2_output.reliability.flag} ({layer2_output.reliability.flag_reason})")

    # =========================================================================
    # LAYER 3: LLM Narrative Generation
    # =========================================================================
    print_separator("LAYER 3: LLM Narrative Generation")

    layer3 = Layer3Pipeline(config)

    layer3_output = layer3.run(layer2_output)

    print(f"\n✅ Generated markdown report:")
    print(f"   • Quick Snapshot: {len(layer3_output['quick_snapshot'])} chars")
    print(f"   • Issues panel: {len(layer3_output['issues'])} chars")
    print(f"   • Worked Well panel: {len(layer3_output['worked_well'])} chars")
    print(f"   • Gaps panel: {len(layer3_output['gaps'])} chars")

    # =========================================================================
    # Display Final Report
    # =========================================================================
    print_separator("FINAL DASHBOARD REPORT")

    print("\n" + layer3_output['markdown'])

    # =========================================================================
    # Summary
    # =========================================================================
    print_separator("PIPELINE SUMMARY")

    print(f"""
✅ All layers completed successfully!

Pipeline Flow:
  Layer 0 → {layer0_output['metadata']['total_signals']} signals
  Layer 1 → {len(layer1_output['clusters'])} clusters
  Layer 1.5 → {mapped_clusters} mapped to sections
  Layer 2 → {len(layer2_output.issues) + len(layer2_output.worked_well) + len(layer2_output.gaps)} evidence packages
  Layer 3 → 4-panel markdown report

Outputs saved to: {config.paths.output_dir}/
  • layer0/ - Cleaned signals
  • layer1/ - Clusters & embeddings
  • layer15/ - Section mappings & teaching investment
  • layer2/ - Evidence bundles (layer2_output.json)
  • layer3/ - Final dashboard (dashboard_output.md, complete_dashboard.json)

Dashboard reliability: {layer2_output.reliability.flag}
Lesson gap: {layer2_output.lesson_shape.lesson_gap:.1f} points ({layer2_output.lesson_shape.lesson_gap_flag})

Next steps:
1. Review the markdown report above
2. Check layer3/dashboard_output.md for the formatted output
3. Verify evidence bundles in layer2/layer2_output.json
4. If satisfied, this pipeline can be run on any lecture!
    """)


if __name__ == "__main__":
    main()