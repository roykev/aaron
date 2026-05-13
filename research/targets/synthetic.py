"""
Synthetic targets for pipeline development and sanity testing.

SyntheticRandom:
  Pure random uniform values. Use to verify the model learns nothing
  (expected correlation ≈ 0).

SyntheticFormula:
  Weighted combination of real features + Gaussian noise.
  Produces a plausible grade-like distribution (mean ~65, std ~15).
  Useful for end-to-end pipeline testing and federation script validation.
  The noise ensures the model can't trivially recover the formula,
  while the signal ensures correlation analysis returns non-zero values.
"""
import numpy as np
import pandas as pd

from .base import TargetStrategy


def _norm(s: pd.Series) -> pd.Series:
    """Min-max normalize a series to 0–100; return 50 if constant."""
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(50.0, index=s.index)
    return (s - lo) / (hi - lo) * 100


class SyntheticRandom(TargetStrategy):
    name = "synthetic_random"

    def __init__(self, seed: int = 42):
        self.seed = seed

    def build(self, features: pd.DataFrame) -> pd.Series:
        rng = np.random.default_rng(self.seed)
        return pd.Series(
            rng.uniform(0, 100, size=len(features)),
            index=features.index,
            name='target',
        )

    def description(self) -> str:
        return "Random uniform [0, 100] — sanity check only"


class SyntheticFormula(TargetStrategy):
    """
    target ≈ 0.35 * eval_avg_score
           + 0.25 * active_weeks_ratio
           + 0.20 * meaningful_sessions_ratio
           + 0.10 * quiz_avg_score
           + 0.10 * feature_diversity_count
           + N(0, noise_std)
    All components normalized to 0-100 before weighting.
    Final value clipped to [0, 100].
    """
    name = "synthetic_formula"

    def __init__(self, noise_std: float = 10.0, seed: int = 42):
        self.noise_std = noise_std
        self.seed = seed

    def build(self, features: pd.DataFrame) -> pd.Series:
        rng = np.random.default_rng(self.seed)

        def safe(col):
            return _norm(features[col].fillna(features[col].median()))

        score = (
            0.35 * safe('eval_avg_score')
            + 0.25 * safe('active_weeks_ratio')
            + 0.20 * safe('meaningful_sessions_ratio')
            + 0.10 * safe('quiz_avg_score')
            + 0.10 * safe('feature_diversity_count')
        )
        noise = rng.normal(0, self.noise_std, size=len(features))
        return pd.Series(
            np.clip(score.values + noise, 0, 100),
            index=features.index,
            name='target',
        ).round(1)

    def description(self) -> str:
        return f"Formula (eval 35%, activity 25%, sessions 20%, quiz 10%, diversity 10%) + N(0,{self.noise_std})"


def create(config: dict) -> TargetStrategy:
    """Factory: build the target strategy from config."""
    target_cfg = config.get('target', {})
    kind = target_cfg.get('type', 'synthetic_formula')
    params = target_cfg.get('params', {})

    if kind == 'synthetic_random':
        return SyntheticRandom(seed=params.get('seed', 42))
    if kind == 'synthetic_formula':
        return SyntheticFormula(
            noise_std=params.get('noise_std', 10.0),
            seed=params.get('seed', 42),
        )
    if kind == 'final_grade':
        from .final_grade import FinalGrade
        return FinalGrade(grades_csv=params['grades_csv'])
    raise ValueError(f"Unknown target type: {kind!r}")
