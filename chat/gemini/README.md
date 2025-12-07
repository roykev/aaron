# Gemini RAG System

A modular RAG (Retrieval-Augmented Generation) system for educational lecture transcripts using Google's Gemini File Search API with semantic chunk references.

**Key Features:**
- 🗂️ Registry-based store management - no hardcoded store IDs
- 📍 Semantic chunk references with timestamps
- 🔍 Answer-to-chunk similarity matching using multilingual embeddings
- 📊 Automatic query logging with metadata

## 📁 Project Structure

```
chat/gemini/
├── Main Scripts (entry points)
│   ├── main_batch.py              # Upload lectures & embed chunks
│   ├── main_interactive.py        # Interactive Q&A with chunk references
│   └── main_manage_stores.py      # Manage Gemini stores & registry
│
├── Core Modules
│   ├── config.py                  # Configuration management
│   ├── store_registry.py          # (institute, course) → store_id mapping
│   ├── store_manager.py           # Gemini File Search Store operations
│   ├── query.py                   # RAG query engine
│   ├── chunk_matcher.py           # Answer-to-chunk similarity matching
│   └── query_logger.py            # Query logging with metadata
│
├── Processing Utilities
│   ├── parsers.py                 # VTT/TXT/CSV transcript parsers
│   ├── chunker.py                 # Time-based transcript chunking
│   └── embed_existing_chunks.py   # Embed chunks without uploading
│
├── Data Files
│   ├── store_registry.json        # Registry database (auto-created)
│   └── query_log.json             # Query logs (auto-created)
│
└── README.md                      # This file
```

## 🎯 How It Works

### 1. Upload & Embedding Pipeline (`main_batch.py`)

```
Transcript → Chunks → Embeddings → Gemini Store
                ↓
         embeddings.pkl (saved locally)
                ↓
         Used for chunk references
```

**Steps:**
1. Parse transcript (VTT/TXT/CSV)
2. Split into 30-second chunks
3. **Embed chunks** using SentenceTransformer (multilingual)
4. Save embeddings to `{chunks_dir}/embeddings.pkl`
5. Upload chunks to Gemini File Search Store
6. Register store in registry

### 2. Query & Reference Pipeline (`main_interactive.py`)

```
Question → Gemini → Answer
              ↓
    Load embeddings.pkl
              ↓
    Embed answer
              ↓
    Similarity search
              ↓
    Top-K chunks with timestamps
```

**Steps:**
1. User asks question
2. Gemini generates rich answer from File Search Store
3. **Load pre-computed chunk embeddings** (fast!)
4. Embed the answer
5. Find top-K similar chunks using cosine similarity
6. Display answer + chunk references with timestamps

### 3. Registry Pattern

The system uses a **registry pattern** to eliminate hardcoded store IDs:

```
config.yaml:
  institute: "ono"
  course_name: "psychology"
         ↓
Registry maps: ono:psychology → fileSearchStores/abc123...
         ↓
Automatic store lookup - no manual IDs needed!
```

**Example registry:**
```json
{
  "ono:psychology": "fileSearchStores/5dqu31ux5614-r0yk8fxg18mf",
  "Hebrew University:machine_learning": "fileSearchStores/xyz789..."
}
```

## 🚀 Quick Start

### 1. Setup

**Install dependencies:**
```bash
pip install google-genai sentence-transformers scikit-learn
```

**Configure in `config.yaml`:**
```yaml
# Global settings
videos_dir: "/path/to/lecture/videos/"
language: "Hebrew"  # or "English"
course_name: "psychology"
class_level: "undergraduate 1st year"

# Gemini RAG configuration
gemini_rag:
  institute: "ono"
  model: "gemini-2.0-flash-exp"
  chunk_interval_seconds: 30
  max_upload_wait_seconds: 300

  # Context files (relative to videos_dir)
  concepts_file: "concepts.txt"
  summary_file: "short_summary.txt"

  # Query logging
  query_log_path: "chat/gemini/query_log.json"
```

