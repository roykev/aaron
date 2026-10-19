"""Layer 0: parse Aaron inputs (export JSON rows, Teaching Snapshot text, class reports, learning report)."""
import html
import json
import re
import sys
from pathlib import Path

# ---------- parsing ----------

def _clean(s):
    return re.sub(r"\s+", " ", s.strip().strip("*").strip())


def _field(text, keys):
    for k in keys:
        m = re.search(r"\*" + re.escape(k) + r":\*\s*(.+)", text)
        if m:
            return _clean(m.group(1))
    return ""


def _section(text, name):
    m = re.search(r"^### " + re.escape(name) + r"\s*$(.*?)(?=^### |\Z)", text, flags=re.M | re.S)
    return m.group(1) if m else ""


def _items(sec):
    out = []
    for p in re.split(r"^\* \d+\.\s*", sec, flags=re.M)[1:]:
        first, _, rest = p.partition("\n")
        title, _, desc = first.partition(":")
        out.append({
            "title": _clean(title),
            "desc": _clean(desc),
            "why": _field(rest, ["למה זה חשוב", "Why it matters"]),
            "evidence": _field(rest, ["Evidence"]),
            "solution": _field(rest, ["הפתרון", "The Solution"]),
            "benefit": _field(rest, ["התועלת הפוטנציאלית", "Potential Benefit"]),
        })
    return out


def _actions(sec):
    out = []
    for line in sec.splitlines():
        m = re.match(r"^\d+\.\s+(.*)", line.strip())
        if not m:
            continue
        t = m.group(1)
        level = "medium" if "🟡" in t else ("easy" if "🟢" in t else "")
        em = re.search(r"\[(?:easy|medium|hard)\s*\((.*)\)\]", t)
        effort = em.group(1) if em else ""
        t = re.sub(r"[🟢🟡🔴].*$", "", t).replace("**", "").strip()
        out.append({"text": _clean(t), "level": level, "effort": _clean(effort)})
    return out


def parse_snapshot(block):
    title_m = re.search(r"^### (.+)$", block, flags=re.M)
    if not title_m:
        return None
    out_sec = _section(block, "Outstanding Performance")
    lines = [l for l in out_sec.strip().splitlines() if l.strip() and not l.strip().startswith("```")]
    return {
        "title": _clean(title_m.group(1)),
        "message": _field(block, ["המסר המרכזי", "Key Message"]),
        "duration": _field(block, ["משך השיעור", "Lecture Duration"]),
        "outstanding": {
            "title": _clean(lines[0]) if lines else "",
            "body": _clean(lines[1]) if len(lines) > 1 and not lines[1].startswith("*Evidence") else "",
            "evidence": _field(out_sec, ["Evidence"]),
        },
        "vision": _field(block, ["Strategic Vision"]),
        "practices": _items(_section(block, "Successful Practices")),
        "opportunities": _items(_section(block, "Opportunities for Enhancement")),
        "actions": _actions(_section(block, "Recommended Actions for Next Session")),
    }


# ---------- Aaron database export (JSON rows with an HTML snapshot_report) ----------

def _txt(fragment):
    s = re.sub(r"<[^>]+>", " ", fragment)
    return _clean(html.unescape(s))


def _labelled(block, labels):
    for lab in labels:
        m = re.search(r"<strong[^>]*>\s*" + re.escape(lab) + r":?\s*</strong>(.*?)</p>", block, flags=re.S | re.I)
        if m:
            return _txt(m.group(1))
    return ""


def _html_section(s, name):
    m = re.search(r"^## " + re.escape(name) + r"\s*$(.*?)(?=^## |\Z)", s, flags=re.M | re.S)
    return m.group(1) if m else ""


def _html_details(sec):
    return re.findall(r"<details[^>]*>(.*?)</details>", sec, flags=re.S)


def _summary(det):
    m = re.search(r"<summary[^>]*>(.*?)</summary>", det, flags=re.S)
    if not m:
        return "", ""
    head = re.search(r"<strong[^>]*>(.*?)</strong>", m.group(1), flags=re.S)
    tail = re.search(r"<span[^>]*>(.*?)</span>", m.group(1), flags=re.S)
    return (_txt(head.group(1)) if head else ""), (_txt(tail.group(1)) if tail else "")


