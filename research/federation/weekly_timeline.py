#!/usr/bin/env python3
"""
Aaron Owl — Weekly engagement timeline by ALS tier
==================================================
Grade-free. Plots per-capita active-learning events per week for each pre-A ALS
tier (High / Medium / Low), with Moed A / Moed B marked. Shows the semester rhythm:
steady learners (flat, sustained) vs last-minute (spike before the exam), and the
post-exam collapse — per tier.

Usage:
    python federation/weekly_timeline.py --course psy --out <dir>
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # research/ on path
import pipeline
from modules.event_loader import EventLoader
from modules.identity_resolver import IdentityResolver

LEVEL_COLOR = {'High': '#2e7d32', 'Medium': '#e65100', 'Low': '#b71c1c'}


def build(config, key, out_dir):
    cc = config['courses'][key]
    fed_dir = Path(cc.get('federation_dir') or config['data']['federation_dir'])
    feats = pd.read_csv(fed_dir / f'student_features_{key}_federation.csv')
    ecol = 'email' if 'email' in feats.columns else feats.columns[0]
    feats[ecol] = feats[ecol].astype(str).str.lower().str.strip()
    tier_of = dict(zip(feats[ecol], feats['active_learning_level']))
    tier_n = feats['active_learning_level'].value_counts().to_dict()

    events = EventLoader(config).load(cc['course_id'])
    events = IdentityResolver(config).resolve(events)
    events = pipeline._drop_excluded_accounts(events, config)
    events['email'] = events['email'].astype(str).str.lower().str.strip()
    events['tier'] = events['email'].map(tier_of)
    ev = events[events['tier'].notna() & events['is_active_event']].copy()
    ev['week'] = ev['datetime'].dt.tz_localize(None).dt.to_period('W').dt.start_time.dt.date

    weeks = sorted(ev['week'].unique())
    order = ['Low', 'Medium', 'High']            # stack bottom→top
    n_total = len(feats)                         # course total N — the common denominator
    piv = ev.groupby(['week', 'tier']).size().unstack(fill_value=0).reindex(weeks, fill_value=0)
    datasets = []
    for t in order:
        # divide EVERY tier by the course total N (not tier size), so the 3 tier bands
        # DECOMPOSE total activity per enrolled student → stacked area (cumulative height = total).
        per_cap = (piv[t] / n_total) if t in piv.columns else pd.Series(0, index=weeks)
        datasets.append({'label': f'{t} (n={tier_n.get(t,0)})', 'data': [round(float(x), 2) for x in per_cap],
                         'borderColor': LEVEL_COLOR[t], 'backgroundColor': LEVEL_COLOR[t] + '99',
                         'fill': True, 'tension': 0.3, 'pointRadius': 1, 'borderWidth': 1})
    labels = [str(w) for w in weeks]

    def moed_week(dstr):
        if not dstr:
            return None
        md = pd.Timestamp(dstr).date()
        cand = [w for w in weeks if w <= md]
        return str(max(cand)) if cand else (labels[0] if labels else None)

    annos = {}
    for name, key_d, col in [('Moed A', 'moed_a_date', '#1565c0'), ('Moed B', 'moed_b_date', '#6a1b9a')]:
        lab = moed_week(cc.get(key_d))
        if lab:
            annos[name] = {'type': 'line', 'xMin': lab, 'xMax': lab,
                           'borderColor': col, 'borderWidth': 2, 'borderDash': [6, 4],
                           'label': {'content': name, 'display': True, 'position': 'start',
                                     'backgroundColor': col, 'font': {'size': 10}}}

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Weekly timeline — {cc['name']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>body{{font:14px/1.5 Segoe UI,Arial,sans-serif;max-width:960px;margin:28px auto;padding:0 16px;color:#1f2328}}
 h1{{font-size:20px}} .mut{{color:#8a929b;font-size:13px}} .card{{background:#fff;border:1px solid #eaecef;border-radius:10px;padding:16px}}</style>
</head><body>
<h1>Weekly engagement by ALS tier — {cc['name']}</h1>
<p class="mut">Per-capita active-learning events per student per week, split by pre-Moed-A tier.
Steady learners hold a sustained line; last-minute learners spike near the exam. Grade-free · {len(feats)} students.</p>
<div class="card"><canvas id="c" height="150"></canvas></div>
<script>
new Chart(document.getElementById('c'), {{
  type:'line',
  data:{{labels:{json.dumps(labels)}, datasets:{json.dumps(datasets)}}},
  options:{{interaction:{{mode:'index',intersect:false}},
    plugins:{{legend:{{position:'bottom'}}, annotation:{{annotations:{json.dumps(annos)}}}}},
    scales:{{y:{{beginAtZero:true, stacked:true, title:{{display:true,text:'active events / enrolled student (÷ course N, stacked)'}}}},
             x:{{ticks:{{maxRotation:90,minRotation:45,autoSkip:true,maxTicksLimit:20}}}}}}}}
}});
</script></body></html>"""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    p = out / f'weekly_timeline_{key}.html'
    p.write_text(html, encoding='utf-8')
    print(f"wrote {p}  ({len(weeks)} weeks, tiers {tier_n})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', required=True)
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg_path = Path(a.config)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parent.parent / cfg_path
    config = yaml.safe_load(open(cfg_path))
    build(config, a.course, a.out)


if __name__ == '__main__':
    main()
