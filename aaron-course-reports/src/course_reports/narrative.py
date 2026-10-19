"""Layer 3: narrative. One LLM call turns the computed facts into the report's prose.
Guards reject invented numbers and banned phrasing; anything that fails falls back to
deterministic Hebrew copy built from the same facts, so the report always renders."""
import json
import os
import re
from pathlib import Path

from .facts import numbers_in

DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """You write the prose of a pedagogic report for a university lecturer, in Hebrew, for AaronOwl.
You receive FACTS computed from the lecturer's lesson reports. Write only what the facts support.

Rules:
- Hebrew only. Warm, positive and concrete: lead with what works, then the next step.
- Every number you write must appear in FACTS. Never compute new numbers, never round differently.
- Behavioral, observational language ("נצפה", "עלה בדוחות"). Adoption is correlation, never proof of cause.
- No em dashes (—). Do not use the construction "לא X אלא Y". No emoji. Short sentences.
- Refer to students with the noun given in FACTS.course.student_noun.
- Never name or describe individual students.
- Write every number as digits (4, 10), never as Hebrew words (ארבעה, עשרת), so it can be checked against FACTS.
- Use few numbers. Prefer course content, unit names and concrete practices over counts and percentages.
- hero.sub: if a recurring recommendation in FACTS.recs has status "yes" or "part", name it as an observed change ("נצפתה פרקטיקה תואמת"). The next step comes from a recurring recommendation with status "no" or "unk".
- hub.sub: walk through the course content in order, using the unit names in FACTS.taught.units, then how it was taught, then (only if available) what was learned. At most one number.
- Output a single JSON object that matches SCHEMA exactly, with no text around it."""

SCHEMA = {
    "hero": {"h1": "short positive headline about the teaching (max 8 words)", "sub": "2-3 sentences: strongest pattern, the most important adopted change, the next step"},
    "insights": [{"title": "max 6 words", "text": "1-2 sentences with one concrete anchor (lesson number or count from FACTS)"}],
    "rec_notes": {"<rec id from FACTS.recs, top 3 only>": "one practical sentence on how to apply it"},
    "dim_notes": {"<each of the 16 dimension ids>": "2 sentences: what was observed; if level is weak, what improvement is suggested"},
    "hub": {
        "sub": "3 sentences: the course path through its units (by name), how it was taught, and (if FACTS.learned.available) what was learned. Positive, at most one number.",
        "reports": {
            "taught": {"insight": "one sentence insight from FACTS.taught", "points": ["teaser 1, makes the reader open the report", "teaser 2"]},
            "how": {"insight": "one sentence", "points": ["teaser 1", "teaser 2"]},
            "learned": {"insight": "one sentence (only if FACTS.learned.available)", "points": ["teaser 1", "teaser 2"]},
        },
        "links": [{"title": "insight that connects the reports", "text": "2 sentences", "taught": "what report 01 shows", "how": "what report 02 shows", "learned": "what report 03 shows (omit if unavailable)", "caveat": "optional: data limits"}],
    },
}


# ---------- guards ----------

EM_DASH = re.compile(r"\s*[—–]\s*")
NOT_BUT = re.compile(r"(^|\s)לא\s[^.?!]{1,60}\sאלא\s")
SMALL_OK = {str(i) for i in range(0, 6)} | {"16"}
# spelled-out numbers the guard must also see (0-5 are always allowed, so only 6 and up)
HEB_NUMS = {"שש": 6, "שישה": 6, "ששת": 6, "שבע": 7, "שבעה": 7, "שבעת": 7, "שמונה": 8, "שמונת": 8,
            "תשע": 9, "תשעה": 9, "תשעת": 9, "עשר": 10, "עשרה": 10, "עשרת": 10, "עשרים": 20}
HEB_NUM_RX = re.compile(r"(?<![א-ת])(?:ו|ב|ל|מ|ה|ש|כ|וב|ול|וה|בה|לה|מה|שה)?(" + "|".join(sorted(HEB_NUMS, key=len, reverse=True)) + r")(?![א-ת])")


