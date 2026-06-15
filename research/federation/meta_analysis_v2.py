#!/usr/bin/env python3
"""
Aaron Owl — Meta-analysis v2
============================
Pools per-course results.json (from analysis_script_v2) across courses using
inverse-variance RANDOM-EFFECTS meta-analysis (DerSimonian-Laird) with Cochran's
Q / I^2 heterogeneity. Designed to scale: weak per-course signals (e.g. n=9
retakers) aggregate into strong pooled inference as courses accumulate.

Usage:
    python meta_analysis_v2.py --results results/psy results/simA results/simB --out results/meta
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from scipy import stats as _st


def dl_pool(effects, ses):
    """DerSimonian-Laird random-effects pool. Returns dict with estimate, CI, Q, I2."""
    eff = np.asarray(effects, float)
    se = np.asarray(ses, float)
    m = np.isfinite(eff) & np.isfinite(se) & (se > 0)
    eff, se = eff[m], se[m]
    k = len(eff)
    if k == 0:
        return None
    if k == 1:
        return {'estimate': round(float(eff[0]), 4), 'se': round(float(se[0]), 4),
                'ci': [round(float(eff[0] - 1.96 * se[0]), 4), round(float(eff[0] + 1.96 * se[0]), 4)],
                'k': 1, 'Q': None, 'I2': None, 'tau2': 0.0}
    w = 1.0 / se ** 2
    fixed = np.sum(w * eff) / np.sum(w)
    Q = float(np.sum(w * (eff - fixed) ** 2))
    df = k - 1
    C = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (Q - df) / C) if C > 0 else 0.0
    wr = 1.0 / (se ** 2 + tau2)
    est = np.sum(wr * eff) / np.sum(wr)
    se_est = math.sqrt(1.0 / np.sum(wr))
    I2 = max(0.0, (Q - df) / Q) * 100 if Q > 0 else 0.0
    p = float(1 - _st.chi2.cdf(Q, df))
    return {'estimate': round(float(est), 4), 'se': round(se_est, 4),
            'ci': [round(float(est - 1.96 * se_est), 4), round(float(est + 1.96 * se_est), 4)],
            'k': int(k), 'Q': round(Q, 3), 'df': df, 'p_het': round(p, 4),
            'I2': round(I2, 1), 'tau2': round(tau2, 4)}


def fisher_pool(rs, ns):
    """Pool correlations via Fisher-z (matches existing meta_analysis.py convention)."""
    rs, ns = np.asarray(rs, float), np.asarray(ns, float)
    m = np.isfinite(rs) & (ns > 3)
    rs, ns = rs[m], ns[m]
    if len(rs) == 0:
        return None
    z = np.arctanh(np.clip(rs, -0.999, 0.999))
    se = 1.0 / np.sqrt(ns - 3)
    pooled = dl_pool(z, se)
    if pooled is None:
        return None
    pooled['estimate_r'] = round(float(np.tanh(pooled['estimate'])), 4)
    pooled['ci_r'] = [round(float(np.tanh(c)), 4) for c in pooled['ci']]
    return pooled


def collect(results, *keys):
    """Pull a nested value from each course's json; returns list aligned to courses."""
    out = []
    for r in results:
        v = r
        for k in keys:
            v = (v or {}).get(k) if isinstance(v, dict) else None
        out.append(v)
    return out


def _forest(est, lo, hi, lim, null=0.0, center=0.0):
    """Inline SVG forest row: point estimate + CI bar on a [center-lim, center+lim] scale."""
    W, H = 240, 22
    def x(v):
        v = max(center - lim, min(center + lim, v))
        return 10 + (v - center + lim) / (2 * lim) * (W - 20)
    zero = x(null)
    sig = (lo > null or hi < null)
    col = '#1a7f37' if sig else '#9a6700'
    return (f'<svg width="{W}" height="{H}">'
            f'<line x1="{zero}" y1="2" x2="{zero}" y2="{H-2}" stroke="#ccc"/>'
            f'<line x1="{x(lo):.1f}" y1="{H/2}" x2="{x(hi):.1f}" y2="{H/2}" stroke="{col}" stroke-width="2"/>'
            f'<circle cx="{x(est):.1f}" cy="{H/2}" r="4" fill="{col}"/></svg>')


