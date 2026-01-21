#!/usr/bin/env python3
"""
quiz_report.py

Schema expected:
{
  "questions": [
    {
      "question": "....",
      "answers": [
        {"choice": "...", "correct": "true"},
        {"choice": "..."}
      ]
    }
  ]
}

Usage:
  python quiz_report.py --input quiz.json --out_html quiz_report.html
  python quiz_report.py --input quiz.json --out_html quiz_report.html --out_json quiz.cleaned.json
  python quiz_report.py --input quiz.json --out_html quiz_report.html --single_correct_only
"""

from __future__ import annotations

import argparse
import json
import html
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Models / helpers
# ----------------------------

@dataclass
class Issue:
    q_idx: int
    a_idx: Optional[int]  # None = question-level
    field: str
    message: str
    value: Optional[str] = None

    def anchor(self) -> str:
        if self.a_idx is None:
            return f"q{self.q_idx}"
        return f"q{self.q_idx}a{self.a_idx}"


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Root must be an object")
    if "questions" not in data or not isinstance(data["questions"], list):
        raise ValueError('Missing "questions" array')

    out = {"questions": []}
    for q in data["questions"]:
        if not isinstance(q, dict):
            q = {}
        qq = q.get("question", "")
        if qq is None:
            qq = ""
        qq = str(qq)

        answers = q.get("answers", [])
        if not isinstance(answers, list):
            answers = []

        norm_answers = []
        for a in answers:
            if not isinstance(a, dict):
                a = {}
            choice = a.get("choice", "")
            if choice is None:
                choice = ""
            choice = str(choice)

            # Keep "correct" only if exactly the string "true"
            corr = a.get("correct", None)
            ans_obj = {"choice": choice}
            if corr == "true":
                ans_obj["correct"] = "true"
            norm_answers.append(ans_obj)

        out["questions"].append({"question": qq, "answers": norm_answers})
    return out


def analyze_and_clean(
    data: Dict[str, Any],
    *,
    single_correct_only: bool = False,
    trim_text: bool = True,
) -> Tuple[Dict[str, Any], List[Issue]]:
    issues: List[Issue] = []
    cleaned = normalize_schema(data)

    for qi, q in enumerate(cleaned["questions"]):
        qtext = q.get("question", "")
        if trim_text:
            qtext = qtext.strip()
            q["question"] = qtext

        if not qtext:
            issues.append(Issue(qi, None, "question", "Empty question text"))

        answers = q.get("answers", [])
        if len(answers) < 2:
            issues.append(Issue(qi, None, "answers", "Must have at least 2 answers", value=str(len(answers))))

        correct_idxs = [ai for ai, a in enumerate(answers) if a.get("correct") == "true"]
        if len(correct_idxs) == 0:
            issues.append(Issue(qi, None, "correct", "No correct answer marked"))
        if single_correct_only and len(correct_idxs) > 1:
            issues.append(Issue(qi, None, "correct", "Multiple correct answers (single-correct mode)", value=str(len(correct_idxs))))

        for ai, a in enumerate(answers):
            choice = a.get("choice", "")
            if trim_text:
                choice = choice.strip()
                a["choice"] = choice
            if not choice:
                issues.append(Issue(qi, ai, "choice", "Empty answer text"))

            # Ensure no other correct values exist (already normalized), but keep safe:
            if "correct" in a and a["correct"] != "true":
                a.pop("correct", None)

    return cleaned, issues


# ----------------------------
# HTML report
# ----------------------------

