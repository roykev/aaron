from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


# =========================
# Configuration / constants
# =========================

LANG_LABELS = {
    "en": {
        "student_id": "student_id",
        "lecture": "lecture",
        "question": "question",
        "source": "source",
        "completion_rate": "completion_rate",
        "accuracy": "accuracy",
        "grade": "grade",
        "overall_accuracy": "overall_accuracy",
        "min_score": "min_score",
        "max_score": "max_score",
        "success_rate": "success_rate",
        "eval_avg": "eval_avg",
        "quiz_avg": "quiz_avg",
        "combined_score": "combined_score",
        "gap_quiz_minus_eval": "gap (quiz - eval)",
    },
    "he": {
        "student_id": "מזהה_סטודנט",
        "lecture": "שיעור",
        "question": "שאלה",
        "source": "סוג",
        "completion_rate": "שיעור_השלמה",
        "accuracy": "דיוק",
        "grade": "ציון",
        "overall_accuracy": "דיוק_כולל",
        "min_score": "ציון_מינימלי",
        "max_score": "ציון_מקסימלי",
        "success_rate": "אחוז_הצלחה",
        "eval_avg": "ממוצע_eval",
        "quiz_avg": "ממוצע_quiz",
        "combined_score": "ציון_משולב",
        "gap_quiz_minus_eval": "פער_קויז_מינוס_איבלואציה",
    },
}


# =========================
# Data structures
# =========================

@dataclass
class CourseBankQuestion:
    lecture_id: str
    lecture_name: str
    source: str           # "quiz" or "evaluation"
    question_index: int
    question_text: str


# =========================
# Low-level helpers
# =========================

def safe_json_loads(value: Any) -> Any:
    """
    Load JSON robustly when the input may already be a dict/list or a JSON string.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return json.loads(value)
    raise TypeError(f"Unsupported JSON value type: {type(value)}")


def normalize_text(text: Any) -> str:
    """
    Normalize question text for matching.
    """
    if text is None:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def to_rate(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def to_percent_score(success_rate: Optional[float]) -> Optional[float]:
    if success_rate is None:
        return None
    return round(success_rate * 100, 2)


def weighted_combined_score(
    eval_avg: Optional[float],
    quiz_avg: Optional[float],
    eval_weight: float = 0.7,
    quiz_weight: float = 0.3,
) -> Optional[float]:
    """
    Weighted average with graceful degradation if one side is missing.
    """
    available: List[Tuple[float, float]] = []
    if eval_avg is not None and not pd.isna(eval_avg):
        available.append((eval_avg, eval_weight))
    if quiz_avg is not None and not pd.isna(quiz_avg):
        available.append((quiz_avg, quiz_weight))

    if not available:
        return None

    total_weight = sum(w for _, w in available)
    return round(sum(v * w for v, w in available) / total_weight, 2)


def apply_language_to_columns(df: pd.DataFrame, output_language: str) -> pd.DataFrame:
    """
    Rename standard columns according to output language.
    """
    labels = LANG_LABELS.get(output_language, LANG_LABELS["en"])
    rename_map = {col: labels[col] for col in df.columns if col in labels}
    return df.rename(columns=rename_map)


# =========================
# Course-bank parsing
# =========================

def load_course_bank_from_json(json_path: str | Path) -> pd.DataFrame:
    """
    Load the course question bank JSON.
    Expected structure: a concatenated JSON objects file or a standard JSON array/file.
    """
    text = Path(json_path).read_text(encoding="utf-8").strip()

    # Try normal JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = [data]
        return pd.DataFrame(data)
    except json.JSONDecodeError:
        pass

    # Fallback: concatenated JSON objects
    decoder = json.JSONDecoder()
    idx = 0
    objects = []
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, next_idx = decoder.raw_decode(text, idx)
        objects.append(obj)
        idx = next_idx

    return pd.DataFrame(objects)


def extract_course_bank_questions(course_bank_df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten quiz/evaluation questions into one normalized table.
    """
    rows: List[Dict[str, Any]] = []

    for _, row in course_bank_df.iterrows():
        lecture_id = str(row.get("lecture_id", "")).strip()
        lecture_name = str(row.get("name", "")).strip()

        for source in ("quiz", "evaluation"):
            blob = safe_json_loads(row.get(source))
            questions = (blob or {}).get("questions", []) if isinstance(blob, dict) else []

            for question_index, q in enumerate(questions, start=1):
                rows.append(
                    {
                        "lecture_id": lecture_id,
                        "lecture": lecture_name,
                        "source": source,
                        "question_index": question_index,
                        "question": normalize_text(q.get("question")),
                    }
                )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(
            columns=["lecture_id", "lecture", "source", "question_index", "question"]
        )

    return df


