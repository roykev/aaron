"""Layer 2: course-level facts. Every number that can appear in a report is computed here,
in code, from the parsed inputs and the layer-1 signals. The narrative layer may only
phrase these facts; it never computes or invents numbers."""
import re

from . import signals as S

STUDENT_Q = re.compile(r"student.?question|שאלת סטודנט", re.I)
ACTIVITY = re.compile(r"זוג|pair|קוויז|quiz|digipad|משימ|תרגיל|ניסוי|קבוצה .*מציג", re.I)
DISTINCTION = re.compile(r"הבדל|הבחנה|מול")


def _lesson_of(key):
    return int(re.match(r"\d+", key).group())


def _mins(secs):
    return round(secs / 60)


def taught_facts(lessons, taught, units):
    if not taught:
        return {"available": False}
    per, all_secs, admin_secs = [], 0, 0
    unit_secs = {i: 0 for i in range(len(units))}
    challenging_total = distinction = 0
    missing_titles = []
    for l in lessons:
        t = taught.get(l["n"])
        if not t:
            continue
        secs = sum(s["secs"] for s in t["sections"])
        adm = sum(s["secs"] for s in t["sections"] if s["admin"])
        all_secs += secs
        admin_secs += adm
        u = next((i for i, x in enumerate(units) if l["n"] in x["lessons"]), None)
        if u is not None:
            unit_secs[u] += secs - adm
        inter = t.get("interactions", [])
        sq = sum(1 for i in inter if STUDENT_Q.search(i["type"]))
        act = sum(1 for i in inter if ACTIVITY.search(i["type"] + " " + i["desc"]) and not re.search(r"האם|שאלה", i["desc"]))
        ch = t.get("challenging", [])
        challenging_total += len(ch)
        distinction += sum(1 for c in ch if DISTINCTION.search(c["title"]))
        if any(not s["title"] for s in t["sections"]):
            missing_titles.append(l["n"])
        per.append({"n": l["n"], "minutes": _mins(secs), "interactions": len(inter), "student_questions": sq,
                    "activities": act, "challenging": len(ch), "challenging_titles": [c["title"] for c in ch][:6]})
    content = all_secs - admin_secs
    return {
        "available": True,
        "documented_lessons": len(per),
        "total_minutes": _mins(all_secs),
        "content_pct": round(100 * content / all_secs) if all_secs else 0,
        "admin_pct": round(100 * admin_secs / all_secs) if all_secs else 0,
        "units": [{"name": u["name"], "lessons": u["lessons"], "minutes": _mins(unit_secs[i]),
                   "pct": round(100 * unit_secs[i] / content) if content else 0} for i, u in enumerate(units)],
        "interactions_total": sum(p["interactions"] for p in per),
        "student_questions_total": sum(p["student_questions"] for p in per),
        "challenging_total": challenging_total,
        "distinction_challenging": distinction,
        "lessons_missing_section_titles": missing_titles,
        "per_lesson": per,
    }


def learned_facts(learned):
    if not learned:
        return {"available": False}
    keep = ("kpis", "summary", "struggles", "struggle_pattern", "worked", "worked_lessons", "worked_note", "gap", "prior", "risk", "title", "subtitle")
    out = {k: learned.get(k) for k in keep if learned.get(k) not in (None, "", [], {})}
    out["available"] = True
    return out  # individual student cards are never passed to the narrative layer


def build_facts(cfg, lessons, taught, learned, dims, item_dims, themes_sig, units):
    ids = [d["id"] for d in dims["dims"]]
    sig = S.dim_signals(item_dims, ids)
    titles = {k: t for k, _, _, t, _ in S.iter_items(lessons)}
    dim_rows = []
    for d in dims["dims"]:
        st = S.dim_state(sig[d["id"]], len(lessons))
        keys = [k for k, v in item_dims.items() if d["id"] in v]
        dim_rows.append({
            "id": d["id"], "he": d["he"], "vector": d["v"], **st,
            "focus": S.dim_focus(d, item_dims, lessons),
            "strength_examples": [f"שיעור {_lesson_of(k)}: {titles[k]}" for k in keys if "W" not in k][:3],
            "improve_examples": [f"שיעור {_lesson_of(k)}: {titles[k]}" for k in keys if "W" in k][:3],
        })
    nums = [l["n"] for l in lessons]
    out_titles = {}
    for l in lessons:
        out_titles.setdefault(l["outstanding"]["title"], []).append(l["n"])
    return {
        "course": {"name": cfg["name"], "student_noun": cfg.get("student_noun", "סטודנטים"),
                   "n_lessons": len(lessons), "lesson_numbers": nums,
                   "first_date": lessons[0].get("date", ""), "last_date": lessons[-1].get("date", "")},
        "lessons": [{"n": l["n"], "date": l.get("date", ""), "title": l["title"], "duration": l["duration"],
                     "outstanding": l["outstanding"]["title"],
                     "practices": [p["title"] for p in l["practices"]],
                     "opportunities": [o["title"] for o in l["opportunities"]]} for l in lessons],
        "dims": dim_rows,
        "strengths_top": [r["id"] for r in sorted(dim_rows, key=lambda r: -r["net"])[:4]],
        "gaps_top": [r["id"] for r in sorted(dim_rows, key=lambda r: r["net"])[:4] if r["net"] < 0],
        "improving": [r["id"] for r in dim_rows if r["improving"]],
        "recs": [{"id": t["id"], "name": t["name"], "lessons": t["lessons"], "count": len(t["lessons"]),
                  "status": t["status"], "evidence_lessons": t["evidence_lessons"],
                  "evidence": S.adoption_evidence_text(t, nums[-1])} for t in themes_sig],
        "outstanding_repeats": {k: v for k, v in out_titles.items() if len(v) > 1},
        "taught": taught_facts(lessons, taught, units),
        "learned": learned_facts(learned),
    }


def numbers_in(obj):
    """Every number a narrative is allowed to mention: all numbers present anywhere in the facts."""
    found = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            found.add(str(x))
            if isinstance(x, float) and x.is_integer():
                found.add(str(int(x)))
        elif isinstance(x, str):
            found.update(re.findall(r"\d+(?:\.\d+)?", x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                walk(v)
    walk(obj)
    return found
