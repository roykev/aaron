"""
Transcript chunking functionality for creating time-based segments
"""

import os
import re
from typing import List, Tuple


def time_to_seconds(time_str: str) -> int:
    """Convert HH:MM:SS to total seconds"""
    h, m, s = map(int, time_str.split(':'))
    return h * 3600 + m * 60 + s


def seconds_to_time(total_seconds: int) -> str:
    """Convert total seconds to HH:MM:SS format"""
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def chunk_transcript(
    transcript_text: str,
    lecture_id: str,
    chunk_interval_seconds: int = 30,
    output_dir: str = "chunks"
) -> List[str]:
    """
    Splits transcript into time-based chunks and saves as separate files

    Args:
        transcript_text: Formatted transcript with [HH:MM:SS] timestamps
        lecture_id: Identifier for the lecture (used in filenames)
        chunk_interval_seconds: Duration of each chunk in seconds
        output_dir: Directory to save chunk files

    Returns:
        List of file paths for created chunks
    """
    print(f"-> Starting chunking process (Interval: {chunk_interval_seconds}s)...")
    os.makedirs(output_dir, exist_ok=True)

    # Extract all time points from transcript
    time_points = re.findall(r"\[(\d{2}:\d{2}:\d{2})\]", transcript_text)

    # Split text by time codes, keeping time codes as delimiters
    parts = re.split(r"(\[\d{2}:\d{2}:\d{2}\])", transcript_text)

    # Parse content into (time, text) tuples
    content_lines: List[Tuple[str, str]] = []
    current_time = "00:00:00"

    for part in parts:
        if part.strip():
            if re.match(r"\[\d{2}:\d{2}:\d{2}\]", part):
                current_time = part.strip().strip('[]')
            else:
                content_lines.append((current_time, part.strip()))

    if not content_lines:
        print("Error: Could not parse transcript content.")
        return []

    # Create chunks based on time intervals
    chunked_files = []
    current_chunk: List[Tuple[str, str]] = []
    start_time_sec = time_to_seconds(content_lines[0][0])

    for line_time_str, line_text in content_lines:
        line_time_sec = time_to_seconds(line_time_str)

        # Check if current line exceeds chunk interval
        if line_time_sec >= start_time_sec + chunk_interval_seconds and current_chunk:
            # Save current chunk
            filepath = _save_chunk(
                current_chunk,
                lecture_id,
                start_time_sec,
                output_dir
            )
            chunked_files.append(filepath)

            # Start new chunk
            current_chunk = [(line_time_str, line_text)]
            start_time_sec = line_time_sec
        else:
            current_chunk.append((line_time_str, line_text))

    # Save final chunk
    if current_chunk:
        filepath = _save_chunk(
            current_chunk,
            lecture_id,
            start_time_sec,
            output_dir
        )
        chunked_files.append(filepath)

    print(f"-> Chunking complete. Generated {len(chunked_files)} files in {output_dir}/")
    return chunked_files


def _save_chunk(
    chunk: List[Tuple[str, str]],
    lecture_id: str,
    start_time_sec: int,
    output_dir: str
) -> str:
    """
    Save a single chunk to file

    Args:
        chunk: List of (time, text) tuples
        lecture_id: Lecture identifier
        start_time_sec: Start time in seconds
        output_dir: Output directory

    Returns:
        Path to saved file
    """
    end_time_sec = time_to_seconds(chunk[-1][0])
    start_time_str = seconds_to_time(start_time_sec).replace(':', '-')
    end_time_str = seconds_to_time(end_time_sec).replace(':', '-')

    filename = f"{lecture_id}_{start_time_str}_to_{end_time_str}.txt"
    filepath = os.path.join(output_dir, filename)

    chunk_content = "\n".join([f"[{t}] {text}" for t, text in chunk])

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"--- {lecture_id}: Lecture Segment ---\n")
        f.write(f"Time Range: {seconds_to_time(start_time_sec)} to {seconds_to_time(end_time_sec)}\n\n")
        f.write(chunk_content)

    return filepath