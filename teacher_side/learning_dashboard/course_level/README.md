# Course-Level Analysis Pipeline

This directory contains the course-level analysis pipeline that aggregates class-level signals into course-wide patterns.

## Architecture

The course-level pipeline has four layers:

### Layer 0: Normalization & Segmentation
**File**: `layer0_normalize.py`
**Purpose**: Normalize engagement data and segment students
**Inputs**:
- `student_roster.json` - List of enrolled students
- `lecture_sequence.json` - Ordered list of lectures in the course
- `quiz.csv`, `eval.csv`, `queries.csv` - Student performance data
- Class-level Layer 2 reports (optional, for counting lectures covered)

**Outputs**:
- Student profiles with engagement metrics
- Student segmentation (EXCEL/MIDDLE/STRUGGLES/UNKNOWN)
- Revisit signals (queries >14 days after lecture)
- Engagement statistics

**Test**: `test_course_layer0.py`

### Layer 1: Cross-Lesson Aggregation
**File**: `layer1_aggregate.py`
**Purpose**: Aggregate class-level signals into course-level patterns
**Inputs**:
- Course Layer 0 output (student profiles, segments, revisits)
- Class-level Layer 2 reports (from all lectures)

**Outputs**:
- **Recurring Concepts**: Issues appearing in ≥2 lectures
- **Problematic Lessons**: Lessons with ≥2 underperformance signals
- **Consistent Successes**: Concepts that worked well in ≥2 lectures
- **Systemic Gaps**: Persistent teaching-learning gaps across ≥2 lectures
- **Prerequisite Gaps**: Out-of-scope clusters indicating missing foundations

**Test**: `test_course_layer1.py`

### Layer 2: Rank & Package
**File**: `layer2_ranking.py`
**Purpose**: Rank aggregated patterns by significance and package for LLM consumption
**Inputs**:
- Course Layer 1 output (all aggregated patterns)

**Outputs**:
- **Top N Recurring Concepts**: Top 5 by recurrence score
- **Top N Problematic Lessons**: Top 3 by problem score
- **Top N Good Lessons**: Top 3 by success score
- **Top N Consistent Successes**: Top 5 by average success rate
- **All Systemic Gaps**: All gaps (usually 1-2)
- **Top N Prerequisite Gaps**: Top 5 by student count

**Test**: `test_course_layer2.py`

### Layer 3: LLM Narrative Generation
**File**: `layer3_narrative.py`
**Purpose**: Generate human-readable 5-panel course dashboard using LLM
**Inputs**:
- Course Layer 2 output (ranked patterns)

**Outputs**:
- **JSON Outputs**:
  - `complete_course_dashboard.json` - Full data (Layer 2 + Layer 3)
  - `course_dashboard_panels.json` - Parsed 5 panels
- **Markdown Output**: `course_dashboard.md` - LLM-generated narrative
- **HTML Output**: `course_dashboard.html` - Visual dashboard with Hebrew RTL support

**5-Panel Structure**:
1. **Course Snapshot**: Overall engagement & performance metrics
2. **What Students Struggle With**: Recurring concepts + problematic lessons
3. **What Consistently Worked**: Successful topics + good lessons
4. **Teaching vs Learning Gap (Systemic)**: Persistent teaching-learning mismatches
5. **Prerequisite & Knowledge Gaps**: Missing foundational knowledge

**Test**: `test_course_layer3.py`

## Workflow

### 1. Generate Class-Level Reports
First, run the class-level pipeline for each lecture to generate Layer 2 reports:

```bash
# For each lecture in your course:
python class_level/test_class_layer2.py --lecture_id <lecture_id>
```

This will create:
```
output/learning_dashboard/class_level/<lecture_id>/layer2/layer2_output.json
```

### 2. Run Course Layer 0
Once you have class reports for multiple lectures, run Layer 0:

```bash
python course_level/test_course_layer0.py
```

This analyzes the entire course and generates:
```
output/learning_dashboard/course_level/layer0/course_layer0_output.json
```

### 3. Run Course Layer 1
Run Layer 1 to aggregate patterns:

```bash
python course_level/test_course_layer1.py
```

This reads the Layer 0 output and all class Layer 2 reports, then generates:
```
output/learning_dashboard/course_level/layer1/course_layer1_output.json
```

### 4. Run Course Layer 2
Run Layer 2 to rank and package patterns:

```bash
python course_level/test_course_layer2.py
```

This reads the Layer 1 output and generates:
```
output/learning_dashboard/course_level/layer2/course_layer2_output.json
```

### 5. Run Course Layer 3 (Two Options)

You can generate the final course dashboard in two ways:

**Option A: LLM-Generated Narrative Dashboard** (requires API key)
```bash
python course_level/test_course_layer3.py
```

This calls the OpenRouter API (takes 30-60 seconds) and generates:
```
output/learning_dashboard/course_level/layer3/
├── course_dashboard.md                  # Markdown narrative
├── course_dashboard_panels.json         # Parsed 5 panels
├── complete_course_dashboard.json       # Full data
└── course_dashboard.html                # Visual dashboard (open in browser)
```

**Option B: Data-Driven 5-Box Dashboard** (no API required, instant)
```bash
python course_level/generate_5box_report.py --output-dir /home/roy/Downloads/attachments/output
```

This generates a pure data-driven report (instant, no LLM) with:
```
output/learning_dashboard/course_level/layer3/
└── course_dashboard_5box.html           # 5-box data dashboard
```

**Key Differences:**
- **LLM Dashboard**: Natural language narrative, requires API key, slower (30-60s)
- **5-Box Dashboard**: Tables and metrics, no API needed, instant, includes ROI analysis

