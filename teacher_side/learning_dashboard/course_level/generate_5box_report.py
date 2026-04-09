#!/usr/bin/env python3
"""
5-Box Course Dashboard Generator (Data-Driven Alternative to LLM Layer 3)

This script generates a comprehensive HTML report that presents course-level learning analytics
in a 5-box format without requiring LLM API calls. It uses raw data from Layers 0, 1, and 2
to create actionable insights for instructors.

5-Box Structure:
    Box 1: Who are my students? (engagement, segments, performance)
    Box 2: What's not working? (problematic lessons & topics)
    Box 3: What worked well? (successful lessons & topics)
    Box 4: Where are the gaps and waste? (surface learning gap + low ROI topics)
    Box 5: What are the fundamental issues? (prerequisites + recurring problems)

Key Innovation - ROI Analysis (Box 4):
    Calculates Return on Investment for teaching concepts by combining:
    - Teaching time investment (from layer15/teaching_investment.json)
    - Student success rates (from eval.csv via question_section_map.json)
    - Formula: ROI = Success Rate ÷ Teaching Time (minutes)
    - Lower ROI = more teaching time with poor results = needs improvement

Data Flow:
    1. Loads aggregated data from course Layer 0, Layer 1, Layer 2
    2. Loads lecture-level Layer 2 data for detailed issue extraction
    3. Calculates ROI from raw eval.csv using concept-section mappings
    4. Generates standalone HTML report with Hebrew RTL support

Usage:
    python generate_5box_report.py --output-dir /path/to/output

Output:
    {output_dir}/course_level/layer3/course_dashboard_5box.html
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import argparse


def load_data(output_dir: Path):
    """Load all required data files."""
    import re

    layer0_path = output_dir / "learning_dashboard" / "course_level" / "layer0" / "course_layer0_output.json"
    layer2_path = output_dir / "learning_dashboard" / "course_level" / "layer2" / "course_layer2_output.json"
    teaching_path = output_dir / "course_level" / "layer1" / "teaching_investments.json"
    lecturer_report_path = output_dir.parent / "lecturer_report.json"

    # Load course data
    with open(layer2_path) as f:
        layer2_data = json.load(f)

    layer0_data = {}
    if layer0_path.exists():
        with open(layer0_path) as f:
            layer0_data = json.load(f)

    teaching_data = {}
    if teaching_path.exists():
        with open(teaching_path) as f:
            teaching_data = json.load(f)

    # Load lecture titles
    lecture_titles = {}
    if lecturer_report_path.exists():
        try:
            with open(lecturer_report_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        lec = json.loads(line.strip())
                        lecture_id = lec.get('lecture_id')
                        lecturer_report = lec.get('lecturer_report', '')

                        if lecture_id and lecturer_report:
                            match = re.search(r'<h2[^>]*>(.*?)</h2>', lecturer_report, re.DOTALL)
                            if match:
                                title = match.group(1).strip()
                                title = re.sub(r'<[^>]+>', '', title)
                                lecture_titles[lecture_id] = title
                            else:
                                lecture_titles[lecture_id] = lec.get('name', '')
                        elif lecture_id:
                            lecture_titles[lecture_id] = lec.get('name', '')
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Warning: Could not load lecturer_report.json: {e}")

    # Load lecture-level data
    # Try both possible locations for lecture layer2 files
    lecture_layer2_paths = [
        output_dir / "learning_dashboard" / "layer2",  # Lecture-specific layer2
        output_dir / "learning_dashboard" / "course_level" / "layer2",  # Course-level might have some data
    ]

    lecture_data = {}
    lecture_issues_by_section = []

    for lecture_layer2_dir in lecture_layer2_paths:
        if not lecture_layer2_dir.exists():
            continue

        for lecture_file in lecture_layer2_dir.glob("*.json"):
            # Skip course-level files, only process lecture-level
            if "course_layer2" in lecture_file.name:
                continue

            try:
                with open(lecture_file) as f:
                    lec_data = json.load(f)
                    lecture_id = lec_data.get('lecture_id')

                    # Skip if no lecture_id (not a lecture file)
                    if not lecture_id:
                        continue

                    full_title = lecture_titles.get(lecture_id, lec_data.get('lecture_name', ''))
                    lecture_data[lecture_id] = {
                        'lecture_name': full_title,
                        'lecture_id': lecture_id
                    }

                    # Extract issues from this lecture
                    for issue in lec_data.get('issues', []):
                        lecture_issues_by_section.append({
                            'lecture_id': lecture_id,
                            'lecture_short_name': lec_data.get('lecture_name', ''),
                            'full_lecture_title': full_title,
                            'section': issue.get('matched_section', issue.get('issue_title', 'Unknown')),
                            'topic': issue.get('cluster_label', ''),
                            'eval_failure_n': issue.get('eval_failure_n', 0),
                            'eval_failure_rate': issue.get('eval_failure_rate', 0),
                            'query_student_count': issue.get('query_student_count', 0),
                            'unique_students': issue.get('unique_students', 0),
                            'corroboration_score': issue.get('corroboration_score', 0),
                        })
            except Exception as e:
                print(f"Warning: Could not load {lecture_file}: {e}")

    for lecture_id, title in lecture_titles.items():
        if lecture_id not in lecture_data:
            lecture_data[lecture_id] = {
                'lecture_name': title,
                'lecture_id': lecture_id
            }

    return layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues_by_section


def calculate_roi_from_eval_data(data_dir: Path, unused_teaching_data: Dict) -> List[Dict]:
    """
    Calculate ROI by combining eval failure rates with teaching time.
    Uses eval.csv + question_section_map.json to calculate section-level failure rates,
    then aggregates by concept using concept_to_sections.json mapping.

    Returns list of ROI items sorted by ROI (lowest first).
    """
    import pandas as pd

    # Load question-to-section mapping
    question_map_path = data_dir / "learning_dashboard" / "layer15" / "question_section_map.json"
    if not question_map_path.exists():
        print(f"Warning: question_section_map.json not found at {question_map_path}")
        return []

    with open(question_map_path) as f:
        question_to_section = json.load(f)

    # Load concept-to-sections mapping
    concept_map_path = data_dir / "learning_dashboard" / "layer15" / "concept_to_sections.json"
    if not concept_map_path.exists():
        print(f"Warning: concept_to_sections.json not found at {concept_map_path}")
        return []

    with open(concept_map_path) as f:
        concept_to_sections = json.load(f)

    # Load teaching data from layer15
    teaching_path = data_dir / "learning_dashboard" / "layer15" / "teaching_investment.json"
    if not teaching_path.exists():
        print(f"Warning: teaching_investment.json not found at {teaching_path}")
        return []

    with open(teaching_path) as f:
        teaching_data = json.load(f)

    # Load eval.csv
    eval_csv_path = data_dir.parent / "eval.csv"
    if not eval_csv_path.exists():
        print(f"Warning: eval.csv not found at {eval_csv_path}")
        return []

    df_eval = pd.read_csv(eval_csv_path)

    # Calculate failure rate per section (from eval data)
    section_stats = {}  # {section_name: {'correct': count, 'total': count}}

    for _, row in df_eval.iterrows():
        try:
            results = json.loads(row['results_full'])
            answers = results.get('answers', {})

            for q_id_str, answer_data in answers.items():
                q_id = str(q_id_str)

                # Map question to section
                if q_id in question_to_section:
                    section = question_to_section[q_id]
                    is_correct = answer_data.get('correct', False)

                    if section not in section_stats:
                        section_stats[section] = {'correct': 0, 'total': 0}

                    section_stats[section]['total'] += 1
                    if is_correct:
                        section_stats[section]['correct'] += 1
        except (json.JSONDecodeError, KeyError) as e:
            continue

    # Now aggregate section stats by concept and calculate ROI
    roi_items = []

    for concept_name, teach_data in teaching_data.items():
        if not concept_name.strip():
            continue

        # Get time data
        time_min = teach_data.get('time_minutes', 0)
        if time_min < 10:  # Skip very short concepts
            continue

        # Get sections for this concept
        sections = concept_to_sections.get(concept_name, [])
        if not sections:
            continue

        # Aggregate stats from all sections for this concept
        total_correct = 0
        total_questions = 0
        for section in sections:
            if section in section_stats:
                stats = section_stats[section]
                total_correct += stats['correct']
                total_questions += stats['total']

        # Only include if we have eval data
        if total_questions > 0:
            success_rate = (total_correct / total_questions) * 100
            failure_rate = 1.0 - (total_correct / total_questions)

            # ROI = success rate / time (lower is worse)
            roi = success_rate / time_min if time_min > 0 else 0

            roi_items.append({
                'topic': concept_name,
                'time': time_min,
                'success_rate': success_rate,
                'failure_rate': failure_rate,
                'corroboration_score': total_questions,  # Use total questions as severity proxy
                'roi': roi,
                'total_questions': total_questions,
                'correct_answers': total_correct,
            })

    # Sort by ROI (lowest first - these are the worst performers)
    roi_items.sort(key=lambda x: x['roi'])

    return roi_items


def generate_5box_html_report(layer0_data: Dict, layer2_data: Dict, teaching_data: Dict,
                               lecture_data: Dict, lecture_issues: List[Dict], output_path: Path):
    """Generate 5-box format HTML report."""

    run_number = layer2_data['run_number']
    run_date = layer2_data['run_date']
    lectures_covered = layer2_data['lectures_covered']
    total_lectures = layer2_data['total_lectures']
    engaged_n = layer2_data['engaged_n']
    course_quiz_avg = layer2_data['course_quiz_avg']
    course_eval_avg = layer2_data['course_eval_avg']
    engagement = layer0_data.get('engagement', {})

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>דוח קורס - 5 שאלות מרכזיות</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            direction: rtl;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .header h1 {{
            margin: 0 0 15px 0;
            font-size: 2.2em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.25);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-box .label {{
            font-size: 0.9em;
            opacity: 0.95;
        }}
        .stat-box .value {{
            font-size: 1.9em;
            font-weight: bold;
            margin-top: 5px;
        }}

        .box-container {{
            background: white;
            padding: 35px;
            margin-bottom: 50px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.15);
            border-top: 6px solid #667eea;
        }}
        .box-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .box-title {{
            font-size: 2em;
            font-weight: bold;
            margin: 0 0 12px 0;
        }}
        .box-subtitle {{
            font-size: 1.2em;
            opacity: 0.96;
            margin: 0;
            line-height: 1.7;
        }}
        .box-question {{
            background: #fff3cd;
            border-right: 6px solid #ffc107;
            padding: 18px 25px;
            margin: 25px 0;
            border-radius: 8px;
            font-size: 1.3em;
            font-weight: bold;
            color: #856404;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: right;
            border: 1px solid #ddd;
            font-size: 0.95em;
        }}
        th {{
            background-color: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        tr:hover {{
            background-color: #f0f0f0;
        }}

        .metric-highlight {{
            color: #667eea;
            font-weight: bold;
        }}
        .positive {{
            color: #28a745;
            font-weight: bold;
        }}
        .negative {{
            color: #dc3545;
            font-weight: bold;
        }}
        .warning {{
            color: #ff6b35;
            font-weight: bold;
        }}
        .segment-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .segment-excel {{
            background-color: #d4edda;
            color: #155724;
        }}
        .segment-middle {{
            background-color: #d1ecf1;
            color: #0c5460;
        }}
        .segment-struggles {{
            background-color: #f8d7da;
            color: #721c24;
        }}
        .lecture-title {{
            font-size: 0.85em;
            color: #666;
            font-style: italic;
        }}
        .note {{
            background: #e7f3ff;
            border-right: 4px solid #2196F3;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 6px;
            font-size: 0.95em;
        }}
        .insight-box {{
            background: #d4edda;
            border-right: 5px solid #28a745;
            padding: 20px;
            border-radius: 8px;
            margin-top: 25px;
        }}
        .insight-box h4 {{
            margin: 0 0 15px 0;
            color: #155724;
            font-size: 1.2em;
        }}
        .insight-box ul {{
            margin: 0;
            padding-right: 25px;
            line-height: 2;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
            border-top: 2px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 דוח קורס - 5 שאלות מרכזיות לשיפור ההוראה</h1>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="label">שיעורים נותחו</div>
                <div class="value">{lectures_covered}/{total_lectures}</div>
            </div>
            <div class="stat-box">
                <div class="label">סטודנטים מעורבים</div>
                <div class="value">{engaged_n}</div>
            </div>
            <div class="stat-box">
                <div class="label">ממוצע קוויז</div>
                <div class="value">{course_quiz_avg:.1f}</div>
            </div>
            <div class="stat-box">
                <div class="label">ממוצע הערכה</div>
                <div class="value">{course_eval_avg:.1f}</div>
            </div>
            <div class="stat-box">
                <div class="label">פער קוויז-הערכה</div>
                <div class="value" style="color: {'#ff6b6b' if (course_quiz_avg - course_eval_avg) > 30 else 'white'}">{course_quiz_avg - course_eval_avg:.1f}</div>
            </div>
        </div>
        <p style="margin: 15px 0 0 0; opacity: 0.95; font-size: 1.05em;">תאריך: {run_date} | ריצה: {run_number}</p>
    </div>
"""

    # BOX 1: Who are my students + High Level Data
    if engagement:
        html += f"""
    <div class="box-container">
        <div class="box-header">
            <div class="box-title">📦 1. מי הסטודנטים שלי?</div>
            <div class="box-subtitle">הבנת הרכב הכיתה ונתונים כלליים על הקורס</div>
        </div>

        <div class="box-question">
            ❓ מי הסטודנטים בכיתה ומה הנתונים הכלליים של הקורס?
        </div>

        <h3 style="color: #667eea; margin: 30px 0 15px 0; font-size: 1.4em;">👥 פילוח הסטודנטים</h3>
        <div class="note">
            <strong>סגמנטציה</strong>: חלוקת הסטודנטים לפי ביצועי הערכות (Eval Scores)<br>
            כל קבוצה זקוקה לגישת הוראה ותמיכה שונה
        </div>
        <table>
            <tr>
                <th>סגמנט</th>
                <th>מספר</th>
                <th>אחוז</th>
                <th>טווח ציונים</th>
                <th style="width: 45%">אפיון וצרכים</th>
            </tr>
            <tr>
                <td><span class="segment-badge segment-excel">EXCEL</span></td>
                <td><strong>{engagement['excel_n']}</strong></td>
                <td>{engagement['excel_pct']*100:.1f}%</td>
                <td>≥75%</td>
                <td>מצטיינים עם הבנה עמוקה. <strong>צרכים</strong>: אתגרים מתקדמים, עומק, פרויקטים</td>
            </tr>
            <tr>
                <td><span class="segment-badge segment-middle">MIDDLE</span></td>
                <td><strong>{engagement['middle_n']}</strong></td>
                <td>{engagement['middle_pct']*100:.1f}%</td>
                <td>45-75%</td>
                <td>ביצועים ממוצעים, הבנה חלקית. <strong>צרכים</strong>: תרגול, דוגמאות, חיזוק</td>
            </tr>
            <tr>
                <td><span class="segment-badge segment-struggles">STRUGGLES</span></td>
                <td><strong>{engagement['struggles_n']}</strong></td>
                <td>{engagement['struggles_pct']*100:.1f}%</td>
                <td>&lt;45%</td>
                <td>מתקשים ודורשים תמיכה. <strong>צרכים</strong>: פישוט, תרגול בסיסי, עזרה אישית</td>
            </tr>
        </table>

        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">📈 נתונים כלליים על הקורס</h3>
        <table>
            <tr>
                <th>מדד</th>
                <th>ערך</th>
                <th>משמעות</th>
            </tr>
            <tr>
                <td><strong>שיעורים נותחו</strong></td>
                <td>{lectures_covered} / {total_lectures}</td>
                <td>כיסוי מלא של הקורס</td>
            </tr>
            <tr>
                <td><strong>סטודנטים מעורבים</strong></td>
                <td><strong>{engaged_n}</strong></td>
                <td>מספר הסטודנטים שהשתתפו באופן אקטיבי</td>
            </tr>
            <tr>
                <td><strong>ממוצע קוויזים</strong></td>
                <td class="positive">{course_quiz_avg:.1f}%</td>
                <td>ביצועים בזיכרון קצר טווח (מיידי)</td>
            </tr>
            <tr>
                <td><strong>ממוצע הערכות</strong></td>
                <td class="{'negative' if course_eval_avg < 60 else 'warning' if course_eval_avg < 75 else 'positive'}">{course_eval_avg:.1f}%</td>
                <td>ביצועים בהבנה עמוקה (לאורך זמן)</td>
            </tr>
            <tr>
                <td><strong>פער קוויז-הערכה</strong></td>
                <td class="{'negative' if (course_quiz_avg - course_eval_avg) > 30 else 'warning'}">{course_quiz_avg - course_eval_avg:.1f} נקודות</td>
                <td>{"⚠️ פער גדול - למידה שטחית!" if (course_quiz_avg - course_eval_avg) > 30 else "פער סביר"}</td>
            </tr>
        </table>
    </div>
"""

    # BOX 2: Issues (Lessons + Topics)
    problematic = layer2_data.get('top_problematic_lessons', [])
    if problematic or lecture_issues:
        html += f"""
    <div class="box-container">
        <div class="box-header">
            <div class="box-title">📦 2. מה לא עובד? (בעיות)</div>
            <div class="box-subtitle">זיהוי שיעורים ונושאים בעייתיים שדורשים תיקון מיידי</div>
        </div>

        <div class="box-question">
            ❓ באילו שיעורים ונושאים הסטודנטים נתקלים בקשיים?
        </div>
"""

        # Problematic Lessons
        if problematic:
            html += f"""
        <h3 style="color: #667eea; margin: 30px 0 15px 0; font-size: 1.4em;">⚠️ שיעורים בעייתיים</h3>
        <div class="note">
            <strong>מדוד לפי</strong>: ציון הערכה נמוך, נפח שאלות גבוה, למידה שטחית<br>
            <strong>קבוצה מושפעת</strong>: בעיקר <span class="segment-badge segment-struggles">STRUGGLES ({engagement.get('struggles_n', 0)} students, {engagement.get('struggles_pct', 0)*100:.1f}%)</span>
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 35%">כותרת מלאה</th>
                <th>ממוצע הערכה</th>
                <th>פער מקורס</th>
                <th>נושאים בעייתיים</th>
                <th>Problem Score</th>
            </tr>"""

            for lesson in problematic[:10]:
                eval_avg = lesson['lesson_eval_avg']
                course_avg = lesson['course_eval_avg']
                gap = course_avg - eval_avg
                lecture_id = lesson.get('lecture_id', '')
                full_title = lecture_data.get(lecture_id, {}).get('lecture_name', 'N/A')

                html += f"""
            <tr>
                <td><strong>{lesson['lecture_name']}</strong></td>
                <td class="lecture-title">{full_title}</td>
                <td class="negative">{eval_avg:.1f}</td>
                <td class="negative">-{gap:.1f}</td>
                <td>{lesson['issue_count']}</td>
                <td class="metric-highlight">{lesson['lesson_problem_score']:.2f}</td>
            </tr>"""

            html += """
        </table>"""

        # Problematic Topics with full lecture titles
        if lecture_issues:
            lecture_issues_sorted = sorted(lecture_issues, key=lambda x: x['corroboration_score'], reverse=True)

            html += f"""
        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">🔴 נושאים/סעיפים בעייתיים</h3>
        <div class="note">
            <strong>Corroboration Score</strong>: מדד חומרת הבעיה - ערך גבוה = בעיה חמורה<br>
            כולל: נכשלים בהערכות + שאלות רבות + חזרות על חומר
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 30%">כותרת שיעור מלאה</th>
                <th style="width: 20%">נושא/סעיף בעייתי</th>
                <th>נכשלו</th>
                <th>% כישלון</th>
                <th>Corroboration</th>
            </tr>"""

            for issue in lecture_issues_sorted[:15]:
                html += f"""
            <tr>
                <td><strong>{issue['lecture_short_name']}</strong></td>
                <td class="lecture-title">{issue.get('full_lecture_title', 'N/A')}</td>
                <td>{issue['section']}</td>
                <td class="negative">{issue['eval_failure_n']}</td>
                <td class="negative">{issue['eval_failure_rate']*100:.1f}%</td>
                <td class="metric-highlight">{issue['corroboration_score']:.1f}</td>
            </tr>"""

            html += """
        </table>"""

        html += """
    </div>
"""

    # BOX 3: Good (Lessons + Topics)
    good_lessons = layer2_data.get('top_good_lessons', [])
    successes = layer2_data.get('top_consistent_successes', [])
    if good_lessons or successes:
        html += f"""
    <div class="box-container">
        <div class="box-header">
            <div class="box-title">📦 3. מה כן עובד? (הצלחות)</div>
            <div class="box-subtitle">למידה מהצלחות - מה הפך שיעורים ונושאים למוצלחים</div>
        </div>

        <div class="box-question">
            ❓ באילו שיעורים ונושאים הסטודנטים הצליחו? מה הסוד?
        </div>
"""

        if good_lessons:
            html += f"""
        <h3 style="color: #667eea; margin: 30px 0 15px 0; font-size: 1.4em;">✅ שיעורים מוצלחים</h3>
        <div class="note">
            <strong>מדוד לפי</strong>: ציון הערכה גבוה, מעט שאלות, מעט חזרות<br>
            <strong>קבוצה מצליחה</strong>: בעיקר <span class="segment-badge segment-excel">EXCEL ({engagement.get('excel_n', 0)})</span> ו-<span class="segment-badge segment-middle">MIDDLE ({engagement.get('middle_n', 0)})</span>
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 35%">כותרת מלאה</th>
                <th>ממוצע הערכה</th>
                <th>פער מקורס</th>
                <th>שאלות</th>
                <th>Success Score</th>
            </tr>"""

            for lesson in good_lessons[:8]:
                eval_avg = lesson['lesson_eval_avg']
                course_avg = lesson['course_eval_avg']
                gap = eval_avg - course_avg
                lecture_id = lesson.get('lecture_id', '')
                full_title = lecture_data.get(lecture_id, {}).get('lecture_name', 'N/A')

                html += f"""
            <tr>
                <td><strong>{lesson['lecture_name']}</strong></td>
                <td class="lecture-title">{full_title}</td>
                <td class="positive">{eval_avg:.1f}</td>
                <td class="positive">+{gap:.1f}</td>
                <td>{lesson['query_count']}</td>
                <td class="metric-highlight">{lesson['lesson_success_score']:.2f}</td>
            </tr>"""

            html += """
        </table>"""

        # Successful Topics - show each topic separately with its OWN lectures
        if successes:
            html += f"""
        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">🌟 נושאים מוצלחים</h3>
        <div class="note">
            <strong>נושאים עקביים</strong>: נושאים שמופיעים במספר שיעורים ובכולם יש הצלחה גבוהה<br>
            למד מהם מה עובד!
        </div>
        <table>
            <tr>
                <th style="width: 40%">נושא</th>
                <th>אחוז הצלחה</th>
                <th>מספר הופעות</th>
                <th style="width: 30%">שיעורים שבהם הופיע</th>
            </tr>"""

            for success in successes[:10]:
                lectures_list = ', '.join(success['lectures'][:3])
                if len(success['lectures']) > 3:
                    lectures_list += f" +{len(success['lectures'])-3}"

                html += f"""
            <tr>
                <td><strong>{success['concept']}</strong></td>
                <td class="positive">{success['avg_success_rate']:.1f}%</td>
                <td>{success['success_count']}</td>
                <td style="font-size: 0.9em;">{lectures_list}</td>
            </tr>"""

            html += """
        </table>"""

        html += """
    </div>
"""

    # BOX 4: Gaps (Gap Table + Low ROI)
    gaps = layer2_data.get('top_systemic_gaps', [])
    surface_learning_gap = next((g for g in gaps if 'Surface Learning' in g['concept']), None)

    # Calculate ROI items using eval data
    roi_items = calculate_roi_from_eval_data(output_path.parent.parent.parent, teaching_data)

    if surface_learning_gap or roi_items:
        affected_lecture_ids = surface_learning_gap.get('lectures', []) if surface_learning_gap else []
        affected_lectures = []
        for lec_id in affected_lecture_ids:
            lec_name = lecture_data.get(lec_id, {}).get('lecture_name', lec_id)
            affected_lectures.append(lec_name)

        html += f"""
    <div class="box-container">
        <div class="box-header">
            <div class="box-title">📦 4. איפה הפערים והבזבוז?</div>
            <div class="box-subtitle">זיהוי פערים בלמידה + נושאים עם ROI נמוך (השקעה רבה, תוצאות חלשות)</div>
        </div>

        <div class="box-question">
            ❓ איפה יש פערים בלמידה? היכן מבזבזים זמן הוראה?
        </div>
"""

        # Gap Table
        if surface_learning_gap:
            html += f"""
        <h3 style="color: #667eea; margin: 30px 0 15px 0; font-size: 1.4em;">📚 פער למידה שטחית (Surface Learning Gap)</h3>
        <div class="note" style="background: #fff3cd; border-right-color: #ffc107;">
            <strong>⚠️ פער נמצא</strong>: {course_quiz_avg - course_eval_avg:.1f} נקודות בממוצע!<br>
            <strong>משמעות</strong>: סטודנטים מצליחים בזיכרון קצר (קוויזים) אבל נכשלים בהבנה עמוקה (הערכות)
        </div>

        <table>
            <tr>
                <th>מדד</th>
                <th>ערך</th>
                <th style="width: 50%">משמעות</th>
            </tr>
            <tr>
                <td><strong>שיעורים מושפעים</strong></td>
                <td class="warning">{surface_learning_gap['gap_appearances']}</td>
                <td>מספר השיעורים בהם התגלה פער משמעותי</td>
            </tr>
            <tr>
                <td><strong>כיוון הפער</strong></td>
                <td>{surface_learning_gap['direction']}</td>
                <td>over-invested = השקענו זמן רב אך התוצאות חלשות</td>
            </tr>
            <tr>
                <td><strong>פער ממוצע</strong></td>
                <td class="negative">{course_quiz_avg - course_eval_avg:.1f} נק'</td>
                <td>הבדל ממוצע בין קוויז (זיכרון) להערכה (הבנה)</td>
            </tr>
            <tr>
                <td><strong>קבוצה מושפעת</strong></td>
                <td><span class="segment-badge segment-struggles">STRUGGLES ({engagement.get('struggles_n', 0)})</span></td>
                <td>הקבוצה המתקשה ביותר בהבנה עמוקה</td>
            </tr>
        </table>"""

            if affected_lectures:
                html += f"""
        <h4 style="color: #667eea; margin: 30px 0 10px 0;">🎯 שיעורים מושפעים מהפער</h4>
        <table>
            <tr>
                <th style="width: 10%">#</th>
                <th>כותרת שיעור</th>
            </tr>"""

                for i, lec_name in enumerate(affected_lectures[:10], 1):
                    html += f"""
            <tr>
                <td>{i}</td>
                <td>{lec_name}</td>
            </tr>"""

                if len(affected_lectures) > 10:
                    html += f"""
            <tr>
                <td colspan="2" style="text-align: center; font-style: italic;">
                    ועוד {len(affected_lectures) - 10} שיעורים נוספים...
                </td>
            </tr>"""

                html += """
        </table>"""

        # Low ROI Topics
        if roi_items:
            html += f"""
        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">⚡ נושאים עם ROI נמוך - בזבוז זמן</h3>
        <div class="note" style="background: #ffe7e7; border-right-color: #dc3545;">
            <strong>ROI = Success Rate ÷ Teaching Time</strong> (נקודות להשקעה בדקה)<br>
            <strong>⚠️ ROI נמוך</strong> = השקענו זמן הוראה רב אבל הסטודנטים נכשלו ← <span class="negative">תקן, צמצם או הוסף תרגול!</span>
        </div>
        <table>
            <tr>
                <th style="width: 40%">נושא/סעיף</th>
                <th>זמן הוראה<br>(דק')</th>
                <th>% כישלון</th>
                <th>Success Rate<br>(%)</th>
                <th>ROI<br>(נק'/דק')</th>
                <th>Severity</th>
            </tr>"""

            for item in roi_items[:15]:
                roi_class = "negative" if item['roi'] < 1.0 else "warning" if item['roi'] < 3.0 else "positive"
                html += f"""
            <tr>
                <td><strong>{item['topic']}</strong></td>
                <td class="warning">{item['time']:.1f}</td>
                <td class="negative">{item['failure_rate']*100:.1f}%</td>
                <td>{item['success_rate']:.1f}%</td>
                <td class="{roi_class}">{item['roi']:.2f}</td>
                <td class="metric-highlight">{item['corroboration_score']:.1f}</td>
            </tr>"""

            html += """
        </table>"""
        else:
            # No ROI data available - show message
            html += f"""
        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">⚡ נושאים עם ROI נמוך - בזבוז זמן</h3>
        <div class="note" style="background: #ffe7e7; border-right-color: #dc3545;">
            <strong>⚠️ נתונים חסרים</strong>: לא נמצאו נתוני ROI מפורטים.<br>
            <strong>הסיבה</strong>: נדרשים נתוני כישלון ברמת נושאים/סעיפים לחישוב ROI.<br>
            <strong>פתרון</strong>: הרץ ניתוח layer2 עבור כל השיעורים בקורס להשגת נתונים מלאים.
        </div>
        <p style="margin: 20px 0; color: #666;">
            <strong>מה זה ROI?</strong> ROI (Return on Investment) = Success Rate ÷ Teaching Time<br>
            ROI נמוך מציין נושאים שבהם השקענו זמן הוראה רב אך הסטודנטים נכשלו.<br>
            נושאים אלה דורשים שיפור או צמצום.
        </p>"""

        html += """
        <div class="insight-box">
            <h4>💡 איך לסגור פערים ולשפר ROI?</h4>
            <ul>
                <li>🎯 <strong>למידה אקטיבית</strong>: הוסף תרגילים מעשיים במהלך השיעור</li>
                <li>🔄 <strong>חזרה מרווחת</strong>: חזור על נושאים קריטיים במספר שיעורים</li>
                <li>⏱️ <strong>צמצם זמן</strong>: נושאים עם ROI נמוך - נסה ללמד ביעילות רבה יותר</li>
                <li>📚 <strong>חומר משלים</strong>: שלח חומר קריאה מקדים או משלים</li>
                <li>❓ <strong>שאלות עומק</strong>: החלף הרצאות בתרגילים ושאלות הבנה</li>
            </ul>
        </div>
    </div>
"""

    # BOX 5: Fundamental Issues (Prerequisite Gaps + Recurring Concepts)
    prereqs = layer2_data.get('top_prerequisite_gaps', [])
    recurring = layer2_data.get('top_recurring_concepts', [])

    if prereqs or recurring:
        html += f"""
    <div class="box-container">
        <div class="box-header">
            <div class="box-title">📦 5. בעיות יסוד (Fundamental Issues)</div>
            <div class="box-subtitle">פערי ידע קודם + מושגים חוזרים שגורמים לבעיות חוזרות</div>
        </div>

        <div class="box-question">
            ❓ אילו בעיות בסיסיות מפריעות ללמידה לאורך הקורס?
        </div>
"""

        # Prerequisite Gaps
        if prereqs:
            html += f"""
        <h3 style="color: #667eea; margin: 30px 0 15px 0; font-size: 1.4em;">🔧 פערי ידע קדם (Prerequisites)</h3>
        <div class="note">
            <strong>Prerequisite Gaps</strong>: נושאים שסטודנטים שואלים עליהם אבל הם <strong>מחוץ</strong> לתכנית הלימודים<br>
            זה מעיד על ידע בסיסי חסר שצריך להשלים או להזכיר בתחילת הקורס
        </div>
        <table>
            <tr>
                <th style="width: 30%">נושא חסר</th>
                <th>מספר סטודנטים</th>
                <th>מספר שיעורים</th>
                <th style="width: 40%">דוגמאות שאילתות</th>
            </tr>"""

            for prereq in prereqs[:10]:
                examples = ', '.join(prereq['example_queries'][:3])

                html += f"""
            <tr>
                <td><strong>{prereq['topic']}</strong></td>
                <td>{prereq['unique_students']}</td>
                <td>{prereq['appearing_in_lectures']}</td>
                <td style="font-size: 0.9em;">{examples}</td>
            </tr>"""

            html += """
        </table>"""

        # Recurring Concepts
        if recurring:
            html += f"""
        <h3 style="color: #667eea; margin: 40px 0 15px 0; font-size: 1.4em;">🔁 מושגים חוזרים (Recurring Issues)</h3>
        <div class="note">
            <strong>Recurrence Score = (failures + queries + revisits) / engaged_students</strong><br>
            מושגים שחוזרים במספר שיעורים ותמיד גורמים לבעיות - ייתכן שיש בעיה במושג עצמו או באופן שבו הוא מלומד
        </div>
        <table>
            <tr>
                <th style="width: 35%">מושג</th>
                <th>הופעות</th>
                <th>Failures</th>
                <th>Queries</th>
                <th>Revisits</th>
                <th>Recurrence Score</th>
                <th>שיעורים</th>
            </tr>"""

            for concept in recurring[:10]:
                lectures_str = ', '.join(concept['lectures'][:3])
                if len(concept['lectures']) > 3:
                    lectures_str += f" +{len(concept['lectures'])-3}"

                html += f"""
            <tr>
                <td><strong>{concept['concept']}</strong></td>
                <td>{concept['appearance_count']}</td>
                <td class="negative">{concept.get('total_failure_n', 0)}</td>
                <td>{concept['total_query_n']}</td>
                <td>{concept['revisit_student_n']}</td>
                <td class="metric-highlight">{concept['recurrence_score']:.3f}</td>
                <td style="font-size: 0.85em;">{lectures_str}</td>
            </tr>"""

            html += """
        </table>"""

        html += """
        <div class="insight-box">
            <h4>💡 כיצד לטפל בבעיות יסוד?</h4>
            <ul>
                <li>📚 <strong>פערי ידע קדם</strong>: הוסף מודול מקדים או חומר רענון בתחילת הקורס</li>
                <li>🔁 <strong>מושגים חוזרים</strong>: בדוק אם ההגדרה ברורה, הוסף דוגמאות טובות יותר</li>
                <li>🎯 <strong>התאמה</strong>: התאם את רמת הקורס לרמת הסטודנטים בפועל</li>
                <li>🆘 <strong>תמיכה מוקדמת</strong>: זהה סטודנטים עם פערים בשלב מוקדם וספק עזרה</li>
            </ul>
        </div>
    </div>
"""

    # Footer
    html += f"""
    <div class="footer">
        <p><strong>דוח נתונים גולמיים | נוצר על ידי Aaron Learning Dashboard</strong></p>
        <p style="margin-top: 10px;">ריצה {run_number} | {run_date}</p>
        <p style="font-size: 0.85em; margin-top: 10px;">
            דוח זה מציג 5 שאלות מרכזיות על בסיס נתונים גולמיים, ללא עיבוד LLM
        </p>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ Generated 5-box HTML report: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate 5-box format HTML report')
    parser.add_argument('--output-dir', default='/home/roy/Downloads/attachments/output',
                        help='Output directory containing learning_dashboard data')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    print("Loading data...")
    layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues = load_data(output_dir)

    output_path = output_dir / "course_level" / "layer3" / "course_dashboard_5box.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Generating 5-box HTML report...")
    generate_5box_html_report(layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues, output_path)

    print(f"\n📊 5-box report generated successfully!")
    print(f"   Open in browser: {output_path}")


if __name__ == "__main__":
    main()