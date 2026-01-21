#!/usr/bin/env python3
"""
concepts_report.py

Usage:
  python concepts_report.py --input concepts.json --out_html report.html
  python concepts_report.py --input concepts.json --out_html report.html --out_json concepts.cleaned.json
  python concepts_report.py --input concepts.json --out_html report.html --duration 02:24:58
"""

from __future__ import annotations

import argparse
import json
import html
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Time parsing / normalization
# ----------------------------

@dataclass
class TimeParse:
    ok: bool
    secs: Optional[int] = None
    norm: Optional[str] = None
    err: Optional[str] = None
    suggestion: Optional[str] = None


def pad2(n: int) -> str:
    return str(n).zfill(2)


def format_hhmmss(total_secs: int) -> str:
    if total_secs < 0:
        total_secs = 0
    hh = total_secs // 3600
    mm = (total_secs % 3600) // 60
    ss = total_secs % 60
    return f"{pad2(hh)}:{pad2(mm)}:{pad2(ss)}"


def parse_time(s: Any, allow_carry_fix: bool = True) -> TimeParse:
    """
    Accepts "mm:ss" or "hh:mm:ss".
    Returns:
      - ok True with secs & norm if valid
      - ok False with err and optional suggestion
    """
    if not isinstance(s, str):
        return TimeParse(ok=False, err="Time must be a string")
    t = s.strip()
    if not t:
        return TimeParse(ok=False, err="Empty time")

    parts = [p.strip() for p in t.split(":")]
    if len(parts) not in (2, 3):
        return TimeParse(ok=False, err="Invalid format (use mm:ss or hh:mm:ss)")

    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return TimeParse(ok=False, err="Time must contain integers")

    if any(n < 0 for n in nums):
        return TimeParse(ok=False, err="Negative values not allowed")

    if len(nums) == 2:
        hh = 0
        mm, ss = nums
    else:
        hh, mm, ss = nums

    # If mm or ss >= 60: invalid, but can suggest a carry fix
    if mm >= 60 or ss >= 60:
        total = hh * 3600 + mm * 60 + ss
        suggestion = format_hhmmss(total)
        if allow_carry_fix:
            # still mark as invalid for reporting unless you prefer auto-fix; we provide suggestion anyway
            return TimeParse(ok=False, err="Minutes/seconds must be < 60", suggestion=suggestion)
        return TimeParse(ok=False, err="Minutes/seconds must be < 60", suggestion=suggestion)

    total = hh * 3600 + mm * 60 + ss
    return TimeParse(ok=True, secs=total, norm=format_hhmmss(total))


