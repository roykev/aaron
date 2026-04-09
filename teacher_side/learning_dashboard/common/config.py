"""
Configuration classes for the Learning Dashboard system.
Centralizes all parameters and thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class ClusteringConfig:
    """Configuration for semantic clustering."""
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    similarity_threshold: float = 0.84
    min_cluster_size: int = 1
    batch_size: int = 64
    normalize_embeddings: bool = True
    verbose: bool = False


@dataclass
class SignificanceThresholds:
    """Thresholds for significance gates (Layer 2)."""
    # Issue significance
    min_corroboration_score: float = 3.0
    min_evidence_strength: str = "moderate"  # "sufficient" | "moderate" | "weak"

    # Worked-well significance
    max_eval_failure_rate: float = 0.25
    min_example_or_time: bool = True

    # Gap significance
    min_gap_score: float = 0.15

    # Out-of-scope
    min_students_out_of_scope: int = 2

    # Reliability
    min_eval_participants_sufficient: int = 5
    min_eval_participants_sparse: int = 2


@dataclass
class ScoringWeights:
    """Weights for various scoring formulas."""
    # Teaching investment score weights
    teaching_time_weight: float = 0.40
    teaching_assessment_weight: float = 0.25
    teaching_example_weight: float = 0.20
    teaching_no_friction_weight: float = 0.15

    # Evidence score weights
    evidence_eval_failure_weight: float = 0.40
    evidence_query_weight: float = 0.30
    evidence_surface_learning_weight: float = 0.15
    evidence_misconception_weight: float = 0.15

    # Corroboration score weights
    corroboration_signal_type_multiplier: float = 1.5
    corroboration_inclass_bonus: float = 1.0

    # Combined performance weights
    eval_weight: float = 0.7
    quiz_weight: float = 0.3


@dataclass
class RankingConfig:
    """Configuration for ranking in Layer 2."""
    max_issues: int = 3
    max_worked_well: int = 2
    max_gaps: int = 3
    max_out_of_scope: int = 5


@dataclass
class NoiseFilterConfig:
    """Configuration for noise removal in Layer 0."""
    # Query patterns to remove
    keyboard_gibberish_pattern: str = r"^[a-zA-Z,\.\s]{1,8}$"
    session_close_terms: List[str] = field(default_factory=lambda: [
        "ביי", "bye", "שלום", "להתראות", "תודה", "thanks"
    ])

    # Deduplication
    levenshtein_threshold: int = 2
    min_query_length: int = 2


@dataclass
class LLMConfig:
    """Configuration for LLM calls via OpenRouter."""
    model_name: str = "nvidia/nemotron-3-super-120b-a12b:free"  # Amazon Nova via OpenRouter (free)
    model_name: str ="minimax/minimax-m2.5:free"
    #model_name: str ="google/gemma-4-31b-it:free"
    #model_name: str ="nvidia/nemotron-3-super-120b-a12b:free"
    #model_name: str = "nvidia/nemotron-nano-12b-v2-vl:free"
    temperature: float = 0.2
    max_tokens: int = 5000
    output_language: str = "Hebrew"  # "Hebrew" | "English"


@dataclass
class PathsConfig:
    """File paths configuration."""
    # Input paths
    queries_csv: Optional[Path] = None
    quiz_csv: Optional[Path] = None
    eval_csv: Optional[Path] = None
    correct_csv: Optional[Path] = None
    concepts_json: Optional[Path] = None
    sections_csv: Optional[Path] = None
    output_txt: Optional[Path] = None
    pedagogy_analysis_md: Optional[Path] = None

    # Output paths
    output_dir: Path = Path("./output/learning_dashboard")
    cache_dir: Path = Path("./cache/learning_dashboard")

    def __post_init__(self):
        """Ensure output directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class LearningDashboardConfig:
    """Master configuration for the Learning Dashboard system."""
    # Sub-configurations
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    significance: SignificanceThresholds = field(default_factory=SignificanceThresholds)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    ranking: RankingConfig = field(default_factory=RankingConfig)
    noise_filter: NoiseFilterConfig = field(default_factory=NoiseFilterConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)

    # General settings
    lecture_id: Optional[str] = None
    lecture_name: Optional[str] = None
    enable_caching: bool = True
    verbose: bool = False

    @classmethod
    def from_files(
        cls,
        queries_csv: str | Path,
        quiz_csv: str | Path,
        eval_csv: str | Path,
        correct_csv: str | Path,
        concepts_json: Optional[str | Path] = None,
        output_txt: Optional[str | Path] = None,
        output_dir: str | Path = "./output/learning_dashboard",
        lecture_id: Optional[str] = None,
        lecture_name: Optional[str] = None,
    ) -> LearningDashboardConfig:
        """
        Create configuration from file paths.

        Args:
            queries_csv: Path to queries.csv
            quiz_csv: Path to quiz.csv
            eval_csv: Path to eval.csv
            correct_csv: Path to correct.csv (question bank)
            concepts_json: Path to concepts.txt/json - Optional for course-level
            output_txt: Path to output.txt (sections, examples, interactions) - Optional for course-level
            output_dir: Output directory for results
            lecture_id: Specific lecture ID to analyze
            lecture_name: Specific lecture name to analyze

        Returns:
            Configured LearningDashboardConfig instance
        """
        paths = PathsConfig(
            queries_csv=Path(queries_csv),
            quiz_csv=Path(quiz_csv),
            eval_csv=Path(eval_csv),
            correct_csv=Path(correct_csv),
            concepts_json=Path(concepts_json) if concepts_json else None,
            output_txt=Path(output_txt) if output_txt else None,
            output_dir=Path(output_dir),
        )

        return cls(
            paths=paths,
            lecture_id=lecture_id,
            lecture_name=lecture_name,
        )

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check required input files exist (core CSV files always required)
        required_files = {
            "queries_csv": self.paths.queries_csv,
            "quiz_csv": self.paths.quiz_csv,
            "eval_csv": self.paths.eval_csv,
            "correct_csv": self.paths.correct_csv,
        }

        for name, path in required_files.items():
            if path is None:
                errors.append(f"Missing required path: {name}")
            elif not path.exists():
                errors.append(f"File not found: {name} at {path}")

        # Check optional files if provided
        optional_files = {
            "concepts_json": self.paths.concepts_json,
            "output_txt": self.paths.output_txt,
        }

        for name, path in optional_files.items():
            if path is not None and not path.exists():
                errors.append(f"File not found: {name} at {path}")

        # Validate weights sum to reasonable values
        teaching_weights_sum = (
            self.scoring.teaching_time_weight +
            self.scoring.teaching_assessment_weight +
            self.scoring.teaching_example_weight +
            self.scoring.teaching_no_friction_weight
        )
        if abs(teaching_weights_sum - 1.0) > 0.01:
            errors.append(
                f"Teaching investment weights should sum to 1.0, got {teaching_weights_sum}"
            )

        # Validate thresholds are positive
        if self.significance.min_corroboration_score < 0:
            errors.append("min_corroboration_score must be positive")

        if not (0 <= self.significance.min_gap_score <= 1):
            errors.append("min_gap_score must be between 0 and 1")

        return errors