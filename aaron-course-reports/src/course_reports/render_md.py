"""Render the report as one Markdown file (RTL, GitHub-flavoured, no scripts) that follows the HTML layout:
the same sections in the same order, card rows as tables, and <details> where the HTML opens a detail on click.
Anchors use the HTML's ids (#overview, #taught, #how, #learned, #l4), so links work the same way.
Same content contract as the HTML: analysis.json + parsed lessons, class reports and learning report.
Individual student data is never rendered here."""
import re

from .render_html import HEB_COUNT

# Color: inline styles in the HTML report's palette. VS Code, Obsidian and Typora show them; GitHub strips the
# style attribute and shows the same text uncolored, so every colored mark also works without color.
# Mid tones, so the text reads on light and dark viewers.
TEAL, AMBER, BLUE, SLATE, ORANGE, QUIET = "#0d9488", "#d97706", "#2563eb", "#64748b", "#ea580c", "#cbd5e1"
LEVEL_DOTS = {"l5": 5, "l4": 4, "l3": 3, "l2": 2, "l1": 1}
LEVEL_COLOR = {"l5": TEAL, "l4": "#14b8a6", "l3": "#94a3b8", "l2": "#f59e0b", "l1": ORANGE}
REPORT_COLOR = {"taught": BLUE, "how": TEAL, "learned": AMBER}
STATUS_STYLE = {"yes": ("#ffffff", TEAL), "part": ("#115e59", "#ccfbf1"), "no": ("#92400e", "#fef3c7"), "unk": ("#475569", "#e2e8f0")}
UNIT_COLORS = ["#94a3b8", "#1e40af", "#0d9488", "#7c3aed", "#d97706", "#0369a1", "#be185d"]  # same as the HTML
LEVEL_HE = {"l5": "חוזקה בולטת", "l4": "חוזקה", "l3": "מאוזן", "l2": "דורש תשומת לב", "l1": "מוקד לשיפור"}
STATUS_HE = {"yes": "אומצה", "part": "אומצה חלקית", "no": "לא נצפתה", "unk": "לא ניתן לקבוע"}
REPORT_HE = {"taught": "מה לימדתי", "how": "איך לימדתי", "learned": "מה למדו"}
STUDENT_Q = re.compile(r"student.?question|שאלת סטודנט", re.I)
ACTIVITY = re.compile(r"זוג|pair|קוויז|quiz|קהוט|kahoot|digipad|משימ|תרגיל|ניסוי", re.I)


# ---------- small helpers ----------

def _t(s):
    """Text safe inside a table cell or an HTML block."""
    return re.sub(r"\s+", " ", str(s or "")).replace("|", "\\|").replace("<", "&lt;").strip()


def _c(text, color, bold=False):
    return f'<span style="color:{color}">' + (f"<b>{text}</b>" if bold else str(text)) + "</span>"


def _pill(text, fg, bg):
    return f'<span style="color:{fg};background:{bg};padding:1px 8px;border-radius:10px;white-space:nowrap">{text}</span>'


def _status(st):
    fg, bg = STATUS_STYLE.get(st, STATUS_STYLE["unk"])
    return _pill(STATUS_HE.get(st, st), fg, bg)


def _bar(pct, width=20, color=BLUE):
    full = round(max(0, min(100, pct)) / 100 * width)
    return _c("█" * full, color) + _c("░" * (width - full), QUIET)


def _badge(level):
    k = LEVEL_DOTS.get(level, 3)
    return _c("●" * k, LEVEL_COLOR.get(level, SLATE)) + _c("○" * (5 - k), QUIET)


def _mins(secs):
    return round(secs / 60)


def _hm(secs):
    m = round(secs / 60)
    return f"{m // 60}:{m % 60:02d}"