def _g(d, *ks, default='—'):
    """Safe nested getter."""
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return default if d is None else d


def write_html(meta, R, out):
    def rows(items):
        h = ''
        for label, key, lim, null in items:
            p = meta.get(key)
            if not p:
                h += f'<tr><td>{label}</td><td colspan="6" class="na">not estimable yet</td></tr>'; continue
            est = p.get('estimate_r', p['estimate']); ci = p.get('ci_r', p['ci'])
            sig = '✔' if (ci[0] > null or ci[1] < null) else '·'
            i2 = '—' if p.get('I2') is None else f"{p['I2']}%"
            ph = '—' if p.get('p_het') is None else p.get('p_het')
            cls = 'sig' if sig == '✔' else ''
            h += (f'<tr class="{cls}"><td>{label}</td>'
                  f'<td class="num">{est:+.3f}</td><td class="num">[{ci[0]:+.3f}, {ci[1]:+.3f}]</td>'
                  f'<td class="ctr">{sig}</td><td>{_forest(est, ci[0], ci[1], lim, null, null)}</td>'
                  f'<td class="ctr">{p["k"]}</td><td class="ctr">{i2}</td><td class="ctr">{ph}</td></tr>')
        return h

    def verdict(key, yes, no, null=0.0, direction='+'):
        """Three-state plain-language one-liner from a pooled result:
        ✅ significant · 🟡 right-direction trend (not yet significant) · ◻️ null / not estimable."""
        p = meta.get(key)
        if not p:
            return '<span class="vbad">◻️ not estimable yet — too few courses / events</span>'
        est = p.get('estimate_r', p['estimate']); ci = p.get('ci_r', p['ci'])
        sig = ci[0] > null or ci[1] < null
        good = (est > null) if direction == '+' else (est < null)
        stat = f'(pooled {est:+.2f}, 95% CI [{ci[0]:+.2f}, {ci[1]:+.2f}], k={p["k"]})'
        if sig and good:
            return f'<span class="vgood">✅ {yes}</span> {stat}'
        if good:
            return (f'<span class="vtrend">🟡 trend: {yes[0].lower()}{yes[1:]} — '
                    f'directional, not yet significant</span> {stat}')
        return f'<span class="vbad">◻️ {no}</span> {stat}'

    Q1 = [('r (ALS → score)', 'Q1_r_ALS_score', 1.0, 0.0),
          ('d (High − Low) score', 'Q1_d_high_low_score', 2.0, 0.0),
          ('logOR high-score', 'Q1_logOR_high', 3.0, 0.0)]
    Q2 = [('r (ALS → improvement)', 'Q2_r_ALS_imp', 1.0, 0.0),
          ('d (High − Low) improvement', 'Q2_d_high_low_imp', 2.0, 0.0),
          ('paired improvement (SD)', 'Q2_paired_improvement_z', 3.0, 0.0)]
    Q3 = [('β (ΔRate_z → grade | moed_a)', 'Q3_beta_dRate', 1.0, 0.0)]
    PRED = [('CV R² — full model', 'pred_r2_full', 1.0, 0.0),
            ('CV R² — ALS only', 'pred_r2_als', 1.0, 0.0)]
    RISK = [('R1 fail-A — model AUC', 'R1_fail_AUC', 0.5, 0.5),
            ('R1 fail-A — logOR(ALS H/L)', 'R1_fail_logOR_ALS', 3.0, 0.0),
            ('R2 no-show — model AUC', 'R2_noshow_AUC', 0.5, 0.5)]
    head = ('<th>effect</th><th>pooled</th><th>95% CI</th><th>sig</th>'
            '<th>forest (RE)</th><th>k</th><th>I²</th><th>p_het</th>')

    pf, pa = meta.get('pred_r2_full'), meta.get('pred_r2_als')
    audit = 'not estimable yet'
    if pf and pa:
        d = pf['estimate'] - pa['estimate']
        v = 'ALS is a good parsimonious summary — a free model does not beat it' if d <= 0.02 \
            else 'the full model adds predictive value beyond ALS'
        audit = (f'<b>Δ(full − ALS) = {d:+.3f}</b> → {v}. Pooled top features: '
                 f'{", ".join(list(meta.get("pred_rf_importance", {}))[:5])}.')
    c = meta.get('churn')
    if c:
        cauc = c.get('AUC') or {}
        est, ci = cauc.get('estimate'), cauc.get('ci')
        if est is None:
            sig_txt = 'predictability not estimable yet'
        elif ci and ci[0] > 0.5:
            sig_txt = f'AUC {est:.2f} — significant'
        elif est > 0.5:
            sig_txt = f'AUC {est:.2f} — directional, not yet statistically significant'
        else:
            sig_txt = f'AUC {est:.2f} — no signal'
        churn_v = (f'Mean churn {c["mean_churn_rate"]*100:.1f}% across {c["k_applicable"]} '
                   f'applicable course(s) ({c["k_na"]} N/A, cram-style). {sig_txt}.')
    else:
        churn_v = 'no applicable courses (all cram-style or single-window).'

    # ── overview row per course (the orientation table, now at the TOP) ────────
    def ov_row(r):
        rk = r.get('risk', {})
        return (f"<tr><td>{r['course']}</td>"
                f"<td class='ctr'>{_g(r,'Q1','n')}</td>"
                f"<td class='ctr'>{_g(r,'Q2','n_retakers')}</td>"
                f"<td class='ctr'>{_g(rk,'R1_fail_a','n_pos')}</td>"
                f"<td class='ctr'>{_g(rk,'R2_no_show_a','n_pos')}</td>"
                f"<td class='num'>{_g(r,'Q1','r_ALS_score','r')}</td>"
                f"<td class='num'>{_g(r,'predictive','cv_r2_full','mean')}</td></tr>")
    overview = ''.join(ov_row(r) for r in R)

    # ── per-course detail (collapsible, at the BOTTOM) ─────────────────────────
    # Each value coloured by AGREEMENT WITH THE EXPECTED TREND:
    #   direction '+' = expected positive (green if > null),  '-' = expected negative.
    def col(raw, direction=None, null=0.0, fmt='{:+.3f}'):
        if raw is None or raw == '—':
            return "<span class='muted'>—</span>"
        try:
            x = float(raw)
        except (TypeError, ValueError):
            return str(raw)
        txt = fmt.format(x)
        if direction is None:
            return txt
        good = (x > null) if direction == '+' else (x < null)
        return f"<span class='{'pos' if good else 'neg'}'>{txt}</span>"

    def detail(r):
        rk = r.get('risk', {}); r1 = rk.get('R1_fail_a', {}); r2 = rk.get('R2_no_show_a', {})
        lo, md, hi = (_g(r, 'Q1', 'tiers_score_z', t, 'mean') for t in ('Low', 'Medium', 'High'))
        tier_ok = isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and hi > lo
        tier = (f"<span class='{'pos' if tier_ok else 'neg'}'>{col(lo,fmt='{:+.2f}')} / "
                f"{col(md,fmt='{:+.2f}')} / {col(hi,fmt='{:+.2f}')}</span>"
                if lo != '—' else "<span class='muted'>—</span>")
        def auc_txt(rx):
            if rx.get('suppressed'):
                return " <span class='muted'>· too few events to model</span>"
            a = rx.get('auc') or {}
            if 'mean' not in a:
                return " <span class='muted'>· AUC not estimable (few events)</span>"
            return f" · AUC {col(a['mean'],'+',0.5,'{:.3f}')}"
        r1auc, r2auc = auc_txt(r1), auc_txt(r2)

        def row(k, v): return f"<tr><td class='k'>{k}</td><td>{v}</td></tr>"
        def grp(g): return f"<tr><td class='grp' colspan='2'>{g}</td></tr>"
        body = ''.join([
            grp('Q1 · ALS ~ Moed-A score  (expect +)'),
            row('r(ALS, score)', col(_g(r, 'Q1', 'r_ALS_score', 'r'), '+')),
            row('d(High − Low)', col(_g(r, 'Q1', 'd_high_low_score', 'd'), '+')),
            row('logOR high-score', col(_g(r, 'Q1', 'logOR_high_score', 'logOR'), '+')),
            row('tier mean z (L / M / H)', tier),
            grp('Q2 · ALS ~ A→B improvement  (expect +)'),
            row('retakers (B-only)', f"{_g(r,'Q2','n_retakers')} ({_g(r,'Q2','n_b_only')})"),
            row('paired improvement (SD)', col(_g(r, 'Q2', 'paired', 'mean_diff_z'), '+')),
            row('r(ALS, improvement)', col(_g(r, 'Q2', 'r_ALS_imp', 'r'), '+')),
            row('d(High − Low) improvement', col(_g(r, 'Q2', 'd_high_low_imp', 'd'), '+')),
            grp('Q3 · within-person ΔRate → grade  (expect +)'),
            row('β(ΔRate | moed_a)', col(_g(r, 'Q3', 'beta_dRate', 'dRate_z', 'beta'), '+')),
            grp('Predictive · ALS audit  (R² expect +)'),
            row('CV R² full model', col(_g(r, 'predictive', 'cv_r2_full', 'mean'), '+')),
            row('CV R² ALS-only', col(_g(r, 'predictive', 'cv_r2_als_only', 'mean'), '+')),
            row('top RF features', ', '.join(list(_g(r, 'predictive', 'rf_importance', default={}))[:4]) or '—'),
            grp('Risk · early-warning  (AUC expect &gt;.5, fail-logOR expect −)'),
            row('R1 fail-A', f"{_g(r1,'n_pos')}/{_g(r1,'n')} fails{r1auc}"),
            row('R1 logOR(ALS High/Low)', col(_g(r1, 'logOR_ALS_high_low', 'logOR'), '-')),
            row('R2 no-show-A', f"{_g(r2,'n_pos')}/{_g(r2,'n')}{r2auc}"),
        ])
        cap = (f"Moed-A mean {_g(r,'standardization','moed_a_mean')}, "
               f"sd {_g(r,'standardization','moed_a_sd')}, high-cut {_g(r,'standardization','high_cut')}")
        return (f"<details><summary>{r['course']} &middot; n={_g(r,'Q1','n')}, "
                f"retakers={_g(r,'Q2','n_retakers')}</summary>"
                f"<div class='cap'>{cap}</div><table class='kv'>{body}</table></details>")
    details = ''.join(detail(r) for r in R)

    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Aaron Owl — Meta v2</title>
