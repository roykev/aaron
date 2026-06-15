#!/usr/bin/env python3
"""
Simulate realistic moed_a / moed_b grades FROM A REAL feature CSV, using the
course's actual ALS + post-A (cram) activity. Lets us dry-run analysis_script_v2
on a real course's activity before the teacher supplies real grades.

Planted structure (so the dry-run is interpretable):
  moed_a    ~ base + beta_als*(ALS-50) + noise              (Q1 signal)
  retakers  = students who FAILED A (moed_a < pass_mark)
  moed_b    = moed_a + RTM_base + q3_gain*z(postA activity)  (Q2/Q3 signal)
  a few B-only students (absent A, sat B)

Usage:
    python simulate_grades.py --features <federation.csv> --out <grades.csv> \
        --seed 11 --base 72 --beta_als 0.32 --sd 11 --pass-mark 60 --q3_gain 4
"""
import argparse
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--features', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=11)
    ap.add_argument('--base', type=float, default=72.0)
    ap.add_argument('--beta_als', type=float, default=0.32)
    ap.add_argument('--sd', type=float, default=11.0)
    ap.add_argument('--pass-mark', type=float, default=60.0)
    ap.add_argument('--q3_gain', type=float, default=4.0)
    ap.add_argument('--n_b_only', type=int, default=2)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    F = pd.read_csv(a.features)
    F['email'] = F['email'].str.lower().str.strip()
    als = F['active_learning_score'].fillna(F['active_learning_score'].median()).values
    n = len(F)

    # Moed A from pre-A ALS
    moed_a = np.clip(a.base + a.beta_als * (als - 50) + rng.normal(0, a.sd, n), 0, 100).round()

    # post-A (cram) activity → drives the retake improvement
    cram = F.get('postA_total_active_events', pd.Series(np.zeros(n))).fillna(0).values
    czs = cram.std()
    cram_z = (cram - cram.mean()) / czs if czs > 0 else np.zeros(n)

    moed_b = np.full(n, np.nan)
    failed = np.where(moed_a < a.pass_mark)[0]
    for i in failed:
        rtm = rng.normal(11, 4)                          # second-attempt / regression-to-mean
        q3 = a.q3_gain * cram_z[i]                        # planted within-person signal
        moed_b[i] = np.clip(moed_a[i] + rtm + q3 + rng.normal(0, 4), 0, 100).round()

    # a few B-only students (absent from A) — drawn from passers
    passers = np.where(moed_a >= a.pass_mark)[0]
    for i in rng.choice(passers, size=min(a.n_b_only, len(passers)), replace=False):
        moed_b[i] = np.clip(moed_a[i] + rng.normal(0, 5), 0, 100).round()
        moed_a[i] = np.nan

    out = pd.DataFrame({'email': F['email'], 'moed_a': moed_a, 'moed_b': moed_b})
    out.to_csv(a.out, index=False)
    nb = int(out['moed_b'].notna().sum())
    nf = int((out['moed_a'] < a.pass_mark).sum())
    print(f"wrote {a.out}: {n} students, {nf} failed A, {nb} retakers (moed_b), "
          f"{int((out['moed_a'].isna() & out['moed_b'].notna()).sum())} B-only")
    print(f"  moed_a mean={np.nanmean(out['moed_a']):.1f} sd={np.nanstd(out['moed_a']):.1f} "
          f"| corr(ALS,moed_a)={np.corrcoef(als[out['moed_a'].notna()], out['moed_a'].dropna())[0,1]:+.2f}")


if __name__ == '__main__':
    main()
