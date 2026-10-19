"""Orchestration: inputs -> layers 0-3 -> analysis.json (the render contract) -> HTML / Markdown."""
import json
from pathlib import Path

from . import signals as S
from .facts import build_facts
from .ingest import load_course
from .narrative import build_narrative
from .validate import validate

ASSETS = Path(__file__).resolve().parent / "assets"
STATUS_ORDER = {"yes": 0, "part": 1, "no": 2, "unk": 3}


def load_dims():
    return json.loads((ASSETS / "dimensions.json").read_text(encoding="utf-8"))


def make_classifier(kind, dims):
    if kind == "embeddings":
        return S.EmbeddingClassifier(dims)
    return S.LexiconClassifier()


def compute(cfg, lessons, taught, learned, classifier="lexicon"):
    """Layers 1-2. Returns (item_dims, themes, units, facts)."""
    dims = load_dims()
    item_dims = S.map_items(lessons, make_classifier(classifier, dims))
    themes = S.theme_signals(lessons, taught, S.load_themes())
    units = cfg.get("units") or S.segment_units(lessons, cfg["name"])
    facts = build_facts(cfg, lessons, taught, learned, dims, item_dims, themes, units)
    return item_dims, themes, units, facts


def assemble(cfg, lessons, taught, learned, item_dims, themes, units, facts, narr):
    """Build analysis.json: computed structure + narrative prose, in the shape template.html expects."""
    name, n = cfg["name"], len(lessons)
    last_n = lessons[-1]["n"]
    recs = [{"name": t["name"], "lessons": t["lessons"], "note": narr["rec_notes"].get(t["id"]) or t["theme"]["next_text"]}
            for t in themes]
    adopt = [{"rec": t["name"], "lessons": ", ".join(map(str, t["lessons"])), "status": t["status"],
              "evidence": S.adoption_evidence_text(t, last_n)}
             for t in sorted([t for t in themes if len(t["lessons"]) >= 2 or t["status"] in ("yes", "part")],
                             key=lambda t: (STATUS_ORDER[t["status"]], -len(t["lessons"])))]
    dim_he = {d["id"]: d["he"] for d in load_dims()["dims"]}
    growth = []
    for d in facts["dims"]:
        if d["improving"]:
            w, s = d["improve_lessons"], d["strength_lessons"]
            after = [x for x in s if x > max(w)]
            growth.append({"dim": dim_he[d["id"]],
                           "before": f"שיעורים {', '.join(map(str, w))}: " + (d["improve_examples"][0].split(": ", 1)[-1] if d["improve_examples"] else "הומלץ לשפר"),
                           "after": f"שיעורים {', '.join(map(str, after))}: " + (d["strength_examples"][-1].split(": ", 1)[-1] if d["strength_examples"] else "נצפה כחוזקה"),
                           "confidence": "ביטחון גבוה" if len(after) >= 2 else "ביטחון בינוני"})
    open_themes = [t for t in themes if t["status"] in ("no", "part", "unk") and len(t["lessons"]) >= 2][:3]
    nxt = [{"time": t["theme"]["next_time"], "title": t["theme"]["next_title"], "text": t["theme"]["next_text"]} for t in open_themes]
    dims_out = {d["id"]: {"note": narr["dim_notes"].get(d["id"], ""), "focus": d["focus"]} for d in facts["dims"]}
    refresh_dim_states({"dims": dims_out, "item_dims": item_dims}, n)
    analysis = {
        "course": {"name": name, "title": cfg.get("title") or f"דוח מרצה ב{name}", "student_noun": cfg.get("student_noun", "סטודנטים"),
                   "description": cfg.get("description") or f"דוח מרצה מלא לקורס {name}, {n} שיעורים מתועדים."},
        "hero": {"eyebrow": f"{name} · איך לימדתי · {n} שיעורים", "h1": narr["hero"]["h1"], "sub": narr["hero"]["sub"]},
        "insights": narr["insights"],
        "recs": recs, "adopt": adopt, "growth": growth,
        "next_minutes": sum(t["theme"]["next_minutes"] for t in open_themes), "next": nxt,
        "dims": dims_out, "item_dims": item_dims,
        "_meta": {"facts": facts},
    }
    if taught or learned:
        h = narr["hub"]
        rep = h.get("reports", {})
        cards = [
            {"id": "taught", "kicker": "דוח 01", "title": "מה לימדתי", "cta": "לחלוקת הקורס לנושאים", **rep.get("taught", {})},
            {"id": "how", "kicker": "דוח 02", "title": "איך לימדתי", "cta": "למפת 16 הממדים", **rep.get("how", {})},
        ]
        if learned:
            cards.append({"id": "learned", "kicker": "דוח 03", "title": "מה למדו", "cta": "למה שהסטודנטים לקחו", **rep.get("learned", {})})
        else:
            cards.append({"id": "learned", "kicker": "דוח 03", "title": "מה למדו", "missing": True,
                          "insight": "חסר פידבק סטודנטים לבניית הדוח.",
                          "text": "כדי לדעת מה הסטודנטים לקחו מהקורס נדרשים נתוני למידה: חידונים, הערכות ושאלות לצ'אטבוט.",
                          "cta": "לא זמין לקורס הזה"})
        if not taught:
            cards = [c for c in cards if c["id"] != "taught"]
        analysis["hub"] = {"eyebrow": "", "h1": name, "subtitle": "דוח מרצה מלא", "sub": h.get("sub", ""),
                           "taught_lead": "החומר שנלמד בפועל, לפי ניתוח הקלטות השיעורים: כמה זמן קיבלה כל יחידה, אילו תתי-נושאים נלמדו בה, וכמה אינטראקציה הייתה בכל שיעור.",
                           "gap_title": h.get("gap_title") or "פער הוראה-למידה",
                           "reports": cards, "links": h.get("links", []), "units": units}
    return analysis


