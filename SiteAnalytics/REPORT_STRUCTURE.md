yes# Analytics Report Structure & Flags

## Report Types & Levels

Your analytics system now supports **3 report types** at **3 different levels**:

###  Report Types

1. **SEMESTER** (Static snapshot combining ALL weekly data)
2. **WEEKLY** (Static snapshot of a specific week)
3. **PROGRESS** (Dynamic time-series with engagement trends, persistence, at-risk analysis)

### Levels

1. **PLATFORM** - All courses combined across entire platform
2. **INSTITUTE** - Courses grouped by institute
3. **COURSE** - Individual course analysis

---

## Folder Structure

```
/reports/
├── semester_report_platform_2025-11-13_2025-12-31.html         # Platform semester
├── weekly_snapshot_platform_week_07_2025-12-28_2026-01-03.html # Platform weekly
│
├── {Institute_Name}/                                            # Institute folder
│   ├── institute_progress_{Institute}_2025-11-13_2025-12-31.html  # Institute progress
│   ├── semester_report_{Institute}_2025-11-13_2025-12-31.html     # Institute semester (if enabled)
│   ├── weekly_snapshot_{Institute}_week_07_...html                # Institute weekly (if enabled)
│   │
│   ├── course_{Course_Name}_2025-11-13_2025-12-31.html          # Course progress reports
│   ├── course_{Another_Course}_2025-11-13_2025-12-31.html
│   └── ...
│
└── {Another_Institute}/
    └── ... (same structure)
```

**Key Points:**
- Platform-level reports go directly in `/reports/`
- Institute-level reports go in `/reports/{Institute_Name}/`
- Course-level reports go in `/reports/{Institute_Name}/` (alongside institute report)

---

## Configuration Flags (`config.yaml`)

### Currently Available Flags

```yaml
semester:
  # Operations to run when using run_all() or no CLI args
  run_data_extraction: false     # Extract only NEW weeks since last extraction
  run_semester_report: true      # Generate PLATFORM-level semester report
  run_weekly_report: true        # Generate PLATFORM-level weekly snapshot
  run_weekly_progress: false     # Generate COURSE-level progress (for progress_course_id)
  run_institute_progress: true   # Generate INSTITUTE-level progress + individual course reports

  report_week_number: null       # Which week to report (null = latest week)
  progress_course_id: "..."      # Specific course for weekly progress (null = all courses combined)
```

### What Each Flag Does

| Flag | Current Level | Report Type | Output Location |
|------|--------------|-------------|-----------------|
| `run_semester_report` | Platform | Semester (static) | `/reports/semester_report_platform_...html` |
| `run_weekly_report` | Platform | Weekly (static) | `/reports/weekly_snapshot_platform_week_...html` |
| `run_weekly_progress` | Course (single) | Progress (dynamic) | `/reports/course/weekly_progress_{course_id}_...html` |
| `run_institute_progress` | Institute + Course | Progress (dynamic) | `/reports/{Institute}/institute_progress_...html`<br>`/reports/{Institute}/course_{name}_...html` |

---

## Current Implementation Status

### ✅ Fully Implemented

1. **Platform-level Semester Report** (`run_semester_report: true`)
   - Combines all weekly data
   - Generates platform-wide semester snapshot
   - Location: `/reports/semester_report_platform_{dates}.html`

2. **Platform-level Weekly Snapshot** (`run_weekly_report: true`)
   - Analyzes specific week (latest by default)
   - Platform-wide view
   - Location: `/reports/weekly_snapshot_platform_week_{num}_{dates}.html`

3. **Institute-level Progress Reports** (`run_institute_progress: true`)
   - One report per institute (aggregated metrics)
   - Individual course reports per institute
   - Location: `/reports/{Institute}/institute_progress_...html` and `/reports/{Institute}/course_...html`

4. **Course-level Progress Report** (`run_weekly_progress: true`)
   - Single course time-series analysis
   - Location: `/reports/course/weekly_progress_{course_id}_...html`

### ⚠️ Partially Implemented (functions exist, not in config)

The codebase now supports **additional levels** for semester and weekly reports through function parameters, but they're not exposed in `run_all()` or config flags yet:

- `run_semester_report(config, level='institute', institute_name='...')` - Institute semester
- `run_semester_report(config, level='course', institute_name='...', course_id='...')` - Course semester
- `run_weekly_report(config, week_number=7, level='institute', institute_name='...')` - Institute weekly
- `run_weekly_report(config, week_number=7, level='course', institute_name='...', course_id='...')` - Course weekly

---

## How to Use

### Run All Configured Reports
```bash
python semester_analyzer.py
# or explicitly:
python semester_analyzer.py --all
```

### Run Individual Reports
```bash
# Extract new data
python semester_analyzer.py --get-recent

# Generate platform semester report
python semester_analyzer.py --semester

# Generate platform weekly snapshot (latest week)
python semester_analyzer.py --weekly

# Generate platform weekly snapshot (specific week)
python semester_analyzer.py --weekly --week 5

# Generate course progress report (all courses combined)
python semester_analyzer.py --progress

# Generate course progress report (specific course)
python semester_analyzer.py --progress --course-id "abc-123"

# Generate institute progress reports (all institutes)
python semester_analyzer.py --institute-progress
```

---

## Next Steps (If Needed)

If you want to enable **institute and course level semester/weekly reports** through config flags, we would need to:

1. Add new config flags like:
   ```yaml
   run_institute_semester: false    # Semester reports per institute
   run_institute_weekly: false      # Weekly snapshots per institute
   run_course_semester: false       # Semester reports per course
   run_course_weekly: false         # Weekly snapshots per course
   ```

2. Update `run_all()` to call the multi-level functions

3. Add logic to iterate through all institutes/courses when generating

**Current Recommendation:** The current setup covers the main use cases:
- **Platform-wide snapshots** for high-level overview
- **Institute progress tracking** with individual course breakdowns
- **Course-specific progress** for deep dives

Let me know if you need additional report levels enabled!