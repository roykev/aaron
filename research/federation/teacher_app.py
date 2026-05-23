#!/usr/bin/env python3
"""
Aaron Owl — Teacher Analysis Web App
=====================================
Deployed on Streamlit Community Cloud.
Teacher opens a unique URL, uploads grades, hits Run, then sends results back.

Secrets structure (set in Streamlit dashboard):

  [tokens.bio_abc123]
  course_name  = "ביולוגיה של התא - חלק א"
  features_b64 = "<base64-encoded federation CSV>"
  usage_b64    = "<base64-encoded usage_report HTML>"  # optional

  [email]
  sender    = "aaron.owl.noreply@gmail.com"
  password  = "<Gmail app password>"
  recipient = "roy.varshavsky@mail.huji.ac.il"
"""
import base64
import io
import smtplib
import sys
import zipfile
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from analysis_script import (
    als_tier_profile,
    correlation_report,
    feature_importance,
    regression_summary,
    render_html,
    select_numeric_features,
)

# ── page config ───────────────────────────────────────────────────────────────

_logo = Image.open(Path(__file__).parent / "assets" / "aaronowl-logo.png")

st.set_page_config(
    page_title="Aaron Owl — Teacher Analysis",
    page_icon=_logo,
    layout="centered",
)

st.markdown("""
<style>
  .block-container { max-width: 820px; padding-top: 2rem; }
  h1 { color: #3f51b5; }
  h2 { color: #5c6bc0; border-bottom: 2px solid #e8eaf6; padding-bottom: 4px; margin-top: 2em; }
  h3 { color: #7986cb; }
</style>
""", unsafe_allow_html=True)


# ── token validation ──────────────────────────────────────────────────────────

token = st.query_params.get("token", "")
tokens = st.secrets.get("tokens", {})

if not token or token not in tokens:
    st.error("❌ Invalid or expired link. Contact the Aaron Owl research team.")
    st.stop()

token_data = tokens[token]
course_name  = token_data["course_name"]
features_b64 = token_data["features_b64"]
usage_b64    = token_data.get("usage_b64", "")

features_df = pd.read_csv(io.BytesIO(base64.b64decode(features_b64)))
features_df["email"] = features_df["email"].str.lower().str.strip()


# ── header ────────────────────────────────────────────────────────────────────

col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(_logo, width=90)
with col_title:
    st.title("Aaron Owl — ניתוח למידה")
st.markdown(f"**קורס:** {course_name} &nbsp;|&nbsp; **סטודנטים:** {len(features_df)}")

# ── privacy banner (Hebrew) ───────────────────────────────────────────────────

st.markdown("""
<div style="background:#e8f5e9;border-right:4px solid #4caf50;padding:16px 20px;
            border-radius:0 6px 6px 0;margin:1.2em 0;direction:rtl;text-align:right">
<b style="font-size:1.05em">🔒 הציונים שלך לא נשמרים — אף פעם.</b><br><br>
כל הניתוח מתבצע בזיכרון של הדפדפן בלבד ונמחק ברגע שסוגרים את הדף.
Aaron Owl <b>אינה מאחסנת ציוני סטודנטים</b> — לא בשרת, לא בקובץ, לא בשום מקום.<br><br>
מה כן נשלח? <b>4 קבצי סטטיסטיקות מצטברות בלבד</b> — ממוצעים, מתאמים ומקדמי מודל.
לא ניתן לשחזר ציון של אף סטודנט מהנתונים האלה. זה עיצוב מכוון, לא רק מדיניות.
</div>
""", unsafe_allow_html=True)


# ── usage report ──────────────────────────────────────────────────────────────

st.header("📊 דוח שימוש — סקירת המעורבות בפלטפורמה")
st.markdown("כיצד הסטודנטים שלך השתמשו ב-Aaron Owl השנה.")

if usage_b64:
    usage_html = base64.b64decode(usage_b64).decode("utf-8")
    with st.expander("הצג דוח שימוש מלא", expanded=True):
        components.html(usage_html, height=520, scrolling=True)
    st.download_button(
        "⬇️ הורד דוח שימוש (HTML)",
        data=usage_html.encode("utf-8"),
        file_name=f"usage_report_{token}.html",
        mime="text/html",
    )
