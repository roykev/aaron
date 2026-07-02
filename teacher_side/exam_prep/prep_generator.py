"""Course-wide student exam-prep generator.

Generic core: given trimmed course data, call Claude and return a validated
prep question bank (valid JSON). The reusable CLI runner lives alongside this
module (teacher_side/exam_prep/run_prep.py); course-specific adapters (e.g.
azrieli/prep/run_prep.py) just call its run() with a course name + data dir,
mirroring the learning_dashboard runner/adapter split.

Minimal, loyal input (decided with the user):
  * coverage  -> per-lecture long_summary + concept labels
  * weak signal -> the teacher course dashboard (markdown, distilled)
  * dedup + misconception signal -> existing question bank, with per-question
    pct_correct + answer_distribution attached where available
Deliberately excluded as redundant/heavy: full teacher snapshot reports, raw
student queries, the student gradebook.
"""
import json
import re
from typing import Any, Dict, List, Optional

from utils.kimi_utils import AnthropicProxy
from teacher_side.exam_prep import prep_prompt


# --------------------------------------------------------------------------- #
# Input assembly (generic; the runner supplies the parsed structures)
# --------------------------------------------------------------------------- #
def _fmt_distribution(dist: Dict[str, int], correct: str = "") -> str:
    """Render the answer spread, marking the correct option(s) and the strongest
    wrong option (the distractor that actually fooled students)."""
    if not dist:
        return ""
    correct_set = {c.strip() for c in str(correct).split(",") if c.strip()}
    parts = []
    for k, v in sorted(dist.items()):
        tag = "✓" if k in correct_set else ""
        parts.append(f"opt{k}:{v}{tag}")
    rendered = ", ".join(parts)
    # the most-chosen wrong option = the distractor worth emulating
    wrong = {k: v for k, v in dist.items() if k not in correct_set}
    if wrong:
        top = max(wrong, key=wrong.get)
        if wrong[top] > 0:
            rendered += f"  [top distractor: opt{top}]"
    return rendered


# Below this % correct, an existing question counts as one students struggled
# with — flagged inline and surfaced in the "most-missed" digest.
WEAK_THRESHOLD = 60.0


def assemble_course_data(
    course_name: str,
    lectures: List[Dict[str, Any]],
    weak_topics_text: str,
    existing_questions: List[Dict[str, Any]],
    extra_sections: Optional[List[Dict[str, str]]] = None,
    weak_threshold: float = WEAK_THRESHOLD,
) -> str:
    """Build the compact ``course_data`` text block fed to the prompt.

    Args:
        course_name: e.g. "מבוא להנדסת חומרים".
        lectures: [{"name", "long_summary", "concepts": [str, ...]}].
        weak_topics_text: the teacher course-dashboard markdown (or "").
        existing_questions: [{"type", "lecture", "question",
            "options": [a1,a2,a3,a4], "correct",
            "pct_correct": float|None, "answer_distribution": {idx:count}|None}].
        extra_sections: optional extension point — a list of
            {"title", "body"} dicts appended verbatim after the core sections.
            Add future inputs (syllabus, raw queries, prerequisites, etc.) here
            without changing the core signature.
    """
    # Distinct banner so our structural sections don't blur with the markdown
    # headers embedded inside the lecture summaries / dashboard.
    def banner(title: str) -> str:
        bar = "=" * 70
        return f"\n{bar}\n=== {title}\n{bar}"

    out: List[str] = [f"COURSE: {course_name}"]

    # 1) Coverage — long summaries + concept labels
    out.append(banner("SECTION 1 — LECTURE COVERAGE (loyal to what was taught)"))
    for lec in lectures:
        out.append(f"### {lec.get('name', '').strip()}")
        concepts = lec.get("concepts") or []
        if concepts:
            out.append("Concepts: " + "; ".join(concepts))
        summ = (lec.get("long_summary") or "").strip()
        if summ:
            out.append(summ)
        out.append("")

    # 2) Weak topics — distilled teacher dashboard
    if weak_topics_text and weak_topics_text.strip():
        out.append(banner("SECTION 2 — WEAK-TOPICS ANALYSIS (teacher course dashboard)"))
        out.append(weak_topics_text.strip())
        out.append("")

    # 3) Existing question bank — for dedup + per-question difficulty/misconception
    out.append(banner(
        "SECTION 3 — EXISTING PER-CLASS QUESTION BANK "
        "(do NOT duplicate; use stats to target misconceptions)"
    ))

    # 3a) Most-missed digest: the questions students struggled with most, ranked.
    scored = [q for q in existing_questions if q.get("pct_correct") is not None
              and q["pct_correct"] < weak_threshold]
    scored.sort(key=lambda q: q["pct_correct"])
    if scored:
        out.append(
            f"MOST-MISSED EXISTING QUESTIONS (below {weak_threshold:.0f}% correct) — "
            "PRIORITISE these concepts for prep, and reuse their winning distractors:")
        for q in scored:
            wrong = {k: v for k, v in (q.get("answer_distribution") or {}).items()
                     if k not in {c.strip() for c in str(q.get("correct", "")).split(",")}}
            trap = ""
            if wrong:
                top = max(wrong, key=wrong.get)
                idx = int(top) - 1
                opts = q.get("options") or []
                if 0 <= idx < len(opts):
                    trap = f"  ← most picked wrong answer: \"{str(opts[idx]).strip()}\""
            out.append(
                f"  * [{str(q.get('lecture', '')).strip()}] {q['pct_correct']:.0f}% "
                f"correct — {str(q.get('question', '')).strip()}{trap}")
        out.append("")

    # 3b) Full bank.
    for q in existing_questions:
        weak_tag = ""
        if q.get("pct_correct") is not None and q["pct_correct"] < weak_threshold:
            weak_tag = " ⚠STRUGGLED"
        line = (
            f"-{weak_tag} [{q.get('type', '')}/{str(q.get('lecture', '')).strip()}] "
            f"{str(q.get('question', '')).strip()}"
        )
        opts = q.get("options") or []
        if opts:
            opt_str = " | ".join(
                f"{i + 1}) {str(o).strip()}" for i, o in enumerate(opts)
            )
            line += f"  OPTIONS: {opt_str}"
        if q.get("correct") not in (None, ""):
            line += f"  CORRECT: {q['correct']}"
        if q.get("pct_correct") is not None:
            line += f"  pct_correct: {q['pct_correct']:.0f}%"
        dist = _fmt_distribution(q.get("answer_distribution") or {}, q.get("correct", ""))
        if dist:
            line += f"  answer_distribution: {dist}"
        out.append(line)
    out.append("")

    # 4) Extension point — any future inputs, appended verbatim.
    for section in extra_sections or []:
        title = str(section.get("title", "")).strip()
        body = str(section.get("body", "")).strip()
        if not body:
            continue
        out.append(banner(title.upper() if title else "ADDITIONAL INPUT"))
        out.append(body)
        out.append("")

    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #
