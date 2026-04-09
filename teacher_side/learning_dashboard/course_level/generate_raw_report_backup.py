#!/usr/bin/env python3
"""
Generate a simple, data-driven HTML report without LLM narratives.
Shows raw numbers and calculations for Teaching ROI and course insights.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import glob


def load_data(output_dir: Path):
    """Load Layer 0, Layer 2, teaching investment, and lecture-level data."""
    import re

    layer0_path = output_dir / "learning_dashboard" / "course_level" / "layer0" / "course_layer0_output.json"
    layer2_path = output_dir / "learning_dashboard" / "course_level" / "layer2" / "course_layer2_output.json"
    teaching_path = output_dir / "course_level" / "layer1" / "teaching_investments.json"
    lecturer_report_path = output_dir.parent / "lecturer_report.json"

    # Load course-level data
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

    # Load lecture titles from lecturer_report.json (JSONL format)
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
                            # Extract title from HTML <h2> tag
                            match = re.search(r'<h2[^>]*>(.*?)</h2>', lecturer_report, re.DOTALL)
                            if match:
                                title = match.group(1).strip()
                                # Clean HTML entities and tags
                                title = re.sub(r'<[^>]+>', '', title)
                                lecture_titles[lecture_id] = title
                            else:
                                # Fallback to 'name' field
                                lecture_titles[lecture_id] = lec.get('name', '')
                        elif lecture_id:
                            lecture_titles[lecture_id] = lec.get('name', '')
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Warning: Could not load lecturer_report.json: {e}")

    # Load lecture-level data for topic-level issues
    lecture_layer2_dir = output_dir / "learning_dashboard" / "layer2"
    lecture_data = {}
    lecture_issues_by_section = []  # All problematic topics across lectures

    if lecture_layer2_dir.exists():
        for lecture_file in lecture_layer2_dir.glob("*.json"):
            if lecture_file.name == "layer2_output.json":
                # This is single lecture format
                try:
                    with open(lecture_file) as f:
                        lec_data = json.load(f)
                        lecture_id = lec_data.get('lecture_id')
                        if lecture_id:
                            # Use title from lecturer_report if available, otherwise use name from layer2
                            full_title = lecture_titles.get(lecture_id, lec_data.get('lecture_name', ''))
                            lecture_data[lecture_id] = {
                                'lecture_name': full_title,
                                'lecture_id': lecture_id
                            }

                            # Collect all issues (problematic topics)
                            for issue in lec_data.get('issues', []):
                                lecture_issues_by_section.append({
                                    'lecture_id': lecture_id,
                                    'lecture_name': lec_data.get('lecture_name', ''),
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

    # Also add titles from lecturer_report to lecture_data for any missing lectures
    for lecture_id, title in lecture_titles.items():
        if lecture_id not in lecture_data:
            lecture_data[lecture_id] = {
                'lecture_name': title,
                'lecture_id': lecture_id
            }

    return layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues_by_section


def generate_raw_html_report(layer0_data: Dict, layer2_data: Dict, teaching_data: Dict,
                             lecture_data: Dict, lecture_issues: List[Dict], output_path: Path):
    """Generate a simple HTML report with raw data tables."""

    # Extract key metrics
    run_number = layer2_data['run_number']
    run_date = layer2_data['run_date']
    lectures_covered = layer2_data['lectures_covered']
    total_lectures = layer2_data['total_lectures']
    engaged_n = layer2_data['engaged_n']
    course_quiz_avg = layer2_data['course_quiz_avg']
    course_eval_avg = layer2_data['course_eval_avg']

    # Get engagement from layer0
    engagement = layer0_data.get('engagement', {})

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Report - Run {run_number} - Raw Data</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1800px;
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
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-box .label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .stat-box .value {{
            font-size: 1.8em;
            font-weight: bold;
            margin-top: 5px;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section-title {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin: 0 0 20px 0;
            font-size: 1.5em;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: right;
            border: 1px solid #ddd;
            font-size: 0.9em;
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
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #ddd;
        }}
        .note {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .segment-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
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
        .box-container {{
            background: white;
            padding: 30px;
            margin-bottom: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            border-top: 5px solid #667eea;
        }}
        .box-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
        }}
        .box-title {{
            font-size: 1.8em;
            font-weight: bold;
            margin: 0 0 10px 0;
        }}
        .box-subtitle {{
            font-size: 1.1em;
            opacity: 0.95;
            margin: 0;
            line-height: 1.6;
        }}
        .box-question {{
            background: #fff3cd;
            border-right: 5px solid #ffc107;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 5px;
            font-size: 1.15em;
            font-weight: bold;
            color: #856404;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 דוח קורס - ריצה {run_number} (5 שאלות מרכזיות)</h1>
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
                <div class="value">{course_quiz_avg - course_eval_avg:.1f}</div>
            </div>
        </div>
        <p style="margin: 15px 0 0 0; opacity: 0.9;">תאריך: {run_date}</p>
    </div>
"""

    # Student Segments breakdown
    if engagement:
        html += f"""
    <div class="section">
        <div class="section-title">📈 פילוח סטודנטים לפי ביצועים (Student Segments)</div>
        <table>
            <tr>
                <th>סגמנט</th>
                <th>מספר תלמידים</th>
                <th>אחוז</th>
                <th>טווח ציונים (Eval)</th>
                <th>תיאור</th>
            </tr>
            <tr>
                <td><span class="segment-badge segment-excel">EXCEL</span></td>
                <td>{engagement['excel_n']}</td>
                <td>{engagement['excel_pct']*100:.1f}%</td>
                <td>≥75%</td>
                <td>סטודנטים מצטיינים - הבנה עמוקה</td>
            </tr>
            <tr>
                <td><span class="segment-badge segment-middle">MIDDLE</span></td>
                <td>{engagement['middle_n']}</td>
                <td>{engagement['middle_pct']*100:.1f}%</td>
                <td>45-75%</td>
                <td>סטודנטים ממוצעים - הבנה חלקית</td>
            </tr>
            <tr>
                <td><span class="segment-badge segment-struggles">STRUGGLES</span></td>
                <td>{engagement['struggles_n']}</td>
                <td>{engagement['struggles_pct']*100:.1f}%</td>
                <td>&lt;45%</td>
                <td>סטודנטים מתקשים - צריכים תמיכה</td>
            </tr>
        </table>
    </div>
"""

    # Teaching ROI Analysis
    if teaching_data:
        # Build a mapping of topics to success rates (from consistent_successes)
        topic_success = {}
        for success in layer2_data.get('top_consistent_successes', []):
            topic_success[success['concept']] = success['avg_success_rate']

        # Build ROI data
        roi_items = []
        for topic_name, teach_data in teaching_data.items():
            if not topic_name.strip():
                continue

            time_min = teach_data.get('total_time_minutes', 0)
            if time_min < 10:  # Skip very short sections
                continue

            # Try to find success rate for this topic
            success_rate = topic_success.get(topic_name)

            # If we have success rate, calculate ROI
            if success_rate is not None:
                roi = success_rate / time_min  # points per minute
                roi_items.append({
                    'topic': topic_name,
                    'time': time_min,
                    'success_rate': success_rate,
                    'roi': roi,
                    'questions': teach_data.get('inclass_questions_total', 0),
                    'lectures': len(teach_data.get('lectures', []))
                })

        # Sort by ROI (lowest first = worst efficiency)
        roi_items.sort(key=lambda x: x['roi'])

        if roi_items:
            html += f"""
    <div class="section">
        <div class="section-title">⚡ Teaching ROI - ניתוח יעילות הוראה</div>
        <div class="note">
            <strong>ROI (Return on Investment)</strong>: מחושב כ-<code>Success Rate / Teaching Time</code><br>
            <strong>ערך נמוך</strong> = יעילות נמוכה (השקענו הרבה זמן אבל ההצלחה נמוכה)<br>
            <strong>ערך גבוה</strong> = יעילות גבוהה (הסטודנטים מצליחים עם מעט זמן הוראה)<br>
            הטבלה ממוינת מהנמוך לגבוה - <span class="negative">נושאים בראש רשימה דורשים תשומת לב!</span>
        </div>
        <table>
            <tr>
                <th style="width: 35%">נושא</th>
                <th>זמן הוראה<br>(דקות)</th>
                <th>Success Rate<br>(%)</th>
                <th>ROI<br>(נקודות/דקה)</th>
                <th>שאלות בכיתה</th>
                <th>מספר שיעורים</th>
            </tr>"""

            for item in roi_items[:15]:  # Show top 15 problematic
                roi_class = "negative" if item['roi'] < 3.0 else "warning" if item['roi'] < 5.0 else "positive"
                html += f"""
            <tr>
                <td><strong>{item['topic']}</strong></td>
                <td class="metric-highlight">{item['time']:.1f}</td>
                <td>{item['success_rate']:.1f}%</td>
                <td class="{roi_class}">{item['roi']:.2f}</td>
                <td>{item['questions']}</td>
                <td>{item['lectures']}</td>
            </tr>"""

            html += """
        </table>
    </div>
"""

    # Problematic Lessons with full titles and segment highlights
    problematic = layer2_data.get('top_problematic_lessons', [])
    if problematic:
        segment_highlight = ""
        if engagement and engagement.get('struggles_n', 0) > 0:
            segment_highlight = f'<strong>🎯 Segment Highlight</strong>: <span class="segment-badge segment-struggles">STRUGGLES ({engagement["struggles_n"]} students, {engagement["struggles_pct"]*100:.1f}%)</span> is the primary group affected by problematic lessons'

        html += f"""
    <div class="section">
        <div class="section-title">⚠️ שיעורים בעייתיים (Problematic Lessons)</div>
        <div class="note">
            <strong>Problem Score</strong>: ציון בעייתיות מחושב. ערך גבוה = בעייתי יותר<br>
            <strong>Signals</strong>: low_eval (הערכה נמוכה), high_query_volume (נפח שאלות גבוה), surface_learning (למידה שטחית)<br>
            {segment_highlight}
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 30%">כותרת מלאה</th>
                <th>ממוצע הערכה</th>
                <th>ממוצע קורס</th>
                <th>פער</th>
                <th>נושאים בעייתיים</th>
                <th>Signals</th>
                <th>Problem Score</th>
            </tr>"""

        for lesson in problematic:
            eval_avg = lesson['lesson_eval_avg']
            course_avg = lesson['course_eval_avg']
            gap = course_avg - eval_avg
            signals_str = ', '.join(lesson['signals'])

            # Get full title from lecture_data
            lecture_id = lesson.get('lecture_id', '')
            full_title = lecture_data.get(lecture_id, {}).get('lecture_name', 'N/A')

            html += f"""
            <tr>
                <td><strong>{lesson['lecture_name']}</strong></td>
                <td class="lecture-title">{full_title}</td>
                <td class="negative">{eval_avg:.1f}</td>
                <td>{course_avg:.1f}</td>
                <td class="negative">-{gap:.1f}</td>
                <td>{lesson['issue_count']}</td>
                <td>{signals_str}</td>
                <td class="metric-highlight">{lesson['lesson_problem_score']:.2f}</td>
            </tr>"""

        html += """
        </table>
    </div>
"""

    # Problematic Topics/Sections (aggregated across all lectures)
    if lecture_issues:
        # Sort by corroboration score (highest first)
        lecture_issues_sorted = sorted(lecture_issues, key=lambda x: x['corroboration_score'], reverse=True)

        segment_highlight = ""
        if engagement and engagement.get('struggles_n', 0) > 0:
            segment_highlight = f'<strong>🎯 Segment Breakdown</strong>: Assuming most failures come from <span class="segment-badge segment-struggles">STRUGGLES ({engagement["struggles_n"]} students)</span> and <span class="segment-badge segment-middle">MIDDLE ({engagement["middle_n"]} students)</span> segments'

        html += f"""
    <div class="section">
        <div class="section-title">🔴 נושאים/סעיפים בעייתיים (Problematic Topics/Sections)</div>
        <div class="note">
            <strong>Problematic Topics</strong>: נושאים ספציפיים בתוך שיעורים שבהם תלמידים נכשלו או שאלו הרבה שאלות<br>
            <strong>Corroboration Score</strong>: מדד לחומרת הבעיה - ערך גבוה = בעיה חמורה יותר<br>
            {segment_highlight}
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 25%">סעיף/נושא</th>
                <th style="width: 20%">שאלה/תוכן בעייתי</th>
                <th>תלמידים שנכשלו</th>
                <th>% כישלון</th>
                <th>תלמידים ששאלו</th>
                <th>Corroboration Score</th>
            </tr>"""

        for issue in lecture_issues_sorted[:20]:  # Show top 20
            html += f"""
            <tr>
                <td><strong>{issue['lecture_name'][:20] if len(issue['lecture_name']) > 20 else issue['lecture_name']}</strong></td>
                <td>{issue['section']}</td>
                <td style="font-size: 0.85em;">{issue['topic'][:60]}{'...' if len(issue['topic']) > 60 else ''}</td>
                <td class="negative">{issue['eval_failure_n']}</td>
                <td class="negative">{issue['eval_failure_rate']*100:.1f}%</td>
                <td>{issue['query_student_count']}</td>
                <td class="metric-highlight">{issue['corroboration_score']:.1f}</td>
            </tr>"""

        html += """
        </table>
    </div>
"""

    # Good Lessons with full titles
    good_lessons = layer2_data.get('top_good_lessons', [])
    if good_lessons:
        segment_highlight = ""
        if engagement:
            segment_highlight = f'<strong>🎯 Segment Highlight</strong>: <span class="segment-badge segment-excel">EXCEL ({engagement["excel_n"]} students)</span> and <span class="segment-badge segment-middle">MIDDLE ({engagement["middle_n"]} students)</span> performed well in these lessons'

        html += f"""
    <div class="section">
        <div class="section-title">✅ שיעורים מוצלחים (Good Lessons)</div>
        <div class="note">
            <strong>Success Score</strong>: ציון הצלחה. ערך גבוה = מוצלח יותר<br>
            <strong>Signals</strong>: high_eval (הערכה גבוהה), low_query_volume (מעט שאלות), low_revisit (מעט חזרות)<br>
            {segment_highlight}
        </div>
        <table>
            <tr>
                <th>שיעור</th>
                <th style="width: 30%">כותרת מלאה</th>
                <th>ממוצע הערכה</th>
                <th>ממוצע קורס</th>
                <th>פער</th>
                <th>שאלות</th>
                <th>חזרות</th>
                <th>Signals</th>
                <th>Success Score</th>
            </tr>"""

        for lesson in good_lessons:
            eval_avg = lesson['lesson_eval_avg']
            course_avg = lesson['course_eval_avg']
            gap = eval_avg - course_avg
            signals_str = ', '.join(lesson['signals'])

            # Get full title from lecture_data
            lecture_id = lesson.get('lecture_id', '')
            full_title = lecture_data.get(lecture_id, {}).get('lecture_name', 'N/A')

            html += f"""
            <tr>
                <td><strong>{lesson['lecture_name']}</strong></td>
                <td class="lecture-title">{full_title}</td>
                <td class="positive">{eval_avg:.1f}</td>
                <td>{course_avg:.1f}</td>
                <td class="positive">+{gap:.1f}</td>
                <td>{lesson['query_count']}</td>
                <td>{lesson['revisit_count']}</td>
                <td>{signals_str}</td>
                <td class="metric-highlight">{lesson['lesson_success_score']:.2f}</td>
            </tr>"""

        html += """
        </table>
    </div>
"""

    # Recurring Concepts
    recurring = layer2_data.get('top_recurring_concepts', [])
    if recurring:
        html += f"""
    <div class="section">
        <div class="section-title">🔁 מושגים חוזרים (Recurring Concepts)</div>
        <div class="note">
            <strong>Recurrence Score</strong>: מחושב מכל האותות: <code>(failures + queries + revisits) / engaged_students</code><br>
            ערך גבוה = המושג חוזר במספר שיעורים ומציג בעיה משמעותית (תלמידים נכשלים, שואלים, או חוזרים על החומר)<br>
            <strong>הבדל מ-ROI</strong>: Recurrence מודד את <em>חומרת הבעיה</em> (כמה תלמידים נתקלים בה), ROI מודד <em>יעילות</em> (הצלחה לעומת זמן)
        </div>
        <table>
            <tr>
                <th style="width: 30%">מושג</th>
                <th>הופעות</th>
                <th>Failures</th>
                <th>Queries</th>
                <th>Revisits</th>
                <th>שיעורים</th>
                <th>Recurrence Score</th>
            </tr>"""

        for concept in recurring:
            lectures_str = ', '.join(concept['lectures'][:3])
            if len(concept['lectures']) > 3:
                lectures_str += f" +{len(concept['lectures'])-3} עוד"

            html += f"""
            <tr>
                <td><strong>{concept['concept']}</strong></td>
                <td>{concept['appearance_count']}</td>
                <td>{concept.get('total_failure_n', 0)}</td>
                <td>{concept['total_query_n']}</td>
                <td>{concept['revisit_student_n']}</td>
                <td>{lectures_str}</td>
                <td class="metric-highlight">{concept['recurrence_score']:.3f}</td>
            </tr>"""

        html += """
        </table>
    </div>
"""

    # Surface Learning Pattern - EXPANDED with actual details
    gaps = layer2_data.get('top_systemic_gaps', [])
    surface_learning_gap = next((g for g in gaps if 'Surface Learning' in g['concept']), None)

    if surface_learning_gap:
        # Get lecture names for affected lectures
        affected_lecture_ids = surface_learning_gap.get('lectures', [])
        affected_lectures = []
        for lec_id in affected_lecture_ids:
            lec_name = lecture_data.get(lec_id, {}).get('lecture_name', lec_id)
            affected_lectures.append(lec_name)

        html += f"""
    <div class="section">
        <div class="section-title">📚 Surface Learning Pattern - למידה שטחית (ניתוח מפורט)</div>
        <div class="note">
            <strong>מה זה Surface Learning?</strong> תופעה שבה סטודנטים מצליחים בקוויזים (זיכרון לטווח קצר) אבל נכשלים בהערכות (הבנה עמוקה)
        </div>

        <h3 style="color: #667eea; margin-top: 25px;">📊 מימדי הבעיה</h3>
        <table>
            <tr>
                <th>מימד</th>
                <th>ערך</th>
                <th>משמעות</th>
            </tr>
            <tr>
                <td><strong>Appearances</strong></td>
                <td class="warning">{surface_learning_gap['gap_appearances']}</td>
                <td>מספר השיעורים בהם התגלה הפער</td>
            </tr>
            <tr>
                <td><strong>Direction</strong></td>
                <td>{surface_learning_gap['direction']}</td>
                <td>over-invested = הושקע זמן רב אך התוצאות חלשות / under-retained = תלמידים לא שומרים את הידע</td>
            </tr>
            <tr>
                <td><strong>Average Gap</strong></td>
                <td class="negative">{course_quiz_avg - course_eval_avg:.1f} נקודות</td>
                <td>פער ממוצע בין קוויז (זיכרון) להערכה (הבנה)</td>
            </tr>"""

        if engagement:
            html += f"""
            <tr>
                <td><strong>Primary Affected Segment</strong></td>
                <td><span class="segment-badge segment-struggles">STRUGGLES ({engagement['struggles_n']} students)</span></td>
                <td>הקבוצה המושפעת ביותר מלמידה שטחית</td>
            </tr>"""

        html += f"""
        </table>

        <h3 style="color: #667eea; margin-top: 25px;">🎯 שיעורים מושפעים (Affected Lectures)</h3>
        <table>
            <tr>
                <th>מספר</th>
                <th style="width: 70%">כותרת שיעור</th>
            </tr>"""

        for i, lec_name in enumerate(affected_lectures[:10], 1):  # Show first 10
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

        html += f"""
        </table>

        <h3 style="color: #667eea; margin-top: 25px;">🔍 Interpretation</h3>
        <div style="background: #f8d7da; padding: 15px; border-radius: 5px; border-left: 4px solid #dc3545;">
            <p style="margin: 0; color: #721c24;"><strong>{surface_learning_gap['interpretation']}</strong></p>
        </div>

        <h3 style="color: #667eea; margin-top: 25px;">💡 Recommended Actions</h3>
        <ul style="line-height: 2;">
            <li>🎯 <strong>Active Learning</strong>: הוסף יותר תרגילים מעשיים במהלך השיעור</li>
            <li>🔄 <strong>Spaced Repetition</strong>: חזור על חומר קריטי במספר שיעורים</li>
            <li>❓ <strong>Deep Questions</strong>: שאל שאלות הבנה במקום שאלות זיכרון</li>
            <li>👥 <strong>Peer Teaching</strong>: עודד סטודנטים להסביר זה לזה</li>
            <li>📝 <strong>Formative Assessment</strong>: הוסף יותר הערכות ביניים</li>
        </ul>
    </div>
"""

    # Low Success Rate Topics (from problematic topics with high failure rates)
    if lecture_issues:
        # Calculate average failure rate per topic across lectures
        topic_failures = {}
        for issue in lecture_issues:
            topic = issue['section']
            if topic not in topic_failures:
                topic_failures[topic] = {
                    'total_failures': 0,
                    'total_students': 0,
                    'appearances': 0,
                    'lectures': [],
                    'example_questions': []
                }

            topic_failures[topic]['total_failures'] += issue['eval_failure_n']
            topic_failures[topic]['total_students'] += issue['unique_students']
            topic_failures[topic]['appearances'] += 1
            topic_failures[topic]['lectures'].append(issue['lecture_name'][:20])
            if issue['topic']:
                topic_failures[topic]['example_questions'].append(issue['topic'][:50])

        # Calculate failure rate for each topic
        low_success_topics = []
        for topic, data in topic_failures.items():
            if data['appearances'] >= 1 and data['total_students'] > 0:
                avg_failure_rate = (data['total_failures'] / data['total_students']) * 100
                success_rate = 100 - avg_failure_rate
                low_success_topics.append({
                    'topic': topic,
                    'success_rate': success_rate,
                    'failure_rate': avg_failure_rate,
                    'total_failures': data['total_failures'],
                    'total_students': data['total_students'],
                    'appearances': data['appearances'],
                    'lectures': list(set(data['lectures']))[:3],
                    'example_question': data['example_questions'][0] if data['example_questions'] else ''
                })

        # Sort by success rate (lowest first)
        low_success_topics.sort(key=lambda x: x['success_rate'])

        if low_success_topics[:15]:  # Show top 15 lowest
            html += f"""
    <div class="section">
        <div class="section-title">📉 נושאים עם אחוז הצלחה נמוך (Low Success Rate Topics)</div>
        <div class="note">
            <strong>Success Rate</strong>: אחוז התלמידים שהצליחו בשאלות על נושא זה<br>
            <strong>ערך נמוך</strong> = נושא קשה שדורש תשומת לב מיוחדת בהוראה<br>
            הטבלה ממוינת מהנמוך לגבוה - <span class="negative">נושאים בראש רשימה הם הקשים ביותר!</span>
        </div>
        <table>
            <tr>
                <th style="width: 30%">נושא/סעיף</th>
                <th>Success Rate<br>(%)</th>
                <th>Failure Rate<br>(%)</th>
                <th>תלמידים שנכשלו</th>
                <th>מתוך סה"כ</th>
                <th>הופעות</th>
                <th>שיעורים</th>
                <th>דוגמה לשאלה</th>
            </tr>"""

            for topic_data in low_success_topics[:15]:
                lectures_str = ', '.join(topic_data['lectures'])
                success_class = "negative" if topic_data['success_rate'] < 20 else "warning" if topic_data['success_rate'] < 40 else ""

                html += f"""
            <tr>
                <td><strong>{topic_data['topic']}</strong></td>
                <td class="{success_class}">{topic_data['success_rate']:.1f}%</td>
                <td class="negative">{topic_data['failure_rate']:.1f}%</td>
                <td class="negative">{topic_data['total_failures']}</td>
                <td>{topic_data['total_students']}</td>
                <td>{topic_data['appearances']}</td>
                <td style="font-size: 0.85em;">{lectures_str}</td>
                <td style="font-size: 0.8em;">{topic_data['example_question']}{'...' if len(topic_data['example_question']) >= 50 else ''}</td>
            </tr>"""

            html += """
        </table>
    </div>
"""

    # Consistent Successes with Teaching Pattern Analysis
    successes = layer2_data.get('top_consistent_successes', [])
    if successes:
        # Build success-to-teaching mapping
        success_teaching_patterns = []
        for success in successes:
            concept = success['concept']

            # Try to find matching teaching section (exact or partial match)
            matched_teaching = None
            for section_name, teach_data in teaching_data.items():
                # Look for concept in section name or vice versa
                if concept.lower() in section_name.lower() or section_name.lower() in concept.lower():
                    if not matched_teaching or teach_data.get('total_time_minutes', 0) > matched_teaching.get('total_time_minutes', 0):
                        matched_teaching = teach_data

            # Calculate teaching efficiency
            teaching_time = matched_teaching.get('total_time_minutes', 0) if matched_teaching else 0
            questions = matched_teaching.get('inclass_questions_total', 0) if matched_teaching else 0
            examples = matched_teaching.get('example_used_count', 0) if matched_teaching else 0

            # Determine what worked well
            success_factors = []
            if teaching_time > 0:
                roi = success['avg_success_rate'] / teaching_time
                if roi > 5.0:
                    success_factors.append(f"⚡ High efficiency (ROI: {roi:.1f})")
                if questions >= 2:
                    success_factors.append(f"❓ Practice questions ({questions})")
                if examples >= 1:
                    success_factors.append(f"📝 Examples used ({examples})")
                if teaching_time >= 15:
                    success_factors.append(f"⏱️ Adequate time ({teaching_time:.0f}min)")
                elif teaching_time < 15 and roi > 5.0:
                    success_factors.append(f"⚡ Very efficient (success with minimal time)")
            else:
                # No teaching data found - likely learned from readings or other methods
                success_factors.append("📚 Self-study / Reading material")

            success_teaching_patterns.append({
                'concept': concept,
                'success_rate': success['avg_success_rate'],
                'success_count': success['success_count'],
                'lectures': success['lectures'],
                'teaching_time': teaching_time,
                'questions': questions,
                'examples': examples,
                'success_factors': success_factors if success_factors else ["✓ Success (reason unclear)"]
            })

        html += f"""
    <div class="section">
        <div class="section-title">🌟 הצלחות עקביות - ניתוח דפוסי הוראה (Consistent Successes - Teaching Pattern Analysis)</div>
        <div class="note">
            <strong>What worked well?</strong> ניתוח של דפוסי הוראה שהובילו להצלחה:<br>
            ⚡ <strong>High efficiency</strong> = ROI > 5.0 (הצלחה גבוהה ביחס לזמן)<br>
            ❓ <strong>Practice questions</strong> = שאלות תרגול בכיתה<br>
            📝 <strong>Examples</strong> = שימוש בדוגמאות<br>
            ⏱️ <strong>Adequate time</strong> = הקדשת זמן מספיק (≥15 דקות)
        </div>
        <table>
            <tr>
                <th style="width: 25%">נושא</th>
                <th>אחוז הצלחה</th>
                <th>הופעות</th>
                <th>זמן הוראה<br>(דקות)</th>
                <th>שאלות</th>
                <th style="width: 30%">מה עבד טוב? (Success Factors)</th>
                <th>שיעורים</th>
            </tr>"""

        for item in success_teaching_patterns:
            lectures_str = ', '.join(item['lectures'][:2])
            if len(item['lectures']) > 2:
                lectures_str += f" +{len(item['lectures'])-2}"

            factors_html = '<br>'.join(item['success_factors'])
            time_display = f"{item['teaching_time']:.0f}" if item['teaching_time'] > 0 else "—"

            html += f"""
            <tr>
                <td><strong>{item['concept']}</strong></td>
                <td class="positive">{item['success_rate']:.1f}%</td>
                <td>{item['success_count']}</td>
                <td class="metric-highlight">{time_display}</td>
                <td>{item['questions'] if item['questions'] > 0 else '—'}</td>
                <td style="font-size: 0.85em;">{factors_html}</td>
                <td style="font-size: 0.8em;">{lectures_str}</td>
            </tr>"""

        html += """
        </table>

        <h3 style="color: #667eea; margin-top: 25px;">💡 Key Insights - What Made These Topics Successful?</h3>
        <div style="background: #d4edda; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745;">
            <ul style="margin: 5px 0; line-height: 2;">"""

        # Analyze patterns across all successes
        high_roi_count = sum(1 for p in success_teaching_patterns if p['teaching_time'] > 0 and (p['success_rate'] / p['teaching_time']) > 5.0)
        practice_heavy = sum(1 for p in success_teaching_patterns if p['questions'] >= 2)
        example_heavy = sum(1 for p in success_teaching_patterns if p['examples'] >= 1)
        time_adequate = sum(1 for p in success_teaching_patterns if p['teaching_time'] >= 15)

        if high_roi_count >= len(success_teaching_patterns) * 0.4:
            html += f"""
                <li>⚡ <strong>Efficiency wins</strong>: {high_roi_count} out of {len(success_teaching_patterns)} topics achieved high success with minimal time investment</li>"""

        if practice_heavy >= len(success_teaching_patterns) * 0.5:
            html += f"""
                <li>❓ <strong>Practice matters</strong>: {practice_heavy} topics included multiple in-class practice questions</li>"""

        if example_heavy >= len(success_teaching_patterns) * 0.3:
            html += f"""
                <li>📝 <strong>Examples helped</strong>: {example_heavy} topics used concrete examples during teaching</li>"""

        if time_adequate >= len(success_teaching_patterns) * 0.6:
            html += f"""
                <li>⏱️ <strong>Time investment</strong>: {time_adequate} topics received adequate teaching time (≥15 minutes)</li>"""
        else:
            html += f"""
                <li>⚡ <strong>Quick wins</strong>: Many successful topics required minimal time, suggesting clear concepts or effective teaching</li>"""

        html += """
            </ul>
        </div>
    </div>
"""

    # Prerequisite Gaps
    prereqs = layer2_data.get('top_prerequisite_gaps', [])
    if prereqs:
        html += f"""
    <div class="section">
        <div class="section-title">🔧 פערי ידע קדם (Prerequisite Gaps)</div>
        <div class="note">
            <strong>Prerequisite Gap</strong>: נושאים שסטודנטים שואלים עליהם אבל הם מחוץ לתכנית הלימודים<br>
            זה מצביע על ידע בסיסי חסר שצריך להשלים או להזכיר בתחילת הקורס
        </div>
        <table>
            <tr>
                <th style="width: 30%">נושא</th>
                <th>מספר סטודנטים</th>
                <th>מספר שיעורים</th>
                <th>דוגמאות שאילתות</th>
            </tr>"""

        for prereq in prereqs:
            examples = ', '.join(prereq['example_queries'][:3])

            html += f"""
            <tr>
                <td><strong>{prereq['topic']}</strong></td>
                <td>{prereq['unique_students']}</td>
                <td>{prereq['appearing_in_lectures']}</td>
                <td>{examples}</td>
            </tr>"""

        html += """
        </table>
    </div>
"""

    # Footer
    html += f"""
    <div class="footer">
        <p>דוח נתונים גולמיים | נוצר על ידי Aaron Learning Dashboard | {run_date}</p>
        <p style="font-size: 0.85em; margin-top: 10px;">
            דוח זה מציג נתונים גולמיים ללא עיבוד LLM. כל הנתונים מבוססים על חישובים ישירים מהמידע הנאסף.
        </p>
    </div>
</body>
</html>
"""

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ Generated raw data HTML report: {output_path}")


def main():
    """Generate raw HTML report."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate raw data HTML report')
    parser.add_argument('--output-dir', default='/home/roy/Downloads/attachments/output',
                        help='Output directory containing learning_dashboard data')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Load data
    print("Loading data...")
    layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues = load_data(output_dir)

    # Generate report
    output_path = output_dir / "course_level" / "layer3" / "course_dashboard_raw.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Generating raw HTML report...")
    generate_raw_html_report(layer0_data, layer2_data, teaching_data, lecture_data, lecture_issues, output_path)

    print(f"\n📊 Raw data report generated successfully!")
    print(f"   Open in browser: {output_path}")


if __name__ == "__main__":
    main()