STATE_KEYS = ("level", "level_he", "improving", "pos")


def refresh_dim_states(analysis, n_lessons):
    """Write the computed level of every dimension into analysis.dims from analysis.item_dims.
    Called on build and again on re-render, so a hand-edited item_dims mapping updates the tiles."""
    ids = [d["id"] for d in load_dims()["dims"]]
    states = S.dim_states(analysis.get("item_dims", {}), ids, n_lessons)
    dims = analysis.setdefault("dims", {})
    for i in ids:
        entry = dims.setdefault(i, {"note": "", "focus": []})
        entry.update({k: states[i][k] for k in STATE_KEYS})
    return analysis


def deep_merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return over


def course_facts(report_paths, cfg, learned_path=None, classifier="lexicon"):
    """Layers 0-2 only: the facts the narrative call receives (used to prepare Batch API requests)."""
    lessons, taught, learned = load_course(report_paths, learned_path)
    return compute(cfg, lessons, taught, learned, classifier)[3]


def run(report_paths, cfg, learned_path=None, use_llm=True, classifier="lexicon", overrides=None, model=None, log=print,
        first_reply=None):
    lessons, taught, learned = load_course(report_paths, learned_path)
    item_dims, themes, units, facts = compute(cfg, lessons, taught, learned, classifier)
    narr, meta = build_narrative(facts, use_llm=use_llm, model=model, log=log, first=first_reply)
    analysis = assemble(cfg, lessons, taught, learned, item_dims, themes, units, facts, narr)
    analysis["_meta"]["narrative"] = meta
    if overrides:
        analysis = deep_merge(analysis, overrides)
        refresh_dim_states(analysis, len(lessons))  # overrides may edit item_dims
    problems, warnings = validate(lessons, analysis, load_dims())
    for w in warnings:
        log("warning: " + w)
    if problems:
        raise ValueError("analysis failed validation:\n" + "\n".join(problems))
    return lessons, taught, learned, analysis
