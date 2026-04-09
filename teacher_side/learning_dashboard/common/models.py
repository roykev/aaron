
"""
Data models for the Learning Dashboard system.
Represents all core entities with clean, typed structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


# =============================================================================
# Enums
# =============================================================================

class SignalType(str, Enum):
    """Types of student signals that indicate learning issues."""
    EVAL_FAILURE = "eval_failure"
    QUERY = "query"
    INCLASS_QUESTION = "inclass_question"


class EvidenceStrength(str, Enum):
    """Reliability classification for evidence."""
    SUFFICIENT = "sufficient"
    MODERATE = "moderate"
    WEAK = "weak"


class GapDirection(str, Enum):
    """Direction of teaching-learning mismatch."""
    OVER_INVESTED = "over-invested/under-retained"
    UNDER_TAUGHT = "under-taught/high-curiosity"
    ASSESSED_NOT_ABSORBED = "assessed-not-absorbed"
    CALIBRATED = "calibrated"


class ReliabilityFlag(str, Enum):
    """Data reliability indicators."""
    SUFFICIENT = "sufficient"
    SPARSE = "sparse"
    INSUFFICIENT = "insufficient"


class QueryType(str, Enum):
    """Classification of query complexity."""
    SINGLE_WORD = "single_word"
    PHRASE = "phrase"
    FULL_QUESTION = "full_question"
    MISCONCEPTION = "misconception"


# =============================================================================
# Core Data Structures
# =============================================================================

@dataclass
class TimeRange:
    """Represents a time range in a lecture."""
    start: str  # Format: "HH:MM:SS"
    end: str    # Format: "HH:MM:SS"

    def to_seconds(self, time_str: str) -> int:
        """Convert HH:MM:SS to seconds."""
        parts = time_str.split(':')
        if len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s

    @property
    def duration_seconds(self) -> int:
        """Get duration in seconds."""
        return self.to_seconds(self.end) - self.to_seconds(self.start)

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0


@dataclass
class Concept:
    """Represents a teaching concept with timing."""
    concept: str
    times: List[TimeRange]

    @property
    def total_duration_minutes(self) -> float:
        """Total time spent on this concept."""
        return sum(t.duration_minutes for t in self.times)


@dataclass
class Section:
    """Represents a lecture section."""
    chapter_num: int
    start_time: str
    end_time: str
    title: str
    duration: str


@dataclass
class Example:
    """Teaching example used in class."""
    topic: str
    example: str
    source: str


@dataclass
class InClassInteraction:
    """Interaction that occurred during class."""
    time: str
    interaction_type: str
    description: str


# =============================================================================
# Student Signals
# =============================================================================

@dataclass
class StudentSignal:
    """Base class for all student signals."""
    text: str
    signal_type: SignalType = SignalType.QUERY
    student_id: Optional[str] = None
    lecture_id: Optional[str] = None
    lecture_name: Optional[str] = None
    timestamp: Optional[str] = None

    def __hash__(self):
        """Make hashable for deduplication."""
        return hash((self.signal_type, self.text, self.student_id))


@dataclass
class QuerySignal(StudentSignal):
    """Student query/search signal."""
    normalized_query: str = ""
    source_type: str = "lecture"
    signal_type: SignalType = SignalType.QUERY


@dataclass
class EvalFailureSignal(StudentSignal):
    """Failed evaluation question signal."""
    question_number: int = 0
    question_text: str = ""
    signal_type: SignalType = SignalType.EVAL_FAILURE


@dataclass
class InClassQuestionSignal(StudentSignal):
    """In-class question from student."""
    signal_type: SignalType = SignalType.INCLASS_QUESTION
    student_id: Optional[str] = None  # Override to enforce None


# =============================================================================
# Clustering Results
# =============================================================================

@dataclass
class SignalCluster:
    """A cluster of related student signals about a topic."""
    cluster_id: int
    cluster_label: str
    signals: List[StudentSignal] = field(default_factory=list)
    unique_students: int = 0
    signal_types_present: List[SignalType] = field(default_factory=list)
    signal_count: int = 0
    example_texts: List[str] = field(default_factory=list)
    corroboration_score: float = 0.0
    evidence_strength: EvidenceStrength = EvidenceStrength.WEAK

    # Layer 1.5 mapping results
    matched_concept: Optional[str] = None
    matched_section: Optional[str] = None
    mapping_confidence: str = "none"
    mapping_note: str = ""

    def compute_corroboration_score(self) -> float:
        """
        Compute corroboration score based on breadth and diversity.
        Formula: unique_students + (signal_type_count * 1.5) + inclass_bonus
        """
        score = self.unique_students
        score += len(self.signal_types_present) * 1.5

        if SignalType.INCLASS_QUESTION in self.signal_types_present:
            score += 1.0

        return score

    def compute_evidence_strength(self) -> EvidenceStrength:
        """Classify evidence strength based on student count and signal diversity."""
        if self.unique_students >= 5:
            return EvidenceStrength.SUFFICIENT

        if self.unique_students >= 3 and len(self.signal_types_present) >= 2:
            return EvidenceStrength.SUFFICIENT

        if self.unique_students >= 2:
            return EvidenceStrength.MODERATE

        if self.unique_students == 1 and len(self.signal_types_present) >= 2:
            return EvidenceStrength.MODERATE

        return EvidenceStrength.WEAK


# =============================================================================
# Teaching Investment
# =============================================================================

@dataclass
class TeachingInvestment:
    """Measures how much teaching effort was invested in a concept."""
    concept: str
    time_minutes: float = 0.0
    time_pct: float = 0.0
    example_used: bool = False
    inclass_questions_n: int = 0
    assessment_weight: float = 0.0
    teaching_investment_score: float = 0.0

    def compute_score(self, total_lesson_minutes: float) -> float:
        """
        Compute teaching investment score.
        Formula: 0.40*time + 0.25*assessment + 0.20*example + 0.15*no_friction
        """
        time_score = self.time_pct
        assessment_score = self.assessment_weight
        example_score = 1.0 if self.example_used else 0.0
        no_friction_score = 1.0 if self.inclass_questions_n == 0 else 0.0

        score = (
            0.40 * time_score +
            0.25 * assessment_score +
            0.20 * example_score +
            0.15 * no_friction_score
        )

        return score


# =============================================================================
# Layer 2 Output - Evidence Bundles
# =============================================================================

@dataclass
class IssueEvidenceBundle:
    """Evidence package for an issue (struggling topic)."""
    cluster_label: str
    matched_concept: Optional[str]
    matched_section: Optional[str]
    corroboration_score: float
    unique_students: int
    signal_types: List[str]
    eval_failure_n: int
    eval_failure_rate: Optional[float]
    query_student_count: int
    query_types: Dict[str, int]
    evidence_strength: str
    top_signal_examples: List[str]
    inclass_question_raised: bool
    difficult_eval_questions: List[str] = field(default_factory=list)  # Actual eval questions students failed
    issue_title: Optional[str] = None  # Better title (section/topic, not question text)


@dataclass
class WorkedWellEvidenceBundle:
    """Evidence package for what worked well."""
    concept: str
    eval_success_rate: float
    eval_success_n: int
    query_signal: str  # "silent" | "curiosity_only"
    example_used: bool
    inclass_questions: int
    teach_minutes: float
    confidence: str  # "clear_win" | "moderate"
    why: str


@dataclass
class GapEvidenceBundle:
    """Evidence package for teaching-learning gap."""
    concept: str
    direction: GapDirection
    teaching_investment: Dict[str, Any]
    learning_outcome: Dict[str, Any]
    raw_gap_score: float
    interpretation_hint: str


@dataclass
class OutOfScopeCluster:
    """Cluster of queries about topics not covered in this lesson."""
    cluster_label: str
    out_of_scope_type: str  # "cross_lesson" | "prerequisite_gap" | "curiosity"
    unique_students: int
    example_queries: List[str]
    note: str


# =============================================================================
# Layer 2 Output - Complete Package
# =============================================================================

@dataclass
class LessonReliability:
    """Reliability metrics for lesson data."""
    eval_participants: int
    query_participants: int
    flag: ReliabilityFlag
    flag_reason: str


@dataclass
class LessonShape:
    """Overview of lesson structure and performance."""
    total_minutes: float
    concept_count: int
    density: str  # "high" | "medium" | "low"
    lesson_quiz_avg: float
    lesson_eval_avg: float
    lesson_gap: float
    lesson_gap_flag: str  # "surface_learning" | "consistent" | "inverted"


@dataclass
class Layer2Output:
    """Complete Layer 2 output package for LLM."""
    lecture_id: str
    lecture_name: str
    reliability: LessonReliability
    lesson_shape: LessonShape
    issues: List[IssueEvidenceBundle] = field(default_factory=list)
    worked_well: List[WorkedWellEvidenceBundle] = field(default_factory=list)
    gaps: List[GapEvidenceBundle] = field(default_factory=list)
    out_of_scope: List[OutOfScopeCluster] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Layer2Output':
        """Reconstruct Layer2Output from dictionary."""
        # Reconstruct reliability
        reliability_data = data.get('reliability', {})
        if isinstance(reliability_data.get('flag'), str):
            reliability_data['flag'] = ReliabilityFlag(reliability_data['flag'])
        reliability = LessonReliability(**reliability_data)

        # Reconstruct lesson_shape
        lesson_shape = LessonShape(**data.get('lesson_shape', {}))

        # Reconstruct issues
        issues = [IssueEvidenceBundle(**i) for i in data.get('issues', [])]

        # Reconstruct worked_well
        worked_well = [WorkedWellEvidenceBundle(**w) for w in data.get('worked_well', [])]

        # Reconstruct gaps
        gaps = []
        for g in data.get('gaps', []):
            if isinstance(g.get('direction'), str):
                g['direction'] = GapDirection(g['direction'])
            gaps.append(GapEvidenceBundle(**g))

        # Reconstruct out_of_scope
        out_of_scope = [OutOfScopeCluster(**o) for o in data.get('out_of_scope', [])]

        return cls(
            lecture_id=data['lecture_id'],
            lecture_name=data['lecture_name'],
            reliability=reliability,
            lesson_shape=lesson_shape,
            issues=issues,
            worked_well=worked_well,
            gaps=gaps,
            out_of_scope=out_of_scope,
        )


# =============================================================================
# Dashboard Output
# =============================================================================

@dataclass
class DashboardOutput:
    """Final dashboard output with all panels."""
    lecture_id: str
    lecture_name: str
    generation_timestamp: str

    # Layer 2 data
    layer2_data: Layer2Output

    # Layer 3 output
    quick_snapshot: str
    issues_panel: str
    worked_well_panel: str
    gap_panel: str

    # Metadata
    reliability_flag: ReliabilityFlag
    html_output_path: Optional[str] = None
    pdf_output_path: Optional[str] = None


# =============================================================================
# Course-Level Models
# =============================================================================

class StudentSegment(str, Enum):
    """Student performance segment classification."""
    EXCEL = "excel"           # avg_eval_score ≥ 75
    MIDDLE = "middle"         # 45 ≤ avg_eval_score < 75
    STRUGGLES = "struggles"   # avg_eval_score < 45
    UNKNOWN = "unknown"       # < 2 eval attempts


@dataclass
class StudentProfile:
    """Course-level profile for a single student."""
    email: str
    student_id: Optional[str] = None
    name: Optional[str] = None

    # Engagement
    attempted_evals: int = 0
    attempted_quizzes: int = 0
    query_count: int = 0
    is_engaged: bool = False  # ≥1 quiz OR eval OR ≥1 query

    # Performance
    avg_eval_score: float = 0.0
    avg_quiz_score: float = 0.0
    eval_consistency: float = 0.0  # std dev of eval scores

    # Segmentation
    segment: StudentSegment = StudentSegment.UNKNOWN

    # Lectures attended
    lectures_with_eval: List[str] = field(default_factory=list)
    lectures_with_quiz: List[str] = field(default_factory=list)
    lectures_with_queries: List[str] = field(default_factory=list)


@dataclass
class RevisitSignal:
    """A query that occurred >14 days after the lecture was taught."""
    student_id: str
    student_email: str
    segment: StudentSegment
    lecture_id: str
    lecture_name: str
    lecture_date: str
    query_text: str
    query_date: str
    days_since_lecture: int

    # Matched to which concept/section (from class-level mapping)
    matched_concept: Optional[str] = None
    matched_section: Optional[str] = None


@dataclass
class LectureMetadata:
    """Metadata for a single lecture in the course."""
    lecture_id: str
    name: str
    date: str
    sequence_number: int  # 1-indexed position in course

    # Class-level Layer 2 JSON path
    class_report_path: Optional[str] = None
    has_class_report: bool = False


@dataclass
class EngagementMetrics:
    """Course-level engagement metrics."""
    enrolled_n: int
    engaged_n: int
    engagement_rate: float

    # Segment breakdown
    excel_n: int
    excel_pct: float
    middle_n: int
    middle_pct: float
    struggles_n: int
    struggles_pct: float
    unknown_n: int  # < 2 evals

    # Flag if segments unreliable
    min_data_for_segments: bool  # engaged_n >= 10


@dataclass
class RevisitMetrics:
    """Aggregated revisit signal metrics for the course."""
    total_revisit_count: int
    unique_students_revisiting: int

    # Per-lecture revisit counts
    revisit_by_lecture: Dict[str, int] = field(default_factory=dict)  # lecture_id → unique student count

    # Per-concept revisit counts (aggregated from matched concepts)
    revisit_by_concept: Dict[str, int] = field(default_factory=dict)  # concept → unique student count


@dataclass
class CourseLayer0Output:
    """Output from course-level Layer 0: normalization & segmentation."""
    run_number: int
    run_date: str
    lectures_covered: int
    total_lectures: int

    # Student profiles
    student_profiles: List[StudentProfile] = field(default_factory=list)

    # Engagement metrics
    engagement: EngagementMetrics = None

    # Revisit signals
    revisit_signals: List[RevisitSignal] = field(default_factory=list)
    revisit_metrics: RevisitMetrics = None

    # Lecture sequence
    lecture_sequence: List[LectureMetadata] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CourseLayer0Output':
        """Reconstruct CourseLayer0Output from dictionary."""
        # Reconstruct nested objects
        student_profiles = []
        for p in data.get('student_profiles', []):
            if isinstance(p, dict):
                # Convert segment string to enum
                segment_str = p.get('segment', 'unknown')
                if isinstance(segment_str, str):
                    p['segment'] = StudentSegment(segment_str)
                student_profiles.append(StudentProfile(**p))
            else:
                student_profiles.append(p)

        engagement_data = data.get('engagement')
        engagement = EngagementMetrics(**engagement_data) if engagement_data else None

        revisit_signals = []
        for r in data.get('revisit_signals', []):
            if isinstance(r, dict):
                # Convert segment string to enum
                segment_str = r.get('segment', 'unknown')
                if isinstance(segment_str, str):
                    r['segment'] = StudentSegment(segment_str)
                revisit_signals.append(RevisitSignal(**r))
            else:
                revisit_signals.append(r)

        revisit_metrics_data = data.get('revisit_metrics')
        revisit_metrics = RevisitMetrics(**revisit_metrics_data) if revisit_metrics_data else None

        lecture_sequence = []
        for l in data.get('lecture_sequence', []):
            if isinstance(l, dict):
                lecture_sequence.append(LectureMetadata(**l))
            else:
                lecture_sequence.append(l)

        return cls(
            run_number=data['run_number'],
            run_date=data['run_date'],
            lectures_covered=data['lectures_covered'],
            total_lectures=data['total_lectures'],
            student_profiles=student_profiles,
            engagement=engagement,
            revisit_signals=revisit_signals,
            revisit_metrics=revisit_metrics,
            lecture_sequence=lecture_sequence,
        )


# =============================================================================
# Course-Level Layer 1 Models
# =============================================================================

@dataclass
class RecurringConcept:
    """A concept that appears as an issue across ≥2 lectures."""
    concept: str
    appearance_count: int  # lectures where it appears
    total_failure_n: int
    total_query_n: int
    revisit_student_n: int
    lectures: List[str] = field(default_factory=list)  # lecture names
    segment_breakdown: Dict[str, int] = field(default_factory=dict)  # EXCEL/MIDDLE/STRUGGLES counts
    is_struggles_dominant: bool = False
    recurrence_score: float = 0.0


@dataclass
class ProblematicLesson:
    """A lesson with holistic underperformance (≥2 independent signals)."""
    lecture_id: str
    lecture_name: str
    lesson_eval_avg: float
    course_eval_avg: float
    issue_count: int
    revisit_student_n: int
    signals: List[str] = field(default_factory=list)  # ["low_eval", "high_issue_count", "high_revisit", "surface_learning"]
    problem_signal_count: int = 0
    lesson_problem_score: float = 0.0


@dataclass
class ConsistentSuccess:
    """A concept that worked well across ≥2 lectures."""
    concept: str
    success_count: int  # lectures where it appears in worked_well
    avg_success_rate: float
    teaching_pattern: Dict[str, bool] = field(default_factory=dict)  # {"example_used": True, "inclass_quiet": True, "assessed": True}
    segment_note: str = ""  # e.g., "consistent across all segments"
    lectures: List[str] = field(default_factory=list)  # lecture names


@dataclass
class SystemicGap:
    """A teaching-learning gap that appears across ≥2 lectures with consistent direction."""
    concept: str
    direction: GapDirection
    gap_appearances: int
    segment_gap: Dict[str, float] = field(default_factory=dict)  # {"EXCEL": 0.10, "STRUGGLES": 0.75}
    interpretation: str = ""  # e.g., "gap concentrated in struggles segment"
    lectures: List[str] = field(default_factory=list)  # lecture names


@dataclass
class PrerequisiteGapCluster:
    """Aggregated out-of-scope clusters indicating prerequisite gaps."""
    topic: str
    unique_students: int
    appearing_in_lectures: int
    lecture_names: List[str] = field(default_factory=list)
    out_of_scope_type: str = ""  # "prerequisite_gap" | "curiosity" | "cross_lesson"
    example_queries: List[str] = field(default_factory=list)


@dataclass
class CourseLayer1Output:
    """Output from course-level Layer 1: cross-lesson aggregation."""
    run_number: int
    run_date: str
    lectures_covered: int
    total_lectures: int
    engaged_n: int
    course_eval_avg: float
    course_quiz_avg: float

    # Aggregated patterns
    recurring_concepts: List[RecurringConcept] = field(default_factory=list)
    problematic_lessons: List[ProblematicLesson] = field(default_factory=list)
    good_lessons: List[Dict[str, Any]] = field(default_factory=list)  # Mirror of problematic_lessons but for successes
    consistent_successes: List[ConsistentSuccess] = field(default_factory=list)
    systemic_gaps: List[SystemicGap] = field(default_factory=list)
    prerequisite_gaps: List[PrerequisiteGapCluster] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict
        return asdict(self)