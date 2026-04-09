"""
Layer 1: Student Signal Clustering
Groups student signals by topic using semantic embeddings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Set, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from ..common.models import (
    StudentSignal,
    SignalCluster,
    SignalType,
    EvidenceStrength,
)
from ..common.config import LearningDashboardConfig


class SignalEmbedder:
    """Generates embeddings for student signals."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.model: Optional[SentenceTransformer] = None

    def load_model(self):
        """Load the embedding model (lazy loading)."""
        if self.model is None:
            if self.config.verbose:
                print(f"Loading embedding model: {self.config.clustering.model_name}")

            self.model = SentenceTransformer(self.config.clustering.model_name)

    def embed_signals(self, signals: List[StudentSignal]) -> np.ndarray:
        """
        Generate embeddings for a list of signals.

        Args:
            signals: List of StudentSignal objects

        Returns:
            numpy array of shape (n_signals, embedding_dim)
        """
        self.load_model()

        texts = [signal.text for signal in signals]

        embeddings = self.model.encode(
            texts,
            batch_size=self.config.clustering.batch_size,
            show_progress_bar=self.config.clustering.verbose,
            convert_to_numpy=True,
            normalize_embeddings=self.config.clustering.normalize_embeddings,
        )

        return embeddings


class SemanticClusterer:
    """Clusters signals by semantic similarity using Union-Find."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def cluster(
        self,
        signals: List[StudentSignal],
        embeddings: np.ndarray
    ) -> List[SignalCluster]:
        """
        Cluster signals by semantic similarity.

        Args:
            signals: List of StudentSignal objects
            embeddings: Embedding matrix (n_signals, embedding_dim)

        Returns:
            List of SignalCluster objects
        """
        n = len(signals)

        if n == 0:
            return []

        # Compute similarity matrix
        sim_matrix = embeddings @ embeddings.T

        # Union-Find clustering
        uf = UnionFind(n)
        threshold = self.config.clustering.similarity_threshold

        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i, j] >= threshold:
                    uf.union(i, j)

        # Group signals by cluster
        cluster_map: Dict[int, List[int]] = {}
        for i in range(n):
            root = uf.find(i)
            if root not in cluster_map:
                cluster_map[root] = []
            cluster_map[root].append(i)

        # Build SignalCluster objects
        clusters = []
        for cluster_id, (root, indices) in enumerate(cluster_map.items(), start=1):
            cluster_signals = [signals[i] for i in indices]

            cluster = SignalCluster(
                cluster_id=cluster_id,
                cluster_label="",  # Will be set by labeler
                signals=cluster_signals,
            )

            clusters.append(cluster)

        return clusters


class UnionFind:
    """Union-Find data structure for clustering."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: int, b: int) -> None:
        """Union by rank."""
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            self.parent[root_a] = root_b
        elif self.rank[root_a] > self.rank[root_b]:
            self.parent[root_b] = root_a
        else:
            self.parent[root_b] = root_a
            self.rank[root_a] += 1


