# Gemini RAG Setup Guide

## Installation

### 1. Install Required Package

```bash
pip install google-genai
```

That's it! All other dependencies are already available (PyYAML, standard library modules).

## Configuration

### 2. Set API Key

```bash
export GEMINI_API_KEY='your-api-key-here'
```

Or add to your `~/.bashrc` or `~/.zshrc` for persistence:
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Update Project Config (Optional)

Add Gemini-specific configuration to your project's `config.yaml`:

```yaml
# Existing config...
language: English
course_name: business
class_level: graduate 1st year

# Add Gemini RAG configuration
gemini_rag:
  store_name: "business_RAG_Store"
  chunk_interval_seconds: 30
  model: "gemini-2.0-flash-exp"
  max_files_per_query: 10
  query_log_path: "chat/gemini/query_log.json"
  institute: "Hebrew University"
```

## Usage

### Batch Upload (Process and Upload Lectures)

```bash
cd chat/gemini

# Upload a lecture with VTT transcript
python batch.py \
  --lecture-id PsychLec4 \
  --transcript /path/to/transcript.vtt \
  --concepts /path/to/concepts.json \
  --summary /path/to/summary.txt

# Or with plain text transcript
python batch.py \
  --lecture-id PsychLec5 \
  --transcript /path/to/lecture5.txt \
  --format txt \
  --chunk-interval 60
```

### Interactive Query Session

```bash
cd chat/gemini

# Basic usage (uses config.yaml settings)
python interactive.py

# With custom options
python interactive.py \
  --concepts /path/to/concepts.json \
  --summary /path/to/summary.txt \
  --scope course \
  --max-files 20
```

### Store Registry (Track Multiple Courses)

```python
from store_registry import StoreRegistry

# Initialize registry
registry = StoreRegistry("store_registry.json")

# Register your existing store
registry.register_store(
    institute="Hebrew University",
    course="Psychology - Memory Unit",
    store_name="fileSearchStores/7askqtkrfkr4-yntw8sntgxmn"
)

# Later, retrieve the store name
store_name = registry.get_store("Hebrew University", "Psychology - Memory Unit")

# List all registered stores
registry.print_registry()
```

### Integrated RAG System

```python
from integrated_rag import IntegratedRAG

# Initialize
rag = IntegratedRAG(api_key="YOUR_KEY")

# Register existing store
rag.registry.register_store(
    institute="Hebrew University",
    course="Psychology - Memory Unit",
    store_name="fileSearchStores/7askqtkrfkr4-yntw8sntgxmn"
)

# Query
response = rag.query_course(
    institute="Hebrew University",
    course="Psychology - Memory Unit",
    query="What is working memory?"
)
print(response)

# Upload new lecture
rag.upload_lecture_content(
    institute="Hebrew University",
    course="Psychology - Memory Unit",
    vtt_path="/path/to/lecture5.vtt",
    lecture_id="PsychLec5"
)
```

## Module Structure

```
chat/gemini/
├── __init__.py              # Package initialization
├── config.py                # Configuration management
├── parsers.py               # VTT/TXT/CSV transcript parsers
├── chunker.py               # Transcript chunking logic
├── store_manager.py         # Gemini store operations
├── store_registry.py        # (institute, course) → store mapping
├── query.py                 # RAG query engine
├── query_logger.py          # Query logging (JSONL)
├── batch.py                 # Batch upload script
├── interactive.py           # Interactive Q&A script
├── integrated_rag.py        # Integrated RAG with registry
└── example_registry_usage.py # Registry examples
```

## Import Fix Applied

All scripts now include this at the top to ensure imports work when running as scripts:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

This allows you to run scripts directly from the IDE or command line without package installation issues.

## Troubleshooting

### Import Error: `cannot import name 'genai' from 'google'`

**Solution:** Install the Google Gemini SDK:
```bash
pip install google-genai
```

### Configuration Error: `GEMINI_API_KEY not set`

**Solution:** Set the environment variable:
```bash
export GEMINI_API_KEY='your-api-key'
```

### Module Not Found: `config`, `parsers`, etc.

**Solution:** Run scripts from the `chat/gemini/` directory, or ensure you're using the updated files with the `sys.path.insert()` fix.

## Next Steps

1. ✅ Install `google-genai`
2. ✅ Set `GEMINI_API_KEY`
3. ✅ Your existing store: `fileSearchStores/7askqtkrfkr4-yntw8sntgxmn` is ready to use
4. Run `python interactive.py` to start querying!