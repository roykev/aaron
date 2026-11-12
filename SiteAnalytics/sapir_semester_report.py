#!/usr/bin/env python3
"""
Semester summary report for one institute (default: Sapir, semester C 2026).

Reads the weekly Mixpanel exports (the same files the dashboard uses), keeps only
the courses listed for the semester, separates students from lecturers, and
writes a single self-contained Hebrew HTML report that covers EVERY course in
the list, including the ones with almost no activity.

Usage (defaults point at the aaron-analytics checkout next to this repo):
    python sapir_semester_report.py
    python sapir_semester_report.py --data-dir /path/to/aaron-analytics/data \
        --courses courses_C-2026.csv --start 2026-07-25 --end 2026-10-09 \
        --benchmark-courses courses_B-2026.csv --benchmark-start 2026-03-16 \
        --benchmark-end 2026-07-12 --out reports/sapir_C-2026_semester_report.html
"""

import argparse
import base64
import glob
import html
import os
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import yaml
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_TIMEOUT_MIN = 5
LOCAL_UTC_OFFSET_H = 3  # Israel daylight time for the summer semester

FEATURES = [
    # key, Hebrew label, matcher(df) -> bool mask
    ('short_summary', 'סיכום קצר', lambda d: d.tab.eq('short_summary') | d.section.eq('short_summary')),
    ('concepts', 'מושגים', lambda d: d.tab.eq('concepts') | d.section.eq('concepts') | d.event.isin(['concept_select', 'jump_to_concept'])),
    ('transcript', 'תמלול', lambda d: d.tab.eq('transcript') | d.section.eq('transcript')),
    ('long_summary', 'סיכום מורחב', lambda d: d.tab.eq('long_summary') | d.section.eq('long_summary')),
    ('mindmap', 'מפת חשיבה', lambda d: d.tab.eq('mindmap') | d.section.eq('mindmap')),
    ('quiz', 'תרגול (Quiz)', lambda d: d.event.str.contains('quiz', case=False, na=False)),
    ('chat', "צ'אט שאלות", lambda d: d.event.eq('chat_question_asked')),
    ('evaluation', 'הערכה עצמית', lambda d: d.event.str.contains('evaluation', case=False, na=False)),
]

HEB_DAYS = {'Sunday': 'א', 'Monday': 'ב', 'Tuesday': 'ג', 'Wednesday': 'ד', 'Thursday': 'ה', 'Friday': 'ו', 'Saturday': 'ש'}
DAY_ORDER = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def load_window(data_dir, courses_csv, start, end, institute_slug, blacklist, teacher_ids):
    """Load every complete week whose start falls inside [start, end] and keep the institute's courses."""
    courses = pd.read_csv(os.path.join(data_dir, courses_csv))
    courses = courses[courses['English Name'] == institute_slug]
    cmap = dict(zip(courses['Course ID'], courses['Course name']))
    reg = dict(zip(courses['Course ID'], courses['registered']))

    today = date.today()
    frames, weeks = [], []
    for f in sorted(glob.glob(os.path.join(data_dir, 'weekly', 'week_*.csv'))):
        parts = os.path.basename(f).replace('.csv', '').split('_')
        w_from, w_to = parts[1], parts[2]
        if w_from < start or w_from > end:
            continue
        if datetime.strptime(w_to, '%Y-%m-%d').date() >= today:
            continue  # incomplete week
        weeks.append(w_from)
        d = pd.read_csv(f, low_memory=False)
        d['week_from'] = w_from
        frames.append(d)
    if not frames:
        raise SystemExit(f'No complete weekly files between {start} and {end} in {data_dir}/weekly')

    df = pd.concat(frames, ignore_index=True)
    for col in ['tab', 'section', 'course', 'event', '$os', 'lecture']:
        if col not in df.columns:
            df[col] = np.nan
    df['uid'] = df['$user_id'].fillna(df['distinct_id'])
    df = df[~df['uid'].isin(blacklist)]
    # An event that names a lecture is attributed to the course that lecture belongs to (majority of its
    # events); the raw 'course' property lags behind when a user switches course inside the app.
    has_lec = df['lecture'].notna() & (df['lecture'] != 'course_overview')
    lec_course = df[has_lec].groupby('lecture')['course'].agg(lambda x: x.value_counts().index[0])
    df.loc[has_lec, 'course'] = df.loc[has_lec, 'lecture'].map(lec_course).fillna(df.loc[has_lec, 'course'])
    df = df[df['course'].isin(cmap)].copy()
    df['datetime'] = pd.to_datetime(df['time'], unit='s') + pd.Timedelta(hours=LOCAL_UTC_OFFSET_H)
    df['is_teacher'] = df['uid'].isin(teacher_ids)
    df['cname'] = df['course'].map(cmap)
    return df, cmap, reg, weeks


CONTENT_EVENTS = ['tab_change', 'sidebar_tab_change', 'concept_select', 'jump_to_concept', 'chat_question_asked',
                  'quiz_start', 'quiz_answer_click', 'quiz_next_question', 'quiz_previous_question', 'quiz_complete',
                  'evaluation_start', 'evaluation_answer_click', 'evaluation_next_question', 'feedback_submission_success']


def substantive(df):
    """Events that show a person actually used course content, as opposed to landing on the default course
    after login or a password reset. A lecture page other than the course overview, or any content tool event."""
    opened_lecture = df['lecture'].notna() & (df['lecture'] != 'course_overview')
    return opened_lecture | df['event'].isin(CONTENT_EVENTS)


def session_table(g):
    """One row per session for one user: start, minutes, whether it touched content, lectures opened."""
    g = g.sort_values('datetime')
    sess = (g['datetime'].diff().dt.total_seconds() / 60 > SESSION_TIMEOUT_MIN).cumsum()
    rows = []
    for _, sg in g.groupby(sess):
        rows.append({'start': sg['datetime'].min(),
                     'minutes': (sg['datetime'].max() - sg['datetime'].min()).total_seconds() / 60 + SESSION_TIMEOUT_MIN,
                     'content': bool(substantive(sg).any()),
                     'lectures': sg.loc[sg['lecture'].notna() & (sg['lecture'] != 'course_overview'), 'lecture'].nunique()})
    return pd.DataFrame(rows)