class ExamPrepGenerator(AnthropicProxy):
    """Generates a course-wide prep quiz + evaluation as validated JSON."""

    def __init__(
        self,
        config: Dict[str, Any],
        course_data: str,
        language: str = "Hebrew",
        n_quiz: int = 20,
        n_eval: int = 15,
        api_key: str = None,
        logger=None,
    ):
        super().__init__(config, api_key, logger)
        self.course_data = course_data
        self.language = language
        self.n_quiz = n_quiz
        self.n_eval = n_eval

    # AnthropicProxy.prepare_prompts() calls these two.
    def compose_system_prompt(self, lan=None):
        self.system_prompt = prep_prompt.compose_system_prompt(
            self.language, self.course_data
        )

    def compose_user_prompt(self, lan=None):
        self.user_prompt = prep_prompt.compose_user_prompt(
            self.language, self.n_quiz, self.n_eval
        )

    def call_api(self) -> str:
        """Stream + accumulate, overriding the parent's non-streaming call.

        A full course-wide set (e.g. 35 Hebrew questions + blueprint + per-question
        feedback/rationale) needs a large max_tokens, which the Anthropic SDK
        refuses to serve non-streaming (its 10-minute guard). Streaming lifts that
        ceiling; get_final_message() returns the same Message the parent parsed,
        so the downstream parse/validate path is unchanged.
        """
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0.1,
            system=self.system_prompt,
            messages=[{"role": "user", "content": self.user_prompt}],
        ) as stream:
            message = stream.get_final_message()
        return message.content[0].text.strip()

    def generate(self) -> Dict[str, Any]:
        """Run the model and return the parsed, validated prep dict."""
        self.prepare_prompts(self.language)
        raw = self.call_api()
        data = parse_prep_json(raw)
        reconcile_buckets(data)
        return data


# --------------------------------------------------------------------------- #
# Parsing + validation
# --------------------------------------------------------------------------- #
def parse_prep_json(text: str) -> Dict[str, Any]:
    """Parse the model output into a dict, tolerating accidental fences/prose."""
    if text is None:
        raise ValueError("Model returned no text")
    s = text.strip()
    # strip ```json ... ``` fences if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, flags=re.S)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # fall back to the outermost {...} span
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise


