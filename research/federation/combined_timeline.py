#!/usr/bin/env python3
"""
Aaron Owl — Combined weekly timeline, aligned to Moed A
=======================================================
Overlays multiple courses on ONE chart with the x-axis = weeks relative to Moed A
(0 = the exam week; negative = before, positive = after). This aligns different
course calendars so the shared rhythm — pre-exam ramp, spike, post-exam collapse —
is directly comparable. Grade-free.

Metric = % of a course's students active (≥1 active event) that week — bounded [0,100]
per course, so cross-course pooling is NOT biased by course size or event volume.
Two charts: (1) one line per course, (2) the three ALS tiers pooled across courses.
(A %-of-T0→Moed-A x-axis variant is a possible follow-up; this build uses weeks-to-Moed-A.)

Usage:
    python federation/combined_timeline.py --courses psy bio az_ceramics --out <dir>
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline
from modules.event_loader import EventLoader
from modules.identity_resolver import IdentityResolver

TIER_COLOR = {'High': '#2e7d32', 'Medium': '#e65100', 'Low': '#b71c1c'}
COURSE_COLORS = ['#1565c0', '#6a1b9a', '#00838f', '#c62828', '#2e7d32', '#ef6c00']


def course_series(config, key):
    """Return per-course per-capita active events/student/week keyed by week-relative-to-Moed-A,
    overall and per tier. None if no Moed A date."""
    cc = config['courses'][key]
    if not cc.get('moed_a_date'):
        return None
    fed = Path(cc.get('federation_dir') or config['data']['federation_dir'])
    feats = pd.read_csv(fed / f'student_features_{key}_federation.csv')
    feats['email'] = feats['email'].astype(str).str.lower().str.strip()
    tier = dict(zip(feats['email'], feats['active_learning_level']))
    tn = feats['active_learning_level'].value_counts().to_dict()
    n_tot = len(feats)

    ev = EventLoader(config).load(cc['course_id'])
    ev = IdentityResolver(config).resolve(ev)
    ev = pipeline._drop_excluded_accounts(ev, config)
    ev['email'] = ev['email'].astype(str).str.lower().str.strip()
    ev['tier'] = ev['email'].map(tier)
    ev = ev[ev['tier'].notna() & ev['is_active_event']].copy()

    # Bin by DAYS relative to the exam date, anchored on Moed A itself (NOT ISO weeks) — so
    # alignment is exact regardless of which weekday the exam falls on. Bin 0 = the 7 days
    # ending on Moed A (the final cram week); negative = earlier, positive = after the exam.
    mA = pd.Timestamp(cc['moed_a_date']).date()
    days = (ev['datetime'].dt.tz_localize(None).dt.date - mA).map(lambda x: x.days)
    ev['rel'] = ((days + 6) // 7).astype(int)
    out = {'name': cc['name'], 'n': n_tot, 'overall': {}, 'tiers': {t: {} for t in TIER_COLOR}}
    # metric = % of the course's students active (≥1 active event) that week — ALWAYS
    # divided by the course's total N (n_tot), for the overall line AND each tier. So it's
    # bounded [0,100] per course (no size/volume bias) and the 3 tiers DECOMPOSE the overall
    # (they sum to it): each tier line = % of the whole class that is active AND in that tier.
    for rel, g in ev.groupby('rel'):
        out['overall'][int(rel)] = round(g['email'].nunique() / n_tot * 100, 1)
        for t in TIER_COLOR:
            gt = g[g['tier'] == t]
            out['tiers'][t][int(rel)] = round(gt['email'].nunique() / n_tot * 100, 1)
    return out


def build(config, keys, out_dir):
    data = {k: course_series(config, k) for k in keys}
    data = {k: v for k, v in data.items() if v}
    rels = sorted({r for v in data.values() for r in v['overall']})
    labels = [f'{r:+d}' if r else '0 (Moed A)' for r in rels]
    n_courses = len(data)

    # chart 1 — stacked by course: each course contributes overall% ÷ #courses, so the
    # course bands stack to the SAME cohort-average % active as the tier chart (decomposed
    # by course instead of tier). No-data weeks count as 0 for that course.
    ds_course = []
    for i, (k, v) in enumerate(data.items()):
        col = COURSE_COLORS[i % len(COURSE_COLORS)]
        ds_course.append({'label': f"{v['name']} (n={v['n']})",
                          'data': [round(v['overall'].get(r, 0.0) / n_courses, 2) for r in rels],
                          'borderColor': col, 'backgroundColor': col + '99',
                          'fill': True, 'tension': 0.3, 'borderWidth': 1, 'pointRadius': 1})
    # chart 2 — tiers pooled across courses. Divide by the FIXED number of courses (not just
    # those with data at that week), so the stacked height is a consistent cohort average — a
    # course with no data that far from its exam counts as 0% active. Tiers still decompose the
    # pooled overall (÷ course N) → stacked area whose cumulative height = avg % active.
    ds_tier = []
    for t in ['Low', 'Medium', 'High']:          # stack bottom→top
        vals = []
        for r in rels:
            s = sum(v['tiers'][t].get(r, 0.0) for v in data.values())
            vals.append(round(s / n_courses, 2))
        ds_tier.append({'label': t, 'data': vals, 'spanGaps': True,
                        'borderColor': TIER_COLOR[t], 'backgroundColor': TIER_COLOR[t] + '99',
                        'fill': True, 'tension': 0.3, 'borderWidth': 1, 'pointRadius': 1})

    zero_idx = rels.index(0) if 0 in rels else None
    anno = ({'MoedA': {'type': 'line', 'xMin': labels[zero_idx], 'xMax': labels[zero_idx],
                       'borderColor': '#111', 'borderWidth': 2, 'borderDash': [6, 4],
                       'label': {'content': 'Moed A', 'display': True, 'position': 'start', 'font': {'size': 10}}}}
            if zero_idx is not None else {})

    def chart(cid, title, ds, sub, stacked=False):
        ys = 'stacked:true,' if stacked else ''
        return f"""<div class="card"><h3>{title}</h3><p class="mut">{sub}</p><canvas id="{cid}" height="150"></canvas></div>
