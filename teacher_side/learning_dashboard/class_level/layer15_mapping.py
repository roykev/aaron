"""
Layer 1.5: Map Clusters to Lesson Content
Maps signal clusters to concepts using semantic similarity (no LLM needed).
Computes teaching investment for each concept.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from ..common.models import (
    SignalCluster,
    Concept,
    Section,
    Example,
    InClassInteraction,
    TeachingInvestment,
    TimeRange,
)
from ..common.config import LearningDashboardConfig


class SemanticConceptMapper:
    """Maps clusters to sections using embedding similarity."""

    def __init__(self, config: LearningDashboardConfig, embedding_model: SentenceTransformer):
        self.config = config
        self.model = embedding_model

    def map_concepts_to_sections(
        self,
        concepts: List[Concept],
        sections: List[Section],
    ) -> Dict[str, List[str]]:
        """
        Map concepts to sections by TIME OVERLAP (concepts can appear in multiple sections).

        Args:
            concepts: List of Concept objects
            sections: List of Section objects

        Returns:
            Dict mapping concept_name → list of section titles
        """
        concept_to_sections = {}

        for concept in concepts:
            concept_to_sections[concept.concept] = []

            for time_range in concept.times:
                concept_start = time_range.to_seconds(time_range.start)
                concept_end = time_range.to_seconds(time_range.end)

                # Find all sections that overlap with this concept time range
                for section in sections:
                    section_start = TimeRange("00:00:00", "00:00:00").to_seconds(section.start_time)
                    section_end = TimeRange("00:00:00", "00:00:00").to_seconds(section.end_time)

                    # Check for overlap
                    if not (concept_end < section_start or concept_start > section_end):
                        if section.title not in concept_to_sections[concept.concept]:
                            concept_to_sections[concept.concept].append(section.title)

                        if self.config.verbose:
                            print(f"Concept '{concept.concept}' → Section '{section.title}' (time overlap)")

        return concept_to_sections

    def map_inclass_questions_to_sections(
        self,
        inclass_signals: List,  # InClassQuestionSignal
        sections: List[Section],
    ) -> Dict[int, str]:
        """
        Map in-class questions to sections by TIMESTAMP.

        Args:
            inclass_signals: List of InClassQuestionSignal objects
            sections: List of Section objects

        Returns:
            Dict mapping signal index → section title
        """
        mapping = {}

        for idx, signal in enumerate(inclass_signals):
            # Parse timestamp
            try:
                time_parts = signal.timestamp.split(':')
                if len(time_parts) == 2:
                    m, s = map(int, time_parts)
                    question_sec = m * 60 + s
                elif len(time_parts) == 3:
                    h, m, s = map(int, time_parts)
                    question_sec = h * 3600 + m * 60 + s
                else:
                    continue
            except (ValueError, AttributeError):
                continue

            # Find which section this timestamp falls into
            for section in sections:
                section_start = TimeRange("00:00:00", "00:00:00").to_seconds(section.start_time)
                section_end = TimeRange("00:00:00", "00:00:00").to_seconds(section.end_time)

                if section_start <= question_sec <= section_end:
                    mapping[idx] = section.title
                    if self.config.verbose:
                        print(f"In-class Q at {signal.timestamp} → Section '{section.title}'")
                    break

        return mapping

    def map_inclass_questions_to_concepts(
        self,
        inclass_signals: List,  # InClassQuestionSignal
        concepts: List[Concept],
    ) -> Dict[int, str]:
        """
        Map in-class questions to concepts by TIMESTAMP (not content).

        Args:
            inclass_signals: List of InClassQuestionSignal objects
            concepts: List of Concept objects

        Returns:
            Dict mapping signal index → concept name
        """
        mapping = {}

        for idx, signal in enumerate(inclass_signals):
            # Parse timestamp
            try:
                time_parts = signal.timestamp.split(':')
                if len(time_parts) == 2:
                    m, s = map(int, time_parts)
                    question_sec = m * 60 + s
                elif len(time_parts) == 3:
                    h, m, s = map(int, time_parts)
                    question_sec = h * 3600 + m * 60 + s
                else:
                    continue
            except (ValueError, AttributeError):
                continue

            # Find which concept this timestamp falls into
            for concept in concepts:
                for time_range in concept.times:
                    start_sec = time_range.to_seconds(time_range.start)
                    end_sec = time_range.to_seconds(time_range.end)

                    if start_sec <= question_sec <= end_sec:
                        mapping[idx] = concept.concept
                        if self.config.verbose:
                            print(f"In-class Q at {signal.timestamp} → Concept '{concept.concept}'")
                        break

                if idx in mapping:
                    break

        return mapping

    def map_clusters_to_sections(
        self,
        clusters: List[SignalCluster],
        sections: List[Section],
    ) -> List[SignalCluster]:
        """
        Map each cluster to the most similar section using embeddings.

        Args:
            clusters: List of SignalCluster objects
            sections: List of Section objects

        Returns:
            Same list of clusters with matched_section filled in
        """
        if not sections:
            if self.config.verbose:
                print("Warning: No sections provided for mapping")
            return clusters

        # Embed all section titles
        section_titles = [s.title for s in sections]
        section_embeddings = self.model.encode(
            section_titles,
            show_progress_bar=self.config.clustering.verbose,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Map each cluster
        for cluster in clusters:
            # Embed cluster label
            cluster_embedding = self.model.encode(
                [cluster.cluster_label],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )[0]

            # Find best matching section
            section_similarities = section_embeddings @ cluster_embedding
            best_section_idx = int(np.argmax(section_similarities))
            best_section_sim = float(section_similarities[best_section_idx])

            # Map to section
            cluster.matched_section = sections[best_section_idx].title

            # Determine confidence based on similarity
            if best_section_sim >= 0.60:
                cluster.mapping_confidence = "high"
            elif best_section_sim >= 0.45:
                cluster.mapping_confidence = "medium"
            elif best_section_sim >= 0.30:
                cluster.mapping_confidence = "low"
            else:
                cluster.mapping_confidence = "none"
                cluster.matched_section = None
                cluster.mapping_note = f"No good match (best similarity: {best_section_sim:.2f})"

            if self.config.verbose and cluster.matched_section:
                print(f"Cluster '{cluster.cluster_label[:50]}...' → "
                      f"Section '{cluster.matched_section}' "
                      f"(confidence: {cluster.mapping_confidence}, "
                      f"similarity: {best_section_sim:.2f})")

        return clusters

    def map_clusters_to_concepts(
        self,
        clusters: List[SignalCluster],
        concepts: List[Concept],
        sections: List[Section],
    ) -> List[SignalCluster]:
        """
        Map each cluster to the most similar concept using embeddings.

        Args:
            clusters: List of SignalCluster objects
            concepts: List of Concept objects
            sections: List of Section objects

        Returns:
            Same list of clusters with matched_concept, matched_section filled in
        """
        if not concepts:
            if self.config.verbose:
                print("Warning: No concepts provided for mapping")
            return clusters

        # Embed all concept names
        concept_names = [c.concept for c in concepts]
        concept_embeddings = self.model.encode(
            concept_names,
            show_progress_bar=self.config.clustering.verbose,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Embed all section titles (for secondary matching)
        section_titles = [s.title for s in sections]
        section_embeddings = None
        if section_titles:
            section_embeddings = self.model.encode(
                section_titles,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

        # Map each cluster
        for cluster in clusters:
            # Embed cluster label
            cluster_embedding = self.model.encode(
                [cluster.cluster_label],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )[0]

            # Find best matching concept
            concept_similarities = concept_embeddings @ cluster_embedding
            best_concept_idx = int(np.argmax(concept_similarities))
            best_concept_sim = float(concept_similarities[best_concept_idx])

            # Map to concept
            matched_concept = concepts[best_concept_idx]
            cluster.matched_concept = matched_concept.concept

            # Determine confidence based on similarity
            if best_concept_sim >= 0.75:
                cluster.mapping_confidence = "high"
            elif best_concept_sim >= 0.60:
                cluster.mapping_confidence = "medium"
            elif best_concept_sim >= 0.45:
                cluster.mapping_confidence = "low"
            else:
                cluster.mapping_confidence = "none"
                cluster.matched_concept = None
                cluster.mapping_note = f"No good match (best similarity: {best_concept_sim:.2f})"

            # Find matching section
            if section_embeddings is not None and cluster.matched_concept:
                section_similarities = section_embeddings @ cluster_embedding
                best_section_idx = int(np.argmax(section_similarities))
                best_section_sim = float(section_similarities[best_section_idx])

                if best_section_sim >= 0.50:
                    cluster.matched_section = sections[best_section_idx].title
                else:
                    # Try to find section by time overlap with concept
                    cluster.matched_section = self._find_section_by_time(
                        matched_concept, sections
                    )
            else:
                cluster.matched_section = None

            if self.config.verbose and cluster.matched_concept:
                print(f"Cluster '{cluster.cluster_label[:50]}...' → "
                      f"Concept '{cluster.matched_concept}' "
                      f"(confidence: {cluster.mapping_confidence}, "
                      f"similarity: {best_concept_sim:.2f})")

        return clusters

    def _find_section_by_time(
        self,
        concept: Concept,
        sections: List[Section],
    ) -> Optional[str]:
        """
        Find section that overlaps with concept's time range.

        Args:
            concept: Concept object
            sections: List of Section objects

        Returns:
            Section title or None
        """
        if not concept.times or not sections:
            return None

        # Get concept's first time range
        concept_time = concept.times[0]
        concept_start_sec = concept_time.to_seconds(concept_time.start)
        concept_end_sec = concept_time.to_seconds(concept_time.end)

        # Find overlapping section
        for section in sections:
            section_start_sec = TimeRange("00:00:00", "00:00:00").to_seconds(section.start_time)
            section_end_sec = TimeRange("00:00:00", "00:00:00").to_seconds(section.end_time)

            # Check for overlap
            if not (concept_end_sec < section_start_sec or concept_start_sec > section_end_sec):
                return section.title

        return None


class TeachingInvestmentCalculator:
    """Computes teaching investment scores for concepts."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def compute_teaching_investment(
        self,
        concepts: List[Concept],
        sections: List[Section],
        examples: List[Example],
        interactions: List[InClassInteraction],
        question_concept_map: Dict[int, str],  # question_number → concept
    ) -> Dict[str, TeachingInvestment]:
        """
        Compute teaching investment for each concept.

        Args:
            concepts: List of Concept objects
            sections: List of Section objects
            examples: List of Example objects
            interactions: List of InClassInteraction objects
            question_concept_map: Mapping of question numbers to concepts

        Returns:
            Dict mapping concept_name → TeachingInvestment
        """
        investments: Dict[str, TeachingInvestment] = {}

        # Calculate total lesson time
        total_lesson_minutes = sum(c.total_duration_minutes for c in concepts)

        if total_lesson_minutes == 0:
            if self.config.verbose:
                print("Warning: Total lesson time is 0")
            total_lesson_minutes = 1.0  # Avoid division by zero

        # Build example lookup
        example_topics = set(ex.topic for ex in examples)

        # Build in-class questions lookup by time
        inclass_questions_by_concept = self._map_interactions_to_concepts(
            interactions, concepts
        )

        # Calculate assessment weight
        total_questions = len(question_concept_map)
        question_counts_by_concept: Dict[str, int] = {}
        for concept_name in question_concept_map.values():
            question_counts_by_concept[concept_name] = \
                question_counts_by_concept.get(concept_name, 0) + 1

        # Compute investment for each concept
        for concept in concepts:
            concept_name = concept.concept
            time_minutes = concept.total_duration_minutes
            time_pct = time_minutes / total_lesson_minutes if total_lesson_minutes > 0 else 0.0

            # Check if example was used
            example_used = concept_name in example_topics

            # Count in-class questions during this concept
            inclass_questions_n = inclass_questions_by_concept.get(concept_name, 0)

            # Assessment weight
            question_count = question_counts_by_concept.get(concept_name, 0)
            assessment_weight = question_count / total_questions if total_questions > 0 else 0.0

            # Create investment object
            investment = TeachingInvestment(
                concept=concept_name,
                time_minutes=time_minutes,
                time_pct=time_pct,
                example_used=example_used,
                inclass_questions_n=inclass_questions_n,
                assessment_weight=assessment_weight,
            )

            # Compute score
            investment.teaching_investment_score = investment.compute_score(total_lesson_minutes)

            investments[concept_name] = investment

        return investments

    def _map_interactions_to_concepts(
        self,
        interactions: List[InClassInteraction],
        concepts: List[Concept],
    ) -> Dict[str, int]:
        """
        Map in-class questions to concepts based on timestamp.

        Args:
            interactions: List of InClassInteraction objects
            concepts: List of Concept objects

        Returns:
            Dict mapping concept_name → count of questions
        """
        questions_by_concept: Dict[str, int] = {}

        # Filter to question interactions only
        questions = [
            i for i in interactions
            if 'שאלת' in i.interaction_type or 'question' in i.interaction_type.lower()
        ]

        for question in questions:
            # Convert time to seconds
            try:
                time_parts = question.time.split(':')
                if len(time_parts) == 2:
                    m, s = map(int, time_parts)
                    question_sec = m * 60 + s
                elif len(time_parts) == 3:
                    h, m, s = map(int, time_parts)
                    question_sec = h * 3600 + m * 60 + s
                else:
                    continue
            except (ValueError, AttributeError):
                continue

            # Find which concept this falls into
            for concept in concepts:
                for time_range in concept.times:
                    start_sec = time_range.to_seconds(time_range.start)
                    end_sec = time_range.to_seconds(time_range.end)

                    if start_sec <= question_sec <= end_sec:
                        questions_by_concept[concept.concept] = \
                            questions_by_concept.get(concept.concept, 0) + 1
                        break

        return questions_by_concept