def _strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")


def check(narr, facts):
    """Return a list of violations. Em dashes are auto-fixed, everything else is reported."""
    allowed = numbers_in(facts) | SMALL_OK
    problems = []
    for path, s in _strings(narr):
        for n in re.findall(r"\d+(?:\.\d+)?", s):
            if n not in allowed:
                problems.append(f"{path}: number {n} is not in FACTS")
        for w in HEB_NUM_RX.findall(s):
            if str(HEB_NUMS[w]) not in allowed:
                problems.append(f"{path}: number word {w} ({HEB_NUMS[w]}) is not in FACTS")
        if NOT_BUT.search(s):
            problems.append(f"{path}: uses the 'לא ... אלא' construction")
    return problems


def fix_dashes(obj):
    if isinstance(obj, str):
        return EM_DASH.sub(", ", obj)
    if isinstance(obj, dict):
        return {k: fix_dashes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_dashes(v) for v in obj]
    return obj


# ---------- LLM ----------

# USD per million tokens (input, output), for the cost estimate in _meta. The Batch API bills half.
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}
MAX_TOKENS = 16000  # thinking counts toward max_tokens; the JSON reply alone is ~3.5k tokens


def model_id(model=None):
    return model or os.environ.get("AARON_LLM_MODEL", DEFAULT_MODEL)


def request_params(facts, feedback=None, model=None):
    """The Messages API request for one narrative. The sync path and the Batch API send exactly this."""
    user = "FACTS:\n" + json.dumps(facts, ensure_ascii=False) + "\n\nSCHEMA:\n" + json.dumps(SCHEMA, ensure_ascii=False)
    if feedback:
        user += "\n\nYour previous answer broke these rules. Fix them and return the full JSON again:\n- " + "\n- ".join(feedback)
    return {"model": model_id(model), "max_tokens": MAX_TOKENS, "system": SYSTEM,
            "messages": [{"role": "user", "content": user}]}


