#!/usr/bin/env python3
"""
Semester Analytics Module
Handles weekly data extraction and semester-wide reporting

Main Functions:
1. get_recent_data() - Extract only NEW weeks since last extraction (0, 1, or more weeks)
2. run_semester_report() - Generate semester HTML report from all weekly files
3. run_weekly_report() - Generate HTML report for specific week (default: latest or from config)
4. run_all() - Orchestrate 1+2+3 based on config settings
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import time

from mixpanel_export import MixpanelExporter
from course_analysis import CourseAnalysis
from weekly_progress_analyzer import WeeklyProgressAnalyzer
from reports_generator import NewWeeklyReportsGenerator
from institute_reports_generator import NewInstituteReportsGenerator
from utils import load_config, get_mixpanel_secret, load_course_list

# Old reporters (kept for backwards compatibility, not used by default)
# from course_reporter_old import CourseReporter
# from weekly_progress_reporter_old import WeeklyProgressReporter
# from institute_progress_reporter_old import InstituteProgressReporter


def calculate_week_ranges(start_date: str, end_date: str = None) -> List[Tuple[str, str]]:
    """
    Calculate weekly date ranges from semester start to current date (or specified end date)
    Weeks run from Saturday to Saturday (7 days)

    Args:
        start_date: Semester start date in YYYY-MM-DD format
        end_date: Optional end date, defaults to today

    Returns:
        List of (from_date, to_date) tuples for each week
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()

    weeks = []

    # Find the first Saturday on or after start_date
    # weekday(): Monday=0, Sunday=6, so Saturday=5
    days_until_saturday = (5 - start.weekday()) % 7
    current_week_start = start + timedelta(days=days_until_saturday)

    # If the first Saturday is after end date, use start date for first week
    if current_week_start > end:
        weeks.append((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
        return weeks

    # Include partial week from start_date to first Saturday if needed
    if current_week_start > start:
        weeks.append((
            start.strftime('%Y-%m-%d'),
            (current_week_start - timedelta(days=1)).strftime('%Y-%m-%d')
        ))

    while current_week_start <= end:
        # Week runs from Saturday to next Friday (7 days)
        week_end = current_week_start + timedelta(days=6)

        # Don't go past the end date
        if week_end > end:
            week_end = end

        weeks.append((
            current_week_start.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        ))

        # Move to next Saturday
        current_week_start = week_end + timedelta(days=1)

    return weeks


def get_recent_data(config: dict) -> int:
    """
    FUNCTION 1: Extract only NEW weeks since last weekly file
    - Checks what weeks already exist
    - Extracts only missing weeks (0 if same week, 1+ if new weeks)
    - Respects rate limits and max_weeks_per_run

    Args:
        config: Configuration dictionary

    Returns:
        Number of new weeks extracted
    """
    semester_config = config.get('semester', {})
    start_date = semester_config.get('start_date')
    output_dir = semester_config.get('weekly_output_dir')

    if not start_date:
        print("Error: semester.start_date not configured")
        return 0

    if not output_dir:
        print("Error: semester.weekly_output_dir not configured")
        return 0

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get Mixpanel credentials
    api_secret = get_mixpanel_secret(config)
    if not api_secret:
        print("Error: Mixpanel API secret not found")
        return 0

    # Calculate all week ranges up to today
    weeks = calculate_week_ranges(start_date)

    # Get settings
    api_delay = semester_config.get('api_request_delay_seconds', 2)
    max_weeks_per_run = semester_config.get('max_weeks_per_run', None)
    force_reextract = semester_config.get('force_reextract_weekly', False)

    print(f"\n{'='*80}")
    print(f"GET RECENT DATA")
    print(f"{'='*80}")
    print(f"Semester start: {start_date}")
    print(f"Total weeks in semester: {len(weeks)}")
    print(f"Output directory: {output_dir}")
    print(f"API delay: {api_delay} seconds between requests")
    if max_weeks_per_run:
        print(f"Max weeks per run: {max_weeks_per_run}")
    print(f"{'='*80}\n")

    # Get blacklist
    blacklist_user_ids = set(config.get('blacklist', {}).get('user_ids', []))
    blacklist_course_ids = set(config.get('blacklist', {}).get('course_ids', []))

    # Initialize exporter with blacklist
    project_id = config.get('mixpanel', {}).get('project_id')
    exporter = MixpanelExporter(api_secret, project_id,
                               blacklist_user_ids=blacklist_user_ids,
                               blacklist_course_ids=blacklist_course_ids)

    # Extract only NEW weeks
    extracted_count = 0
    today_date = datetime.now().date()

    for week_num, (from_date, to_date) in enumerate(weeks, 1):
        week_file = os.path.join(output_dir, f"week_{from_date}_{to_date}.csv")

        # Check if week is complete (ended before today and at least 6 days long)
        from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date()
        to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date()
        week_duration = (to_date_obj - from_date_obj).days + 1

        # Skip incomplete weeks
        if to_date_obj >= today_date or week_duration < 6:
            print(f"Week {week_num:02d}: {from_date} to {to_date} - Incomplete week ({week_duration} days), skipping")
            continue

        # Skip if file already exists (unless force reextract is enabled)
        if os.path.exists(week_file) and not force_reextract:
            print(f"Week {week_num:02d}: {from_date} to {to_date} - Already exists, skipping")
            continue
        elif os.path.exists(week_file) and force_reextract:
            print(f"Week {week_num:02d}: {from_date} to {to_date} - Overwriting existing file")
        else:
            print(f"Week {week_num:02d}: {from_date} to {to_date} - NEW week, extracting")

        # Add delay before request (except for first request)
        if extracted_count > 0:
            print(f"  Waiting {api_delay} seconds before next request...")
            time.sleep(api_delay)

        print(f"  Extracting from Mixpanel...", end=" ", flush=True)

        try:
            # Use export_to_csv which properly flattens the events
            exporter.export_to_csv(from_date, to_date, output_file=week_file)

            # Count events in saved file
            df_check = pd.read_csv(week_file)
            print(f"✓ Saved {len(df_check)} events")
            extracted_count += 1

        except Exception as e:
            error_msg = str(e)
            print(f"✗ Error: {error_msg}")

            # If rate limit error, suggest increasing delay
            if "429" in error_msg or "rate limit" in error_msg.lower():
                print(f"\n⚠️  RATE LIMIT HIT!")
                print(f"Consider increasing 'api_request_delay_seconds' in config.yaml")
                print(f"Current delay: {api_delay} seconds")
                print(f"Extracted {extracted_count} weeks before hitting limit")
                print(f"You can re-run the script to continue from where it stopped.\n")
                break

        # Check if we've hit the max weeks per run limit
        if max_weeks_per_run and extracted_count >= max_weeks_per_run:
            print(f"\n✓ Reached max weeks per run limit ({max_weeks_per_run})")
            print(f"Run the script again later to continue extracting more weeks.\n")
            break

    print(f"\n{'='*80}")
    print(f"GET RECENT DATA COMPLETE")
    print(f"Extracted {extracted_count} new week(s)")
    print(f"{'='*80}\n")

    return extracted_count


def run_semester_report(config: dict, level: str = 'platform', institute_name: str = None, course_id: str = None) -> str:
    """
    DEPRECATED: Use run_new_reports() instead

    FUNCTION 2: Generate semester HTML report from all weekly CSV files
    - Loads ALL weekly files
    - Combines them into semester dataset
    - Generates semester HTML report at specified level

    Args:
        config: Configuration dictionary
        level: Report level - 'platform', 'institute', or 'course'
        institute_name: Institute name (required if level='institute' or 'course')
        course_id: Course ID (required if level='course')

    Returns:
        Path to generated report (or None if failed)
    """
    print("⚠️  WARNING: run_semester_report() is DEPRECATED. Use run_new_reports() instead.")
    print("    This function uses old report formats and will be removed in a future version.\n")
    return None
    semester_config = config.get('semester', {})
    start_date = semester_config.get('start_date')
    weekly_dir = semester_config.get('weekly_output_dir')

    if not start_date:
        print("Error: semester.start_date not configured")
        return None

    if not weekly_dir or not os.path.exists(weekly_dir):
        print("Error: weekly_output_dir not found or does not exist")
        return None

    # Get directory configuration
    export_config = config.get('export', {})
    raw_data_dir = export_config.get('raw_data_dir', export_config.get('output_dir', '.'))
    reports_base_dir = export_config.get('reports_dir', export_config.get('output_dir', '.'))

    # Determine output directory based on level
    if level == 'platform':
        reports_dir = reports_base_dir
        level_suffix = 'platform'
    elif level == 'institute':
        if not institute_name:
            print("Error: institute_name required for institute-level report")
            return None
        safe_name = institute_name.replace(' ', '_').replace('/', '_')
        reports_dir = os.path.join(reports_base_dir, safe_name)
        level_suffix = safe_name
    elif level == 'course':
        if not institute_name or not course_id:
            print("Error: institute_name and course_id required for course-level report")
            return None
        safe_inst = institute_name.replace(' ', '_').replace('/', '_')
        reports_dir = os.path.join(reports_base_dir, safe_inst)
        level_suffix = course_id
    else:
        print(f"Error: Invalid level '{level}'. Must be 'platform', 'institute', or 'course'")
        return None

    # Create directories
    os.makedirs(raw_data_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # Calculate current date
    today = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{'='*80}")
    print(f"SEMESTER REPORT GENERATION ({level.upper()} LEVEL)")
    print(f"{'='*80}")
    print(f"Semester period: {start_date} to {today}")
    print(f"Weekly data directory: {weekly_dir}")
    print(f"Reports directory: {reports_dir}")
    if level == 'institute':
        print(f"Institute filter: {institute_name}")
    elif level == 'course':
        print(f"Institute: {institute_name}, Course filter: {course_id}")
    print(f"{'='*80}\n")

    # Load all weekly files
    print("Loading weekly data files...")
    weekly_files = sorted([f for f in os.listdir(weekly_dir) if f.startswith('week_') and f.endswith('.csv')])

    if not weekly_files:
        print("Error: No weekly files found")
        return None

    print(f"Found {len(weekly_files)} weekly data files")
    dfs = []
    for week_file in weekly_files:
        week_path = os.path.join(weekly_dir, week_file)
        try:
            df_week = pd.read_csv(week_path)
            dfs.append(df_week)
            print(f"  Loaded {week_file}: {len(df_week)} events")
        except Exception as e:
            print(f"  Warning: Could not load {week_file}: {e}")

    if not dfs:
        print("Error: No weekly data could be loaded")
        return None

    # Combine all weeks
    df_semester = pd.concat(dfs, ignore_index=True)
    print(f"\nCombined semester data: {len(df_semester)} total events")

    # Filter by course if needed
    if level == 'course' and course_id:
        course_col = 'course' if 'course' in df_semester.columns else 'course_id'
        if course_col in df_semester.columns:
            df_semester = df_semester[df_semester[course_col] == course_id]
            print(f"Filtered to course {course_id}: {len(df_semester)} events")
        else:
            print(f"Warning: No course column found, cannot filter by course")

    # Convert time column to datetime if needed
    if 'datetime' not in df_semester.columns:
        if 'time' in df_semester.columns:
            print("Converting 'time' column to 'datetime'...")
            df_semester['datetime'] = pd.to_datetime(df_semester['time'], unit='s')
        else:
            print("Error: No 'time' or 'datetime' column found")
            return None

    # Load course information
    course_info = load_course_list(config)

    # For institute-level, filter course_info
    if level == 'institute' and course_info is not None:
        if 'institute' in course_info.columns:
            course_info = course_info[course_info['institute'] == institute_name]
            print(f"Filtered course info to {len(course_info)} courses in {institute_name}")

    # Perform analysis
    print("\nAnalyzing semester data...")
    analyzer = CourseAnalysis(df_semester, course_info)

    # Export analysis results to raw_data_dir
    print("Exporting analysis results...")
    analysis_files = analyzer.export_to_csv(raw_data_dir, start_date, today)
    json_file = analyzer.export_to_json(raw_data_dir, start_date, today)

    # Generate HTML report to reports_dir
    print("Generating semester HTML report...")
    reporter = CourseReporter.from_json(json_file)

    report_path = os.path.join(reports_dir, f"semester_report_{level_suffix}_{start_date}_{today}.html")

    # For platform/institute level, use split mode from config; for course level, always unified
    if level == 'course':
        split_mode = False
    else:
        split_mode = config.get('report', {}).get('split_by_institution', False)

    reporter.generate_html_report(report_path, split_by_institution=split_mode, report_type='semester')

    print(f"\n{'='*80}")
    print(f"SEMESTER REPORT COMPLETE")
    print(f"Report: {report_path}")
    print(f"{'='*80}\n")

    return report_path


def run_weekly_report(config: dict, week_number: int = None, level: str = 'platform',
                      institute_name: str = None, course_id: str = None) -> str:
    """
    DEPRECATED: Use run_new_reports() instead

    FUNCTION 3: Generate HTML report for a specific week
    - Loads specific week CSV file
    - Generates weekly HTML report at specified level

    Args:
        config: Configuration dictionary
        week_number: Week number to generate report for (None = latest week)
        level: Report level - 'platform', 'institute', or 'course'
        institute_name: Institute name (required if level='institute' or 'course')
        course_id: Course ID (required if level='course')

    Returns:
        Path to generated report (or None if failed)
    """
    print("⚠️  WARNING: run_weekly_report() is DEPRECATED. Use run_new_reports() instead.")
    print("    This function uses old report formats and will be removed in a future version.\n")
    return None
    semester_config = config.get('semester', {})
    weekly_dir = semester_config.get('weekly_output_dir')

    if not weekly_dir or not os.path.exists(weekly_dir):
        print("Error: weekly_output_dir not found or does not exist")
        return None

    # Get directory configuration
    export_config = config.get('export', {})
    reports_base_dir = export_config.get('reports_dir', export_config.get('output_dir', '.'))

    # Determine output directory based on level
    if level == 'platform':
        reports_dir = reports_base_dir
        level_suffix = 'platform'
    elif level == 'institute':
        if not institute_name:
            print("Error: institute_name required for institute-level report")
            return None
        safe_name = institute_name.replace(' ', '_').replace('/', '_')
        reports_dir = os.path.join(reports_base_dir, safe_name)
        level_suffix = safe_name
    elif level == 'course':
        if not institute_name or not course_id:
            print("Error: institute_name and course_id required for course-level report")
            return None
        safe_inst = institute_name.replace(' ', '_').replace('/', '_')
        reports_dir = os.path.join(reports_base_dir, safe_inst)
        level_suffix = course_id
    else:
        print(f"Error: Invalid level '{level}'. Must be 'platform', 'institute', or 'course'")
        return None

    os.makedirs(reports_dir, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"WEEKLY REPORT GENERATION ({level.upper()} LEVEL)")
    print(f"{'='*80}")

    # Find weekly files
    weekly_files = sorted([f for f in os.listdir(weekly_dir) if f.startswith('week_') and f.endswith('.csv')])

    if not weekly_files:
        print("Error: No weekly files found")
        return None

    # Determine which week to process
    if week_number is None:
        # Default: use latest week from config or last file
        week_number = semester_config.get('report_week_number')
        if week_number is None:
            week_number = len(weekly_files)  # Default to latest week

    if week_number < 1 or week_number > len(weekly_files):
        print(f"Error: Week {week_number} not found (available: 1-{len(weekly_files)})")
        return None

    week_file = weekly_files[week_number - 1]
    week_path = os.path.join(weekly_dir, week_file)

    # Extract week info from filename: week_01_2025-10-16_2025-10-17.csv
    parts = week_file.replace('.csv', '').split('_')
    week_num = parts[1]
    from_date = parts[2]
    to_date = parts[3]

    print(f"Week {week_num}: {from_date} to {to_date}")
    if level == 'institute':
        print(f"Institute filter: {institute_name}")
    elif level == 'course':
        print(f"Institute: {institute_name}, Course filter: {course_id}")
    print(f"{'='*80}\n")

    # Load week data
    print(f"Loading {week_file}...")
    df_week = pd.read_csv(week_path)
    print(f"Loaded {len(df_week)} events")

    # Filter by course if needed
    if level == 'course' and course_id:
        course_col = 'course' if 'course' in df_week.columns else 'course_id'
        if course_col in df_week.columns:
            df_week = df_week[df_week[course_col] == course_id]
            print(f"Filtered to course {course_id}: {len(df_week)} events")
        else:
            print(f"Warning: No course column found, cannot filter by course")

    # Convert time column to datetime if needed
    if 'datetime' not in df_week.columns:
        if 'time' in df_week.columns:
            df_week['datetime'] = pd.to_datetime(df_week['time'], unit='s')
        else:
            print("Error: No time column found")
            return None

    # Load course information
    course_info = load_course_list(config)

    # For institute-level, filter course_info
    if level == 'institute' and course_info is not None:
        if 'institute' in course_info.columns:
            course_info = course_info[course_info['institute'] == institute_name]
            print(f"Filtered course info to {len(course_info)} courses in {institute_name}")

    # Perform analysis
    print("Analyzing week data...")
    analyzer = CourseAnalysis(df_week, course_info)

    # Export to JSON (for report generation)
    print("Exporting analysis results...")
    json_file = analyzer.export_to_json(reports_dir, from_date, to_date)

    # Generate HTML report
    print("Generating weekly HTML report...")
    reporter = CourseReporter.from_json(json_file)

    report_path = os.path.join(reports_dir, f"weekly_snapshot_{level_suffix}_week_{week_num}_{from_date}_{to_date}.html")

    # For platform/institute level, use split mode from config; for course level, always unified
    if level == 'course':
        split_mode = False
    else:
        split_mode = config.get('report', {}).get('split_by_institution', False)

    reporter.generate_html_report(report_path, split_by_institution=split_mode, report_type='weekly')

    # Clean up temp JSON
    if os.path.exists(json_file):
        os.remove(json_file)

    print(f"\n{'='*80}")
    print(f"WEEKLY REPORT COMPLETE")
    print(f"Report: {report_path}")
    print(f"{'='*80}\n")

    return report_path


def run_weekly_progress(config: dict, course_id: str = None) -> str:
    """
    DEPRECATED: Use run_new_reports() instead

    FUNCTION 4: Generate weekly progress report with semester-long engagement analysis
    - Loads ALL weekly CSV files
    - Calculates week-by-week metrics (WAU, persistence, at-risk, features, etc.)
    - Generates dynamic progress HTML report with executive summary

    Args:
        config: Configuration dictionary
        course_id: Specific course ID to analyze (None = all courses combined)

    Returns:
        Path to generated report (or None if failed)
    """
    print("⚠️  WARNING: run_weekly_progress() is DEPRECATED. Use run_new_reports() instead.")
    print("    This function uses old report formats and will be removed in a future version.\n")
    return None
    semester_config = config.get('semester', {})
    start_date = semester_config.get('start_date')
    end_date = semester_config.get('end_date')  # Get semester end date
    weekly_dir = semester_config.get('weekly_output_dir')

    if not start_date:
        print("Error: semester.start_date not configured")
        return None

    if not weekly_dir or not os.path.exists(weekly_dir):
        print("Error: weekly_output_dir not found or does not exist")
        return None

    # Get directory configuration
    export_config = config.get('export', {})
    reports_base_dir = export_config.get('reports_dir', export_config.get('output_dir', '.'))
    reports_dir = os.path.join(reports_base_dir, 'course')
    os.makedirs(reports_dir, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"WEEKLY PROGRESS REPORT GENERATION")
    print(f"{'='*80}")
    print(f"Semester start: {start_date}")
    if end_date:
        print(f"Semester end: {end_date}")
    print(f"Weekly data directory: {weekly_dir}")
    if course_id:
        print(f"Course filter: {course_id}")
    else:
        print(f"Course filter: All courses combined")
    print(f"{'='*80}\n")

    # Get all weekly files
    weekly_files = sorted([
        os.path.join(weekly_dir, f)
        for f in os.listdir(weekly_dir)
        if f.startswith('week_') and f.endswith('.csv')
    ])

    if not weekly_files:
        print("Error: No weekly files found")
        return None

    print(f"Found {len(weekly_files)} weekly data files\n")

    # Initialize analyzer with semester end date and config
    print("Initializing weekly progress analyzer...")
    analyzer = WeeklyProgressAnalyzer(weekly_files, start_date, end_date, course_id, config)

    # Calculate weekly metrics
    print("Calculating weekly metrics...")
    weekly_metrics = analyzer.calculate_weekly_metrics()

    if len(weekly_metrics) == 0:
        print("Error: No metrics calculated")
        return None

    print(f"Calculated metrics for {len(weekly_metrics)} weeks")

    # Add trend metrics
    print("Calculating trend metrics...")
    weekly_metrics = analyzer.calculate_trend_metrics(weekly_metrics)

    # Add semester phase metrics
    print("Calculating semester phase metrics...")
    weekly_metrics = analyzer.calculate_semester_phase_metrics(weekly_metrics)

    # Generate executive summary
    print("Generating executive summary...")
    executive_summary = analyzer.generate_executive_summary(weekly_metrics)

    # Get student leaderboards
    print("Generating student leaderboards...")
    latest_week = int(weekly_metrics.iloc[-1]['week_number'])
    leaderboards = analyzer.get_student_leaderboards(latest_week, top_n=10)
    print(f"  Top engaged students: {len(leaderboards['top_engaged'])}")
    print(f"  At-risk students: {len(leaderboards['at_risk'])}")

    # Generate HTML report
    print("Generating HTML report...")

    # Get course name for display
    if course_id:
        # Try to get course name from course_info
        course_info = load_course_list(config)
        if course_info is not None and 'course_id' in course_info.columns:
            match = course_info[course_info['course_id'] == str(course_id)]
            if len(match) > 0:
                course_name = match.iloc[0].get('course_name', course_id)
            else:
                course_name = course_id
        else:
            course_name = course_id
    else:
        course_name = "All Courses"

    reporter = WeeklyProgressReporter(weekly_metrics, course_name, semester_start=start_date, semester_end=end_date, config=config)

    # Generate report path
    today = datetime.now().strftime('%Y-%m-%d')
    course_suffix = f"_{course_id}" if course_id else "_all_courses"
    report_path = os.path.join(reports_dir, f"weekly_progress{course_suffix}_{start_date}_{today}.html")

    reporter.generate_html_report(report_path, executive_summary, leaderboards)

    print(f"\n{'='*80}")
    print(f"WEEKLY PROGRESS REPORT COMPLETE")
    print(f"Report: {report_path}")
    print(f"{'='*80}\n")

    return report_path


def run_institute_progress(config: dict) -> List[str]:
    """
    DEPRECATED: Use run_new_reports() instead

    FUNCTION 5: Generate institute-level weekly progress reports
    - Loads ALL weekly CSV files
    - Groups courses by institute (from courses.csv)
    - For each institute, calculates aggregated weekly metrics
    - Generates one HTML report per institute with collapsible per-course breakdowns

    Args:
        config: Configuration dictionary

    Returns:
        List of paths to generated reports (one per institute)
    """
    print("⚠️  WARNING: run_institute_progress() is DEPRECATED. Use run_new_reports() instead.")
    print("    This function uses old report formats and will be removed in a future version.\n")
    return []
    semester_config = config.get('semester', {})
    start_date = semester_config.get('start_date')
    end_date = semester_config.get('end_date')
    weekly_dir = semester_config.get('weekly_output_dir')

    if not start_date:
        print("Error: semester.start_date not configured")
        return []

    if not weekly_dir or not os.path.exists(weekly_dir):
        print("Error: weekly_output_dir not found or does not exist")
        return []

    # Get directory configuration
    export_config = config.get('export', {})
    reports_base_dir = export_config.get('reports_dir', export_config.get('output_dir', '.'))

    print(f"\n{'='*80}")
    print(f"INSTITUTE WEEKLY PROGRESS REPORT GENERATION")
    print(f"{'='*80}")
    print(f"Semester start: {start_date}")
    if end_date:
        print(f"Semester end: {end_date}")
    print(f"Weekly data directory: {weekly_dir}")
    print(f"Reports base directory: {reports_base_dir}")
    print(f"Folder structure: {reports_base_dir}/{{institute_name}}/")
    print(f"{'='*80}\n")

    # Load course information to get institute mappings
    course_info = load_course_list(config)
    if course_info is None:
        print("Error: Could not load course information. Cannot group by institute.")
        return []

    # Check for institute column
    if 'institute' not in course_info.columns:
        print("Error: 'institute' column not found in course information. Cannot group by institute.")
        print(f"Available columns: {list(course_info.columns)}")
        return []

    # Get all weekly files
    all_weekly_files = sorted([
        os.path.join(weekly_dir, f)
        for f in os.listdir(weekly_dir)
        if f.startswith('week_') and f.endswith('.csv')
    ])

    if not all_weekly_files:
        print("Error: No weekly files found")
        return []

    # Filter to only complete weeks (exclude current partial week and single-day weeks)
    today = datetime.now().date()
    weekly_files = []
    excluded_partial = []

    for week_file in all_weekly_files:
        # Extract from_date and to_date from filename: week_01_2025-10-16_2025-10-22.csv
        filename = os.path.basename(week_file)
        parts = filename.replace('.csv', '').split('_')
        if len(parts) >= 4:
            from_date_str = parts[2]  # e.g., "2025-10-16"
            to_date_str = parts[3]     # e.g., "2025-10-22"
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()

            # Calculate week duration
            week_duration = (to_date - from_date).days + 1  # +1 to include both start and end days

            # Only include weeks that:
            # 1. Have already ended (to_date < today)
            # 2. Are full weeks (6-7 days long)
            if to_date < today and week_duration >= 6:
                weekly_files.append(week_file)
            else:
                excluded_partial.append(filename)

    if not weekly_files:
        print("Error: No complete weekly files found (all weeks are partial)")
        return []

    print(f"Found {len(all_weekly_files)} total weekly data files")
    if excluded_partial:
        print(f"Excluded {len(excluded_partial)} partial week(s): {', '.join(excluded_partial)}")
    print(f"Using {len(weekly_files)} complete week(s) for analysis\n")

    # Get unique courses from weekly files
    print("Scanning weekly files for active courses...")
    active_courses = set()
    for week_file in weekly_files:  # Check all weeks to find all courses
        df = pd.read_csv(week_file)
        if 'course' in df.columns:
            active_courses.update(df['course'].dropna().unique())
        elif 'course_id' in df.columns:
            active_courses.update(df['course_id'].dropna().unique())

    print(f"Found {len(active_courses)} active courses in weekly data")

    # Filter course_info to only include active courses
    course_info_filtered = course_info[course_info['course_id'].isin(active_courses)]
    print(f"Matched {len(course_info_filtered)} courses with institute information\n")

    # Group courses by institute
    institutes = {}
    for _, row in course_info_filtered.iterrows():
        course_id = row['course_id']
        institute = row.get('institute', 'Unknown')

        # Skip courses with missing institute
        if pd.isna(institute) or institute == 'Unknown':
            continue

        if institute not in institutes:
            institutes[institute] = []
        institutes[institute].append({
            'course_id': course_id,
            'course_name': row.get('course_name', course_id)
        })

    if not institutes:
        print("Error: No courses with valid institute information found")
        return []

    print(f"Found {len(institutes)} institutes:")
    for institute, courses in institutes.items():
        print(f"  - {institute}: {len(courses)} course(s)")
    print()

    # For each institute, calculate metrics for all its courses
    generated_reports = []

    for institute_name, institute_courses in institutes.items():
        print(f"\n{'='*60}")
        print(f"Processing institute: {institute_name}")
        print(f"{'='*60}")
        print(f"Courses: {len(institute_courses)}")

        # Calculate metrics for each course in this institute
        course_metrics = {}
        course_names = {}

        for course_dict in institute_courses:
            course_id = course_dict['course_id']
            course_name = course_dict['course_name']

            print(f"\n  Analyzing course: {course_name} ({course_id})")

            # Initialize analyzer for this course
            analyzer = WeeklyProgressAnalyzer(weekly_files, start_date, end_date, course_id, config)

            # Calculate weekly metrics
            weekly_metrics = analyzer.calculate_weekly_metrics()

            if len(weekly_metrics) == 0:
                print(f"    Warning: No metrics calculated for {course_id}, skipping")
                continue

            print(f"    Calculated metrics for {len(weekly_metrics)} weeks")

            # Add trend and phase metrics
            weekly_metrics = analyzer.calculate_trend_metrics(weekly_metrics)
            weekly_metrics = analyzer.calculate_semester_phase_metrics(weekly_metrics)

            course_metrics[course_id] = weekly_metrics
            course_names[course_id] = course_name

        if not course_metrics:
            print(f"\n  Warning: No metrics calculated for any course in {institute_name}, skipping institute")
            continue

        # Create institute subdirectory
        safe_institute_name = institute_name.replace(' ', '_').replace('/', '_')
        institute_dir = os.path.join(reports_base_dir, safe_institute_name)
        os.makedirs(institute_dir, exist_ok=True)

        # Generate institute report
        print(f"\n  Generating institute HTML report...")
        reporter = InstituteProgressReporter(
            course_metrics=course_metrics,
            course_names=course_names,
            semester_start=start_date,
            semester_end=end_date,
            config=config
        )

        # Generate institute report path in subdirectory
        today = datetime.now().strftime('%Y-%m-%d')
        institute_report_path = os.path.join(institute_dir, f"institute_progress_{safe_institute_name}_{start_date}_{today}.html")

        # Reporter now generates executive summary internally from aggregated data
        reporter.generate_html_report(institute_report_path, institute_name)
        generated_reports.append(institute_report_path)

        print(f"  ✓ Institute report generated: {institute_report_path}")

        # Generate individual course reports in the same institute subdirectory
        print(f"\n  Generating individual course reports...")
        for course_id, weekly_metrics in course_metrics.items():
            course_name = course_names[course_id]
            safe_course_name = course_name.replace(' ', '_').replace('/', '_')

            print(f"    - {course_name}")

            # Create course reporter
            course_reporter = WeeklyProgressReporter(
                weekly_metrics=weekly_metrics,
                course_name=course_name,
                semester_start=start_date,
                semester_end=end_date,
                config=config
            )

            # Generate executive summary for this course
            analyzer = WeeklyProgressAnalyzer(weekly_files, start_date, end_date, course_id, config)
            executive_summary = analyzer.generate_executive_summary(weekly_metrics)

            # Get student leaderboards for this course
            latest_week = int(weekly_metrics.iloc[-1]['week_number'])
            leaderboards = analyzer.get_student_leaderboards(latest_week, top_n=10)

            # Generate course report path in institute subdirectory
            course_report_path = os.path.join(institute_dir, f"course_{safe_course_name}_{start_date}_{today}.html")

            # Generate course report
            course_reporter.generate_html_report(course_report_path, executive_summary, leaderboards)
            generated_reports.append(course_report_path)

        print(f"  ✓ Generated {len(course_metrics)} course report(s)")

    print(f"\n{'='*80}")
    print(f"INSTITUTE PROGRESS REPORTS COMPLETE")
    print(f"Generated {len(generated_reports)} institute report(s)")
    for report in generated_reports:
        print(f"  - {report}")
    print(f"{'='*80}\n")

    return generated_reports


def run_new_reports(config: dict) -> List[str]:
    """
    FUNCTION 6: Generate NEW report format (A, B, C, D)
    - Report A: Weekly Snapshot per course (last complete week)
    - Report C: Dynamics per course (all complete weeks)
    - Report B: Weekly Snapshot per institute (aggregated)
    - Report D: Dynamics per institute (aggregated)

    Saves to: report/new/{institute}/

    Args:
        config: Configuration dictionary

    Returns:
        List of paths to generated reports
    """
    semester_config = config.get('semester', {})
    start_date = semester_config.get('start_date')
    end_date = semester_config.get('end_date')
    weekly_dir = semester_config.get('weekly_output_dir')

    if not start_date:
        print("Error: semester.start_date not configured")
        return []

    if not weekly_dir or not os.path.exists(weekly_dir):
        print("Error: weekly_output_dir not found or does not exist")
        return []

    # Get directory configuration
    export_config = config.get('export', {})
    reports_base_dir = export_config.get('reports_dir', export_config.get('output_dir', '.'))

    print(f"\n{'='*80}")
    print(f"NEW REPORTS GENERATION (A, B, C, D)")
    print(f"{'='*80}")
    print(f"Semester start: {start_date}")
    if end_date:
        print(f"Semester end: {end_date}")
    print(f"Weekly data directory: {weekly_dir}")
    print(f"Reports base directory: {reports_base_dir}")
    print(f"Output: {reports_base_dir}/new/{{institute}}/")
    print(f"{'='*80}\n")

    # Load course information to get institute mappings
    course_info = load_course_list(config)
    if course_info is None:
        print("Error: Could not load course information. Cannot group by institute.")
        return []

    # Check for institute column
    if 'institute' not in course_info.columns:
        print("Error: 'institute' column not found in course information. Cannot group by institute.")
        print(f"Available columns: {list(course_info.columns)}")
        return []

    # Get all weekly files
    all_weekly_files = sorted([
        os.path.join(weekly_dir, f)
        for f in os.listdir(weekly_dir)
        if f.startswith('week_') and f.endswith('.csv')
    ])

    if not all_weekly_files:
        print("Error: No weekly files found")
        return []

    # Filter to only complete weeks (exclude current partial week)
    today = datetime.now().date()
    weekly_files = []
    excluded_partial = []

    for week_file in all_weekly_files:
        filename = os.path.basename(week_file)
        parts = filename.replace('.csv', '').split('_')
        # New format: week_2025-10-18_2025-10-24.csv (3 parts)
        # Old format: week_01_2025-10-18_2025-10-24.csv (4 parts)
        if len(parts) >= 3:
            if len(parts) == 3:
                # New format without week number
                from_date_str = parts[1]
                to_date_str = parts[2]
            else:
                # Old format with week number
                from_date_str = parts[2]
                to_date_str = parts[3]

            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            week_duration = (to_date - from_date).days + 1

            if to_date < today and week_duration >= 6:
                weekly_files.append(week_file)
            else:
                excluded_partial.append(filename)

    if not weekly_files:
        print("Error: No complete weekly files found (all weeks are partial)")
        return []

    print(f"Found {len(all_weekly_files)} total weekly data files")
    if excluded_partial:
        print(f"Excluded {len(excluded_partial)} partial week(s): {', '.join(excluded_partial)}")
    print(f"Using {len(weekly_files)} complete week(s) for analysis\n")

    # Get unique courses from weekly files
    print("Scanning weekly files for active courses...")
    active_courses = set()
    for week_file in weekly_files:
        df = pd.read_csv(week_file)
        if 'course' in df.columns:
            active_courses.update(df['course'].dropna().unique())
        elif 'course_id' in df.columns:
            active_courses.update(df['course_id'].dropna().unique())

    print(f"Found {len(active_courses)} active courses in weekly data")

    # Filter course_info to only include active courses
    course_info_filtered = course_info[course_info['course_id'].isin(active_courses)]
    print(f"Matched {len(course_info_filtered)} courses with institute information\n")

    # Group courses by institute
    institutes = {}
    for _, row in course_info_filtered.iterrows():
        course_id = row['course_id']
        institute = row.get('institute', 'Unknown')

        if pd.isna(institute) or institute == 'Unknown':
            continue

        if institute not in institutes:
            institutes[institute] = []
        institutes[institute].append({
            'course_id': course_id,
            'course_name': row.get('course_name', course_id)
        })

    if not institutes:
        print("Error: No courses with valid institute information found")
        return []

    print(f"Found {len(institutes)} institutes:")
    for institute, courses in institutes.items():
        print(f"  - {institute}: {len(courses)} course(s)")
    print()

    # For each institute, generate all 4 report types
    generated_reports = []

    for institute_name, institute_courses in institutes.items():
        print(f"\n{'='*60}")
        print(f"Processing institute: {institute_name}")
        print(f"{'='*60}")
        print(f"Courses: {len(institute_courses)}")

        # Calculate metrics for each course in this institute
        course_metrics = {}

        for course_dict in institute_courses:
            course_id = course_dict['course_id']
            course_name = course_dict['course_name']

            print(f"\n  Analyzing course: {course_name} ({course_id})")

            # Initialize analyzer for this course
            analyzer = WeeklyProgressAnalyzer(weekly_files, start_date, end_date, course_id, config)

            # Calculate weekly metrics
            weekly_metrics = analyzer.calculate_weekly_metrics()

            if len(weekly_metrics) == 0:
                print(f"    Warning: No metrics calculated for {course_id}, skipping")
                continue

            print(f"    Calculated metrics for {len(weekly_metrics)} weeks")

            # Add trend and phase metrics
            weekly_metrics = analyzer.calculate_trend_metrics(weekly_metrics)
            weekly_metrics = analyzer.calculate_semester_phase_metrics(weekly_metrics)

            course_metrics[course_name] = weekly_metrics

        if not course_metrics:
            print(f"\n  Warning: No metrics calculated for any course in {institute_name}, skipping institute")
            continue

        print(f"\n  Generating NEW reports for {institute_name}...")

        # Generate per-course reports (A & C)
        print(f"  Generating per-course reports...")
        for course_name, weekly_metrics in course_metrics.items():
            # Create report generator for this course
            reporter = NewWeeklyReportsGenerator(
                weekly_metrics=weekly_metrics,
                course_name=course_name,
                institute_name=institute_name,
                config=config
            )

            # Generate Report A: Snapshot (last week)
            print(f"    - {course_name}: Snapshot (Report A)")
            reporter.generate_snapshot_report(reports_base_dir)

            # Generate Report C: Dynamics (all weeks)
            print(f"    - {course_name}: Dynamics (Report C)")
            reporter.generate_dynamics_report(reports_base_dir)

        # Generate institute-level reports (B & D)
        print(f"\n  Generating institute-level reports...")
        institute_reporter = NewInstituteReportsGenerator(
            courses_metrics=course_metrics,
            institute_name=institute_name,
            config=config
        )

        # Generate Report B: Institute Snapshot
        print(f"    - {institute_name}: Institute Snapshot (Report B)")
        institute_reporter.generate_snapshot_report(reports_base_dir)

        # Generate Report D: Institute Dynamics
        print(f"    - {institute_name}: Institute Dynamics (Report D)")
        institute_reporter.generate_dynamics_report(reports_base_dir)

        # Add to generated reports list
        safe_institute_name = institute_name.replace(' ', '_').replace('/', '_')
        new_report_dir = os.path.join(reports_base_dir, "new", safe_institute_name)
        generated_reports.append(new_report_dir)

        print(f"  ✓ Generated 4 report types for {institute_name}")
        print(f"    + {len(course_metrics)} courses × 2 reports (A, C)")
        print(f"    + 1 institute × 2 reports (B, D)")
        print(f"    = {len(course_metrics) * 2 + 2} total reports")

    print(f"\n{'='*80}")
    print(f"NEW REPORTS GENERATION COMPLETE")
    print(f"Generated reports for {len(institutes)} institute(s)")
    for report_dir in generated_reports:
        print(f"  - {report_dir}/")
    print(f"{'='*80}\n")

    return generated_reports


def run_all(config: dict):
    """
    Orchestrate full process based on config
    - Step 1: get_recent_data() if enabled (extract new weekly data from Mixpanel)
    - Step 2: run_new_reports() to generate all reports (A, B, C, D)

    Args:
        config: Configuration dictionary
    """
    semester_config = config.get('semester', {})

    # Get settings from config
    do_extract = semester_config.get('run_data_extraction', True)

    print(f"\n{'='*80}")
    print(f"RUN ALL - FULL PROCESS")
    print(f"{'='*80}")
    print(f"Step 1 - Extract recent data: {do_extract}")
    print(f"Step 2 - Generate new reports (A, B, C, D): True")
    print(f"{'='*80}\n")

    # Step 1: Extract recent data
    if do_extract:
        new_weeks = get_recent_data(config)
        if new_weeks > 0:
            print(f"✓ Extracted {new_weeks} new week(s)\n")
        else:
            print(f"✓ No new weeks to extract\n")

    # Step 2: Generate new reports
    print(f"Generating new reports (A, B, C, D)...")
    generated_reports = run_new_reports(config)
    if generated_reports:
        print(f"✓ Reports generated successfully\n")
    else:
        print(f"✗ Report generation failed\n")

    print(f"\n{'='*80}")
    print(f"RUN ALL COMPLETE")
    print(f"{'='*80}\n")


def main():
    """Main entry point for semester analytics"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Semester Analytics - Modular data extraction and reporting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --get-recent          # Extract only new weeks since last run
  %(prog)s --semester            # Generate semester report from all weeks
  %(prog)s --weekly              # Generate weekly report (latest or from config)
  %(prog)s --weekly --week 5     # Generate report for week 5
  %(prog)s --progress            # Generate weekly progress report (all courses)
  %(prog)s --progress --course-id 123  # Generate weekly progress for specific course
  %(prog)s --all                 # Run full process based on config settings
        """
    )
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--get-recent', action='store_true',
                       help='[FUNCTION 1] Extract only NEW weeks since last extraction')
    parser.add_argument('--semester', action='store_true',
                       help='[FUNCTION 2] Generate semester report from all weekly files')
    parser.add_argument('--weekly', action='store_true',
                       help='[FUNCTION 3] Generate weekly report for specific week')
    parser.add_argument('--week', type=int, metavar='N',
                       help='Week number for --weekly (default: latest or from config)')
    parser.add_argument('--progress', action='store_true',
                       help='[FUNCTION 4] Generate weekly progress report with engagement analysis')
    parser.add_argument('--course-id', type=str, metavar='ID',
                       help='Course ID for --progress (default: all courses or from config)')
    parser.add_argument('--institute-progress', action='store_true',
                       help='[FUNCTION 5] Generate institute-level weekly progress reports (one per institute)')
    parser.add_argument('--all', action='store_true',
                       help='[FUNCTION 6] Run full process based on config settings')

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    # Execute requested operation
    if args.get_recent:
        get_recent_data(config)
    elif args.semester:
        run_semester_report(config)
    elif args.weekly:
        run_weekly_report(config, args.week)
    elif args.progress:
        # Get course_id from CLI or config
        course_id = args.course_id if hasattr(args, 'course_id') and args.course_id else \
                   config.get('semester', {}).get('progress_course_id', None)
        run_weekly_progress(config, course_id)
    elif args.institute_progress:
        run_institute_progress(config)
    elif args.all:
        run_all(config)
    else:
        # No CLI args - use config to determine what to run
        run_all(config)


if __name__ == '__main__':
    main()
