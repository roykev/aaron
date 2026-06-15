#!/usr/bin/env python3
"""
Aaron Owl — Federated Meta-Analysis
=====================================
Combines per-teacher analysis results (correlations, importances, regression R²)
across multiple courses WITHOUT ever seeing individual student grades.

Each teacher runs analysis_script.py locally and shares only the aggregated outputs:
    correlation_report.csv
    feature_importance.csv
    regression_summary.txt

This script applies:
    - Fisher z-transform for pooling Pearson/Spearman correlations (weighted by n-3)
    - N-weighted average for feature importances
    - N-weighted average R² with per-course breakdown

Usage:
    python meta_analysis.py \\
        --courses "Psy:/path/to/psy/results,Math:/path/to/math/results" \\
        --out     /path/to/combined/

Or using a YAML manifest:
    python meta_analysis.py --manifest courses_manifest.yaml --out /path/to/combined/
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ── loaders ───────────────────────────────────────────────────────────────────

def load_course_results(name: str, results_dir: str) -> dict:
    p = Path(results_dir)
    result = {'name': name, 'n': None, 'r2': None, 'r2_std': None,
              'corr': None, 'importance': None, 'coefs': None, 'tier': None}

    corr_path = p / 'correlation_report.csv'
    if corr_path.exists():
        result['corr'] = pd.read_csv(corr_path)
        # n is consistent across features for a given course
        result['n'] = int(result['corr']['n'].iloc[0]) if not result['corr'].empty else None

    fi_path = p / 'feature_importance.csv'
    if fi_path.exists():
        result['importance'] = pd.read_csv(fi_path)

    tier_path = p / 'als_tier_profile.csv'
    if tier_path.exists():
        result['tier'] = pd.read_csv(tier_path)

    reg_path = p / 'regression_summary.txt'
    if reg_path.exists():
        txt = reg_path.read_text()
        for line in txt.splitlines():
            if line.startswith('Cross-validated R²:'):
                parts = line.split()
                result['r2'] = float(parts[2])
                result['r2_std'] = float(parts[4])
            if line.startswith('N students:'):
                parts = line.replace(',', '').split()
                result['n'] = int(parts[2])
        # Parse coefficients
        coef_lines = []
        in_coef = False
        for line in txt.splitlines():
            if line.strip().startswith('Coefficients'):
                in_coef = True
                continue
            if in_coef and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    coef_lines.append({'feature': parts[0], 'coef': float(parts[1])})
        if coef_lines:
            result['coefs'] = pd.DataFrame(coef_lines)

    return result


# ── Fisher z-transform pooling ────────────────────────────────────────────────

def fisher_pool(rs: list[float], ns: list[int]) -> tuple[float, float, float]:
    """Pool correlation coefficients via Fisher z. Returns (r_pooled, ci_lower, ci_upper)."""
    zs = np.arctanh(np.clip(rs, -0.9999, 0.9999))
    ws = [max(n - 3, 1) for n in ns]
    z_bar = np.average(zs, weights=ws)
    se = 1.0 / np.sqrt(sum(ws))
    r_pool = float(np.tanh(z_bar))
    ci_lo = float(np.tanh(z_bar - 1.96 * se))
    ci_hi = float(np.tanh(z_bar + 1.96 * se))
    return r_pool, ci_lo, ci_hi


# ── Cochran's Q heterogeneity ─────────────────────────────────────────────────

def cochran_q(rs: list[float], ns: list[int]) -> tuple[float, int, float, float]:
    """
    Cochran's Q test for between-course heterogeneity of a correlation, computed
    on Fisher-z transformed r's with weights w_i = n_i - 3 (same weighting the
    fixed-effect pool uses).

    Q   = Σ w_i (z_i - z̄)²      ~ χ²(k-1) under the null "all courses share one true r"
    I²  = max(0, (Q - df) / Q) · 100   — % of variance due to real between-course
                                          difference rather than sampling error.

    Returns (Q, df, p_value, I2_percent). Needs ≥2 courses; else NaNs.
    """
    if len(rs) < 2:
        return (np.nan, 0, np.nan, np.nan)
    zs = np.arctanh(np.clip(rs, -0.9999, 0.9999))
    ws = np.array([max(n - 3, 1) for n in ns], dtype=float)
    z_bar = np.average(zs, weights=ws)
    Q = float(np.sum(ws * (zs - z_bar) ** 2))
    df = len(rs) - 1
    p = float(stats.chi2.sf(Q, df)) if df > 0 else np.nan
    I2 = float(max(0.0, (Q - df) / Q) * 100.0) if Q > 0 else 0.0
    return (Q, df, p, I2)


def het_flag(n_courses: int, p: float, I2: float) -> str:
    """Classify a feature's cross-course consistency."""
    if n_courses < 2:
        return 'single'
    if p is not None and not np.isnan(p) and p < 0.05:
        return 'disagree'        # significant heterogeneity — courses genuinely differ
    if I2 >= 50.0:
        return 'substantial'     # large I² but not significant (often few courses)
    return 'consistent'


