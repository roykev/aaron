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


# per grade-mode: the template columns + their Hebrew explanation in the HOW_TO
GRADE_COLS = {
    'full_ab': [('moed_a', "ציון מועד א' (מספר). ריק = לא ניגש/ה."),
                ('moed_b', "ציון מועד ב' (מספר), רק למי שניגש/ה שוב. אחרת — ריק.")],
    'single_a': [('moed_a', "ציון מועד א' (מספר). ריק = לא ניגש/ה.")],
    'final': [('final', "הציון הסופי בקורס (מספר). אם הסטודנט/ית ניגש/ה גם למועד ב', "
                        "רשום/י את הציון הקובע (הגבוה). ריק = לא נבחן/ה כלל.")],
    'pass_fail': [('passed', "1 = עבר/ה, 0 = נכשל/ה. ריק = לא נבחן/ה.")],
}


def grades_template(features_csv: Path, mode: str = 'full_ab') -> str:
    df = pd.read_csv(features_csv, usecols=[0])
    ecol = df.columns[0]
    out = {'email': df[ecol]}
    for col, _ in GRADE_COLS[mode]:
        out[col] = ''
    return pd.DataFrame(out).to_csv(index=False)


def how_to_html(course_name: str, features_name: str,
                mode: str = 'full_ab', pass_mark: int = 60,
                final_rule: str = 'max') -> str:
    col_rows = ''.join(
        f"<tr><td><code>{c}</code></td><td>{desc}</td></tr>" for c, desc in GRADE_COLS[mode])
    # explicit mode flags for any non-default mode (auto-detect also works, but be safe)
    mode_flags = ''
    if mode != 'full_ab':
        mode_flags = f" \\\n    --grade-mode {mode}"
        if mode == 'final':
            mode_flags += f" --final-rule {final_rule}"
    return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<title>הוראות — {course_name}</title><style>
 body{{font:15px/1.7 "Segoe UI",Arial,sans-serif;max-width:760px;margin:30px auto;padding:0 18px;color:#1f2328}}
 h1{{font-size:22px}} h2{{font-size:17px;border-bottom:1px solid #eaecef;padding-bottom:4px;margin-top:26px}}
 code,pre{{background:#f6f8fa;border-radius:6px}} code{{padding:1px 5px}} pre{{padding:10px;overflow:auto;direction:ltr;text-align:left}}
 .box{{background:#f6fff8;border:1px solid #b9e6c4;border-radius:8px;padding:10px 14px;margin:12px 0}}
 table{{border-collapse:collapse;margin:8px 0}} td,th{{border:1px solid #eaecef;padding:5px 10px}}
 .muted{{color:#656d76}} ol{{padding-inline-start:22px}} ol li{{margin:6px 0}}
 details{{border:1px solid #eaecef;border-radius:8px;padding:6px 12px;margin:10px 0;background:#fbfcfd}}
 summary{{cursor:pointer;font-weight:600;color:#0969da}}</style></head><body>
<h1>ניתוח פדרטיבי — {course_name}</h1>
<p>תודה שאת/ה משתתף/ת. <b>הציונים שלך לא יוצאים מהמחשב שלך.</b> הסקריפט מחשב מקומית ומחזיר רק
קובץ אחד עם תוצאות מצרפיות (<code>results.json</code>) — ללא ציונים אישיים.</p>

<h2>שני קבצים למילוי</h2>
<p>יש רק <b>2 קבצים</b> למלא: <code>grades_template.csv</code> (הציונים) ו-<code>course_metadata.yaml</code>
(פרטי הקורס). למטה — איך. <span class="muted">Just 2 files to fill: grades + course metadata.</span></p>

<h2>שלב 1 — מילוי הציונים</h2>
<p>פתח/י את <code>grades_template.csv</code> ומלא/י את עמודות הציונים לכל סטודנט. עמודות ברירת המחדל:</p>
<table><tr><th>עמודה</th><th>פירוש</th></tr>
 {col_rows}</table>
<div class="box"><b>חשוב:</b> רק מספרים. ציון נכשל → רשום/י את המספר עצמו (למשל <code>52</code>, לא "52 נכשל").
"לא נבחן/לא השתתף" → השאר/י ריק. אל תשנה/י את עמודת <code>email</code>.
<br><b>קורס עם מטלות:</b> יש מטלות/בחינות נוספות? הוסף/י <u>עמודה לכל אחת</u> — שם העמודה זהה לשם המטלה
ב-<code>course_metadata.yaml</code>. <span class="muted">Coursework: add one column per graded item;
the column header must match the task name in the metadata file.</span></div>

<h2>שלב 2 — מטא-דאטה של הקורס / Course metadata</h2>
<div class="box">מלא/י את הקובץ <code>course_metadata.yaml</code>: <b>תאריכי בחינות</b> (מועד א'/ב'),
סוג הקורס, <b>אופן ההוראה</b> (פרונטלי / מקוון / משולב), חובת נוכחות, ורשימת מטלות. מידע זה
משפר את הניתוח ומאפשר השוואה בין קורסים. <br>
<span class="muted">Fill <code>course_metadata.yaml</code> — exam dates, course type, delivery mode
(frontal/online), attendance policy, and the graded-task list. It's not sensitive; return it with the results.</span></div>

<h2>שלב 3 — הרצת הניתוח</h2>
<p>בטרמינל, מתוך תיקיית החבילה (צריך Python עם <code>pandas, numpy, scipy, scikit-learn</code>):</p>
<pre>python analysis_script_v2.py \\
    --features    {features_name} \\
    --grades      grades_template.csv \\
    --course-meta course_metadata.yaml \\
    --course      "{course_name}"{mode_flags} \\
    --pass-mark {pass_mark} \\
    --out       results</pre>
<p class="muted">החלף/י <code>--pass-mark</code> לציון העובר בקורס שלך אם שונה מ-{pass_mark}.</p>

<div class="box"><b>רוצה לבדוק שהכל עובד קודם?</b> הרץ/י דמו על ציונים לדוגמה (מצורפים) — בלי למלא כלום:
<pre>python analysis_script_v2.py \\
    --features    {features_name} \\
    --grades      demo_grades_template.csv \\
    --course-meta demo_course_metadata.yaml \\
    --course      "{course_name}"{mode_flags} \\
    --pass-mark {pass_mark} \\
    --out       demo_results</pre>
<span class="muted">A dry run on example grades to confirm it works.</span></div>

<h2>החזרה</h2>
<p>שלח/י בחזרה שני קבצים בלבד: <code>results/results.json</code> (סטטיסטיקות מצרפיות — מתאמים,
גדלי-אפקט, AUC, ללא ציונים אישיים) ו-<code>course_metadata.yaml</code> (מטא-דאטה של הקורס, לא רגיש).
קבוצות עם פחות מ-3 סטודנטים מודחקות אוטומטית. <span class="muted">Return only
<code>results.json</code> + <code>course_metadata.yaml</code>.</span></p>

<details><summary>ניתוח אימוץ — מומלץ (רץ אוטומטית)</summary>
<p>בודק אם עצם השימוש באפליקציה קשור לציון. <b>פועל אוטומטית</b> — פשוט הוסף/י ל-<code>grades_template.csv</code>
שורות (email + ציון) של סטודנטים שניגשו לבחינה אך אינם בקובץ הנתונים (הם לא השתמשו באפליקציה). זהו.
<br><span class="muted">Adoption runs automatically — just add rows to the grades file for students who sat the
exam but aren't in the feature file (non-users). Advanced: for name-keyed rosters use
<code>match_roster.py</code> then add <code>--roster roster_matched.csv</code>.</span></p></details>

<details><summary>פרטיות — מה נשלח בחזרה</summary>
<p>הציונים נשארים על המחשב שלך. <code>results.json</code> מכיל סטטיסטיקות מצרפיות בלבד (מתאמים,
גדלי-אפקט, AUC) — ללא ציונים אישיים; קבוצות עם פחות מ-3 סטודנטים מודחקות.</p></details>

<details><summary>תוכן החבילה</summary>
<ul>
 <li><code>{features_name}</code> — נתוני שימוש (ללא ציונים).</li>
 <li><code>grades_template.csv</code>, <code>course_metadata.yaml</code> — למילוי.</li>
 <li><code>demo_grades_template.csv</code>, <code>demo_course_metadata.yaml</code> — לדמו / demo.</li>
 <li><code>analysis_script_v2.py</code>, <code>match_roster.py</code> — סקריפטים.</li>
 <li><code>FEDERATED_QUESTIONS_SPEC.md</code> — הסבר על השאלות והפרטיות.</li>
</ul></details>
</body></html>"""


def metadata_form(cc: dict) -> str:
    """Fillable course-metadata questionnaire (bilingual EN/HE), pre-filled with whatever we
    already know; the teacher completes the rest and returns it. Collects exam dates, course
    type, delivery mode, attendance policy, and the graded-task structure — the one-shot ask."""
    def v(x):
        return '' if x in (None, '') else x
    tasks = cc.get('milestones') or []
    tblk = ('\n'.join(f'  - {{name: "{t.get("name","")}", date: {v(t.get("date"))}, weight: {v(t.get("weight"))}}}'
                      for t in tasks)
            or '  # - {name: "HW 1", date: 2026-03-01, weight: 0.1}\n'
               '  # - {name: "Exam", date: 2026-06-15, weight: 0.5}')
    return f"""# ─────────────────────────────────────────────────────────────
# Aaron Owl — Course metadata  /  מטא-דאטה של הקורס
# Fill what you know; leave blank if unknown. Return this file with results.json.
# מלא/י את מה שידוע; השאר/י ריק אם לא ידוע. החזר/י קובץ זה יחד עם results.json.
# ─────────────────────────────────────────────────────────────

grading_type:        {v(cc.get('grading_type') or cc.get('course_type'))}     # exam | coursework | mixed | project | pass_fail   (אופן ההערכה: בחינה / מטלות / משולב / פרויקט / עובר-נכשל)
delivery_mode:       {v(cc.get('delivery_mode'))}    # frontal | online | hybrid   (פרונטלי / מקוון / משולב)
attendance_required: {v(cc.get('attendance_required'))}    # mandatory | optional | partial   (חובת נוכחות: חובה / רשות / חלקית)
discipline:          {v(cc.get('discipline'))}       # engineering | computer_science | chemistry | physics | mathematics | materials | life_sciences | business | humanities | other   (תחום — בחר/י מהרשימה)
level:               {v(cc.get('level'))}            # intro | intermediate | advanced   (רמה: מבוא / ביניים / מתקדם)

# Exam dates — enable the windowed (pre/post-exam) analysis  /  תאריכי בחינות
moed_a_date:         {v(cc.get('moed_a_date'))}      # YYYY-MM-DD   (מועד א')
moed_b_date:         {v(cc.get('moed_b_date'))}      # YYYY-MM-DD   (מועד ב' / retake, if any)

# Coursework/mixed only — list graded items; `name` must match the column
# header in your grades file.  /  מטלות מדורגות; השם = כותרת העמודה בקובץ הציונים.
tasks:
{tblk}

notes:               # anything else worth knowing / הערות
"""


def demo_grades(feats_csv: Path, mode: str) -> str:
    """A runnable DEMO grades file: real student emails + random plausible grades, plus a few
    fake non-user rows so the (automatic) adoption contrast has a control group."""
    import random
    df = pd.read_csv(feats_csv, usecols=[0])
    random.seed(0)
    cols = [c for c, _ in GRADE_COLS[mode]]
    rows = []
    for e in df[df.columns[0]].tolist():
        r = {'email': e}
        for c in cols:
            if c == 'moed_b':
                r[c] = random.randint(55, 90) if random.random() < 0.15 else ''
            elif c == 'passed':
                r[c] = random.choice([0, 1])
            else:
                r[c] = random.randint(50, 98)
        rows.append(r)
    for i in range(4):                                   # demo non-users (not in the feature file)
        rows.append({'email': f'demo_nonuser_{i}@example.edu',
                     **{c: ('' if c == 'moed_b' else random.randint(45, 78)) for c in cols}})
    return pd.DataFrame(rows).to_csv(index=False)


def demo_metadata(cc: dict) -> str:
    """A filled DEMO metadata file for the dry run."""
    return ("# DEMO metadata (example values) — for the test run only / ערכי דוגמה לבדיקה בלבד\n"
            "grading_type:        exam\n"
            "delivery_mode:       frontal\n"
            "attendance_required: optional\n"
            f"discipline:          {cc.get('discipline') or 'engineering'}\n"
            "level:               intermediate\n"
            f"moed_a_date:         {cc.get('moed_a_date') or '2026-01-29'}\n"
            f"moed_b_date:         {cc.get('moed_b_date') or ''}\n"
            "tasks:\n"
            "notes:               demo\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', required=True)
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--grade-mode', choices=list(GRADE_COLS), default='full_ab',
                    help='which grades the teacher has (drives template columns + HOW_TO)')
    ap.add_argument('--final-rule', choices=['max', 'last'], default='max',
                    help='for --grade-mode final: how the single final grade is defined')
    ap.add_argument('--pass-mark', type=int, default=60)
    a = ap.parse_args()
    cfg = load_config(a.config)
    cc = cfg['courses'][a.course]
    name = cc['name']
    fed_dir = Path(cc.get('federation_dir') or cfg['data']['federation_dir'])
    feats = fed_dir / f'student_features_{a.course}_federation.csv'
    if not feats.exists():
        raise FileNotFoundError(f"feature file not found: {feats} (run pipeline.py --course {a.course} first)")

    mode = a.grade_mode
    stamp = date.today().strftime('%Y%m%d')
    tag = '' if mode == 'full_ab' else f'_{mode}'
    pkg = fed_dir / f'teacher_package_{a.course}_v2{tag}_{stamp}'
    pkg.mkdir(parents=True, exist_ok=True)

    shutil.copy(feats, pkg / feats.name)
    shutil.copy(HERE / 'analysis_script_v2.py', pkg / 'analysis_script_v2.py')
    shutil.copy(HERE / 'match_roster.py', pkg / 'match_roster.py')
    shutil.copy(HERE / 'FEDERATED_QUESTIONS_SPEC.md', pkg / 'FEDERATED_QUESTIONS_SPEC.md')
    (pkg / 'grades_template.csv').write_text(grades_template(feats, mode), encoding='utf-8')
    (pkg / 'HOW_TO.html').write_text(
        how_to_html(name, feats.name, mode, a.pass_mark, a.final_rule), encoding='utf-8')
    # v3: metadata questionnaire (the teacher fills + returns) + our known course_meta
    (pkg / 'course_metadata.yaml').write_text(metadata_form(cc), encoding='utf-8')
    cm = fed_dir / f'course_meta_{a.course}.json'
    if cm.exists():
        shutil.copy(cm, pkg / cm.name)
    # demo files so the teacher can dry-run before filling anything
    (pkg / 'demo_grades_template.csv').write_text(demo_grades(feats, mode), encoding='utf-8')
    (pkg / 'demo_course_metadata.yaml').write_text(demo_metadata(cc), encoding='utf-8')

    zpath = fed_dir / f'{pkg.name}.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pkg.iterdir()):
            z.write(f, f'{pkg.name}/{f.name}')

    n_students = sum(1 for _ in open(feats)) - 1
    print(f"Package: {pkg}")
    print(f"Zip:     {zpath}")
    print(f"Grade mode: {mode}" + (f" (final_rule={a.final_rule})" if mode == 'final' else ''))
    print(f"Template columns: email, {', '.join(c for c, _ in GRADE_COLS[mode])}")
    print(f"Contents: {[f.name for f in sorted(pkg.iterdir())]}")
    print(f"Students in feature file: {n_students}  ·  teacher returns: results.json")


if __name__ == '__main__':
    main()
