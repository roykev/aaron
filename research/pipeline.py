#!/usr/bin/env python3
"""
Aaron Owl Research Pipeline
============================
Entry point. Runs the full pipeline for one or all configured courses.

Usage:
    python pipeline.py                          # all courses in config.yaml
    python pipeline.py --course example_course  # single course key (as defined in config.yaml)
    python pipeline.py --course example_course --target synthetic_random
"""
import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd
import yaml

from modules.event_loader import EventLoader
from modules.identity_resolver import IdentityResolver
from modules.session_builder import SessionBuilder
from modules.student_features import StudentFeatureBuilder, load_academic_csv
from modules import active_learning_score as als
from modules import normalization
from targets.synthetic import create as create_target
from federation.usage_report import generate as generate_usage_report


def load_config(path: str = 'config.yaml') -> dict:
    cfg_path = Path(path)
    if not cfg_path.is_absolute():
        cfg_path = Path(__file__).parent / cfg_path
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _resolve_windows(config: dict, course_cfg: dict):
    """Return the activity windows for a course as [(name, start_date|None, end_date|None), ...].

    Driven by per-course exam dates:
      - moed_a_date present            -> 'preA'  window [start, moed_a_date)
                                          + 'postA' window [moed_a_date, moed_b_date)
                                            (open-ended if moed_b_date is absent)
      - no moed_a_date (e.g. math)     -> single 'all' window [None, None]
    --cutoff none (config['_cutoff_override']=='none') forces a single 'all' window (baseline).

    'postA' is the retake/cram window (activity after Moed A). The upper bound is
    moed_b_date when known (excludes post-retake noise) but is OPTIONAL: the retake
    subgroup is identified downstream by a non-null `moed_b` grade, not by the date,
    so an open-ended postA window is equivalent for Model B (e.g. psy).
    Boundaries partition cleanly: preA = date < A, postA = A <= date (< B if set).
    """
    if str(config.get('_cutoff_override', '')).lower() == 'none':
        return [('all', None, None)]
    a_raw, b_raw = course_cfg.get('moed_a_date'), course_cfg.get('moed_b_date')
    a = pd.Timestamp(a_raw).date() if a_raw else None
    b = pd.Timestamp(b_raw).date() if b_raw else None
    if a is None:
        return [('all', None, None)]
    return [('preA', None, a), ('postA', a, b)]  # b may be None -> open-ended postA


def _window(df, col: str, start, end, label: str = ''):
    """Keep rows whose `col` date is in [start, end): start/end are dates or None.
    No-op if df is None or column absent."""
    if df is None or col not in getattr(df, 'columns', []):
        return df
    d = pd.to_datetime(df[col], utc=True, errors='coerce').dt.date
    keep = pd.Series(True, index=df.index)
    if start is not None:
        keep &= d >= start
    if end is not None:
        keep &= d < end
    if label and (start is not None or end is not None):
        print(f"    window[{label}] {start}..{end}: {len(df)} -> {int(keep.sum())} rows")
    return df[keep.values]


def _build_block(config, course_key, events, eval_df, quiz_df, start, end, label):
    """Build one windowed feature block (events+eval+quiz sliced to [start,end)) with ALS."""
    ev = _window(events, 'datetime', start, end, f'{label}:events')
    ses = SessionBuilder(config).build(ev)
    ed = _window(eval_df, 'time', start, end, f'{label}:eval')
    qd = _window(quiz_df, 'time', start, end, f'{label}:quiz')
    block = StudentFeatureBuilder(config, course_key).build(ev, ses, ed, qd)
    als_weights = config.get('active_learning_score', {}).get('weights')
    block['active_learning_score'] = als.compute(block, als_weights)
    block['active_learning_level'] = als.classify(block['active_learning_score'])
    return block