# ── combined correlation ───────────────────────────────────────────────────────

def combined_correlations(courses: list[dict]) -> pd.DataFrame:
    """Pool Pearson r across courses per feature."""
    # Collect per-feature data
    feature_data: dict[str, list] = {}
    for c in courses:
        if c['corr'] is None or c['n'] is None:
            continue
        for _, row in c['corr'].iterrows():
            feat = row['feature']
            if feat not in feature_data:
                feature_data[feat] = []
            feature_data[feat].append({
                'r': row['pearson_r'],
                'sr': row['spearman_r'],
                'n': int(row['n']),
                'course': c['name'],
            })

    rows = []
    for feat, entries in feature_data.items():
        rs = [e['r'] for e in entries]
        srs = [e['sr'] for e in entries]
        ns = [e['n'] for e in entries]
        r_pool, ci_lo, ci_hi = fisher_pool(rs, ns)
        sr_pool, _, _ = fisher_pool(srs, ns)
        Q, df_q, p_q, I2 = cochran_q(rs, ns)
        flag = het_flag(len(entries), p_q, I2)
        per_course_r = '; '.join(f"{e['course']}: {e['r']:+.2f}" for e in entries)
        rows.append({
            'feature': feat,
            'pearson_r_pooled': round(r_pool, 4),
            'pearson_ci_lo': round(ci_lo, 4),
            'pearson_ci_hi': round(ci_hi, 4),
            'spearman_r_pooled': round(sr_pool, 4),
            'n_total': sum(ns),
            'n_courses': len(entries),
            'het_Q': round(Q, 3) if not np.isnan(Q) else np.nan,
            'het_df': df_q,
            'het_p': round(p_q, 4) if not np.isnan(p_q) else np.nan,
            'het_I2': round(I2, 1) if not np.isnan(I2) else np.nan,
            'het_flag': flag,
            'per_course_r': per_course_r,
            'courses': ', '.join(e['course'] for e in entries),
        })

    df = pd.DataFrame(rows).sort_values('pearson_r_pooled', key=abs, ascending=False)
    return df.reset_index(drop=True)


# ── combined feature importance ───────────────────────────────────────────────

def combined_importance(courses: list[dict]) -> pd.DataFrame:
    """N-weighted average feature importance across courses."""
    feature_data: dict[str, list] = {}
    for c in courses:
        if c['importance'] is None or c['n'] is None:
            continue
        for _, row in c['importance'].iterrows():
            feat = row['feature']
            if feat not in feature_data:
                feature_data[feat] = []
            feature_data[feat].append({'imp': row['importance'], 'n': c['n'], 'course': c['name']})

    rows = []
    for feat, entries in feature_data.items():
        imps = np.array([e['imp'] for e in entries])
        ns = np.array([e['n'] for e in entries])
        w_avg = float(np.average(imps, weights=ns))
        rows.append({
            'feature': feat,
            'importance_pooled': round(w_avg, 4),
            'n_courses': len(entries),
            'n_total': int(ns.sum()),
        })

    df = pd.DataFrame(rows).sort_values('importance_pooled', ascending=False)
    return df.reset_index(drop=True)


# ── ALS tier pooling ─────────────────────────────────────────────────────────

