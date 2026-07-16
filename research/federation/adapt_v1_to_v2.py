#!/usr/bin/env python3
"""
Aaron Owl — v1 → v2 results adapter
===================================
Converts a legacy v1 teacher return (the 4-file bundle from analysis_script.py:
correlation_report.csv, als_tier_profile.csv, feature_importance.csv,
regression_summary.txt) into a v2-format results.json that meta_analysis_v2.py
can pool — but ONLY for the questions the v1 return actually supports (Q1 + the
ALS tier profile). Everything else is emitted as {available: false} so the meta
coverage matrix honestly shows this course answering Q1 only.

Use when a teacher ran the OLD script and won't re-run (e.g. math, final-only,
no exam windows, no early-warning). An optional --external JSON is copied through
verbatim into results['external_correlates'] (course-specific, never pooled).

Usage:
    python adapt_v1_to_v2.py --v1-dir <dir> --course "Name" \
        --grade-mode final --n-features 51 --external math_external_correlates.json \
        --out <out_dir>
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

TIER_ORDER = ['Low', 'Medium', 'High']


def _q1_from_v1(v1: Path):
    corr = pd.read_csv(v1 / 'correlation_report.csv')
    prof = pd.read_csv(v1 / 'als_tier_profile.csv')

    # r(ALS, grade) — the poolable Q1 correlation
    als = corr[corr['feature'] == 'active_learning_score']
    r = float(als['pearson_r'].iloc[0]); sp = float(als['spearman_r'].iloc[0])
    n = int(als['n'].iloc[0])
    r_ALS = {'r': round(r, 4), 'spearman': round(sp, 4), 'n': n}

    # reconstruct within-course grade mean/sd from the tier profile (mean_grade + mean_grade_z)
    prof = prof.set_index('als_level')
    tot_n = int(prof['n'].sum())
    mean = float((prof['n'] * prof['mean_grade']).sum() / tot_n)
    sds = [(prof.loc[t, 'mean_grade'] - mean) / prof.loc[t, 'mean_grade_z']
           for t in prof.index if abs(prof.loc[t, 'mean_grade_z']) > 1e-6]
    sd = float(np.mean(sds)) if sds else float('nan')

    # tier sufficient stats in z-units (poolable exactly like the v2 tier_suff_stats)
    tiers = {}
    for t in TIER_ORDER:
        if t not in prof.index:
            tiers[t] = {'n': 0, 'suppressed': True}; continue
        ni = int(prof.loc[t, 'n']); mz = float(prof.loc[t, 'mean_grade_z'])
        sdz = float(prof.loc[t, 'std_grade']) / sd if sd else float('nan')
        tiers[t] = {'n': ni, 'mean': round(mz, 4), 'sd': round(sdz, 4),
                    'sum': round(ni * mz, 4),
                    'sumsq': round((ni - 1) * sdz ** 2 + ni * mz ** 2, 4) if ni > 1 else round(ni * mz ** 2, 4),
                    'suppressed': ni < 3}

    # Cohen's d (High vs Low) — from the profile, with Hedges-style SE
    d_hl = None
    if 'High' in prof.index and 'Low' in prof.index and not pd.isna(prof.loc[prof.index == 'High', 'cohens_d_vs_low']).all():
        d = float(prof.loc['High', 'cohens_d_vs_low'])
        n1, n0 = int(prof.loc['High', 'n']), int(prof.loc['Low', 'n'])
        se = float(np.sqrt((n1 + n0) / (n1 * n0) + d ** 2 / (2 * (n1 + n0))))
        d_hl = {'d': round(d, 4), 'se': round(se, 4), 'n1': n1, 'n2': n0}

    q1 = {'n': n, 'tiers_score_z': tiers, 'r_ALS_score': r_ALS,
          'd_high_low_score': d_hl, 'logOR_high_score': None}
    return q1, mean, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v1-dir', required=True)
    ap.add_argument('--course', required=True)
    ap.add_argument('--grade-mode', default='final')
    ap.add_argument('--outcome-semantics', default='final_max')
    ap.add_argument('--n-features', type=int, default=None)
    ap.add_argument('--external', default=None, help='optional course-specific correlates JSON (verbatim)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    v1 = Path(a.v1_dir)

    q1, mean, sd = _q1_from_v1(v1)
    na = {'available': False, 'reason': 'v1 teacher return: final-only, no exam windows / no classifier'}
    res = {
        'course': a.course,
        'course_id': hashlib.sha256(a.course.encode()).hexdigest()[:12],
        'n_features': a.n_features if a.n_features is not None else q1['n'],
        'grade_mode': a.grade_mode,
        'outcome_semantics': a.outcome_semantics,
        'has_exam_windows': False,
        'answered': ['Q1'],
        'source': 'adapted from v1 teacher return (4-file bundle)',
        'standardization': {'moed_a_mean': round(mean, 2), 'moed_a_sd': round(sd, 2),
                            'high_cut': None, 'suppress_k': 3, 'outcome': a.outcome_semantics},
        'Q1': q1,
        'Q2': na, 'Q3': na,
        'risk': {'R1_fail_a': dict(na), 'R2_no_show_a': dict(na)},
        'predictive': {'suppressed': True, 'n': q1['n'],
                       'note': 'v1 CV R² was overfit (n<<features); not pooled'},
        'subgroups': dict(na),
    }
    # attach the real v1 feature importance for reference (informational, not pooled)
    fi = pd.read_csv(v1 / 'feature_importance.csv')
    res['v1_feature_importance'] = {r.feature: round(float(r.importance), 4)
                                    for r in fi.head(10).itertuples()}
    if a.external:
        res['external_correlates'] = json.loads(Path(a.external).read_text())

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[{a.course}] wrote {out/'results.json'}")
    print(f"  answered: {res['answered']}  (grade_mode={a.grade_mode}, mean={mean:.1f}, sd={sd:.1f})")
    print(f"  Q1 r(ALS,grade)={q1['r_ALS_score']['r']} (n={q1['n']}), d(H-L)={q1['d_high_low_score']}")
    if a.external:
        ec = res['external_correlates']['correlates_vs_exam']
        print(f"  external: assignment r={ec['assignment_score_0_100']['pearson_r']}, "
              f"tutor r={ec['tutor_use_1_3_5']['pearson_r']}")


if __name__ == '__main__':
    main()