class ClusterLabeler:
    """Generates human-readable labels for clusters."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def label_clusters(self, clusters: List[SignalCluster]) -> List[SignalCluster]:
        """
        Generate labels for clusters.

        Args:
            clusters: List of SignalCluster objects

        Returns:
            Same list with cluster_label set
        """
        for cluster in clusters:
            cluster.cluster_label = self._generate_label(cluster)

        return clusters

    def _generate_label(self, cluster: SignalCluster) -> str:
        """
        Generate label for a single cluster.
        Uses the most frequent query text as the label.

        Args:
            cluster: SignalCluster object

        Returns:
            Cluster label string
        """
        if not cluster.signals:
            return "Empty cluster"

        # Count frequency of each text
        text_counts: Dict[str, int] = {}
        for signal in cluster.signals:
            text = signal.text.strip()
            text_counts[text] = text_counts.get(text, 0) + 1

        # Pick most frequent (shortest if tie)
        best_text = max(
            text_counts.keys(),
            key=lambda t: (text_counts[t], -len(t))
        )

        # Truncate if too long
        max_len = 120
        if len(best_text) > max_len:
            best_text = best_text[:max_len-3] + "..."

        return best_text


class ClusterAnalyzer:
    """Computes metrics for clusters."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def analyze_clusters(self, clusters: List[SignalCluster]) -> List[SignalCluster]:
        """
        Compute metrics for each cluster.

        Args:
            clusters: List of SignalCluster objects

        Returns:
            Same list with metrics filled in
        """
        for cluster in clusters:
            self._analyze_cluster(cluster)

        return clusters

    def _analyze_cluster(self, cluster: SignalCluster):
        """Compute metrics for a single cluster (modifies in place)."""
        # Count unique students (excluding None for in-class questions)
        unique_students_set: Set[str] = set()
        for signal in cluster.signals:
            if signal.student_id:
                unique_students_set.add(signal.student_id)

        cluster.unique_students = len(unique_students_set)

        # Identify signal types present
        signal_types_set: Set[SignalType] = set()
        for signal in cluster.signals:
            signal_types_set.add(signal.signal_type)

        cluster.signal_types_present = list(signal_types_set)

        # Count total signals
        cluster.signal_count = len(cluster.signals)

        # Select example texts (up to 3)
        example_texts = []
        seen_texts = set()

        for signal in cluster.signals:
            text = signal.text.strip()
            if text not in seen_texts:
                example_texts.append(text)
                seen_texts.add(text)

                if len(example_texts) >= 3:
                    break

        cluster.example_texts = example_texts

        # Compute corroboration score
        cluster.corroboration_score = cluster.compute_corroboration_score()

        # Compute evidence strength
        cluster.evidence_strength = cluster.compute_evidence_strength()


