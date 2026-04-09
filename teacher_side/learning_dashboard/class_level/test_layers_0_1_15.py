"""
Test script for Layers 0, 1, and 1.5
Runs the first three layers and outputs results for analysis.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from teacher_side.learning_dashboard.common.config import LearningDashboardConfig
from teacher_side.learning_dashboard.class_level.layer0_data import Layer0Pipeline
from teacher_side.learning_dashboard.class_level.layer1_clustering import Layer1Pipeline
from teacher_side.learning_dashboard.class_level.layer15_mapping import Layer15Pipeline


def main():
    """Run Layers 0, 1, and 1.5 with real data."""

    print("=" * 80)
    print("LEARNING DASHBOARD - Testing Layers 0, 1, 1.5")
    print("=" * 80)

    # Configure paths
    config = LearningDashboardConfig.from_files(
        queries_csv="/home/roy/Downloads/attachments/queries.csv",
        quiz_csv="/home/roy/Downloads/attachments/quiz.csv",
        eval_csv="/home/roy/Downloads/attachments/eval.csv",
        correct_csv="/home/roy/Downloads/attachments/correct.csv",
        concepts_json="/home/roy/Downloads/attachments/concepts.txt",
        output_txt="/home/roy/Downloads/attachments/output.txt",
        output_dir="/home/roy/Downloads/attachments/"
                   "output/learning_dashboard",
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
    print(f"  • Unique query students: {layer0_output['metadata']['unique_query_students']}")
    print(f"  • Unique eval students: {layer0_output['metadata']['unique_eval_students']}")
    print(f"  • Lecture: {layer0_output['metadata']['lecture_name']}")

    # =========================================================================
    # LAYER 1: Student Signal Clustering
    # =========================================================================
    print("\n" + "=" * 80)
    print("LAYER 1: Student Signal Clustering")
    print("=" * 80)

    layer1 = Layer1Pipeline(config)

    # Load quiz and eval data for participation metrics
    from teacher_side.learning_dashboard.class_level.layer0_data import DataLoader
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

    # Show cluster details
    print("\n  Clusters by evidence strength:")
    clusters_by_strength = {}
    for cluster in layer1_output['clusters']:
        strength = str(cluster.evidence_strength)
        clusters_by_strength[strength] = clusters_by_strength.get(strength, 0) + 1

    for strength, count in sorted(clusters_by_strength.items()):
        print(f"    - {strength}: {count}")

    # Show top clusters
    print("\n  Top 5 clusters by corroboration score:")
    sorted_clusters = sorted(
        layer1_output['clusters'],
        key=lambda c: c.corroboration_score,
        reverse=True
    )
    for i, cluster in enumerate(sorted_clusters[:5], 1):
        print(f"    {i}. {cluster.cluster_label[:60]}...")
        print(f"       Students: {cluster.unique_students}, "
              f"Score: {cluster.corroboration_score:.1f}, "
              f"Strength: {cluster.evidence_strength}")

    # Participation metrics
    print("\n  Participation metrics:")
    pm = layer1_output['participation_metrics']
    print(f"    - Eval participants: {pm['eval_participants']}")
    print(f"    - Quiz participants: {pm['quiz_participants']}")
    print(f"    - Query participants: {pm['query_participants']}")
    if pm['lesson_quiz_avg'] is not None:
        print(f"    - Quiz avg: {pm['lesson_quiz_avg']:.1f}")
    if pm['lesson_eval_avg'] is not None:
        print(f"    - Eval avg: {pm['lesson_eval_avg']:.1f}")
    if pm['lesson_gap'] is not None:
        print(f"    - Gap (quiz - eval): {pm['lesson_gap']:.1f} ({pm['lesson_gap_flag']})")
    print(f"    - Reliability: {pm['reliability_flag']} - {pm['reliability_reason']}")

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

    print(f"\n  Found {len(question_texts)} evaluation questions")
    print(f"  Found {len(layer1_output.get('inclass_signals', []))} in-class questions to map by time")

    layer15 = Layer15Pipeline(config)
    layer15_output = layer15.run(
        clusters=layer1_output['clusters'],
        concepts=layer0_output['concepts'],
        sections=layer0_output['sections'],
        examples=layer0_output['examples'],
        interactions=layer0_output['interactions'],
        question_texts=question_texts,
        inclass_signals=layer1_output.get('inclass_signals', []),  # Pass in-class questions
    )

    print("\n📊 Layer 1.5 Results:")

    # Mapping success rate (now mapping to sections)
    mapped_clusters = sum(
        1 for c in layer15_output['clusters']
        if c.matched_section is not None
    )
    print(f"  • Mapped clusters to sections: {mapped_clusters}/{len(layer15_output['clusters'])}")

    # Show mappings by confidence
    print("\n  Mappings by confidence:")
    mappings_by_confidence = {}
    for cluster in layer15_output['clusters']:
        conf = cluster.mapping_confidence
        mappings_by_confidence[conf] = mappings_by_confidence.get(conf, 0) + 1

    for conf, count in sorted(mappings_by_confidence.items(), reverse=True):
        print(f"    - {conf}: {count}")

    # Show top mapped clusters (to sections)
    print("\n  Top 5 mapped clusters (to sections):")
    high_conf_clusters = [
        c for c in layer15_output['clusters']
        if c.matched_section and c.mapping_confidence in ('high', 'medium')
    ]
    high_conf_clusters.sort(key=lambda c: c.corroboration_score, reverse=True)

    for i, cluster in enumerate(high_conf_clusters[:5], 1):
        print(f"    {i}. Cluster: {cluster.cluster_label[:50]}")
        print(f"       → Section: {cluster.matched_section}")
        print(f"       Confidence: {cluster.mapping_confidence}, "
              f"Students: {cluster.unique_students}")

    # Teaching investment
    print("\n  Teaching investment (top 5 by score):")
    sorted_investments = sorted(
        layer15_output['teaching_investments'].items(),
        key=lambda x: x[1].teaching_investment_score,
        reverse=True
    )
    for i, (concept, inv) in enumerate(sorted_investments[:5], 1):
        print(f"    {i}. {concept}")
        print(f"       Time: {inv.time_minutes:.1f}min ({inv.time_pct*100:.1f}%), "
              f"Example: {inv.example_used}, "
              f"Assessment: {inv.assessment_weight*100:.0f}%")
        print(f"       Score: {inv.teaching_investment_score:.2f}")

    # Question-section mapping
    print(f"\n  Question-section mappings: {len(layer15_output['question_section_map'])}/{len(question_texts)}")

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

📁 Output saved to: {config.paths.output_dir}
    - layer0/: Cleaned signals and metadata
    - layer1/: Clusters, embeddings, participation metrics
    - layer15/: Section mappings, teaching investment, concept-to-section mapping

Next steps:
1. Review the JSON files in output/ directories
2. Check cluster_section_mapping.json for mapping quality
3. Check concept_to_sections.json to see how concepts map to sections
4. Verify teaching_investment.json scores make sense
5. If results look good, proceed to Layer 2 (ranking & evidence packaging)
    """)


if __name__ == "__main__":
    main()