def reconcile_buckets(data: Dict[str, Any]) -> Dict[str, Any]:
    """Re-sort questions into quiz_questions / evaluation_questions by ``type``.

    The model occasionally dumps the whole set into ``quiz_questions`` and omits
    ``evaluation_questions`` (or vice-versa). Each question still carries its own
    ``type`` ("quiz"/"evaluation") and an id prefix (Q*/E*), so we pool both
    arrays and re-split deterministically. For well-formed output this is a
    no-op. Mutates and returns ``data``.
    """
    pool = list(data.get("quiz_questions") or []) + list(data.get("evaluation_questions") or [])

    def is_eval(q: Dict[str, Any]) -> bool:
        t = str(q.get("type", "")).strip().lower()
        if t in ("evaluation", "eval"):
            return True
        if t == "quiz":
            return False
        return str(q.get("id", "")).strip().upper().startswith("E")

    data["evaluation_questions"] = [q for q in pool if is_eval(q)]
    data["quiz_questions"] = [q for q in pool if not is_eval(q)]
    return data


_REQUIRED_KEYS = (
    "course_blueprint",
    "question_allocation",
    "quiz_questions",
    "evaluation_questions",
    "coverage_summary",
)


def validate_prep(data: Dict[str, Any], n_quiz: int, n_eval: int) -> List[str]:
    """Return a list of human-readable problems ([] means clean)."""
    problems: List[str] = []
    for k in _REQUIRED_KEYS:
        if k not in data:
            problems.append(f"missing top-level key: {k}")

    quiz = data.get("quiz_questions", []) or []
    ev = data.get("evaluation_questions", []) or []
    if len(quiz) != n_quiz:
        problems.append(f"expected {n_quiz} quiz questions, got {len(quiz)}")
    if len(ev) != n_eval:
        problems.append(f"expected {n_eval} evaluation questions, got {len(ev)}")

    valid_tiers = {name for name, _ in prep_prompt.TIERS}
    for label, items in (("quiz", quiz), ("eval", ev)):
        for i, q in enumerate(items):
            qid = q.get("id", f"{label}#{i + 1}")
            for f in ("question", "answer1", "answer2", "answer3", "answer4", "correct"):
                if not q.get(f):
                    problems.append(f"{qid}: missing field '{f}'")
            # correct must be 1-based indices within 1..4
            correct = str(q.get("correct", "")).strip()
            idxs = [c.strip() for c in correct.split(",") if c.strip()]
            if not idxs or any(c not in {"1", "2", "3", "4"} for c in idxs):
                problems.append(f"{qid}: invalid 'correct'={correct!r}")
            if q.get("tier") not in valid_tiers:
                problems.append(f"{qid}: invalid tier={q.get('tier')!r}")

    # tier distribution sanity (warn only if wildly off)
    total = len(quiz) + len(ev)
    if total:
        counts = {name: 0 for name, _ in prep_prompt.TIERS}
        for q in list(quiz) + list(ev):
            if q.get("tier") in counts:
                counts[q["tier"]] += 1
        for name, pct in prep_prompt.TIERS:
            actual = counts[name] / total
            if abs(actual - pct) > 0.15:
                problems.append(
                    f"tier {name}: {actual:.0%} (target {pct:.0%}) — off by >15pts"
                )
    return problems


# --------------------------------------------------------------------------- #
# Platform export — the class quiz/evaluation upload schema
# --------------------------------------------------------------------------- #
def to_platform_format(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert internal questions to the platform asset-creation schema.

    Internal: {"question", "answer1".."answer4", "correct": "2" | "1,3",
               "explanation" (or legacy "feedback"/"rationale"), ...}
    Platform: {"questions": [{"question", "explanation",
                              "answers": [{"choice", "correct": "true"?}]}]}
    Matches the asset_creation `quiz`/`quiz_eval` contract: the 1-based
    ``correct`` index (comma-joined for multi-answer) becomes a
    ``"correct": "true"`` flag on the matching choices; wrong choices omit it.
    The explanation falls back to legacy ``feedback``/``rationale`` keys so
    output produced before the schema change still converts.
    """
    questions: List[Dict[str, Any]] = []
    for q in items:
        correct = {c.strip() for c in str(q.get("correct", "")).split(",") if c.strip()}
        answers: List[Dict[str, str]] = []
        for i in range(1, 5):
            choice = q.get(f"answer{i}")
            if choice in (None, ""):
                continue
            ans = {"choice": str(choice).strip()}
            if str(i) in correct:
                ans["correct"] = "true"
            answers.append(ans)
        explanation = (q.get("explanation") or q.get("feedback")
                       or q.get("rationale") or "")
        questions.append({
            "question": str(q.get("question", "")).strip(),
            "explanation": str(explanation).strip(),
            "answers": answers,
        })
    return {"questions": questions}