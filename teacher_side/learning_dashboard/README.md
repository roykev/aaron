lessons w# Learning Dashboard

A system that analyzes student data (queries, evaluations, in-class questions) and generates actionable teaching insights.

## Project Structure

```
learning_dashboard/
├── common/                    # Shared utilities
│   ├── config.py             # Configuration dataclasses
│   ├── models.py             # Data models (signals, clusters, evidence bundles)
│   └── __init__.py
│
├── class_level/              # Per-lecture analysis
│   ├── layer0_data.py        # Data loading & cleaning
│   ├── layer1_clustering.py  # Semantic clustering
│   ├── layer15_mapping.py    # Section mapping & teaching investment
│   ├── layer2_ranking.py     # Ranking & evidence packaging
│   ├── layer3_narrative.py   # LLM narrative generation
│   ├── html_renderer.py      # HTML dashboard renderer
│   ├── test_*.py             # Test scripts
│   └── __init__.py
│
├── course_level/             # Course-wide analysis (to be implemented)
│   ├── layer0_normalize.py   # Engagement normalization & segmentation
│   ├── layer1_aggregate.py   # Cross-lesson aggregation
│   ├── layer2_package.py     # Course-level evidence packaging
│   ├── layer3_narrative.py   # Course report LLM generation
│   └── __init__.py
│
├── __init__.py
└── README.md
```

## Two Analysis Modes

### 1. Class-Level Analysis (single lecture)

Generates a **4-panel dashboard** for one lecture:
- **Quick Snapshot** - lesson performance overview
- **Issues & What To Do** - struggling topics + actionable suggestions (table format)
- **What Worked Well** - successful concepts
- **Teaching vs Learning Gap** - mismatches between investment and outcome

**When**: ~1 week after each class
**Output**: `dashboard.html` + JSON artifacts

### 2. Course-Level Analysis (all lectures)

Generates a **5-panel strategic dashboard** aggregating all lectures:
- **Course Snapshot** - engagement, segments (EXCEL/MIDDLE/STRUGGLES), overall performance
- **What Students Struggle With** - recurring concepts + problematic lessons (unified table)
- **What Consistently Worked** - teaching patterns that work across ≥2 lessons
- **Teaching vs Learning Gap** - systemic gaps (≥2 lessons, consistent direction)
- **Prerequisite & Knowledge Gaps** - foundational gaps students lack

**When**: 2-3 times per semester (weeks 5, 10, 13)
**Output**: `course_report.html` + JSON artifacts

## Quick Start

### Class-Level Report

```python
from teacher_side.learning_dashboard.common import LearningDashboardConfig
from teacher_side.learning_dashboard.class_level import test_complete_pipeline

# Configure paths
config = LearningDashboardConfig.from_files(
    queries_csv="/path/to/queries.csv",
    quiz_csv="/path/to/quiz.csv",
    eval_csv="/path/to/eval.csv",
    correct_csv="/path/to/correct.csv",
    concepts_json="/path/to/concepts.txt",
    output_txt="/path/to/output.txt",
    lecture_id="specific-lecture-id"
)

# Run pipeline
test_complete_pipeline.main()
```

### Course-Level Report

```python
from teacher_side.learning_dashboard.course_level import CoursePipeline

# Run course analysis
pipeline = CoursePipeline(config)
course_report = pipeline.run()  # Aggregates all lectures
```

## Input Files

Both modes require:
- `queries.csv` - Student search queries
- `quiz.csv` - Quiz scores
- `eval.csv` - Evaluation scores
- `correct.csv` - Question bank with answers
- `concepts.txt` - Concept timecodes
- `output.txt` - Sections, examples, interactions

Course-level additionally requires:
- `lecture_sequence.json` - Ordered list of lectures with dates
- `student_roster.json` - Enrolled students list

## Key Concepts

### Signals
- **Query** - Student search in bot/search
- **Eval Failure** - Wrong answer on evaluation
- **In-Class Question** - Question asked during lecture
- **Revisit** (course-level only) - Query >14 days after lecture

