#!/usr/bin/env python3
"""
Aaron Owl — Program Dashboard
=============================
A portfolio view ABOVE the pairwise meta: every configured course with its status,
exam dates, activity, what's still missing, links to per-course reports, and the
headline significant findings pooled so far.

Usage:
    python federation/program_dashboard.py --config config.yaml \
        --results psy:/path/psy/output/results_v2 math:/path/real_pool/math \
        --meta /path/real_pool/meta \
        --out  /path/program_dashboard.html
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent


def _load_cfg(p):
    p = Path(p)
    if not p.is_absolute():
        p = HERE.parent / p
    return yaml.safe_load(open(p))


def _fed_dir(cfg, key):
    cc = cfg['courses'][key]
    return Path(cc.get('federation_dir') or cfg['data']['federation_dir'])


def _activity(fcsv):
    """High-level activity stats from a federation feature CSV."""
    d = pd.read_csv(fcsv)
    out = {'n': len(d)}
    if 'active_learning_level' in d.columns:
        vc = d['active_learning_level'].value_counts()
        out['tiers'] = {t: int(vc.get(t, 0)) for t in ('High', 'Medium', 'Low')}
    if 'active_weeks' in d.columns:
        out['pct_active'] = round(100 * (d['active_weeks'] > 0).mean(), 0)
    if 'postA_total_active_events' in d.columns:
        act = (d['postA_total_active_events'].fillna(0) > 0)
        out['has_postA'] = True
        out['pct_postA_active'] = round(100 * act.mean(), 0)
        # grade-free paired pre→post-A activity change (Cohen's dz + SE), poolable
        pre = d['total_active_events'].fillna(0).astype(float)
        post = d['postA_total_active_events'].fillna(0).astype(float)
        diff = post - pre; sd = diff.std(ddof=1) if len(d) > 1 else 0
        if len(d) > 2 and sd > 0:
            dz = float(diff.mean() / sd)
            out['prepost_dz'] = round(dz, 3)
            out['prepost_se'] = round(float((1 / len(d) + dz ** 2 / (2 * len(d))) ** 0.5), 3)
    else:
        out['has_postA'] = False
    return out


def _pool_iv(pairs):
    """Inverse-variance pooled (estimate, lo, hi, k) from [(est, se), ...]."""
    if not pairs:
        return None
    est = np.array([e for e, _ in pairs]); se = np.array([s for _, s in pairs])
    w = 1 / se ** 2; m = float((w * est).sum() / w.sum()); pse = float((1 / w.sum()) ** 0.5)
    return {'est': m, 'lo': m - 1.96 * pse, 'hi': m + 1.96 * pse, 'k': len(pairs)}


def _forest(est, lo, hi, lim, null=0.0, center=0.0):
    """Inline SVG forest row: point + CI bar on [center-lim, center+lim]; green if CI excludes null."""
    W, H = 200, 20
    def x(v):
        v = max(center - lim, min(center + lim, v))
        return 8 + (v - center + lim) / (2 * lim) * (W - 16)
    zero = x(null); sig = (lo > null or hi < null)
    col = '#1a7f37' if sig else '#9a6700'
    return (f'<svg width="{W}" height="{H}">'
            f'<line x1="{zero}" y1="2" x2="{zero}" y2="{H-2}" stroke="#ccc"/>'
            f'<line x1="{x(lo):.1f}" y1="{H/2}" x2="{x(hi):.1f}" y2="{H/2}" stroke="{col}" stroke-width="2"/>'
            f'<circle cx="{x(est):.1f}" cy="{H/2}" r="4" fill="{col}"/></svg>')


def _missing(cc, act, res):
    """What each course still needs."""
    m = []
    if act is None:
        return ['run pipeline — no activity features yet']
    if not cc.get('moed_a_date'):
        m.append('exam dates (Moed A)')
    elif not cc.get('moed_b_date'):
        m.append('Moed B date (postA open-ended)')
    if res is None:
        m.append('teacher grades (results.json)')
    elif res.get('grade_mode') == 'final':
        m.append('A/B split (only final grade)')
    return m or ['—']


def _status_badge(res, act):
    if act is None:
        return ('pending', '#9a6700', '#fff8e1')
    if res is None:
        return ('activity only', '#0969da', '#ddf4ff')
    return ('grades in', '#1a7f37', '#e6ffec')


def build(cfg, results_map, meta, out_path, timelines=None):
    courses = cfg['courses']
    rows, totals = [], {'students': 0, 'with_data': 0, 'with_grades': 0, 'with_windows': 0}
    for key, cc in courses.items():
        fdir = _fed_dir(cfg, key)
        fcsv = fdir / f'student_features_{key}_federation.csv'
        act = _activity(fcsv) if fcsv.exists() else None
        rdir = results_map.get(key)
        res = json.loads((Path(rdir) / 'results.json').read_text()) if rdir and (Path(rdir) / 'results.json').exists() else None
        report = fdir / f'usage_report_{key}.html'
        if act:
            totals['students'] += act['n']; totals['with_data'] += 1
            if act.get('has_postA'): totals['with_windows'] += 1
        if res: totals['with_grades'] += 1
        rows.append((key, cc, act, res, report if report.exists() else None))

    # grade-free pooled pre→post-A engagement change (all windowed courses)
    prepost = _pool_iv([(a['prepost_dz'], a['prepost_se']) for _, _, a, _, _ in rows
                        if a and a.get('prepost_dz') is not None])

    # ── program KPI cards ─────────────────────────────────────────────────────
    def card(v, t, c='#0969da'):
        return f'<div class="kpi"><div class="v" style="color:{c}">{v}</div><div class="t">{t}</div></div>'
    kpis = (card(len(courses), 'Configured courses') +
            card(totals['with_data'], 'With activity data', '#1a7f37') +
            card(totals['students'], 'Total students', '#4527a0') +
            card(totals['with_grades'], 'With grades in', '#bf8700') +
            card(totals['with_windows'], 'Exam-windowed'))
    combined = Path(timelines) / 'combined_timeline.html' if timelines else None
    combined_link = (f'<p><a href="{combined.as_uri()}">▸ Combined timeline — all courses aligned to Moed A ↗</a></p>'
                     if combined and combined.exists() else '')

    # ── per-course status table ───────────────────────────────────────────────
    trs = ''
    for key, cc, act, res, report in rows:
        label, col, bg = _status_badge(res, act)
        badge = f'<span class="badge" style="color:{col};background:{bg}">{label}</span>'
        dates = f"{cc.get('moed_a_date','—')} / {cc.get('moed_b_date','—')}"
        if act:
            t = act.get('tiers', {})
            tiers = f"{t.get('High',0)}/{t.get('Medium',0)}/{t.get('Low',0)}"
            n = act['n']
            postA = f"{act.get('pct_postA_active','—')}%" if act.get('has_postA') else '—'
            if act.get('prepost_dz') is not None:
                postA += f'<br><span class="mut">dz {act["prepost_dz"]:+}</span>'
        else:
            tiers = n = postA = '—'
        q1 = ''
        if res and isinstance(res.get('Q1'), dict) and res['Q1'].get('r_ALS_score'):
            q1 = f"r(ALS,grade)={res['Q1']['r_ALS_score'].get('r')}"
        miss = ', '.join(_missing(cc, act, res))
        links = []
        if report:
            links.append(f'<a href="{report.as_uri()}">report ↗</a>')
        if timelines:
            tl = Path(timelines) / f'weekly_timeline_{key}.html'
            if tl.exists():
                links.append(f'<a href="{tl.as_uri()}">timeline ↗</a>')
        link = ' · '.join(links) or '—'
        trs += (f'<tr><td><b>{cc.get("name","")}</b><br><span class="mut">{key}</span></td>'
                f'<td class="c">{badge}</td><td class="c">{n}</td><td class="c">{tiers}</td>'
                f'<td class="c">{postA}</td><td class="c" dir="ltr">{dates}</td>'
                f'<td>{q1 or "<span class=mut>—</span>"}</td>'
                f'<td class="miss">{miss}</td><td class="c">{link}</td></tr>')

    # ── headline findings as forest bars (like meta_report) ───────────────────
    frows = ''
    def _add(label, est, lo, hi, null, lim, center, k, gf=False):
        nonlocal frows
        sig = lo > null or hi < null
        icon = '✅' if sig else '🟡'
        tag = ' <span class="mut">grade-free</span>' if gf else ''
        frows += (f'<tr><td>{icon} <b>{label}</b>{tag}</td>'
                  f'<td class="c">{est:+.2f}</td><td class="c mut">[{lo:+.2f}, {hi:+.2f}]</td>'
                  f'<td>{_forest(est, lo, hi, lim, null, center)}</td>'
                  f'<td class="c">{k}</td><td class="c">{"significant" if sig else "trend"}</td></tr>')
    FIND = [('Q1_r_ALS_score', 'ALS → grade (r)', 0.0, 1.0, 0.0),
            ('Q1_d_high_low_score', 'ALS High−Low grade gap (d)', 0.0, 2.0, 0.0),
            ('value_added_beta', 'Value-added: ALS above baseline (β)', 0.0, 1.0, 0.0),
            ('R1_ew_AUC', 'Fail-A early warning (AUC)', 0.5, 0.5, 0.5),
            ('R2_ew_AUC', 'No-show early warning (AUC)', 0.5, 0.5, 0.5),
            ('adoption_d', 'Adoption: app-users − non-users (d)', 0.0, 2.0, 0.0)]
    for key, label, null, lim, center in (FIND if meta else []):
        p = meta.get(key)
        if not p: continue
        est = p.get('estimate_r', p.get('estimate')); ci = p.get('ci_r', p.get('ci'))
        if est is not None and ci:
            _add(label, est, ci[0], ci[1], null, lim, center, p.get('k'))
    if prepost:
        _add('Engagement change after Moed A (dz)', prepost['est'], prepost['lo'], prepost['hi'],
             0.0, 2.0, 0.0, prepost['k'], gf=True)
    findings = frows or '<tr><td colspan="6" class="mut">No pooled findings yet — add ≥2 courses with results.</td></tr>'

    # ── expandable: every question, plain-language ask, pooled answer, colored ──
    # (qid, text, meta_key, expected_direction, null)
    QA = [('Q1', 'Does higher active-learning (ALS) go with a higher exam grade?', 'Q1_r_ALS_score', '+', 0.0),
          ('Q2', 'Does ALS predict who improves most from Moed A to B?', 'Q2_r_ALS_imp', '+', 0.0),
          ('Q3', 'Does increasing activity raise the grade (within-person)?', 'Q3_beta_dRate', '+', 0.0),
          ('R1', 'Can we predict who fails Moed A from pre-exam activity?', 'R1_ew_AUC', '+', 0.5),
          ('R2', 'Can we predict exam no-shows from pre-exam activity?', 'R2_ew_AUC', '+', 0.5),
          ('predictive', 'Does a free model beat ALS alone at predicting the grade?', 'pred_r2_full', '+', 0.0),
          ('subgroups', 'Does ALS→grade differ by post-A activity segment?', None, '+', 0.0),
          ('pre_post_a', 'Does engagement change after Moed A? (grade-free)', 'prepostA_dz', '-', 0.0),
          ('adoption', 'Do app-users outscore students who never used the app?', 'adoption_d', '+', 0.0),
          ('value_added', 'Does engagement predict the outcome ABOVE baseline (early activity + performance)?', 'value_added_beta', '+', 0.0)]
    # status → (background shade). Green=significant right-way, yellow=trend, red=significant
    # wrong-way, pale=answered-but-null, gray=not analyzed yet. Shade darkens with significance.
    COLORS = {'sig_strong': '#8fe1a6', 'sig': '#c9f2d4', 'trend': '#fff3c4',
              'opposite': '#ffc9c4', 'null': '#ffe9dd', 'none': '#eef0f2'}

    def _status(est, lo, hi, null, direction):
        if est is None or lo is None:
            return 'none', 'not analyzed yet'
        sig = lo > null or hi < null
        good = est > null if direction == '+' else est < null
        if sig and good:
            margin = min(abs(lo - null), abs(hi - null))
            return ('sig_strong' if margin > 0.1 else 'sig'), 'significant ✅'
        if good:
            return 'trend', 'trend 🟡'
        if sig:
            return 'opposite', 'significant, opposite ❌'
        return 'null', 'no effect'

    cov = meta.get('coverage_k', {}) if meta else {}
    qarows = ''
    for qid, qtext, mkey, direction, null in QA:
        k = cov.get(qid, 0)
        est = lo = hi = None
        if qid == 'pre_post_a' and prepost:
            est, lo, hi = prepost['est'], prepost['lo'], prepost['hi']; k = prepost['k']
        else:
            p = meta.get(mkey) if (meta and mkey) else None
            if p:
                est = p.get('estimate_r', p.get('estimate')); ci = p.get('ci_r', p.get('ci'))
                if ci: lo, hi = ci
        stat, label = _status(est, lo, hi, null, direction)
        ans = (f"{est:+.2f} [{lo:+.2f}, {hi:+.2f}], k={k}" if est is not None
               else f"not answered yet (k={k})")
        qarows += (f'<tr style="background:{COLORS[stat]}"><td class="c"><b>{qid}</b></td><td>{qtext}</td>'
                   f'<td class="c">{k}</td><td>{ans}</td><td class="c" style="font-size:.82em">{label}</td></tr>')

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Aaron Owl — Program Dashboard</title><style>
 body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1080px;margin:28px auto;padding:0 16px;color:#1f2328}}
 h1{{font-size:23px;margin-bottom:2px}} h2{{font-size:16px;margin:26px 0 8px;border-bottom:1px solid #eaecef;padding-bottom:4px}}
 .mut{{color:#8a929b;font-size:12px}} .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
 .kpi{{background:#fff;border:1px solid #eaecef;border-radius:10px;padding:14px 20px;flex:1;min-width:120px}}
 .kpi .v{{font-size:1.8em;font-weight:700}} .kpi .t{{font-size:.78em;color:#656d76;margin-top:2px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{padding:8px 9px;border-bottom:1px solid #eaecef;text-align:left;vertical-align:top}}
 th{{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:.03em}} td.c{{text-align:center}}
 .badge{{padding:2px 9px;border-radius:11px;font-size:.8em;font-weight:600}}
 .miss{{color:#9a6700;font-size:12px}} a{{color:#0969da}}
 .findings{{background:#f6f8fa;border:1px solid #eaecef;border-radius:10px;padding:12px 20px}}
 .findings li{{margin:5px 0}}
 table.find td{{vertical-align:middle}} table.find svg{{vertical-align:middle}}
 details{{margin:8px 0}} details summary{{cursor:pointer;font-weight:600;color:#0969da}}
 .chip{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.8em;margin-right:4px}}
</style></head><body>
<h1>Aaron Owl — Program Dashboard</h1>
<p class="mut">Learning-analytics portfolio across all configured courses · privacy-federated (grades stay with each teacher)</p>
<div class="kpis">{kpis}</div>
{combined_link}

<h2>Headline findings (pooled)</h2>
<table class="find"><tr><th>finding</th><th class="c">pooled</th><th class="c">95% CI</th>
 <th>forest (null-line marked)</th><th class="c">k</th><th class="c">verdict</th></tr>{findings}</table>
<details><summary>▸ All questions &amp; answers so far</summary>
<table style="margin-top:8px"><tr><th class="c">Q</th><th>question</th><th class="c">courses</th><th>pooled answer</th><th class="c">status</th></tr>{qarows}</table>
<p class="mut" style="margin-top:6px">
 <span class="chip" style="background:#8fe1a6">significant</span>
 <span class="chip" style="background:#fff3c4">trend</span>
 <span class="chip" style="background:#ffc9c4">opposite</span>
 <span class="chip" style="background:#ffe9dd">no effect</span>
 <span class="chip" style="background:#eef0f2">not analyzed yet</span>
 &nbsp;· k = courses that can answer each question (self-describing). Absence of evidence ≠ evidence of absence.</p>
</details>

<h2>Courses</h2>
<table><tr>
 <th>Course</th><th class="c">Status</th><th class="c">Students</th><th class="c">ALS H/M/L</th>
 <th class="c">%postA-active</th><th class="c">Moed A / B</th><th>Signal</th><th>Missing</th><th class="c">Report</th>
</tr>{trs}</table>
<p class="mut">Status: <b>grades in</b> = teacher returned results · <b>activity only</b> = features built, awaiting grades ·
<b>pending</b> = configured, no activity features yet. %postA-active = share active in the Moed-A→B window.</p>
</body></html>"""
    Path(out_path).write_text(html, encoding='utf-8')
    print(f"wrote {out_path}")
    print(f"  courses={len(courses)} with_data={totals['with_data']} students={totals['students']} "
          f"with_grades={totals['with_grades']} windowed={totals['with_windows']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--results', nargs='*', default=[], help='key:dir pairs holding results.json')
    ap.add_argument('--meta', default=None, help='dir holding meta.json')
    ap.add_argument('--timelines', default=None, help='dir holding weekly_timeline_*.html + combined_timeline.html')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg = _load_cfg(a.config)
    results_map = dict(kv.split(':', 1) for kv in a.results)
    meta = None
    if a.meta and (Path(a.meta) / 'meta.json').exists():
        meta = json.loads((Path(a.meta) / 'meta.json').read_text())
    build(cfg, results_map, meta, a.out, timelines=a.timelines)


if __name__ == '__main__':
    main()