def _dur_secs(d):
    p = [int(x) for x in re.findall(r"\d+", d or "")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else (p[0] * 60 + p[1] if len(p) == 2 else 0)


def _section_main(title):
    return re.split(r"\s[-–]\s", title or "")[0].strip()


def _short_title(title, course):
    parts = [x.strip() for x in re.split(r"[:\-–]", title or "") if x.strip()]
    return next((x for x in parts if not course or course not in x), parts[0] if parts else title)


def _reach(n, total):
    r = n / total
    return "בכל השיעורים" if r >= 1 else "כמעט בכל השיעורים" if r >= 0.85 else "ברוב השיעורים" if r >= 0.55 else "בחלק מהשיעורים"


def _strip(ls, nums):
    return "".join(_c("■", TEAL) if n in ls else _c("□", QUIET) for n in nums)


def _lesson_links(ns, have):
    return ", ".join(f"[{n}](#l{n})" if n in have else str(n) for n in ns)


def _kicker(w, text, color=SLATE):
    w(f"<sub>{_c(_t(text), color, bold=color != SLATE)}</sub>\n")


def _details(w, summary, lines):
    w(f"<details><summary>{_t(summary)}</summary>\n")
    for x in lines:
        w(x)
    w("\n</details>\n")


def _card_table(w, cols, rows):
    """A row of cards: one column per card, one table row per card part."""
    w("| " + " | ".join(cols) + " |")
    w("| " + " | ".join(":--" for _ in cols) + " |")
    for r in rows:
        w("| " + " | ".join(r) + " |")
    w("")


def _kpi_table(w, items, color=TEAL):
    """Big numbers on top, labels under them (the HTML KPI tiles)."""
    w("| " + " | ".join(_c(v, color, bold=True) for v, _ in items) + " |")
    w("| " + " | ".join(":-:" for _ in items) + " |")
    w("| " + " | ".join(_t(lab) for _, lab in items) + " |")
    w("")


def _learned_scores(learned):
    m = {}
    if not learned:
        return m
    for x in (learned.get("gap") or {}).get("lessons", []):
        n = re.search(r"\d+", x.get("label", ""))
        if n:
            m[int(n.group())] = x["value"]
    for x in learned.get("worked_lessons", []):
        m[x["lesson"]] = x["score"]
    return m


def _course_avg(learned):
    k = next((x for x in (learned or {}).get("kpis", []) if "הערכה" in x["label"] and "פער" not in x["label"]), None)
    try:
        return float(k["value"]) if k else None
    except ValueError:
        return None


def _score(s, avg):
    if s is None:
        return ""
    if avg is not None and s < avg - 10:
        return _c(f"<b>{s}</b> ▼", ORANGE)
    if avg is not None and s > avg + 10:
        return _c(f"<b>{s}</b> ▲", TEAL)
    return f"**{s}**"


def _inter_counts(t):
    inter = t.get("interactions", [])
    sq = sum(1 for i in inter if STUDENT_Q.search(i["type"]))
    act = sum(1 for i in inter if ACTIVITY.search(f"{i['type']} {i['desc']}"))
    return len(inter), sq, act


def _dim_lessons(item_dims):
    out = {}
    for k, ids in item_dims.items():
        m = re.match(r"^(\d+)([OPW])", k)
        for d in ids:
            s, w = out.setdefault(d, (set(), set()))
            (w if m.group(2) == "W" else s).add(int(m.group(1)))
    return out


# ---------- sections ----------

def _overview(w, A, lessons, taught, learned):
    hub = A["hub"]
    w('<a id="overview"></a>\n')
    w(f"# {A['course']['name']}\n")
    w(f"**{_t(hub.get('subtitle') or 'דוח מרצה מלא')}** · AaronOwl\n")
    if hub.get("sub"):
        w(f"{hub['sub']}\n")

    _kicker(w, "שלושה דוחות")
    w("## הכוונה, הדרך והתוצאה\n")
    cards = hub["reports"]
    _card_table(w, [f"{_t(c['kicker'])} · " + _c(_t(c["title"]), SLATE if c.get("missing") else REPORT_COLOR.get(c["id"], TEAL), bold=True)
                    for c in cards], [
        [f"**{_t(c.get('insight', ''))}**" for c in cards],
        ["<br>".join(f"• {_t(p)}" for p in c.get("points", [])) or _t(c.get("text", "")) for c in cards],
        [_t(c.get("cta", "")) if c.get("missing") else f"[{_t(c.get('cta') or 'לדוח המלא')} ←](#{c['id']})" for c in cards],
    ])

    if hub.get("links"):
        _kicker(w, "כוונה מול תוצאה")
        w(f"## מה הינשוף רואה כשמחברים את {'שלושת הדוחות' if learned else 'הדוחות'}\n")
        for x in hub["links"]:
            lines = [f"{x.get('text', '')}\n"]
            lines += [f"- **{he}:** {x[k]}" for k, he in REPORT_HE.items() if x.get(k)]
            if x.get("caveat"):
                lines.append(f"\n_{x['caveat']}_")
            _details(w, x["title"], lines)

    _kicker(w, "ציר הקורס")
    w(f"## {'השיעורים, מה נלמד ומה נקלט' if learned else 'השיעורים לאורך הסמסטר'}\n")
    units = hub.get("units") or []
    scores, avg = _learned_scores(learned), _course_avg(learned)
    max_n = max([l["n"] for l in lessons] + list(scores) + [n for u in units for n in u["lessons"]])
    unit_of = {n: u.get("short") or u["name"] for u in units for n in u["lessons"]}
    by_n = {l["n"]: l for l in lessons}
    cols = ["שיעור", "יחידה", "נושא", "נושאים מאתגרים"] + (["הערכה"] if learned else [])
    w("| " + " | ".join(cols) + " |")
    w("| " + " | ".join("---" for _ in cols) + " |")
    for n in range(1, max_n + 1):
        l, t = by_n.get(n), (taught or {}).get(n)
        row = [f"[**{n}**](#l{n})" if l else str(n), _t(unit_of.get(n, "")),
               _t(_short_title(l["title"], A["course"]["name"])) if l else "_לא מתועד_",
               str(len(t["challenging"])) if t else ""]
        if learned:
            row.append(_score(scores.get(n), avg))
        w("| " + " | ".join(row) + " |")
    if learned:
        w(f"\n<sub>הערכה: ממוצע ההערכה בשיעור, מתוך דוח הלמידה. {_c('▼', ORANGE)} נמוכה מממוצע הקורס"
          f"{f' ({avg:g})' if avg is not None else ''} · {_c('▲', TEAL)} גבוהה ממנו.</sub>")
    w("")


def _report_taught(w, A, lessons, taught, noun):
    hub = A.get("hub") or {}
    course = A["course"]["name"]
    w("---\n")
    w('<a id="taught"></a>\n')
    _kicker(w, "דוח 01", BLUE)
    w(f"## {_c('מה לימדתי', BLUE)}\n")
    w((hub.get("taught_lead") or "החומר שנלמד בפועל, לפי ניתוח הקלטות השיעורים.") + "\n")
    units = hub.get("units") or []
    nums = [l["n"] for l in lessons if l["n"] in taught]
    all_s = adm = 0
    unit_secs, topics, orphan = [0] * len(units), [dict() for _ in units], {}
    for l in lessons:
        t = taught.get(l["n"])
        if not t:
            continue
        ui = next((i for i, u in enumerate(units) if l["n"] in u["lessons"]), None)
        for s in t["sections"]:
            all_s += s["secs"]
            if s["admin"]:
                adm += s["secs"]
                continue
            key = _section_main(s["title"]) or f"שיעור {l['n']}: אין חלוקה לנושאים בדוח השיעור"
            bucket = topics[ui] if ui is not None else orphan
            if ui is not None:
                unit_secs[ui] += s["secs"]
            tp = bucket.setdefault(key, {"secs": 0, "lessons": set(), "missing": not _section_main(s["title"])})
            tp["secs"] += s["secs"]
            tp["lessons"].add(l["n"])
    counts = [(n, *_inter_counts(taught[n])) for n in nums]
    content = all_s - adm
    _kpi_table(w, [(len(nums), "שיעורים מתועדים"), (_hm(all_s), "שעות הוראה"),
                   (f"{round(100 * content / all_s) if all_s else 0}%", "מהזמן מוקדש לתוכן"),
                   (sum(c[1] for c in counts), f"אינטראקציות בכיתה, מהן {sum(c[2] for c in counts)} שאלות {noun}")])

    if units:
        _kicker(w, "חלוקת הזמן")
        w("### על מה הלך זמן הקורס\n")
        w("זמן התוכן בכל השיעורים המתועדים, לפי יחידה. זמן מנהלי (הודעות, בעיות טכניות) לא נכלל.\n")
        w("| יחידה | שיעורים | חלק מזמן התוכן | |")
        w("| --- | --- | --- | --- |")
        for i, u in enumerate(units):
            pct = round(100 * unit_secs[i] / content) if content else 0
            uc = UNIT_COLORS[i % len(UNIT_COLORS)]
            w(f"| {_c('■', uc)} {_c(_t(u['name']), uc, bold=True)} | {_lesson_links(u['lessons'], set(nums))} | "
              f"{pct}% · {_hm(unit_secs[i])} שעות | {_bar(pct, color=uc)} |")
        w("")

        _kicker(w, "תתי-נושאים")
        w("### מה נלמד בכל יחידה\n")
        w("תתי-הנושאים לפי ניתוח ההקלטה, מהארוך לקצר.\n")
        groups = [(u["name"], [n for n in u["lessons"] if n in taught], topics[i], UNIT_COLORS[i % len(UNIT_COLORS)])
                  for i, u in enumerate(units)]
        if orphan:
            groups.append(("שיעורים נוספים", sorted({n for v in orphan.values() for n in v["lessons"]}), orphan, SLATE))
        for uname, uls, tps, uc in groups:
            if not tps:
                continue
            w(f"#### {_c('■', uc)} {_c(_t(uname), uc)}\n")
            w(f"<sub>{' · '.join(f'שיעור {n}' for n in uls)}</sub>\n")
            ranked = sorted(tps.items(), key=lambda kv: -kv[1]["secs"])
            row = lambda k, v: (f"| {'_' + _t(k) + '_' if v['missing'] else _t(k)} | {_mins(v['secs'])} דק' | "
                                f"{_lesson_links(sorted(v['lessons']), set(nums))} |")
            w("| תת-נושא | זמן | שיעור |")
            w("| --- | --- | --- |")
            for k, v in ranked[:6]:
                w(row(k, v))
            w("")
            if len(ranked) > 6:
                _details(w, f"עוד {len(ranked) - 6} תתי-נושאים",
                         ["| תת-נושא | זמן | שיעור |", "| --- | --- | --- |"] + [row(k, v) for k, v in ranked[6:]])

    _kicker(w, "בכיתה")
    w("### אינטראקציות ושאלות בכל שיעור\n")
    w("הפירוט של כל שיעור (מבנה השיעור, נושאים מאתגרים, דוגמאות ויומן האינטראקציות) נמצא בעמוד השיעור.\n")
    top = max([c[1] for c in counts] + [1])
    w(f"| שיעור | נושא | | אינטראקציות | שאלות {noun} | פעילויות |")
    w("| --- | --- | --- | --- | --- | --- |")
    by_n = {l["n"]: l for l in lessons}
    for n, total, sq, act in counts:
        w(f"| [**{n}**](#l{n}) | {_t(_short_title(by_n[n]['title'], course))} | {_bar(100 * total / top, 12)} | **{total}** | {sq} | {act or ''} |")
    w("")


def _report_how(w, A, lessons, dims, has_hub):
    nums = [l["n"] for l in lessons]
    have = set(nums)
    w("---\n")
    w('<a id="how"></a>\n')
    if has_hub:
        _kicker(w, "דוח 02", TEAL)
        w(f"## {_c('איך לימדתי', TEAL)}\n")
    _kicker(w, A["hero"]["eyebrow"])
    w(f"{'###' if has_hub else '#'} {A['hero']['h1']}\n")
    w(f"{A['hero']['sub']}\n")
    total = sum(_dur_secs(l["duration"]) for l in lessons)
    w(f"**{len(lessons)}** שיעורים · **{_hm(total)}** שעות הוראה מתועדות · "
      f"**{round(total / len(lessons) / 60)}** דקות בממוצע לשיעור · **16** ממדים פדגוגיים\n")

    _kicker(w, "תובנות עיקריות")
    n_ins = len(A["insights"])
    w(f"### {HEB_COUNT.get(n_ins, n_ins)} דברים שעולים מהדוחות\n")
    for i, x in enumerate(A["insights"], 1):
        w(f"{i}. {_c(_t(x['title']), TEAL, bold=True)}  \n   {x['text']}")
    w("")

    # summary cubes
    c = {}
    for a in A["adopt"]:
        c[a["status"]] = c.get(a["status"], 0) + 1
    open_n = c.get("no", 0) + c.get("unk", 0)
    recs, growth, nxt = A["recs"], A["growth"], A["next"]
    cubes = [
        ("המלצות הינשוף", min(3, len(recs)), "ההמלצות שחזרו הכי הרבה", " · ".join(r["name"] for r in recs[:3]), "sec-recs"),
        ("המלצות הינשוף שאומצו", c.get("yes", 0) + c.get("part", 0), f"מתוך {len(A['adopt'])} המלצות נוסו, מלא או חלקית",
         f"{c.get('yes', 0)} אומצו · {c.get('part', 0)} חלקית · {open_n} עדיין פתוחות", "sec-adopt"),
        ("ממדי שיפור", len(growth), "ממדים שבהם נצפתה התקדמות", " · ".join(g["dim"] for g in growth), "sec-growth"),
        ("המלצות להמשך", A.get("next_minutes", 0), f"דקות לשיעור, ל-{len(nxt)} שינויים קבועים", " · ".join(x["title"] for x in nxt), "sec-next"),
    ]
    _card_table(w, [_t(k) for k, *_ in cubes], [
        [_c(big, TEAL, bold=True) for _, big, *_ in cubes],
        [f"**{_t(t)}**" for _, _, t, *_ in cubes],
        [f"<sub>{_t(sub)}</sub>" for *_, sub, _ in cubes],
        [f"[לפירוט ←](#{a})" for *_, a in cubes],
    ])

    # map of the 16 dimensions
    w('<a id="dims"></a>\n')
    _kicker(w, "16 הממדים הפדגוגיים")
    w("### מפת ההוראה\n")
    w("הצבע מראה עד כמה הממד בלט כחוזקה לאורך הסמסטר. חץ מסמן ממד שבו הומלץ שיפור, ובהמשך הסמסטר הוא נצפה כחוזקה.\n")
    w("<sub>מוקד לשיפור " + " · ".join(_badge(f"l{k}") for k in range(1, 6)) + f" חוזקה בולטת · {_c('↑', TEAL, bold=True)} התקדמות</sub>\n")
    vecs = dims["vectors"]
    cols = [[d for d in dims["dims"] if d["v"] == v["id"]] for v in vecs]
    state = lambda d: A["dims"].get(d["id"], {})
    cell = lambda d: (f"{_badge(state(d).get('level', 'l3'))} {_t(d['he'])}"
                      f"{' ' + _c('↑', TEAL, bold=True) if state(d).get('improving') else ''}") if d else ""
    w("| " + " | ".join(f"**{_t(v['he'])}**" for v in vecs) + " |")
    w("| " + " | ".join(":--" for _ in vecs) + " |")
    for i in range(max(len(x) for x in cols)):
        w("| " + " | ".join(cell(col[i] if i < len(col) else None) for col in cols) + " |")
    w("")
    sig = _dim_lessons(A["item_dims"])
    detail = []
    for v, col in zip(vecs, cols):
        detail.append(f"\n**{_t(v['he'])}**\n")
        for d in col:
            st = state(d)
            s, wk = sig.get(d["id"], (set(), set()))
            focus = " · ".join(st.get("focus", []))
            focus_k = "מה בולט" if st.get("level") in ("l4", "l5") else "במה להתמקד"
            lv = st.get("level", "l3")
            detail.append(f"- **{_t(d['he'])}** · {_c(st.get('level_he') or LEVEL_HE[lv], LEVEL_COLOR[lv], bold=True)}"
                          f"{' · ' + _c('↑ התקדמות', TEAL) if st.get('improving') else ''}  \n  {st.get('note', '')}  \n"
                          f"  <sub>חוזקה בשיעורים: {_lesson_links(sorted(s), have) or 'אין'} · "
                          f"הומלץ שיפור בשיעורים: {_lesson_links(sorted(wk), have) or 'אין'}"
                          f"{f' · {focus_k}: {_t(focus)}' if focus else ''}</sub>")
    _details(w, "פירוט הממדים לפי שיעורים", detail)

    # recurring recommendations
    w('<a id="sec-recs"></a>\n')
    _kicker(w, "המלצות חוזרות")
    w("### ההמלצות שהינשוף חזר עליהן הכי הרבה\n")
    w(f"<sub>כל ריבוע הוא שיעור, מימין לשמאל: שיעורים {nums[0]} עד {nums[-1]}. ■ ההמלצה עלתה בשיעור.</sub>\n")
    for r in recs[:3]:
        w(f"{_c(_t(r['name']), TEAL, bold=True)} · <sub>{_reach(len(r['lessons']), len(nums))}</sub>  ")
        w(f"{_strip(r['lessons'], nums)}  ")
        w(f"{r.get('note', '')}\n")
    if recs:
        top = max(len(r["lessons"]) for r in recs)
        _details(w, "כל ההמלצות לפי שכיחות", ["| המלצה | | שיעורים |", "| --- | --- | --- |"] + [
            f"| {_t(r['name'])} | {_bar(100 * len(r['lessons']) / top, 12, TEAL)} **{len(r['lessons'])}** | {_lesson_links(r['lessons'], have)} |"
            for r in recs])

    # adoption
    w('<a id="sec-adopt"></a>\n')
    _kicker(w, "מעקב אימוץ")
    w("### אילו המלצות של הינשוף אומצו בפועל?\n")
    w("אימוץ מסומן כשנצפתה פרקטיקה תואמת בשיעור מאוחר יותר. זהו מתאם תצפיתי, לא הוכחה שההמלצה גרמה לשינוי.\n")
    w(" · ".join(f"{_status(s)} **{c[s]}**" for s in ("yes", "part", "no", "unk") if c.get(s)) + "\n")
    w("| המלצה | סטטוס |")
    w("| --- | --- |")
    for a in A["adopt"]:
        w(f"| {_t(a['rec'])} | {_status(a['status'])} |")
    w("")
    _details(w, "העדות לכל המלצה", ["| המלצה | עדות | הומלצה בשיעורים |", "| --- | --- | --- |"] + [
        f"| {_t(a['rec'])} | {_t(a['evidence'])} | {_lesson_links([int(x) for x in re.findall(r'[0-9]+', str(a['lessons']))], have)} |"
        for a in A["adopt"]])

    # growth
    if growth:
        w('<a id="sec-growth"></a>\n')
        _kicker(w, "התפתחות")
        w("### ממדים שבהם נצפה שיפור\n")
        w("| ממד | ביטחון |")
        w("| --- | --- |")
        for g in growth:
            w(f"| {_c('↑', TEAL, bold=True)} **{_t(g['dim'])}** | {_c(_t(g['confidence']), TEAL if 'גבוה' in g['confidence'] else SLATE)} |")
        w("")
        _details(w, "המצב בתחילת הסמסטר ובסופו",
                 [f"- **{_t(g['dim'])}**  \n  לפני: {g['before']}  \n  אחרי: {g['after']}" for g in growth])

    # next
    w('<a id="sec-next"></a>\n')
    _kicker(w, "להמשך")
    w(f"### מה הינשוף ממליץ להמשך: {HEB_COUNT.get(len(nxt), len(nxt))} שינויים קבועים\n")
    if nxt:
        _card_table(w, [_pill(_t(x["time"]), "#92400e", "#fef3c7") for x in nxt],
                    [[f"**{_t(x['title'])}**" for x in nxt], [_t(x["text"]) for x in nxt]])

    # lesson index
    _kicker(w, "הדוחות המלאים")
    w("### השיעורים\n")
    w("| שיעור | נושא | משך | חוזקה בולטת |")
    w("| --- | --- | --- | --- |")
    for l in lessons:
        w(f"| [**{l['n']}**](#l{l['n']}) | {_t(_short_title(l['title'], A['course']['name']))} | "
          f"{_hm(_dur_secs(l['duration']))} | {_t(l['outstanding']['title'])} |")
    w("")


def _report_learned(w, learned, hub, have):
    w("---\n")
    w('<a id="learned"></a>\n')
    _kicker(w, "דוח 03", AMBER)
    w(f"## {_c('מה למדו', AMBER)}\n")
    if not learned:
        w("> **חסר פידבק סטודנטים לבניית הדוח.** כדי לדעת מה הסטודנטים לקחו מהקורס נדרשים נתוני למידה: חידונים, הערכות ושאלות לצ'אטבוט.\n")
        return
    if learned.get("summary"):
        w(f"> **תמונת מצב:** {learned['summary']}\n")
    if learned.get("kpis"):
        _kpi_table(w, [(k["value"], k["label"]) for k in learned["kpis"]], AMBER)
    if learned.get("struggles"):
        _kicker(w, "קשיים")
        w("### במה מתקשים\n")
        w("| נושא | סוג | עדות | המלצה |")
        w("| --- | --- | --- | --- |")
        for s in learned["struggles"]:
            w(f"| **{_t(s['topic'])}**<br><sub>{_t(s.get('meta', ''))}</sub> | {_t(s.get('kind', ''))} | "
              f"{_t(s.get('evidence', ''))} | {_t(s.get('rec', ''))} |")
        if learned.get("struggle_pattern"):
            w(f"\n> **דפוס משותף:** {learned['struggle_pattern']}")
        w("")
    if learned.get("worked"):
        _kicker(w, "הצלחות")
        w("### מה עבד בעקביות\n")
        w("| | נושא | |")
        w("| --- | --- | --- |")
        for x in learned["worked"]:
            w(f"| {_c(_t(x['value']), TEAL, bold=True)} | {_t(x['topic'])} | <sub>{_t(x.get('note', ''))}</sub> |")
        w("")
        if learned.get("worked_lessons"):
            link = lambda n: f"[שיעור {n}](#l{n})" if n in have else f"שיעור {n}"  # lessons 1-3 may have no report
            w("שיעורים שעבדו טוב: " + " · ".join(f"{link(x['lesson'])} (**{x['score']}**)"
                                                 for x in learned["worked_lessons"]) + "\n")
        if learned.get("worked_note"):
            w(f"> **המלצה:** {learned['worked_note']}\n")
    gap = learned.get("gap") or {}
    if gap.get("bars"):
        _kicker(w, "פער")
        w(f"### {(hub or {}).get('gap_title', 'פער הוראה-למידה')}\n")
        w("| | | |")
        w("| --- | --- | --- |")
        for i, b in enumerate(gap["bars"]):
            col = TEAL if i == 0 else AMBER
            w(f"| {_t(b['label'])} | {_c(b['value'], col, bold=True)} | {_bar(b['value'], color=col)} |")
        w("")
        if gap.get("note"):
            w(f"> {gap['note']}\n")
    if learned.get("prior"):
        _kicker(w, "ידע מוקדם")
        w("### פערי ידע מוקדם\n")
        for p in learned["prior"]:
            w(f"- **{_t(p['title'])}** · <sub>{p.get('students')} סטודנטים</sub>  \n  {p.get('desc', '')}"
              + (f"  \n  ↩ {p['fix']}" if p.get("fix") else ""))
        w("")
    if learned.get("risk"):
        _kicker(w, "סיכון")
        w("### סטודנטים בסיכון\n")
        risk_col = lambda k: ORANGE if "גבוה" in k else AMBER if "בינוני" in k else TEAL
        w("| " + " | ".join(_c(v, risk_col(k), bold=True) for k, v in learned["risk"].items()) + " |")
        w("| " + " | ".join(":-:" for _ in learned["risk"]) + " |")
        w("| " + " | ".join(_t(k) for k in learned["risk"]) + " |\n")
        w("<sub>הפירוט האישי זמין למרצה במערכת Aaron ואינו נכלל בדוח.</sub>\n")


def _lesson(w, l, i, lessons, A, dims, taught, learned, has_hub):
    n = l["n"]
    prev = lessons[i - 1] if i > 0 else None
    nxt = lessons[i + 1] if i + 1 < len(lessons) else None
    w("---\n")
    w(f'<a id="l{n}"></a>\n')
    nav = [f"[→ חזרה לסיכום הקורס](#{'overview' if has_hub else 'how'})"]
    if prev:
        nav.append(f"[→ שיעור {prev['n']}](#l{prev['n']})")
    if nxt:
        nav.append(f"[שיעור {nxt['n']} ←](#l{nxt['n']})")
    w(f"<sub>{' · '.join(nav)}</sub>\n")
    date = ".".join(reversed(l["date"].split("-"))) if l.get("date") else ""
    _kicker(w, " · ".join(x for x in (f"שיעור {n}", date, f"{_hm(_dur_secs(l['duration']))} שעות",
                                      f"{i + 1} מתוך {len(lessons)} שיעורים מתועדים") if x))
    w(f"### {n} · {l['title']}\n")
    if l.get("message"):
        w(f"{l['message']}\n")

    easy = sum(1 for a in l["actions"] if a["level"] == "easy")
    _card_table(w, ["ביצוע בולט", f"[פרקטיקות מוצלחות](#l{n}-p)", f"[הזדמנויות לשיפור](#l{n}-o)", f"[פעולות לשיעור הבא](#l{n}-a)"], [
        [_c(_t(l["outstanding"]["title"]), TEAL, bold=True), _c(len(l["practices"]), TEAL, bold=True),
         _c(len(l["opportunities"]), AMBER, bold=True), _c(len(l["actions"]), BLUE, bold=True)],
        ["", f"<sub>{_t(' · '.join(p['title'] for p in l['practices']))}</sub>",
         f"<sub>{_t(' · '.join(o['title'] for o in l['opportunities']))}</sub>", f"<sub>{easy} קלות ליישום</sub>"],
    ])

    scores, avg = _learned_scores(learned), _course_avg(learned)
    if n in scores:
        w(f"> **מה למדו:** ממוצע ההערכה בשיעור הזה {_score(scores[n], avg)}"
          + (f", מול {avg:g} בקורס כולו." if avg is not None else ".") + "\n")

    t = (taught or {}).get(n)
    if t:
        _kicker(w, "מה לימדתי בשיעור")
        w("#### מבנה השיעור\n")
        if t.get("untitled"):
            w("_אין חלוקה לנושאים בדוח השיעור._\n")
        else:
            for k, s in enumerate(t["sections"], 1):
                title = _t(s["title"]) or "_ללא כותרת בדוח השיעור_"
                w(f"{k}. {'_' + title + '_' if s['admin'] else title} · <sub>{_mins(s['secs'])} דק'</sub>")
            w("")
        if t.get("challenging"):
            _details(w, f"נושאים מאתגרים בשיעור ({len(t['challenging'])})", [
                f"- **{_t(c['title'])}**  \n  {c['why']}" + (f"  \n  _הצעה: {c['suggestion']}_" if c.get("suggestion") else "")
                for c in t["challenging"]])
        if t.get("examples"):
            _details(w, f"דוגמאות מהשיעור ({len(t['examples'])})", [f"- **{_t(e['topic'])}:** {e['example']}" for e in t["examples"]])
        if t.get("interactions"):
            _details(w, f"יומן אינטראקציות בכיתה ({len(t['interactions'])})",
                     [f"- `{_t(x['time'])}` **{_t(x['type'].replace('_', ' '))}** {x['desc']}" for x in t["interactions"]])
        qs = t.get("questions") or {}
        if qs.get("basic") or qs.get("advanced"):
            _details(w, "שאלות לחזרה", ["**בסיס**\n"] + [f"{k}. {q}" for k, q in enumerate(qs.get("basic", []), 1)]
                     + ["\n**מתקדם**\n"] + [f"{k}. {q}" for k, q in enumerate(qs.get("advanced", []), 1)])

    # this lesson on the dimension map
    s_ids, w_ids = set(), set()
    for k, ids in A["item_dims"].items():
        m = re.match(r"^(\d+)([OPW])", k)
        if int(m.group(1)) == n:
            (w_ids if m.group(2) == "W" else s_ids).update(ids)
    _kicker(w, "השיעור על מפת הממדים")
    w("#### מה בלט בשיעור הזה\n")
    for v in dims["vectors"]:
        ds = [d for d in dims["dims"] if d["v"] == v["id"]]
        parts = []
        for label, pick in (("חוזקה", lambda d: d["id"] in s_ids and d["id"] not in w_ids),
                            ("מקום לשיפור", lambda d: d["id"] in w_ids and d["id"] not in s_ids),
                            ("שניהם", lambda d: d["id"] in s_ids and d["id"] in w_ids)):
            names = [d["he"] for d in ds if pick(d)]
            fg, bg = {"חוזקה": ("#ffffff", TEAL), "מקום לשיפור": ("#92400e", "#fef3c7"), "שניהם": ("#1e3a8a", "#dbeafe")}[label]
            if names:
                parts.append(f"{label}: " + " ".join(_pill(_t(x), fg, bg) for x in names))
        w(f"- **{_t(v['he'])}** · " + (" · ".join(parts) or "<sub>לא עלה בשיעור</sub>"))
    w("")

    dim_he = {d["id"]: d["he"] for d in dims["dims"]}
    tags = lambda key: " · ".join(dim_he[x] for x in A["item_dims"].get(key, []) if x in dim_he)
    o = l["outstanding"]
    _kicker(w, "ביצוע בולט")
    w(f"#### {_c(_t(o['title']), TEAL)}\n")
    if tags(f"{n}O"):
        w(f"<sub>{_t(tags(f'{n}O'))}</sub>\n")
    if o.get("body"):
        w(f"{o['body']}\n")
    if o.get("evidence"):
        w(f"> _{o['evidence']}_\n")
    if l.get("vision"):
        _details(w, "כיוון צמיחה לטווח ארוך", [l["vision"]])

    def items(kind, lst, key):
        for k, it in enumerate(lst):
            body = []
            if tags(f"{n}{key}{k}"):
                body.append(f"<sub>{_t(tags(f'{n}{key}{k}'))}</sub>\n")
            if it.get("desc") and it["desc"] != it["title"]:
                body.append(it["desc"] + "\n")
            if kind == "prac" and it.get("why"):
                body.append(f"**למה זה חשוב:** {it['why']}\n")
            if kind == "opp" and it.get("solution"):
                body.append(f"**מה אפשר לעשות:** {it['solution']}\n")
            if kind == "opp" and it.get("benefit"):
                body.append(f"**התועלת:** {it['benefit']}\n")
            if it.get("evidence"):
                body.append(f"> _{it['evidence']}_")
            _details(w, it["title"], body)

    w(f'<a id="l{n}-p"></a>\n')
    w("#### פרקטיקות מוצלחות\n")
    items("prac", l["practices"], "P")
    w(f'<a id="l{n}-o"></a>\n')
    w("#### הזדמנויות לשיפור\n")
    items("opp", l["opportunities"], "W")
    w(f'<a id="l{n}-a"></a>\n')
    w("#### פעולות מומלצות לשיעור הבא\n")
    if l["actions"]:
        w("| רמה | פעולה |")
        w("| --- | --- |")
        for a in l["actions"]:
            lvl = {"easy": _pill("קל", "#115e59", "#ccfbf1"), "medium": _pill("בינוני", "#92400e", "#fef3c7")}.get(a["level"], "")
            w(f"| {lvl} | {_t(a['text'])}" + (f"<br><sub>{_t(a['effort'])}</sub>" if a.get("effort") else "") + " |")
        w("")
    else:
        w("_אין נתונים בדוח._\n")


# ---------- entry point ----------

def render_md(lessons, analysis, dims, taught=None, learned=None, rtl=True):
    A, out = analysis, []
    w = out.append
    noun = A["course"].get("student_noun") or "סטודנטים"
    has_hub = bool(A.get("hub") and (taught or learned))
    if rtl:
        w('<div dir="rtl">\n')
    if has_hub:
        tabs = ([("overview", "סקירה")] + ([("taught", "מה לימדתי")] if taught else [])
                + [("how", "איך לימדתי"), ("learned", "מה למדו")])
        w("**AaronOwl** · " + " · ".join(f"[{he}](#{i})" for i, he in tabs) + "\n")
        _overview(w, A, lessons, taught, learned)
        if taught:
            _report_taught(w, A, lessons, taught, noun)
    _report_how(w, A, lessons, dims, has_hub)
    if has_hub:
        _report_learned(w, learned, A.get("hub"), {l["n"] for l in lessons})
    for i, l in enumerate(lessons):
        _lesson(w, l, i, lessons, A, dims, taught, learned, has_hub)
    w("---\n\n<sub>דוח פדגוגי מבית **AaronOwl** · aaronowl.com</sub>\n")
    if rtl:
        w("</div>\n")
    return "\n".join(out)