### Significance Gates

**Class-level:**
- **Issues**: corroboration_score ≥ 3 AND evidence_strength ≥ moderate
- **Worked Well**: eval_failure_rate < 25% AND (example OR quiet class OR time invested)
- **Gap**: |gap_score| > 0.15 AND evidence_strength ≥ moderate

**Course-level:**
- **Recurring Concept**: appears in ≥2 lectures
- **Problematic Lesson**: ≥2 independent signals (low eval, high issues, high revisit)
- **Consistent Success**: success in ≥2 lectures with both teacher + student signals
- **Systemic Gap**: appears in ≥2 lectures with consistent direction

### Formulas

**Teaching Investment Score** (class-level):
```
0.40×time + 0.25×assessment + 0.20×example + 0.15×no_friction
```

**Gap Score** (class & course):
```
teaching_investment_score - learning_struggle_score
```
- Positive gap = over-invested (taught a lot, students still confused)
- Negative gap = under-taught (little teaching, high curiosity)

**Recurrence Score** (course-level):
```
(appearance_count × 2.0) + (total_failures × 0.5) + (revisit_students × 1.5)
+ (struggles_dominant bonus) / engaged_n
```

## Configuration

Edit `common/config.py` or override at runtime:

```python
config.clustering.similarity_threshold = 0.84
config.significance.min_corroboration_score = 3.0
config.ranking.max_issues = 3
config.llm.model_name = "nvidia/nemotron-3-super-120b-a12b:free"  # OpenRouter
config.llm.output_language = "Hebrew"
```

## Testing

**Class-level:**
```bash
cd class_level/
python test_complete_pipeline.py
```

**Course-level:**
```bash
cd course_level/
python test_course_pipeline.py  # To be implemented
```

## Output Structure

```
output/learning_dashboard/
├── class_level/
│   ├── layer0/cleaned_signals.json
│   ├── layer1/clusters_summary.json
│   ├── layer15/teaching_investment.json
│   ├── layer2/layer2_output.json
│   └── layer3/
│       ├── dashboard_output.md
│       ├── dashboard.html
│       └── complete_dashboard.json
│
└── course_level/
    ├── layer0/segments_and_revisits.json
    ├── layer1/recurring_patterns.json
    ├── layer2/course_evidence.json
    └── layer3/
        ├── course_report.md
        ├── course_report.html
        └── complete_course_report.json
```

## Implementation Status

✅ **Class-level**: Fully implemented (Layers 0-3)
✅ **Course-level**: Fully implemented (Layers 0-3 + 5-Box Data Dashboard)
  - ✅ Layer 0: Engagement normalization & student segmentation
  - ✅ Layer 1: Cross-lesson aggregation with semantic clustering
  - ✅ Layer 2: Ranking & evidence packaging
  - ✅ Layer 3: LLM narrative generation (optional)
  - ✅ Alternative: 5-Box Data-Driven Dashboard (no LLM required)

## Report Options

### Course-Level Dashboards

You can generate course-level dashboards in two ways:

**Option 1: LLM-Generated Narrative** (`layer3_narrative.py`)
- Uses OpenRouter API to generate natural language insights
- Provides rich narrative explanations
- Requires API key and takes 30-60 seconds
- Output: `course_dashboard.html` with 5 panels

**Option 2: Data-Driven 5-Box Report** (`generate_5box_report.py`)
- Pure data presentation without LLM calls
- Instant generation
- Includes innovative ROI analysis (teaching time vs. student success)
- Output: `course_dashboard_5box.html` with 5 boxes
- **NEW**: Now includes ROI table showing topics with low scores + high investment

## Next Steps

1. Test both dashboard options with real data
2. Refine ROI calculation thresholds based on instructor feedback
3. Add segment-specific insights (EXCEL vs STRUGGLES performance)
4. Implement export to PDF functionality
5. Add comparative analysis across multiple course runs