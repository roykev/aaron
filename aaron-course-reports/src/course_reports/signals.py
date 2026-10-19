"""Layer 1: deterministic signals from the parsed lesson reports. No LLM here.

- item -> pedagogic dimension mapping (lexicon classifier, or embeddings when available)
- per-dimension strength / improvement signals per lesson, net position and the "improving" arrow
- recurring recommendations (recommendation_themes.json) and whether they were adopted later
- course units (consecutive lessons that share a topic word)
"""
import json
import re
from collections import Counter
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

# ---------- items ----------

def iter_items(lessons):
    """Yield (key, kind, lesson_n, title, body) for every item a lesson report contains.
    kind: 'O' outstanding (strength), 'P' practice (strength), 'W' opportunity (improvement)."""
    for l in lessons:
        n = l["n"]
        o = l["outstanding"]
        yield f"{n}O", "O", n, o["title"], o.get("body", "")
        for i, p in enumerate(l["practices"]):
            yield f"{n}P{i}", "P", n, p["title"], p.get("desc", "")
        for i, w in enumerate(l["opportunities"]):
            yield f"{n}W{i}", "W", n, w["title"], w.get("desc", "")


# ---------- dimension classifiers ----------

class LexiconClassifier:
    """Scores each dimension by weighted stem matches; title matches count double."""

    def __init__(self, lexicon_path=ASSETS / "dimension_lexicon.json", second_ratio=0.6, max_dims=2):
        raw = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
        self.rules = {d: [(int(w), re.compile(p, re.I)) for w, pats in v.items() for p in pats]
                      for d, v in raw.items() if not d.startswith("_")}
        self.second_ratio, self.max_dims = second_ratio, max_dims

    def scores(self, title, body=""):
        out = {}
        for d, rules in self.rules.items():
            s = 0.0
            for w, rx in rules:
                if rx.search(title or ""):
                    s += 2 * w
                elif rx.search(body or ""):
                    s += w
            if s:
                out[d] = s
        return out

    def classify(self, title, body=""):
        sc = self.scores(title, body)
        if not sc:
            return []
        ranked = sorted(sc.items(), key=lambda kv: -kv[1])
        top = ranked[0][1]
        return [d for d, s in ranked[: self.max_dims] if s >= top * self.second_ratio]


class EmbeddingClassifier:
    """Cosine similarity between the item text and each dimension's description
    (name + sub-dimensions), using sentence-transformers. Optional dependency;
    the model must be available locally or downloadable."""

    def __init__(self, dims, model_name="paraphrase-multilingual-MiniLM-L12-v2", second_margin=0.03, min_sim=0.25):
        from sentence_transformers import SentenceTransformer  # optional
        self.model = SentenceTransformer(model_name)
        self.ids = [d["id"] for d in dims["dims"]]
        texts = [f'{d["he"]}: ' + ", ".join(d.get("subs", [])) for d in dims["dims"]]
        self.dim_vecs = self.model.encode(texts, normalize_embeddings=True)
        self.second_margin, self.min_sim = second_margin, min_sim

    def classify(self, title, body=""):
        v = self.model.encode([f"{title}. {body}"], normalize_embeddings=True)[0]
        sims = self.dim_vecs @ v
        order = sims.argsort()[::-1]
        best = float(sims[order[0]])
        if best < self.min_sim:
            return []
        out = [self.ids[order[0]]]
        if float(sims[order[1]]) >= best - self.second_margin:
            out.append(self.ids[order[1]])
        return out


def map_items(lessons, classifier):
    return {key: classifier.classify(title, body) for key, _, _, title, body in iter_items(lessons)}


# ---------- dimension signals ----------

# Thresholds on the net position, tuned on 10-lesson courses. For other lengths the net is scaled
# to 10 lessons first, so a 4-lesson and a 20-lesson course get comparable colors.
LEVELS = [(6, "l5", "חוזקה בולטת"), (3, "l4", "חוזקה"), (-2, "l3", "מאוזן"), (-5, "l2", "דורש תשומת לב"), (-99, "l1", "מוקד לשיפור")]
REF_LESSONS = 10