<script>new Chart(document.getElementById('{cid}'),{{type:'line',
 data:{{labels:{json.dumps(labels)},datasets:{json.dumps(ds)}}},
 options:{{interaction:{{mode:'index',intersect:false}},
  plugins:{{legend:{{position:'bottom'}},annotation:{{annotations:{json.dumps(anno)}}}}},
  scales:{{y:{{beginAtZero:true,{ys}max:100,title:{{display:true,text:'% of students active'}}}},
    x:{{title:{{display:true,text:'weeks relative to Moed A'}}}}}}}}}});</script>"""

    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Combined timeline — aligned to Moed A</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>body{{font:14px/1.5 Segoe UI,Arial,sans-serif;max-width:980px;margin:26px auto;padding:0 16px;color:#1f2328}}
 h1{{font-size:20px}} .mut{{color:#8a929b;font-size:12px}} .card{{background:#fff;border:1px solid #eaecef;border-radius:10px;padding:16px;margin:14px 0}}</style>
</head><body>
<h1>Engagement aligned to Moed A — {len(data)} courses</h1>
<p class="mut">x-axis = weeks relative to Moed A (0 = exam week). y = <b>% of students active</b> that week
(≥1 active-learning event) — bounded per course, so pooling isn't biased by course size or event volume.
Grade-free.</p>
{chart('c1', 'By course (stacked, cohort average)', ds_course, f'Each course band = that course % active / {len(data)} courses; bands STACK to the cohort-average % active (same total as the tier chart, split by course).', stacked=True)}
{chart('c2', 'By ALS tier (stacked, averaged over all courses)', ds_tier, f'Each tier = % of a class active in that tier (÷ course N), averaged over all {len(data)} courses (no-data weeks count as 0); bands STACK to the cohort-average % active.', stacked=True)}
</body></html>"""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    p = out / 'combined_timeline.html'
    p.write_text(html, encoding='utf-8')
    print(f"wrote {p}  · courses={list(data)} · rel-weeks {rels[0]}..{rels[-1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--courses', nargs='+', required=True)
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg_path = Path(a.config)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parent.parent / cfg_path
    build(yaml.safe_load(open(cfg_path)), a.courses, a.out)


if __name__ == '__main__':
    main()