else:
    st.info("דוח שימוש לא זמין לקורס זה.")

# Download usage data as CSV (the features, without grades)
st.download_button(
    "⬇️ הורד נתוני שימוש (CSV)",
    data=base64.b64decode(features_b64),
    file_name=f"student_usage_{token}.csv",
    mime="text/csv",
    help="קובץ CSV עם נתוני השימוש של כל סטודנט — ללא ציונים.",
)

st.divider()


# ── step 1: grade template ────────────────────────────────────────────────────

st.header("שלב 1 — הורד תבנית ציונים")
st.markdown(
    "הורד את הקובץ, מלא את עמודת `final_grade` לכל סטודנט (מספר 0–100), "
    "ושמור כ-CSV."
)

template_df = pd.DataFrame({"email": features_df["email"], "final_grade": ""})
st.download_button(
    "⬇️ הורד grades_template.csv",
    data=template_df.to_csv(index=False).encode("utf-8"),
    file_name="grades_template.csv",
    mime="text/csv",
)

with st.expander("📋 דוגמה — כך ייראה הקובץ לאחר מילוי"):
    st.markdown("""
| email | final_grade |
|---|---|
| student1@post.bgu.ac.il | 87 |
| student2@post.bgu.ac.il | 74 |
| student3@post.bgu.ac.il | *(ריק — לא ניגש/ה)* |

✔ המייל חייב להתאים בדיוק לעמודה שקיבלת (אותיות קטנות, ללא רווחים).<br>
✔ שמור מ-Excel: **קובץ → שמור בשם → CSV UTF-8**.
    """, unsafe_allow_html=True)


# ── step 2: upload grades ─────────────────────────────────────────────────────

st.header("שלב 2 — העלה את הציונים שלך")
uploaded = st.file_uploader(
    "העלה את grades_template.csv לאחר המילוי",
    type=["csv"],
    key="grades_upload",
)

if not uploaded:
    st.stop()

grades_raw = pd.read_csv(uploaded)
grades_raw.columns = [c.strip().lower() for c in grades_raw.columns]

if "email" not in grades_raw.columns or "final_grade" not in grades_raw.columns:
    st.error("הקובץ חייב לכלול עמודות `email` ו-`final_grade`.")
    st.stop()

grades_raw["email"] = grades_raw["email"].str.lower().str.strip()

# ── detect fail-word entries ───────────────────────────────────────────────────
raw_str   = grades_raw["final_grade"].astype(str).str.strip()
is_empty  = raw_str.isin({"", "nan", "NaN", "None", "none", "-"})
is_number = pd.to_numeric(raw_str, errors="coerce").notna()
is_fail   = ~is_empty & ~is_number          # non-empty, non-numeric → fail word

n_fails  = int(is_fail.sum())
n_absent = int(is_empty.sum())

if n_fails > 0:
    fail_words = grades_raw.loc[is_fail, "final_grade"].value_counts().to_dict()
    st.warning(
        f"⚠️ נמצאו **{n_fails}** סטודנטים עם ציון טקסטואלי (נכשל / fail): "
        + ", ".join(f'"{w}" ({c})' for w, c in fail_words.items())
    )
    fail_score = st.number_input(
        "איזה ציון לתת להם? (ברירת מחדל: 40)",
        min_value=0, max_value=100, value=40, step=1,
        help="סטודנטים עם ציון 'נכשל' יקבלו ציון זה לצורך הניתוח.",
    )
    grades_raw.loc[is_fail, "final_grade"] = fail_score

if n_absent > 0:
    st.info(f"ℹ️ {n_absent} סטודנטים עם ציון ריק (לא ניגשו) — לא ייכללו בניתוח.")

grades_raw["final_grade"] = pd.to_numeric(grades_raw["final_grade"], errors="coerce")

