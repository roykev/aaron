"""
Learning Dashboard - Layer 0: Data Cleaning & Deduplication

Purpose: Collect all raw student signals into a single flat list, deduplicated per student.
Output: Clean signals table, one row per unique (student × topic × signal_type).

No user_id→email mapping required - signals are kept in separate student pools.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd


# =========================================================
# Data structures
# =========================================================

@dataclass
class StudentSignal:
    """A single cleaned student signal about a topic."""
    signal_type: str  # "eval_failure" | "quiz_failure" | "query" | "inclass_question"
    signal_text: str  # The actual content (query text or question text)
    lecture_id: str
    lecture_name: str
    student_id: Optional[str] = None  # user_id for queries, email for assessments, None for in-class
    question_number: Optional[int] = None  # For assessment signals
    timestamp: Optional[str] = None  # For queries and in-class questions

    def __hash__(self):
        # For deduplication
        return hash((self.signal_type, self.signal_text, self.lecture_id, self.student_id))


@dataclass
class QuestionTextMap:
    """Maps (lecture_id, question_number) → question_text for both quiz and eval."""
    quiz: Dict[str, Dict[int, str]]  # lecture_id → {question_num → text}
    evaluation: Dict[str, Dict[int, str]]


# =========================================================
# Step 0.1: Load raw data files
# =========================================================

def load_queries_csv(csv_path: str | Path, lecture_id: Optional[str] = None) -> pd.DataFrame:
    """
    Load queries.csv and filter to lecture-level queries only.

    Columns: time, query, name (lecture_name), entity_id (lecture_id), user_id, source_type
    """
    df = pd.read_csv(csv_path, encoding="utf-8")

    # Filter to lecture-level queries only
    df = df[df["source_type"] == "lecture"].copy()

    # If specific lecture requested, filter further
    if lecture_id:
        df = df[df["entity_id"] == lecture_id].copy()

    return df


def load_assessment_csv(csv_path: str | Path, lecture_id: Optional[str] = None) -> pd.DataFrame:
    """
    Load quiz.csv or eval.csv.

    Columns: name (student), email, name (lecture), lecture_id, score, time, type, answers (JSON), results_full

    Note: There are duplicate 'name' columns - first is student name, second is lecture name.
    """
    # Read without header first to handle duplicate column names
    df = pd.read_csv(csv_path, encoding="utf-8", header=None, skiprows=1)

    # Set proper column names
    df.columns = ["student_name", "email", "lecture_name", "lecture_id", "score", "time", "type", "answers", "results_full"]

    # Filter to specific lecture if requested
    if lecture_id:
        df = df[df["lecture_id"] == lecture_id].copy()

    return df


def load_correct_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    Load correct.csv (the course question bank).

    Columns: lecture_id, name, quiz (JSON), evaluation (JSON)
    """
    return pd.read_csv(csv_path, encoding="utf-8")


def load_concepts_json(json_path: str | Path) -> List[Dict[str, Any]]:
    """
    Load concepts.json.

    Format: {"concepts": [{"concept": "name", "times": [{"start": "00:11:00", "end": "00:30:00"}]}]}
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("concepts", [])


def parse_output_txt(txt_path: str | Path) -> Dict[str, Any]:
    """
    Parse output.txt which contains sections, examples, interactions, etc.

    Returns dict with: interactions (only what we need for Layer 0)
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = {}

    # Extract interactions (CSV format) - only thing we need for Layer 0
    interactions_match = re.search(r'### interaction ###\s*(.+?)(?=\n### |\Z)', content, re.DOTALL)
    if interactions_match:
        interactions_text = interactions_match.group(1).strip()
        lines = interactions_text.split("\n")
        if len(lines) > 1:
            try:
                result["interactions"] = pd.read_csv(pd.io.common.StringIO(interactions_text))
            except Exception as e:
                print(f"Warning: Could not parse interactions: {e}")
                result["interactions"] = None

    return result


# =========================================================
# Step 0.2: Extract question texts from correct.csv
# =========================================================

