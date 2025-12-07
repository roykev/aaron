#!/usr/bin/env python3
"""
Batch processing script for uploading and updating lecture content in Gemini RAG

Usage:
    python batch.py --lecture-id PsychLec4 --transcript transcript.vtt --concepts concepts.json --summary summary.txt
    python batch.py --lecture-id PsychLec5 --transcript lecture5.txt --concepts concepts.json --summary summary.txt --format txt
"""

import argparse
import sys
import os
from pathlib import Path

# Add both current directory and project root to path
# IMPORTANT: Current dir must be FIRST so we import the right parsers.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)  # Add project root second
sys.path.insert(0, current_dir)   # Add current dir first (highest priority)

from google import genai

from chat.gemini.config import GeminiConfig
from chat.gemini.parsers import read_file_with_fallback, parse_transcript, parse_concepts, parse_summary
from chat.gemini.chunker import chunk_transcript
from chat.gemini.store_manager import StoreManager
from chat.gemini.store_registry import StoreRegistry


def main():
    parser = argparse.ArgumentParser(
        description="Upload and process lecture content for Gemini RAG"
    )

    # Required arguments
    parser.add_argument(
        '--lecture-id',
        help='Unique identifier for the lecture (e.g., PsychLec4). Auto-generated if not provided.'
    )
    parser.add_argument(
        '--transcript',
        help='Path to transcript file (.vtt, .txt, or .csv). Auto-detected from videos_dir if not provided.'
    )

    # Optional arguments
    parser.add_argument(
        '--concepts',
        help='Path to concepts JSON file'
    )
    parser.add_argument(
        '--summary',
        help='Path to summary text file'
    )
    parser.add_argument(
        '--format',
        choices=['auto', 'vtt', 'txt', 'csv'],
        default='auto',
        help='Transcript format (auto-detected by default)'
    )
    parser.add_argument(
        '--chunk-interval',
        type=int,
        default=30,
        help='Chunk interval in seconds (default: 30)'
    )
    parser.add_argument(
        '--store-name',
        help='Custom store name (optional)'
    )
    parser.add_argument(
        '--api-key',
        help='Gemini API key (alternatively set GEMINI_API_KEY env var)'
    )

    args = parser.parse_args()

    # Initialize configuration
    try:
        if args.api_key:
            # Use direct API key if provided
            config = GeminiConfig(api_key=args.api_key)
        else:
            # Load from project-wide config.yaml
            config = GeminiConfig.from_project_config()

        # Override store name if provided via command line
        if args.store_name:
            config.store_display_name = args.store_name

    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Config file error: {e}")
        print("Falling back to environment variables only...")
        try:
            config = GeminiConfig.from_env(store_name=args.store_name)
        except ValueError as e2:
            print(f"Configuration error: {e2}")
            sys.exit(1)

    # Auto-detect transcript file if not provided
    transcript_path = args.transcript
    if not transcript_path and config.videos_dir:
        print(f"\n-> Auto-detecting transcript file in: {config.videos_dir}")
        import glob
        vtt_files = glob.glob(os.path.join(config.videos_dir, "*.vtt"))
        if vtt_files:
            transcript_path = vtt_files[0]
            print(f"-> Found: {os.path.basename(transcript_path)}")
        else:
            print("Error: No .vtt file found in videos_dir")
            sys.exit(1)
    elif not transcript_path:
        print("Error: No transcript file specified and no videos_dir in config")
        sys.exit(1)

    # Auto-generate lecture ID if not provided
    lecture_id = args.lecture_id
    if not lecture_id:
        # Generate from course name and timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        lecture_id = f"{config.course_name}_{timestamp}"
        print(f"\n-> Auto-generated lecture ID: {lecture_id}")

    # Auto-detect concepts and summary from videos_dir if not provided
    concepts_path = args.concepts
    summary_path = args.summary

    if not concepts_path and config.videos_dir:
        concepts_file = os.path.join(config.videos_dir, config.concepts_file)
        if os.path.exists(concepts_file):
            concepts_path = concepts_file
            print(f"-> Found concepts file: {config.concepts_file}")

    if not summary_path and config.videos_dir:
        summary_file = os.path.join(config.videos_dir, config.summary_file)
        if os.path.exists(summary_file):
            summary_path = summary_file
            print(f"-> Found summary file: {config.summary_file}")

    # Update configuration with lecture-specific settings
    config.update_lecture_paths(
        vtt_path=transcript_path,
        concepts_path=concepts_path,
        summary_path=summary_path,
        lecture_id=lecture_id
    )
    config.chunk_interval_seconds = args.chunk_interval

    print("=" * 70)
    print(f"📚 Gemini RAG Batch Upload - Lecture: {lecture_id}")
    print("=" * 70)
    print(f"Transcript: {transcript_path}")
    if concepts_path:
        print(f"Concepts: {concepts_path}")
    if summary_path:
        print(f"Summary: {summary_path}")
    print("=" * 70)

    # Step 1: Read and parse input files
    print("\n[Step 1/4] Reading and parsing input files...")

    transcript_content = read_file_with_fallback(transcript_path, "transcript")
    concepts_content = read_file_with_fallback(concepts_path, "concepts") if concepts_path else ""
    summary_content = read_file_with_fallback(summary_path, "summary") if summary_path else ""

    # Parse content
    transcript_text = parse_transcript(transcript_content, file_format=args.format)
    course_topics = parse_concepts(concepts_content) if concepts_content else "N/A"
    lecture_summary = parse_summary(summary_content) if summary_content else "N/A"

    if not transcript_text:
        print("Error: Failed to parse transcript. Exiting.")
        sys.exit(1)

    print(f"✓ Transcript parsed: {len(transcript_text.split(chr(10)))} lines")
    print(f"✓ Topics: {course_topics[:100]}...")
    print(f"✓ Summary: {lecture_summary[:100]}...")

    # Step 2: Chunk transcript
    print(f"\n[Step 2/4] Chunking transcript ({config.chunk_interval_seconds}s intervals)...")

    chunk_files = chunk_transcript(
        transcript_text=transcript_text,
        lecture_id=lecture_id,
        chunk_interval_seconds=config.chunk_interval_seconds,
        output_dir=config.output_dir
    )

    if not chunk_files:
        print("Error: Failed to create chunks. Exiting.")
        sys.exit(1)

    print(f"✓ Created {len(chunk_files)} chunk files in {config.output_dir}/")

    # TESTING: Limit to first 10 files for fast testing
    # if len(chunk_files) > 10:
    #     print(f"\n⚠️  TESTING MODE: Limiting upload to first 10 files (out of {len(chunk_files)})")
    #     chunk_files = chunk_files[:10]

    # Step 2.5: Embed chunks for later retrieval
    print(f"\n[Step 2.5/5] Embedding chunks for semantic search...")

    try:
        from chat.embedding import embed_segments, save_embeddings
        import re

        # Load chunks into the format expected by embed_segments
        chunks_data = []
        for file_path in chunk_files:
            filename = os.path.basename(file_path)
            match = re.match(r'(.+?)_(\d{2}-\d{2}-\d{2})_to_(\d{2}-\d{2}-\d{2})\.txt', filename)

            if match:
                lecture_id_from_file = match.group(1)
                start_time = match.group(2).replace('-', ':')
                end_time = match.group(3).replace('-', ':')

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                chunks_data.append({
                    'lecture_id': lecture_id_from_file,
                    'start_time': start_time,
                    'end_time': end_time,
                    'filename': filename,
                    'text': content,
                    'reference': f"{start_time} - {end_time}"
                })

        # Embed all chunks
        embedded_chunks, model = embed_segments(chunks_data)

        # Save embeddings to disk
        embeddings_file = os.path.join(config.output_dir, "embeddings.pkl")
        save_embeddings(embeddings_file, embedded_chunks)

        print(f"✓ Embedded {len(embedded_chunks)} chunks")
        print(f"✓ Saved embeddings to: {embeddings_file}")

    except Exception as e:
        print(f"⚠️  Warning: Could not embed chunks: {e}")
        print(f"   Chunk references in queries may not be available.")

    # Step 3: Initialize Gemini client and store
    print("\n[Step 3/4] Connecting to Gemini and preparing store...")

    try:
        client = genai.Client(api_key=config.api_key)

        # Look up store_id from registry using (institute, course)
        registry_path = "chat/gemini/store_registry.json"
        registry = StoreRegistry(registry_path)

        institute = config.institute if config.institute else "default_institute"
        course = config.course_name if config.course_name else "default_course"

        # Try to get existing store from registry
        store_id = registry.get_store(institute, course)

        if store_id:
            print(f"-> Found existing store in registry for {institute}:{course}")
            print(f"-> Store ID: {store_id}")
        else:
            print(f"-> No existing store found for {institute}:{course}")
            print(f"-> Will create new store")

        # Initialize store manager with store_id from registry (or None for new store)
        store_manager = StoreManager(
            client,
            config.store_display_name,
            store_id=store_id
        )
        store = store_manager.get_or_create_store()
        print(f"✓ Store ready: {store.name}")
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        sys.exit(1)

    # Step 4: Upload chunks to store
    print(f"\n[Step 4/4] Uploading {len(chunk_files)} files to store...")

    try:
        operations = store_manager.upload_files(
            file_paths=chunk_files,
            max_wait_seconds=config.max_upload_wait_seconds
        )
        print(f"✓ Upload complete! {len(operations)} files processed")
    except Exception as e:
        print(f"Error during upload: {e}")
        sys.exit(1)

    # Register store in registry (if not already registered)
    print("\n[Step 5/5] Updating store registry...")
    try:
        # Re-register to ensure registry is up-to-date (idempotent operation)
        registry.register_store(institute, course, store.name)
        print(f"✓ Registry updated: {institute}:{course} → {store.name}")

    except Exception as e:
        print(f"⚠️  Warning: Could not update registry: {e}")
        print(f"   You can manually register it later using store_registry.py")

    # Summary
    print("\n" + "=" * 70)
    print("✅ Batch upload completed successfully!")
    print("=" * 70)
    print(f"Lecture ID: {lecture_id}")
    print(f"Chunks created: {len(chunk_files)}")
    print(f"Store Name: {store.name}")
    print(f"Store Display: {config.store_display_name}")
    print(f"Registry: {institute}:{course}")
    print(f"Files uploaded: {len(operations)}")
    print("\nYou can now use the interactive.py script to query this lecture.")
    print("=" * 70)


if __name__ == "__main__":
    main()