def parse_html_snapshot(s):
    title_m = re.search(r"^## (?!Outstanding|Long-Term|Successful|Opportunities|Recommended)(.+)$", s, flags=re.M)
    if not title_m:
        return None
    out_sec = _html_section(s, "Outstanding Performance")
    ps = [_txt(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", out_sec, flags=re.S)]
    ps = [p for p in ps if p]
    practices, opps, actions = [], [], []
    for det in _html_details(_html_section(s, "Successful Practices")):
        head, desc = _summary(det)
        title = re.sub(r"^\d+\.\s*", "", head).rstrip(":").strip()
        practices.append({"title": title, "desc": desc, "why": _labelled(det, ["למה זה חשוב", "Why it matters"]),
                          "evidence": _labelled(det, ["Evidence"]), "solution": "", "benefit": ""})
    for det in _html_details(_html_section(s, "Opportunities for Enhancement")):
        head, desc = _summary(det)
        title = re.sub(r"^\d+\.\s*", "", head).rstrip(":").strip()
        opps.append({"title": title, "desc": _labelled(det, ["ההזדמנות", "The Opportunity"]) or desc, "why": "",
                     "evidence": _labelled(det, ["Evidence"]),
                     "solution": _labelled(det, ["הפתרון", "The Solution"]),
                     "benefit": _labelled(det, ["התועלת הפוטנציאלית", "Potential Benefit"])})
    for det in _html_details(_html_section(s, "Recommended Actions for Next Session")):
        head, tail = _summary(det)
        full = _labelled(det, ["פעולה מלאה", "Full action"]) or re.sub(r"^\d+\.\s*", "", head)
        level = "medium" if "🟡" in tail else ("easy" if "🟢" in tail else "")
        em = re.search(r"\[(?:easy|medium|hard)\s*\((.*)\)\]", tail)
        actions.append({"text": full, "level": level, "effort": _clean(em.group(1)) if em else ""})
    return {
        "title": _clean(title_m.group(1)),
        "message": _labelled(s, ["המסר המרכזי", "Key Message"]),
        "duration": _labelled(s, ["משך השיעור", "Lecture Duration"]),
        "outstanding": {
            "title": ps[0] if ps else "",
            "body": ps[1] if len(ps) > 1 and not ps[1].startswith("Evidence") else "",
            "evidence": _labelled(out_sec, ["Evidence"]),
        },
        "vision": _labelled(s, ["Strategic Vision"]),
        "practices": practices,
        "opportunities": opps,
        "actions": actions,
    }


def parse_export(path):
    """Rows exported from the Aaron lectures table: name, event_time, snapshot_report (HTML/markdown)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("rows", data) if isinstance(data, dict) else data
    out = []
    for r in sorted(rows, key=lambda r: r.get("event_time") or ""):
        rep = r.get("snapshot_report")
        if not rep:
            print(f"note: {r.get('name', '?')} has no snapshot report, skipped", file=sys.stderr)
            continue
        snap = parse_html_snapshot(rep)
        if not snap:
            print(f"warning: could not parse the snapshot of {r.get('name', '?')}", file=sys.stderr)
            continue
        m = re.search(r"\d+", r.get("name", ""))
        snap["n"] = int(m.group()) if m else None
        if snap["n"] is None:
            print(f"warning: no lesson number in the name '{r.get('name', '')}'; lessons will be numbered by date", file=sys.stderr)
        snap["date"] = (r.get("event_time") or "")[:10]
        snap["_lecturer"] = r.get("lecturer_report") or ""
        snap["_name"] = r.get("name", "?")
        out.append(snap)
    return _dedupe_numbers(out)


def _dedupe_numbers(snaps):
    """Two rows with the same lesson number are usually a re-upload of the same lesson.
    Keep the richer report (the later one on a tie) and say which row was dropped."""
    keep = {}
    for s in snaps:
        n = s["n"]
        if n is None:
            keep[id(s)] = s
            continue
        prev = keep.get(n)
        if prev is None:
            keep[n] = s
            continue
        winner, loser = (s, prev) if (_richness(s), bool(s["_lecturer"])) >= (_richness(prev), bool(prev["_lecturer"])) else (prev, s)
        print(f"warning: lesson {n} appears twice ('{prev['_name']}', '{s['_name']}'); "
              f"kept '{winner['title']}' ({winner['date']}), dropped '{loser['title']}' ({loser['date']})", file=sys.stderr)
        keep[n] = winner
    out = sorted(keep.values(), key=lambda s: s["date"])
    for s in out:
        s.pop("_name", None)
    return out


def parse_reports(paths):
    lessons = []
    for p in map(str, paths):
        if p.lower().endswith(".json"):
            blocks = parse_export(p)
        else:
            text = Path(p).read_text(encoding="utf-8")
            raw = re.split(r"^### Teaching Snapshot\s*$", text, flags=re.M)[1:]
            if not raw:
                print(f"warning: no '### Teaching Snapshot' block in {p}", file=sys.stderr)
            blocks = [parse_snapshot(b.split("\n```", 1)[0] if "\n```\n" in b else b) for b in raw]
        for snap in blocks:
            if not snap:
                continue
            same = next((i for i, l in enumerate(lessons) if l["title"] == snap["title"]), None)
            if same is None:
                lessons.append(snap)
            elif _richness(snap) >= _richness(lessons[same]):
                lessons[same] = snap  # complete version replaces a truncated one
    # keep the real lesson numbers from an export; number text reports by order
    nums = [l.get("n") for l in lessons]
    if None in nums or len(set(nums)) != len(nums):
        for i, l in enumerate(lessons, 1):
            l["n"] = i
    return lessons


def _richness(l):
    return len(l["practices"]) + len(l["opportunities"]) + len(l["actions"])


def item_keys(lessons):
    for l in lessons:
        yield f'{l["n"]}O', "ביצוע בולט", l["outstanding"]["title"]
        for i, p in enumerate(l["practices"]):
            yield f'{l["n"]}P{i}', "חוזקה", p["title"]
        for i, o in enumerate(l["opportunities"]):
            yield f'{l["n"]}W{i}', "שיפור", o["title"]






def _t(fragment):
    s = re.sub(r"<br\s*/?>", " ", fragment)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _sec(s, name):
    m = re.search(r"^## " + re.escape(name) + r"\s*$(.*?)(?=^## |\Z)", s, flags=re.M | re.S)
    return m.group(1) if m else ""


def _rows(sec):
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", sec, flags=re.S)
    if not body:
        return []
    return [[_t(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), flags=re.S)]


def _secs(hms):
    p = [int(x) for x in re.findall(r"\d+", hms)]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    return 0


ADMIN = re.compile(r"הודעות|ארגוני|מנהל|הפסקה|טכני|פתיחת השיעור$|התארגנות|נוכחות")


def parse_lecturer_report(s):
    sections = []
    for r in _rows(_sec(s, "Class Structure")):
        if len(r) >= 5:
            sections.append({"title": r[1], "start": r[2], "end": r[3], "secs": _secs(r[4]),
                             "admin": bool(ADMIN.search(r[1]))})
    examples = [{"topic": r[0], "example": r[1], "ref": r[2]} for r in _rows(_sec(s, "Examples from Class")) if len(r) >= 3]
    interactions = [{"time": r[0], "type": r[1], "desc": r[2]} for r in _rows(_sec(s, "Class Interactions")) if len(r) >= 3]
    ch_sec = _sec(s, "Challenging Topics")
    challenging = []
    for block in re.split(r"<div[^>]*>\s*<p[^>]*>\s*<strong[^>]*>\s*\d+\.", ch_sec)[1:]:
        title = _t(block.split("</strong>", 1)[0])
        why = re.search(r"Why it's challenging:?\s*</strong>(.*?)</p>", block, flags=re.S)
        sug = re.search(r"Suggestion:?\s*</strong>(.*?)</p>", block, flags=re.S)
        challenging.append({"title": title, "why": _t(why.group(1)) if why else "",
                            "suggestion": _t(sug.group(1)) if sug else ""})
    if not challenging:  # plainer markup
        txt = _t(ch_sec)
        for m in re.finditer(r"(\d+)\.\s*(.+?)\s*Why it's challenging:\s*(.+?)\s*Suggestion:\s*(.+?)(?=\s\d+\.\s|$)", txt):
            challenging.append({"title": m.group(2), "why": m.group(3), "suggestion": m.group(4)})
    q_txt = _t(_sec(s, "Questions for Students"))
    found = re.split(r"(Foundational Questions|Advanced Questions)\s*\(\d+ questions?\)", q_txt)
    questions = {"basic": [], "advanced": []}
    for i in range(1, len(found) - 1, 2):
        key = "basic" if found[i].startswith("Foundational") else "advanced"
        questions[key] = [q.strip() for q in re.split(r"\s\d+\.\s", " " + found[i + 1]) if q.strip()]
    return {"sections": sections, "examples": examples, "interactions": interactions,
            "challenging": challenging, "questions": questions}


# ---------- learned (course learning report) ----------

def _num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    return float(m.group()) if m else None


def parse_learning_report(text):
    out = {"kpis": [], "summary": "", "struggles": [], "struggle_pattern": "", "worked": [], "worked_lessons": [],
           "worked_note": "", "gap": {}, "prior": [], "risk": {}, "risk_note": ""}
    head = re.search(r"<h1[^>]*>(.*?)</h1>\s*<p[^>]*>(.*?)</p>", text, flags=re.S)
    if head:
        out["title"], out["subtitle"] = _t(head.group(1)), _t(head.group(2))
    first_table = re.search(r"<table.*?</table>", text, flags=re.S)
    if first_table:
        for td in re.findall(r"<td[^>]*>(.*?)</td>", first_table.group(0), flags=re.S):
            v = re.search(r"<strong[^>]*>(.*?)</strong>", td, flags=re.S)
            lab = re.search(r"<span[^>]*>(.*?)</span>", td, flags=re.S)
            if v and lab:
                out["kpis"].append({"value": _t(v.group(1)), "label": _t(lab.group(1))})
    m = re.search(r"<strong>\s*תמונת מצב:?\s*</strong>(.*?)</div>", text, flags=re.S)
    out["summary"] = _t(m.group(1)) if m else ""

    def card(heading_kw):
        m = re.search(r"<h2[^>]*>[^<]*" + heading_kw + r".*?</h2>(.*?)(?=<h2|\Z)", text, flags=re.S)
        return m.group(1) if m else ""

    st = card("מתקשים")
    for row in re.findall(r"<div style=\"display:flex;padding:12px.*?</div>", st, flags=re.S):
        spans = re.findall(r"<span style=\"(?:width:\d+%|flex:1)[^\"]*\">(.*?)</span>(?=<span style=\"(?:width|flex)|\s*</div>|$)", row, flags=re.S)
        cells = re.split(r"</span><span style=\"(?:width:\d+%|flex:1)", row)
        parts = [_t(re.sub(r"^[^>]*>", "", c, count=1)) for c in cells]
        title_m = re.search(r"<strong>(.*?)</strong><br><span[^>]*>(.*?)</span>", row, flags=re.S)
        kind_m = re.search(r"border-radius:20px[^\"]*\">([^<]+)</span>", row)
        rec_m = re.search(r"<span style=\"flex:1[^\"]*\">(.*?)</span>\s*$", row.strip()[:-6] if row.strip().endswith("</div>") else row, flags=re.S)
        ev = parts[2] if len(parts) > 3 else ""
        out["struggles"].append({
            "topic": _t(title_m.group(1)) if title_m else (parts[0] if parts else ""),
            "meta": _t(title_m.group(2)) if title_m else "",
            "kind": _t(kind_m.group(1)) if kind_m else "",
            "evidence": ev,
            "rec": _t(rec_m.group(1)) if rec_m else (parts[-1] if parts else ""),
        })
    m = re.search(r"<strong>\s*דפוס משותף:?\s*</strong>(.*?)</div>", st, flags=re.S)
    out["struggle_pattern"] = _t(m.group(1)) if m else ""

    wk = card("מה עבד")
    for td in re.findall(r"<td style=\"border:1px solid #d1fae5[^\"]*\">(.*?)</td>", wk, flags=re.S):
        strongs = re.findall(r"<strong[^>]*>(.*?)</strong>", td, flags=re.S)
        note = re.search(r"<span[^>]*>(.*?)</span>", td, flags=re.S)
        if len(strongs) >= 2:
            out["worked"].append({"value": _t(strongs[0]), "topic": _t(strongs[1]), "note": _t(note.group(1)) if note else ""})
    for lm in re.finditer(r"<strong>(שיעור \d+)</strong>\s*[—-]\s*הערכה\s*<strong>([\d.]+)</strong>", wk):
        out["worked_lessons"].append({"lesson": int(re.search(r"\d+", lm.group(1)).group()), "score": float(lm.group(2))})
    m = re.search(r"<strong>\s*המלצה:?\s*</strong>(.*?)</div>", wk, flags=re.S)
    out["worked_note"] = _t(m.group(1)) if m else ""

    gp = card("פער הוראה")
    bars = re.findall(r"<span[^>]*>([^<]*ממוצע[^<]*)</span>.*?<strong[^>]*>([\d.]+)</strong>", gp, flags=re.S)
    out["gap"]["bars"] = [{"label": _t(a), "value": float(b)} for a, b in bars]
    out["gap"]["lessons"] = [{"value": float(v), "label": _t(l)} for v, l in
                             re.findall(r"<strong[^>]*>([\d.]+)</strong><span[^>]*>(שיעור[^<]*)</span>", gp)]
    m = re.search(r"<div style=\"background:#fff1f2;border-right[^\"]*\">(.*?)</div>", gp, flags=re.S)
    out["gap"]["note"] = _t(m.group(1)) if m else ""

    pk = card("ידע מוקדם")
    for blk in re.findall(r"<div style=\"display:flex;gap:14px.*?</p></div>\s*</div>", pk, flags=re.S):
        n = re.search(r"<strong[^>]*font-size:28px[^>]*>(\d+)</strong>", blk)
        title = re.search(r"<strong style=\"display:block;font-size:14px[^\"]*\">(.*?)</strong>", blk, flags=re.S)
        desc = re.search(r"</strong><p[^>]*>(.*?)</p>", blk, flags=re.S)
        tags = [_t(x) for x in re.findall(r"font-family:monospace[^\"]*\">(.*?)</span>", blk)]
        fix = re.search(r"↩\s*(.*?)</p>", blk, flags=re.S)
        out["prior"].append({"students": int(n.group(1)) if n else None, "title": _t(title.group(1)) if title else "",
                             "desc": _t(desc.group(1)) if desc else "", "terms": tags, "fix": _t(fix.group(1)) if fix else ""})

    rk = card("בסיכון")
    for val, lab in re.findall(r"font-size:28px[^\"]*\">(\d+)</strong><span[^>]*>([^<]+)</span>", rk):
        out["risk"][_t(lab)] = int(val)
    m = re.search(r"<strong>\s*הערה:?\s*</strong>(.*?)</div>", rk, flags=re.S)
    out["risk_note"] = _t(m.group(1)) if m else ""
    # individual students are deliberately not carried over: the hub shows tiers only

    if not out["kpis"] or not out["struggles"]:
        print("warning: learning report parsed partially; check its format", file=sys.stderr)
    return out


def load_course(report_paths, learned_path=None):
    """Parse every input of one course. Returns (lessons, taught, learned)."""
    lessons = parse_reports(report_paths)
    if not lessons:
        raise ValueError("no lessons could be parsed from the reports")
    taught = {}
    for l in lessons:
        raw = l.pop("_lecturer", "")
        if raw:
            t = parse_lecturer_report(raw)
            untitled = [s for s in t["sections"] if not s["title"]]
            t["untitled"] = bool(t["sections"]) and len(untitled) == len(t["sections"])
            if untitled:
                print(f"warning: lesson {l['n']}: {len(untitled)} of {len(t['sections'])} class-report sections have no title; "
                      "shown as 'אין חלוקה לנושאים'", file=sys.stderr)
            taught[l["n"]] = t
    learned = None
    if learned_path:
        raw_learned = Path(learned_path).read_text(encoding="utf-8")
        learned = parse_learning_report(raw_learned)
        learned["_html"] = raw_learned
    return lessons, taught, learned