def build_question_text_map(correct_df: pd.DataFrame) -> QuestionTextMap:
    """
    Extract full question text for each (lecture_id, question_number, source).

    Returns mapping: lecture_id → question_number → question_text
    """
    quiz_map: Dict[str, Dict[int, str]] = {}
    eval_map: Dict[str, Dict[int, str]] = {}

    for _, row in correct_df.iterrows():
        lecture_id = row["lecture_id"]

        # Parse quiz questions
        if pd.notna(row["quiz"]):
            quiz_data = json.loads(row["quiz"]) if isinstance(row["quiz"], str) else row["quiz"]
            questions = quiz_data.get("questions", [])
            quiz_map[lecture_id] = {
                i + 1: q.get("question", "")
                for i, q in enumerate(questions)
            }

        # Parse evaluation questions
        if pd.notna(row["evaluation"]):
            eval_data = json.loads(row["evaluation"]) if isinstance(row["evaluation"], str) else row["evaluation"]
            questions = eval_data.get("questions", [])
            eval_map[lecture_id] = {
                i + 1: q.get("question", "")
                for i, q in enumerate(questions)
            }

    return QuestionTextMap(quiz=quiz_map, evaluation=eval_map)


# =========================================================
# Step 0.3: Extract signals from each source
# =========================================================

def extract_query_signals(queries_df: pd.DataFrame) -> List[StudentSignal]:
    """
    Extract query signals from queries.csv.

    One signal per (user_id, query_text, lecture).
    """
    signals = []

    for _, row in queries_df.iterrows():
        signal = StudentSignal(
            signal_type="query",
            signal_text=str(row["query"]).strip(),
            lecture_id=row["entity_id"],
            lecture_name=row["name"],
            student_id=row["user_id"],
            timestamp=row["time"]
        )
        signals.append(signal)

    return signals


def extract_assessment_signals(
    assessment_df: pd.DataFrame,
    question_map: Dict[int, str],
    signal_type: str,  # "quiz_failure" or "eval_failure"
) -> List[StudentSignal]:
    """
    Extract failure signals from quiz.csv or eval.csv.

    One signal per (student, question) where correct=False.
    """
    signals = []

    for _, row in assessment_df.iterrows():
        # Parse answers JSON
        answers_str = row["answers"]
        if pd.isna(answers_str):
            continue

        answers = json.loads(answers_str) if isinstance(answers_str, str) else answers_str

        # Extract failures only
        for q_num_str, q_data in answers.items():
            if not q_data.get("correct", True):  # If not correct
                q_num = int(q_num_str)
                question_text = question_map.get(q_num, f"Question {q_num}")

                signal = StudentSignal(
                    signal_type=signal_type,
                    signal_text=question_text,
                    lecture_id=row["lecture_id"],
                    lecture_name=row["lecture_name"],
                    student_id=row["email"],  # Using email as student_id for assessments
                    question_number=q_num,
                    timestamp=row["time"]
                )
                signals.append(signal)

    return signals


def extract_inclass_question_signals(
    interactions_df: pd.DataFrame,
    lecture_id: str,
    lecture_name: str
) -> List[StudentSignal]:
    """
    Extract in-class question signals from interactions data.

    Only include rows where סוג (type) contains "שאלת" (question).
    """
    signals = []

    if interactions_df is None or interactions_df.empty:
        return signals

    # Filter to questions only
    question_rows = interactions_df[
        interactions_df["סוג"].str.contains("שאלת", na=False)
    ]

    for _, row in question_rows.iterrows():
        signal = StudentSignal(
            signal_type="inclass_question",
            signal_text=row["תיאור"],  # Description column
            lecture_id=lecture_id,
            lecture_name=lecture_name,
            student_id=None,  # In-class questions have no student ID
            timestamp=row["זמן"]  # Time column
        )
        signals.append(signal)

    return signals


# =========================================================
# Step 0.4: Noise removal
# =========================================================

