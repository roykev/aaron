# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based educational content processing system that analyzes lecture videos/transcripts and generates teaching materials. The system provides:

1. **Video/Audio Processing**: Transcription, scene analysis, and silence detection
2. **Content Analysis**: Educational content summarization, concept extraction, quiz generation
3. **Teacher Reports**: Automated generation of teaching reports with interactions, difficult topics, and assessments
4. **Video Clip Creation**: Intelligent selection and creation of educational video clips/trailers
5. **Multi-Modal AI Integration**: Uses OpenAI, Anthropic Claude, and OpenRouter APIs

## Architecture

### Core Components

- **Main Processing Scripts**: Located in root directory
  - `aaron_*.py` - Various specialized processing pipelines
  - `clips_creator.py` - Video clip extraction and trailer creation
  - `parse_AI_output.py` - AI response parsing utilities

- **Teacher Functionality**: `teacher_side/`
  - `generate_report.py` - HTML/PDF report generation from analysis artifacts
  - `teacher_prompts.py` - LLM prompts for educational analysis

- **Utilities**: `utils/`
  - `utils.py` - File handling, transcription chunking, audio processing
  - `kimi_utils.py` - OpenRouter API integration
  - Audio processing and silence detection utilities

- **Configuration**: `config.yaml` - Central configuration for models, logging, directories

### Key Dependencies

- **AI/ML**: `anthropic`, `openai`, `tiktoken`
- **Audio/Video**: Audio processing libraries, silence detection
- **Data Processing**: `pandas`, `pdfkit`, `matplotlib`
- **Web**: `streamlit` (for UI components)

## Development Workflow

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (no requirements.txt found - dependencies managed manually)
```

### Common Commands

Since this is a research/educational processing project, there are no standard build/test commands. Instead, run individual processing scripts:

```bash
# Generate teacher reports
python teacher_side/generate_report.py

# Process educational content with Anthropic
python aaron_RAG_Anthropic.py

# Create video clips
python clips_creator.py
```

### Configuration

- Primary config file: `config.yaml`
- Contains video directories, logging settings, LLM model selection
- API keys loaded from environment variables via `source_key()` function in `utils.py`

### Key Environment Variables Required

- `ANTHROPIC_API_KEY` - For Claude API access
- `OPENAI_API_KEY` - For OpenAI API access
- `OPEN_ROUTER_API_KEY` - For OpenRouter API access

## File Structure Patterns

- **Input**: Video/audio files in configured directories, transcript files (.txt, .vtt, .json)
- **Artifacts**: Generated analysis files (.csv, .txt, .json, .svg) in working directories
- **Output**: HTML/PDF reports, video clips, educational materials

## Important Implementation Details

- **Chunking Strategy**: Large transcripts are split using tiktoken for API token limits
- **Error Handling**: Retry logic implemented for API rate limits and overload scenarios
- **Multi-language Support**: Hebrew and English content processing
- **Streaming Responses**: Uses streaming API calls for better performance

## Development Notes

- This appears to be an active research/development project with multiple experimental approaches
- File paths are often hardcoded for specific use cases
- Configuration values are mixed between config files and hardcoded constants
- No formal testing framework is in place - testing appears to be done through manual script execution