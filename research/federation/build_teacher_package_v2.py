#!/usr/bin/env python3
"""
Aaron Owl — Build Teacher Package v2
====================================
Bundles everything a teacher needs to run the v2 federated analysis (Q1–Q3 +
risk + predictive) locally. Grades never leave; the teacher returns only results.json.

Package contents:
    student_features_<course>_federation.csv  — two-block (preA + postA_) feature vectors, no grades
    grades_template.csv                       — email, moed_a, moed_b  (teacher fills in)
    analysis_script_v2.py                     — runs Q1–Q3 + risk + predictive locally
    FEDERATED_QUESTIONS_SPEC.md               — what each question is + return contract
    HOW_TO.html                               — Hebrew, RTL, step-by-step

Teacher returns ONE file: results.json (aggregates only).

Usage:
    python build_teacher_package_v2.py --course bio
"""
import argparse
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent


def load_config(path):
    p = Path(path)
    if not p.is_absolute():
        p = HERE.parent / p
    with open(p) as f:
        return yaml.safe_load(f)


def grades_template(features_csv: Path) -> str:
    df = pd.read_csv(features_csv, usecols=[0])
    ecol = df.columns[0]
    return pd.DataFrame({'email': df[ecol], 'moed_a': '', 'moed_b': ''}).to_csv(index=False)


def how_to_html(course_name: str, features_name: str) -> str:
    return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<title>הוראות — {course_name}</title><style>
 body{{font:15px/1.7 "Segoe UI",Arial,sans-serif;max-width:760px;margin:30px auto;padding:0 18px;color:#1f2328}}
 h1{{font-size:22px}} h2{{font-size:17px;border-bottom:1px solid #eaecef;padding-bottom:4px;margin-top:26px}}
 code,pre{{background:#f6f8fa;border-radius:6px}} code{{padding:1px 5px}} pre{{padding:10px;overflow:auto;direction:ltr;text-align:left}}
 .box{{background:#f6fff8;border:1px solid #b9e6c4;border-radius:8px;padding:10px 14px;margin:12px 0}}
 table{{border-collapse:collapse;margin:8px 0}} td,th{{border:1px solid #eaecef;padding:5px 10px}}
 .muted{{color:#656d76}}</style></head><body>
<h1>ניתוח פדרטיבי — {course_name}</h1>
<p>תודה שאת/ה משתתף/ת. <b>הציונים שלך לא יוצאים מהמחשב שלך.</b> הסקריפט מחשב מקומית ומחזיר רק
קובץ אחד עם תוצאות מצרפיות (<code>results.json</code>) — ללא ציונים אישיים.</p>

<h2>מה יש בחבילה</h2>
<ul>
 <li><code>{features_name}</code> — נתוני שימוש בפלטפורמה (ללא ציונים).</li>
 <li><code>grades_template.csv</code> — כאן את/ה ממלא/ת את הציונים.</li>
 <li><code>analysis_script_v2.py</code> — סקריפט הניתוח.</li>
 <li><code>FEDERATED_QUESTIONS_SPEC.md</code> — הסבר על השאלות והפרטיות.</li>
</ul>

<h2>שלב 1 — מילוי הציונים</h2>
<p>פתח/י את <code>grades_template.csv</code> ומלא/י שתי עמודות לכל סטודנט:</p>
<table><tr><th>עמודה</th><th>פירוש</th></tr>
 <tr><td><code>moed_a</code></td><td>ציון מועד א' (מספר). ריק = לא ניגש/ה.</td></tr>
 <tr><td><code>moed_b</code></td><td>ציון מועד ב' (מספר), רק למי שניגש/ה שוב. אחרת — ריק.</td></tr></table>
<div class="box"><b>חשוב:</b> רק מספרים. ציון נכשל → רשום/י את המספר עצמו (למשל <code>52</code>, לא "52 נכשל").
"לא נבחן/לא השתתף" → השאר/י ריק. אל תשנה/י את עמודת <code>email</code>.</div>

<h2>שלב 2 — הרצת הניתוח</h2>
<p>בטרמינל, מתוך תיקיית החבילה (צריך Python עם <code>pandas, numpy, scipy, scikit-learn</code>):</p>
<pre>python analysis_script_v2.py \\
    --features {features_name} \\
    --grades   grades_template.csv \\
    --course   "{course_name}" \\
    --pass-mark 60 \\
    --out      results</pre>
<p class="muted">החלף/י <code>--pass-mark</code> לציון העובר בקורס שלך אם שונה מ-60.</p>

<h2>שלב 3 — החזרה</h2>
<p>שלח/י בחזרה <b>רק</b> את הקובץ <code>results/results.json</code>. הוא מכיל סטטיסטיקות מצרפיות בלבד
(מתאמים, גדלי-אפקט, AUC) — ללא ציונים אישיים. קבוצות עם פחות מ-3 סטודנטים מודחקות אוטומטית.</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', required=True)
    ap.add_argument('--config', default='config.yaml')
    a = ap.parse_args()
    cfg = load_config(a.config)
    cc = cfg['courses'][a.course]
    name = cc['name']
    fed_dir = Path(cc.get('federation_dir') or cfg['data']['federation_dir'])
    feats = fed_dir / f'student_features_{a.course}_federation.csv'
    if not feats.exists():
        raise FileNotFoundError(f"feature file not found: {feats} (run pipeline.py --course {a.course} first)")

    stamp = date.today().strftime('%Y%m%d')
    pkg = fed_dir / f'teacher_package_{a.course}_v2_{stamp}'
    pkg.mkdir(parents=True, exist_ok=True)

    shutil.copy(feats, pkg / feats.name)
    shutil.copy(HERE / 'analysis_script_v2.py', pkg / 'analysis_script_v2.py')
    shutil.copy(HERE / 'FEDERATED_QUESTIONS_SPEC.md', pkg / 'FEDERATED_QUESTIONS_SPEC.md')
    (pkg / 'grades_template.csv').write_text(grades_template(feats), encoding='utf-8')
    (pkg / 'HOW_TO.html').write_text(how_to_html(name, feats.name), encoding='utf-8')

    zpath = fed_dir / f'{pkg.name}.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pkg.iterdir()):
            z.write(f, f'{pkg.name}/{f.name}')

    n_students = sum(1 for _ in open(feats)) - 1
    print(f"Package: {pkg}")
    print(f"Zip:     {zpath}")
    print(f"Contents: {[f.name for f in sorted(pkg.iterdir())]}")
    print(f"Students in feature file: {n_students}  ·  teacher returns: results.json")


if __name__ == '__main__':
    main()
