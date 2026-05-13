"""
Post-lesson email notification generator.

Reads from smart_insights.json (preferred) or teaching_snapshot.md / output.md
and produces email_notification.html + email_notification.txt in the artifact dir.

Usage:
    from teacher_side.email_generator import generate_and_save_email

    generate_and_save_email(
        artifact_dir="/path/to/output",
        teacher_name="דנה",
        course_name="פסיכולוגיה מבוא",
        lecture_number=4,
        date="28/04/2026",
        app_url="https://app.hinshuf.ai",  # optional
    )
"""

import os
import re
import json
import base64
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_ASSETS_DIR = Path(__file__).parent / "assets"
_LOGO_PATH = _ASSETS_DIR / "aaronowl-logo.png"


def _logo_base64() -> str:
    """Return the logo as a base64 data URI, or empty string if file missing."""
    if _LOGO_PATH.exists():
        data = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"
    return ""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EmailData:
    teacher_name: str = ""
    course_name: str = ""
    lecture_number: Optional[int] = None
    date: str = ""
    title: str = ""
    interaction_count: int = 0
    overall_assessment: str = ""
    duration: str = ""
    insight_category: str = ""   # label for "insight of the week"
    insight_text: str = ""       # the insight body
    insight_emoji: str = ""      # decorative emoji for the category
    language: str = "Hebrew"
    is_rtl: bool = True
    app_url: str = ""


# ---------------------------------------------------------------------------
# Artifact readers
# ---------------------------------------------------------------------------

def _is_hebrew(text: str) -> bool:
    return any('א' <= c <= 'ת' for c in text)


def _read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _find_md_file(artifact_dir: str, *candidates: str) -> str:
    for name in candidates:
        content = _read_file(os.path.join(artifact_dir, name))
        if content:
            return content
    return ""


def _extract_title_from_md(md_content: str) -> str:
    """
    Extract the lesson title. Tries (in order):
    1. HTML <h2> tag (used in output.md for the lesson heading)
    2. First markdown ## heading that looks like a real title (contains course/topic words)
    3. First ## heading overall
    4. H1 heading
    """
    # 1. HTML <h2> — output.md embeds the title this way
    m = re.search(r'<h2[^>]*>([^<]+)</h2>', md_content)
    if m:
        return m.group(1).strip()

    # 2 & 3. Markdown ## headings — skip generic section names
    _generic = {"class structure", "examples from class", "class interactions",
                "challenging topics", "questions for students",
                "outstanding performance", "successful practices",
                "opportunities for enhancement", "recommended actions",
                "long-term growth opportunity", "teaching snapshot"}
    for m in re.finditer(r'^##\s+(.+)$', md_content, re.MULTILINE):
        candidate = m.group(1).strip()
        if candidate.lower() not in _generic:
            return candidate

    # 4. H1
    m = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    if m:
        return m.group(1).strip()

    return ""


def _extract_assessment_from_snapshot_md(md_content: str) -> str:
    """Pull המסר המרכזי text from teaching_snapshot.md."""
    m = re.search(r'המסר המרכזי[:\s]*</strong>\s*(.+?)</p>', md_content, re.DOTALL)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1))
        return text.strip()
    return ""


def _extract_duration_from_snapshot_md(md_content: str) -> str:
    m = re.search(r'משך השיעור[:\s]*</strong>\s*([0-9:]+)', md_content)
    if m:
        return m.group(1).strip()
    return ""


def _count_interactions_from_output_md(md_content: str) -> int:
    """Count data rows in the Class Interactions table."""
    section = re.search(
        r'## Class Interactions.+?(<table\b.*?</table>)',
        md_content, re.DOTALL | re.IGNORECASE
    )
    if not section:
        return 0
    rows = re.findall(r'<tr\b', section.group(1))
    return max(0, len(rows) - 1)  # subtract header row


def _build_insight_pool(insights: dict, is_hebrew: bool) -> list[dict]:
    """
    Build a flat pool of insight items from smart_insights.json.
    Each entry has keys: category, text, emoji.
    """
    pool = []

    # Outstanding Performance (top_strength)
    ts = insights.get("top_strength", {})
    if ts.get("description"):
        pool.append({
            "category": "ביצוע מצטיין" if is_hebrew else "Outstanding Performance",
            "text": ts["description"],
            "emoji": "⭐",
        })

    # Successful Practices (preserve)
    for item in insights.get("preserve", []):
        if item.get("strength"):
            dim = item.get("dimension", "")
            pool.append({
                "category": f"שמור על זה – {dim}" if is_hebrew else f"Keep Doing – {dim}",
                "text": item["strength"],
                "emoji": "✅",
            })

    # Opportunities for Enhancement (growth_opportunities)
    for item in insights.get("growth_opportunities", []):
        if item.get("opportunity"):
            dim = item.get("dimension", "")
            pool.append({
                "category": f"הזדמנות לשיפור – {dim}" if is_hebrew else f"Enhancement Opportunity – {dim}",
                "text": item["opportunity"],
                "emoji": "💡",
            })

    # Action Items (priority_actions)
    for item in insights.get("priority_actions", []):
        if item.get("action"):
            pool.append({
                "category": "פעולה מומלצת" if is_hebrew else "Recommended Action",
                "text": item["action"],
                "emoji": "🎯",
            })

    return pool