# ── detect multiple sittings (duplicate emails) ───────────────────────────────
n_dupes = int(grades_raw["email"].duplicated().sum())
if n_dupes > 0:
    st.warning(
        f"⚠️ נמצאו **{n_dupes}** סטודנטים עם יותר ממועד אחד (מועד א + מועד ב)."
    )
    dup_strategy = st.radio(
        "איזה ציון לקחת לניתוח?",
        options=["min", "max", "last"],
        format_func=lambda x: {
            "min":  "הנמוך ביותר — הציון הגרוע מכל המועדים (מומלץ)",
            "max":  "הגבוה ביותר — הציון הטוב מכל המועדים",
            "last": "האחרון — השורה האחרונה בקובץ",
        }[x],
        index=0,
    )
    if dup_strategy == "min":
        grades_raw = grades_raw.groupby("email", as_index=False)["final_grade"].min()
    elif dup_strategy == "max":
        grades_raw = grades_raw.groupby("email", as_index=False)["final_grade"].max()
    else:
        grades_raw = grades_raw.drop_duplicates(subset="email", keep="last")[["email", "final_grade"]]

merged   = features_df.merge(grades_raw[["email", "final_grade"]], on="email", how="inner")
n_valid  = int(merged["final_grade"].notna().sum())
n_missed = len(grades_raw) - len(merged)

st.success(
    f"✅ הותאמו **{len(merged)}** סטודנטים "
    f"({n_valid} עם ציון תקין"
    + (f", {n_fails} נכשלו" if n_fails > 0 else "")
    + (f", {n_absent} לא ניגשו" if n_absent > 0 else "")
    + (f", {n_dupes} עם מועד חוזר" if n_dupes > 0 else "")
    + (f", {n_missed} מיילים לא נמצאו בנתוני הפלטפורמה" if n_missed else "")
    + ")"
)

if n_valid < 10:
    st.warning(
        f"רק {n_valid} סטודנטים הותאמו. "
        "בדוק שכתובות המייל זהות בדיוק לאלה שבתבנית."
    )
    st.dataframe(merged[["email", "final_grade"]].head(10))
    st.stop()


# ── step 3: run analysis ──────────────────────────────────────────────────────

st.header("שלב 3 — הרץ ניתוח")

if st.button("▶️ הרץ ניתוח", type="primary", use_container_width=True):
    with st.spinner("מחשב מתאמים, רגרסיה, Random Forest…"):
        X, y, _ = select_numeric_features(merged)
        target_stats = {
            "mean": float(y.mean()), "std": float(y.std()),
            "min": float(y.min()),   "max": float(y.max()),
        }

        corr_df = correlation_report(X, y)
        reg     = regression_summary(X, y)
        fi_df   = feature_importance(X, y)
        tier_df = als_tier_profile(merged)
        html    = render_html(corr_df, reg, fi_df, len(y), target_stats, tier_df)

        reg_txt = ""
        if reg:
            reg_txt = (
                f"Cross-validated R²: {reg['cv_r2_mean']:.4f} ± {reg['cv_r2_std']:.4f}\n"
                f"N students: {reg['n_students']}, N features: {reg['n_features']}\n\n"
                "Coefficients (standardized):\n"
            )
            for feat, coef in reg["coefficients"].items():
                reg_txt += f"  {feat:<45} {coef:+.4f}\n"

        st.session_state["results"] = {
            "corr_df": corr_df, "reg": reg, "fi_df": fi_df,
            "tier_df": tier_df, "html": html, "reg_txt": reg_txt,
            "n_students": len(y), "target_stats": target_stats,
        }

if "results" not in st.session_state:
    st.stop()

r = st.session_state["results"]
st.success(f"✅ הניתוח הושלם — {r['n_students']} סטודנטים נותחו.")

if r["tier_df"] is not None and not r["tier_df"].empty:
    st.subheader("ציון לפי רמת למידה פעילה (ALS)")
    st.dataframe(r["tier_df"], use_container_width=True, hide_index=True)

st.subheader("מתאמים חזקים עם הציון הסופי")
st.dataframe(r["corr_df"].head(10), use_container_width=True, hide_index=True)

