#!/usr/bin/env python3
"""
Aaron Owl — Teacher Analysis Web App (v3)
=========================================
Deployed on Streamlit Community Cloud. A teacher opens a private URL
(`…/?token=<secret code>`), confirms course metadata, fills grades, runs the v3
analysis in-session, and returns `results.json` (aggregates only).

Secrets structure (Streamlit dashboard → Secrets, TOML):

  [tokens.ceramics_ab12cd34ef56]
  course_name  = "חומרים קרמיים"
  grade_mode   = "full_ab"          # full_ab | single_a | final | pass_fail | components
  pass_mark    = 60
  features_b64 = "<base64 federation CSV (with warmup + cluster_id)>"
  usage_b64    = "<base64 usage_report HTML>"           # optional
  meta_b64     = "<base64 course_meta_<key>.json>"       # optional (pre-fills the metadata form)

  [email]
  sender="…"  password="…"  recipient="…"
"""
import base64
import io
import json
import random
import smtplib
import sys
import tempfile
import zipfile
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import analysis_script_v2 as A
from match_roster import build_index, match_one

# ── page config ───────────────────────────────────────────────────────────────
_logo = Image.open(Path(__file__).parent / "assets" / "aaronowl-logo.png")
st.set_page_config(page_title="Aaron Owl — Teacher Analysis", page_icon=_logo, layout="centered")
st.markdown("""<style>
  .block-container { max-width: 840px; padding-top: 2rem; }
  h1 { color: #3f51b5; } h2 { color: #5c6bc0; border-bottom: 2px solid #e8eaf6; padding-bottom: 4px; margin-top: 1.6em; }
</style>""", unsafe_allow_html=True)

# ── token (secret code) ───────────────────────────────────────────────────────
token = st.query_params.get("token", "")
tokens = st.secrets.get("tokens", {})
if not token or token not in tokens:
    st.error("❌ קישור לא תקין או שפג תוקפו. אנא פנה/י לצוות המחקר של Aaron Owl.\n\n"
             "Invalid or expired link — contact the Aaron Owl research team.")
    st.stop()

td = tokens[token]
course_name = td["course_name"]
grade_mode = td.get("grade_mode", "full_ab")
pass_mark = int(td.get("pass_mark", 60))
known_meta = {}
if td.get("meta_b64"):
    try:
        known_meta = json.loads(base64.b64decode(td["meta_b64"]))
    except Exception:
        known_meta = {}

work = Path(tempfile.mkdtemp())
feat_path = work / "features.csv"
feat_path.write_bytes(base64.b64decode(td["features_b64"]))
features_df = pd.read_csv(feat_path)
features_df["email"] = features_df["email"].astype(str).str.lower().str.strip()

# ── header + privacy ──────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 5])
with c1:
    st.image(_logo, width=90)
with c2:
    st.title("Aaron Owl — ניתוח למידה")
st.markdown(f"**קורס:** {course_name} &nbsp;|&nbsp; **סטודנטים בפלטפורמה:** {len(features_df)}")
st.markdown("""<div style="background:#e8f5e9;border-right:4px solid #4caf50;padding:14px 18px;
 border-radius:0 6px 6px 0;margin:1em 0;direction:rtl;text-align:right">
<b>🔒 הציונים לא נשמרים.</b> הניתוח רץ באופן חד-פעמי ונמחק בסגירת הדף. חוזרות רק
<b>סטטיסטיקות מצרפיות</b> (מתאמים, גדלי-אפקט) — לא ניתן לשחזר ציון של אף סטודנט.</div>""",
            unsafe_allow_html=True)

# ── usage report ──────────────────────────────────────────────────────────────
if td.get("usage_b64"):
    st.header("📊 דוח שימוש")
    usage_html = base64.b64decode(td["usage_b64"]).decode("utf-8")
    with st.expander("הצג דוח שימוש מלא", expanded=False):
        components.html(usage_html, height=520, scrolling=True)