def inside_metrics(frame):
    """What happens once a person is in: sessions per user, return rates, session length."""
    if frame.empty:
        return None
    per, allsess = [], []
    for uid, g in frame.groupby('uid'):
        st = session_table(g)
        allsess.append(st)
        per.append({'uid': uid, 'sessions': len(st), 'days': st['start'].dt.date.nunique(),
                    'content_sessions': int(st['content'].sum()), 'total_min': st['minutes'].sum(),
                    'span_days': (st['start'].max() - st['start'].min()).days,
                    'weeks': g['week_from'].nunique(), 'lectures': int(st['lectures'].sum())})
    per = pd.DataFrame(per)
    allsess = pd.concat(allsess)
    content = allsess[allsess['content']]
    n = len(per)
    return {
        'users': n,
        'users_content': int((per['content_sessions'] >= 1).sum()),
        'sessions': len(allsess), 'content_sessions': len(content),
        'sessions_per_user_median': float(per['sessions'].median()), 'sessions_per_user_mean': float(per['sessions'].mean()),
        'one_session': int((per['sessions'] == 1).sum()),
        'returned_session': int((per['sessions'] >= 2).sum()),
        'returned_day': int((per['days'] >= 2).sum()),
        'returned_week': int((per['weeks'] >= 2).sum()),
        'session_median': float(allsess['minutes'].median()), 'session_mean': float(allsess['minutes'].mean()),
        'session_p75': float(allsess['minutes'].quantile(.75)), 'session_max': float(allsess['minutes'].max()),
        'content_session_median': float(content['minutes'].median()) if len(content) else 0.0,
        'lectures_per_content_session': float(content['lectures'].median()) if len(content) else 0.0,
        'total_min_median': float(per['total_min'].median()), 'total_min_mean': float(per['total_min'].mean()),
        'returners': per[per['days'] >= 2].sort_values('total_min', ascending=False),
        'by_hour': allsess['start'].dt.hour.value_counts().sort_index(),
    }


def user_sessions(g):
    """Session count and minutes for one user's (sorted) events: gap > timeout opens a new session."""
    g = g.sort_values('datetime')
    gaps = g['datetime'].diff().dt.total_seconds() / 60
    sess = (gaps > SESSION_TIMEOUT_MIN).cumsum()
    total = 0.0
    for _, sg in g.groupby(sess):
        total += (sg['datetime'].max() - sg['datetime'].min()).total_seconds() / 60 + SESSION_TIMEOUT_MIN
    return pd.Series({'minutes': total, 'sessions': int(sess.max()) + 1})


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------

def compute(df, cmap, reg, weeks, exclude_dates=()):
    st = df[~df['is_teacher']].copy()
    lt = df[df['is_teacher']].copy()
    excl = [pd.Timestamp(d).date() for d in exclude_dates]
    organic = df[~df['datetime'].dt.date.isin(excl)]
    m_inside = {'exclude_dates': list(exclude_dates),
                'students': inside_metrics(organic[~organic['is_teacher']]),
                'lecturers': inside_metrics(organic[organic['is_teacher']]),
                'students_all': inside_metrics(st)}
    n_students = st['uid'].nunique()
    m = {'inside': m_inside, 'n_students': n_students, 'n_lecturers': lt['uid'].nunique(), 'n_courses': len(cmap),
         'seats': int(sum(reg.values())), 'weeks': weeks, 'n_weeks': len(weeks), 'events': len(st)}

    # per-student time and persistence
    if n_students:
        ut = st.groupby('uid').apply(user_sessions)
        m['median_min'] = float(ut['minutes'].median())
        m['mean_min'] = float(ut['minutes'].mean())
        m['total_hours'] = float(ut['minutes'].sum() / 60)
        m['sessions'] = int(ut['sessions'].sum())
        wk = st.groupby('uid')['week_from'].nunique()
        m['pct_multi_week'] = float((wk > 1).mean() * 100)
        m['multi_week'] = int((wk > 1).sum())
        m['courses_per_student'] = float(st.groupby('uid')['course'].nunique().mean())
        os_first = st.groupby('uid')['$os'].first()
        m['mobile_students'] = int(os_first.isin(['iOS', 'Android']).sum())
        m['pct_mobile'] = float(os_first.isin(['iOS', 'Android']).mean() * 100)
    else:
        m.update(median_min=0, mean_min=0, total_hours=0, sessions=0, pct_multi_week=0, multi_week=0,
                 courses_per_student=0, mobile_students=0, pct_mobile=0)

    # weekly series
    rows = []
    for w in weeks:
        s = st[st['week_from'] == w]
        l = lt[lt['week_from'] == w]
        rows.append({'week': w, 'students': s['uid'].nunique(), 'lecturers': l['uid'].nunique(),
                     'courses': s['course'].nunique(), 'events': len(s)})
    m['weekly'] = pd.DataFrame(rows)

    # per course (every listed course, even with zero events)
    st_sub = st[substantive(st)]
    m['n_students_engaged'] = st_sub['uid'].nunique()
    m['n_students_landing_only'] = n_students - m['n_students_engaged']
    crows = []
    for cid, name in cmap.items():
        s_all = st[st['course'] == cid]
        s = st_sub[st_sub['course'] == cid]
        l = lt[lt['course'] == cid]
        n = s['uid'].nunique()
        if n:
            ut_c = s.groupby('uid').apply(user_sessions)
            minutes, sessions, med = float(ut_c['minutes'].sum()), int(ut_c['sessions'].sum()), float(ut_c['minutes'].median())
        else:
            minutes, sessions, med = 0.0, 0, 0.0
        crows.append({
            'course_id': cid, 'name': name, 'registered': int(reg[cid]), 'students': n,
            'pct': n / reg[cid] * 100 if reg[cid] else 0, 'sessions': sessions, 'minutes': minutes,
            'median_min': med, 'weeks': s['week_from'].nunique(), 'lecturer_events': len(l),
            'lecturers': l['uid'].nunique(),
            'chat_q': int((s['event'] == 'chat_question_asked').sum()),
            'quiz_starts': int((s['event'] == 'quiz_start').sum()),
            'last_seen': s['datetime'].max() if n else pd.NaT,
            'landed': s_all['uid'].nunique(),
        })
    m['courses'] = pd.DataFrame(crows).sort_values(['students', 'minutes'], ascending=False).reset_index(drop=True)

    # features (% of active students)
    feats = []
    for key, label, fn in FEATURES:
        mask = fn(st) if len(st) else pd.Series([], dtype=bool)
        users = st[mask]['uid'].nunique() if len(st) else 0
        feats.append({'key': key, 'label': label, 'users': users, 'pct': users / n_students * 100 if n_students else 0,
                      'courses': st[mask]['course'].nunique() if len(st) else 0})
    m['features'] = pd.DataFrame(feats)
    m['quiz_starts'] = int((st['event'] == 'quiz_start').sum())
    m['quiz_complete'] = int((st['event'] == 'quiz_complete').sum())
    m['chat_questions'] = int((st['event'] == 'chat_question_asked').sum())
    m['chat_by_course'] = st[st['event'] == 'chat_question_asked']['cname'].value_counts().to_dict()

    # login friction (all users of the institute's courses, students and lecturers)
    m['pw_fail'] = int((df['event'] == 'password_reset_failure').sum())
    m['pw_success'] = int((df['event'] == 'password_reset_success').sum())
    m['pw_fail_users'] = int(df[df['event'] == 'password_reset_failure']['uid'].nunique())

    # when do students work
    m['by_day'] = st['datetime'].dt.day_name().value_counts().reindex(DAY_ORDER).fillna(0).astype(int)
    m['by_hour'] = st['datetime'].dt.hour.value_counts().sort_index()
    daily = st.groupby(st['datetime'].dt.date)['uid'].nunique().sort_values(ascending=False)
    m['peak_day'] = (daily.index[0], int(daily.iloc[0])) if len(daily) else (None, 0)
    if len(daily):
        peak = st[st['datetime'].dt.date == daily.index[0]]
        m['peak_day_courses'] = peak['course'].nunique()
        best, best_start = 0, peak['datetime'].min()
        for t0 in peak['datetime'].sort_values().unique():
            t0 = pd.Timestamp(t0)
            n_win = peak[(peak['datetime'] >= t0) & (peak['datetime'] < t0 + pd.Timedelta(hours=1))]['uid'].nunique()
            if n_win > best:
                best, best_start = n_win, t0
        m['peak_hour'] = (best, best_start.strftime('%H:%M'), (best_start + pd.Timedelta(hours=1)).strftime('%H:%M'))
    else:
        m['peak_day_courses'], m['peak_hour'] = 0, (0, '', '')

    # lecturers
    lrows = []
    for uid, g in lt.groupby('uid'):
        lrows.append({'courses': sorted(g['cname'].unique().tolist()), 'events': len(g),
                      'edits': int(g['event'].isin(['publish_edit', 'save_edit', 'start_editing']).sum()),
                      'quiz': int(g['event'].str.contains('quiz|evaluation', na=False).sum()),
                      'reports': int(g['event'].eq('download_course_report').sum()),
                      'weeks': g['week_from'].nunique(), 'minutes': float(user_sessions(g)['minutes'])})
    m['lecturers'] = sorted(lrows, key=lambda r: -r['events'])
    m['courses_with_lecturer'] = int((m['courses']['lecturer_events'] > 0).sum())
    return m