def run_course(config: dict, course_key: str) -> pd.DataFrame:
    course_cfg = config['courses'][course_key]
    course_id = course_cfg['course_id']
    print(f"\n{'='*60}")
    print(f"Course: {course_cfg['name']} ({course_key})")
    print(f"{'='*60}")

    windows = _resolve_windows(config, course_cfg)
    print(f"Activity windows: {[(n, str(s), str(e)) for n, s, e in windows]}")

    # 1. Load events + resolve identities (done once; windows slice afterwards)
    loader = EventLoader(config)
    events = loader.load(course_id)
    resolver = IdentityResolver(config)
    events = resolver.resolve(events)

    # 4. Load academic data (CSV or Excel sheet)
    eval_df = load_academic_csv(course_cfg.get('eval_csv', ''), sheet=course_cfg.get('eval_sheet'))
    quiz_df  = load_academic_csv(course_cfg.get('quiz_csv', ''),  sheet=course_cfg.get('quiz_sheet'))

    # 5. Build the primary feature block (preA, or the single 'all' window)
    primary_name, p_start, p_end = windows[0]
    features = _build_block(config, course_key, events, eval_df, quiz_df, p_start, p_end, primary_name)

    # 5b. Build & graft any secondary window blocks (e.g. AtoB cram window), prefixed
    for name, s, e in windows[1:]:
        blk = _build_block(config, course_key, events, eval_df, quiz_df, s, e, name)
        blk = blk.add_prefix(f'{name}_')
        features = features.join(blk, how='left')
        print(f"Grafted {name}_ block: +{blk.shape[1]} cols ({blk.shape[0]} students with {name} activity)")

    # 7. Normalize (primary block only — secondary blocks carry raw + ALS)
    features = normalization.add_zscore(features)
    features = normalization.add_percentile(features)

    # 8. Build target
    target_strategy = create_target(config)
    print(f"\nTarget: {target_strategy.description()}")
    features['target'] = target_strategy.build(features)

    # 9. Save
    out_dir, fed_dir = _course_dirs(config, course_key)
    out_path = out_dir / f'student_features_{course_key}.csv'
    features.to_csv(out_path)
    print(f"\nSaved: {out_path}  ({len(features)} students × {len(features.columns)} columns)")

    # 10. Export federation CSV
    fed_csv_path = _export_federation(features, config, course_key)

    # 11. Teacher usage report
    from datetime import date
    report_path = fed_dir / f'usage_report_{course_key}.html'
    fed_df = pd.read_csv(fed_csv_path)
    html = generate_usage_report(fed_df, course_cfg['name'], str(date.today()))
    report_path.write_text(html, encoding='utf-8')
    print(f"Usage report:  {report_path}")

    return features


def _course_dirs(config: dict, course_key: str) -> tuple[Path, Path]:
    """Return (output_dir, federation_dir) for this course, with per-course override support."""
    course_cfg = config['courses'][course_key]
    out_dir = Path(course_cfg.get('output_dir') or config['data']['output_dir'])
    fed_dir = Path(course_cfg.get('federation_dir') or config['data']['federation_dir'])
    out_dir.mkdir(parents=True, exist_ok=True)
    fed_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, fed_dir


def _export_federation(features: pd.DataFrame, config: dict, course_key: str) -> None:
    """
    Write the CSV that teachers receive:
    - email replaced by anonymous ID (sha256) if anonymize_ids=True
    - target column excluded (teacher supplies that)
    - _z and _pct duplicates excluded (keep originals only, teachers prefer raw)
    """
    _, fed_dir = _course_dirs(config, course_key)

    # Drop only normalisation duplicates: columns named {col}_z or {col}_pct
    # where the base column also exists.  Raw features like lecture_coverage_pct
    # and active_learning_level must be kept.
    base_cols = set(features.columns)
    norm_dupes = [
        c for c in features.columns
        if (c.endswith('_z') and c[:-2] in base_cols)
        or (c.endswith('_pct') and c[:-4] in base_cols)
    ]
    drop_cols = norm_dupes + ['target']
    export = features.drop(columns=[c for c in drop_cols if c in features.columns])

    if config.get('federation', {}).get('anonymize_ids', True):
        export.index = export.index.map(
            lambda e: 'uid_' + hashlib.sha256(e.encode()).hexdigest()[:12]
        )
        export.index.name = 'student_id'
    else:
        export.index.name = 'email'

    out_path = fed_dir / f'student_features_{course_key}_federation.csv'
    export.to_csv(out_path)
    print(f"Federation CSV: {out_path}  (anonymized={config.get('federation',{}).get('anonymize_ids',True)})")
    return out_path


def print_summary(features: pd.DataFrame) -> None:
    print(f"\n{'─'*60}")
    print("SUMMARY")
    print(f"{'─'*60}")
    print(f"Students: {len(features)}")
    print(f"\nActive Learning Score:")
    print(features['active_learning_score'].describe().round(1).to_string())
    print(f"\nALS levels:\n{features['active_learning_level'].value_counts().to_string()}")
    if 'target' in features.columns:
        print(f"\nTarget (synthetic):")
        print(features['target'].describe().round(1).to_string())
    print(f"\nTop features by ALS correlation:")
    numeric_cols = features.select_dtypes('number').columns
    if 'active_learning_score' in numeric_cols:
        corr = features[numeric_cols].corr()['active_learning_score'].drop('active_learning_score')
        corr = corr[~corr.index.str.endswith(('_z', '_pct'))]
        print(corr.abs().sort_values(ascending=False).head(8).round(3).to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--course', default=None, help="Course key from config (default: all)")
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--target', default=None,
                        help="Override target type: synthetic_random | synthetic_formula | final_grade")
    parser.add_argument('--cutoff', default=None,
                        help="'none' forces a single all-activity window (baseline, ignores moed dates)")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.target:
        config['target']['type'] = args.target
    if args.cutoff:
        config['_cutoff_override'] = args.cutoff

    course_keys = [args.course] if args.course else list(config['courses'].keys())

    for key in course_keys:
        if key not in config['courses']:
            print(f"Unknown course key: {key!r}. Available: {list(config['courses'].keys())}")
            sys.exit(1)
        features = run_course(config, key)
        print_summary(features)


if __name__ == '__main__':
    main()