def dim_signals(item_dims, dim_ids):
    sig = {d: {"s": set(), "w": set()} for d in dim_ids}
    for key, ids in item_dims.items():
        m = re.match(r"^(\d+)([OPW])", key)
        n, kind = int(m.group(1)), ("w" if m.group(2) == "W" else "s")
        for d in ids:
            if d in sig:
                sig[d][kind].add(n)
    return sig


def dim_state(sig_d, n_lessons=REF_LESSONS):
    """net = strength lessons - improvement lessons (never shown as a number), scaled to REF_LESSONS.
    This is the only place the level rule lives; the HTML template reads the result from analysis.dims."""
    s, w = sig_d["s"], sig_d["w"]
    net = len(s) - len(w)
    n = max(1, n_lessons)
    scaled = net * REF_LESSONS / n
    level = next((cls, he) for lo, cls, he in LEVELS if scaled >= lo)
    allv = s | w
    last = max(allv) if allv else 0
    improving = bool(w) and last in s and last not in w and min(w) < last
    pos = round(max(4, min(96, (net + n) / (2 * n) * 100)), 1)
    return {"net": net, "level": level[0], "level_he": level[1], "improving": improving, "pos": pos,
            "strength_lessons": sorted(s), "improve_lessons": sorted(w)}


def dim_states(item_dims, dim_ids, n_lessons):
    sig = dim_signals(item_dims, dim_ids)
    return {d: dim_state(sig[d], n_lessons) for d in dim_ids}


def dim_focus(dim, item_dims, lessons, max_subs=3):
    """Sub-dimensions whose words appear in the items mapped to this dimension."""
    texts = [f"{t} {b}" for key, _, _, t, b in iter_items(lessons) if dim["id"] in item_dims.get(key, [])]
    blob = " ".join(texts)
    scored = []
    for sub in dim.get("subs", []):
        words = [w for w in re.findall(r"[\w\-']+", sub) if len(w) >= 3]
        hits = sum(blob.count(w[:4]) for w in words)
        if hits:
            scored.append((hits, sub))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:max_subs]] or dim.get("subs", [])[:2]


# ---------- recurring recommendations and adoption ----------

def load_themes(path=ASSETS / "recommendation_themes.json"):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    for t in raw["themes"]:
        for k in ("rec_patterns", "adopt_patterns", "interaction_patterns", "interaction_exclude"):
            t["_" + k] = [re.compile(p, re.I) for p in t.get(k, [])]
    return raw["themes"]


def _hit(rxs, text):
    return any(rx.search(text or "") for rx in rxs)


def theme_signals(lessons, taught, themes):
    """For each theme: lessons where it was recommended, and later lessons where it was observed."""
    nums = [l["n"] for l in lessons]
    last_n = max(nums)
    out = []
    for th in themes:
        rec_lessons, rec_items = [], {}
        for l in lessons:
            texts = [f'{w["title"]} {w.get("desc", "")}' for w in l["opportunities"]] + [a["text"] for a in l["actions"]]
            matched = [t for t in texts if _hit(th["_rec_patterns"], t)]
            if matched:
                rec_lessons.append(l["n"])
                rec_items[l["n"]] = matched[0][:160]
        if not rec_lessons:
            continue
        first = rec_lessons[0]
        evidence = []
        for l in lessons:
            if l["n"] <= first:
                continue
            strengths = [l["outstanding"]] + l["practices"]
            for s in strengths:
                if _hit(th["_adopt_patterns"], f'{s["title"]} {s.get("desc", "") or s.get("body", "")}'):
                    evidence.append((l["n"], s["title"], "report"))
                    break
            t = (taught or {}).get(l["n"])
            if t and th["_interaction_patterns"]:
                acts = [i for i in t.get("interactions", [])
                        if _hit(th["_interaction_patterns"], i["desc"]) and not _hit(th["_interaction_exclude"], i["desc"])]
                if acts:
                    evidence.append((l["n"], acts[0]["desc"][:90], "class"))
        ev_lessons = sorted({e[0] for e in evidence})
        recent = [n for n in rec_lessons if n >= sorted(nums)[-2]] if len(nums) > 1 else rec_lessons
        if ev_lessons:
            status = "part" if last_n in rec_lessons else "yes"
        elif recent:
            status = "no"
        else:
            status = "unk"
        out.append({"id": th["id"], "name": th["name"], "dims": th["dims"], "lessons": rec_lessons,
                    "first_example": rec_items[first], "evidence": evidence, "evidence_lessons": ev_lessons,
                    "status": status, "theme": {k: v for k, v in th.items() if not k.startswith("_")}})
    out.sort(key=lambda t: (-len(t["lessons"]), t["lessons"][0]))
    return out


