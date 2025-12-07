#!/usr/bin/env python3
"""
Embed existing chunk files without uploading to store
Useful when chunks already exist but need embeddings
"""

import sys
import os
import glob
import re
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from chat.embedding import embed_segments, save_embeddings


def main():
    # Find the most recent chunks directory
    chunks_dirs = glob.glob(os.path.join(os.getcwd(), "*_chunks"))

    if not chunks_dirs:
        print("Error: No chunks directory found in current directory")
        print("Looking for directories matching: *_chunks")
        sys.exit(1)

    # Use most recent chunks directory
    chunks_dir = max(chunks_dirs, key=os.path.getmtime)

    print("=" * 70)
    print("🔢 Embedding Existing Chunks")
    print("=" * 70)
    print(f"Chunks directory: {chunks_dir}")
    print()

    # Check if embeddings already exist
    embeddings_file = os.path.join(chunks_dir, "embeddings.pkl")
    if os.path.exists(embeddings_file):
        print(f"⚠️  Warning: Embeddings file already exists: {embeddings_file}")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)

    # Load all chunk files
    chunk_files = sorted(glob.glob(os.path.join(chunks_dir, "*.txt")))

    if not chunk_files:
        print(f"Error: No .txt files found in {chunks_dir}")
        sys.exit(1)

    print(f"Found {len(chunk_files)} chunk files")
    print()

    # Load chunks into the format expected by embed_segments
    print("Loading chunks...")
    chunks_data = []

    for file_path in chunk_files:
        filename = os.path.basename(file_path)

        # Parse filename: LectureID_START_to_END.txt
        match = re.match(r'(.+?)_(\d{2}-\d{2}-\d{2})_to_(\d{2}-\d{2}-\d{2})\.txt', filename)

        if match:
            lecture_id = match.group(1)
            start_time = match.group(2).replace('-', ':')
            end_time = match.group(3).replace('-', ':')

            # Read chunk content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks_data.append({
                'lecture_id': lecture_id,
                'start_time': start_time,
                'end_time': end_time,
                'filename': filename,
                'text': content,
                'content': content,
                'reference': f"{start_time} - {end_time}"
            })

    print(f"✓ Loaded {len(chunks_data)} chunks")
    print()

    # Embed all chunks
    print("Embedding chunks...")
    print("(This may take a few minutes for the first run)")
    print()

    embedded_chunks, model = embed_segments(chunks_data)

    print()
    print(f"✓ Embedded {len(embedded_chunks)} chunks")
    print()

    # Save embeddings to disk
    print(f"Saving embeddings to: {embeddings_file}")
    save_embeddings(embeddings_file, embedded_chunks)

    print()
    print("=" * 70)
    print("✅ Embedding complete!")
    print("=" * 70)
    print(f"Chunks directory: {chunks_dir}")
    print(f"Embeddings file: {embeddings_file}")
    print(f"Total chunks: {len(embedded_chunks)}")
    print()
    print("You can now use interactive.py to query with chunk references!")
    print("=" * 70)


if __name__ == "__main__":
    main()