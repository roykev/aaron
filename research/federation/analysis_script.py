#!/usr/bin/env python3
"""
Aaron Owl — Local Analysis Script (Teacher / Institution)
==========================================================
Run this script on your own machine. Your grade data never leaves.

Usage:
    python analysis_script.py \
        --features student_features_math_business.csv \
        --grades   my_grades.csv \
        --out      results/

Input files:
    features CSV  — provided by Aaron Owl (usage + platform behavior)
    grades CSV    — you create this: two columns: email (or student_id), final_grade

Output (in --out directory, no individual grades included):
    correlation_report.csv   — Pearson & Spearman per feature vs. final_grade
    regression_summary.txt   — linear regression coefficients + R²
    feature_importance.csv   — Random Forest feature importances
    analysis_report.html     — human-readable summary

This script requires only: pandas, numpy, scikit-learn, scipy
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("Warning: scikit-learn not installed. Regression and RF outputs will be skipped.")


# ── helpers ───────────────────────────────────────────────────────────────────

def load_and_merge(features_path: str, grades_path: str) -> pd.DataFrame:
    features = pd.read_csv(features_path)
    grades = pd.read_csv(grades_path)
    grades.columns = [c.strip().lower() for c in grades.columns]

    # Accept 'email' or 'student_id' as join key in grades file
    join_col = 'email' if 'email' in grades.columns else 'student_id'
    if join_col not in grades.columns:
        raise ValueError("Grades CSV must have an 'email' or 'student_id' column")
    if 'final_grade' not in grades.columns:
        raise ValueError("Grades CSV must have a 'final_grade' column")

    # Normalize email casing
    if 'email' in features.columns:
        features['email'] = features['email'].str.lower().str.strip()
    if join_col == 'email':
        grades['email'] = grades['email'].str.lower().str.strip()

    merged = features.merge(grades[[join_col, 'final_grade']], on=join_col, how='inner')
    print(f"Matched {len(merged)} students (features: {len(features)}, grades: {len(grades)})")
    return merged


def select_numeric_features(df: pd.DataFrame, target_col: str = 'final_grade') -> tuple:
    exclude = {'email', 'student_id', 'course_id', target_col,
               'active_learning_level'}  # categorical
    # Drop _z and _pct duplicates — keep originals only
    exclude |= {c for c in df.columns if c.endswith('_z') or c.endswith('_pct')}
    # Drop binary feature flags — keep diversity count instead
    exclude |= {c for c in df.columns if c.startswith('used_')}

    feat_cols = [
        c for c in df.columns
        if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
    ]
    X = df[feat_cols].copy()
    y = df[target_col].copy()

    # Drop rows where target is missing
    valid = y.notna()
    X, y = X[valid], y[valid]

    # Fill remaining NaNs with column median
    X = X.fillna(X.median())

    # Drop constant columns — they carry no signal and cause warnings
    constant = [c for c in X.columns if X[c].nunique() <= 1]
    if constant:
        print(f"Dropping {len(constant)} constant column(s): {constant}")
        X = X.drop(columns=constant)

    feat_cols = list(X.columns)
    return X, y, feat_cols


# ── analysis functions ────────────────────────────────────────────────────────

def correlation_report(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    rows = []
    for col in X.columns:
        valid = X[col].notna() & y.notna()
        if valid.sum() < 5:
            continue
        x_vals, y_vals = X[col][valid], y[valid]
        pearson_r, pearson_p = stats.pearsonr(x_vals, y_vals)
        spearman_r, spearman_p = stats.spearmanr(x_vals, y_vals)
        rows.append({
            'feature': col,
            'pearson_r': round(pearson_r, 4),
            'pearson_p': round(pearson_p, 4),
            'spearman_r': round(spearman_r, 4),
            'spearman_p': round(spearman_p, 4),
            'n': int(valid.sum()),
        })
    return pd.DataFrame(rows).sort_values('pearson_r', key=abs, ascending=False)


def regression_summary(X: pd.DataFrame, y: pd.Series) -> dict:
    if not HAS_SKLEARN:
        return {}
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    cv_scores = cross_val_score(model, X, y, cv=min(5, len(y)), scoring='r2')
    model.fit(X, y)
    ridge = model.named_steps['ridgecv'] if 'ridgecv' in model.named_steps else model.named_steps['ridge']
    scaler = model.named_steps['standardscaler']
    coefs = pd.Series(ridge.coef_, index=X.columns).sort_values(key=abs, ascending=False)
    return {
        'cv_r2_mean': round(float(cv_scores.mean()), 4),
        'cv_r2_std': round(float(cv_scores.std()), 4),
        'n_students': len(y),
        'n_features': len(X.columns),
        'coefficients': coefs.round(4).to_dict(),
        'intercept': round(float(ridge.intercept_), 4),
    }


def feature_importance(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    if not HAS_SKLEARN:
        return pd.DataFrame()
    rf = RandomForestRegressor(n_estimators=200, random_state=42)
    rf.fit(X, y)
    return pd.DataFrame({
        'feature': X.columns,
        'importance': rf.feature_importances_.round(4),
    }).sort_values('importance', ascending=False).reset_index(drop=True)


# ── ALS tier profiling ────────────────────────────────────────────────────────

def als_tier_profile(df: pd.DataFrame, target_col: str = 'final_grade') -> pd.DataFrame:
    """
    Mean / std / median / n of final_grade per ALS level, plus z-scored mean
    (grade z-scored within the course so it's scale-independent for cross-course pooling).
    Rows with fewer than 3 students in a tier are suppressed (privacy floor).
    """
    if 'active_learning_level' not in df.columns:
        return pd.DataFrame()
    valid = df[[target_col, 'active_learning_level']].dropna()
    if valid.empty:
        return pd.DataFrame()

    grade_mean = valid[target_col].mean()
    grade_std  = valid[target_col].std()
    valid = valid.copy()
    valid['grade_z'] = (valid[target_col] - grade_mean) / grade_std if grade_std > 0 else 0.0

    order = ['Low', 'Medium', 'High']
    rows = []
    for level in order:
        grp = valid[valid['active_learning_level'] == level][target_col]
        grp_z = valid[valid['active_learning_level'] == level]['grade_z']
        if len(grp) < 3:
            continue
        rows.append({
            'als_level':     level,
            'n':             int(len(grp)),
            'mean_grade':    round(float(grp.mean()), 2),
            'std_grade':     round(float(grp.std()), 2),
            'median_grade':  round(float(grp.median()), 2),
            'mean_grade_z':  round(float(grp_z.mean()), 3),
        })

    tier_df = pd.DataFrame(rows)
    # Cohen's d: High vs Low
    low  = valid[valid['active_learning_level'] == 'Low'][target_col]
    high = valid[valid['active_learning_level'] == 'High'][target_col]
    if len(low) >= 3 and len(high) >= 3:
        pooled_sd = np.sqrt((low.var() + high.var()) / 2)
        cohens_d  = round((high.mean() - low.mean()) / pooled_sd, 3) if pooled_sd > 0 else np.nan
        tier_df['cohens_d_vs_low'] = [np.nan if r.als_level == 'Low' else cohens_d
                                       if r.als_level == 'High' else np.nan
                                       for r in tier_df.itertuples()]
    return tier_df


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(corr_df: pd.DataFrame, reg: dict, fi_df: pd.DataFrame,
                n_students: int, target_stats: dict,
                tier_df: pd.DataFrame = None) -> str:
    top_corr = corr_df.head(10)

    corr_rows = ''.join(
        f'<tr><td>{r.feature}</td>'
        f'<td style="color:{"green" if r.pearson_r>0 else "red"}">{r.pearson_r:+.3f}</td>'
        f'<td>{"<b>✓</b>" if r.pearson_p < 0.05 else "–"}</td>'
        f'<td style="color:{"green" if r.spearman_r>0 else "red"}">{r.spearman_r:+.3f}</td>'
        f'<td>{r.n}</td></tr>'
        for r in top_corr.itertuples()
    )

    fi_rows = ''
    if not fi_df.empty:
        fi_rows = ''.join(
            f'<tr><td>{r.feature}</td>'
            f'<td><div style="background:#4caf50;width:{r.importance*400:.0f}px;height:12px;display:inline-block"></div> {r.importance:.4f}</td></tr>'
            for r in fi_df.head(10).itertuples()
        )

    cv_block = ''
    if reg:
        cv_block = f"""
        <h2>Linear Model (Ridge, 5-fold CV)</h2>
        <p>Cross-validated R²: <b>{reg['cv_r2_mean']:.3f}</b> ± {reg['cv_r2_std']:.3f}
        &nbsp;&nbsp;(n={reg['n_students']})</p>
        """

    # ALS tier table
    tier_block = ''
    if tier_df is not None and not tier_df.empty:
        COLORS = {'Low': '#ef9a9a', 'Medium': '#fff176', 'High': '#a5d6a7'}
        tier_rows = ''.join(
            f'<tr>'
            f'<td><span style="background:{COLORS.get(r.als_level,"#eee")};'
            f'padding:2px 10px;border-radius:12px;font-weight:600">{r.als_level}</span></td>'
            f'<td>{r.n}</td>'
            f'<td><b>{r.mean_grade:.1f}</b></td>'
            f'<td>{r.std_grade:.1f}</td>'
            f'<td>{r.median_grade:.1f}</td>'
            f'<td style="color:#5c6bc0">{r.mean_grade_z:+.2f}σ</td>'
            f'<td>{"–" if str(getattr(r,"cohens_d_vs_low","")) in ("nan","") else f"<b>{r.cohens_d_vs_low:.2f}</b>"}</td>'
            f'</tr>'
            for r in tier_df.itertuples()
        )
        tier_block = f"""
        <h2>Grade by Active Learning Level</h2>
        <table>
          <tr><th>ALS Level</th><th>N</th><th>Mean grade</th><th>±SD</th><th>Median</th>
              <th>Mean (z-scored)</th><th>Cohen's d vs Low</th></tr>
          {tier_rows}
        </table>
        <p style="color:#888;font-size:0.85em">
          z-scored mean: grade expressed in within-course standard deviations (scale-independent).
          Cohen's d: effect size of High vs Low ALS group on final grade.
        </p>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Aaron Owl — Learning Analytics Report</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;color:#333}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}
th{{background:#f5f5f5}}tr:hover{{background:#fafafa}}</style></head><body>
<h1>Aaron Owl Learning Analytics</h1>
<p>Students analysed: <b>{n_students}</b> &nbsp;|&nbsp;
Target mean: <b>{target_stats['mean']:.1f}</b> &nbsp;
std: <b>{target_stats['std']:.1f}</b> &nbsp;
range: [{target_stats['min']:.0f}–{target_stats['max']:.0f}]</p>
<p style="color:#888;font-size:0.85em">
This report contains only aggregated statistics. No individual student grades are included.</p>
{tier_block}
<h2>Top Feature Correlations with Final Grade</h2>
<table><tr><th>Feature</th><th>Pearson r</th><th>p&lt;0.05</th><th>Spearman r</th><th>N</th></tr>
{corr_rows}</table>
{cv_block}
{'<h2>Random Forest Feature Importance</h2><table><tr><th>Feature</th><th>Importance</th></tr>' + fi_rows + '</table>' if fi_rows else ''}
<hr><p style="font-size:0.8em;color:#aaa">Generated by Aaron Owl analytics — no raw grades included.</p>
</body></html>"""


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aaron Owl local analysis script")
    parser.add_argument('--features', required=True, help="Path to student_features CSV")
    parser.add_argument('--grades', required=True, help="Path to grades CSV (email, final_grade)")
    parser.add_argument('--out', default='./results', help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    df = load_and_merge(args.features, args.grades)
    X, y, feat_cols = select_numeric_features(df)
    print(f"Running analysis on {len(X)} students × {len(feat_cols)} features")

    target_stats = {'mean': y.mean(), 'std': y.std(), 'min': y.min(), 'max': y.max()}

    print("Computing correlations...")
    corr_df = correlation_report(X, y)
    corr_df.to_csv(out_dir / 'correlation_report.csv', index=False)

    print("Fitting regression model...")
    reg = regression_summary(X, y)
    if reg:
        with open(out_dir / 'regression_summary.txt', 'w') as f:
            f.write(f"Cross-validated R²: {reg['cv_r2_mean']:.4f} ± {reg['cv_r2_std']:.4f}\n")
            f.write(f"N students: {reg['n_students']}, N features: {reg['n_features']}\n\n")
            f.write("Coefficients (standardized):\n")
            for feat, coef in reg['coefficients'].items():
                f.write(f"  {feat:<45} {coef:+.4f}\n")

    print("Computing feature importances...")
    fi_df = feature_importance(X, y)
    if not fi_df.empty:
        fi_df.to_csv(out_dir / 'feature_importance.csv', index=False)

    print("Computing ALS tier profile...")
    tier_df = als_tier_profile(df)
    if not tier_df.empty:
        tier_df.to_csv(out_dir / 'als_tier_profile.csv', index=False)

    print("Generating HTML report...")
    html = render_html(corr_df, reg, fi_df, len(y), target_stats, tier_df)
    (out_dir / 'analysis_report.html').write_text(html, encoding='utf-8')

    print(f"\nDone. Results saved to {out_dir}/")
    print(f"  correlation_report.csv   — {len(corr_df)} features")
    if reg:
        print(f"  regression_summary.txt   — CV R²={reg['cv_r2_mean']:.3f}")
    if not fi_df.empty:
        print(f"  feature_importance.csv   — top: {fi_df.iloc[0]['feature']} ({fi_df.iloc[0]['importance']:.3f})")
    if not tier_df.empty:
        high = tier_df[tier_df['als_level'] == 'High']
        low  = tier_df[tier_df['als_level'] == 'Low']
        if not high.empty and not low.empty:
            diff = high.iloc[0]['mean_grade'] - low.iloc[0]['mean_grade']
            print(f"  als_tier_profile.csv     — High vs Low grade gap: {diff:+.1f} pts")
    print(f"  analysis_report.html     — open in browser")


if __name__ == '__main__':
    main()
