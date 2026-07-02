"""Generic, reusable exam-prep runner (project-level, version-controlled).

Point it at a folder of raw course exports; it discovers the four inputs by
filename pattern (override any with an explicit flag), assembles the trimmed
``course_data``, calls the model, and writes results under ``<out>/<course>/``:

    prep_questions.json     rich output (blueprint, allocation, tiers, feedback,
                            rationale, coverage_summary) — for review/debugging
    quiz.json / eval.json   thin platform-upload files (asset_creation schema):
                            {"questions": [{"question", "explanation",
                             "answers": [{"choice", "correct": "true"?}]}]}

Discovered inputs (in ``--data-dir``):
    *summaries*concepts*.csv   long_summary + concept labels (coverage)
    *questions_report*.csv      existing per-class question bank (dedup)
    *eval_detailed*.csv         per-eval pct_correct + answer distribution
    *dashboard*.md              teacher course dashboard (weak-topics signal)

Usage:
    python -m teacher_side.exam_prep.run_prep \
        --course "מבוא להנדסת חומרים" --data-dir /path/to/exports
    python -m teacher_side.exam_prep.run_prep --course X --data-dir DIR --dry-run
    python -m teacher_side.exam_prep.run_prep --course X --data-dir DIR \
        --n-quiz 30 --n-eval 20 --language English

Course-specific adapters (e.g. azrieli/prep/run_prep.py) just call :func:`run`
with that course's name + data directory, mirroring the learning_dashboard
runner/adapter split.
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import yaml

from teacher_side.exam_prep.prep_inputs import build_course_data_from_files
from teacher_side.exam_prep.prep_prompt import DEFAULTS
from teacher_side.exam_prep.prep_generator import (
    ExamPrepGenerator,
    validate_prep,
    to_platform_format,
)

# Defaults come from prep_prompt.yaml (one source of truth); constants are the
# fallback. A real Anthropic model — repo config.yaml points at a free
# OpenRouter model, and ExamPrepGenerator subclasses AnthropicProxy.
DEFAULT_MODEL = DEFAULTS.get("model", "claude-sonnet-4-5-20250929")
# Big enough for a full course-wide set (e.g. 35 Hebrew questions); the
# generator streams, so this can exceed the SDK's non-streaming ceiling.
DEFAULT_MAX_TOKENS = DEFAULTS.get("max_tokens", 40000)
DEFAULT_N_QUIZ = DEFAULTS.get("n_quiz", 20)
DEFAULT_N_EVAL = DEFAULTS.get("n_eval", 15)

# Input discovery: ordered glob patterns, first match wins.
_PATTERNS = {
    "summaries": ["*summaries*concepts*.csv", "*summaries*.csv"],
    "qbank": ["*questions_report*.csv", "*question*bank*.csv"],
    "eval_detail": ["*eval_detailed*.csv", "*eval*detail*.csv"],
    "dashboard": ["*dashboard*.md", "course_dashboard.md"],
}


def _discover(data_dir: Path, kind: str) -> Optional[Path]:
    """First file in ``data_dir`` matching ``kind``'s patterns, else None."""
    for pat in _PATTERNS[kind]:
        hits = sorted(data_dir.glob(pat))
        if hits:
            return hits[0]
    return None


