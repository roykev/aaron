"""
Parsers for lecture content files (VTT transcripts, concepts, summaries)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)  # Add project root second
sys.path.insert(0, current_dir)   # Add current dir first (highest priority)
from chat.gemini.config import PLACEHOLDER_VTT, PLACEHOLDER_CONCEPTS, PLACEHOLDER_SUMMARY


def read_file_with_fallback(filepath: Optional[str], content_type: str) -> str:
    """
    Attempts to read content from filepath, falls back to placeholder if not found

    Args:
        filepath: Path to the file
        content_type: Type of content ('transcript', 'concepts', or 'summary')

    Returns:
        File content as string
    """
    if filepath and os.path.exists(filepath):
        print(f"-> Reading actual file: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read file at {filepath}. Error: {e}")

    # Fallback to placeholder content
    print(f"-> Using placeholder content for {content_type} (File not found or path not provided).")
    if 'transcript' in content_type:
        return PLACEHOLDER_VTT
    elif 'concepts' in content_type:
        return PLACEHOLDER_CONCEPTS
    elif 'summary' in content_type:
        return PLACEHOLDER_SUMMARY
    return ""


def parse_transcript(transcript_content: str, file_format: str = 'auto') -> str:
    """
    Parses transcript content from various formats (VTT, TXT, CSV)

    Args:
        transcript_content: Raw transcript file content
        file_format: Format type ('vtt', 'txt', 'csv', or 'auto' for auto-detection)

    Returns:
        Formatted transcript with timestamps: "[HH:MM:SS] text..."
    """
    # Auto-detect format if not specified
    if file_format == 'auto':
        if 'WEBVTT' in transcript_content[:100]:
            file_format = 'vtt'
        elif ',' in transcript_content[:500] and ('\n' in transcript_content[:500]):
            file_format = 'csv'
        else:
            file_format = 'txt'

    print(f"-> Parsing transcript (format: {file_format.upper()})...")

    if file_format == 'vtt':
        return _parse_vtt(transcript_content)
    elif file_format == 'csv':
        return _parse_csv(transcript_content)
    elif file_format == 'txt':
        return _parse_txt(transcript_content)
    else:
        raise ValueError(f"Unsupported transcript format: {file_format}")


def _parse_vtt(vtt_content: str) -> str:
    """Parse WebVTT format transcript"""
    # Split by two or more newlines (cue separators)
    cues = re.split(r'\n{2,}', vtt_content)
    transcript_lines = []

    for cue in cues:
        # Skip header and empty cues
        if 'WEBVTT' in cue or not cue.strip():
            continue

        lines = cue.strip().split('\n')

        # Find timecode line (contains -->)
        time_line = next((line for line in lines if '-->' in line), None)
        if time_line:
            # Extract start time (HH:MM:SS.mmm) and convert to [HH:MM:SS]
            time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.\d{3}', time_line)
            if time_match:
                start_time = time_match.group(1)

                # Extract text (lines after timecode)
                text_lines = lines[lines.index(time_line) + 1:]
                text = " ".join(text_lines).strip()

                # Clean up VTT formatting (HTML tags, excessive spaces)
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r' +', ' ', text).strip()

                if text:
                    transcript_lines.append(f"[{start_time}] {text}")

    print(f"-> VTT parsing successful. Extracted {len(transcript_lines)} transcript points.")
    return "\n".join(transcript_lines)


def _parse_txt(txt_content: str) -> str:
    """
    Parse plain text transcript
    Assumes format: "[HH:MM:SS] text" or "HH:MM:SS text" or just text with timestamps
    """
    lines = txt_content.strip().split('\n')
    transcript_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if line already has [HH:MM:SS] format
        if re.match(r'\[\d{2}:\d{2}:\d{2}\]', line):
            transcript_lines.append(line)
        # Check if line has HH:MM:SS format without brackets
        elif re.match(r'\d{2}:\d{2}:\d{2}', line):
            # Add brackets around timestamp
            line = re.sub(r'^(\d{2}:\d{2}:\d{2})', r'[\1]', line)
            transcript_lines.append(line)
        else:
            # Line has no timestamp - skip or assign generic timestamp
            # For now, we'll skip lines without timestamps
            continue

    print(f"-> TXT parsing successful. Extracted {len(transcript_lines)} transcript points.")
    return "\n".join(transcript_lines)


def _parse_csv(csv_content: str) -> str:
    """
    Parse CSV transcript
    Expected format: timestamp,text or time,speaker,text
    """
    lines = csv_content.strip().split('\n')
    transcript_lines = []

    # Skip header row if present
    start_idx = 1 if ('time' in lines[0].lower() or 'timestamp' in lines[0].lower()) else 0

    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue

        # Split by comma (handle quoted fields)
        parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', line)

        if len(parts) >= 2:
            timestamp = parts[0].strip().strip('"')
            # If 3 columns, assume timestamp,speaker,text; otherwise timestamp,text
            text = parts[2].strip().strip('"') if len(parts) >= 3 else parts[1].strip().strip('"')

            # Normalize timestamp to HH:MM:SS format
            time_match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', timestamp)
            if time_match:
                h, m, s = time_match.groups()
                normalized_time = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
                transcript_lines.append(f"[{normalized_time}] {text}")

    print(f"-> CSV parsing successful. Extracted {len(transcript_lines)} transcript points.")
    return "\n".join(transcript_lines)


def parse_concepts(json_content: str) -> str:
    """
    Parses concepts JSON and returns comma-separated string

    Args:
        json_content: JSON string with concepts

    Returns:
        Comma-separated concepts string
    """
    print("-> Parsing concepts JSON...")
    try:
        data = json.loads(json_content)
        concepts = [item['concept'] for item in data.get('concepts', [])]
        concepts_str = ", ".join(concepts)
        print(f"-> Extracted {len(concepts)} concepts.")
        return concepts_str
    except json.JSONDecodeError as e:
        print(f"Error decoding concepts JSON: {e}")
        return "N/A"


def parse_summary(text_content: str) -> str:
    """
    Reads and cleans lecture summary text

    Args:
        text_content: Raw summary text

    Returns:
        Cleaned summary text
    """
    print("-> Reading short summary...")
    return text_content.strip()