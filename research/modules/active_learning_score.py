"""
ActiveLearningScore: computes a 0-100 score reflecting meaningful engagement.

Components (each normalized 0-100 via within-course percentile rank):
  - active_weeks_ratio    → consistency
  - total_active_events   → quantity of active interactions
  - feature_diversity_count → breadth of platform usage
  - meaningful_sessions_ratio → depth/quality of sessions

Percentile rank is used so the score is always relative to the course cohort
and requires no absolute calibration per course.
"""
import pandas as pd


def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method='average') * 100


def compute(features: pd.DataFrame, weights: dict = None) -> pd.Series:
    """
    Args:
        features: student feature DataFrame (one row per student)
        weights: optional override for component weights

    Returns:
        Series 'active_learning_score' (0-100), indexed like features
    """
    if weights is None:
        weights = {
            'active_weeks_ratio': 0.35,
            'active_events': 0.25,
            'feature_diversity': 0.20,
            'meaningful_sessions': 0.20,
        }

    score = (
        weights['active_weeks_ratio'] * _pct_rank(features['active_weeks_ratio'])
        + weights['active_events'] * _pct_rank(features['total_active_events'])
        + weights['feature_diversity'] * _pct_rank(features['feature_diversity_count'])
        + weights['meaningful_sessions'] * _pct_rank(features['meaningful_sessions_ratio'])
    )

    return score.clip(0, 100).rename('active_learning_score')


def classify(score: pd.Series) -> pd.Series:
    """Map continuous score to Low / Medium / High label."""
    return pd.cut(
        score,
        bins=[-1, 30, 60, 101],
        labels=['Low', 'Medium', 'High'],
    ).rename('active_learning_level')
