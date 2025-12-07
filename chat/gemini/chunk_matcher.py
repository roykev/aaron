"""
Match Gemini answers to source chunks using embeddings
"""

import os
import re
import glob
import sys
from pathlib import Path
from typing import List, Dict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path to import embedding modules
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)

from chat.embedding import embed_segments, load_embeddings
from sentence_transformers import SentenceTransformer


class ChunkMatcher:
    """Matches Gemini answers to source chunks using embedding similarity"""

    def __init__(
        self,
        chunks_dir: str,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        embeddings_file: str = None
    ):
        """
        Initialize chunk matcher

        Args:
            chunks_dir: Directory containing chunk files
            model_name: SentenceTransformer model name (default: multilingual MiniLM)
            embeddings_file: Path to pre-computed embeddings file (.pkl)
                           If None, will look for embeddings.pkl in chunks_dir
        """
        self.chunks_dir = chunks_dir
        self.model_name = model_name
        print(f"-> Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        # Try to load pre-computed embeddings
        if embeddings_file is None:
            embeddings_file = os.path.join(chunks_dir, "embeddings.pkl")

        if os.path.exists(embeddings_file):
            print(f"-> Loading pre-computed embeddings from: {embeddings_file}")
            self.chunks = load_embeddings(embeddings_file)
            print(f"-> Loaded {len(self.chunks)} pre-embedded chunks")
        else:
            print(f"-> No pre-computed embeddings found, embedding chunks...")
            self.chunks = self._load_chunks()
            self._embed_chunks()

    def _load_chunks(self) -> List[Dict]:
        """Load all chunk files from directory"""
        chunks = []

        if not os.path.exists(self.chunks_dir):
            print(f"Warning: Chunks directory not found: {self.chunks_dir}")
            return chunks

        chunk_files = sorted(glob.glob(os.path.join(self.chunks_dir, "*.txt")))

        for file_path in chunk_files:
            filename = os.path.basename(file_path)

            # Parse filename: LectureID_START_to_END.txt
            # Example: psychology_20251206_234701_00-00-00_to_00-00-00.txt
            match = re.match(r'(.+?)_(\d{2}-\d{2}-\d{2})_to_(\d{2}-\d{2}-\d{2})\.txt', filename)

            if match:
                lecture_id = match.group(1)
                start_time = match.group(2).replace('-', ':')
                end_time = match.group(3).replace('-', ':')

                # Read chunk content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    chunks.append({
                        'lecture_id': lecture_id,
                        'start_time': start_time,
                        'end_time': end_time,
                        'file_path': file_path,
                        'filename': filename,
                        'text': content,  # Use 'text' key for compatibility with embedding.py
                        'content': content,
                        'reference': f"{start_time} - {end_time}"
                    })
                except Exception as e:
                    print(f"Warning: Could not read {filename}: {e}")

        print(f"-> Loaded {len(chunks)} chunks from {self.chunks_dir}")
        return chunks

    def _embed_chunks(self):
        """Embed all chunks using the sentence transformer model"""
        if not self.chunks:
            return

        print(f"-> Embedding {len(self.chunks)} chunks...")

        # Use the existing embed_segments function from embedding.py
        self.chunks, _ = embed_segments(self.chunks, model_name=self.model_name)

        print(f"-> Finished embedding chunks")

    def find_matching_chunks(
        self,
        answer: str,
        top_k: int = 3,
        score_threshold: float = 0.3
    ) -> List[Dict]:
        """
        Find chunks that best match the given answer using semantic search

        Args:
            answer: Gemini's answer text
            top_k: Number of top matching chunks to return
            score_threshold: Minimum similarity score threshold

        Returns:
            List of top matching chunks with similarity scores
        """
        if not self.chunks:
            return []

        # Embed the answer using the same model
        answer_embedding = self.model.encode([answer], convert_to_numpy=True)

        # Get all chunk embeddings
        chunk_embeddings = np.array([c["embedding"] for c in self.chunks])

        # Calculate cosine similarity (using sklearn, same as search.py)
        similarities = cosine_similarity(answer_embedding, chunk_embeddings)[0]

        # Sort by similarity (highest first)
        top_indices = similarities.argsort()[::-1]

        # Build results with score threshold
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score < score_threshold:
                continue  # Skip low-relevance results

            chunk = self.chunks[idx]
            results.append({
                **chunk,
                'similarity': round(score, 3),
                'score': round(score, 3)  # Add 'score' for compatibility
            })

            if len(results) >= top_k:
                break

        return results

    def match_and_display(
        self,
        answer: str,
        top_k: int = 3,
        verbose: bool = True
    ) -> List[Dict]:
        """
        Find and display matching chunks

        Args:
            answer: Gemini's answer text
            top_k: Number of chunks to display
            verbose: Whether to print results

        Returns:
            List of top matching chunks
        """
        matches = self.find_matching_chunks(answer, top_k)

        if verbose and matches:
            print(f"\n📚 Top {len(matches)} Source Chunks (based on answer similarity):")
            print("=" * 70)

            for i, chunk in enumerate(matches, 1):
                print(f"\n[{i}] {chunk['lecture_id']}")
                print(f"    ⏰ Time: {chunk['start_time']} - {chunk['end_time']}")
                print(f"    📄 File: {chunk['filename']}")
                print(f"    🎯 Similarity: {chunk['similarity']:.3f}")

                # Display chunk content preview
                content = chunk['content']
                max_length = 200
                if len(content) > max_length:
                    preview = content[:max_length] + "..."
                else:
                    preview = content

                print(f"    📝 Content:\n       {preview.replace(chr(10), chr(10) + '       ')}")
                print()

        return matches