def normalize_query_text(text: str) -> str:
    """Normalize query text for deduplication."""
    text = str(text).strip().lower()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def is_noise_query(text: str) -> bool:
    """
    Detect noise queries:
    - Keyboard gibberish (short English-only on Hebrew content)
    - Session-close terms
    - Empty or single-character
    """
    normalized = normalize_query_text(text)

    # Empty or too short
    if len(normalized) < 2:
        return True

    # Session-close terms (Hebrew and English)
    close_terms = {"ביי", "bye", "שלום", "להתראות", "תודה", "thanks"}
    if normalized in close_terms:
        return True

    # Keyboard gibberish: short English-only strings (< 8 chars) with only letters/punctuation
    if len(normalized) <= 8 and re.match(r'^[a-z,.\s]+$', normalized):
        # Check if it looks like Hebrew context (this is a heuristic)
        # In a real implementation, you'd check the lecture language
        return True

    return False


def remove_noise_signals(signals: List[StudentSignal]) -> List[StudentSignal]:
    """Remove noise query signals."""
    clean_signals = []

    for signal in signals:
        # Only filter queries, keep all other signal types
        if signal.signal_type == "query":
            if not is_noise_query(signal.signal_text):
                clean_signals.append(signal)
        else:
            clean_signals.append(signal)

    return clean_signals


# =========================================================
# Step 0.5: Deduplication per student
# =========================================================

def deduplicate_signals(signals: List[StudentSignal]) -> List[StudentSignal]:
    """
    Deduplicate signals per student.

    Rules:
    - For eval/quiz failures: one signal per (student, question_number) - already unique
    - For queries: deduplicate by (user_id, normalized_query, lecture)
    - For inclass_questions: no deduplication - already discrete events
    """
    # Separate by type
    assessment_signals = [s for s in signals if s.signal_type in ("eval_failure", "quiz_failure")]
    query_signals = [s for s in signals if s.signal_type == "query"]
    inclass_signals = [s for s in signals if s.signal_type == "inclass_question"]

    # Assessment signals: deduplicate by (student, lecture, question_number)
    assessment_unique = {}
    for signal in assessment_signals:
        key = (signal.student_id, signal.lecture_id, signal.question_number, signal.signal_type)
        if key not in assessment_unique:
            assessment_unique[key] = signal

    # Query signals: deduplicate by (student, lecture, normalized_query)
    query_unique = {}
    for signal in query_signals:
        normalized = normalize_query_text(signal.signal_text)
        key = (signal.student_id, signal.lecture_id, normalized)
        if key not in query_unique:
            query_unique[key] = signal

    # In-class signals: no deduplication

    return list(assessment_unique.values()) + list(query_unique.values()) + inclass_signals


# =========================================================
# Main orchestration
# =========================================================