# ----------------------------------------------------------------------------
# HTML helpers
# ----------------------------------------------------------------------------

def esc(s):
    return html.escape(str(s), quote=True)


def fmt_min(minutes):
    minutes = int(round(minutes))
    if minutes >= 60:
        return f'{minutes // 60} ש׳ {minutes % 60} ד׳'
    return f'{minutes} ד׳'


def dmy(s):
    d = datetime.strptime(s, '%Y-%m-%d')
    return d.strftime('%d.%m')


def logo_data_uri(data_dir):
    for p in [os.path.join(HERE, 'assets', 'aaronowl-logo.png'),
              os.path.join(os.path.dirname(data_dir), 'assets', 'aaronowl-logo.png'),
              os.path.join(HERE, '..', 'teacher_side', 'assets', 'aaronowl-logo.png')]:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    return ''


def svg_weekly(weekly):
    """Grouped bars: students and lecturers per week. One scale, direct labels, native tooltips."""
    n = len(weekly)
    W, H = 760, 260
    ml, mr, mt, mb = 36, 12, 24, 44
    pw, ph = W - ml - mr, H - mt - mb
    ymax = max(1, int(weekly[['students', 'lecturers']].values.max()))
    step = 5 if ymax > 12 else (2 if ymax > 6 else 1)
    ymax = ((ymax + step - 1) // step) * step
    slot = pw / n
    bw = min(28, slot * 0.32)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="סטודנטים ומרצים פעילים לפי שבוע" class="chart">']
    for v in range(0, ymax + 1, step):
        y = mt + ph - v / ymax * ph
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" class="tick" text-anchor="end">{v}</text>')
    for i, r in weekly.iterrows():
        cx = ml + slot * i + slot / 2
        for j, (key, cls) in enumerate([('students', 's1'), ('lecturers', 's2')]):
            v = int(r[key])
            x = cx - bw - 1 if j == 0 else cx + 1
            h = v / ymax * ph
            y = mt + ph - h
            title = f"שבוע {dmy(r['week'])}: {v} {'סטודנטים' if key == 'students' else 'מרצים'}"
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" class="bar {cls}"><title>{esc(title)}</title></rect>')
            if v:
                out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 5:.1f}" class="val" text-anchor="middle">{v}</text>')
        out.append(f'<text x="{cx:.1f}" y="{H - mb + 18}" class="tick" text-anchor="middle">{dmy(r["week"])}</text>')
    out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{mt + ph}" y2="{mt + ph}" class="axis"/>')
    out.append('</svg>')
    return '\n'.join(out)


def svg_features(feats, bench):
    """Horizontal paired bars growing right-to-left: this semester vs benchmark, % of active students."""
    rows = feats.to_dict('records')
    W = 760
    rh = 40
    ml, mr, mt = 56, 130, 8
    H = mt + rh * len(rows) + 8
    pw = W - ml - mr
    right = W - mr
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="שימוש בכלים, אחוז מהסטודנטים הפעילים" class="chart">']
    for v in (25, 50, 75, 100):
        x = right - v / 100 * pw
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{mt}" y2="{H - 8}" class="grid"/>')
    for i, r in enumerate(rows):
        y = mt + rh * i
        out.append(f'<text x="{W - 6}" y="{y + 20}" class="lbl" text-anchor="end">{esc(r["label"])}</text>')
        b = bench.get(r['key'], 0) if bench else None
        pairs = [(r['pct'], 's1', f"סמסטר ג׳: {r['pct']:.0f}% ({r['users']} סטודנטים)")]
        if b is not None:
            pairs.append((b, 's3', f"סמסטר ב׳: {b:.0f}%"))
        for j, (pct, cls, title) in enumerate(pairs):
            bh = 12 if len(pairs) == 2 else 20
            by = y + 6 + j * (bh + 2)
            w = max(0, pct) / 100 * pw
            out.append(f'<rect x="{right - w:.1f}" y="{by}" width="{w:.1f}" height="{bh}" rx="3" class="bar {cls}"><title>{esc(title)}</title></rect>')
            out.append(f'<text x="{right - w - 6:.1f}" y="{by + bh - 2}" class="val" text-anchor="end">{pct:.0f}%</text>')
    out.append('</svg>')
    return '\n'.join(out)


def svg_days(by_day):
    W, H = 760, 120
    ml, mr, mt, mb = 12, 12, 20, 26
    pw, ph = W - ml - mr, H - mt - mb
    mx = max(1, int(by_day.max()))
    slot = pw / 7
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="אירועי סטודנטים לפי יום בשבוע" class="chart">']
    for i, day in enumerate(DAY_ORDER):
        v = int(by_day.get(day, 0))
        # RTL reading: Sunday on the right
        cx = W - mr - slot * i - slot / 2
        h = v / mx * ph
        out.append(f'<rect x="{cx - 22:.1f}" y="{mt + ph - h:.1f}" width="44" height="{h:.1f}" rx="3" class="bar s1"><title>{esc(f"יום {HEB_DAYS[day]}׳: {v} אירועים")}</title></rect>')
        out.append(f'<text x="{cx:.1f}" y="{mt + ph - h - 5:.1f}" class="val" text-anchor="middle">{v}</text>')
        out.append(f'<text x="{cx:.1f}" y="{H - 8}" class="tick" text-anchor="middle">{HEB_DAYS[day]}׳</text>')
    out.append('</svg>')
    return '\n'.join(out)


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------

