#!/usr/bin/env python3
"""
Aaron Owl — Build Teacher Package
===================================
Assembles everything a teacher needs into a single zip file.

What goes in the package:
    student_features_<course>_federation.csv  — usage feature vectors (no grades)
    usage_report_<course>.html               — student engagement overview
    analysis_script.py                       — runs correlation/regression locally
    grades_template.csv                      — fill in email + final_grade
    HOW_TO.html                              — step-by-step instructions

What the teacher sends back (4 files only — no individual grades):
    correlation_report.csv
    regression_summary.txt
    feature_importance.csv
    als_tier_profile.csv

Usage:
    python build_teacher_package.py --course psy
    python build_teacher_package.py --course example_course --config config.yaml
"""
import argparse
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import yaml


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).parent.parent / p
    with open(p) as f:
        return yaml.safe_load(f)


def _course_dirs(config: dict, course_key: str) -> tuple[Path, Path]:
    course_cfg = config['courses'][course_key]
    out_dir = Path(course_cfg.get('output_dir') or config['data']['output_dir'])
    fed_dir = Path(course_cfg.get('federation_dir') or config['data']['federation_dir'])
    return out_dir, fed_dir


def build_grades_template(features_csv: Path) -> str:
    df = pd.read_csv(features_csv, usecols=[0])
    email_col = df.columns[0]
    template = pd.DataFrame({email_col: df[email_col], 'final_grade': ''})
    return template.to_csv(index=False)


