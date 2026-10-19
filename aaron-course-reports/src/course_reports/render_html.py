"""Render the single-file HTML report from template.html."""
import base64
import html
import json
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

HEB_COUNT = {3: "שלושה", 4: "ארבעה", 5: "חמישה"}
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp"}


def logo_data_uri(path):
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"logo file not found: {path}")
    mime = LOGO_TYPES.get(p.suffix.lower())
    if not mime:
        raise SystemExit(f"logo must be one of {sorted(LOGO_TYPES)}")
    data = p.read_bytes()
    if len(data) > 2_000_000:
        print("warning: logo is over 2MB; a smaller export keeps the report light", file=sys.stderr)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def seal_svg(logo):
    """Round AaronOwl stamp: ring text around the logo (or a wordmark when no logo is given)."""
    center = (f'<clipPath id="sealclip"><circle cx="60" cy="60" r="32"/></clipPath>'
              f'<circle cx="60" cy="60" r="32" fill="#ffffff"/>'
              f'<image href="{logo}" x="34" y="35" width="52" height="52" preserveAspectRatio="xMidYMid meet" clip-path="url(#sealclip)"/>'
              if logo else
              '<text x="60" y="58" text-anchor="middle" font-family="Heebo, Arial, sans-serif" font-size="15" font-weight="700" fill="var(--seal-ink)">Aaron</text>'
              '<text x="60" y="75" text-anchor="middle" font-family="Heebo, Arial, sans-serif" font-size="15" font-weight="400" fill="var(--seal-ring)">Owl</text>')
    return ('<svg class="seal" viewBox="0 0 120 120" role="img" aria-label="AaronOwl">'
            '<defs><path id="sealring" d="M60,60 m-45,0 a45,45 0 1,1 90,0 a45,45 0 1,1 -90,0"/></defs>'
            '<circle cx="60" cy="60" r="58" fill="var(--seal-fill)"/>'
            '<circle cx="60" cy="60" r="54" fill="none" stroke="var(--seal-ring)" stroke-width="1.4"/>'
            '<circle cx="60" cy="60" r="36" fill="none" stroke="var(--seal-ring)" stroke-width="1"/>'
            '<text font-family="Heebo, Arial, sans-serif" font-size="9.5" font-weight="700" fill="var(--seal-ring)" direction="ltr">'
            '<textPath href="#sealring" textLength="276" lengthAdjust="spacing">AARONOWL • TEACHING INSIGHTS • AARONOWL • </textPath></text>'
            + center + '</svg>')


def seal_mini(logo):
    inner = (f'<image href="{logo}" x="6" y="6.5" width="24" height="24" preserveAspectRatio="xMidYMid meet"/>'
             if logo else
             '<text x="18" y="22.5" text-anchor="middle" font-family="Heebo, Arial, sans-serif" font-size="11" font-weight="700" fill="var(--seal-ink)">AO</text>')
    bg = "#ffffff" if logo else "var(--seal-fill)"
    return (f'<svg class="seal-mini" viewBox="0 0 36 36" aria-hidden="true">'
            f'<circle cx="18" cy="18" r="17" fill="{bg}" stroke="var(--seal-fill)" stroke-width="1.5"/>{inner}</svg>')


# Heebo (SIL OFL 1.1, assets/heebo-OFL.txt), embedded so the report opens offline with no network requests
FONT_SUBSETS = {"hebrew": "U+0307-0308, U+0590-05FF, U+200C-2010, U+20AA, U+25CC, U+FB1D-FB4F",
                "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
                         "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"}


def font_face():
    out = []
    for sub, rng in FONT_SUBSETS.items():
        data = base64.b64encode((ASSETS / f"heebo-{sub}.woff2").read_bytes()).decode()
        out.append(f"@font-face {{ font-family: 'Heebo'; font-style: normal; font-weight: 400 900; font-display: swap; "
                   f"src: url(data:font/woff2;base64,{data}) format('woff2'); unicode-range: {rng}; }}")
    return "\n".join(out)


def render(lessons, analysis, dims, standalone, logo="", taught=None, learned=None):
    t = (ASSETS / "template.html").read_text(encoding="utf-8")
    e = html.escape
    insights = "\n".join(
        f'      <li><div><b>{e(i["title"])}</b><span>{e(i["text"])}</span></div></li>'
        for i in analysis["insights"])
    nxt = "\n".join(
        f'      <article><span class="time num">{e(x["time"])}</span><h3>{e(x["title"])}</h3><p>{e(x["text"])}</p></article>'
        for x in analysis["next"])
    n_ins, n_next = len(analysis["insights"]), len(analysis["next"])

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    reps = {
        "__TITLE__": e(analysis["course"]["title"]),
        "__FONT_FACE__": font_face(),
        "__HERO_EYEBROW__": e(analysis["hero"]["eyebrow"]),
        "__HERO_H1__": e(analysis["hero"]["h1"]),
        "__HERO_SUB__": e(analysis["hero"]["sub"]),
        "__INSIGHTS_HEAD__": f'{HEB_COUNT.get(n_ins, n_ins)} דברים שעולים מהדוחות',
        "__INSIGHTS__": insights,
        "__NEXT_HEAD__": f'מה הינשוף ממליץ להמשך: {HEB_COUNT.get(n_next, n_next)} שינויים קבועים',
        "__SEAL__": seal_svg(logo),
        "__SEAL_MINI__": seal_mini(logo),
        "__NEXT__": nxt,
        "__ANALYSIS__": js(analysis),
        "__DIMS__": js(dims),
        "__DATA__": js(lessons),
        "__TAUGHT__": js(taught) if taught else "null",
        "__LEARNED__": js(learned) if learned else "null",
        "__LEARNED_HTML__": js(learned.get("_html", "")) if learned else "null",
    }
    for k, v in reps.items():
        if k not in t:
            raise SystemExit(f"template.html is missing placeholder {k}")
        t = t.replace(k, v)
    if standalone:
        t = ('<!doctype html>\n<html lang="he" dir="rtl">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
             '<style>[hidden]{display:none!important}body{margin:0}img{max-width:100%}</style>\n'
             + t.replace("</style>", "</style>\n</head>\n<body>", 1) + "\n</body>\n</html>\n")
    return t