def _pick_insight(pool: list[dict], seed: str) -> Optional[dict]:
    """Deterministic pick: same lesson always gets the same insight."""
    if not pool:
        return None
    rng = random.Random(seed)
    return rng.choice(pool)


def read_artifacts(artifact_dir: str) -> dict:
    """
    Extract email-relevant data from artifact files.
    JSON takes priority; MD files fill any gaps.
    Returns a dict with keys: title, interaction_count, overall_assessment,
    duration, is_rtl, language.
    """
    result: dict = {}

    # --- smart_insights.json (structured, preferred) ---
    json_path = os.path.join(artifact_dir, "smart_insights.json")
    insights = {}
    raw_json = _read_file(json_path)
    if raw_json:
        try:
            insights = json.loads(raw_json)
        except json.JSONDecodeError:
            pass

    if insights:
        result["overall_assessment"] = insights.get("overall_assessment", "")

    # --- output.md / lecturer_report.md (interactions + title) ---
    output_md = _find_md_file(artifact_dir, "output.md", "lecturer_report.md")
    if output_md:
        result.setdefault("title", _extract_title_from_md(output_md))
        result["interaction_count"] = _count_interactions_from_output_md(output_md)

    # --- teaching_snapshot.md (title, assessment fallback, duration) ---
    snapshot_md = _find_md_file(artifact_dir, "teaching_snapshot.md")
    if snapshot_md:
        result.setdefault("title", _extract_title_from_md(snapshot_md))
        result.setdefault("overall_assessment", _extract_assessment_from_snapshot_md(snapshot_md))
        result["duration"] = _extract_duration_from_snapshot_md(snapshot_md)

    # --- Language detection ---
    sample = " ".join(str(v) for v in result.values())
    result["is_rtl"] = _is_hebrew(sample)
    result["language"] = "Hebrew" if result["is_rtl"] else "English"

    # --- Insight of the week ---
    if insights:
        pool = _build_insight_pool(insights, result["is_rtl"])
        seed = result.get("title", "") + result.get("duration", "")
        picked = _pick_insight(pool, seed)
        if picked:
            result["insight_category"] = picked["category"]
            result["insight_text"] = picked["text"]
            result["insight_emoji"] = picked["emoji"]

    return result


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

def _build_email_data(
    artifact_dir: str,
    teacher_name: str,
    course_name: str,
    lecture_number: Optional[int],
    date: str,
    app_url: str,
) -> EmailData:
    data = EmailData(
        teacher_name=teacher_name,
        course_name=course_name,
        lecture_number=lecture_number,
        date=date,
        app_url=app_url,
    )
    artifacts = read_artifacts(artifact_dir)
    data.title = artifacts.get("title", "")
    data.interaction_count = artifacts.get("interaction_count", 0)
    data.overall_assessment = artifacts.get("overall_assessment", "")
    data.duration = artifacts.get("duration", "")
    data.is_rtl = artifacts.get("is_rtl", True)
    data.language = artifacts.get("language", "Hebrew")
    data.insight_category = artifacts.get("insight_category", "")
    data.insight_text = artifacts.get("insight_text", "")
    data.insight_emoji = artifacts.get("insight_emoji", "")
    return data


def _lecture_line(d: EmailData) -> str:
    if d.language == "Hebrew":
        num_part = f"הרצאה מספר {d.lecture_number} " if d.lecture_number else "הרצאה "
        return f"{num_part}בקורס {d.course_name} מתאריך {d.date} עלתה לאוויר"
    else:
        num_part = f"Lecture {d.lecture_number} " if d.lecture_number else "A lecture "
        return f"{num_part}in {d.course_name} ({d.date}) is now available"