**Set API key:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 2. Upload a Lecture

**Fully automatic mode (recommended):**
```bash
cd chat/gemini
python main_batch.py
```

This will:
- ✅ Auto-detect transcript (*.vtt) from `videos_dir`
- ✅ Auto-generate lecture ID (e.g., `psychology_20251206_143022`)
- ✅ Create 30-second chunks
- ✅ **Embed all chunks** and save to `embeddings.pkl`
- ✅ Upload to Gemini File Search Store
- ✅ Register in store registry

**Manual mode with options:**
```bash
# Custom lecture ID
python main_batch.py --lecture-id PsychLec_Week5

# Different chunk size
python main_batch.py --chunk-interval 60

# Specify files
python main_batch.py \
  --transcript /path/to/lecture.vtt \
  --concepts /path/to/concepts.json \
  --summary /path/to/summary.txt
```

**All options:**
- `--lecture-id`: Unique ID (auto-generated if omitted)
- `--transcript`: Transcript path (auto-detected)
- `--concepts`: Concepts file (auto-detected)
- `--summary`: Summary file (auto-detected)
- `--format`: `auto`, `vtt`, `txt`, `csv` (default: auto)
- `--chunk-interval`: Seconds (default: 30)

### 3. Embed Existing Chunks (Optional)

If you have chunks but need to re-embed them:

```bash
python embed_existing_chunks.py
```

This will find the most recent `*_chunks` directory and embed all chunks without re-uploading.

### 4. Interactive Q&A with Chunk References

```bash
python main_interactive.py
```

**Example output:**
```
❓ Your question: working memory

-> Running query with store reference: fileSearchStores/5dqu31ux5614-r0yk8fxg18mf
Store has 174 active documents

-> No grounding metadata - using answer similarity matching
-> Loading embedding model: paraphrase-multilingual-MiniLM-L12-v2
-> Loading pre-computed embeddings from: psychology_20251206_234701_chunks/embeddings.pkl
-> Loaded 174 pre-embedded chunks
   Found 3 matching chunks based on answer similarity

----------------------------------------------------------------------
🤖 Model Response:
----------------------------------------------------------------------
Working memory is the "workbench of the mind" where active thinking
takes place. It comprises three components: the phonological loop
(for verbal information), the visuospatial sketchpad (for visual
and spatial information), and the central executive (which oversees
and allocates resources).
----------------------------------------------------------------------
⏱️  Response time: 1.54 seconds

📚 Source Chunks (3 total):
======================================================================

[1] psychology_20251206_234701
    ⏰ Time: 00:15:30 - 00:16:00
    📄 File: psychology_20251206_234701_00-15-30_to_00-16-00.txt
    🎯 Similarity: 0.847
    📝 Content:
       Working memory is sometimes called the workbench of the mind.
       This is where active thinking happens. We discussed three main
       components: the phonological loop, the visuospatial sketchpad...

[2] psychology_20251206_234701
    ⏰ Time: 00:16:00 - 00:16:30
    📄 File: psychology_20251206_234701_00-16-00_to_00-16-30.txt
    🎯 Similarity: 0.792
    📝 Content:
       The central executive is the control system of working memory.
       It decides which information gets attention and coordinates...

[3] psychology_20251206_234701
    ⏰ Time: 00:03:30 - 00:04:00
    📄 File: psychology_20251206_234701_00-03-30_to_00-04-00.txt
    🎯 Similarity: 0.715
    📝 Content:
       We conducted practical experiments in class to demonstrate
       active working memory processes...
----------------------------------------------------------------------
```

**Options:**
- `--mode`: `interactive` (default) or `search` (single query)
- `--concepts`: Context file path
- `--summary`: Summary file path
- `--model`: Gemini model (default: gemini-2.0-flash-exp)
- `--scope`: `class` (default) or `course`

### 5. Manage Stores & Registry

```bash
python main_manage_stores.py
```