def build_howto_html(course_name: str, features_filename: str, course_key: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<title>Aaron Owl — מדריך הפעלה</title>
<style>
  body  {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #333; line-height: 1.7 }}
  h1   {{ color: #3f51b5 }}
  h2   {{ color: #5c6bc0; margin-top: 2em; border-bottom: 2px solid #e8eaf6; padding-bottom: 4px }}
  code, pre {{ direction: ltr; unicode-bidi: embed; font-family: monospace }}
  code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 0.95em }}
  pre  {{ background: #f5f5f5; padding: 14px 18px; border-radius: 6px; overflow-x: auto; text-align: left }}
  .box {{ background: #e8eaf6; border-right: 4px solid #3f51b5; padding: 12px 16px; margin: 1em 0; border-radius: 6px 0 0 6px }}
  .warn{{ background: #fff8e1; border-right: 4px solid #ffc107; padding: 12px 16px; margin: 1em 0; border-radius: 6px 0 0 6px }}
  .ok  {{ background: #e8f5e9; border-right: 4px solid #4caf50; padding: 12px 16px; margin: 1em 0; border-radius: 6px 0 0 6px }}
  table{{ border-collapse: collapse; width: 100% }}
  td, th {{ border: 1px solid #ddd; padding: 8px 12px; text-align: right }}
  th   {{ background: #f5f5f5 }}
  ol li {{ margin-bottom: 0.7em }}
  .example-table td, .example-table th {{ text-align: left; direction: ltr; font-family: monospace; font-size: 0.9em }}
  .example-table {{ width: auto; margin: 1em 0 }}
  .fade {{ color: #aaa }}
</style>
</head><body>

<h1>Aaron Owl — ניתוח למידה</h1>
<p>קורס: <b>{course_name}</b></p>

<div class="ok">
  <b>🔒 ערבות פרטיות — הציונים של הסטודנטים לא עוזבים את המחשב שלך.</b><br><br>
  הניתוח מתבצע <em>אצלך</em> בלבד. Aaron Owl לא מקבלת ציונים בודדים של סטודנטים.
  הדבר היחיד שתשלח/י חזרה הוא קובץ קטן של סטטיסטיקות מצטברות (ממוצעים, מתאמים) —
  שמבחינה מתמטית לא ניתן להפוך אותן לציונים של פרטים.<br><br>
  <b>זה עיצוב מכוון:</b> מידע על ציונים הוא רגיש.
  בנינו את המערכת כך שיהיה בלתי אפשרי <em>מבחינה טכנית</em> לראות את הנתונים —
  לא רק עניין של מדיניות.
</div>

<h2>מה יש בחבילה זו</h2>
<table>
  <tr><th>קובץ</th><th>תיאור</th></tr>
  <tr><td><code>{features_filename}</code></td>
      <td>נתוני שימוש של סטודנטים שנוצרו על ידי Aaron Owl. ללא ציונים — רק התנהגות בפלטפורמה.</td></tr>
  <tr><td><code>usage_report_{course_key}.html</code></td>
      <td>סקירת מעורבות הסטודנטים בפלטפורמה. פתח/י בכל דפדפן.</td></tr>
  <tr><td><code>analysis_script.py</code></td>
      <td>סקריפט Python שמחבר את הציונים שלך עם נתוני השימוש ומריץ את הניתוח.</td></tr>
  <tr><td><code>grades_template.csv</code></td>
      <td>ממולא מראש עם כתובות המייל של הסטודנטים. הוסף/י עמודת ציון סופי ושמור/י.</td></tr>
  <tr><td><code>HOW_TO.html</code></td>
      <td>הקובץ הזה.</td></tr>
</table>

<h2>שלב 1 — הגדרה חד-פעמית (5 דקות)</h2>
<p>צריך Python 3.8 ומעלה ומספר ספריות. אם יש לך אותן כבר, עבור/י לשלב 2.</p>
<pre>pip install pandas numpy scipy scikit-learn openpyxl</pre>
<p>אין Python? הורד/י בחינם מ־<a href="https://www.python.org/downloads/">python.org</a>.</p>

<h2>שלב 2 — הוסף/י את הציונים שלך</h2>
<ol>
  <li>פתח/י את <code>grades_template.csv</code> ב־Excel או בכל עורך טקסט.</li>
  <li>מלא/י את עמודת <code>final_grade</code> לכל סטודנט (מספר, 0–100).</li>
  <li>השאר/י ריק (או מחק/י את השורה) עבור סטודנטים שלא ניגשו לבחינה.</li>
  <li>שמור/י את הקובץ — שמור/י אותו בפורמט CSV.</li>
</ol>

<p><b>דוגמה — כך צריך להיראות grades_template.csv לאחר המילוי:</b></p>
<table class="example-table">
  <tr><th>email</th><th>final_grade</th></tr>
  <tr><td>avraham.cohen@university.ac.il</td><td>87</td></tr>
  <tr><td>miriam.levi@university.ac.il</td><td>74</td></tr>
  <tr><td>yosef.mizrahi@university.ac.il</td><td>91</td></tr>
  <tr><td>shira.shapiro@university.ac.il</td><td class="fade">(ריק — לא ניגשה)</td></tr>
  <tr><td>... שאר הסטודנטים ...</td><td>...</td></tr>
</table>
<p style="font-size:0.9em;color:#555">
  ✔ המייל חייב להתאים בדיוק לכתובות שבקובץ <code>grades_template.csv</code> שקיבלת.<br>
  ✔ עמודת הציון — מספר בלבד. אין צורך באחוזים, אין צורך בטקסט.<br>
  ✔ ניתן לשמור מ-Excel: <em>קובץ → שמור בשם → CSV UTF-8</em>.
</p>

<div class="warn">
  <b>🔒 השאר/י את grades_template.csv (עם הציונים) על המחשב שלך — אל תשלח/י אותו.</b>
  הסקריפט קורא את הציונים רק כדי לחשב סטטיסטיקות. הוא אינו מעביר אותם לשום מקום.
  רק 4 הקבצים המפורטים בשלב 4 משותפים — הם מכילים ממוצעי קבוצות ומקדמי מודל,
  ולא ציון בודד של אף סטודנט.
</div>

<h2>שלב 3 — הרץ/י את הניתוח</h2>
<p>פתח/י מסוף (Terminal / Command Prompt) בתיקייה שבה שמרת את קבצי החבילה, ואז הרץ/י:</p>
<pre>python analysis_script.py \\
    --features {features_filename} \\
    --grades   grades_template.csv \\
    --out      results/</pre>
<p>זה לוקח פחות מדקה. תיקיית <code>results/</code> תופיע עם הפלטים.</p>

<h2>שלב 4 — מה לשלוח חזרה</h2>

<div class="ok">
  <b>🔒 4 הקבצים האלה לא מכילים ציונים בודדים של סטודנטים.</b>
  כל קובץ מכיל רק סטטיסטיקות ברמת הקבוצה — ממוצעים, מתאמים ומקדמי מודל
  שחושבו על פני כלל הסטודנטים. לא ניתן לשחזר ציון של שום סטודנט מהם.
</div>

<p>שלח/י ל-Aaron Owl <b>רק 4 קבצים אלה</b> מתיקיית <code>results/</code>:</p>
<table>
  <tr><th>קובץ</th><th>מה הוא מכיל</th><th>שורות</th></tr>
  <tr><td><code>correlation_report.csv</code></td>
      <td>מתאם פירסון וספירמן של כל פיצ'ר פלטפורמה עם הציון הסופי.</td>
      <td>~35 שורות. ללא ערכים בודדים.</td></tr>
  <tr><td><code>regression_summary.txt</code></td>
      <td>מקדמי רגרסיה ו-R² מאומת בצלב.</td>
      <td>בלוק סיכום אחד. ללא ערכים בודדים.</td></tr>
  <tr><td><code>feature_importance.csv</code></td>
      <td>חשיבות פיצ'רים של Random Forest (משקלים יחסיים, סכום = 1).</td>
      <td>~35 שורות. ללא ערכים בודדים.</td></tr>
  <tr><td><code>als_tier_profile.csv</code></td>
      <td>ממוצע ציון לפי רמת למידה פעילה (נמוך / בינוני / גבוה).</td>
      <td><b>3 שורות בלבד</b> — ממוצעי קבוצות, לא ציונים בודדים.</td></tr>
</table>

<p><b>אל תשלח/י:</b> <code>grades_template.csv</code>, <code>analysis_report.html</code>,
או כל קובץ אחר. רק 4 הקבצים לעיל.</p>

<p>ניתן לפתוח את <code>results/analysis_report.html</code> בדפדפן לצפייה בסיכום ויזואלי
עבור הקורס שלך — קובץ זה מיועד לשימושך בלבד ואינו נשלח.</p>

<div class="box">
  <b>שאלות?</b> צרו קשר עם צוות המחקר של Aaron Owl. נשמח ללוות אתכם בתהליך.
</div>

<p>You can open <code>results/analysis_report.html</code> in your browser to see
a visual summary for your own course — this is for your use only and is not shared.</p>

<div class="box">
  <b>Questions?</b> Contact the Aaron Owl research team. We are happy to walk you through the process.
</div>

<hr>
<p style="font-size:0.8em;color:#aaa">Aaron Owl Learning Analytics — {date.today().isoformat()}</p>
</body></html>"""


def build_package(config: dict, course_key: str, out_dir: Path) -> Path:
    course_cfg = config['courses'][course_key]
    course_name = course_cfg['name']
    _, fed_dir = _course_dirs(config, course_key)
    today = date.today().strftime('%Y%m%d')

    features_filename = f'student_features_{course_key}_federation.csv'
    features_src = fed_dir / features_filename
    usage_report_src = fed_dir / f'usage_report_{course_key}.html'
    analysis_src = Path(__file__).parent / 'analysis_script.py'

    missing = [p for p in [features_src, usage_report_src, analysis_src] if not p.exists()]
    if missing:
        print(f"ERROR: Missing files: {missing}")
        sys.exit(1)

    # Staging directory
    stage = out_dir / f'teacher_package_{course_key}_{today}'
    stage.mkdir(parents=True, exist_ok=True)

    shutil.copy(features_src, stage / features_filename)
    shutil.copy(usage_report_src, stage / f'usage_report_{course_key}.html')
    shutil.copy(analysis_src, stage / 'analysis_script.py')

    # Grades template
    template_csv = build_grades_template(features_src)
    (stage / 'grades_template.csv').write_text(template_csv, encoding='utf-8')

    # How-to HTML
    howto = build_howto_html(course_name, features_filename, course_key)
    (stage / 'HOW_TO.html').write_text(howto, encoding='utf-8')

    # Zip
    zip_path = out_dir / f'teacher_package_{course_key}_{today}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in stage.iterdir():
            zf.write(f, arcname=f.name)

    shutil.rmtree(stage)
    return zip_path


def main():
    parser = argparse.ArgumentParser(description='Build teacher package zip')
    parser.add_argument('--course', required=True, help='Course key from config.yaml')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--out', default=None,
                        help='Directory to write the zip (default: federation_dir for the course)')
    args = parser.parse_args()

    config = load_config(args.config)
    if args.course not in config['courses']:
        print(f"Unknown course: {args.course!r}. Available: {list(config['courses'].keys())}")
        sys.exit(1)

    if args.out:
        out_dir = Path(args.out)
    else:
        _, fed_dir = _course_dirs(config, args.course)
        out_dir = fed_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building teacher package for: {config['courses'][args.course]['name']}")
    zip_path = build_package(config, args.course, out_dir)
    print(f"\nPackage ready: {zip_path}")
    print(f"\nContents:")
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            info = zf.getinfo(name)
            print(f"  {name:<55} {info.file_size/1024:>6.1f} KB")
    print(f"\nSend this zip to the {config['courses'][args.course]['name']} teacher.")
    print(f"Ask them to return: correlation_report.csv, regression_summary.txt,")
    print(f"                    feature_importance.csv, als_tier_profile.csv")


if __name__ == '__main__':
    main()
