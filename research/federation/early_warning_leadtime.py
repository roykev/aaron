#!/usr/bin/env python3
"""
Aaron Owl — Early-warning lead-time (flagship #2, actionable)
============================================================
"How early can we flag an at-risk student?" For each lead time k (weeks before the exam),
build CUMULATIVE activity from course start up to (exam − k weeks), fit an out-of-fold
classifier to predict the at-risk target, and report OOF AUC. Produces the AUC-vs-lead-time
curve + a chart.

Research demo: reads local grades to compute the target. The FEDERATED production version
moves the cumulative-feature build into the pipeline (ship `lead<k>w_` blocks) and the AUC
into analysis_script (grades never leave). This proves the signal is there and detectable early.

    python federation/early_warning_leadtime.py --course psy --grades <moed_ab.csv> --out <dir>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline
from modules.event_loader import EventLoader
from modules.identity_resolver import IdentityResolver
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.metrics import roc_auc_score

FEATS = ['n_active_events', 'n_active_days', 'n_active_weeks', 'n_eval', 'n_lectures', 'diversity']


def cumulative_features(events, cutoff):
    """Compact cumulative activity per student for all events strictly before `cutoff`."""
    d = events['datetime'].dt.tz_localize(None).dt.date
    e = events[d < cutoff].copy()
    e['date'] = d[d < cutoff]
    act = e[e['is_active_event']]
    idx = pd.Index(sorted(e['email'].dropna().unique()), name='email')
    f = pd.DataFrame(index=idx)
    f['n_active_events'] = act.groupby('email').size()
    f['n_active_days'] = act.groupby('email')['date'].nunique()
    f['n_active_weeks'] = act.assign(w=act['datetime'].dt.to_period('W')).groupby('email')['w'].nunique()
    f['n_eval'] = act[act['event'].astype(str).str.contains('eval', na=False)].groupby('email').size()
    f['n_lectures'] = e.groupby('email')['lecture'].nunique() if 'lecture' in e.columns else 0
    f['diversity'] = e.groupby('email')['event'].nunique()
    return f.fillna(0.0)


def oof_auc(X, y):
    n_pos, n = int(y.sum()), len(y)
    if min(n_pos, n - n_pos) < 3:
        return None
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))
    try:
        proba = cross_val_predict(clf, X, y, cv=LeaveOneOut(), method='predict_proba')[:, 1]
        return round(float(roc_auc_score(y, proba)), 4)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', required=True)
    ap.add_argument('--grades', required=True)
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--pass-mark', type=float, default=None,
                    help='at-risk = grade < pass-mark; if omitted, bottom-tertile of the grade')
    ap.add_argument('--leads', nargs='+', type=int, default=[10, 8, 6, 4, 2, 1, 0])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg_path = Path(a.config)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).resolve().parent.parent / cfg_path
    cfg = yaml.safe_load(open(cfg_path))
    cc = cfg['courses'][a.course]
    exam = pd.Timestamp(cc['moed_a_date']).date()

    ev = EventLoader(cfg).load(cc['course_id'])
    ev = IdentityResolver(cfg).resolve(ev)
    ev = pipeline._drop_excluded_accounts(ev, cfg)
    ev['email'] = ev['email'].astype(str).str.lower().str.strip()

    G = pd.read_csv(a.grades); G.columns = [c.strip().lower() for c in G.columns]
    G['email'] = G['email'].astype(str).str.lower().str.strip()
    gcol = 'moed_a' if 'moed_a' in G.columns else ('final' if 'final' in G.columns else G.columns[1])
    G[gcol] = pd.to_numeric(G[gcol], errors='coerce')
    G = G.dropna(subset=[gcol])
    if a.pass_mark is not None:
        G['at_risk'] = (G[gcol] < a.pass_mark).astype(int)
        target = f'grade < {a.pass_mark}'
    else:
        cut = G[gcol].quantile(1 / 3)
        G['at_risk'] = (G[gcol] <= cut).astype(int)
        target = f'bottom-tertile (≤ {cut:.0f})'
    tgt = G.set_index('email')['at_risk']

    curve = []
    for k in sorted(set(a.leads), reverse=True):
        cutoff = exam - pd.Timedelta(weeks=k)
        f = cumulative_features(ev, cutoff)
        m = f.index.intersection(tgt.index)
        X = f.loc[m, FEATS].values
        y = tgt.loc[m].values.astype(int)
        auc = oof_auc(X, y) if len(m) else None
        curve.append({'lead_weeks': k, 'cutoff': str(cutoff), 'n': int(len(m)),
                      'n_at_risk': int(y.sum()) if len(m) else 0, 'auc_oof': auc})
        print(f"  lead {k:2d}w before exam (cutoff {cutoff}): n={len(m):3d} at-risk={int(y.sum()) if len(m) else 0:2d}  AUC={auc}")

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {'course': cc['name'], 'target': target, 'exam_date': str(exam), 'curve': curve}
    (out / f'leadtime_{a.course}.json').write_text(json.dumps(res, indent=2, ensure_ascii=False))

    pts = [(c['lead_weeks'], c['auc_oof']) for c in curve if c['auc_oof'] is not None]
    labels = [p[0] for p in pts]; vals = [p[1] for p in pts]
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Early-warning lead-time — {cc['name']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>body{{font:14px/1.5 Segoe UI,Arial,sans-serif;max-width:820px;margin:26px auto;padding:0 16px}}
 .mut{{color:#8a929b;font-size:13px}} .card{{background:#fff;border:1px solid #eaecef;border-radius:10px;padding:16px}}</style></head><body>
<h1>How early can we flag at-risk students? — {cc['name']}</h1>
<p class="mut">Target: at-risk = {target}. Out-of-fold AUC of a classifier trained on cumulative activity up to each cutoff.
Higher = the signal is already detectable that many weeks before the exam. Grade-free features; target from grades.</p>
<div class="card"><canvas id="c" height="150"></canvas></div>
<script>new Chart(document.getElementById('c'),{{type:'line',
 data:{{labels:{json.dumps(labels)},datasets:[{{label:'OOF AUC',data:{json.dumps(vals)},borderColor:'#1565c0',backgroundColor:'#1565c0',tension:0.3,pointRadius:4}}]}},
 options:{{plugins:{{legend:{{display:false}}}},scales:{{
   y:{{min:0.4,max:1,title:{{display:true,text:'OOF AUC (0.5 = chance)'}}}},
   x:{{reverse:true,title:{{display:true,text:'weeks before exam (10 = early … 0 = exam)'}}}}}}}}}});</script>
</body></html>"""
    (out / f'leadtime_{a.course}.html').write_text(html, encoding='utf-8')
    print(f"\nwrote {out/f'leadtime_{a.course}.json'} + .html")


if __name__ == '__main__':
    main()
