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


def run_course(config: dict, course_key: str) -> pd.DataFrame:
    course_cfg = config['courses'][course_key]
    course_id = course_cfg['course_id']
    print(f"\n{'='*60}")
    print(f"Course: {course_cfg['name']} ({course_key})")
    print(f"{'='*60}")

    # 1. Load events
    loader = EventLoader(config)
    events = loader.load(course_id)

    # 2. Resolve identities
    resolver = IdentityResolver(config)
    events = resolver.resolve(events)

    # 3. Build sessions
    session_builder = SessionBuilder(config)
    sessions = session_builder.build(events)

    # 4. Load academic data (CSV or Excel sheet)
    eval_df = load_academic_csv(course_cfg.get('eval_csv', ''), sheet=course_cfg.get('eval_sheet'))
    quiz_df  = load_academic_csv(course_cfg.get('quiz_csv', ''),  sheet=course_cfg.get('quiz_sheet'))

    # 5. Build student feature table
    feature_builder = StudentFeatureBuilder(config, course_key)
    features = feature_builder.build(events, sessions, eval_df, quiz_df)

    # 6. Active Learning Score
    als_weights = config.get('active_learning_score', {}).get('weights')
    features['active_learning_score'] = als.compute(features, als_weights)
    features['active_learning_level'] = als.classify(features['active_learning_score'])

    # 7. Normalize
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
    args = parser.parse_args()

    config = load_config(args.config)

    if args.target:
        config['target']['type'] = args.target

    course_keys = [args.course] if args.course else list(config['courses'].keys())

    for key in course_keys:
        if key not in config['courses']:
            print(f"Unknown course key: {key!r}. Available: {list(config['courses'].keys())}")
            sys.exit(1)
        features = run_course(config, key)
        print_summary(features)


if __name__ == '__main__':
    main()