<style>
 body{{font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:940px;margin:32px auto;color:#1f2328;padding:0 16px}}
 h1{{font-size:22px;margin-bottom:2px}} h2{{font-size:16px;margin:26px 0 4px;border-bottom:1px solid #eaecef;padding-bottom:4px}}
 table{{border-collapse:collapse;width:100%;margin:8px 0 4px}} th,td{{padding:6px 9px;border-bottom:1px solid #eaecef;text-align:left}}
 th{{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:.03em}}
 .num{{font-variant-numeric:tabular-nums;text-align:right}} .ctr{{text-align:center}}
 tr.sig{{background:#f6fff8}} td.na,.muted{{color:#9a6700}} .q{{color:#656d76;font-size:13px;margin:2px 0 0}}
 .legend{{color:#656d76;font-size:12px;margin-top:8px}}
 .card{{border:1px solid #eaecef;border-radius:8px;padding:12px 14px;margin:10px 0}}
 .card h3{{margin:0 0 2px;font-size:15px}} .verdict{{font-size:13px;margin:4px 0 8px}}
 .vgood{{color:#1a7f37;font-weight:600}} .vbad{{color:#57606a;font-weight:600}} .vtrend{{color:#9a6700;font-weight:600}}
 .ovr th{{background:#f6f8fa}} details{{margin:6px 0;border:1px solid #eaecef;border-radius:6px;padding:4px 10px}}
 summary{{cursor:pointer;font-weight:600}} table.kv td{{border:none;padding:3px 8px}} table.kv td.k{{color:#656d76;width:46%}}
 .pos{{color:#1a7f37;font-weight:600}} .neg{{color:#cf222e;font-weight:600}}
 td.grp{{background:#f6f8fa;font-weight:700;font-size:12px;color:#1f2328;padding-top:7px}}
 .cap{{color:#656d76;font-size:12px;margin:4px 0 2px}}
</style></head><body>
<h1>Aaron Owl — Federated Meta-analysis</h1>
<p class="muted">{meta['k']} courses · random-effects (DerSimonian–Laird) pooling · within-course standardized scores · grades never leave a teacher</p>

<h2>Courses</h2>
<table class="ovr"><tr><th>course</th><th>students</th><th>retakers</th><th>fails (A)</th>
<th>no-shows</th><th>r(ALS,score)</th><th>pred R²</th></tr>{overview}</table>

<h2>Findings (pooled across courses)</h2>

<div class="card"><h3>Q1 · Does ALS correlate with the Moed-A outcome?</h3>
<div class="verdict">{verdict('Q1_r_ALS_score', 'Higher ALS correlates with higher Moed-A score', 'No ALS–score correlation')}</div>
<p class="q">Cross-sectional, all students. Outcome = standardized Moed-A score. Association, not causation.</p>
<table><tr>{head}</tr>{rows(Q1)}</table></div>

<div class="card"><h3>Q2 · Does ALS correlate with A→B improvement?</h3>
<div class="verdict">{verdict('Q2_r_ALS_imp', 'Higher ALS correlates with bigger retake gain', 'ALS does not (yet) correlate with who improves most')}</div>
<p class="q">Retakers only. Outcome = standardized improvement (Moed B − Moed A). Retakers do improve overall (paired row); the question is whether ALS predicts <em>who</em>.</p>
<table><tr>{head}</tr>{rows(Q2)}</table></div>

<div class="card"><h3>Q3 · Does <em>increasing</em> activity raise the grade?</h3>
<div class="verdict">{verdict('Q3_beta_dRate', 'Increasing activity → higher grade (within-person)', 'No within-person evidence yet (underpowered)')}</div>
<p class="q">Within-person fixed-effects, controlling baseline Moed A (regression-to-mean).</p>
<table><tr>{head}</tr>{rows(Q3)}</table></div>

<div class="card"><h3>Predictive model · ALS audit</h3>
<div class="verdict">{audit}</div>
<p class="q">Data-driven Ridge on all pre-A features vs ALS alone — does a free model beat the construct?</p>
<table><tr>{head}</tr>{rows(PRED)}</table></div>

<div class="card"><h3>Risk / early-warning</h3>
<div class="verdict">{verdict('R1_fail_AUC', 'Failing Moed A is predictable from early activity', 'Fail-A not yet predictable', null=0.5)}</div>
<p class="q">Classification from pre-exam activity. AUC null = 0.5; logOR null = 0. <b>Churn:</b> {churn_v}</p>
<table><tr>{head}</tr>{rows(RISK)}</table></div>

<p class="legend"><b>Verdict states:</b> <span class="vgood">✅ significant</span> (95% CI excludes the null — 0 for effect sizes, 0.5 for AUC) ·
<span class="vtrend">🟡 trend</span> (point estimate in the expected direction but CI still spans the null — directional, underpowered) ·
<span class="vbad">◻️ not estimable / null</span> (too few courses or events — e.g. an easy course with almost no fails; pools as more courses join).
<b>Absence of evidence ≠ evidence of absence.</b> I² = between-course heterogeneity; p_het = Cochran's Q. Forest scale differs per row.</p>

<h2>Per-course detail <span class="muted" style="font-weight:400">(click to expand)</span></h2>
{details}
</body></html>"""
    (out / 'meta_report.html').write_text(html, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', nargs='+', required=True, help='dirs each holding results.json')
    ap.add_argument('--out', default='results/meta')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    R = [json.loads((Path(d) / 'results.json').read_text()) for d in a.results]
    names = [r['course'] for r in R]
    print(f"Pooling {len(R)} courses: {names}\n")

    meta = {'courses': names, 'k': len(R)}

    # Q1: r(ALS, score) via Fisher-z ; d(High-Low) via DL
    r1 = [(x or {}) for x in collect(R, 'Q1', 'r_ALS_score')]
    meta['Q1_r_ALS_score'] = fisher_pool([x.get('r', np.nan) for x in r1],
                                         [x.get('n', 0) for x in r1])
    d1 = [(x or {}) for x in collect(R, 'Q1', 'd_high_low_score')]
    meta['Q1_d_high_low_score'] = dl_pool([x.get('d', np.nan) for x in d1],
                                          [x.get('se', np.nan) for x in d1])
    lor = [(x or {}) for x in collect(R, 'Q1', 'logOR_high_score')]
    meta['Q1_logOR_high'] = dl_pool([x.get('logOR', np.nan) for x in lor],
                                    [x.get('se', np.nan) for x in lor])

    # Q2: r(ALS, improvement) ; d(High-Low improvement) ; pooled paired improvement
    r2 = [(x or {}) for x in collect(R, 'Q2', 'r_ALS_imp')]
    meta['Q2_r_ALS_imp'] = fisher_pool([x.get('r', np.nan) for x in r2],
                                       [x.get('n', 0) for x in r2])
    d2 = [(x or {}) for x in collect(R, 'Q2', 'd_high_low_imp')]
    meta['Q2_d_high_low_imp'] = dl_pool([x.get('d', np.nan) for x in d2],
                                        [x.get('se', np.nan) for x in d2])
    pj = [(x or {}) for x in collect(R, 'Q2', 'paired')]
    eff = [x.get('mean_diff_z', np.nan) for x in pj]
    se = [x.get('sd_diff_z', np.nan) / math.sqrt(x['n']) if x.get('n', 0) > 1 else np.nan for x in pj]
    meta['Q2_paired_improvement_z'] = dl_pool(eff, se)

    # Q3: standardized within-person beta(dRate) via DL
    b3 = []
    for x in collect(R, 'Q3', 'beta_dRate'):
        x = x or {}
        dr = x.get('dRate_z') if isinstance(x, dict) else None
        b3.append(dr or {})
    meta['Q3_beta_dRate'] = dl_pool([x.get('beta', np.nan) for x in b3],
                                    [x.get('se', np.nan) for x in b3])

    # ── Risk family ──────────────────────────────────────────────────────────
    r1a = [(x or {}) for x in collect(R, 'risk', 'R1_fail_a', 'auc')]
    meta['R1_fail_AUC'] = dl_pool([x.get('mean', np.nan) for x in r1a],
                                  [x.get('se', np.nan) for x in r1a])
    r1o = [(x or {}) for x in collect(R, 'risk', 'R1_fail_a', 'logOR_ALS_high_low')]
    meta['R1_fail_logOR_ALS'] = dl_pool([x.get('logOR', np.nan) for x in r1o],
                                        [x.get('se', np.nan) for x in r1o])
    r2a = [(x or {}) for x in collect(R, 'risk', 'R2_no_show_a', 'auc')]
    meta['R2_noshow_AUC'] = dl_pool([x.get('mean', np.nan) for x in r2a],
                                    [x.get('se', np.nan) for x in r2a])

    # ── Predictive block + ALS audit ─────────────────────────────────────────
    pf = [(x or {}) for x in collect(R, 'predictive', 'cv_r2_full')]
    pa = [(x or {}) for x in collect(R, 'predictive', 'cv_r2_als_only')]
    meta['pred_r2_full'] = dl_pool([x.get('mean', np.nan) for x in pf], [x.get('se', np.nan) for x in pf])
    meta['pred_r2_als'] = dl_pool([x.get('mean', np.nan) for x in pa], [x.get('se', np.nan) for x in pa])
    imp_acc = {}
    for r in R:
        pb = r.get('predictive') or {}
        if pb.get('suppressed'):
            continue
        n = pb.get('n', 0)
        for f, v in (pb.get('rf_importance') or {}).items():
            imp_acc.setdefault(f, [0.0, 0])
            imp_acc[f][0] += v * n; imp_acc[f][1] += n
    meta['pred_rf_importance'] = dict(sorted(
        {f: round(s / w, 4) for f, (s, w) in imp_acc.items() if w > 0}.items(),
        key=lambda kv: -kv[1])[:10])

    # ── Churn (separate grade-free file, applicable courses only) ─────────────
    ch = [json.loads((Path(d) / 'churn_results.json').read_text())
          for d in a.results if (Path(d) / 'churn_results.json').exists()]
    ch_ok = [c for c in ch if c.get('applicable')]
    meta['churn'] = None
    if ch_ok:
        cauc = [(c.get('model_auc') or {}) for c in ch_ok]
        meta['churn'] = {
            'k_applicable': len(ch_ok), 'k_na': len(ch) - len(ch_ok),
            'mean_churn_rate': round(float(np.mean([c['churn_rate'] for c in ch_ok])), 4),
            'AUC': dl_pool([x.get('mean', np.nan) for x in cauc],
                           [x.get('se', np.nan) for x in cauc])}

    (out / 'meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    write_html(meta, R, out)

    # ── console forest report ────────────────────────────────────────────────
    def line(label, p, null=0.0):
        if not p:
            print(f"  {label:30s}  (no poolable data)"); return
        est = p.get('estimate_r', p['estimate']); ci = p.get('ci_r', p['ci'])
        het = '' if p.get('I2') is None else f"  I²={p['I2']}%  p_het={p.get('p_het')}"
        sig = '*' if (ci[0] > null or ci[1] < null) else ' '
        print(f"  {label:30s} {est:+.3f}  [{ci[0]:+.3f},{ci[1]:+.3f}] {sig}  k={p['k']}{het}")

    print("="*78)
    print(f"META  ({len(R)} courses)   * = 95% CI excludes 0")
    print("="*78)
    print("Q1  Does ALS correlate with Moed-A outcome?")
    line('r(ALS, score)', meta['Q1_r_ALS_score'])
    line('d(High-Low) score', meta['Q1_d_high_low_score'])
    line('logOR high-score', meta['Q1_logOR_high'])
    print("Q2  Does ALS correlate with A->B improvement? (retakers)")
    line('r(ALS, improvement)', meta['Q2_r_ALS_imp'])
    line('d(High-Low) improvement', meta['Q2_d_high_low_imp'])
    line('paired improvement (SD)', meta['Q2_paired_improvement_z'])
    print("Q3  Does INCREASING activity raise grade? (within-person, RTM-ctrl)")
    line('beta(dRate_z)', meta['Q3_beta_dRate'])
    print("Predictive (data-driven) — ALS audit  (does a free model beat ALS-only?)")
    line('CV R² full model', meta['pred_r2_full'])
    line('CV R² ALS-only', meta['pred_r2_als'])
    if meta['pred_r2_full'] and meta['pred_r2_als']:
        d = meta['pred_r2_full']['estimate'] - meta['pred_r2_als']['estimate']
        verdict = 'ALS is a good parsimonious summary' if d <= 0.02 else 'full model adds predictive value'
        print(f"  {'Δ full − ALS':30s} {d:+.3f}  → {verdict}")
    if meta.get('pred_rf_importance'):
        top = list(meta['pred_rf_importance'])[:5]
        print(f"  {'pooled top RF features':30s} {top}")
    print("Risk / early-warning   (AUC null = 0.5)")
    line('R1 fail-A  AUC', meta['R1_fail_AUC'], null=0.5)
    line('R1 fail-A  logOR(ALS H/L)', meta['R1_fail_logOR_ALS'])
    line('R2 no-show AUC', meta['R2_noshow_AUC'], null=0.5)
    if meta['churn']:
        c = meta['churn']
        print(f"Churn (grade-free)  mean rate={c['mean_churn_rate']*100:.1f}%  "
              f"applicable={c['k_applicable']} N/A={c['k_na']}")
        line('  churn AUC', c['AUC'], null=0.5)
    print("="*78)
    print(f"wrote {out/'meta.json'}")


if __name__ == '__main__':
    main()