def run(
    course: str,
    data_dir,
    out_dir=None,
    *,
    summaries=None,
    qbank=None,
    eval_detail=None,
    dashboard=None,
    language: str = "Hebrew",
    n_quiz: int = 20,
    n_eval: int = 15,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    dry_run: bool = False,
    discover: bool = True,
) -> Optional[Path]:
    """Generate exam-prep material for one course. Returns the output dir.

    File args (summaries/qbank/eval_detail/dashboard) override auto-discovery.
    With ``discover=True`` (single-course folder) any input left None is filled
    by a pattern search in ``data_dir``; set ``discover=False`` for a SHARED
    multi-course folder, where a None input means "absent" (no glob fallback,
    which would otherwise grab an unrelated course's file). ``out_dir`` defaults
    to ``<data_dir>/output``; artifacts land under ``<out_dir>/<course>/``.
    """
    data_dir = Path(data_dir)
    out_root = Path(out_dir) if out_dir else data_dir / "output"
    course_out = out_root / course.replace(" ", "_")
    course_out.mkdir(parents=True, exist_ok=True)

    def _pick(explicit, kind):
        if explicit:
            return Path(explicit)
        return _discover(data_dir, kind) if discover else None

    summaries = _pick(summaries, "summaries")
    qbank = _pick(qbank, "qbank")
    eval_detail = _pick(eval_detail, "eval_detail")
    dashboard = _pick(dashboard, "dashboard")

    if not summaries or not summaries.exists():
        raise FileNotFoundError(f"summaries+concepts CSV not found in {data_dir}")
    if not qbank or not qbank.exists():
        raise FileNotFoundError(f"questions_report CSV not found in {data_dir}")

    print(f"Stripping inputs for: {course}")
    print(f"  summaries : {summaries.name}")
    print(f"  qbank     : {qbank.name}")
    print(f"  eval_detail: {eval_detail.name if eval_detail else '(none)'}")
    print(f"  dashboard : {dashboard.name if dashboard else '(none)'}")

    course_data = build_course_data_from_files(
        course_name=course,
        summaries_concepts_csv=summaries,
        questions_report_csv=qbank,
        course_dashboard_md=dashboard if dashboard and dashboard.exists() else None,
        eval_detailed_csv=eval_detail if eval_detail and eval_detail.exists() else None,
    )
    approx_tokens = len(course_data) // 4
    print(f"  course_data: {len(course_data):,} chars (~{approx_tokens:,} tokens)")

    if dry_run:
        dump = course_out / "course_data_preview.txt"
        dump.write_text(course_data, encoding="utf-8")
        print(f"  wrote preview -> {dump}")
        print("Dry run complete (no API call).")
        return course_out

    # Build a config whose llm block targets a real Anthropic model.
    config = copy.deepcopy(yaml.safe_load(open(REPO / "config.yaml")))
    config.setdefault("llm", {})
    config["llm"]["model"] = model
    config["llm"]["max_tokens"] = max_tokens

    print(f"Generating {n_quiz} quiz + {n_eval} eval questions "
          f"in {language} with {model} ...")
    t0 = time.time()
    gen = ExamPrepGenerator(
        config=config,
        course_data=course_data,
        language=language,
        n_quiz=n_quiz,
        n_eval=n_eval,
    )
    data = gen.generate()
    print(f"  model returned in {time.time() - t0:.1f}s")

    problems = validate_prep(data, n_quiz, n_eval)
    rich = course_out / "prep_questions.json"
    rich.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote -> {rich}")

    # Thin platform-upload files (asset_creation schema: question/explanation/answers).
    for name, key in (("quiz", "quiz_questions"), ("eval", "evaluation_questions")):
        platform = to_platform_format(data.get(key, []))
        pf = course_out / f"{name}.json"
        pf.write_text(json.dumps(platform, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote -> {pf}  ({len(platform['questions'])} questions)")

    if problems:
        print(f"  ⚠ {len(problems)} validation issue(s):")
        for p in problems:
            print(f"     - {p}")
    else:
        print("  ✓ output validated clean")
    return course_out


def parse_args():
    p = argparse.ArgumentParser(description="Generate course-wide exam-prep material.")
    p.add_argument("--course", required=True, help="course display name")
    p.add_argument("--data-dir", required=True, help="folder holding the raw course exports")
    p.add_argument("--out", default=None, help="output root (default: <data-dir>/output)")
    p.add_argument("--summaries", default=None, help="override: summaries+concepts CSV")
    p.add_argument("--qbank", default=None, help="override: questions_report CSV")
    p.add_argument("--eval-detail", default=None, help="override: eval_detailed_results CSV")
    p.add_argument("--dashboard", default=None, help="override: course dashboard .md")
    p.add_argument("--language", default="Hebrew", help="output language (default: Hebrew)")
    p.add_argument("--n-quiz", type=int, default=DEFAULT_N_QUIZ, help="number of quiz questions")
    p.add_argument("--n-eval", type=int, default=DEFAULT_N_EVAL, help="number of evaluation questions")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model name")
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help="max response tokens")
    p.add_argument("--dry-run", action="store_true",
                   help="assemble course_data and report size; do not call the API")
    return p.parse_args()


def main():
    a = parse_args()
    run(
        course=a.course,
        data_dir=a.data_dir,
        out_dir=a.out,
        summaries=a.summaries,
        qbank=a.qbank,
        eval_detail=a.eval_detail,
        dashboard=a.dashboard,
        language=a.language,
        n_quiz=a.n_quiz,
        n_eval=a.n_eval,
        model=a.model,
        max_tokens=a.max_tokens,
        dry_run=a.dry_run,
    )


if __name__ == "__main__":
    main()
