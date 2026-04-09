"""
Common utilities and models shared between class-level and course-level analysis.
"""
from .config import (
    LearningDashboardConfig,
    ClusteringConfig,
    SignificanceThresholds,
    ScoringWeights,
    RankingConfig,
    NoiseFilterConfig,
    LLMConfig,
    PathsConfig,
)
from .models import (
    # Enums
    SignalType,
    EvidenceStrength,
    GapDirection,
    ReliabilityFlag,
    QueryType,
    # Core structures
    TimeRange,
    Concept,
    Section,
    Example,
    InClassInteraction,
    # Signals
    StudentSignal,
    QuerySignal,
    EvalFailureSignal,
    InClassQuestionSignal,
    # Clustering
    SignalCluster,
    # Teaching investment
    TeachingInvestment,
    # Evidence bundles
    IssueEvidenceBundle,
    WorkedWellEvidenceBundle,
    GapEvidenceBundle,
    OutOfScopeCluster,
    # Layer 2 output
    LessonReliability,
    LessonShape,
    Layer2Output,
    DashboardOutput,
)

__all__ = [
    # Config
    "LearningDashboardConfig",
    "ClusteringConfig",
    "SignificanceThresholds",
    "ScoringWeights",
    "RankingConfig",
    "NoiseFilterConfig",
    "LLMConfig",
    "PathsConfig",
    # Enums
    "SignalType",
    "EvidenceStrength",
    "GapDirection",
    "ReliabilityFlag",
    "QueryType",
    # Core structures
    "TimeRange",
    "Concept",
    "Section",
    "Example",
    "InClassInteraction",
    # Signals
    "StudentSignal",
    "QuerySignal",
    "EvalFailureSignal",
    "InClassQuestionSignal",
    # Clustering
    "SignalCluster",
    # Teaching investment
    "TeachingInvestment",
    # Evidence bundles
    "IssueEvidenceBundle",
    "WorkedWellEvidenceBundle",
    "GapEvidenceBundle",
    "OutOfScopeCluster",
    # Layer 2 output
    "LessonReliability",
    "LessonShape",
    "Layer2Output",
    "DashboardOutput",
]