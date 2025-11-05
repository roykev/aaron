# Teacher Report Smart Snapshot Generator

## Overview

The Smart Snapshot Generator creates concise, actionable reports from teacher report outputs, highlighting the most important insights and recommendations from your lecture analysis.

## What it does

The SnapshotGenerator analyzes three input files:
- **output.txt** - Basic report (sections, examples, interactions, difficult topics)
- **deep.txt** - Deep pedagogical analysis (communication, engagement, pedagogical approach, content)
- **story.txt** - Storytelling analysis (narrative, characters, curiosity, emotional engagement, coherence)

And generates two smart reports:
- **teaching_snapshot.md** - Minimalist report with top insights (most important findings)
- **teaching_snapshot_expanded.md** - Detailed comprehensive report

## The Smart Report includes

### Minimalist Snapshot (teaching_snapshot.md)
- **Main Message** - Overall assessment
- **What Worked Great** - Top strength from the analysis
- **To Preserve** - Top 3 strengths (expandable for details)
- **To Improve** - Top 3 areas for improvement with recommendations (expandable)
- **Recommended Actions** - Top 4 actionable recommendations for next class
- **Hot Topics** - Key topics covered
- **Leading Questions** - Top student questions
- **Challenging Topics** - Difficult areas identified

### Expanded Snapshot (teaching_snapshot_expanded.md)
- Full analysis by all dimensions
- Complete breakdown of all modules
- All strengths, weaknesses, and recommendations
- Detailed evidence and examples
- Full class structure and timeline

## Usage

### Option 1: Generate from existing output files

If you already have `output.txt`, `deep.txt`, and `story.txt`:

```bash
# From the project root directory
python teacher_side/generate_smart_snapshot.py

# Or specify a custom output directory
python teacher_side/generate_smart_snapshot.py /path/to/output/directory
```

### Option 2: Run the complete pipeline

To generate all reports from scratch:

1. Update `config.yaml` with your settings:
```yaml
videos_dir: "/path/to/your/video/directory"

teacher_reports:
  generate_basic: true      # Generate output.txt
  generate_deep: true       # Generate deep.txt
  generate_story: true      # Generate story.txt
  generate_markdown: true   # Generate all markdown reports including smart snapshot

language: "Hebrew"  # or "English"
course_name: "Your Course Name"
class_level: "undergraduate 1st year"
```

2. Run the pipeline:
```bash
python teacher_side/run_teacher_pipeline.py
```

## Output Files

All files are saved to `{videos_dir}/output/`:

- `output.txt` - Basic analysis (raw)
- `deep.txt` - Deep pedagogical analysis (raw JSON)
- `story.txt` - Storytelling analysis (raw JSON)
- `output.md` - Basic analysis (markdown)
- `deep.md` - Deep analysis (markdown)
- `story.md` - Storytelling analysis (markdown)
- `teaching_snapshot.md` - **Smart snapshot with key insights**
- `teaching_snapshot_expanded.md` - **Comprehensive detailed report**

## How the Smart Report Works

The SnapshotGenerator uses a scoring algorithm to:

1. **Calculate scores** for each dimension based on strengths vs weaknesses
2. **Identify top strengths** - Dimensions with the most positive indicators
3. **Prioritize improvements** - Areas with the most significant weaknesses
4. **Extract actionable recommendations** - Concrete next steps
5. **Surface key topics** - Most important content from the class
6. **Highlight student engagement** - Top questions and interactions

This gives you a **quick, actionable summary** instead of having to read through all the detailed analysis.

## Example Workflow

```bash
# 1. Your transcript is ready in the videos directory
# 2. Generate all reports
python teacher_side/run_teacher_pipeline.py

# 3. Review the smart snapshot for quick insights
open output/teaching_snapshot.md

# 4. Dive into details if needed
open output/teaching_snapshot_expanded.md
```

## Quick Start for Existing Files

If you already have your 3 output files and just want the smart snapshot:

```bash
cd /path/to/aaron
python teacher_side/generate_smart_snapshot.py /path/to/your/output/directory
```

This will create:
- `teaching_snapshot.md` - Quick overview with top insights
- `teaching_snapshot_expanded.md` - Full detailed analysis

## Requirements

- Python 3.7+
- Required packages: `pyyaml`, `pandas`, `matplotlib`
- Input files: `output.txt`, `deep.txt`, `story.txt` in JSON format

## Troubleshooting

**Error: Missing required files**
- Ensure you have all three files: output.txt, deep.txt, story.txt
- Check they are in the correct directory
- Verify they contain valid JSON data

**Error: Could not parse JSON**
- Check that deep.txt and story.txt contain valid JSON
- They can be wrapped in markdown code fences (```json ... ```)
- Ensure the format matches the expected structure

## More Information

For details on the analysis dimensions:
- See `teacher_report_storytelling.py` for storytelling dimensions
- See `teacher_report_deep.py` for pedagogical dimensions
- See `teacher_minimal_snapshot_report.py` for the snapshot generation logic
