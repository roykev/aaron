#!/usr/bin/env python3
"""
Aaron Owl — Central student clustering (v3, grade-free, WHOLE-PLATFORM)
======================================================================
Usage data is grade-free and centralized, so we cluster on the ENTIRE platform — every
student in every course in the raw event data (not just pipeline-run courses). Behavioral
features are computed directly from events and standardized WITHIN each course, so clusters
capture behavioral *shape* (steady / crammer / browser / power-user …), comparable across
courses. Output: a `cluster_id` + `cluster_name` per (course, student); with --write-back it
is appended to each configured course's federation feature CSV (grade-free feature + lens).

    python federation/cluster_students.py --k 5 --out <dir> --write-back          # all events
    python federation/cluster_students.py --from-features --courses psy bio ...    # 4-course mode
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import pipeline
from modules.identity_resolver import IdentityResolver
from sklearn.cluster import KMeans

# behavioral features (event-derived); counts are log1p'd before z to tame skew
COUNT_FEATS = ['total_active_events', 'active_days', 'n_eval', 'unique_lectures', 'events_per_active_day']
RATIO_FEATS = ['active_weeks_ratio', 'feature_diversity']
CLUSTER_FEATS = RATIO_FEATS + COUNT_FEATS
TAG = {'active_weeks_ratio': 'consistent', 'total_active_events': 'high-volume',
       'events_per_active_day': 'intense-sessions', 'feature_diversity': 'broad',
       'unique_lectures': 'wide-coverage', 'n_eval': 'assessment-focused', 'active_days': 'frequent'}


def _load_all_events(cfg):
    wd = Path(cfg['data']['weekly_events_dir'])
    keep = ['event', 'datetime', 'distinct_id', 'course', 'lecture', 'tab']
    frames = [pd.read_csv(f, low_memory=False, usecols=lambda c: c in keep)
              for f in sorted(glob.glob(str(wd / 'week_*.csv')))]
    ev = pd.concat(frames, ignore_index=True)
    ev['datetime'] = pd.to_datetime(ev['datetime'], errors='coerce')
    aet = set(cfg['events']['active_event_types']); atc = set(cfg['events'].get('active_tab_changes', []))
    ev['is_active'] = ev['event'].isin(aet) | ((ev['event'] == 'tab_change') & ev.get('tab', pd.Series(index=ev.index)).isin(atc))
    ev = IdentityResolver(cfg).resolve(ev)
    ev = pipeline._drop_excluded_accounts(ev, cfg)
    return ev[ev['email'].notna()]


def features_from_events(cfg):
    ev = _load_all_events(cfg)
    ev['date'] = ev['datetime'].dt.date
    ev['week'] = ev['datetime'].dt.to_period('W')
    span = ev.groupby('course')['week'].nunique().rename('course_weeks')
    act = ev[ev['is_active']]
    ge = act.groupby(['course', 'email'])
    f = pd.DataFrame({'total_active_events': ge.size(),
                      'active_days': ge['date'].nunique(),
                      'active_weeks': ge['week'].nunique()})
    f['n_eval'] = act[act['event'].astype(str).str.contains('eval', na=False)].groupby(['course', 'email']).size()
    f['feature_diversity'] = ev.groupby(['course', 'email'])['event'].nunique()
    f['unique_lectures'] = ev.groupby(['course', 'email'])['lecture'].nunique()
    f = f.fillna(0.0).reset_index().merge(span, on='course')
    f['active_weeks_ratio'] = f['active_weeks'] / f['course_weeks'].clip(lower=1)
    f['events_per_active_day'] = f['total_active_events'] / f['active_days'].clip(lower=1)
    return f


def features_from_csvs(cfg, courses):
    frames = []
    for key in courses:
        cc = cfg['courses'].get(key, {})
        fed = Path(cc.get('federation_dir') or cfg['data']['federation_dir'])
        fpath = fed / f'student_features_{key}_federation.csv'
        if not fpath.exists():
            continue
        d = pd.read_csv(fpath)
        d = d.rename(columns={d.columns[0]: 'email'})
        d['course'] = cc.get('course_id', key)
        frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _z_within(df, feats):
    X = pd.DataFrame(index=df.index)
    logset = set(COUNT_FEATS)
    for c in feats:
        v = pd.to_numeric(df[c], errors='coerce')
        if c in logset:
            v = np.log1p(v.clip(lower=0))
        g = df['course']
        X[c] = v.groupby(g).transform(lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else 0.0)
    return X.fillna(0.0)


def _name_clusters(prof):
    names, seen = {}, {}
    for cid, row in prof.iterrows():
        base = 'low-engaged' if row.mean() < -0.3 else TAG.get(row.idxmax(), str(row.idxmax()))
        seen[base] = seen.get(base, 0) + 1
        names[cid] = base if seen[base] == 1 else f'{base}-{seen[base]}'
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml')
    ap.add_argument('--from-features', action='store_true', help='cluster from pipeline feature CSVs instead of all events')
    ap.add_argument('--courses', nargs='*', default=[], help='(feature mode) which courses')
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--out', required=True)
    ap.add_argument('--write-back', action='store_true')
    a = ap.parse_args()
    cfg_path = Path(a.config)
    if not cfg_path.is_absolute():
        cfg_path = HERE.parent / cfg_path
    cfg = yaml.safe_load(open(cfg_path))

    if a.from_features:
        df = features_from_csvs(cfg, a.courses or list(cfg['courses']))
        feats = [c for c in CLUSTER_FEATS if c in df.columns]
    else:
        print("Computing behavioral features from ALL events across every course…")
        df = features_from_events(cfg)
        feats = [c for c in CLUSTER_FEATS if c in df.columns]
    if df.empty:
        raise SystemExit("no data to cluster")

    Z = _z_within(df, feats)
    km = KMeans(n_clusters=a.k, n_init=10, random_state=0).fit(Z[feats].values)
    df['cluster_id'] = km.labels_
    prof = pd.DataFrame(Z[feats].values, columns=feats).assign(cluster_id=km.labels_).groupby('cluster_id').mean().round(2)
    names = _name_clusters(prof)
    df['cluster_name'] = df['cluster_id'].map(names)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    prof_out = prof.copy()
    prof_out.insert(0, 'cluster_name', [names[i] for i in prof.index])
    prof_out.insert(1, 'n', df['cluster_id'].value_counts().sort_index().values)
    prof_out.to_csv(out / 'cluster_profiles.csv')
    df[['course', 'email', 'cluster_id', 'cluster_name']].to_csv(out / 'cluster_assignments.csv', index=False)

    print(f"\nClustered {len(df):,} (course,student) rows from {df['course'].nunique()} courses into k={a.k}:")
    for cid in prof.index:
        top = prof.loc[cid].abs().sort_values(ascending=False).index[:3]
        print(f"  [{cid}] {names[cid]:18s} n={int((df['cluster_id']==cid).sum()):4d}  "
              f"top: {', '.join(f'{c}={prof.loc[cid,c]:+.1f}' for c in top)}")

    if a.write_back:
        for key, cc in cfg['courses'].items():
            fed = Path(cc.get('federation_dir') or cfg['data']['federation_dir'])
            fpath = fed / f'student_features_{key}_federation.csv'
            cid = cc.get('course_id')
            if not fpath.exists() or cid is None:
                continue
            sub = df[df['course'] == cid]
            if sub.empty:
                continue
            d = pd.read_csv(fpath); ecol = d.columns[0]
            emap = sub.set_index('email')['cluster_id'].to_dict()
            nmap = sub.set_index('email')['cluster_name'].to_dict()
            d['cluster_id'] = d[ecol].astype(str).str.lower().map(emap)
            d['cluster_name'] = d[ecol].astype(str).str.lower().map(nmap)
            d.to_csv(fpath, index=False)
            print(f"  wrote cluster_id -> {key} ({int(d['cluster_id'].notna().sum())}/{len(d)} matched)")
    print(f"\nProfiles: {out/'cluster_profiles.csv'}")


if __name__ == '__main__':
    main()