CSS = """
<style>
:root{
  --bg:#f6f7f5; --surface:#ffffff; --ink:#171b1f; --ink-2:#4b5359; --ink-3:#7a8288; --line:#dfe3e0;
  --accent:#2a78d6; --accent-ink:#1c5cab; --s1:#2a78d6; --s2:#eb6834; --s3:#9ec5f4; --warn-bg:#fff4e8; --warn-ink:#8a3d10;
  --good-bg:#e8f6ef; --good-ink:#1c6b45; --grid:#e6e9e6;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  color-scheme:dark; --bg:#15181b; --surface:#1e2226; --ink:#f1f2f0; --ink-2:#c0c6c9; --ink-3:#8d959a; --line:#333a3f;
  --accent:#3987e5; --accent-ink:#86b6ef; --s1:#3987e5; --s2:#d95926; --s3:#3b5a7e; --warn-bg:#3a2415; --warn-ink:#f2b78a;
  --good-bg:#15302a; --good-ink:#8fd6b5; --grid:#2c3236; }}
:root[data-theme="dark"]{
  color-scheme:dark; --bg:#15181b; --surface:#1e2226; --ink:#f1f2f0; --ink-2:#c0c6c9; --ink-3:#8d959a; --line:#333a3f;
  --accent:#3987e5; --accent-ink:#86b6ef; --s1:#3987e5; --s2:#d95926; --s3:#3b5a7e; --warn-bg:#3a2415; --warn-ink:#f2b78a;
  --good-bg:#15302a; --good-ink:#8fd6b5; --grid:#2c3236; }
html{direction:rtl}
body{background:var(--bg); color:var(--ink); font-family:'Heebo',system-ui,-apple-system,'Segoe UI',Arial,sans-serif; font-size:16px; line-height:1.6; padding-inline:16px; padding-block:24px 64px; margin:0}
.wrap{max-width:880px; margin:0 auto}
h1,h2,h3{font-family:'Frank Ruhl Libre','Heebo',serif; text-wrap:balance; line-height:1.2; margin:0}
h1{font-size:2.3rem; font-weight:700}
h2{font-size:1.5rem; font-weight:700; margin-block:0 12px}
h3{font-size:1.1rem; font-weight:700; margin-block:12px 6px}
p{margin:0 0 12px; max-width:68ch}
.eyebrow{font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
header{display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap; padding-bottom:20px; border-bottom:1px solid var(--line); margin-bottom:28px}
header .meta{color:var(--ink-2); font-size:.95rem}
header img{height:56px; width:auto; flex:none}
section{margin-bottom:40px}
.num{font-variant-numeric:tabular-nums}
.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-block:16px 20px}
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px}
.kpi .v{font-size:1.9rem; font-weight:700; line-height:1.1; font-variant-numeric:tabular-nums}
.kpi .l{color:var(--ink-2); font-size:.85rem; margin-top:4px}
.kpi .d{color:var(--ink-3); font-size:.78rem; margin-top:2px}
.callout{border-radius:10px; padding:14px 18px; margin-block:12px 16px; border:1px solid var(--line); background:var(--surface)}
.callout.warn{background:var(--warn-bg); color:var(--warn-ink); border-color:transparent}
.callout.good{background:var(--good-bg); color:var(--good-ink); border-color:transparent}
.callout p{color:inherit; margin:0}
.chart{direction:ltr; width:100%; height:auto; display:block; background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:8px; box-sizing:border-box}
.chart .grid{stroke:var(--grid); stroke-width:1}
.chart .axis{stroke:var(--line); stroke-width:1}
.chart .tick{fill:var(--ink-3); font-size:12px; font-family:inherit}
.chart .lbl{fill:var(--ink); font-size:13px; font-family:inherit}
.chart .val{fill:var(--ink-2); font-size:12px; font-family:inherit; font-variant-numeric:tabular-nums}
.chart .bar.s1{fill:var(--s1)} .chart .bar.s2{fill:var(--s2)} .chart .bar.s3{fill:var(--s3)}
.chart .bar{stroke:var(--surface); stroke-width:1}
.legend{display:flex; gap:18px; flex-wrap:wrap; font-size:.85rem; color:var(--ink-2); margin-block:8px 4px}
.legend span::before{content:''; display:inline-block; width:12px; height:12px; border-radius:3px; margin-inline-end:6px; vertical-align:-1px; background:var(--s1)}
.legend .l2::before{background:var(--s2)} .legend .l3::before{background:var(--s3)}
.tablewrap{overflow-x:auto; background:var(--surface); border:1px solid var(--line); border-radius:10px}
table{border-collapse:collapse; width:100%; font-size:.92rem}
th,td{padding:9px 12px; text-align:right; border-bottom:1px solid var(--line); vertical-align:top; white-space:nowrap}
th{font-size:.78rem; letter-spacing:.04em; color:var(--ink-3); font-weight:600; background:var(--surface); position:sticky; top:0}
td.n,th.n{font-variant-numeric:tabular-nums; text-align:left; direction:ltr}
tr:last-child td{border-bottom:none}
tr.quiet td{color:var(--ink-3)}
td.name{white-space:normal; min-width:180px; font-weight:500}
tr.quiet td.name{font-weight:400}
.sub{font-size:.78rem; color:var(--ink-3); font-weight:400; margin-top:2px}
.pill{display:inline-block; font-size:.74rem; padding:1px 8px; border-radius:999px; border:1px solid var(--line); color:var(--ink-2); margin-inline-start:6px; vertical-align:1px}
.pill.on{background:var(--good-bg); color:var(--good-ink); border-color:transparent}
.pill.off{background:transparent; color:var(--ink-3)}
.meter{display:inline-block; height:8px; width:80px; background:var(--grid); border-radius:4px; vertical-align:middle; margin-inline-start:8px; overflow:hidden; direction:ltr}
.meter i{display:block; height:100%; background:var(--s1); border-radius:4px}
ol.recs{padding-inline-start:22px; margin:0}
ol.recs li{margin-bottom:12px; max-width:68ch}
ol.recs b{font-weight:700}
.note{font-size:.85rem; color:var(--ink-3); border-top:1px solid var(--line); padding-top:14px; margin-top:24px}
.note p{max-width:none}
.two{display:grid; grid-template-columns:1fr 1fr; gap:16px}
@media (max-width:640px){ .two{grid-template-columns:1fr} h1{font-size:1.8rem} th,td{padding:8px 8px} }
a{color:var(--accent-ink)}
</style>
"""