# ── step 1: course metadata form ──────────────────────────────────────────────
st.header("שלב 1 — פרטי הקורס / Course metadata")
st.caption("אשר/י או השלם/י את הפרטים. משפר את הניתוח ומאפשר השוואה בין קורסים.")


def _sel(label, opts, cur):
    idx = opts.index(cur) if cur in opts else 0
    return st.selectbox(label, opts, index=idx)


m1, m2 = st.columns(2)
with m1:
    grading_type = _sel("אופן ההערכה / grading type",
                        ["exam", "coursework", "mixed", "project", "pass_fail"],
                        known_meta.get("course_type") or "exam")
    delivery_mode = _sel("אופן הוראה / delivery", ["frontal", "online", "hybrid"],
                         known_meta.get("delivery_mode") or "frontal")
    attendance = _sel("חובת נוכחות / attendance", ["optional", "mandatory", "partial"],
                      known_meta.get("attendance_required") or "optional")
with m2:
    discipline = st.text_input("תחום / discipline", known_meta.get("discipline") or "engineering")
    moed_a = st.text_input("מועד א' (YYYY-MM-DD)", str(known_meta.get("moed_a_date") or ""))
    moed_b = st.text_input("מועד ב' (אם יש)", str(known_meta.get("moed_b_date") or ""))

meta_out = {"course_type": grading_type, "grading_type": grading_type, "delivery_mode": delivery_mode,
            "attendance_required": attendance, "discipline": discipline,
            "moed_a_date": moed_a or None, "moed_b_date": moed_b or None,
            "milestones": known_meta.get("milestones", [])}

# ── step 2: grades ────────────────────────────────────────────────────────────
st.header("שלב 2 — ציונים")
GRADE_COLS = {"full_ab": ["moed_a", "moed_b"], "single_a": ["moed_a"],
              "final": ["final"], "pass_fail": ["passed"], "components": ["moed_a", "moed_b"]}
cols = GRADE_COLS.get(grade_mode, ["moed_a", "moed_b"])
grade_col = cols[0]                                   # primary outcome column (for adoption)
roster_pre = pd.read_csv(io.BytesIO(base64.b64decode(td["roster_b64"]))) if td.get("roster_b64") else None
_idx, key_by = None, "email"

if roster_pre is not None:
    # pre-mapped roster (names + emails already filled) → the teacher fills only grades
    st.success("התבנית כבר כוללת את כל הנבחנים עם שמות ואימיילים — מלא/י רק את הציונים "
               f"(**{', '.join(cols)}**), שמור/י כ-CSV והעלה/י.")
    keep = [c for c in ["name", "email"] if c in roster_pre.columns]
    tmpl = roster_pre[keep].copy()
    for c in cols:
        tmpl[c] = ""
    random.seed(0)
    demo = tmpl.copy()
    for c in cols:
        demo[c] = ["" if (c == "moed_b" and random.random() > 0.15) else random.randint(52, 96)
                   for _ in range(len(demo))]
    tmpl_bytes, demo_bytes = tmpl.to_csv(index=False).encode("utf-8"), demo.to_csv(index=False).encode("utf-8")
else:
    has_names = bool(td.get("name_email_b64"))
    if has_names:
        key_by = st.radio("איך רשומים הציונים שלך? / How is your gradebook keyed?",
                          ["email", "name"], horizontal=True,
                          format_func=lambda x: "לפי אימייל / by email" if x == "email" else "לפי שם / by name")
    if key_by == "name":
        ne_map = pd.read_csv(io.BytesIO(base64.b64decode(td["name_email_b64"])))
        _idx = build_index(ne_map, "name", "email")
        id_col, id_vals, nu = "name", list(ne_map["name"]), "סטודנט לא-משתמש"
        st.markdown(f"מלא/י את העמודות **{', '.join(cols)}** לכל סטודנט (לפי **שם**). נתאים שמות→אימיילים אוטומטית.")
    else:
        id_col, id_vals, nu = "email", list(features_df["email"]), "demo_nonuser"
        st.markdown(f"מלא/י את העמודות **{', '.join(cols)}** לכל סטודנט (לפי **אימייל**).")
    random.seed(0)
    tmpl = pd.DataFrame({id_col: id_vals, **{c: "" for c in cols}})
    _demo = [{id_col: v, **{c: ("" if (c == "moed_b" and random.random() > 0.15) else random.randint(52, 96)) for c in cols}}
             for v in id_vals]
    for i in range(4):
        _demo.append({id_col: f"{nu} {i}", **{c: ("" if c == "moed_b" else random.randint(45, 78)) for c in cols}})
    tmpl_bytes = tmpl.to_csv(index=False).encode("utf-8")
    demo_bytes = pd.DataFrame(_demo).to_csv(index=False).encode("utf-8")

