"""
Normalization: within-course z-score and percentile rank for feature columns.
"""
import pandas as pd

NORMALIZE_FEATURES = [
    'total_events', 'total_active_events', 'active_days', 'active_weeks',
    'active_weeks_ratio', 'longest_streak_weeks', 'total_time_minutes',
    'avg_session_duration_minutes', 'sessions_count', 'meaningful_sessions_count',
    'meaningful_sessions_ratio', 'unique_lectures_viewed', 'lecture_coverage_pct',
    'feature_diversity_count', 'concept_selects', 'eval_avg_score', 'eval_submission_rate',
    'quiz_avg_score', 'quiz_submission_rate', 'active_learning_score',
]


def add_zscore(df: pd.DataFrame, cols: list = None) -> pd.DataFrame:
    cols = [c for c in (cols or NORMALIZE_FEATURES) if c in df.columns]
    for col in cols:
        std = df[col].std()
        df[f'{col}_z'] = ((df[col] - df[col].mean()) / std).round(3) if std > 0 else 0.0
    return df


def add_percentile(df: pd.DataFrame, cols: list = None) -> pd.DataFrame:
    cols = [c for c in (cols or NORMALIZE_FEATURES) if c in df.columns]
    for col in cols:
        df[f'{col}_pct'] = (df[col].rank(pct=True) * 100).round(1)
    return df