def reply_text(msg):
    """Text of a Messages API reply, or an error for a reply that cannot hold a complete JSON object."""
    if msg.stop_reason == "refusal":
        raise RuntimeError("the model declined the request (stop_reason: refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"the reply hit max_tokens ({MAX_TOKENS}) and is truncated")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def usage_of(msg, batch=False):
    u = msg.usage
    return {"model": msg.model, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens, "batch": batch}


def _request(facts, feedback=None, model=None):
    """Send the facts to the model. Returns (raw text, usage)."""
    import anthropic  # optional dependency
    msg = anthropic.Anthropic().messages.create(**request_params(facts, feedback, model))
    return reply_text(msg), usage_of(msg)


def parse_reply(text):
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("LLM returned no JSON object")
    return json.loads(m.group(0))


def _record(text, retry=False):
    rec = os.environ.get("AARON_LLM_RECORD")  # path stem: saves raw replies as test fixtures
    if rec:
        path = Path(f"{rec}.retry.txt" if retry else f"{rec}.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _call_llm(facts, feedback=None, model=None):
    """One model call. Returns (parsed reply, usage)."""
    text, usage = _request(facts, feedback=feedback, model=model)
    _record(text, retry=bool(feedback))
    return parse_reply(text), usage


def cost_usd(usage):
    """Estimated cost of the calls in usage (a list of usage dicts); None for a model without a price."""
    total = 0.0
    for u in usage:
        price = next((v for k, v in PRICES.items() if u.get("model", "").startswith(k)), None)
        if price is None:
            return None
        c = (u["input_tokens"] * price[0] + u["output_tokens"] * price[1]) / 1e6
        total += c / 2 if u.get("batch") else c
    return round(total, 4)


def llm_narrative(facts, model=None, log=print, first=None):
    """first: an already-fetched (reply text, usage) pair, e.g. from the Batch API. A retry is always synchronous."""
    if first is not None:
        _record(first[0])
        narr, usage = parse_reply(first[0]), [first[1]]
    else:
        narr, u = _call_llm(facts, model=model)
        usage = [u]
    narr = fix_dashes(narr)
    problems = check(narr, facts)
    if problems:
        log(f"narrative: {len(problems)} rule violations, retrying once")
        narr, u = _call_llm(facts, feedback=problems[:20], model=model)
        narr, usage = fix_dashes(narr), usage + [u]
        problems = check(narr, facts)
    return narr, problems, usage


# ---------- deterministic fallback ----------

def _dim(facts, i):
    return next(d for d in facts["dims"] if d["id"] == i)


def _ls(ns):
    ns = list(ns)
    return ", ".join(str(n) for n in ns[:-1]) + (f" ו-{ns[-1]}" if len(ns) > 1 else str(ns[0]) if ns else "")


def fallback_narrative(facts):
    c, noun = facts["course"], facts["course"]["student_noun"]
    n = c["n_lessons"]
    strengths = [_dim(facts, i) for i in facts["strengths_top"]]
    gaps = [_dim(facts, i) for i in facts["gaps_top"]]
    recs = facts["recs"]
    adopted = [r for r in recs if r["status"] in ("yes", "part") and r["count"] >= 2]
    open_recs = [r for r in recs if r["status"] in ("no", "unk") and r["count"] >= 2]
    top_s = strengths[0]
    insights = [{"title": "הבסיס של ההוראה", "text": f"{top_s['he']}: נצפה כחוזקה ב-{len(top_s['strength_lessons'])} מתוך {n} שיעורים."}]
    if recs:
        r = recs[0]
        insights.append({"title": "ההמלצה שחזרה הכי הרבה", "text": f"{r['name']}: הומלצה ב-{r['count']} שיעורים."})
    if adopted:
        r = adopted[0]
        insights.append({"title": "המלצה שנכנסה לכיתה", "text": f"{r['name']}: נצפתה בשיעורים {_ls(r['evidence_lessons'])}."})
    if facts["improving"]:
        d = _dim(facts, facts["improving"][0])
        insights.append({"title": "ממד בהתקדמות", "text": f"{d['he']}: הומלץ לשפר בשיעורים {_ls(d['improve_lessons'])}, ובשיעור {d['strength_lessons'][-1]} נצפה כחוזקה."})
    if open_recs:
        r = open_recs[0]
        insights.append({"title": "הצעד הבא", "text": f"{r['name']}: הומלצה ב-{r['count']} שיעורים ועדיין לא נצפתה בדוחות."})
    insights = insights[:5]
    dim_notes = {}
    for d in facts["dims"]:
        if d["strength_lessons"] and not d["improve_lessons"]:
            s = f"נצפה כחוזקה בשיעורים {_ls(d['strength_lessons'])}."
        elif d["improve_lessons"] and not d["strength_lessons"]:
            s = f"עלה כמקום לשיפור בשיעורים {_ls(d['improve_lessons'])}."
        elif d["strength_lessons"]:
            s = f"נצפה כחוזקה בשיעורים {_ls(d['strength_lessons'])}, והומלץ לשפר בשיעורים {_ls(d['improve_lessons'])}."
        else:
            s = "הדוחות כמעט לא נגעו בממד הזה."
        ex = (d["strength_examples"] + d["improve_examples"])[:2]
        dim_notes[d["id"]] = s + (" לדוגמה: " + "; ".join(ex) + "." if ex else "")
    t, lf = facts["taught"], facts["learned"]
    hub_sub = f"{n} שיעורים מתועדים. החוזקה העקבית ביותר בהוראה: {top_s['he']}"
    hub_sub += f". המוקד לשיפור: {gaps[0]['he']}." if gaps else "."
    if lf.get("available") and lf.get("summary"):
        hub_sub += " " + lf["summary"]
    reports = {"how": {"insight": f"{top_s['he']}: חוזקה ב-{len(top_s['strength_lessons'])} מתוך {n} שיעורים.",
                       "points": ["ההמלצה שחזרה הכי הרבה, והאם אומצה", "הממדים שבהם נרשמה התקדמות"]}}
    if t.get("available"):
        big = max(t["units"], key=lambda u: u["pct"]) if t["units"] else None
        reports["taught"] = {"insight": (f"{big['name']}: {big['pct']}% מזמן התוכן בקורס." if big else f"{t['content_pct']}% מזמן השיעורים מוקדש לתוכן."),
                             "points": ["איך התחלק הזמן בין יחידות הקורס", "באילו שיעורים עלו הכי הרבה שאלות"]}
    if lf.get("available"):
        reports["learned"] = {"insight": (lf.get("summary") or "").split(".")[0] + ".",
                              "points": ["אילו נושאים נקלטו היטב", "במה הסטודנטים מתקשים"]}
    links = []
    if recs and t.get("available"):
        r = recs[0]
        links.append({"title": f"{r['name']}: מה רואים בכיתה ומה בהמלצות",
                      "text": "השוואה בין מה שהומלץ לבין מה שנרשם ביומני הכיתה.",
                      "taught": f"{t['interactions_total']} אינטראקציות בכיתה, מהן {t['student_questions_total']} שאלות {noun}.",
                      "how": f"{r['name']} הומלצה ב-{r['count']} שיעורים. {r['evidence']}."})
    if t.get("available") and t["distinction_challenging"]:
        links.append({"title": "הבחנה בין מושגים דומים",
                      "text": "חלק ניכר מהנושאים המאתגרים בכיתה הם הבחנות בין מושגים קרובים.",
                      "taught": f"{t['distinction_challenging']} מתוך {t['challenging_total']} הנושאים המאתגרים הם הבחנות בין מושגים.",
                      "how": next((f"{r['name']} הומלצה ב-{r['count']} שיעורים." for r in recs if r["id"] == "visual"), "")})
    return {
        "hero": {"h1": f"{c['name']}: איך לימדתי", "sub": " ".join(i["text"] for i in insights[:2])},
        "insights": insights,
        "rec_notes": {r["id"]: "" for r in recs[:3]},
        "dim_notes": dim_notes,
        "hub": {"sub": hub_sub, "reports": reports, "links": links},
    }


def merge(primary, fallback):
    """Fill anything missing or empty in primary from fallback."""
    if isinstance(fallback, dict):
        out = dict(fallback)
        for k, v in (primary or {}).items():
            out[k] = merge(v, fallback.get(k)) if k in fallback else v
        return out
    if primary in (None, "", [], {}):
        return fallback
    return primary


def build_narrative(facts, use_llm=True, model=None, log=print, first=None):
    fb = fallback_narrative(facts)
    if not use_llm:
        return fb, {"source": "fallback"}
    try:
        narr, problems, usage = llm_narrative(facts, model=model, log=log, first=first)
    except Exception as e:  # no key, no network, bad JSON, refusal, truncation
        log(f"narrative: LLM unavailable ({e.__class__.__name__}: {e}); using deterministic copy")
        return fb, {"source": "fallback", "error": str(e)}
    if problems:
        bad = {p.split(":")[0].split("[")[0].split(".")[0] for p in problems}
        log(f"narrative: {len(problems)} violations remain in {sorted(bad)}; those sections use deterministic copy")
        for top in bad:
            narr.pop(top, None)
    meta = {"source": "llm", "violations": problems, "model": usage[0].get("model") or model_id(model),
            "calls": len(usage), "input_tokens": sum(u["input_tokens"] for u in usage),
            "output_tokens": sum(u["output_tokens"] for u in usage), "batch": bool(usage[0].get("batch")),
            "cost_usd_est": cost_usd(usage)}
    log(f"narrative: {meta['model']} · {meta['calls']} call(s) · {meta['input_tokens']} in / {meta['output_tokens']} out"
        f" · ~${meta['cost_usd_est']}")
    return merge(narr, fb), meta
