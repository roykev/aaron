"""The "strip" utility: turn raw course exports into lean prompt input.

One entry point, :func:`build_course_data_from_files`, takes the raw export
paths and returns the trimmed ``course_data`` string ready for the prompt. It
keeps only what the task needs and drops redundant / heavy data:

  KEEP   long_summary + concept labels        (coverage, loyal to class)
  KEEP   teacher course dashboard (markdown)   (weak-topics signal)
  KEEP   question bank + per-eval-question      (dedup + misconception signal)
         pct_correct + answer_distribution
  DROP   short_summary (covered by long), concept timecodes, full teacher
         snapshot reports, raw student queries, student gradebook

All loaders strip a UTF-8 BOM and are tolerant of missing optional files.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from teacher_side.exam_prep.prep_generator import assemble_course_data


def _read_csv(path) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


# --------------------------------------------------------------------------- #
# Coverage: long_summary + concept labels
# --------------------------------------------------------------------------- #
def load_lectures(summaries_concepts_csv) -> List[Dict[str, Any]]:
    """Read summaries+concepts.csv -> [{name, long_summary, concepts:[label]}].

    Drops short_summary (redundant with long) and concept timecodes (irrelevant
    to question writing).
    """
    rows = _read_csv(summaries_concepts_csv)
    lectures = []
    for r in rows:
        concepts = []
        raw = _norm(r.get("concepts"))
        if raw:
            try:
                parsed = json.loads(raw)
                for c in parsed.get("concepts", []):
                    label = _norm(c.get("concept"))
                    if label:
                        concepts.append(label)
            except (json.JSONDecodeError, AttributeError):
                pass
        lectures.append({
            "name": _norm(r.get("name")),
            "long_summary": _norm(r.get("long_summary")),
            "concepts": concepts,
        })
    return lectures


# --------------------------------------------------------------------------- #
# Weak topics: teacher course dashboard markdown
# --------------------------------------------------------------------------- #
def load_weak_topics(course_dashboard_md) -> str:
    p = Path(course_dashboard_md)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# Question bank + per-eval-question student stats
# --------------------------------------------------------------------------- #
def _compute_eval_stats(eval_detailed_csv) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """lecture_name -> question_number(int) -> {pct_correct, distribution}.

    Reads eval_detailed_results.csv, where each row's ``answers`` is a JSON map
    question_number -> {"answers":[chosen 1-based opts], "correct": bool}.
    """
    rows = _read_csv(eval_detailed_csv)
    # lecture -> qnum -> {"total", "correct", "dist": {opt:count}}
    acc: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"total": 0, "correct": 0, "dist": defaultdict(int)})
    )
    for r in rows:
        if _norm(r.get("type")) != "evaluation":
            continue
        lecture = _norm(r.get("name"))
        try:
            answers = json.loads(r.get("answers") or "{}")
        except json.JSONDecodeError:
            continue
        for qnum_str, a in answers.items():
            try:
                qnum = int(qnum_str)
            except ValueError:
                continue
            cell = acc[lecture][qnum]
            cell["total"] += 1
            if a.get("correct"):
                cell["correct"] += 1
            for opt in a.get("answers", []) or []:
                cell["dist"][str(opt)] += 1

    stats: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for lecture, qmap in acc.items():
        stats[lecture] = {}
        for qnum, cell in qmap.items():
            total = cell["total"]
            stats[lecture][qnum] = {
                "pct_correct": (100.0 * cell["correct"] / total) if total else None,
                "answer_distribution": dict(cell["dist"]),
            }
    return stats


def load_question_bank(
    questions_report_csv,
    eval_detailed_csv=None,
) -> List[Dict[str, Any]]:
    """Read the question bank; attach pct_correct + distribution to eval questions.

    Per-lecture evaluation questions are matched to the detailed-results question
    numbers by their order within the bank (1-based, in file order).
    """
    rows = _read_csv(questions_report_csv)
    stats = _compute_eval_stats(eval_detailed_csv) if eval_detailed_csv else {}

    # position of each evaluation question within its lecture (for stats mapping)
    eval_counter: Dict[str, int] = defaultdict(int)
    questions: List[Dict[str, Any]] = []
    for r in rows:
        qtype = _norm(r.get("type"))
        lecture = _norm(r.get("lecture name"))
        q = {
            "type": qtype,
            "lecture": lecture,
            "question": _norm(r.get("question")),
            "options": [
                _norm(r.get("answer1")), _norm(r.get("answer2")),
                _norm(r.get("answer3")), _norm(r.get("answer4")),
            ],
            "correct": _norm(r.get("correct")),
            "pct_correct": None,
            "answer_distribution": None,
        }
        if qtype == "evaluation":
            eval_counter[lecture] += 1
            qnum = eval_counter[lecture]
            lec_stats = stats.get(lecture, {}).get(qnum)
            if lec_stats:
                q["pct_correct"] = lec_stats["pct_correct"]
                q["answer_distribution"] = lec_stats["answer_distribution"]
        questions.append(q)
    return questions


# --------------------------------------------------------------------------- #
# One-call entry point
# --------------------------------------------------------------------------- #
def build_course_data_from_files(
    course_name: str,
    summaries_concepts_csv,
    questions_report_csv,
    course_dashboard_md=None,
    eval_detailed_csv=None,
    extra_sections: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Load, strip, and assemble everything into the prompt ``course_data``.

    Pure deterministic Python — no LLM. ``extra_sections`` (list of
    {"title","body"}) is the forward-compatible hook for new inputs: write a
    plain loader that returns such a section and pass it here, no core changes.
    """
    lectures = load_lectures(summaries_concepts_csv)
    weak = load_weak_topics(course_dashboard_md) if course_dashboard_md else ""
    questions = load_question_bank(questions_report_csv, eval_detailed_csv)
    return assemble_course_data(
        course_name, lectures, weak, questions, extra_sections=extra_sections
    )