def generate_email_text(d: EmailData) -> str:
    """Plain-text version of the notification email."""
    lines = []

    if d.language == "Hebrew":
        lines.append(f"שלום {d.teacher_name}" if d.teacher_name else "שלום")
        lines.append(_lecture_line(d))
        if d.title:
            lines.append(f"נושא ההרצאה: {d.title}")
        if d.duration:
            lines.append(f"משך ההרצאה: {d.duration}")
        if d.interaction_count:
            lines.append(
                f"בהרצאה נספרו {d.interaction_count} אינטראקציות "
                "(שאלות תלמידים, מרצה ודיון)"
            )
        if d.overall_assessment:
            lines.append("")
            lines.append("הינשוף אפיין את ההוראה כ")
            lines.append(d.overall_assessment)
        if d.insight_text:
            lines.append("")
            lines.append(f"{d.insight_emoji} תובנת השבוע – {d.insight_category}")
            lines.append(d.insight_text)
        lines.append("")
        if d.app_url:
            lines.append(f"מוזמן/ת להיכנס לאפליקציה לראות עוד: {d.app_url}")
        else:
            lines.append("מוזמן/ת להיכנס לאפליקציה לראות עוד")
        lines.append("בברכה צוות הינשוף")
    else:
        lines.append(f"Hello {d.teacher_name}" if d.teacher_name else "Hello")
        lines.append(_lecture_line(d))
        if d.title:
            lines.append(f"Lecture topic: {d.title}")
        if d.duration:
            lines.append(f"Duration: {d.duration}")
        if d.interaction_count:
            lines.append(
                f"The lecture included {d.interaction_count} interactions "
                "(student questions, teacher questions, and discussions)"
            )
        if d.overall_assessment:
            lines.append("")
            lines.append("Hinshuf characterized the teaching as:")
            lines.append(d.overall_assessment)
        if d.insight_text:
            lines.append("")
            lines.append(f"{d.insight_emoji} Insight of the Week – {d.insight_category}")
            lines.append(d.insight_text)
        lines.append("")
        if d.app_url:
            lines.append(f"Visit the app to see more: {d.app_url}")
        else:
            lines.append("Visit the app to see more")
        lines.append("Best regards, The Hinshuf Team")

    return "\n".join(lines)