def combined_tier_profile(courses: list[dict]) -> pd.DataFrame:
    """
    Pool ALS tier grade stats across courses.
    Uses N-weighted average of within-course z-scored means (scale-independent).
    Pooled absolute mean is suppressed — grades differ across courses by design.
    """
    LEVELS = ['Low', 'Medium', 'High']
    level_data: dict[str, list] = {lv: [] for lv in LEVELS}

    for c in courses:
        if c['tier'] is None or c['tier'].empty:
            continue
        for _, row in c['tier'].iterrows():
            lv = row['als_level']
            if lv not in level_data:
                continue
            level_data[lv].append({
                'course': c['name'],
                'n': int(row['n']),
                'mean_grade_z': float(row['mean_grade_z']),
                'mean_grade': float(row['mean_grade']),
                'std_grade': float(row['std_grade']),
                'cohens_d': float(row['cohens_d_vs_low']) if 'cohens_d_vs_low' in row and not pd.isna(row.get('cohens_d_vs_low', np.nan)) else np.nan,
            })

    rows = []
    for lv in LEVELS:
        entries = level_data[lv]
        if not entries:
            continue
        ns = np.array([e['n'] for e in entries])
        zs = np.array([e['mean_grade_z'] for e in entries])
        pooled_z = float(np.average(zs, weights=ns))

        # Per-course detail string
        per_course = '; '.join(
            f"{e['course']}: {e['mean_grade']:.1f} (n={e['n']})"
            for e in entries
        )

        d_vals = [e['cohens_d'] for e in entries if not np.isnan(e['cohens_d'])]
        cohens_d_pool = float(np.mean(d_vals)) if d_vals else np.nan

        rows.append({
            'als_level':       lv,
            'n_total':         int(ns.sum()),
            'n_courses':       len(entries),
            'mean_grade_z_pooled': round(pooled_z, 3),
            'cohens_d_pooled': round(cohens_d_pool, 3) if not np.isnan(cohens_d_pool) else np.nan,
            'per_course':      per_course,
        })

    return pd.DataFrame(rows)


# ── R² summary ────────────────────────────────────────────────────────────────