d1, d2 = st.columns(2)
with d1:
    st.download_button("⬇️ הורד תבנית / template", tmpl_bytes, "grades_template.csv", "text/csv", use_container_width=True)
with d2:
    st.download_button("🧪 הורד דוגמה מלאה (dry run)", demo_bytes, "demo_grades.csv", "text/csv",
                       use_container_width=True, help="ציונים אקראיים לבדיקה — הורד/י והעלה/י.")
st.caption("💡 מלא/י ציונים בלבד; אל תשנה/י את עמודות name/email. לבדיקה מהירה — השתמש/י בקובץ הדוגמה.")
uploaded = st.file_uploader("העלה/י את הקובץ (או את קובץ הדוגמה)", type=["csv"], key="grades")
if not uploaded:
    st.stop()

# ── step 3: run ───────────────────────────────────────────────────────────────
st.header("שלב 3 — הרצת הניתוח")
if st.button("▶️ הרץ ניתוח", type="primary", use_container_width=True):
    meta_path = work / "course_metadata.yaml"
    meta_path.write_text(yaml.safe_dump(meta_out, allow_unicode=True), encoding="utf-8")
    rdf = pd.read_csv(io.BytesIO(uploaded.getvalue()))
    rdf.columns = [c.strip().lower() for c in rdf.columns]
    adoption_override = None
    if key_by == "name":
        ncol = next((c for c in rdf.columns if c in ("name", "שם", "student", "full_name")), rdf.columns[0])
        rdf["email"] = rdf[ncol].map(lambda n: match_one(n, _idx))
        gcol = grade_col if grade_col in rdf.columns else rdf.columns[-1]
        gd = pd.DataFrame({"email": rdf["email"], "grade": pd.to_numeric(rdf[gcol], errors="coerce"),
                           "is_app_user": rdf["email"].isin(set(features_df["email"]))})
        adoption_override = A.adoption_from_grades(gd)
        rdf = rdf[rdf["email"].notna()]              # matched app-users feed the main analysis
    grades_path = work / "grades.csv"
    rdf.to_csv(grades_path, index=False)
    with st.spinner("מחשב… Q1, סיכון, ערך-מוסף, אימוץ"):
        try:
            res = A.analyze(str(feat_path), str(grades_path), course_name,
                            pass_mark=pass_mark, grade_mode=grade_mode if grade_mode != "components" else None,
                            course_meta_path=str(meta_path))
            if adoption_override is not None:
                res["adoption"] = adoption_override
                if adoption_override.get("available") and not adoption_override.get("suppressed"):
                    res.setdefault("answered", [])
                    if "adoption" not in res["answered"]:
                        res["answered"].append("adoption")
            st.session_state["res"] = res
            st.session_state["meta_yaml"] = meta_path.read_text(encoding="utf-8")
        except Exception as exc:
            st.error(f"הניתוח נכשל: {exc}")
            st.stop()

if "res" not in st.session_state:
    st.stop()
res = st.session_state["res"]

# ── findings ──────────────────────────────────────────────────────────────────
st.success(f"✅ הניתוח הושלם · שאלות שנענו: {', '.join(res.get('answered', []))}")


def _fmt_ci(p, key="estimate", cikey="ci"):
    return f"{p[key]:+.2f} [{p[cikey][0]:+.2f}, {p[cikey][1]:+.2f}]" if p else "—"