class QuestionConceptMapper:
    """Maps quiz/eval questions to concepts using semantic similarity."""

    def __init__(self, config: LearningDashboardConfig, embedding_model: SentenceTransformer):
        self.config = config
        self.model = embedding_model

    def map_questions_to_concepts(
        self,
        question_texts: List[str],
        concepts: List[Concept],
    ) -> Dict[int, str]:
        """
        Map question numbers to concept names using semantic similarity.

        Args:
            question_texts: List of question texts (index = question_number - 1)
            concepts: List of Concept objects

        Returns:
            Dict mapping question_number → concept_name
        """
        if not question_texts or not concepts:
            return {}

        # Embed questions
        question_embeddings = self.model.encode(
            question_texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Embed concepts
        concept_names = [c.concept for c in concepts]
        concept_embeddings = self.model.encode(
            concept_names,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Map each question to best concept
        question_concept_map = {}
        for q_idx, q_embedding in enumerate(question_embeddings):
            similarities = concept_embeddings @ q_embedding
            best_concept_idx = int(np.argmax(similarities))
            best_similarity = float(similarities[best_concept_idx])

            # Only map if similarity is reasonable
            if best_similarity >= 0.40:
                question_number = q_idx + 1
                concept_name = concepts[best_concept_idx].concept
                question_concept_map[question_number] = concept_name

                if self.config.verbose:
                    print(f"Question {question_number} → Concept '{concept_name}' "
                          f"(similarity: {best_similarity:.2f})")

        return question_concept_map


class Layer15Pipeline:
    """Main pipeline for Layer 1.5: mapping clusters to lesson content."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.model: Optional[SentenceTransformer] = None

    def _load_model(self):
        """Load embedding model (lazy loading, reuse from Layer 1 if possible)."""
        if self.model is None:
            if self.config.verbose:
                print(f"Loading embedding model: {self.config.clustering.model_name}")

            self.model = SentenceTransformer(self.config.clustering.model_name)

    def run(
        self,
        clusters: List[SignalCluster],
        concepts: List[Concept],
        sections: List[Section],
        examples: List[Example],
        interactions: List[InClassInteraction],
        question_texts: List[str],  # From eval.csv
        inclass_signals: Optional[List] = None,  # InClassQuestionSignal from Layer 1
        output_dir: Optional[Path] = None,
    ) -> Dict[str, any]:
        """
        Run the complete Layer 1.5 pipeline.

        Args:
            clusters: List of SignalCluster objects from Layer 1
            concepts: List of Concept objects
            sections: List of Section objects
            examples: List of Example objects
            interactions: List of InClassInteraction objects
            question_texts: List of evaluation question texts
            inclass_signals: List of InClassQuestionSignal objects (mapped by time, not content)
            output_dir: Directory to save outputs

        Returns:
            Dict with:
                - 'clusters': List[SignalCluster] (with mapping filled in)
                - 'teaching_investments': Dict[str, TeachingInvestment]
                - 'question_concept_map': Dict[int, str]
                - 'inclass_question_map': Dict[int, str] (signal index → concept)
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "layer15"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Load model
        self._load_model()

        # Create mapper
        section_mapper = SemanticConceptMapper(self.config, self.model)

        # 0. Map concepts to sections (for reference)
        if self.config.verbose:
            print(f"Mapping {len(concepts)} concepts to sections by time...")

        concept_to_sections = section_mapper.map_concepts_to_sections(concepts, sections)

        if self.config.verbose:
            total_mappings = sum(len(secs) for secs in concept_to_sections.values())
            print(f"Mapped {len(concept_to_sections)} concepts to {total_mappings} section references")

        # 1. Map clusters to sections (semantic similarity)
        if self.config.verbose:
            print(f"Mapping {len(clusters)} clusters to sections...")

        clusters = section_mapper.map_clusters_to_sections(clusters, sections)

        # Count successful mappings
        mapped_clusters = sum(1 for c in clusters if c.matched_section is not None)
        if self.config.verbose:
            print(f"Mapped {mapped_clusters}/{len(clusters)} clusters to sections")

        # 2. Map in-class questions to sections by timestamp
        inclass_section_map = {}
        if inclass_signals:
            if self.config.verbose:
                print(f"Mapping {len(inclass_signals)} in-class questions to sections by timestamp...")

            inclass_section_map = section_mapper.map_inclass_questions_to_sections(
                inclass_signals, sections
            )

            if self.config.verbose:
                print(f"Mapped {len(inclass_section_map)}/{len(inclass_signals)} in-class questions to sections")

        # 3. Map eval questions to sections (via concepts first, then use concept→section mapping)
        if self.config.verbose:
            print(f"Mapping {len(question_texts)} questions to sections...")

        question_mapper = QuestionConceptMapper(self.config, self.model)
        question_concept_map = question_mapper.map_questions_to_concepts(
            question_texts, concepts
        )

        # Convert question→concept to question→section using the concept_to_sections mapping
        question_section_map = {}
        for q_num, concept_name in question_concept_map.items():
            # Get sections for this concept
            sections_for_concept = concept_to_sections.get(concept_name, [])
            if sections_for_concept:
                # Use first section if concept appears in multiple
                question_section_map[q_num] = sections_for_concept[0]

        if self.config.verbose:
            print(f"Mapped {len(question_section_map)}/{len(question_texts)} questions to sections")

        # 4. Compute teaching investment
        if self.config.verbose:
            print("Computing teaching investment scores...")

        investment_calc = TeachingInvestmentCalculator(self.config)
        teaching_investments = investment_calc.compute_teaching_investment(
            concepts, sections, examples, interactions, question_concept_map
        )

        if self.config.verbose:
            print(f"Computed investment for {len(teaching_investments)} concepts")

        # Save outputs
        self._save_outputs(
            clusters, teaching_investments, question_section_map, inclass_section_map,
            concept_to_sections, output_dir
        )

        return {
            'clusters': clusters,
            'teaching_investments': teaching_investments,
            'question_section_map': question_section_map,
            'inclass_section_map': inclass_section_map,
            'concept_to_sections': concept_to_sections,
        }

    def _save_outputs(
        self,
        clusters: List[SignalCluster],
        teaching_investments: Dict[str, TeachingInvestment],
        question_section_map: Dict[int, str],
        inclass_section_map: Dict[int, str],
        concept_to_sections: Dict[str, List[str]],
        output_dir: Path,
    ):
        """Save intermediate outputs."""
        # Save cluster-section mapping
        mapping_data = []
        for cluster in clusters:
            mapping_data.append({
                'cluster_id': cluster.cluster_id,
                'cluster_label': cluster.cluster_label,
                'matched_section': cluster.matched_section,
                'mapping_confidence': cluster.mapping_confidence,
                'mapping_note': cluster.mapping_note,
            })

        mapping_path = output_dir / "cluster_section_mapping.json"
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved cluster-section mapping to {mapping_path}")

        # Save teaching investment
        investment_data = {
            concept: {
                'time_minutes': inv.time_minutes,
                'time_pct': inv.time_pct,
                'example_used': inv.example_used,
                'inclass_questions_n': inv.inclass_questions_n,
                'assessment_weight': inv.assessment_weight,
                'teaching_investment_score': inv.teaching_investment_score,
            }
            for concept, inv in teaching_investments.items()
        }

        investment_path = output_dir / "teaching_investment.json"
        with open(investment_path, 'w', encoding='utf-8') as f:
            json.dump(investment_data, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved teaching investment to {investment_path}")

        # Save question-section mapping
        question_map_path = output_dir / "question_section_map.json"
        with open(question_map_path, 'w', encoding='utf-8') as f:
            json.dump(
                {str(k): v for k, v in question_section_map.items()},
                f,
                ensure_ascii=False,
                indent=2
            )

        if self.config.verbose:
            print(f"Saved question-section mapping to {question_map_path}")

        # Save in-class question-section mapping
        if inclass_section_map:
            inclass_map_path = output_dir / "inclass_section_map.json"
            with open(inclass_map_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {str(k): v for k, v in inclass_section_map.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )

            if self.config.verbose:
                print(f"Saved in-class question-section mapping to {inclass_map_path}")

        # Save concept-to-sections mapping
        concept_sections_path = output_dir / "concept_to_sections.json"
        with open(concept_sections_path, 'w', encoding='utf-8') as f:
            json.dump(concept_to_sections, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved concept-to-sections mapping to {concept_sections_path}")