# =========================
# Results loading / normalization
# =========================

def load_excel_sheets(xlsx_path: str | Path) -> Dict[str, pd.DataFrame]:
    """
    Load all sheets from an Excel workbook.
    """
    return pd.read_excel(xlsx_path, sheet_name=None)


def guess_results_sheet(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Choose the most likely results sheet.
    You may later replace this with an explicit sheet name parameter.
    """
    # Prefer a sheet containing both "quiz" and "eval" in the name
    priorities = ["quiz_eval", "quiz+eval", "evaluation", "eval", "results"]
    lower_map = {name.lower(): name for name in sheets.keys()}

    for key in priorities:
        for lower_name, original_name in lower_map.items():
            if key in lower_name:
                return sheets[original_name]

    # Fallback: first sheet
    first_sheet_name = next(iter(sheets))
    return sheets[first_sheet_name]


def normalize_results_columns(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names to a standard internal schema.
    This function is intentionally heuristic and should be adapted once your file structure is fixed.
    """
    df = results_df.copy()
    original_cols = list(df.columns)
    normalized = {c: c.strip().lower().replace(" ", "_") for c in original_cols}
    df = df.rename(columns=normalized)

    # Common aliases
    aliases = {
        "student": "student_id",
        "student_name": "student_id",
        "user_id": "student_id",
        "user": "student_id",
        "lecture_name": "lecture",
        "lesson": "lecture",
        "class": "lecture",
        "type": "source",
        "kind": "source",
        "question_text": "question",
        "score_percent": "score",
        "grade_percent": "score",
        "is_correct": "correct",
        "answered_correctly": "correct",
    }

    for old, new in aliases.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    return df


def normalize_source_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize source values to exactly 'quiz' or 'evaluation' where possible.
    """
    if "source" not in df.columns:
        return df

    def _norm(v: Any) -> Any:
        if pd.isna(v):
            return v
        s = str(v).strip().lower()
        if s in {"quiz", "practice"}:
            return "quiz"
        if s in {"evaluation", "eval", "exam"}:
            return "evaluation"
        return s

    df = df.copy()
    df["source"] = df["source"].map(_norm)
    return df


def coerce_result_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce expected numeric / boolean fields.
    """
    out = df.copy()

    if "question" in out.columns:
        out["question"] = out["question"].map(normalize_text)

    if "correct" in out.columns:
        def _to_bool(v: Any) -> Optional[bool]:
            if pd.isna(v):
                return None
            if isinstance(v, bool):
                return v
            s = str(v).strip().lower()
            if s in {"1", "true", "yes", "y"}:
                return True
            if s in {"0", "false", "no", "n"}:
                return False
            return None
        out["correct"] = out["correct"].map(_to_bool)

    if "score" in out.columns:
        out["score"] = pd.to_numeric(out["score"], errors="coerce")

    return out


# =========================
# Matching / enrichment
# =========================

def enrich_results_with_course_bank(
    results_df: pd.DataFrame,
    course_questions_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Match result rows to the course bank by lecture + source + question text.
    """
    df = results_df.copy()

    required = {"lecture", "source", "question"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Results file missing required columns for matching: {sorted(missing)}")

    bank = course_questions_df.copy()

    merged = df.merge(
        bank,
        how="left",
        on=["lecture", "source", "question"],
        suffixes=("", "_bank"),
    )
    return merged


# =========================
# Student metrics
# =========================

def build_student_performance_by_class(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 1:
    Per student, per lecture, per source.
    completion_rate here = attempted questions / available questions in that lecture+source
    accuracy = correct / attempts
    grade = accuracy * 100
    """
    required = {"student_id", "lecture", "source", "question_index", "correct"}
    missing = required - set(results_df.columns)
    if missing:
        raise ValueError(f"Missing required columns for student-by-class table: {sorted(missing)}")

    df = results_df.copy()

    # available questions per lecture + source
    available = (
        df[["lecture", "source", "question_index"]]
        .dropna(subset=["question_index"])
        .drop_duplicates()
        .groupby(["lecture", "source"], as_index=False)
        .agg(available_questions=("question_index", "nunique"))
    )

    attempted = (
        df.dropna(subset=["student_id", "lecture", "source"])
        .groupby(["student_id", "lecture", "source"], as_index=False)
        .agg(
            attempted_questions=("question_index", "nunique"),
            correct_answers=("correct", lambda s: sum(x is True for x in s)),
            total_answered=("correct", lambda s: sum(x is not None for x in s)),
        )
    )

    out = attempted.merge(available, how="left", on=["lecture", "source"])
    out["completion_rate"] = out.apply(
        lambda r: to_rate(r["attempted_questions"], r["available_questions"]), axis=1
    )
    out["accuracy"] = out.apply(
        lambda r: to_rate(r["correct_answers"], r["total_answered"]), axis=1
    )
    out["grade"] = out["accuracy"].map(to_percent_score)

    return out[
        [
            "student_id",
            "lecture",
            "source",
            "completion_rate",
            "accuracy",
            "grade",
        ]
    ].sort_values(["lecture", "source", "student_id"]).reset_index(drop=True)


def build_student_overall_course_performance(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2:
    Only evaluation, unless you later decide otherwise.
    completion_rate = attempted evaluation lecture-sources / total evaluation lecture-sources
    overall_accuracy = total correct / total answered
    min_score / max_score = across evaluation lecture grades
    """
    required = {"student_id", "lecture", "source", "question_index", "correct"}
    missing = required - set(results_df.columns)
    if missing:
        raise ValueError(f"Missing required columns for overall student table: {sorted(missing)}")

    df = results_df.copy()
    df = df[df["source"] == "evaluation"].copy()

    per_class = build_student_performance_by_class(df)

    total_eval_lectures = (
        df[["lecture", "source"]].drop_duplicates().shape[0]
    )

    overall = (
        per_class.groupby("student_id", as_index=False)
        .agg(
            completed_lecture_units=("lecture", "count"),
            total_correct=("accuracy", lambda s: None),  # placeholder
            overall_accuracy=("accuracy", lambda s: None),  # placeholder
            min_score=("grade", "min"),
            max_score=("grade", "max"),
        )
    )

    # More exact overall accuracy from raw rows
    raw = (
        df.groupby("student_id", as_index=False)
        .agg(
            correct_answers=("correct", lambda s: sum(x is True for x in s)),
            total_answered=("correct", lambda s: sum(x is not None for x in s)),
        )
    )

    overall = overall.drop(columns=["total_correct", "overall_accuracy"]).merge(raw, on="student_id", how="left")
    overall["completion_rate"] = overall["completed_lecture_units"].map(
        lambda x: to_rate(x, total_eval_lectures)
    )
    overall["overall_accuracy"] = overall.apply(
        lambda r: to_rate(r["correct_answers"], r["total_answered"]), axis=1
    )

    return overall[
        ["student_id", "completion_rate", "overall_accuracy", "min_score", "max_score"]
    ].sort_values("student_id").reset_index(drop=True)


# =========================
# Question difficulty
# =========================

def build_question_level_stats(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate question stats across students.
    completion_rate = unique students who attempted / total students in relevant population
    success_rate = correct attempts / total attempts
    """
    required = {"student_id", "lecture", "source", "question", "correct"}
    missing = required - set(results_df.columns)
    if missing:
        raise ValueError(f"Missing required columns for question stats: {sorted(missing)}")

    df = results_df.copy()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "lecture", "source", "question",
                "attempting_students", "total_students",
                "completion_rate", "correct_answers", "attempts", "success_rate"
            ]
        )

    total_students = df["student_id"].dropna().nunique()

    out = (
        df.groupby(["lecture", "source", "question"], as_index=False)
        .agg(
            attempting_students=("student_id", "nunique"),
            correct_answers=("correct", lambda s: sum(x is True for x in s)),
            attempts=("correct", lambda s: sum(x is not None for x in s)),
        )
    )
    out["total_students"] = total_students
    out["completion_rate"] = out.apply(
        lambda r: to_rate(r["attempting_students"], r["total_students"]), axis=1
    )
    out["success_rate"] = out.apply(
        lambda r: to_rate(r["correct_answers"], r["attempts"]), axis=1
    )
    out["difficulty_score"] = 1 - out["success_rate"]

    return out.sort_values(
        ["lecture", "difficulty_score", "completion_rate"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_difficult_questions_by_lesson(
    results_df: pd.DataFrame,
    top_n: int = 3,
) -> Dict[str, pd.DataFrame]:
    """
    Table 3:
    Return one table per lecture, with the hardest quiz/evaluation questions together.
    """
    stats = build_question_level_stats(results_df)
    per_lesson: Dict[str, pd.DataFrame] = {}

    for lecture, grp in stats.groupby("lecture"):
        table = grp.sort_values(
            ["difficulty_score", "completion_rate"],
            ascending=[False, False],
        ).head(top_n)[
            ["question", "source", "completion_rate", "success_rate"]
        ].reset_index(drop=True)
        per_lesson[lecture] = table

    return per_lesson


def build_difficult_questions_coursewide(
    results_df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Table 4:
    Hardest questions in the entire course.
    """
    stats = build_question_level_stats(results_df)

    out = stats.sort_values(
        ["difficulty_score", "completion_rate"],
        ascending=[False, False],
    ).head(top_n)[
        ["lecture", "question", "source", "completion_rate", "success_rate"]
    ].reset_index(drop=True)

    return out


# =========================
# Lesson difficulty
# =========================

def build_lesson_difficulty_table(
    results_df: pd.DataFrame,
    eval_weight: float = 0.7,
    quiz_weight: float = 0.3,
) -> pd.DataFrame:
    """
    Table 5:
    completion_rate, eval_avg, quiz_avg, combined_score, gap (quiz - eval)
    completion_rate here = students who attempted that lesson in either source / total students
    """
    required = {"student_id", "lecture", "source", "correct"}
    missing = required - set(results_df.columns)
    if missing:
        raise ValueError(f"Missing required columns for lesson difficulty: {sorted(missing)}")

    df = results_df.copy()
    total_students = df["student_id"].dropna().nunique()

    # Completion by lecture regardless of source
    completion = (
        df.groupby("lecture", as_index=False)
        .agg(attempting_students=("student_id", "nunique"))
    )
    completion["completion_rate"] = completion["attempting_students"].map(
        lambda x: to_rate(x, total_students)
    )

    # Accuracy per lecture + source
    perf = (
        df.groupby(["lecture", "source"], as_index=False)
        .agg(
            correct_answers=("correct", lambda s: sum(x is True for x in s)),
            attempts=("correct", lambda s: sum(x is not None for x in s)),
        )
    )
    perf["avg_score"] = perf.apply(
        lambda r: to_percent_score(to_rate(r["correct_answers"], r["attempts"])),
        axis=1,
    )

    eval_df = perf[perf["source"] == "evaluation"][["lecture", "avg_score"]].rename(columns={"avg_score": "eval_avg"})
    quiz_df = perf[perf["source"] == "quiz"][["lecture", "avg_score"]].rename(columns={"avg_score": "quiz_avg"})

    out = completion.merge(eval_df, on="lecture", how="left").merge(quiz_df, on="lecture", how="left")
    out["combined_score"] = out.apply(
        lambda r: weighted_combined_score(
            r.get("eval_avg"),
            r.get("quiz_avg"),
            eval_weight=eval_weight,
            quiz_weight=quiz_weight,
        ),
        axis=1,
    )
    out["gap_quiz_minus_eval"] = out.apply(
        lambda r: None
        if pd.isna(r.get("quiz_avg")) or pd.isna(r.get("eval_avg"))
        else round(r["quiz_avg"] - r["eval_avg"], 2),
        axis=1,
    )

    return out[
        ["lecture", "completion_rate", "eval_avg", "quiz_avg", "combined_score", "gap_quiz_minus_eval"]
    ].sort_values(["combined_score", "completion_rate"], ascending=[True, False]).reset_index(drop=True)


# =========================
# Table rendering split by class
# =========================

def split_table_by_lecture(df: pd.DataFrame, lecture_col: str = "lecture") -> Dict[str, pd.DataFrame]:
    """
    Convert a combined table into a dict of per-lecture tables.
    """
    tables: Dict[str, pd.DataFrame] = {}
    for lecture, grp in df.groupby(lecture_col):
        tables[lecture] = grp.drop(columns=[lecture_col]).reset_index(drop=True)
    return tables


# =========================
# Exports
# =========================

def export_table_dict_to_csvs(
    tables: Dict[str, pd.DataFrame],
    output_dir: str | Path,
    prefix: str,
    output_language: str = "en",
) -> List[Path]:
    """
    Save a dict of DataFrames to separate CSV files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: List[Path] = []
    for lecture, df in tables.items():
        safe_name = re.sub(r"[^\w\-]+", "_", lecture.strip(), flags=re.UNICODE).strip("_")
        out_path = output_dir / f"{prefix}_{safe_name}.csv"
        apply_language_to_columns(df, output_language).to_csv(out_path, index=False, encoding="utf-8-sig")
        paths.append(out_path)

    return paths


def export_single_table_to_csv(
    df: pd.DataFrame,
    output_path: str | Path,
    output_language: str = "en",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    apply_language_to_columns(df, output_language).to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


# =========================
# Orchestration
# =========================

def analyze_course_assessment(
    course_bank_json_path: str | Path,
    results_xlsx_path: str | Path,
    output_language: str = "en",
    top_n_questions_per_lesson: int = 3,
    top_n_questions_course: int = 10,
    eval_weight: float = 0.7,
    quiz_weight: float = 0.3,
) -> Dict[str, Any]:
    """
    Main entry point.
    Returns the internal tables, not exported files.
    """
    # 1) Load course bank
    course_bank_raw = load_course_bank_from_json(course_bank_json_path)
    course_questions = extract_course_bank_questions(course_bank_raw)

    # 2) Load results
    sheets = load_excel_sheets(results_xlsx_path)
    results_raw = guess_results_sheet(sheets)
    results_norm = normalize_results_columns(results_raw)
    results_norm = normalize_source_values(results_norm)
    results_norm = coerce_result_fields(results_norm)

    # 3) Enrich with course-bank question_index where possible
    results_enriched = enrich_results_with_course_bank(results_norm, course_questions)

    # If question_index missing in raw but found in bank, use bank version
    if "question_index_bank" in results_enriched.columns:
        if "question_index" not in results_enriched.columns:
            results_enriched["question_index"] = results_enriched["question_index_bank"]
        else:
            results_enriched["question_index"] = results_enriched["question_index"].fillna(
                results_enriched["question_index_bank"]
            )

    # 4) Build tables
    table1_combined = build_student_performance_by_class(results_enriched)
    table1_per_class = split_table_by_lecture(table1_combined)

    table2 = build_student_overall_course_performance(results_enriched)

    table3_per_class = build_difficult_questions_by_lesson(
        results_enriched,
        top_n=top_n_questions_per_lesson,
    )

    table4 = build_difficult_questions_coursewide(
        results_enriched,
        top_n=top_n_questions_course,
    )

    table5 = build_lesson_difficulty_table(
        results_enriched,
        eval_weight=eval_weight,
        quiz_weight=quiz_weight,
    )

    return {
        "output_language": output_language,
        "course_questions": course_questions,
        "results_enriched": results_enriched,
        "table_1_student_performance_by_class": table1_per_class,
        "table_2_student_overall_course_performance": table2,
        "table_3_difficult_questions_by_class": table3_per_class,
        "table_4_difficult_questions_coursewide": table4,
        "table_5_difficult_lessons": table5,
    }