q1 = (res.get("Q1") or {}).get("r_ALS_score")
va = (res.get("value_added") or {})
ad = (res.get("adoption") or {})
r1 = ((res.get("risk") or {}).get("R1_fail_a") or {})
r2 = ((res.get("risk") or {}).get("R2_no_show_a") or {})
pp = (res.get("pre_post_a") or {})

st.subheader("ממצאים עיקריים")
if q1:
    st.markdown(f"**Q1 · קשר בין למידה פעילה (ALS) לציון:** r = **{q1['r']:+.2f}** (n={q1['n']})")
if va.get("available") and not va.get("suppressed"):
    b = va.get("als_partial") or {}
    st.markdown(f"**ערך מוסף (סיבתיות):** גם בבקרה על פעילות מוקדמת + ביצועים בפלטפורמה, "
                f"ALS מנבא את הציון — β = **{b.get('beta'):+.2f} ± {b.get('se')}** "
                f"(ΔR² = {va.get('delta_r2_als'):+})")
if ad.get("available") and not ad.get("suppressed"):
    st.markdown(f"**אימוץ:** משתמשי האפליקציה {ad['mean_grade_app_users']} מול "
                f"לא-משתמשים {ad['mean_grade_non_users']} "
                f"(d = {(_ad := ad.get('cohens_d_user_minus_non') or {}).get('d')}, p = {ad.get('welch_p')})")
if not r1.get("suppressed") and r1.get("n_pos") is not None:
    st.markdown(f"**סיכון כישלון (R1):** {r1['n_pos']}/{r1['n']} נכשלו")
if pp.get("available") and not pp.get("suppressed"):
    st.markdown(f"**שינוי מעורבות אחרי הבחינה:** {pp['pre_mean']:.0f}→{pp['post_mean']:.0f} "
                f"(dz = {pp.get('cohens_dz')}, p = {pp.get('p')})")

with st.expander("results.json המלא (לעיונך — זה מה שנשלח)"):
    st.json(res)

# ── step 4: return ────────────────────────────────────────────────────────────
st.header("שלב 4 — שליחה / הורדה")
results_bytes = json.dumps(res, indent=2, ensure_ascii=False).encode("utf-8")
meta_bytes = st.session_state.get("meta_yaml", "").encode("utf-8")


def _zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("results.json", results_bytes)
        z.writestr("course_metadata.yaml", meta_bytes)
    return buf.getvalue()


def _send_email():
    cfg = st.secrets["email"]
    msg = MIMEMultipart()
    msg["From"], msg["To"] = cfg["sender"], cfg["recipient"]
    msg["Subject"] = f"Aaron Owl v3 Results — {course_name}"
    msg.attach(MIMEText(f"Results for {course_name}. answered={res.get('answered')}", "plain", "utf-8"))
    part = MIMEBase("application", "zip"); part.set_payload(_zip()); encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="results_{token}.zip"')
    msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(cfg["sender"], cfg["password"]); s.send_message(msg)


st.markdown("""<div style="background:#e8eaf6;border-right:4px solid #3f51b5;padding:10px 14px;
 border-radius:0 6px 6px 0;direction:rtl;text-align:right;margin-bottom:.8em">
מה שנשלח: <b>results.json</b> (סטטיסטיקות מצרפיות) + <b>course_metadata.yaml</b>. אין ציונים אישיים.</div>""",
            unsafe_allow_html=True)
b1, b2 = st.columns(2)
with b1:
    if st.button("📧 שלח ל-Aaron Owl", type="primary", use_container_width=True):
        if "email" not in st.secrets:
            st.error("שליחת מייל לא מוגדרת — השתמש/י בכפתור ההורדה.")
        else:
            try:
                _send_email(); st.success("✅ נשלח! תודה."); st.balloons()
            except Exception as exc:
                st.error(f"שליחה נכשלה ({exc}). הורד/י ושלח/י ידנית.")
with b2:
    st.download_button("⬇️ הורד תוצאות (zip)", _zip(), f"results_{token}.zip",
                       "application/zip", use_container_width=True)