def parse_duration(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    p = parse_time(s, allow_carry_fix=False)
    if not p.ok or p.secs is None:
        raise ValueError(f"Invalid duration '{s}'. Use hh:mm:ss or mm:ss.")
    return p.secs


# ----------------------------
# Validation / normalization
# ----------------------------

@dataclass
class Issue:
    concept_idx: int
    concept_name: str
    seg_idx: Optional[int]  # None = concept-level
    field: str
    message: str
    value: Optional[str] = None
    suggestion: Optional[str] = None

    def anchor(self) -> str:
        if self.seg_idx is None:
            return f"c{self.concept_idx}"
        return f"c{self.concept_idx}s{self.seg_idx}"


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Root must be an object")
    if "concepts" not in data or not isinstance(data["concepts"], list):
        raise ValueError('Missing "concepts" array')

    out = {"concepts": []}
    for c in data["concepts"]:
        if not isinstance(c, dict):
            c = {}
        concept = c.get("concept", "")
        if concept is None:
            concept = ""
        concept = str(concept)

        times = c.get("times", [])
        if not isinstance(times, list):
            times = []
        norm_times = []
        for t in times:
            if not isinstance(t, dict):
                t = {}
            start = t.get("start", "")
            end = t.get("end", "")
            norm_times.append({"start": "" if start is None else str(start),
                               "end": "" if end is None else str(end)})
        out["concepts"].append({"concept": concept, "times": norm_times})
    return out


def analyze_and_clean(
    data: Dict[str, Any],
    *,
    duration_secs: Optional[int] = None,
    auto_fix_carry: bool = False,
) -> Tuple[Dict[str, Any], List[Issue]]:
    """
    Returns (cleaned_data, issues).
    auto_fix_carry: if True, will convert invalid mm/ss>=60 into carried HH:MM:SS.
    """
    issues: List[Issue] = []
    cleaned = normalize_schema(data)

    for ci, c in enumerate(cleaned["concepts"]):
        name = (c.get("concept") or "").strip()
        if not name:
            issues.append(Issue(ci, name, None, "concept", "Empty concept name"))

        # validate segments
        new_times = []
        for si, seg in enumerate(c.get("times", [])):
            start_raw = seg.get("start", "")
            end_raw = seg.get("end", "")

            ps = parse_time(start_raw, allow_carry_fix=True)
            pe = parse_time(end_raw, allow_carry_fix=True)

            # start
            if not ps.ok:
                issues.append(Issue(ci, name, si, "start", ps.err or "Invalid time", start_raw, ps.suggestion))
                if auto_fix_carry and ps.suggestion:
                    seg["start"] = ps.suggestion
                    ps = parse_time(seg["start"], allow_carry_fix=False)

            # end
            if not pe.ok:
                issues.append(Issue(ci, name, si, "end", pe.err or "Invalid time", end_raw, pe.suggestion))
                if auto_fix_carry and pe.suggestion:
                    seg["end"] = pe.suggestion
                    pe = parse_time(seg["end"], allow_carry_fix=False)

            # if both parse ok: normalize
            if ps.ok and pe.ok and ps.secs is not None and pe.secs is not None:
                seg["start"] = ps.norm or seg["start"]
                seg["end"] = pe.norm or seg["end"]

                if ps.secs >= pe.secs:
                    issues.append(Issue(ci, name, si, "range", "Start must be < End", f"{seg['start']}..{seg['end']}"))

                # bounds
                if duration_secs is not None:
                    if ps.secs < 0 or ps.secs > duration_secs:
                        issues.append(Issue(ci, name, si, "start", "Start out of video bounds", seg["start"]))
                    if pe.secs < 0 or pe.secs > duration_secs:
                        issues.append(Issue(ci, name, si, "end", "End out of video bounds", seg["end"]))

                new_times.append(seg)
            else:
                # keep as-is so teacher can see it
                new_times.append(seg)

        c["times"] = new_times

    # Sorting (name, then within each concept by start time if parsable)
    for c in cleaned["concepts"]:
        def seg_key(seg: Dict[str, str]) -> Tuple[int, int]:
            ps = parse_time(seg.get("start", ""), allow_carry_fix=False)
            if ps.ok and ps.secs is not None:
                return (0, ps.secs)
            return (1, 10**12)  # invalid last
        c["times"].sort(key=seg_key)

    cleaned["concepts"].sort(key=lambda c: (c.get("concept","").strip().lower(),))

    return cleaned, issues


# ----------------------------
# HTML report
# ----------------------------

def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def render_html_report(
    cleaned: Dict[str, Any],
    issues: List[Issue],
    *,
    input_name: str,
    duration_secs: Optional[int] = None,
) -> str:
    concepts = cleaned.get("concepts", [])
    total_concepts = len(concepts)
    total_segments = sum(len(c.get("times", [])) for c in concepts)
    issue_count = len(issues)

    duration_str = format_hhmmss(duration_secs) if duration_secs is not None else "N/A"

    # Build per-concept issue map
    issues_by_anchor: Dict[str, List[Issue]] = {}
    for it in issues:
        issues_by_anchor.setdefault(it.anchor(), []).append(it)

    def seg_duration(seg: Dict[str, str]) -> Optional[int]:
        ps = parse_time(seg.get("start",""), allow_carry_fix=False)
        pe = parse_time(seg.get("end",""), allow_carry_fix=False)
        if ps.ok and pe.ok and ps.secs is not None and pe.secs is not None and ps.secs < pe.secs:
            return pe.secs - ps.secs
        return None

    # CSS
    css = f"""
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#E6ECF9; margin:0; color:#1f2a44; }}
    .wrap {{ max-width:1100px; margin:18px auto; padding:0 14px 22px; }}
    .panel {{ background:#fff; border-radius:14px; box-shadow:0 10px 30px rgba(20,35,80,.08); border:1px solid rgba(46,107,207,.10); overflow:hidden; }}
    .top {{ padding:14px 16px; border-bottom:1px solid rgba(46,107,207,.10); display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; }}
    .title h1 {{ margin:0; font-size:16px; font-weight:800; }}
    .muted {{ color:#6c7a96; font-size:12px; }}
    .content {{ padding:14px 16px 18px; }}
    .bad {{ color:#b42318; }}
    .badge {{ display:inline-block; font-size:11px; padding:3px 8px; border-radius:999px; background:rgba(46,107,207,.12); color:#2E6BCF; border:1px solid rgba(46,107,207,.16); margin-inline-start:6px; }}
    .badge.badge-bad {{ background:rgba(180,35,24,.08); color:#b42318; border-color:rgba(180,35,24,.18); }}
    .card {{ border:1px solid #D4E9C5; border-radius:14px; background:#fff; padding:12px; margin-bottom:12px; }}
    .row {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; flex-wrap:wrap; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th, td {{ text-align:left; padding:8px; border-bottom:1px solid rgba(46,107,207,.08); vertical-align:top; }}
    th {{ color:#6c7a96; font-weight:700; font-size:12px; }}
    code {{ background:rgba(46,107,207,.06); padding:1px 6px; border-radius:8px; }}
    a {{ color:#2E6BCF; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .issue {{ padding:8px; border:1px solid rgba(180,35,24,.18); background:rgba(180,35,24,.08); border-radius:10px; margin-top:8px; }}
    """

    # Issues table
    issues_rows = []
    for it in issues:
        suggestion = f"<code>{esc(it.suggestion)}</code>" if it.suggestion else ""
        val = f"<code>{esc(it.value)}</code>" if it.value else ""
        where = f'<a href="#{it.anchor()}">Q{it.concept_idx+1}{"" if it.seg_idx is None else f" / seg {it.seg_idx+1}"}</a>'
        issues_rows.append(
            f"<tr>"
            f"<td>{where}</td>"
            f"<td>{esc(it.concept_name) or '<span class=\"muted\">(empty)</span>'}</td>"
            f"<td>{esc(it.field)}</td>"
            f"<td class='bad'>{esc(it.message)}</td>"
            f"<td>{val}</td>"
            f"<td>{suggestion}</td>"
            f"</tr>"
        )

    issues_table_html = (
        "<div class='card'>"
        "<div class='row'><div><b>Issues</b>"
        f"<span class='badge badge-bad'>{issue_count}</span></div>"
        "<div class='muted'>Click to jump to the concept/segment</div></div>"
        "<div style='margin-top:10px; overflow:auto;'>"
        "<table>"
        "<thead><tr><th>Where</th><th>Concept</th><th>Field</th><th>Message</th><th>Value</th><th>Suggestion</th></tr></thead>"
        "<tbody>"
        + ("".join(issues_rows) if issues_rows else "<tr><td colspan='6' class='muted'>No issues 🎉</td></tr>")
        + "</tbody></table></div></div>"
    )

    # Concepts list
    concept_cards = []
    for ci, c in enumerate(concepts):
        cname = (c.get("concept") or "").strip()
        times = c.get("times", [])
        concept_anchor = f"c{ci}"
        concept_issue_block = ""
        if concept_anchor in issues_by_anchor:
            msgs = "<br/>".join(f"• <b>{esc(i.field)}</b>: {esc(i.message)}" for i in issues_by_anchor[concept_anchor])
            concept_issue_block = f"<div class='issue'><b class='bad'>Concept issues:</b><br/>{msgs}</div>"

        # segment rows
        seg_rows = []
        for si, seg in enumerate(times):
            a = f"c{ci}s{si}"
            start = seg.get("start","")
            end = seg.get("end","")
            dur = seg_duration(seg)
            dur_str = format_hhmmss(dur) if dur is not None else "—"
            seg_issue_block = ""
            if a in issues_by_anchor:
                msgs = "<br/>".join(
                    f"• <b>{esc(i.field)}</b>: {esc(i.message)}" + (f" (suggest: <code>{esc(i.suggestion)}</code>)" if i.suggestion else "")
                    for i in issues_by_anchor[a]
                )
                seg_issue_block = f"<div class='issue'><b class='bad'>Segment issues:</b><br/>{msgs}</div>"

            seg_rows.append(
                f"<tr id='{a}'>"
                f"<td>{si+1}</td>"
                f"<td><code>{esc(start)}</code></td>"
                f"<td><code>{esc(end)}</code></td>"
                f"<td><code>{esc(dur_str)}</code></td>"
                f"<td>{seg_issue_block or '<span class=\"muted\">OK</span>'}</td>"
                f"</tr>"
            )

        concept_cards.append(
            f"<div class='card' id='{concept_anchor}'>"
            f"<div class='row'>"
            f"<div><b>{esc(cname) or '<span class=\"bad\">(empty name)</span>'}</b>"
            f"<span class='badge'>{len(times)} segments</span></div>"
            f"<div class='muted'>#{ci+1}</div>"
            f"</div>"
            f"{concept_issue_block}"
            f"<div style='margin-top:10px; overflow:auto;'>"
            f"<table>"
            f"<thead><tr><th>#</th><th>Start</th><th>End</th><th>Duration</th><th>Status</th></tr></thead>"
            f"<tbody>{''.join(seg_rows) if seg_rows else '<tr><td colspan=\"5\" class=\"muted\">No segments</td></tr>'}</tbody>"
            f"</table></div>"
            f"</div>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Concepts Report</title>
<style>{css}</style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <div class="top">
        <div class="title">
          <h1>Concepts Report</h1>
          <div class="muted">Input: <code>{esc(input_name)}</code></div>
        </div>
        <div class="muted">
          Video duration: <code>{esc(duration_str)}</code><br/>
          Concepts: <code>{total_concepts}</code> • Segments: <code>{total_segments}</code> • Issues: <code class="{ 'bad' if issue_count else '' }">{issue_count}</code>
        </div>
      </div>
      <div class="content">
        {issues_table_html}
        <div class="card">
          <div class="row">
            <div><b>Concepts</b><span class="badge">{total_concepts}</span></div>
            <div class="muted">Sorted by name; segments sorted by start time</div>
          </div>
        </div>
        {''.join(concept_cards)}
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
    ap.add_argument("--input", required=True, help="Path to concepts JSON")
    ap.add_argument("--out_html", required=True, help="Path to output HTML report")
    ap.add_argument("--out_json", default=None, help="Optional: write cleaned JSON here")
    ap.add_argument("--duration", default=None, help="Optional: video duration (hh:mm:ss or mm:ss) for bounds checks")
    ap.add_argument("--auto_fix_carry", action="store_true",
                    help="If set, will auto-fix mm/ss>=60 by carrying to HH:MM:SS in the cleaned JSON")
    args = ap.parse_args()

    duration_secs = parse_duration(args.duration)

    raw = load_json(args.input)
    cleaned, issues = analyze_and_clean(
        raw,
        duration_secs=duration_secs,
        auto_fix_carry=args.auto_fix_carry,
    )

    report = render_html_report(
        cleaned,
        issues,
        input_name=args.input,
        duration_secs=duration_secs,
    )

    with open(args.out_html, "w", encoding="utf-8") as f:
        f.write(report)

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)

    # Console summary
    print(f"Wrote HTML report: {args.out_html}")
    if args.out_json:
        print(f"Wrote cleaned JSON: {args.out_json}")
    print(f"Concepts: {len(cleaned.get('concepts', []))}, Issues: {len(issues)}")


if __name__ == "__main__":
    main()