def generate_email_html(d: EmailData) -> str:
    """HTML email suitable for embedding in a mail body."""
    dir_attr = 'rtl' if d.is_rtl else 'ltr'
    align = 'right' if d.is_rtl else 'left'

    logo_src = _logo_base64()
    logo_img = (
        f"<img src='{logo_src}' alt='AaronOwl' height='48' "
        f"style='display:block; height:48px; width:auto;'>"
        if logo_src else ""
    )

    greeting = f"שלום {d.teacher_name}" if d.language == "Hebrew" else f"Hello {d.teacher_name}"
    if not d.teacher_name:
        greeting = "שלום" if d.language == "Hebrew" else "Hello"

    lecture_line = _lecture_line(d)

    topic_line = ""
    if d.title:
        label = "נושא ההרצאה" if d.language == "Hebrew" else "Lecture topic"
        topic_line = f"<p style='margin:4px 0;'><strong>{label}:</strong> {d.title}</p>"

    duration_line = ""
    if d.duration:
        label = "משך ההרצאה" if d.language == "Hebrew" else "Duration"
        duration_line = f"<p style='margin:4px 0;'><strong>{label}:</strong> {d.duration}</p>"

    interactions_line = ""
    if d.interaction_count:
        if d.language == "Hebrew":
            interactions_line = (
                f"<p style='margin:4px 0;'>בהרצאה נספרו "
                f"<strong>{d.interaction_count}</strong> אינטראקציות "
                f"(שאלות תלמידים, מרצה ודיון)</p>"
            )
        else:
            interactions_line = (
                f"<p style='margin:4px 0;'>The lecture included "
                f"<strong>{d.interaction_count}</strong> interactions "
                f"(student questions, teacher questions, and discussions)</p>"
            )

    assessment_block = ""
    if d.overall_assessment:
        if d.language == "Hebrew":
            assessment_block = f"""
            <div style='margin:20px 0; padding:16px 20px;
                        border-right:4px solid #4f46e5; background:#f5f3ff;
                        border-radius:4px; direction:rtl; text-align:right;'>
              <p style='margin:0 0 8px 0; color:#6b7280; font-size:13px;'>
                הינשוף אפיין את ההוראה כ
              </p>
              <p style='margin:0; color:#1f2937; font-size:15px; line-height:1.7;'>
                {d.overall_assessment}
              </p>
            </div>"""
        else:
            assessment_block = f"""
            <div style='margin:20px 0; padding:16px 20px;
                        border-left:4px solid #4f46e5; background:#f5f3ff;
                        border-radius:4px;'>
              <p style='margin:0 0 8px 0; color:#6b7280; font-size:13px;'>
                Hinshuf characterized the teaching as:
              </p>
              <p style='margin:0; color:#1f2937; font-size:15px; line-height:1.7;'>
                {d.overall_assessment}
              </p>
            </div>"""

    insight_block = ""
    if d.insight_text:
        week_label = "תובנת השבוע" if d.language == "Hebrew" else "Insight of the Week"
        insight_block = f"""
            <div style='margin:24px 0; padding:16px 20px;
                        background:#fffbeb; border-radius:6px;
                        border:1px solid #fde68a;
                        direction:{dir_attr}; text-align:{align};'>
              <p style='margin:0 0 6px 0; font-size:12px; color:#92400e;
                        text-transform:uppercase; letter-spacing:.05em; font-weight:bold;'>
                {d.insight_emoji} {week_label}
              </p>
              <p style='margin:0 0 4px 0; font-size:12px; color:#b45309;'>
                {d.insight_category}
              </p>
              <p style='margin:0; color:#1f2937; font-size:14px; line-height:1.6;'>
                {d.insight_text}
              </p>
            </div>"""

    cta_label = "כניסה לאפליקציה" if d.language == "Hebrew" else "Open the app"
    cta_block = ""
    if d.app_url:
        cta_block = f"""
        <p style='margin:24px 0 8px 0;'>
          <a href='{d.app_url}'
             style='display:inline-block; padding:10px 24px;
                    background:#4f46e5; color:#ffffff; text-decoration:none;
                    border-radius:6px; font-size:14px;'>
            {cta_label}
          </a>
        </p>"""
    else:
        cta_text = "מוזמן/ת להיכנס לאפליקציה לראות עוד" if d.language == "Hebrew" \
            else "Visit the app to see more"
        cta_block = f"<p style='margin:20px 0 4px 0; color:#4f46e5;'>{cta_text}</p>"

    signature = "בברכה, צוות הינשוף" if d.language == "Hebrew" else "Best regards,<br>The Hinshuf Team"

    return f"""<!DOCTYPE html>
<html lang="{'he' if d.is_rtl else 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{'עדכון הרצאה' if d.language == 'Hebrew' else 'Lecture Update'} – Hinshuf</title>
</head>
<body style='margin:0; padding:0; background:#f9fafb; font-family:Arial,sans-serif;'>
  <table role='presentation' width='100%' cellpadding='0' cellspacing='0'
         style='background:#f9fafb; padding:32px 0;'>
    <tr>
      <td align='center'>
        <table role='presentation' width='560' cellpadding='0' cellspacing='0'
               style='background:#ffffff; border-radius:8px;
                      box-shadow:0 1px 4px rgba(0,0,0,0.08); overflow:hidden;'>

          <!-- Header -->
          <tr>
            <td style='background:#ffffff; padding:16px 32px;
                       border-bottom:1px solid #e5e7eb;
                       direction:{dir_attr}; text-align:{align};'>
              {logo_img}
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style='padding:28px 32px; direction:{dir_attr}; text-align:{align};
                       color:#374151; font-size:15px; line-height:1.6;'>

              <p style='margin:0 0 16px 0; font-size:16px;'>{greeting}</p>

              <p style='margin:0 0 16px 0;'>{lecture_line}</p>

              {topic_line}
              {duration_line}
              {interactions_line}

              {assessment_block}

              {insight_block}

              {cta_block}

              <p style='margin:24px 0 0 0; color:#6b7280; font-size:13px;
                         border-top:1px solid #e5e7eb; padding-top:16px;'>
                {signature}
              </p>

            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

APP_URL = "https://app.aaronowl.com/"


def generate_and_save_email(
    artifact_dir: str,
    teacher_name: str = "",
    course_name: str = "",
    lecture_number: Optional[int] = None,
    date: str = "",
    app_url: str = APP_URL,
) -> tuple[str, str]:
    """
    Read artifacts, build email content, save both formats, and return (html, text).

    Files written:
        <artifact_dir>/email_notification.html
        <artifact_dir>/email_notification.txt
    """
    d = _build_email_data(artifact_dir, teacher_name, course_name, lecture_number, date, app_url)

    html = generate_email_html(d)
    text = generate_email_text(d)

    html_path = os.path.join(artifact_dir, "email_notification.html")
    txt_path = os.path.join(artifact_dir, "email_notification.txt")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Email saved → {html_path}")
    print(f"Email saved → {txt_path}")
    return html, text


# ---------------------------------------------------------------------------
# CLI / quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    artifact_dir = sys.argv[1] if len(sys.argv) > 1 \
        else "/home/roy/FS/Dropbox/WORK/Ideas/aaron/demo/psy/output"

    html, text = generate_and_save_email(
        artifact_dir=artifact_dir,
        teacher_name="דנה",
        course_name="פסיכולוגיה מבוא",
        lecture_number=4,
        date="28/04/2026",
        app_url="https://app.aaronowl.com/",
    )

    print("\n--- PLAIN TEXT PREVIEW ---")
    print(text)