if r["reg"]:
    cv  = r["reg"]["cv_r2_mean"]
    std = r["reg"]["cv_r2_std"]
    color = "#4caf50" if cv > 0.15 else "#ff9800" if cv > 0 else "#f44336"
    st.markdown(
        f'Ridge CV R²: <b style="color:{color}">{cv:.3f}</b> ± {std:.3f}',
        unsafe_allow_html=True,
    )

with st.expander("הצג דוח HTML מלא (לעיונך בלבד — אינו נשלח)"):
    components.html(r["html"], height=600, scrolling=True)


# ── build zip ─────────────────────────────────────────────────────────────────

def _build_zip(r: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("correlation_report.csv", r["corr_df"].to_csv(index=False))
        if r["reg_txt"]:
            zf.writestr("regression_summary.txt", r["reg_txt"])
        if r["fi_df"] is not None and not r["fi_df"].empty:
            zf.writestr("feature_importance.csv", r["fi_df"].to_csv(index=False))
        if r["tier_df"] is not None and not r["tier_df"].empty:
            zf.writestr("als_tier_profile.csv", r["tier_df"].to_csv(index=False))
    return buf.getvalue()


zip_bytes = _build_zip(r)


# ── step 4: send / download ───────────────────────────────────────────────────

st.header("שלב 4 — שלח תוצאות ל-Aaron Owl")

st.markdown("""
<div style="background:#e8eaf6;border-right:4px solid #3f51b5;padding:12px 16px;
            border-radius:0 6px 6px 0;direction:rtl;text-align:right;margin-bottom:1em">
הקובץ שיישלח מכיל <b>4 קבצי סטטיסטיקות מצטברות בלבד</b> — ממוצעי קבוצות, מתאמים ומקדמי מודל.
<b>אין בו ציון של אף סטודנט בודד.</b>
</div>
""", unsafe_allow_html=True)


def _send_email(course_name: str, zip_bytes: bytes, r: dict) -> None:
    cfg = st.secrets["email"]
    msg = MIMEMultipart()
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["recipient"]
    msg["Subject"] = f"Aaron Owl Results — {course_name}"
    msg.attach(MIMEText(
        f"Results for: {course_name}\n"
        f"Students: {r['n_students']}\n"
        f"Grade mean: {r['target_stats']['mean']:.1f}, std: {r['target_stats']['std']:.1f}\n"
        + (f"CV R²: {r['reg']['cv_r2_mean']:.3f}\n" if r["reg"] else "")
        + "\nAttached: correlation_report.csv, regression_summary.txt, "
          "feature_importance.csv, als_tier_profile.csv",
        "plain", "utf-8",
    ))
    part = MIMEBase("application", "zip")
    part.set_payload(zip_bytes)
    encoders.encode_base64(part)
    safe = course_name.replace(" ", "_").replace("/", "-")
    part.add_header("Content-Disposition", f'attachment; filename="results_{safe}.zip"')
    msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(cfg["sender"], cfg["password"])
        srv.send_message(msg)


col1, col2 = st.columns(2)

with col1:
    if st.button("📧 שלח תוצאות ל-Aaron Owl", type="primary", use_container_width=True):
        if "email" not in st.secrets:
            st.error("שליחת מייל לא מוגדרת. השתמש בכפתור ההורדה ושלח ידנית.")
        else:
            with st.spinner("שולח…"):
                try:
                    _send_email(course_name, zip_bytes, r)
                    st.success("✅ התוצאות נשלחו! תודה רבה.")
                    st.balloons()
                except Exception as exc:
                    st.error(
                        f"שליחת המייל נכשלה ({exc}). "
                        "אנא הורד את הקובץ ושלח אותו ידנית."
                    )

with col2:
    st.download_button(
        "⬇️ הורד תוצאות (גיבוי)",
        data=zip_bytes,
        file_name=f"results_{token}.zip",
        mime="application/zip",
        use_container_width=True,
    )

st.markdown("""
---
<p style="font-size:0.8em;color:#aaa;text-align:center">
Aaron Owl Learning Analytics — הנתונים שנשלחים מכילים סטטיסטיקות מצטברות בלבד,
ללא ציוני פרט. שום מידע לא נשמר לאחר סגירת הדף.
</p>
""", unsafe_allow_html=True)