def adoption_evidence_text(t, last_n):
    if t["status"] in ("yes", "part"):
        parts = []
        for n in t["evidence_lessons"][:3]:
            items = [e for e in t["evidence"] if e[0] == n]
            parts.append(f"שיעור {n}: {items[0][1]}")
        tail = f". ההמלצה עדיין חוזרת בשיעור {last_n}" if t["status"] == "part" else ""
        return " · ".join(parts) + tail
    if t["status"] == "no":
        return f"לא נצפתה פרקטיקה תואמת. ההמלצה חוזרת עד שיעור {t['lessons'][-1]}"
    return f"הדוחות שאחרי שיעור {t['lessons'][-1]} אינם מתייחסים לנושא"


# ---------- course units ----------

STOP = set("""של את על עם בין גם או כל זה זו הם הן היא הוא מה איך למה כי אם לא כן יש אין דרך מול לפי עד
מבוא שיעור שיעורים סיום המשך חלק הקורס קורס בקורס הצגת הנחיות דיון ו ה ב ל מ ש""".split())


def _tokens(title, course_words):
    words = re.findall(r"[א-תA-Za-z][א-תA-Za-z\-']+", title)
    out = set()
    for w in words:
        base = re.sub(r"^(ו|ה|ב|ל|מ|ש|כש|וה|וב|ול|במ|בה|לה|מה)(?=..)", "", w)
        if len(base) >= 4 and base not in STOP and base not in course_words:
            out.add(base[:5])
    return out


def segment_units(lessons, course_name=""):
    """Consecutive lessons that share a title word form a unit. The shared word is the fallback unit name."""
    course_words = {w[:5] for w in course_name.split()} | {re.sub(r"^(ו|ה|ל)", "", w)[:5] for w in course_name.split()}
    freq = Counter(t for l in lessons for t in _tokens(l["title"], course_words))
    too_common = {t for t, c in freq.items() if c > max(3, len(lessons) * 0.6)}
    units = []
    for l in lessons:
        toks = _tokens(l["title"], course_words) - too_common
        if units and units[-1]["_toks"] & toks:
            u = units[-1]
            u["lessons"].append(l["n"])
            u["_shared"].update(units[-1]["_toks"] & toks)
            u["_toks"] = (u["_toks"] & toks) or toks
        else:
            units.append({"lessons": [l["n"]], "_toks": toks, "_shared": Counter(), "_first_title": l["title"]})
    for u in units:
        word = u["_shared"].most_common(1)[0][0] if u["_shared"] else ""
        full = ""
        if word:
            m = re.search(r"\S*" + re.escape(word) + r"\S*", u["_first_title"])
            full = m.group(0).strip(":,-") if m else word
        u["name"] = full or re.split(r"[:\-–]", u["_first_title"])[0].strip()
        u["short"] = u["name"][:14]
        del u["_toks"], u["_shared"], u["_first_title"]
    return units
