#!/usr/bin/env python3
"""
Aaron Owl — Teacher Usage Report
Generates a self-contained HTML report from the student features CSV.

Usage:
    python federation/usage_report.py \
        --features /path/to/student_features_<course>_federation.csv \
        --course-name "My Course" \
        --out /path/to/output/
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# ── human-readable labels ────────────────────────────────────────────────────

COL_LABELS = {
    'active_learning_score':    'Active Learning Score',
    'active_learning_level':    'Engagement Level',
    'active_weeks':             'Active Weeks',
    'active_weeks_ratio':       'Consistency',
    'total_time_minutes':       'Total Time (min)',
    'avg_session_duration_minutes': 'Avg Session (min)',
    'sessions_count':           'Sessions',
    'meaningful_sessions_count':'Meaningful Sessions',
    'unique_lectures_viewed':   'Lectures Viewed',
    'lecture_coverage_pct':     'Lecture Coverage',
    'eval_avg_score':           'Avg Eval Score',
    'eval_submission_rate':     'Eval Completion',
    'quiz_avg_score':           'Avg Quiz Score',
    'quiz_submission_rate':     'Quiz Completion',
    'feature_diversity_count':  'Features Used',
    'concept_selects':          'Concept Clicks',
}

FEATURE_LABELS = {
    'used_quiz':              'Quiz',
    'used_quiz_eval':         'Quiz / Eval',
    'used_short_summary':     'Short Summary',
    'used_long_summary':      'Long Summary',
    'used_mindmap':           'Mind Map',
    'used_search':            'Search',
    'used_concepts':          'Concepts',
    'used_transcript':        'Transcript',
    'used_additional_material': 'Extra Material',
}

LEVEL_COLOR = {'High': '#2e7d32', 'Medium': '#e65100', 'Low': '#b71c1c'}
LEVEL_BG    = {'High': '#e8f5e9', 'Medium': '#fff3e0', 'Low': '#ffebee'}


# ── helpers ───────────────────────────────────────────────────────────────────

def _pct(val, decimals=0):
    if pd.isna(val):
        return '—'
    return f'{val:.{decimals}f}%'

def _num(val, decimals=1):
    if pd.isna(val):
        return '—'
    return f'{val:.{decimals}f}'

def _fmt_time(minutes):
    if pd.isna(minutes) or minutes == 0:
        return '—'
    h, m = int(minutes) // 60, int(minutes) % 60
    return f'{h}h {m:02d}m' if h else f'{m}m'

def _level_badge(level):
    if pd.isna(level) or level not in LEVEL_COLOR:
        return f'<span class="badge badge-unknown">—</span>'
    c  = LEVEL_COLOR[level]
    bg = LEVEL_BG[level]
    return (f'<span class="badge" '
            f'style="color:{c};background:{bg};border:1px solid {c}">'
            f'{level}</span>')


# ── chart data builders ───────────────────────────────────────────────────────

def _als_histogram(df):
    bins = [0, 20, 40, 60, 80, 101]
    labels = ['0–20', '20–40', '40–60', '60–80', '80–100']
    counts, _ = np.histogram(df['active_learning_score'].dropna(), bins=bins)
    colors = ['#ef9a9a', '#ffcc80', '#fff176', '#a5d6a7', '#66bb6a']
    return json.dumps({
        'labels': labels,
        'datasets': [{'label': 'Students', 'data': counts.tolist(),
                      'backgroundColor': colors, 'borderRadius': 6}]
    })

def _coverage_histogram(df):
    bins = [0, 20, 40, 60, 80, 101]
    labels = ['0–20%', '20–40%', '40–60%', '60–80%', '80–100%']
    counts, _ = np.histogram(df['lecture_coverage_pct'].clip(upper=100).dropna(), bins=bins)
    colors = ['#ef9a9a', '#ffcc80', '#fff176', '#a5d6a7', '#66bb6a']
    return json.dumps({
        'labels': labels,
        'datasets': [{'label': 'Students', 'data': counts.tolist(),
                      'backgroundColor': colors, 'borderRadius': 6}]
    })

def _feature_adoption(df):
    feat_cols = [c for c in FEATURE_LABELS if c in df.columns]
    pcts = [(df[c].sum() / len(df) * 100) for c in feat_cols]
    labels = [FEATURE_LABELS[c] for c in feat_cols]
    # sort descending
    pairs = sorted(zip(pcts, labels), reverse=True)
    pcts_s, labels_s = zip(*pairs) if pairs else ([], [])
    return json.dumps({
        'labels': list(labels_s),
        'datasets': [{'label': '% of Students',
                      'data': [round(p, 1) for p in pcts_s],
                      'backgroundColor': '#5c6bc0', 'borderRadius': 4}]
    })

def _engagement_pie(df):
    if 'active_learning_level' not in df.columns:
        return 'null'
    counts = df['active_learning_level'].value_counts()
    order = ['High', 'Medium', 'Low']
    vals  = [int(counts.get(l, 0)) for l in order]
    return json.dumps({
        'labels': order,
        'datasets': [{'data': vals,
                      'backgroundColor': [LEVEL_BG[l] for l in order],
                      'borderColor':     [LEVEL_COLOR[l] for l in order],
                      'borderWidth': 2}]
    })


# ── summary cards ─────────────────────────────────────────────────────────────

def _kpi_card(title, value, sub='', color='#5c6bc0'):
    return f'''
    <div class="kpi-card">
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-title">{title}</div>
        {f'<div class="kpi-sub">{sub}</div>' if sub else ''}
    </div>'''


# ── student table ─────────────────────────────────────────────────────────────

def _student_row(row):
    level = row.get('active_learning_level', None)
    bg = LEVEL_BG.get(str(level), '#fff')
    email = row['email'] if 'email' in row.index else row.name
    return (
        f'<tr style="background:{bg}">'
        f'<td style="font-size:0.82em">{email}</td>'
        f'<td style="text-align:center">{_level_badge(level)}</td>'
        f'<td style="text-align:center">{_num(row.get("active_learning_score"), 0)}</td>'
        f'<td style="text-align:center">{_num(row.get("active_weeks"), 0)} / {int(row.get("course_total_weeks", 0))}</td>'
        f'<td style="text-align:center">{_fmt_time(row.get("total_time_minutes"))}</td>'
        f'<td style="text-align:center">{_num(row.get("unique_lectures_viewed"), 0)} '
        f'({_pct(row.get("lecture_coverage_pct"), 0)})</td>'
        f'<td style="text-align:center">{_num(row.get("eval_avg_score"), 0) if not pd.isna(row.get("eval_avg_score", float("nan"))) else "—"}</td>'
        f'<td style="text-align:center">{_num(row.get("meaningful_sessions_count"), 0)}</td>'
        f'</tr>'
    )


# ── attention section ────────────────────────────────────────────────────────

def _attention_rows(df):
    at_risk = df[df.get('active_learning_level', pd.Series(dtype=str)) == 'Low'] if 'active_learning_level' in df.columns else pd.DataFrame()
    if at_risk.empty:
        return '<p style="color:#666">No students flagged.</p>'
    rows = ''
    for _, row in at_risk.iterrows():
        email = row.get('email', row.name)
        weeks = int(row.get('active_weeks', 0))
        time  = _fmt_time(row.get('total_time_minutes', 0))
        eval_ = _num(row.get('eval_avg_score', float('nan')), 0)
        rows += (f'<tr><td style="font-size:0.82em">{email}</td>'
                 f'<td style="text-align:center">{weeks}</td>'
                 f'<td style="text-align:center">{time}</td>'
                 f'<td style="text-align:center">{eval_}</td></tr>')
    return f'''<table class="tbl">
        <tr><th>Student</th><th>Active Weeks</th><th>Total Time</th><th>Avg Eval</th></tr>
        {rows}</table>'''


# ── post-Moed-A (retake window) section ───────────────────────────────────────

def _postA_section(df: pd.DataFrame) -> str:
    """Grade-free post-Moed-A analytics.

    Proxy: any activity in the postA window ⇒ the student is likely preparing for a
    retake (Moed B), which in turn hints they may not have passed Moed A. Renders only
    when the pipeline produced postA_ columns (i.e. exam dates were set); otherwise ''.
    Counts are small per course — an early, directional signal, robust only when pooled.
    """
    if not any(c.startswith('postA_') for c in df.columns):
        return ''
    d = df.copy()
    d['_tier'] = d['active_learning_level'] if 'active_learning_level' in d.columns \
        else pd.Series(index=d.index, dtype=object)
    aw = d['postA_active_weeks'] if 'postA_active_weeks' in d.columns else pd.Series(0, index=d.index)
    ev = d['postA_total_active_events'] if 'postA_total_active_events' in d.columns else pd.Series(0, index=d.index)
    d['_active'] = (aw.fillna(0) > 0) | (ev.fillna(0) > 0)
    n_active = int(d['_active'].sum())
    n_silent = int((~d['_active']).sum())

    # 1) matrix: pre-A engagement tier × post-A activity
    tiers = [t for t in ['High', 'Medium', 'Low'] if (d['_tier'] == t).any()]
    mrows = ''
    for t in tiers:
        sub = d[d['_tier'] == t]
        c = LEVEL_COLOR.get(t, '#333')
        mrows += (f'<tr><td style="font-weight:600;color:{c}">{t} ALS</td>'
                  f'<td style="text-align:center">{int((~sub["_active"]).sum())}</td>'
                  f'<td style="text-align:center;font-weight:600">{int(sub["_active"].sum())}</td></tr>')
    matrix = (f'<table class="tbl" style="max-width:460px">'
              f'<tr><th>Pre-Moed-A engagement</th>'
              f'<th style="text-align:center">Silent after A<br>'
              f'<span style="font-weight:400;font-size:.82em">likely passed / done</span></th>'
              f'<th style="text-align:center">Active after A<br>'
              f'<span style="font-weight:400;font-size:.82em">likely retaking</span></th></tr>'
              f'{mrows}</table>')

    # 2) retake-prep watchlist: lower pre-A engagement + active in retake window
    watch = d[d['_tier'].isin(['Low', 'Medium']) & d['_active']].copy()
    if 'active_learning_score' in watch.columns:
        watch = watch.sort_values('active_learning_score')
    wrows = ''
    for _, r in watch.iterrows():
        ev_score = r.get('postA_eval_avg_score', float('nan'))
        wrows += (f'<tr><td style="font-size:.82em">{r.get("email", r.name)}</td>'
                  f'<td style="text-align:center">{_level_badge(r.get("_tier"))}</td>'
                  f'<td style="text-align:center">{_num(r.get("active_learning_score"), 0)}</td>'
                  f'<td style="text-align:center">{_num(r.get("postA_active_learning_score"), 0)}</td>'
                  f'<td style="text-align:center">{_num(r.get("postA_meaningful_sessions_count"), 0)}</td>'
                  f'<td style="text-align:center">{_fmt_time(r.get("postA_total_time_minutes"))}</td>'
                  f'<td style="text-align:center">{_num(ev_score, 0) if not pd.isna(ev_score) else "—"}</td></tr>')
    watch_html = (f'<table class="tbl">'
                  f'<tr><th>Student</th><th style="text-align:center">Pre-A Level</th>'
                  f'<th style="text-align:center">Pre-A ALS</th><th style="text-align:center">Post-A ALS</th>'
                  f'<th style="text-align:center">Post-A Meaningful Sessions</th>'
                  f'<th style="text-align:center">Post-A Time</th>'
                  f'<th style="text-align:center">Post-A Eval</th></tr>{wrows}</table>') if wrows \
        else '<p style="color:#666">No lower-engagement students are active in the retake window.</p>'

    # 3) 'late surge' segment: low pre-A → high post-A engagement
    woke_html = ''
    if 'postA_active_learning_level' in d.columns:
        woke = d[(d['_tier'] == 'Low') & (d['postA_active_learning_level'] == 'High')]
        if len(woke):
            emails = ', '.join(str(r.get('email', r.name)) for _, r in woke.iterrows())
            woke_html = (f'<p style="margin-top:12px;padding:10px 14px;background:{LEVEL_BG["High"]};'
                         f'border:1px solid {LEVEL_COLOR["High"]};border-radius:8px;font-size:.86em">'
                         f'🌱 <strong>{len(woke)} “late surge” student(s)</strong> — low pre-Moed-A '
                         f'engagement but high activity in the retake window: {emails}</p>')

    return f'''
  <h2>Post-Moed A — Retake-Window Activity</h2>
  <p style="font-size:.85em;color:#666;margin-bottom:10px">
    Activity <em>after</em> Moed A, used as a grade-free proxy: a student still active in the
    Moed-A→B window is most likely preparing for a <strong>retake (Moed B)</strong> — which itself
    hints they may not have passed Moed A. Counts are small per course and meant as an early,
    directional signal (robust only when pooled across courses). No grades are used.
  </p>
  <div class="charts-row" style="align-items:flex-start">
    <div class="chart-box" style="max-width:480px"><h3>Pre-A engagement × post-A activity</h3>{matrix}</div>
    <div class="chart-box" style="min-width:260px"><h3>Retake window at a glance</h3>
      <p style="font-size:.9em;line-height:1.9">Active in retake window: <strong>{n_active}</strong><br>
      Silent after Moed A: <strong>{n_silent}</strong></p>{woke_html}</div>
  </div>

  <h2 style="border-left-color:#ff9800">⚠ Retake-Prep Watchlist (grade-free)</h2>
  <div class="attention-box">
    <p style="font-size:.85em;color:#bf360c;margin-bottom:10px">
      Lower pre-Moed-A engagement <em>and</em> active in the retake window — the strongest
      grade-free early signal that a student may be re-sitting the exam. Worth a check-in.
    </p>
    {watch_html}
  </div>
'''


# ── tier dynamics (pre-A tier → post-A tier, fixed scale) ─────────────────────

_ALS_COMP = [('active_weeks_ratio', 0.35), ('total_active_events', 0.25),
             ('feature_diversity_count', 0.20), ('meaningful_sessions_ratio', 0.20)]


def _tier_transition_section(df: pd.DataFrame) -> str:
    """Who changed ALS tier after Moed A. Post-A activity is scored against the
    PRE-A distribution (fixed scale, same 0-100 as pre-A) so tiers are comparable —
    NOT the percentile-re-ranked postA_active_learning_score (whose mean is ~50 by
    construction and hides the drop). Grade-free."""
    if not any(c.startswith('postA_') for c in df.columns) or 'active_learning_level' not in df.columns:
        return ''
    d = df.copy()
    fixed = np.zeros(len(d))
    for c, w in _ALS_COMP:
        pre = d[c].fillna(0).values
        post = d['postA_' + c].fillna(0).values if 'postA_' + c in d.columns else np.zeros(len(d))
        fixed += w * np.array([(pre <= v).mean() * 100 for v in post])
    tier = lambda x: 'High' if x > 60 else ('Medium' if x >= 30 else 'Low')
    d['_pre'] = d['active_learning_level']
    d['_post'] = [tier(x) for x in fixed]
    order = ['High', 'Medium', 'Low']; rank = {'High': 2, 'Medium': 1, 'Low': 0}

    header = ''.join(f'<th style="text-align:center;color:{LEVEL_COLOR[t]}">{t}</th>' for t in order)
    body = ''
    for pre in order:
        sub = d[d['_pre'] == pre]
        cells = ''
        for post in order:
            n = int((sub['_post'] == post).sum())
            bg = ('#fff' if n == 0 else '#eef2f7' if post == pre
                  else '#d7f5df' if rank[post] > rank[pre] else '#ffdad4')
            cells += f'<td style="text-align:center;background:{bg}">{n or ""}</td>'
        body += (f'<tr><td style="font-weight:600;color:{LEVEL_COLOR[pre]}">{pre} →</td>{cells}</tr>')

    dropped = int(d.apply(lambda r: rank[r['_post']] < rank[r['_pre']], axis=1).sum())
    n_high = int((d['_pre'] == 'High').sum())
    stayed_high = int(((d['_pre'] == 'High') & (d['_post'] == 'High')).sum())
    steady = int((d['active_weeks_ratio'].fillna(0) >= 0.5).sum())
    return f'''
  <h2>Tier dynamics — who changed after Moed A</h2>
  <p style="font-size:.85em;color:#666;margin-bottom:8px">
    Each student's Active Learning Score is re-computed for the post-Moed-A window on the
    <b>same pre-A scale</b>, then re-classified into Low / Medium / High. Rows = tier before Moed A,
    columns = tier after. <span style="background:#ffdad4;padding:1px 5px">red</span> = dropped a tier,
    <span style="background:#d7f5df;padding:1px 5px">green</span> = rose. Grade-free; activity only.</p>
  <table class="tbl" style="max-width:420px"><tr><th>before ↓ / after →</th>{header}</tr>{body}</table>
  <p style="font-size:.88em;margin-top:8px"><b>{dropped}/{len(d)}</b> students dropped ≥1 tier after Moed A;
    only <b>{stayed_high}/{n_high}</b> High-tier students stayed High. Before Moed A,
    <b>{steady}/{len(d)}</b> were steady learners (active ≥ half the course weeks); the rest were
    sporadic / last-minute.</p>
'''


# ── main render ───────────────────────────────────────────────────────────────

def generate(df: pd.DataFrame, course_name: str, generated_date: str) -> str:
    n = len(df)
    n_active = int((df['active_weeks'] > 0).sum()) if 'active_weeks' in df.columns else n
    engagement_rate = n_active / n * 100 if n > 0 else 0

    avg_als  = df['active_learning_score'].mean() if 'active_learning_score' in df.columns else float('nan')
    avg_time = df['total_time_minutes'].mean() if 'total_time_minutes' in df.columns else float('nan')
    avg_eval = df['eval_avg_score'].mean() if 'eval_avg_score' in df.columns else float('nan')
    avg_cov  = df['lecture_coverage_pct'].mean() if 'lecture_coverage_pct' in df.columns else float('nan')

    level_counts = df['active_learning_level'].value_counts() if 'active_learning_level' in df.columns else pd.Series()
    n_high   = int(level_counts.get('High', 0))
    n_medium = int(level_counts.get('Medium', 0))
    n_low    = int(level_counts.get('Low', 0))

    # Sort for table: low engagement first so teacher notices them
    sort_col = 'active_learning_score' if 'active_learning_score' in df.columns else df.columns[0]
    table_df = df.sort_values(sort_col, ascending=True)

    kpis = (
        _kpi_card('Students', n, color='#1565c0') +
        _kpi_card('Avg Active Learning Score', f'{avg_als:.0f}/100' if not pd.isna(avg_als) else '—', color='#2e7d32') +
        _kpi_card('Avg Total Time', _fmt_time(avg_time), color='#4527a0') +
        _kpi_card('Avg Eval Score', f'{avg_eval:.0f}%' if not pd.isna(avg_eval) else '—', color='#e65100') +
        _kpi_card('Lecture Coverage', f'{avg_cov:.0f}%' if not pd.isna(avg_cov) else '—',
                  sub=f'avg % of lectures opened  •  median {df["lecture_coverage_pct"].median():.0f}%',
                  color='#00695c')
    )

    student_rows = ''.join(_student_row(row) for _, row in table_df.iterrows())

    return f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aaron Owl — Teacher Report: {course_name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; background: #f4f6f8; color: #333; }}
  .page {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px; }}
  h1 {{ font-size: 1.6em; color: #1a237e; }}
  h2 {{ font-size: 1.1em; color: #283593; margin: 28px 0 12px; border-left: 4px solid #5c6bc0; padding-left: 10px; }}
  .meta {{ color: #666; font-size: 0.88em; margin-top: 4px; }}
  .kpi-row {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 20px 0; }}
  .kpi-card {{ background: #fff; border-radius: 10px; padding: 18px 22px; flex: 1; min-width: 140px;
               box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .kpi-value {{ font-size: 1.9em; font-weight: 700; }}
  .kpi-title {{ font-size: 0.8em; color: #666; margin-top: 4px; }}
  .kpi-sub   {{ font-size: 0.78em; color: #999; margin-top: 2px; }}
  .charts-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .chart-box  {{ background: #fff; border-radius: 10px; padding: 18px; flex: 1; min-width: 280px;
                 box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .chart-box h3 {{ font-size: 0.9em; color: #555; margin-bottom: 14px; }}
  .level-summary {{ display: flex; gap: 12px; margin: 14px 0; flex-wrap: wrap; }}
  .level-box {{ border-radius: 8px; padding: 14px 20px; flex: 1; min-width: 120px; text-align: center; }}
  .level-box .lv-n {{ font-size: 2em; font-weight: 700; }}
  .level-box .lv-label {{ font-size: 0.82em; margin-top: 2px; }}
  .tbl {{ width: 100%; border-collapse: collapse; font-size: 0.88em; background: #fff;
          border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  .tbl th {{ background: #e8eaf6; color: #283593; padding: 10px 8px; text-align: left; }}
  .tbl td {{ padding: 9px 8px; border-bottom: 1px solid #f0f0f0; }}
  .tbl tr:last-child td {{ border-bottom: none; }}
  .tbl tr:hover {{ filter: brightness(0.97); }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px;
            font-size: 0.8em; font-weight: 600; }}
  .badge-unknown {{ color: #999; background: #f5f5f5; border: 1px solid #ccc; }}
  .attention-box {{ background: #fff3e0; border: 1px solid #ff9800; border-radius: 10px;
                    padding: 18px; margin-top: 8px; }}
  .footer {{ font-size: 0.78em; color: #bbb; text-align: center; margin-top: 32px; }}
  details {{ margin-bottom: 6px; }}
  details summary {{
    cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px;
    font-size: 1.1em; font-weight: 600; color: #283593;
    border-left: 4px solid #5c6bc0; padding: 8px 10px;
    background: #eef0fb; border-radius: 0 6px 6px 0; margin: 28px 0 0;
    user-select: none;
  }}
  details summary::-webkit-details-marker {{ display: none; }}
  details summary::before {{ content: '▶'; font-size: 0.7em; color: #5c6bc0; transition: transform .2s; }}
  details[open] summary::before {{ transform: rotate(90deg); }}
</style>
</head><body>
<div class="page">

  <h1>Aaron Owl — Teacher Usage Report</h1>
  <p class="meta">Course: <strong>{course_name}</strong> &nbsp;|&nbsp; Generated: {generated_date} &nbsp;|&nbsp; {n} students</p>

  <!-- KPI cards -->
  <div class="kpi-row">{kpis}</div>

  <!-- ALS definition box -->
  <details>
  <summary>Active Learning Score (ALS) — definition</summary>
  <div style="background:#e8eaf6;border-left:4px solid #3949ab;border-radius:8px;padding:16px 20px;margin:12px 0 18px;font-size:0.88em;line-height:1.7">
    <p style="margin-bottom:10px">
      The <strong>Active Learning Score</strong> is a single 0–100 index that captures
      <em>how meaningfully</em> each student engaged with the course platform —
      not just how often they logged in.
      It is computed from four components, each normalised relative to the rest of the class:
    </p>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#c5cae9">
        <th style="padding:6px 10px;text-align:left;border-radius:4px 0 0 4px">Component</th>
        <th style="padding:6px 10px;text-align:left">What it measures</th>
        <th style="padding:6px 10px;text-align:center;border-radius:0 4px 4px 0">Weight</th>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 10px"><strong>Consistency</strong></td>
        <td style="padding:6px 10px">Fraction of course weeks in which the student was active.
          A student who studies every week scores higher than one who crammed at the end.</td>
        <td style="padding:6px 10px;text-align:center">35%</td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:6px 10px"><strong>Active Interactions</strong></td>
        <td style="padding:6px 10px">Volume of deliberate learning actions: starting/completing
          quizzes and evaluations, clicking concepts, navigating to learning features.
          Passive events (logins, lecture browsing) are excluded.</td>
        <td style="padding:6px 10px;text-align:center">25%</td>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 10px"><strong>Feature Diversity</strong></td>
        <td style="padding:6px 10px">Number of distinct platform features the student used
          (quiz, evaluation, summaries, mind map, search, concepts, transcript, extra material).
          Students who explore multiple learning modes score higher.</td>
        <td style="padding:6px 10px;text-align:center">20%</td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:6px 10px"><strong>Session Depth</strong></td>
        <td style="padding:6px 10px">Ratio of <em>meaningful sessions</em> — sessions lasting
          at least 5 minutes, containing at least 3 events and at least one active learning action.
          Measures whether study time was focused rather than superficial.</td>
        <td style="padding:6px 10px;text-align:center">20%</td>
      </tr>
    </table>
    <p style="margin-top:10px;color:#555">
      Each component is ranked within this course cohort (percentile rank), so the score
      reflects a student's engagement <em>relative to their peers</em>, not an absolute standard.
      It is based solely on platform usage data and does not include exam or assignment grades.
    </p>
  </div>
  </details>

  <!-- Metrics glossary -->
  <details>
  <summary>Metric Definitions</summary>
  <div style="background:#fff;border-radius:8px;padding:16px 20px;margin:12px 0 18px;
              box-shadow:0 1px 4px rgba(0,0,0,.1);font-size:0.86em;line-height:1.75">
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#e8eaf6">
        <th style="padding:6px 12px;text-align:left;width:26%">Metric</th>
        <th style="padding:6px 12px;text-align:left">Definition</th>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 12px"><strong>Lecture Coverage</strong></td>
        <td style="padding:6px 12px">
          Percentage of course lectures the student <em>opened</em> at least once —
          meaning they had any platform interaction with that lecture
          (tab view, quiz click, search, concept click, etc.).
          It does <strong>not</strong> mean they watched the full video or studied the material in depth.
          The denominator is the total number of distinct lectures in the course
          (including lectures without assessments).
          A low average (e.g. 60%) may reflect students who dropped the course,
          enrolled late, or focused only on assessed lectures —
          check the per-student breakdown to distinguish these cases.
        </td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:6px 12px"><strong>Total Time</strong></td>
        <td style="padding:6px 12px">
          Estimated active study time, based on platform sessions.
          A <em>session</em> ends after 30 minutes of inactivity.
          Very long idle gaps are excluded; session duration is capped at 2 hours.
          This reflects time the student was actively using the platform,
          not total time since first login.
        </td>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 12px"><strong>Meaningful Sessions</strong></td>
        <td style="padding:6px 12px">
          Sessions that meet all three criteria:
          lasted at least 5 minutes,
          contained at least 3 events,
          and included at least one active learning action
          (quiz, evaluation, concept click, or navigation to a learning feature).
          Brief visits or accidental openings do not count.
        </td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:6px 12px"><strong>Active Interactions</strong></td>
        <td style="padding:6px 12px">
          Count of deliberate learning actions: starting or completing a quiz or evaluation,
          clicking on a concept, or navigating to search, summaries, mind map, concepts,
          or extra material. Login, lecture browsing, and passive video viewing are
          classified as passive and excluded from this count.
        </td>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 12px"><strong>Eval / Quiz Score</strong></td>
        <td style="padding:6px 12px">
          Average score across all attempts at in-platform evaluations or quizzes, scored 0–100.
          Evaluations are graded assessments; quizzes are self-check exercises
          (students may retake quizzes freely, which is why quiz scores are typically higher).
          These scores come from the Aaron Owl platform and do not reflect external exam results.
        </td>
      </tr>
      <tr style="background:#f5f5f5">
        <td style="padding:6px 12px"><strong>Consistency</strong></td>
        <td style="padding:6px 12px">
          Fraction of course weeks (Saturday–Friday) in which the student had at least
          one platform event. A student active in 12 of 18 weeks has a consistency of 67%.
          Consistent learners spread study time across the semester
          rather than concentrating it near deadlines.
        </td>
      </tr>
      <tr style="background:#fff">
        <td style="padding:6px 12px"><strong>Features Used</strong></td>
        <td style="padding:6px 12px">
          Number of distinct platform features the student used at least once out of:
          Quiz, Evaluation, Short Summary, Long Summary, Mind Map,
          Search, Concepts, Transcript, Extra Material (max 9).
          A higher count indicates broader engagement with the platform's learning tools.
        </td>
      </tr>
    </table>
  </div>
  </details>

  <!-- Engagement level summary -->
  <h2>Engagement Levels</h2>
  <p style="font-size:0.85em;color:#666;margin-bottom:10px">
    Students are grouped into three levels based on their Active Learning Score.
  </p>
  <div class="level-summary">
    <div class="level-box" style="background:{LEVEL_BG['High']};border:1px solid {LEVEL_COLOR['High']}">
      <div class="lv-n" style="color:{LEVEL_COLOR['High']}">{n_high}</div>
      <div class="lv-label" style="color:{LEVEL_COLOR['High']}">High Engagement<br>(score ≥ 60)</div>
    </div>
    <div class="level-box" style="background:{LEVEL_BG['Medium']};border:1px solid {LEVEL_COLOR['Medium']}">
      <div class="lv-n" style="color:{LEVEL_COLOR['Medium']}">{n_medium}</div>
      <div class="lv-label" style="color:{LEVEL_COLOR['Medium']}">Medium Engagement<br>(score 30–60)</div>
    </div>
    <div class="level-box" style="background:{LEVEL_BG['Low']};border:1px solid {LEVEL_COLOR['Low']}">
      <div class="lv-n" style="color:{LEVEL_COLOR['Low']}">{n_low}</div>
      <div class="lv-label" style="color:{LEVEL_COLOR['Low']}">Low Engagement<br>(score &lt; 30)</div>
    </div>
  </div>

  <!-- Charts -->
  <h2>Engagement Distribution &amp; Feature Adoption</h2>
  <div class="charts-row">
    <div class="chart-box" style="max-width:340px">
      <h3>Active Learning Score — Distribution</h3>
      <canvas id="alsChart" height="200"></canvas>
    </div>
    <div class="chart-box" style="max-width:340px">
      <h3>Lecture Coverage — Distribution</h3>
      <p style="font-size:0.78em;color:#888;margin-bottom:8px">% of lectures each student opened at least once</p>
      <canvas id="coverageChart" height="200"></canvas>
    </div>
    <div class="chart-box">
      <h3>Feature Adoption — % of students who used each feature</h3>
      <canvas id="featureChart" height="200"></canvas>
    </div>
    <div class="chart-box" style="max-width:220px">
      <h3>Engagement Level Breakdown</h3>
      <canvas id="pieChart" height="200"></canvas>
    </div>
  </div>

  <!-- Student table -->
  <h2>All Students (sorted: low engagement first)</h2>
  <table class="tbl">
    <tr>
      <th>Student</th>
      <th style="text-align:center">Level</th>
      <th style="text-align:center">ALS</th>
      <th style="text-align:center">Active Weeks</th>
      <th style="text-align:center">Total Time</th>
      <th style="text-align:center">Lectures</th>
      <th style="text-align:center">Avg Eval</th>
      <th style="text-align:center">Meaningful Sessions</th>
    </tr>
    {student_rows}
  </table>

  <!-- Post-Moed A retake-window analytics (grade-free; only if postA_ columns present) -->
  {_postA_section(df)}

  <!-- Tier dynamics: pre-A → post-A tier transitions (grade-free) -->
  {_tier_transition_section(df)}

  <!-- Attention needed -->
  <h2>⚠ Students Needing Attention (Low Engagement)</h2>
  <div class="attention-box">
    <p style="font-size:0.85em;color:#bf360c;margin-bottom:10px">
      These students have an Active Learning Score below 30.
      Consider reaching out to check if they need support.
    </p>
    {_attention_rows(df)}
  </div>

  <p class="footer">Aaron Owl Learning Analytics — report based on platform usage data only. No exam grades included.</p>
</div>

<script>
const alsData      = {_als_histogram(df)};
const coverageData = {_coverage_histogram(df)};
const featureData  = {_feature_adoption(df)};
const pieData      = {_engagement_pie(df)};

new Chart(document.getElementById('alsChart'), {{
  type: 'bar',
  data: alsData,
  options: {{ plugins: {{ legend: {{ display: false }} }},
             scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});

new Chart(document.getElementById('coverageChart'), {{
  type: 'bar',
  data: coverageData,
  options: {{ plugins: {{ legend: {{ display: false }} }},
             scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});

new Chart(document.getElementById('featureChart'), {{
  type: 'bar',
  data: featureData,
  options: {{
    indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true, max: 100,
                     ticks: {{ callback: v => v + '%' }} }} }}
  }}
}});

new Chart(document.getElementById('pieChart'), {{
  type: 'doughnut',
  data: pieData,
  options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
</script>
</body></html>'''


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', required=True)
    parser.add_argument('--course-name', default='Course')
    parser.add_argument('--out', default='.')
    args = parser.parse_args()

    from datetime import date
    df = pd.read_csv(args.features)

    html = generate(df, args.course_name, str(date.today()))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'usage_report.html'
    report_path.write_text(html, encoding='utf-8')
    print(f'Report saved: {report_path}')


if __name__ == '__main__':
    main()