def r2_summary(courses: list[dict]) -> dict:
    valid = [c for c in courses if c['r2'] is not None and c['n'] is not None]
    if not valid:
        return {}
    ns = np.array([c['n'] for c in valid])
    r2s = np.array([c['r2'] for c in valid])
    weighted_r2 = float(np.average(r2s, weights=ns))
    return {
        'per_course': {c['name']: {'r2': c['r2'], 'r2_std': c['r2_std'], 'n': c['n']} for c in valid},
        'n_weighted_r2': round(weighted_r2, 4),
        'n_total': int(ns.sum()),
    }


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(corr_df: pd.DataFrame, fi_df: pd.DataFrame,
                r2: dict, course_names: list[str],
                tier_df: pd.DataFrame = None) -> str:

    # Per-course R² table
    r2_rows = ''
    if r2.get('per_course'):
        for name, v in r2['per_course'].items():
            r2_rows += f'<tr><td>{name}</td><td>{v["n"]}</td><td><b>{v["r2"]:.3f}</b></td><td>±{v["r2_std"]:.3f}</td></tr>'

    # ALS tier block
    tier_block = ''
    if tier_df is not None and not tier_df.empty:
        COLORS = {'Low': '#ef9a9a', 'Medium': '#fff176', 'High': '#a5d6a7'}
        # Bar scale: z ranges from ~-1 to +1 → map to 0-200px
        z_vals = tier_df['mean_grade_z_pooled'].values
        z_min, z_max = z_vals.min(), z_vals.max()
        def bar_w(z):
            return int((z - z_min) / max(z_max - z_min, 0.01) * 180 + 20)

        tier_rows = ''.join(
            f'<tr>'
            f'<td><span style="background:{COLORS.get(r.als_level,"#eee")};'
            f'padding:2px 10px;border-radius:12px;font-weight:600">{r.als_level}</span></td>'
            f'<td>{r.n_total} ({r.n_courses}/{len(course_names)} courses)</td>'
            f'<td><div style="background:#5c6bc0;width:{bar_w(r.mean_grade_z_pooled)}px;height:14px;'
            f'display:inline-block;border-radius:2px;vertical-align:middle"></div> '
            f'<b>{r.mean_grade_z_pooled:+.2f}σ</b></td>'
            f'<td>{"–" if pd.isna(r.cohens_d_pooled) else f"<b>{r.cohens_d_pooled:.2f}</b>"}</td>'
            f'<td style="color:#888;font-size:0.82em">{r.per_course}</td>'
            f'</tr>'
            for r in tier_df.itertuples()
        )
        tier_block = f"""
        <h2>Grade by Active Learning Level (Pooled)</h2>
        <table>
          <tr><th>ALS Level</th><th>N (students)</th><th>Mean grade (z-scored, pooled)</th>
              <th>Cohen's d vs Low</th><th>Per-course absolute means</th></tr>
          {tier_rows}
        </table>
        <p style="color:#888;font-size:0.85em">
          Grades are z-scored <em>within each course</em> before pooling, so absolute grade-scale
          differences between courses don't distort the comparison.
          Cohen's d: effect size of High vs Low ALS on final grade (≥0.8 = large effect).
        </p>"""

    # Heterogeneity badge styling
    FLAG_STYLE = {
        'disagree':    ('#c62828', 'courses disagree'),
        'substantial': ('#ef6c00', 'substantial'),
        'consistent':  ('#2e7d32', 'consistent'),
        'single':      ('#9e9e9e', '1 course'),
    }

    def het_badge(flag, I2):
        color, label = FLAG_STYLE.get(flag, ('#9e9e9e', flag))
        i2_txt = '' if (I2 is None or pd.isna(I2)) else f' I²={I2:.0f}%'
        return (f'<span style="background:{color};color:#fff;padding:1px 8px;'
                f'border-radius:10px;font-size:0.8em;white-space:nowrap">{label}{i2_txt}</span>')

    # Top correlations
    top_corr = corr_df.head(12)
    corr_rows = ''.join(
        f'<tr><td>{r.feature}</td>'
        f'<td style="color:{"#2e7d32" if r.pearson_r_pooled>0 else "#c62828"}">{r.pearson_r_pooled:+.3f}</td>'
        f'<td>[{r.pearson_ci_lo:+.3f}, {r.pearson_ci_hi:+.3f}]</td>'
        f'<td style="color:{"#2e7d32" if r.spearman_r_pooled>0 else "#c62828"}">{r.spearman_r_pooled:+.3f}</td>'
        f'<td style="color:#666">{r.n_total}</td>'
        f'<td>{het_badge(r.het_flag, r.het_I2)}</td></tr>'
        for r in top_corr.itertuples()
    )

    # Dedicated heterogeneity section — features measured in ≥2 courses, most divergent first
    multi = corr_df[corr_df['n_courses'] >= 2].copy()
    het_block = ''
    if not multi.empty:
        multi = multi.sort_values('het_I2', ascending=False)
        n_disagree = int((multi['het_flag'] == 'disagree').sum())
        het_rows = ''.join(
            f'<tr>'
            f'<td>{r.feature}</td>'
            f'<td>{het_badge(r.het_flag, r.het_I2)}</td>'
            f'<td style="color:#666">{("–" if pd.isna(r.het_Q) else f"{r.het_Q:.1f}")} '
            f'(df={r.het_df})</td>'
            f'<td style="color:#666">{("–" if pd.isna(r.het_p) else f"{r.het_p:.3f}")}</td>'
            f'<td style="color:#888;font-size:0.85em">{r.per_course_r}</td>'
            f'</tr>'
            for r in multi.head(15).itertuples()
        )
        het_block = f"""
        <h2>Cross-Course Heterogeneity (Cochran's Q)</h2>
        <p style="color:#555">
          Tests whether each feature's correlation with grade is <em>the same</em> across courses.
          <b>{n_disagree}</b> of {len(multi)} multi-course features show <span style="color:#c62828">
          significant disagreement</span> (Q-test p&lt;0.05). High I² means the differences are real,
          not sampling noise — pooling those features hides a course-specific story.
        </p>
        <table>
          <tr><th>Feature</th><th>Verdict</th><th>Cochran's Q</th><th>p-value</th>
              <th>Per-course Pearson r</th></tr>
          {het_rows}
        </table>
        <p style="color:#888;font-size:0.85em">
          I² guide: &lt;25% low · 25–50% moderate · 50–75% substantial · &gt;75% considerable heterogeneity.
          A sign flip in "per-course r" (e.g. +0.30 vs −0.30) is the strongest signal a feature does not
          generalise across courses.
        </p>"""

    # Feature importance bar chart
    fi_rows = ''
    if not fi_df.empty:
        max_imp = fi_df['importance_pooled'].max()
        fi_rows = ''.join(
            f'<tr><td>{r.feature}</td>'
            f'<td><div style="background:#5c6bc0;width:{r.importance_pooled/max_imp*300:.0f}px;height:12px;'
            f'display:inline-block;border-radius:2px"></div> {r.importance_pooled:.4f}</td>'
            f'<td style="color:#888;font-size:0.85em">{r.n_courses}/{len(course_names)}</td></tr>'
            for r in fi_df.head(12).itertuples()
        )

    n_weighted_r2_block = ''
    if r2.get('n_weighted_r2') is not None:
        n_weighted_r2_block = f"""
        <div class="kpi-row">
          <div class="kpi">
            <div class="kpi-val">{r2['n_weighted_r2']:.3f}</div>
            <div class="kpi-label">N-weighted CV R²<br><span class="sub">pooled across {len(course_names)} courses</span></div>
          </div>
          <div class="kpi">
            <div class="kpi-val">{r2['n_total']}</div>
            <div class="kpi-label">Total students</div>
          </div>
          <div class="kpi">
            <div class="kpi-val">{len(course_names)}</div>
            <div class="kpi-label">Courses</div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Aaron Owl — Federated Meta-Analysis</title>
<style>
body{{font-family:Arial,sans-serif;max-width:960px;margin:40px auto;color:#333;line-height:1.5}}
h1{{color:#3f51b5}}h2{{color:#5c6bc0;margin-top:2em;border-bottom:2px solid #e8eaf6;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;margin-top:1em}}
td,th{{border:1px solid #e0e0e0;padding:8px 12px;text-align:left}}
th{{background:#f5f5f5;font-weight:600}}tr:hover{{background:#fafafa}}
.kpi-row{{display:flex;gap:24px;margin:16px 0}}
.kpi{{background:#e8eaf6;border-radius:8px;padding:16px 24px;min-width:130px;text-align:center}}
.kpi-val{{font-size:2em;font-weight:700;color:#3f51b5}}
.kpi-label{{font-size:0.85em;color:#555;margin-top:4px}}
.sub{{color:#888;font-size:0.9em}}
.notice{{background:#fff8e1;border-left:4px solid #ffc107;padding:12px 16px;font-size:0.9em;margin:1em 0}}
</style></head><body>
<h1>Aaron Owl — Federated Meta-Analysis</h1>
<p>Courses: <b>{', '.join(course_names)}</b></p>
<div class="notice">
  ℹ️  <b>Privacy-preserving aggregation.</b>
  Individual student grades were never shared. Each teacher ran analysis locally and returned only aggregated statistics.
  Correlations are pooled using Fisher's z-transform (weighted by n). Importances are N-weighted averages.
</div>

{n_weighted_r2_block}

{tier_block}

<h2>Pooled Feature Correlations with Final Grade</h2>
<table>
  <tr><th>Feature</th><th>Pearson r (pooled)</th><th>95% CI</th><th>Spearman r (pooled)</th><th>N (total)</th><th>Consistency</th></tr>
  {corr_rows}
</table>
<p style="color:#888;font-size:0.85em">"Consistency" = Cochran's Q verdict (see heterogeneity section). A pooled r with a
  "courses disagree" badge should be read with caution — it averages over courses that genuinely differ.</p>

{het_block}

<h2>Per-Course Model Performance (Ridge Regression, 5-fold CV)</h2>
<table>
  <tr><th>Course</th><th>N students</th><th>CV R²</th><th>±std</th></tr>
  {r2_rows}
</table>
<p style="color:#888;font-size:0.85em">R² varies across courses partly due to sample size (small n → high variance) and course-specific grade distributions.</p>

{'<h2>Pooled Feature Importance (Random Forest, N-weighted)</h2><table><tr><th>Feature</th><th>Importance</th><th>Courses</th></tr>' + fi_rows + '</table>' if fi_rows else ''}

<hr><p style="font-size:0.8em;color:#aaa">Generated by Aaron Owl federated meta-analysis — no individual grades included.</p>
</body></html>"""


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aaron Owl federated meta-analysis")
    parser.add_argument('--courses', default=None,
                        help='Comma-separated "Name:results_dir" pairs, e.g. "Psy:/path/psy,Math:/path/math"')
    parser.add_argument('--manifest', default=None,
                        help='YAML file with course list: [{name: ..., results_dir: ...}]')
    parser.add_argument('--out', default='./meta_results', help='Output directory')
    args = parser.parse_args()

    course_entries = []
    if args.courses:
        for token in args.courses.split(','):
            name, path = token.strip().split(':', 1)
            course_entries.append((name.strip(), path.strip()))
    elif args.manifest:
        import yaml
        with open(args.manifest) as f:
            for entry in yaml.safe_load(f):
                course_entries.append((entry['name'], entry['results_dir']))
    else:
        parser.error("Provide --courses or --manifest")

    print("Loading course results...")
    courses = []
    for name, path in course_entries:
        c = load_course_results(name, path)
        print(f"  {name}: n={c['n']}, R²={c['r2']}")
        courses.append(c)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Pooling correlations (Fisher z)...")
    corr_df = combined_correlations(courses)
    corr_df.to_csv(out_dir / 'meta_correlation.csv', index=False)

    print("Pooling feature importances...")
    fi_df = combined_importance(courses)
    fi_df.to_csv(out_dir / 'meta_importance.csv', index=False)

    print("Pooling ALS tier profiles...")
    tier_df = combined_tier_profile(courses)
    if not tier_df.empty:
        tier_df.to_csv(out_dir / 'meta_tier_profile.csv', index=False)

    r2 = r2_summary(courses)
    with open(out_dir / 'meta_r2.json', 'w') as f:
        json.dump(r2, f, indent=2)

    print("Generating HTML report...")
    html = render_html(corr_df, fi_df, r2, [c['name'] for c in courses], tier_df)
    (out_dir / 'meta_report.html').write_text(html, encoding='utf-8')

    # Console summary
    print(f"\n{'='*60}")
    print(f"FEDERATED META-ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Courses: {', '.join(c['name'] for c in courses)}")
    print(f"Total students: {r2.get('n_total', '?')}")
    print(f"N-weighted CV R²: {r2.get('n_weighted_r2', '?'):.3f}")
    print(f"\nPer-course R²:")
    for name, v in r2.get('per_course', {}).items():
        print(f"  {name:<20} R²={v['r2']:.3f} ±{v['r2_std']:.3f}  (n={v['n']})")
    print(f"\nTop 8 pooled correlations with final grade:")
    print(corr_df.head(8)[['feature','pearson_r_pooled','pearson_ci_lo','pearson_ci_hi','n_total']].to_string(index=False))
    print(f"\nTop 8 pooled feature importances:")
    print(fi_df.head(8)[['feature','importance_pooled','n_total']].to_string(index=False))

    multi = corr_df[corr_df['n_courses'] >= 2]
    disagree = multi[multi['het_flag'] == 'disagree'].sort_values('het_I2', ascending=False)
    print(f"\nCross-course heterogeneity (Cochran's Q): "
          f"{len(disagree)}/{len(multi)} multi-course features disagree (p<0.05)")
    if not disagree.empty:
        print("Most heterogeneous (courses genuinely differ):")
        print(disagree.head(8)[['feature','het_I2','het_p','per_course_r']].to_string(index=False))

    print(f"\nResults saved to {out_dir}/")


if __name__ == '__main__':
    main()