class ParticipationMetrics:
    """Computes participation and reliability metrics."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def compute_metrics(
        self,
        signals: List[StudentSignal],
        quiz_df: pd.DataFrame,
        eval_df: pd.DataFrame,
    ) -> Dict[str, any]:
        """
        Compute participation and reliability metrics.

        Args:
            signals: All student signals
            quiz_df: Quiz DataFrame
            eval_df: Evaluation DataFrame

        Returns:
            Dict with metrics:
                - enrolled_students
                - eval_participants
                - quiz_participants
                - query_participants
                - lesson_quiz_avg
                - lesson_eval_avg
                - lesson_gap
                - lesson_gap_flag
                - reliability_flag
        """
        # Count participants
        eval_participants = eval_df['email'].nunique() if not eval_df.empty else 0
        quiz_participants = quiz_df['email'].nunique() if not quiz_df.empty else 0

        query_student_ids = set(
            s.student_id for s in signals
            if s.signal_type == SignalType.QUERY and s.student_id
        )
        query_participants = len(query_student_ids)

        # Compute averages
        lesson_quiz_avg = quiz_df['score'].mean() if not quiz_df.empty else None
        lesson_eval_avg = eval_df['score'].mean() if not eval_df.empty else None

        # Compute gap
        if lesson_quiz_avg is not None and lesson_eval_avg is not None:
            lesson_gap = lesson_quiz_avg - lesson_eval_avg

            if lesson_gap > 30:
                lesson_gap_flag = "surface_learning"
            elif lesson_gap < -10:
                lesson_gap_flag = "inverted"
            else:
                lesson_gap_flag = "consistent"
        else:
            lesson_gap = None
            lesson_gap_flag = "unknown"

        # Reliability flag
        thresholds = self.config.significance

        if eval_participants >= thresholds.min_eval_participants_sufficient:
            reliability_flag = "sufficient"
            reliability_reason = f"{eval_participants} students completed evaluation"
        elif eval_participants >= thresholds.min_eval_participants_sparse:
            reliability_flag = "sparse"
            reliability_reason = f"Only {eval_participants} students completed evaluation"
        else:
            reliability_flag = "insufficient"
            reliability_reason = f"Insufficient data: {eval_participants} eval participants"

        return {
            'eval_participants': eval_participants,
            'quiz_participants': quiz_participants,
            'query_participants': query_participants,
            'lesson_quiz_avg': lesson_quiz_avg,
            'lesson_eval_avg': lesson_eval_avg,
            'lesson_gap': lesson_gap,
            'lesson_gap_flag': lesson_gap_flag,
            'reliability_flag': reliability_flag,
            'reliability_reason': reliability_reason,
        }


class Layer1Pipeline:
    """Main pipeline for Layer 1: clustering and analysis."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.embedder = SignalEmbedder(config)
        self.clusterer = SemanticClusterer(config)
        self.labeler = ClusterLabeler(config)
        self.analyzer = ClusterAnalyzer(config)
        self.participation = ParticipationMetrics(config)

    def run(
        self,
        signals: List[StudentSignal],
        quiz_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, any]:
        """
        Run the complete Layer 1 pipeline.

        Args:
            signals: List of cleaned student signals from Layer 0
            quiz_df: Quiz DataFrame
            eval_df: Evaluation DataFrame
            output_dir: Directory to save intermediate outputs

        Returns:
            Dict with:
                - 'clusters': List[SignalCluster]
                - 'inclass_signals': List[StudentSignal] (not clustered, mapped by time)
                - 'participation_metrics': Dict
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "layer1"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Separate in-class questions from other signals
        # In-class questions will be mapped by timestamp, not clustered
        from ..common.models import SignalType

        inclass_signals = [s for s in signals if s.signal_type == SignalType.INCLASS_QUESTION]
        clusterable_signals = [s for s in signals if s.signal_type != SignalType.INCLASS_QUESTION]

        if self.config.verbose:
            print(f"Separating signals: {len(clusterable_signals)} for clustering, "
                  f"{len(inclass_signals)} in-class questions (will map by time)")

        # 1. Generate embeddings for clusterable signals only
        if self.config.verbose:
            print(f"Generating embeddings for {len(clusterable_signals)} signals...")

        embeddings = self.embedder.embed_signals(clusterable_signals)

        # Save embeddings
        if self.config.enable_caching:
            embeddings_path = output_dir / "signal_embeddings.npy"
            np.save(embeddings_path, embeddings)

            if self.config.verbose:
                print(f"Saved embeddings to {embeddings_path}")

        # 2. Cluster signals (excluding in-class questions)
        if self.config.verbose:
            print("Clustering signals...")

        clusters = self.clusterer.cluster(clusterable_signals, embeddings)

        if self.config.verbose:
            print(f"Created {len(clusters)} clusters")

        # 3. Label clusters
        if self.config.verbose:
            print("Labeling clusters...")

        clusters = self.labeler.label_clusters(clusters)

        # 4. Analyze clusters
        if self.config.verbose:
            print("Computing cluster metrics...")

        clusters = self.analyzer.analyze_clusters(clusters)

        # 5. Compute participation metrics (use all signals for stats)
        if self.config.verbose:
            print("Computing participation metrics...")

        participation_metrics = self.participation.compute_metrics(
            signals, quiz_df, eval_df
        )

        # Save outputs
        self._save_outputs(clusters, participation_metrics, output_dir)

        return {
            'clusters': clusters,
            'inclass_signals': inclass_signals,  # Return separately for Layer 1.5
            'participation_metrics': participation_metrics,
        }

    def _save_outputs(
        self,
        clusters: List[SignalCluster],
        participation_metrics: Dict,
        output_dir: Path,
    ):
        """Save intermediate outputs for inspection."""
        # Save clusters summary
        clusters_summary = []
        for c in clusters:
            clusters_summary.append({
                'cluster_id': c.cluster_id,
                'cluster_label': c.cluster_label,
                'unique_students': c.unique_students,
                'signal_count': c.signal_count,
                'signal_types': [str(t) for t in c.signal_types_present],
                'corroboration_score': c.corroboration_score,
                'evidence_strength': str(c.evidence_strength),
                'example_texts': c.example_texts,
            })

        clusters_path = output_dir / "clusters_summary.json"
        with open(clusters_path, 'w', encoding='utf-8') as f:
            json.dump(clusters_summary, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved clusters summary to {clusters_path}")

        # Save participation metrics
        metrics_path = output_dir / "participation_metrics.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(participation_metrics, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved participation metrics to {metrics_path}")