def build_html(m, b, args, logo):
    c = m['courses']
    wk = m['weekly']
    active = c[c['students'] > 0]
    quiet = c[c['students'] <= 1]
    peak_date, peak_n = m['peak_day']
    peak_dmy = peak_date.strftime('%d.%m.%Y') if peak_date else ''
    peak_hour = m['peak_hour']
    last_data = datetime.strptime(m['weeks'][-1], '%Y-%m-%d') + timedelta(days=6)
    top = c.iloc[0]
    n_single = int((c['sessions'] <= 1).sum())
    no_lect = c[c['lecturer_events'] == 0]

    def kpi(v, l, d=''):
        return f'<div class="kpi"><div class="v num">{v}</div><div class="l">{l}</div>' + (f'<div class="d">{d}</div>' if d else '') + '</div>'

    # ---- section 1: summary
    bench_line = ''
    if b:
        bench_line = (f"בסמסטר ב׳ (עשרים קורסים של ספיר, {b['n_students']} סטודנטים פעילים) החציון היה {fmt_min(b['median_min'])} לסטודנט "
                      f"ו-{b['pct_multi_week']:.0f}% מהסטודנטים חזרו ליותר משבוע אחד.")
    summary = f"""
<section id="summary">
<div class="eyebrow">1 · תמצית</div>
<h2>מה קרה בקיץ</h2>
<p>הפלטפורמה הופעלה ב-{m['n_courses']} קורסי קיץ ({m['seats']} מקומות רישום, מפוצלים לכמה קבוצות לימוד). עד {last_data.strftime('%d.%m.%Y')} נכנסו אליה
<b>{m['n_students']} סטודנטים</b> ו-<b>{m['n_lecturers']} מרצים</b>; {m['n_students_engaged']} מהסטודנטים פתחו הרצאה או השתמשו בכלי תוכן, והשאר הגיעו רק לעמוד הנחיתה של הקורס לאחר הכניסה או איפוס הסיסמה. כמעט כל הפעילות התרחשה ביום אחד: ב-{peak_dmy} (יום {HEB_DAYS[peak_date.strftime('%A')] if peak_date else ''}׳)
נכנסו {peak_n} סטודנטים ל-{m['peak_day_courses']} קורסים, {peak_hour[0]} מהם בתוך שעה אחת (<span dir="ltr">{peak_hour[1]}–{peak_hour[2]}</span>), ככל הנראה במסגרת הדגמה בכיתה. מחוץ לאותו יום הפעילות הייתה דלילה: {m['multi_week']} סטודנטים בלבד חזרו לפלטפורמה ביותר משבוע אחד.</p>
<div class="kpis">
{kpi(m['n_students_engaged'], 'סטודנטים שהשתמשו בתוכן', f"{m['n_students']} נכנסו לפלטפורמה, מתוך {m['seats']} מקומות רישום")}
{kpi(f"{m['courses_with_lecturer']}/{m['n_courses']}", 'קורסים עם מרצה פעיל', f"{m['n_lecturers']} מרצים נכנסו לפלטפורמה")}
{kpi(fmt_min(m['median_min']), 'זמן חציוני לסטודנט', 'לאורך כל הסמסטר')}
{kpi(f"{m['pct_multi_week']:.0f}%", 'חזרו ליותר משבוע', f"{m['multi_week']} מתוך {m['n_students']}")}
{kpi(f"{m['pct_mobile']:.0f}%", 'גולשים מהטלפון', f"{m['mobile_students']} מתוך {m['n_students']}")}
{kpi(m['pw_fail'], 'ניסיונות איפוס סיסמה שנכשלו', f"{m['pw_fail_users']} משתמשים, מול {m['pw_success']} הצלחות")}
</div>
<p>{bench_line}</p>
</section>
"""

    # ---- section 2: weekly
    weekly_html = f"""
<section id="weekly">
<div class="eyebrow">2 · ציר הזמן</div>
<h2>סטודנטים ומרצים פעילים לפי שבוע</h2>
<p>שבועות נספרים משבת עד שישי. השבוע הנוכחי, שטרם הסתיים, אינו מוצג. שבוע ה-{dmy(wk.iloc[wk['students'].idxmax()]['week'])} הוא שבוע ההדגמה בכיתה; אחריו נרשמו {int(wk['students'].iloc[wk['students'].idxmax() + 1:].sum())} כניסות-שבועיות של סטודנטים בסך הכול.</p>
<div class="legend"><span>סטודנטים</span><span class="l2">מרצים</span></div>
{svg_weekly(wk)}
</section>
"""

    # ---- section 3: all courses
    def row(r):
        cls = ' class="quiet"' if r['students'] <= 1 else ''
        lect = '<span class="pill on">מרצה פעיל</span>' if r['lecturer_events'] > 0 else '<span class="pill off">ללא מרצה</span>'
        last = r['last_seen'].strftime('%d.%m') if pd.notna(r['last_seen']) else '—'
        meter = f'<span class="meter"><i style="width:{min(100, r["pct"]):.0f}%"></i></span>'
        extra = []
        if r['chat_q']:
            extra.append(f"{r['chat_q']} שאלות צ׳אט")
        if r['quiz_starts']:
            extra.append(f"{r['quiz_starts']} תרגולים")
        who = ''
        if pd.notna(r.get('lecturer')):
            who = f'<div class="sub">{esc(r["lecturer"])} · {esc(r["program"])} · יום {esc(r["day"])}׳ <span dir="ltr">{esc(r["from"])}–{esc(r["to"])}</span></div>'
        return (f'<tr{cls}><td class="name">{esc(r["name"])}{lect}{who}</td>'
                f'<td class="n">{r["students"]} / {r["registered"]}</td>'
                f'<td class="n">{r["pct"]:.0f}%{meter}</td>'
                f'<td class="n">{r["landed"]}</td>'
                f'<td class="n">{r["sessions"]}</td>'
                f'<td class="n">{fmt_min(r["minutes"])}</td>'
                f'<td class="n">{r["weeks"]}</td>'
                f'<td class="n">{last}</td>'
                f'<td>{", ".join(extra) if extra else "—"}</td></tr>')

    courses_html = f"""
<section id="courses">
<div class="eyebrow">3 · כל הקורסים</div>
<h2>{m['n_courses']} הקורסים, מהפעיל ביותר לשקט ביותר</h2>
<p>הטבלה כוללת את כל הקורסים ברשימת הסמסטר, גם אלה שראו ביקור יחיד. "סטודנטים" הם משתמשים שאינם מרצים שפתחו הרצאה או השתמשו בכלי תוכן בקורס; כניסה לעמוד הקורס בלבד (למשל הקורס שנפתח אוטומטית אחרי איפוס סיסמה) נספרת בעמודה "נחתו" ולא כשימוש. האחוז מחושב מול מספר הרשומים לקורס.
ב-{n_single} קורסים נרשמה כניסה אחת בלבד לאורך כל הסמסטר, וב-{len(no_lect)} קורסים המרצה לא נכנס כלל.</p>
<div class="tablewrap"><table>
<thead><tr><th>קורס</th><th class="n">סטודנטים / רשומים</th><th class="n">אחוז פעילים</th><th class="n">נחתו</th><th class="n">כניסות</th><th class="n">זמן מצטבר</th><th class="n">שבועות</th><th class="n">ביקור אחרון</th><th>שימוש בולט</th></tr></thead>
<tbody>{''.join(row(r) for _, r in c.iterrows())}</tbody>
</table></div>
<div class="callout">
<p><b>הקורס הבולט:</b> {esc(top['name'])} ({top['students']} סטודנטים, {fmt_min(top['minutes'])} מצטבר). {esc(c.sort_values('minutes', ascending=False).iloc[0]['name'])} הוא הקורס עם הכי הרבה זמן שימוש{' ועם המרצה הפעיל ביותר' if c.sort_values('minutes', ascending=False).iloc[0]['lecturer_events'] > 0 else ''}.
ב-{len(quiet)} קורסים ({', '.join(esc(n) for n in quiet['name'].tolist()[:5])}{'…' if len(quiet) > 5 else ''}) השתמש בתוכן סטודנט אחד לכל היותר.</p>
</div>
</section>
"""

    # ---- section 4: features
    bench_feats = {r['key']: r['pct'] for r in b['features'].to_dict('records')} if b else None
    f = m['features'].sort_values('pct', ascending=False)
    ftop = f.iloc[0]
    features_html = f"""
<section id="features">
<div class="eyebrow">4 · מה הסטודנטים עשו</div>
<h2>שימוש בכלים, כאחוז מהסטודנטים הפעילים</h2>
<p>{esc(ftop['label'])} הוא הכלי הנפוץ ביותר ({ftop['pct']:.0f}% מהסטודנטים, ב-{ftop['courses']} קורסים). הצ׳אט נשאל {m['chat_questions']} שאלות, רובן ב{esc(next(iter(m['chat_by_course']), ''))}.
תרגולים הותחלו {m['quiz_starts']} פעמים והושלמו {m['quiz_complete']} פעמים. הערכה עצמית לא הופעלה כלל.
{'לשם השוואה מוצג גם סמסטר ב׳ (בר בהיר).' if b else ''}</p>
<div class="legend"><span>סמסטר ג׳ (קיץ)</span>{'<span class="l3">סמסטר ב׳</span>' if b else ''}</div>
{svg_features(f, bench_feats)}
</section>
"""

    # ---- section 5: lecturers
    name_by_course = dict(zip(c['name'], c['lecturer'])) if 'lecturer' in c.columns else {}
    def lname(r):
        n = name_by_course.get(r['courses'][0])
        return f'<b>{esc(n)}</b><br>' if isinstance(n, str) else ''
    lrows = ''.join(
        f'<tr><td class="name">{lname(r)}{esc(", ".join(r["courses"]))}</td><td class="n">{r["weeks"]}</td><td class="n">{fmt_min(r["minutes"])}</td>'
        f'<td class="n">{r["edits"]}</td><td class="n">{r["quiz"]}</td><td class="n">{r["reports"]}</td></tr>'
        for r in m['lecturers'])
    lecturers_html = f"""
<section id="lecturers">
<div class="eyebrow">5 · מרצים</div>
<h2>{m['n_lecturers']} מרצים נכנסו, {len(no_lect)} קורסים ללא נוכחות מרצה</h2>
<p>לפי רשימת המכללה, {c['lecturer'].nunique() if 'lecturer' in c.columns else ''} מרצים מלמדים את {m['n_courses']} הקורסים בשלוש מגמות (חשמל, מכטרוניקה, בטיחות). המרצים מזוהים בפלטפורמה לפי רשימת הסגל; השורות מסודרות לפי היקף הפעילות, ומרצה שמלמד כמה קורסים מופיע בשורה אחת.</p>
<div class="tablewrap"><table>
<thead><tr><th>קורסים</th><th class="n">שבועות פעילים</th><th class="n">זמן מצטבר</th><th class="n">עריכות ופרסום</th><th class="n">פעולות תרגול והערכה</th><th class="n">הורדות דוח</th></tr></thead>
<tbody>{lrows}</tbody></table></div>
<div class="callout warn"><p>הקורסים ללא מרצה פעיל: {', '.join(esc(n) for n in no_lect['name'].tolist())}. בקורסים אלה התוכן לא נבדק, לא נערך ולא פורסם תרגול, והסטודנטים לא הופנו לפלטפורמה במהלך הסמסטר.</p></div>
</section>
"""

    # ---- section 6: usage patterns
    by_hour = m['by_hour']
    top_hours = by_hour.sort_values(ascending=False).head(2).index.tolist() if len(by_hour) else []
    patterns_html = f"""
<section id="patterns">
<div class="eyebrow">6 · דפוסי שימוש וחסמים</div>
<h2>מתי ואיך נכנסים, ומה מפריע</h2>
<div class="two">
<div>
<h3>ימים בשבוע</h3>
{svg_days(m['by_day'])}
<p style="margin-top:8px">יום ה׳ הוא יום הלימודים העיקרי בפלטפורמה. שעות השיא: <span dir="ltr">{', '.join(f'{h:02d}:00' for h in sorted(top_hours))}</span>.</p>
</div>
<div>
<h3>מכשיר</h3>
<p>{m['mobile_students']} מתוך {m['n_students']} הסטודנטים ({m['pct_mobile']:.0f}%) נכנסו מהטלפון. {'בסמסטר ב׳ שיעור זה עמד על ' + f"{b['pct_mobile']:.0f}%." if b else ''} המסך הקטן מסביר את ההעדפה לסיכום הקצר ולמושגים על פני הסיכום המורחב.</p>
<h3>כניסה למערכת</h3>
<div class="callout warn"><p>{m['pw_fail']} ניסיונות איפוס סיסמה נכשלו אצל {m['pw_fail_users']} משתמשים (מול {m['pw_success']} איפוסים שהצליחו). זהו חסם כניסה ממשי עבור קבוצה קטנה, ואפשר לפתור אותו במדריך כניסה קצר או בליווי בשיעור הראשון.</p></div>
</div>
</div>
</section>
"""

    # ---- section 7: once inside (organic, demo day excluded)
    ins, inl, ina = m['inside']['students'], m['inside']['lecturers'], m['inside']['students_all']
    excl_txt = ', '.join(datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m') for d in m['inside']['exclude_dates'])

    def irow(label, fs, fl):
        return f'<tr><td>{label}</td><td class="n">{fs}</td><td class="n">{fl}</td></tr>'

    def pct(a, n):
        return f'{a} ({a / n * 100:.0f}%)' if n else '0'

    if ins and inl:
        inside_rows = ''.join([
            irow('נכנסו לפלטפורמה', ins['users'], inl['users']),
            irow('פתחו הרצאה או כלי תוכן', pct(ins['users_content'], ins['users']), pct(inl['users_content'], inl['users'])),
            irow('סך מפגשים (sessions)', ins['sessions'], inl['sessions']),
            irow('מפגשים לאדם, חציון', f"{ins['sessions_per_user_median']:.0f}", f"{inl['sessions_per_user_median']:.0f}"),
            irow('ביקור יחיד בלבד', pct(ins['one_session'], ins['users']), pct(inl['one_session'], inl['users'])),
            irow('חזרו למפגש נוסף', pct(ins['returned_session'], ins['users']), pct(inl['returned_session'], inl['users'])),
            irow('חזרו ביום אחר', pct(ins['returned_day'], ins['users']), pct(inl['returned_day'], inl['users'])),
            irow('חזרו בשבוע אחר', pct(ins['returned_week'], ins['users']), pct(inl['returned_week'], inl['users'])),
            irow('אורך מפגש, חציון', fmt_min(ins['session_median']), fmt_min(inl['session_median'])),
            irow('אורך מפגש, ממוצע', fmt_min(ins['session_mean']), fmt_min(inl['session_mean'])),
            irow('המפגש הארוך ביותר', fmt_min(ins['session_max']), fmt_min(inl['session_max'])),
            irow('הרצאות שנפתחו במפגש תוכן, חציון', f"{ins['lectures_per_content_session']:.0f}", f"{inl['lectures_per_content_session']:.0f}"),
            irow('זמן כולל לאדם, חציון', fmt_min(ins['total_min_median']), fmt_min(inl['total_min_median'])),
            irow('זמן כולל לאדם, ממוצע', fmt_min(ins['total_min_mean']), fmt_min(inl['total_min_mean'])),
        ])
        ret = ins['returners']
        ret_rows = ''.join(f'<tr><td class="n">{r["sessions"]}</td><td class="n">{r["days"]}</td><td class="n">{r["weeks"]}</td><td class="n">{r["lectures"]}</td><td class="n">{fmt_min(r["total_min"])}</td></tr>' for _, r in ret.iterrows())
        inside_html = f"""
<section id="inside">
<div class="eyebrow">7 · אחרי הכניסה</div>
<h2>מה קורה אחרי שסטודנט או מרצה נכנסים</h2>
<p>הסעיף הזה מודד שימוש עצמאי בלבד: יום ההדגמה בכיתה ({excl_txt}) הוצא מהחישוב. מפגש (session) מסתיים אחרי {SESSION_TIMEOUT_MIN} דקות ללא פעולה.
ללא ההדגמה נכנסו {ins['users']} סטודנטים; {ins['one_session']} מהם ביקרו פעם אחת בלבד ו-{ins['returned_day']} חזרו ביום אחר. מרצה טיפוסי חוזר לפלטפורמה; סטודנט טיפוסי לא.</p>
<div class="tablewrap"><table>
<thead><tr><th>מדד</th><th class="n">סטודנטים</th><th class="n">מרצים</th></tr></thead>
<tbody>{inside_rows}</tbody></table></div>
<h3>הסטודנטים שחזרו</h3>
<p>{len(ret)} סטודנטים חזרו ביום אחר. אלה הסטודנטים שהפלטפורמה כן נכנסה אצלם לשגרה, ומהם אפשר ללמוד מה עובד.</p>
<div class="tablewrap"><table>
<thead><tr><th class="n">מפגשים</th><th class="n">ימים</th><th class="n">שבועות</th><th class="n">הרצאות שנפתחו</th><th class="n">זמן כולל</th></tr></thead>
<tbody>{ret_rows}</tbody></table></div>
<p style="margin-top:12px">כולל יום ההדגמה: {ina['users']} סטודנטים, {ina['returned_day']} חזרו ביום אחר, חציון מפגש {fmt_min(ina['session_median'])}. ההדגמה מוסיפה כניסות אך כמעט לא חזרות: {ina['returned_day'] - ins['returned_day']} מהסטודנטים שהגיעו רק דרכה חזרו אחר כך.</p>
</section>
"""
    else:
        inside_html = ''

    # ---- section 8: benchmark
    bench_html = ''
    if b:
        def brow(l, cv, bv):
            return f'<tr><td>{l}</td><td class="n">{cv}</td><td class="n">{bv}</td></tr>'
        bench_html = f"""
<section id="benchmark">
<div class="eyebrow">8 · השוואה לסמסטר ב׳</div>
<h2>סמסטר קיץ מול סמסטר ב׳ בספיר</h2>
<p>סמסטר ב׳ נמשך {b['n_weeks']} שבועות מול {m['n_weeks']} שבועות שהושלמו עד כה בקיץ, ולכן ההשוואה היא בעיקר על עומק השימוש לסטודנט ועל שיעור החזרה, לא על המספרים המוחלטים.</p>
<div class="tablewrap"><table>
<thead><tr><th>מדד</th><th class="n">סמסטר ג׳ (קיץ)</th><th class="n">סמסטר ב׳</th></tr></thead><tbody>
{brow('קורסים ברשימה', m['n_courses'], b['n_courses'])}
{brow('קורסים עם מרצה פעיל', m['courses_with_lecturer'], b['courses_with_lecturer'])}
{brow('סטודנטים פעילים', m['n_students'], b['n_students'])}
{brow('מרצים פעילים', m['n_lecturers'], b['n_lecturers'])}
{brow('זמן חציוני לסטודנט', fmt_min(m['median_min']), fmt_min(b['median_min']))}
{brow('חזרו ליותר משבוע אחד', f"{m['pct_multi_week']:.0f}%", f"{b['pct_multi_week']:.0f}%")}
{brow('גולשים מהטלפון', f"{m['pct_mobile']:.0f}%", f"{b['pct_mobile']:.0f}%")}
{brow('השתמשו בתרגול', f"{m['features'].set_index('key').loc['quiz','pct']:.0f}%", f"{b['features'].set_index('key').loc['quiz','pct']:.0f}%")}
{brow('שאלו בצ׳אט', f"{m['features'].set_index('key').loc['chat','pct']:.0f}%", f"{b['features'].set_index('key').loc['chat','pct']:.0f}%")}
{brow('איפוסי סיסמה שנכשלו', m['pw_fail'], b['pw_fail'])}
</tbody></table></div>
</section>
"""

    # ---- section 8: recommendations
    recs_html = f"""
<section id="recs">
<div class="eyebrow">{9 if b else 8} · המלצות</div>
<h2>מה כדאי לעשות לקראת סמסטר א׳</h2>
<ol class="recs">
<li><b>ההדגמה בכיתה עובדת. לחזור עליה בכל קורס, לא פעם אחת לסמסטר.</b> ביום ההדגמה נכנסו {peak_n} סטודנטים, {peak_hour[0]} מהם בתוך שעה אחת, יותר מבכל שאר הסמסטר יחד. עשר דקות בשיעור הראשון של כל קורס, עם משימה קטנה (למשל תרגול על ההרצאה הראשונה), הן הדרך הזולה ביותר להכפיל את השימוש.</li>
<li><b>להפעיל את המרצים לפני הסטודנטים.</b> רק ב-{m['courses_with_lecturer']} מ-{m['n_courses']} הקורסים המרצה נכנס. הקורס עם המרצה הפעיל ביותר הוא גם הקורס עם הכי הרבה זמן סטודנטים. מומלץ מפגש הכנה של חצי שעה לכל מרצה, שבו הוא בודק את התוכן ומפרסם תרגול אחד לפחות.</li>
<li><b>לפתור את חסם הכניסה.</b> {m['pw_fail']} איפוסי סיסמה כושלים אצל {m['pw_fail_users']} משתמשים בסמסטר קטן הם אות אזהרה. מדריך כניסה בעמוד אחד (או כניסה מאוחדת דרך המכללה) ומענה מהיר בשבוע הראשון ימנעו נשירה עוד לפני השימוש הראשון.</li>
<li><b>לתכנן לטלפון.</b> {m['pct_mobile']:.0f}% מהסטודנטים נכנסו מהנייד והשתמשו בעיקר בסיכום הקצר ובמושגים. כדאי להציג את הפלטפורמה כ"סיכום ותרגול בדרך הביתה" ולוודא שהתרגולים קצרים.</li>
<li><b>למדוד שוב אחרי הבחינות.</b> הסמסטר נמשך עד {datetime.strptime(args.end, '%Y-%m-%d').strftime('%d.%m.%Y')}; תקופת הבחינות עשויה להביא גל שימוש נוסף בסיכומים ובתרגול. נעדכן את הדוח עם סיום הסמסטר.</li>
</ol>
</section>
"""

    note = f"""
<div class="note">
<p><b>שיטה.</b> הנתונים הם אירועי שימוש בפלטפורמה (Mixpanel) בין {dmy(m['weeks'][0])}.{m['weeks'][0][:4]} ל-{last_data.strftime('%d.%m.%Y')}, ב-{m['n_weeks']} שבועות מלאים. משתמשי הדגמה וצוות AaronOwl הוסרו. מרצים זוהו לפי רשימת הסגל של המכללה; כל משתמש אחר נספר כסטודנט. סטודנט נספר כמשתמש בקורס רק אם פתח בו הרצאה או הפעיל כלי תוכן (תרגול, צ׳אט, מושגים, לשוניות); אירועי כניסה ואיפוס סיסמה מיוחסים לקורס ברירת המחדל ולכן אינם נספרים.
זמן שימוש מחושב לפי מפגשים (הפסקה של יותר מ-{SESSION_TIMEOUT_MIN} דקות פותחת מפגש חדש, וכל מפגש מקבל תוספת של {SESSION_TIMEOUT_MIN} דקות עבור הפעולה האחרונה). השעות בשעון ישראל.
"רשומים" הוא מספר המקומות בכל קורס לפי רשימת המכללה; אותו סטודנט עשוי להיות רשום לכמה קורסים. הופק ב-{date.today().strftime('%d.%m.%Y')}.</p>
</div>
"""

    head = f"""
<title>ספיר קיץ 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@700&display=swap">
{CSS}
<div class="wrap">
<header>
<div>
<div class="eyebrow">AaronOwl · המכללה האקדמית ספיר</div>
<h1>סמסטר קיץ 2026 בפלטפורמה</h1>
<div class="meta">נתונים עד {last_data.strftime('%d.%m.%Y')} · {m['n_courses']} קורסים · {m['n_weeks']} שבועות</div>
</div>
{f'<img src="{logo}" alt="AaronOwl">' if logo else ''}
</header>
"""
    return head + summary + weekly_html + courses_html + features_html + lecturers_html + patterns_html + inside_html + bench_html + recs_html + note + '</div>\n'


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', default=os.path.join(HERE, '..', '..', 'aaron-analytics', 'data'),
                    help='folder with weekly/, courses_<slug>.csv and teachers.csv')
    ap.add_argument('--config', default=os.path.join(HERE, 'config.yaml'), help='config with blacklist.user_ids')
    ap.add_argument('--institute', default='Sapir', help='value of the "English Name" column to keep')
    ap.add_argument('--courses', default='courses_C-2026.csv')
    ap.add_argument('--start', default='2026-07-25')
    ap.add_argument('--end', default='2026-10-09')
    ap.add_argument('--benchmark-courses', default='courses_B-2026.csv', help='previous semester course list ("" to skip)')
    ap.add_argument('--benchmark-start', default='2026-03-16')
    ap.add_argument('--benchmark-end', default='2026-07-12')
    ap.add_argument('--exclude-dates', default='2026-08-06',
                    help='comma-separated dates (in-class demo days) left out of the "once inside" section')
    ap.add_argument('--roster', default=os.path.join(HERE, 'data', 'sapir_C-2026_roster.csv'),
                    help='optional CSV: course_name, lecturer, program, day, from, to, weekly_hours ("" to skip)')
    ap.add_argument('--out', default=os.path.join(HERE, 'reports', 'sapir_C-2026_semester_report.html'))
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    cfg = yaml.safe_load(open(args.config)) if os.path.exists(args.config) else {}
    blacklist = set(cfg.get('blacklist', {}).get('user_ids', []))
    teachers = pd.read_csv(os.path.join(data_dir, 'teachers.csv'))
    tcol = '$distinct_id' if '$distinct_id' in teachers.columns else 'user_id'
    teacher_ids = set(teachers[tcol].dropna()) - blacklist

    df, cmap, reg, weeks = load_window(data_dir, args.courses, args.start, args.end, args.institute, blacklist, teacher_ids)
    excl = [d for d in args.exclude_dates.split(',') if d]
    m = compute(df, cmap, reg, weeks, excl)
    if args.roster and os.path.exists(args.roster):
        roster = pd.read_csv(args.roster)
        m['courses'] = m['courses'].merge(roster, how='left', left_on='name', right_on='course_name').drop(columns=['course_name'])
        missing = m['courses'][m['courses']['lecturer'].isna()]['name'].tolist()
        if missing:
            print('roster: no match for', missing)
    else:
        for col in ['lecturer', 'program', 'day', 'from', 'to', 'weekly_hours']:
            m['courses'][col] = np.nan
    print(f'{args.institute} {args.courses}: {m["n_weeks"]} weeks, {m["n_students"]} students, {m["n_lecturers"]} lecturers, {m["n_courses"]} courses')

    b = None
    if args.benchmark_courses:
        dfb, cmapb, regb, weeksb = load_window(data_dir, args.benchmark_courses, args.benchmark_start, args.benchmark_end,
                                               args.institute, blacklist, teacher_ids)
        b = compute(dfb, cmapb, regb, weeksb)
        print(f'benchmark {args.benchmark_courses}: {b["n_weeks"]} weeks, {b["n_students"]} students, {b["n_courses"]} courses')

    html_out = build_html(m, b, args, logo_data_uri(data_dir))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html_out)
    print(f'wrote {args.out} ({len(html_out) // 1024} KB)')


if __name__ == '__main__':
    main()