def collect_clean_signals(
    queries_csv_path: str | Path,
    quiz_csv_path: str | Path,
    eval_csv_path: str | Path,
    correct_csv_path: str | Path,
    output_txt_path: Optional[str | Path] = None,
    lecture_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Layer 0 orchestration: collect all raw student signals and clean them.

    Returns:
        {
            "signals": List[StudentSignal],  # All cleaned signals
            "signals_df": pd.DataFrame,      # DataFrame version for analysis
            "question_map": QuestionTextMap,
            "metadata": {
                "total_signals_raw": int,
                "total_signals_after_noise_removal": int,
                "total_signals_after_dedup": int,
                "signal_type_counts": Dict[str, int],
                "unique_query_students": int,
                "unique_assessment_students": int,
                "student_linking_available": False
            }
        }
    """
    # Load data
    queries_df = load_queries_csv(queries_csv_path, lecture_id)
    quiz_df = load_assessment_csv(quiz_csv_path, lecture_id)
    eval_df = load_assessment_csv(eval_csv_path, lecture_id)
    correct_df = load_correct_csv(correct_csv_path)

    # Build question text map
    question_map = build_question_text_map(correct_df)

    # Extract signals from each source
    all_signals: List[StudentSignal] = []

    # Query signals
    query_signals = extract_query_signals(queries_df)
    all_signals.extend(query_signals)

    # Quiz failure signals
    if not quiz_df.empty and lecture_id in question_map.quiz:
        quiz_signals = extract_assessment_signals(
            quiz_df, question_map.quiz[lecture_id], "quiz_failure"
        )
        all_signals.extend(quiz_signals)

    # Eval failure signals
    if not eval_df.empty and lecture_id in question_map.evaluation:
        eval_signals = extract_assessment_signals(
            eval_df, question_map.evaluation[lecture_id], "eval_failure"
        )
        all_signals.extend(eval_signals)

    # In-class question signals (if output.txt provided)
    if output_txt_path:
        output_data = parse_output_txt(output_txt_path)
        interactions_df = output_data.get("interactions")
        if interactions_df is not None:
            # Get lecture name from first signal or queries
            lecture_name = queries_df["name"].iloc[0] if not queries_df.empty else "Unknown"
            inclass_signals = extract_inclass_question_signals(
                interactions_df, lecture_id, lecture_name
            )
            all_signals.extend(inclass_signals)

    total_raw = len(all_signals)

    # Remove noise
    all_signals = remove_noise_signals(all_signals)
    total_after_noise = len(all_signals)

    # Deduplicate
    all_signals = deduplicate_signals(all_signals)
    total_after_dedup = len(all_signals)

    # Convert to DataFrame for easier analysis
    signals_df = pd.DataFrame([
        {
            "signal_type": s.signal_type,
            "signal_text": s.signal_text,
            "lecture_id": s.lecture_id,
            "lecture_name": s.lecture_name,
            "student_id": s.student_id,
            "question_number": s.question_number,
            "timestamp": s.timestamp,
        }
        for s in all_signals
    ])

    # Compute metadata
    signal_type_counts = signals_df["signal_type"].value_counts().to_dict()
    unique_query_students = signals_df[
        signals_df["signal_type"] == "query"
    ]["student_id"].nunique()
    unique_assessment_students = signals_df[
        signals_df["signal_type"].isin(["eval_failure", "quiz_failure"])
    ]["student_id"].nunique()

    return {
        "signals": all_signals,
        "signals_df": signals_df,
        "question_map": question_map,
        "metadata": {
            "total_signals_raw": total_raw,
            "total_signals_after_noise_removal": total_after_noise,
            "total_signals_after_dedup": total_after_dedup,
            "signal_type_counts": signal_type_counts,
            "unique_query_students": unique_query_students,
            "unique_assessment_students": unique_assessment_students,
            "student_linking_available": False,  # No user_id→email mapping
        }
    }


# =========================================================
# Example usage
# =========================================================

if __name__ == "__main__":
    # Example: process a single lecture
    result = collect_clean_signals(
        queries_csv_path="/home/roy/Downloads/attachments/queries.csv",
        quiz_csv_path="/home/roy/Downloads/attachments/quiz.csv",
        eval_csv_path="/home/roy/Downloads/attachments/eval.csv",
        correct_csv_path="/home/roy/Downloads/attachments/correct.csv",
        output_txt_path="/home/roy/Downloads/attachments/output.txt",
        lecture_id="f867f9a3-3bab-41b3-9765-8a091544d13e",  # Example lecture ID
    )

    print("=== Layer 0 Results ===")
    print(f"Total signals (raw): {result['metadata']['total_signals_raw']}")
    print(f"After noise removal: {result['metadata']['total_signals_after_noise_removal']}")
    print(f"After deduplication: {result['metadata']['total_signals_after_dedup']}")
    print(f"\nSignal type breakdown:")
    for signal_type, count in result['metadata']['signal_type_counts'].items():
        print(f"  {signal_type}: {count}")
    print(f"\nUnique query students: {result['metadata']['unique_query_students']}")
    print(f"Unique assessment students: {result['metadata']['unique_assessment_students']}")
    print(f"\nStudent linking available: {result['metadata']['student_linking_available']}")

    print("\n=== Sample signals ===")
    print(result["signals_df"].head(10))