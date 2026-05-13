# Aaron Owl — Federated Analysis Guide

How to organize incoming teacher results and run the cross-course meta-analysis.

## Expected directory layout

When teachers return their result files, place each course under a named subdirectory:

```
federated_results/
├── Psychology/
│   ├── correlation_report.csv
│   ├── regression_summary.txt
│   ├── feature_importance.csv
│   └── als_tier_profile.csv
├── Math/
│   ├── correlation_report.csv
│   ├── regression_summary.txt
│   ├── feature_importance.csv
│   └── als_tier_profile.csv
└── ...
```

One subdirectory per course. The 4 files per course are exactly what the teacher's
`analysis_script.py` produces in their `results/` folder.

## Run the meta-analysis

```bash
python federation/meta_analysis.py \
    --courses "Psychology:federated_results/Psychology,Math:federated_results/Math" \
    --out     federated_results/meta/
```

Or use a YAML manifest for many courses:

```yaml
# courses_manifest.yaml
- name: Psychology
  results_dir: federated_results/Psychology
- name: Math
  results_dir: federated_results/Math
```

```bash
python federation/meta_analysis.py \
    --manifest courses_manifest.yaml \
    --out      federated_results/meta/
```

## Outputs

| File | Contents |
|---|---|
| `meta_correlation.csv` | Pearson r pooled across courses (Fisher z-transform, weighted by n) |
| `meta_importance.csv` | Random Forest importances averaged across courses (N-weighted) |
| `meta_tier_profile.csv` | Mean grade per ALS tier, z-scored within course before pooling |
| `meta_r2.json` | Per-course CV R² + N-weighted combined R² |
| `meta_report.html` | Visual summary — open in browser |

## What you never receive

- Individual student grades (teachers keep those)
- Raw grade values for any individual student
- Any data that could re-identify a specific student's grade

The federation model: Aaron Owl provides feature vectors → teacher adds grades locally →
teacher returns only the 4 aggregated result files listed above.