def render_html_report(cleaned: Dict[str, Any], issues: List[Issue], *, input_name: str) -> str:
    questions = cleaned.get("questions", [])
    total_q = len(questions)
    total_a = sum(len(q.get("answers", [])) for q in questions)
    issue_count = len(issues)

    issues_by_anchor: Dict[str, List[Issue]] = {}
    for it in issues:
        issues_by_anchor.setdefault(it.anchor(), []).append(it)

    css = """
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#E6ECF9; margin:0; color:#1f2a44; }
    .wrap { max-width:1100px; margin:18px auto; padding:0 14px 22px; }
    .panel { background:#fff; border-radius:14px; box-shadow:0 10px 30px rgba(20,35,80,.08); border:1px solid rgba(46,107,207,.10); overflow:hidden; }
    .top { padding:14px 16px; border-bottom:1px solid rgba(46,107,207,.10); display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; }
    .title h1 { margin:0; font-size:16px; font-weight:800; }
    .muted { color:#6c7a96; font-size:12px; }
    .content { padding:14px 16px 18px; }
    .bad { color:#b42318; }
    .badge { display:inline-block; font-size:11px; padding:3px 8px; border-radius:999px; background:rgba(46,107,207,.12); color:#2E6BCF; border:1px solid rgba(46,107,207,.16); margin-inline-start:6px; }
    .badge.badge-bad { background:rgba(180,35,24,.08); color:#b42318; border-color:rgba(180,35,24,.18); }
    .card { border:1px solid #D4E9C5; border-radius:14px; background:#fff; padding:12px; margin-bottom:12px; }
    .row { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; flex-wrap:wrap; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; padding:8px; border-bottom:1px solid rgba(46,107,207,.08); vertical-align:top; }
    th { color:#6c7a96; font-weight:700; font-size:12px; }
    code { background:rgba(46,107,207,.06); padding:1px 6px; border-radius:8px; }
    a { color:#2E6BCF; text-decoration:none; }
    a:hover { text-decoration:underline; }
    .issue { padding:8px; border:1px solid rgba(180,35,24,.18); background:rgba(180,35,24,.08); border-radius:10px; margin-top:8px; }
    .ans-ok { background: rgba(46,107,207,.06); border-radius: 8px; padding: 1px 6px; }
    """

    # Issues table
    issues_rows = []
    for it in issues:
        where = f'<a href="#{it.anchor()}">Q{it.q_idx+1}{"" if it.a_idx is None else f" / A{it.a_idx+1}"}</a>'
        val = f"<code>{esc(it.value)}</code>" if it.value else ""
        issues_rows.append(
            f"<tr>"
            f"<td>{where}</td>"
            f"<td>{esc(it.field)}</td>"
            f"<td class='bad'>{esc(it.message)}</td>"
            f"<td>{val}</td>"
            f"</tr>"
        )

    issues_table_html = (
        "<div class='card'>"
        "<div class='row'><div><b>Issues</b>"
        f"<span class='badge badge-bad'>{issue_count}</span></div>"
        "<div class='muted'>Click to jump to the question/answer</div></div>"
        "<div style='margin-top:10px; overflow:auto;'>"
        "<table>"
        "<thead><tr><th>Where</th><th>Field</th><th>Message</th><th>Value</th></tr></thead>"
        "<tbody>"
        + ("".join(issues_rows) if issues_rows else "<tr><td colspan='4' class='muted'>No issues 🎉</td></tr>")
        + "</tbody></table></div></div>"
    )

    # Quiz view
    q_cards = []
    for qi, q in enumerate(questions):
        qtext = q.get("question", "")
        answers = q.get("answers", [])
        correct_idxs = [ai for ai, a in enumerate(answers) if a.get("correct") == "true"]

        q_anchor = f"q{qi}"
        q_issue_block = ""
        if q_anchor in issues_by_anchor:
            msgs = "<br/>".join(f"• <b>{esc(i.field)}</b>: {esc(i.message)}" for i in issues_by_anchor[q_anchor])
            q_issue_block = f"<div class='issue'><b class='bad'>Question issues:</b><br/>{msgs}</div>"

        ans_rows = []
        for ai, a in enumerate(answers):
            a_anchor = f"q{qi}a{ai}"
            choice = a.get("choice", "")
            is_correct = a.get("correct") == "true"
            a_issue_block = ""
            if a_anchor in issues_by_anchor:
                msgs = "<br/>".join(f"• <b>{esc(i.field)}</b>: {esc(i.message)}" for i in issues_by_anchor[a_anchor])
                a_issue_block = f"<div class='issue'><b class='bad'>Answer issues:</b><br/>{msgs}</div>"

            ans_rows.append(
                f"<tr id='{a_anchor}'>"
                f"<td>{ai+1}</td>"
                f"<td>{'✅' if is_correct else ''}</td>"
                f"<td>{esc(choice) or '<span class=\"bad\">(empty)</span>'}</td>"
                f"<td>{a_issue_block or '<span class=\"ans-ok\">OK</span>'}</td>"
                f"</tr>"
            )

        q_cards.append(
            f"<div class='card' id='{q_anchor}'>"
            f"<div class='row'>"
            f"<div><b>Q{qi+1}:</b> {esc(qtext) or '<span class=\"bad\">(empty)</span>'}"
            f"<span class='badge'>{len(answers)} answers</span>"
            f"<span class='badge'>{len(correct_idxs)} correct</span>"
            f"</div>"
            f"<div class='muted'>#{qi+1}</div>"
            f"</div>"
            f"{q_issue_block}"
            f"<div style='margin-top:10px; overflow:auto;'>"
            f"<table>"
            f"<thead><tr><th>#</th><th>Correct</th><th>Choice</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(ans_rows) if ans_rows else '<tr><td colspan=\"4\" class=\"muted\">No answers</td></tr>'}</tbody>"
            f"</table></div>"
            f"</div>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Quiz Report</title>
<style>{css}</style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="top">
        <div class="title">
          <h1>Quiz Report</h1>
          <div class="muted">Input: <code>{esc(input_name)}</code></div>
        </div>
        <div class="muted">
          Questions: <code>{total_q}</code> • Answers: <code>{total_a}</code> • Issues: <code class="{ 'bad' if issue_count else '' }">{issue_count}</code>
        </div>
      </div>
      <div class="content">
        {issues_table_html}
        <div class="card">
          <div class="row">
            <div><b>Quiz</b><span class="badge">{total_q}</span></div>
            <div class="muted">Schema preserves correct as string "true"</div>
          </div>
        </div>
        {''.join(q_cards)}
      </div>
    </div>
  </div>
</body>
</html>
"""
    return html_doc


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to quiz JSON")
    ap.add_argument("--out_html", required=True, help="Path to output HTML report")
    ap.add_argument("--out_json", default=None, help="Optional: write cleaned JSON here")
    ap.add_argument("--single_correct_only", action="store_true",
                    help="If set, flags questions with multiple correct answers as issues")
    ap.add_argument("--no_trim", action="store_true", help="Do not trim whitespace in texts")
    args = ap.parse_args()

    raw = load_json(args.input)
    cleaned, issues = analyze_and_clean(
        raw,
        single_correct_only=args.single_correct_only,
        trim_text=(not args.no_trim),
    )

    report = render_html_report(cleaned, issues, input_name=args.input)

    with open(args.out_html, "w", encoding="utf-8") as f:
        f.write(report)

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"Wrote HTML report: {args.out_html}")
    if args.out_json:
        print(f"Wrote cleaned JSON: {args.out_json}")
    print(f"Questions: {len(cleaned.get('questions', []))}, Issues: {len(issues)}")


if __name__ == "__main__":
    main()