**Interactive menu:**
```
🗄️  Gemini Store Management Tool
======================================================================
Options:
  1. List all stores
  2. List all files (shows active_documents_count per store)
  3. Delete specific store
  4. Delete ALL stores (⚠️  CAUTION)
  5. View registry
  6. Register a store manually
  7. Clear registry
  8. Exit
```

## 📝 Supported Transcript Formats

### WebVTT (.vtt)
```
WEBVTT

1
00:00:00.000 --> 00:00:05.000
Today we'll discuss working memory.
```

### Plain Text (.txt)
```
[00:00:00] Today we'll discuss working memory.
[00:00:05] Working memory is essential.
```

### CSV (.csv)
```csv
timestamp,text
00:00:00,"Today we'll discuss working memory."
00:00:05,"Working memory is essential."
```

## 🔬 Technical Details

### Embedding Model

Uses **SentenceTransformer** with multilingual support:
```python
model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

Supports Hebrew, English, and 50+ languages.

### Chunk Matching Algorithm

```python
# 1. Embed answer (rich, detailed response from Gemini)
answer_embedding = model.encode(answer)

# 2. Load pre-computed chunk embeddings
chunk_embeddings = load_embeddings("embeddings.pkl")

# 3. Calculate cosine similarity
similarities = cosine_similarity(answer_embedding, chunk_embeddings)

# 4. Return top-K chunks with similarity > threshold
top_chunks = get_top_k(similarities, k=3, threshold=0.3)
```

### Why Answer-to-Chunk Matching?

**Problem:** Short questions don't embed well
- ❌ Question: "working memory" (2 words)
- ✅ Answer: "Working memory is the workbench of the mind..." (rich context)

**Solution:** Match the detailed answer to chunks
- Better semantic similarity
- More accurate source attribution

### Store Operations

**Improved error detection:**
```python
# Check operation.done AND operation.error
if op.done:
    if hasattr(op, 'error') and op.error:
        raise Exception(f"Upload failed: {op.error}")
```

**Operation refresh (required for local execution):**
```python
# Must refresh operation status from server
operations[i] = client.operations.get(operations[i])
```

## 📊 Query Logging

All queries logged to `query_log.json` with:
- Timestamp
- Institute, course, class level
- Query & answer
- Model & store
- Response time
- **Chunk references** with timestamps and similarity scores

Example:
```json
{
  "timestamp": "2025-12-07T15:30:45",
  "institute": "ono",
  "course": "psychology",
  "query": "working memory",
  "answer": "Working memory is...",
  "response_time_seconds": 1.54,
  "chunks_used": [
    {
      "lecture_id": "psychology_20251206_234701",
      "start_time": "00:15:30",
      "end_time": "00:16:00",
      "similarity": 0.847,
      "content": "Working memory is..."
    }
  ]
}
```

## 🔧 Advanced Usage

### Custom Embedding Model

Edit `chunk_matcher.py`:
```python
model_name = "sentence-transformers/all-mpnet-base-v2"  # English-only, higher quality
```

### Adjust Similarity Threshold

```python
# In query.py, line 103
score_threshold = 0.5  # Higher = stricter matching
```

### Batch Re-embedding

```bash
# Delete old embeddings
rm psychology_*_chunks/embeddings.pkl

# Re-embed
python embed_existing_chunks.py
```

## 🐛 Troubleshooting

### No chunk references shown
**Cause:** Embeddings not created
**Solution:** Run `main_batch.py` or `embed_existing_chunks.py`

### Slow queries
**Cause:** Embedding chunks on every query
**Solution:** Ensure `embeddings.pkl` exists in chunks directory

### Wrong store ID
**Cause:** Registry out of sync
**Solution:** Use `main_manage_stores.py` → View registry

### Upload timeout
**Cause:** Large number of files
**Solution:** Increase `max_upload_wait_seconds` in config.yaml

## 📦 Dependencies

```
google-genai>=1.0.0
sentence-transformers>=2.0.0
scikit-learn>=1.0.0
numpy>=1.20.0
```

## 📄 License

Part of the Aaron educational content processing system.