## Expected File Structure

```
/home/roy/Downloads/attachments/
├── student_roster.json
├── lecture_sequence.json
├── quiz.csv
├── eval.csv
├── queries.csv
├── correct.csv
└── output/
    └── learning_dashboard/
        ├── class_level/
        │   ├── <lecture_id_1>/
        │   │   └── layer2/
        │   │       └── layer2_output.json
        │   ├── <lecture_id_2>/
        │   │   └── layer2/
        │   │       └── layer2_output.json
        │   └── ...
        └── course_level/
            ├── layer0/
            │   └── course_layer0_output.json
            ├── layer1/
            │   └── course_layer1_output.json
            ├── layer2/
            │   └── course_layer2_output.json
            └── layer3/
                ├── course_dashboard.md
                ├── course_dashboard_panels.json
                ├── complete_course_dashboard.json
                └── course_dashboard.html
```

## Key Features

### Layer 0 Features:
- Student segmentation based on evaluation performance
- Engagement tracking (quiz attempts, eval attempts, queries)
- Revisit detection (queries >14 days after lecture)
- Support for progressive runs (mid-semester, end-semester)

### Layer 1 Features:
- **Semantic concept matching** using sentence transformers
  - Groups similar concepts across lectures (e.g., "working memory" and "זיכרון עבודה")
  - Similarity threshold: 0.85
- **Significance gates** enforce quality standards:
  - Recurring concepts: ≥2 lectures
  - Problematic lessons: ≥2 independent signals
  - Consistent successes: ≥2 lectures
  - Systemic gaps: ≥2 lectures with consistent direction
  - Prerequisite gaps: ≥3 students AND ≥2 lectures
- **No LLM calls** - pure Python + sentence transformers
- **Multilingual support** - Works with Hebrew and English content

### Layer 2 Features:
- **Simple ranking** - Leverages Layer 1's pre-sorted results
- **Top N selection** per category:
  - Top 5 recurring concepts (by recurrence score)
  - Top 3 problematic lessons (by problem score)
  - Top 3 good lessons (by success score)
  - Top 5 consistent successes (by avg success rate)
  - All systemic gaps (usually 1-2)
  - Top 5 prerequisite gaps (by student count)
- **LLM-ready packaging** - JSON format optimized for Layer 3 consumption

### Layer 3 Features:

**Option A: LLM Narrative Dashboard** (`test_course_layer3.py`)
- **OpenRouter API integration** - Uses `nvidia/nemotron-3-super-120b-a12b:free` model
- **5-panel narrative structure** - Strategic course-level insights
- **Multi-format output**:
  - JSON: Structured data for programmatic access
  - Markdown: Human-readable narrative
  - HTML: Visual dashboard with RTL Hebrew support
- **Robust error handling** - Retry logic with exponential backoff
- **Thinking tag removal** - Cleans up `<think>...</think>` tags from LLM output
- **Professional HTML styling** - Gradient header, responsive stats, panel-based layout

**Option B: Data-Driven 5-Box Dashboard** (`generate_5box_report.py`)
- **No LLM required** - Pure data presentation, instant generation
- **5-box structure** - Answers 5 key strategic questions for instructors
- **ROI Analysis (Innovation)** - Calculates Return on Investment for each teaching concept:
  - Maps eval question results to teaching concepts via layer15 mappings
  - Formula: ROI = Success Rate ÷ Teaching Time (minutes)
  - Identifies topics with high time investment but low student success
  - Helps instructors prioritize where to improve teaching efficiency
- **Student Segmentation Display** - Shows EXCEL/MIDDLE/STRUGGLES breakdown
- **Complete Data Tables** - All metrics visible without narrative summarization
- **Hebrew RTL Support** - Professional styling with gradient headers

## Scoring Formulas

### Recurrence Score (for concepts)
```
score = (appearances * 2.0 + failures * 0.5 + revisits * 1.5 + struggles_bonus) / engaged_n
```

### Problem Score (for lessons)
```
score = (course_eval_avg - lesson_eval_avg) * 0.4 + issue_count * 0.3 + revisit_count * 0.3
```

## Troubleshooting

**Q: Layer 1 shows "0 lectures covered"**
A: This means no class-level Layer 2 reports exist yet. Run the class-level pipeline first.

**Q: Layer 1 shows "0 class-level reports"**
A: Class reports must be in the expected directory structure:
   `output/learning_dashboard/class_level/<lecture_id>/layer2/layer2_output.json`

**Q: Concept matching isn't working**
A: Ensure the sentence-transformers model is installed:
   `pip install sentence-transformers`

**Q: Layer 3 API call fails**
A: Check that your `OPEN_ROUTER_API_KEY` environment variable is set correctly.
   The pipeline uses OpenRouter API to call the LLM model.

**Q: Layer 3 HTML looks broken**
A: Open `course_dashboard.html` in a modern web browser (Chrome, Firefox, Safari).
   The HTML uses RTL (right-to-left) layout for Hebrew content and requires CSS support.

## API Requirements

Layer 3 requires OpenRouter API access:
- Set environment variable: `OPEN_ROUTER_API_KEY`
- Model used: `nvidia/nemotron-3-super-120b-a12b:free`
- Configured in `config.yaml` under `llm.model_name`

## Summary

The complete course-level pipeline flow:
1. **Layer 0**: Normalize engagement data → student segments
2. **Layer 1**: Aggregate class signals → course patterns
3. **Layer 2**: Rank patterns → top N selections
4. **Layer 3**: Generate LLM narrative → 5-panel dashboard (JSON/MD/HTML)

Final output: **course_dashboard.html** - A visual, Hebrew-supported dashboard ready for instructor review.