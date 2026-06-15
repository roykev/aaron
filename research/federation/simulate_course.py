#!/usr/bin/env python3
"""
Simulate a synthetic course (federation feature CSV + grades_moed_ab.csv) with a
KNOWN planted signal, to exercise analysis_script_v2 + meta_analysis_v2 end-to-end.

Ground truth planted:
  Q1: moed_a rises with ALS            (beta_als > 0)
  Q2: retakers (low moed_a) improve, more so for higher-ALS students
  Q3: bigger post-A activity increase  -> bigger A->B improvement (within-person)

Usage:
    python simulate_course.py --name "Sim Course A" --seed 1 --out results/simA \
        --n 120 --beta_als 0.30 --q3_gain 0.6
"""
import argparse, hashlib
from pathlib import Path
import numpy as np
import pandas as pd


def simulate(name, seed, n, beta_als, q3_gain):
    rng = np.random.default_rng(seed)
    als = np.clip(rng.normal(50, 22, n), 0, 100)
    level = np.where(als < 30, 'Low', np.where(als <= 60, 'Medium', 'High'))
    # pre-A activity scales with ALS
    pre_rate = np.clip(als * rng.uniform(0.6, 1.4, n), 1, None)
    active_days = np.clip((als / 8 + rng.normal(0, 2, n)).round(), 1, None)
    total_active = (pre_rate * active_days).round()

    # Moed A grade: rises with ALS (planted Q1 signal), ceiling at 100
    moed_a = np.clip(70 + beta_als * (als - 50) + rng.normal(0, 8, n), 0, 100).round()

    # retakers = students who scored below pass (60); a few B-only (absent A)
    failed = moed_a < 60
    moed_b = np.full(n, np.nan)
    postA_active = np.zeros(n)
    postA_days = np.zeros(n)
    for i in np.where(failed)[0]:
        # some retakers study post-A (variable intensity), some don't
        studied = rng.random() < 0.6
        d_rate = rng.uniform(0, 1.5) * als[i] if studied else 0.0
        postA_days[i] = rng.integers(1, 6) if studied else 0
        postA_active[i] = round(d_rate * postA_days[i])
        # improvement = retake/RTM base + Q3 effect of post-A study + ALS-tier effect
        base = rng.normal(12, 5)                       # RTM / second-attempt
        q3 = q3_gain * (d_rate / 40.0)                 # planted Q3 within-person signal
        tier = 0.08 * (als[i] - 50)                    # planted Q2 ALS-tier signal
        moed_b[i] = np.clip(moed_a[i] + base + q3 + tier + rng.normal(0, 4), 0, 100).round()

    # a couple of B-only students (absent from A)
    for i in rng.choice(np.where(~failed)[0], size=2, replace=False):
        moed_b[i] = np.clip(moed_a[i] + rng.normal(0, 5), 0, 100).round()
        moed_a[i] = np.nan

    emails = [f"sim{seed}_{i:03d}@example.edu" for i in range(n)]
    feats = pd.DataFrame({
        'email': emails, 'course_id': hashlib.sha256(name.encode()).hexdigest()[:12],
        'active_learning_score': als.round(2), 'active_learning_level': level,
        'total_active_events': total_active, 'active_days': active_days,
        'postA_total_active_events': postA_active, 'postA_active_days': postA_days,
    })
    grades = pd.DataFrame({'email': emails, 'moed_a': moed_a, 'moed_b': moed_b})
    return feats, grades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--n', type=int, default=120)
    ap.add_argument('--beta_als', type=float, default=0.30)
    ap.add_argument('--q3_gain', type=float, default=0.6)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    feats, grades = simulate(a.name, a.seed, a.n, a.beta_als, a.q3_gain)
    feats.to_csv(out / 'features.csv', index=False)
    grades.to_csv(out / 'grades_moed_ab.csv', index=False)
    print(f"[{a.name}] n={a.n}  retakers={int(grades['moed_b'].notna().sum())}  "
          f"-> {out}  (planted beta_als={a.beta_als}, q3_gain={a.q3_gain})")


if __name__ == '__main__':
    main()
