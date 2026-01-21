# AaronOwl Teacher Report Pipeline - Setup Guide

## Overview

The AaronOwl Teacher Report Pipeline analyzes teaching effectiveness from lecture transcripts using AI-powered analysis. It generates comprehensive reports covering storytelling, pedagogy, engagement, and provides actionable insights.

## Prerequisites

- **Python 3.8+** required
- **OpenRouter API Key** (for LLM access)
- Lecture transcript files (`.txt`, `.vtt`, or `.srt` format)

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the `aaron` directory with your API key:

```bash
# .env
OPEN_ROUTER_API_KEY=your_api_key_here
```

Alternatively, add to your `~/.bashrc`:

```bash
export OPEN_ROUTER_API_KEY="your_api_key_here"
```

### 3. Configure the Pipeline

Edit `config.yaml` to customize the pipeline:

```yaml
# Set the directory containing your lecture video/transcript
videos_dir: "/path/to/your/lecture/directory"

# Configure which reports to generate
teacher_reports:
  generate_basic: true          # Sections, examples, interactions
  generate_deep: true            # Deep pedagogical analysis
  generate_story: true           # Storytelling effectiveness
  generate_smart_insights: true  # AI-powered key insights
  generate_markdown: true        # Formatted markdown reports

# Language configuration
language: "English"  # Options: "Hebrew", "English", etc.
course_name: "Your Course Name"
class_level: "undergraduate 1st year"

# LLM model selection
llm:
  model: "anthropic/claude-sonnet-4.5-20250929"
  # Other options: "moonshotai/kimi-k2:free", "google/gemini-2.0-flash-exp:free"
```

## Usage

### Run the Complete Pipeline

```bash
cd /path/to/aaron
python teacher_side/run_teacher_pipeline.py
```

The pipeline will:
1. ✅ Generate basic report (`output.txt`) - sections, examples, interactions, questions
2. ✅ Generate deep analysis (`deep.txt`) - communication, content, pedagogical approach, engagement
3. ✅ Generate storytelling analysis (`story.txt`) - narrative structure, curiosity, emotional engagement
4. ✅ Generate smart insights (`smart_insights.json` + `smart_insights.md`) - AI-powered key insights
5. ✅ Generate markdown reports (`output.md`, `deep.md`, `story.md`, snapshots)

### Output Files

All outputs are saved to: `{videos_dir}/output/`

**Generated Files:**
- `output.txt` / `output.md` - Basic class analysis
- `deep.txt` / `deep.md` - Deep pedagogical analysis
- `story.txt` / `story.md` - Storytelling effectiveness
- `smart_insights.json` / `smart_insights.md` - Key insights and recommendations
- `teaching_snapshot.md` - Minimalist snapshot report
- `teaching_snapshot_expanded.md` - Detailed snapshot report

## Project Structure

```
aaron/
├── teacher_side/
│   ├── run_teacher_pipeline.py          # Main orchestration script
│   ├── teacher_report.py                # Basic report generator
│   ├── teacher_report_deep.py           # Deep analysis
│   ├── teacher_report_storytelling.py   # Storytelling analysis
│   ├── teacher_report_smart_insights.py # AI-powered insights
│   ├── teacher_minimal_snapshot_report.py # Snapshot generator
│   ├── teacher_utils.py                 # Utility functions
│   └── teacher_prompts.py               # LLM prompts
├── utils/
│   ├── utils.py                         # General utilities
│   └── kimi_utils.py                    # OpenRouter LLM proxy
├── config.yaml                          # Main configuration file
├── requirements.txt                     # Python dependencies
└── .env                                 # API keys (create this)
```

## Analysis Modules

### Basic Report
- **Sections**: Chapter breakdown with timestamps
- **Examples**: Examples used with references
- **Interactions**: Student questions and discussions
- **Open Questions**: Simple and difficult questions posed
- **Difficult Topics**: Challenging concepts identified

### Deep Analysis (Pedagogical)
- **Communication**: Language clarity, vocabulary, speech patterns
- **Content**: Topic handling, conceptual gaps, depth vs breadth
- **Pedagogical**: Scaffolding, examples, assessment, learning theory
- **Engagement**: Interaction quality, energy, attention management

### Storytelling Analysis
- **Curiosity**: Questions, mystery, surprises, stakes
- **Coherence**: Signposting, callbacks, central thread
- **Emotional**: Enthusiasm, empathy, wonder, relevance
- **Narrative**: Hook, rising action, climax, resolution
- **Concrete→Abstract**: Analogies, sensory language, abstraction sequence
- **Characters**: Real people, character development, relatable scenarios

### Smart Insights (AI-Powered)
- **Overall Assessment**: Holistic view of teaching effectiveness
- **Top Strength**: Most outstanding teaching dimension
- **Preserve**: Successful practices to continue
- **Growth Opportunities**: Areas for improvement
- **Priority Actions**: Specific steps for next class
- **Long-term Focus**: Strategic development area

## Customization

### Change Language

Edit `config.yaml`:
```yaml
language: "Hebrew"  # or "English", "Spanish", etc.
```

### Select Different LLM Model

Edit `config.yaml`:
```yaml
llm:
  model: "google/gemini-2.0-flash-exp:free"  # Free tier option
```

### Enable/Disable Specific Reports

Edit `config.yaml`:
```yaml
teacher_reports:
  generate_basic: true
  generate_deep: false      # Skip deep analysis
  generate_story: false     # Skip storytelling
  generate_smart_insights: true
  generate_markdown: true
```

## Troubleshooting

### API Key Issues
```
ValueError: API key is required
```
**Solution**: Ensure `OPEN_ROUTER_API_KEY` is set in `.env` or `~/.bashrc`

### Missing Transcript File
```
FileNotFoundError: No transcript file found
```
**Solution**: Ensure your `videos_dir` contains a `.txt`, `.vtt`, or `.srt` file

### Import Errors
```
ModuleNotFoundError: No module named 'X'
```
**Solution**: Run `pip install -r requirements.txt`

### Smart Insights Requires Prerequisites
```
Cannot generate smart insights - missing files: deep.txt, story.txt
```
**Solution**: Enable `generate_deep: true` and `generate_story: true` first

## Tips

1. **Start Small**: Enable only `generate_basic: true` for your first run to test the setup
2. **Incremental Analysis**: Generate basic → deep → story → smart insights sequentially
3. **API Costs**: Free tier models are available (see config for options)
4. **Transcript Quality**: Better transcripts = better analysis
5. **Language Consistency**: Use the same language for transcripts and reports

## Support

For issues or questions:
- Check `config.yaml` settings
- Review log output for detailed error messages
- Ensure transcript files are properly formatted
- Verify API key is valid and has sufficient quota

---

*Generated for AaronOwl Teacher Excellence Analyzer*

