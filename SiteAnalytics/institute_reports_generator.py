#!/usr/bin/env python3
"""
New Institute Reports Generator
Generates Report B (Snapshot) and Report D (Dynamics) for institutes
with collapsible per-course breakdowns
Saves to report/new/{institute}/
"""

import pandas as pd
import os
from typing import Dict, List
import json


class NewInstituteReportsGenerator:
    """Generates institute-level weekly reports (B & D) with per-course breakdowns"""

    def __init__(self, courses_metrics: Dict[str, pd.DataFrame], institute_name: str, config: dict = None):
        """
        Initialize report generator

        Args:
            courses_metrics: Dict mapping course_name -> weekly_metrics DataFrame
            institute_name: Name of the institute
            config: Configuration dictionary
        """
        self.courses_metrics = courses_metrics
        self.institute_name = institute_name
        self.config = config or {}

        # Load scoring configuration from config
        report_config = self.config.get('report', {})
        engagement_config = report_config.get('engagement_scoring', {})
        feature_config = report_config.get('feature_scoring', {})

        # Engagement scoring parameters
        self.eng_consistent_weight = engagement_config.get('consistent_weight', 10)
        self.eng_moderate_weight = engagement_config.get('moderate_weight', 3)
        self.eng_sporadic_weight = engagement_config.get('sporadic_weight', 1)
        self.eng_expected_consistent = engagement_config.get('expected_consistent_pct', 5)
        self.eng_expected_moderate = engagement_config.get('expected_moderate_pct', 25)
        self.eng_expected_sporadic = engagement_config.get('expected_sporadic_pct', 70)

        # Feature scoring parameters
        self.feat_high_weight = feature_config.get('high_weight', 5)
        self.feat_moderate_weight = feature_config.get('moderate_weight', 3)
        self.feat_low_weight = feature_config.get('low_weight', 1)
        self.feat_high_threshold = feature_config.get('high_threshold', 40)
        self.feat_moderate_threshold = feature_config.get('moderate_threshold', 20)

    def _format_time_hms(self, minutes: float) -> str:
        """Format minutes as h:m:s"""
        total_seconds = int(minutes * 60)
        hours = total_seconds // 3600
        mins = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours}:{mins:02d}:{secs:02d}"

    def _normalize_score(self, score: float, min_val: float, expected_val: float, max_val: float) -> float:
        """
        Normalize score to 0-100 scale where expected = 50
        """
        if score <= min_val:
            return 0.0
        elif score >= max_val:
            return 100.0
        elif score < expected_val:
            return ((score - min_val) / (expected_val - min_val)) * 50
        else:
            return 50 + ((score - expected_val) / (max_val - expected_val)) * 50

    def _get_metric_color(self, metric_type: str, value: float) -> tuple:
        """Determine background and text color based on metric type and value"""
        if value > 60:
            return ('#c8e6c9', '#1b5e20')  # Green
        elif value >= 26:
            return ('#fff9c4', '#f57f17')  # Yellow
        else:
            return ('#ffcdd2', '#b71c1c')  # Red

    def generate_snapshot_report(self, output_dir: str):
        """Generate Report B: Institute Weekly Snapshot (Last complete week)"""
        if not self.courses_metrics:
            print(f"No data for {self.institute_name}, skipping institute snapshot")
            return

        report_dir = os.path.join(output_dir, "new", self.institute_name)
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, f"{self.institute_name}_institute_snapshot.html")

        html = self._generate_snapshot_html()

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Institute snapshot report generated: {output_path}")

    def generate_dynamics_report(self, output_dir: str):
        """Generate Report D: Institute Dynamics (All complete weeks)"""
        if not self.courses_metrics:
            print(f"No data for {self.institute_name}, skipping institute dynamics")
            return

        report_dir = os.path.join(output_dir, "new", self.institute_name)
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, f"{self.institute_name}_institute_dynamics.html")

        html = self._generate_dynamics_html()

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Institute dynamics report generated: {output_path}")

    def _generate_snapshot_html(self) -> str:
        """Generate HTML for Report B: Institute Snapshot"""
        # Aggregate latest week metrics
        total_wau = 0
        total_enrolled = 0
        all_median_times = []
        feature_totals = {}
        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']

        course_data = []

        for course_name, metrics in self.courses_metrics.items():
            if len(metrics) == 0:
                continue

            latest = metrics.iloc[-1]
            wau_count = int(latest.get('wau_count', 0))
            enrolled = int(latest.get('total_enrolled', 0))
            median_time = latest.get('median_weekly_time_minutes', 0)

            total_wau += wau_count
            total_enrolled += enrolled
            if wau_count > 0:
                all_median_times.append(median_time)

            # Aggregate features
            for feature in features:
                usage_col = f'feature_usage_{feature}'
                time_col = f'feature_time_{feature}_minutes'
                usage_pct = latest.get(usage_col, 0)
                time_min = latest.get(time_col, 0)
                user_count = int((usage_pct / 100) * wau_count) if wau_count > 0 else 0

                if feature not in feature_totals:
                    feature_totals[feature] = {'count': 0, 'time': 0}

                feature_totals[feature]['count'] += user_count
                feature_totals[feature]['time'] += time_min

            course_data.append({
                'name': course_name,
                'wau': wau_count,
                'enrolled': enrolled,
                'wau_pct': (wau_count / enrolled * 100) if enrolled > 0 else 0,
                'median_time': median_time
            })

        inst_wau_pct = (total_wau / total_enrolled * 100) if total_enrolled > 0 else 0
        inst_median_time = pd.Series(all_median_times).median() if all_median_times else 0
        inst_median_time_hms = self._format_time_hms(inst_median_time)

        # Feature scores
        high_count = 0
        moderate_count = 0
        low_count = 0
        feature_table_rows = ""

        for i, feature in enumerate(features):
            if feature in feature_totals:
                count = feature_totals[feature]['count']
                time = feature_totals[feature]['time']
                usage_pct = (count / total_wau * 100) if total_wau > 0 else 0

                if usage_pct >= self.feat_high_threshold:
                    high_count += 1
                    status = "🟢"
                elif usage_pct >= self.feat_moderate_threshold:
                    moderate_count += 1
                    status = "🟡"
                else:
                    low_count += 1
                    status = "⚫"

                time_hms = self._format_time_hms(time)
                feature_table_rows += f"""
                <tr>
                    <td>{feature_labels[i]}</td>
                    <td style="text-align: center;">{usage_pct:.1f}% {status}</td>
                    <td style="text-align: center;">{time_hms}</td>
                </tr>
                """

        # Calculate and normalize feature score (expected = 50)
        expected_feat_score_raw = (self.feat_high_weight * 2 + self.feat_moderate_weight * 3 + self.feat_low_weight * 2) / len(features)
        raw_feature_score = (high_count * self.feat_high_weight +
                        moderate_count * self.feat_moderate_weight +
                        low_count * self.feat_low_weight) / len(features)
        feature_score = self._normalize_score(
            raw_feature_score,
            self.feat_low_weight,
            expected_feat_score_raw,
            self.feat_high_weight
        )

        # Course breakdown for median time
        course_time_rows = ""
        for course in sorted(course_data, key=lambda x: x['median_time'], reverse=True):
            time_hms = self._format_time_hms(course['median_time'])
            course_time_rows += f"""
            <tr>
                <td>{course['name']}</td>
                <td style="text-align: center;">{time_hms}</td>
            </tr>
            """

        # Course breakdown for activity
        course_activity_rows = ""
        for course in sorted(course_data, key=lambda x: x['wau'], reverse=True):
            time_hms = self._format_time_hms(course['median_time'])
            course_activity_rows += f"""
            <tr>
                <td>{course['name']}</td>
                <td style="text-align: center;">{course['wau']}</td>
                <td style="text-align: center;">{course['wau_pct']:.1f}% (of {course['enrolled']})</td>
                <td style="text-align: center;">{time_hms}</td>
            </tr>
            """

        # Executive summary
        top_active = sorted(course_data, key=lambda x: x['wau'], reverse=True)[:3]
        top_time = sorted(course_data, key=lambda x: x['median_time'], reverse=True)[:3]

        # Get date range from latest week across all courses
        latest_from_date = None
        latest_to_date = None
        latest_week_num = None
        for metrics in self.courses_metrics.values():
            if len(metrics) > 0:
                latest = metrics.iloc[-1]
                from_date = pd.to_datetime(latest['from_date'])
                to_date = pd.to_datetime(latest['to_date'])
                week_num = int(latest.get('week_number', 0))
                if latest_from_date is None or from_date > latest_from_date:
                    latest_from_date = from_date
                    latest_to_date = to_date
                    latest_week_num = week_num

        week_str = f"Week {latest_week_num}: {latest_from_date.strftime('%b %d, %Y')} - {latest_to_date.strftime('%b %d, %Y')}" if latest_from_date else "Last Complete Week"

        exec_summary = f"""
        <strong>Total Enrolled:</strong> {total_enrolled} students across {len(self.courses_metrics)} courses<br>
        <strong>Total Active:</strong> {total_wau} students ({inst_wau_pct:.1f}%)<br>
        <strong>Median Time:</strong> {inst_median_time_hms} per student<br>
        <strong>Top Active Courses:</strong> {', '.join([c['name'] for c in top_active])}<br>
        <strong>Top Engagement (Time):</strong> {', '.join([c['name'] for c in top_time])}
        """

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Institute Snapshot: {self.institute_name} - {week_str}</title>
    {self._get_common_styles()}
</head>
<body>
    <div class="header">
        <h1>🏛️ Institute Weekly Snapshot</h1>
        <p><strong>{self.institute_name}</strong></p>
        <p>{week_str}</p>
    </div>

    <div class="executive-summary">
        <h2>📋 Executive Summary</h2>
        <p>{exec_summary}</p>
    </div>

    <div class="section">
        <h2>2. Institute Activity Rate</h2>
        <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px; margin-bottom: 20px;">
            <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{inst_wau_pct:.1f}%</div>
            <div style="color: #666; font-size: 1.1em;">Institute Activity Rate</div>
            <div style="color: #999; font-size: 0.9em;">Registered: {total_enrolled}</div>
        </div>

        <details>
            <summary>📊 Per-Course Activity Breakdown (Click to Expand)</summary>
            <table style="margin-top: 15px;">
                <tr>
                    <th>Course</th>
                    <th style="text-align: center;">Active Users</th>
                    <th style="text-align: center;">Activity % (of registered)</th>
                    <th style="text-align: center;">Median Time</th>
                </tr>
                {course_activity_rows}
            </table>
        </details>
    </div>

    <div class="section">
        <h2>3. Median Weekly Time Per Student</h2>
        <div style="text-align: center; padding: 30px; background: #f3e5f5; border-radius: 8px; margin-bottom: 20px;">
            <div style="font-size: 3em; font-weight: bold; color: #764ba2;">{inst_median_time_hms}</div>
            <div style="color: #666; font-size: 1.2em;">Institute Median Weekly Time</div>
        </div>

        <details>
            <summary>📊 Per-Course Time Breakdown (Click to Expand)</summary>
            <table style="margin-top: 15px;">
                <tr>
                    <th>Course</th>
                    <th style="text-align: center;">Median Time (h:m:s)</th>
                </tr>
                {course_time_rows}
            </table>
        </details>
    </div>

    <div class="section">
        <h2>3. Feature Usage - Institute Total</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div style="padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="text-align: center;">
                    <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{feature_score:.1f}</div>
                    <div style="color: #1565c0; font-weight: 600; font-size: 1.1em;">Feature Usage Score</div>
                    <div style="font-size: 0.9em; color: #666;">Out of 100</div>
                </div>
            </div>
            <div style="padding: 20px; background: #f8f9fa; border-radius: 8px;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #2e7d32;">{high_count}</div>
                        <div style="color: #1b5e20; font-weight: 600; font-size: 0.9em;">High</div>
                        <div style="font-size: 0.75em; color: #666;">>={self.feat_high_threshold}%</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #f57c00;">{moderate_count}</div>
                        <div style="color: #e65100; font-weight: 600; font-size: 0.9em;">Moderate</div>
                        <div style="font-size: 0.75em; color: #666;">{self.feat_moderate_threshold}-{self.feat_high_threshold-1}%</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #c62828;">{low_count}</div>
                        <div style="color: #b71c1c; font-weight: 600; font-size: 0.9em;">Low</div>
                        <div style="font-size: 0.75em; color: #666;"><{self.feat_moderate_threshold}%</div>
                    </div>
                </div>
            </div>
        </div>
        <table>
            <tr>
                <th>Feature</th>
                <th style="text-align: center;">Usage % (Status)</th>
                <th style="text-align: center;">Total Time</th>
            </tr>
            {feature_table_rows}
        </table>
        <p style="font-size: 0.9em; color: #666; margin-top: 15px;">
            🟢 High: >={self.feat_high_threshold}% | 🟡 Moderate: {self.feat_moderate_threshold}-{self.feat_high_threshold-1}% | ⚫ Low: <{self.feat_moderate_threshold}%
        </p>
    </div>

    {self._get_footer()}
</body>
</html>
"""

    def _generate_dynamics_html(self) -> str:
        """Generate HTML for Report D: Institute Dynamics"""
        # Get all weeks
        all_weeks = set()
        for metrics in self.courses_metrics.values():
            for _, row in metrics.iterrows():
                all_weeks.add(pd.to_datetime(row['from_date']))
        all_weeks = sorted(list(all_weeks))

        # Aggregate by week
        weekly_data = []
        for week_date in all_weeks:
            week_wau = 0
            week_enrolled = 0
            week_median_times = []
            week_consistent = []
            week_moderate = []
            week_sporadic = []
            week_coverage_count = 0  # Sum of coverage_count across courses
            week_wau_pct_of_active_weighted_sum = 0
            week_cumulative_active = 0

            for metrics in self.courses_metrics.values():
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == week_date:
                        wau = int(row.get('wau_count', 0))
                        enrolled = int(row.get('total_enrolled', 0))
                        wau_pct_of_active = row.get('wau_percentage_of_active', 0)
                        cumulative_active = int(row.get('cumulative_active_users', 0))
                        coverage_count = int(row.get('coverage_count', 0))
                        week_wau += wau
                        week_enrolled += enrolled
                        week_wau_pct_of_active_weighted_sum += wau * wau_pct_of_active
                        week_cumulative_active += cumulative_active
                        week_coverage_count += coverage_count

                        if wau > 0:
                            week_median_times.append(row.get('median_weekly_time_minutes', 0))

                        week_consistent.append(row.get('persistent_consistent_pct', 0))
                        week_moderate.append(row.get('persistent_moderate_pct', 0))
                        week_sporadic.append(row.get('persistent_sporadic_pct', 0))
                        break

            weekly_data.append({
                'date': week_date,
                'wau': week_wau,
                'enrolled': week_enrolled,
                'wau_pct': (week_wau / week_enrolled * 100) if week_enrolled > 0 else 0,
                'wau_pct_of_active': (week_wau_pct_of_active_weighted_sum / week_wau) if week_wau > 0 else 0,
                'cumulative_active_users': week_cumulative_active,
                'median_time': pd.Series(week_median_times).median() if week_median_times else 0,
                'consistent': pd.Series(week_consistent).mean() if week_consistent else 0,
                'moderate': pd.Series(week_moderate).mean() if week_moderate else 0,
                'sporadic': pd.Series(week_sporadic).mean() if week_sporadic else 0,
                'coverage': (week_coverage_count / week_cumulative_active * 100) if week_cumulative_active > 0 else 0
            })

        # Calculate engagement scores (normalized to 0-100 where expected = 50)
        expected_score_raw = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                         (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                         (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)

        eng_scores = []  # Normalized scores (0-100, expected=50)
        for w in weekly_data:
            if w['enrolled'] > 0:
                cons_cnt = (w['consistent'] / 100) * w['enrolled']
                mod_cnt = (w['moderate'] / 100) * w['enrolled']
                spor_cnt = (w['sporadic'] / 100) * w['enrolled']
                score_raw = (cons_cnt * self.eng_consistent_weight +
                        mod_cnt * self.eng_moderate_weight +
                        spor_cnt * self.eng_sporadic_weight) / w['enrolled']
                score_normalized = self._normalize_score(
                    score_raw,
                    self.eng_sporadic_weight,
                    expected_score_raw,
                    self.eng_consistent_weight
                )
                eng_scores.append(score_normalized)
            else:
                eng_scores.append(None)

        # Prepare chart data
        date_labels = [w['date'].strftime('%b %d') for w in weekly_data]
        wau_counts = [w['wau'] for w in weekly_data]
        wau_pcts = [w['wau_pct'] for w in weekly_data]
        wau_pcts_of_active = [w['wau_pct_of_active'] for w in weekly_data]
        median_times = [w['median_time'] for w in weekly_data]
        consistent_data = [w['consistent'] for w in weekly_data]
        moderate_data = [w['moderate'] for w in weekly_data]
        sporadic_data = [w['sporadic'] for w in weekly_data]
        coverage_data = [w['coverage'] for w in weekly_data]

        # Make coverage monotonic (cumulative max)
        monotonic_coverage = []
        max_coverage = 0
        for cov in coverage_data:
            max_coverage = max(max_coverage, cov)
            monotonic_coverage.append(max_coverage)
        coverage_data = monotonic_coverage

        # Calculate coverage from registered (% of potential)
        coverage_from_registered_data = []
        for w in weekly_data:
            week_coverage_count = 0
            week_enrolled = 0
            for metrics in self.courses_metrics.values():
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == w['date']:
                        week_coverage_count += int(row.get('coverage_count', 0))
                        week_enrolled += int(row.get('total_enrolled', 0))
                        break
            coverage_from_reg_pct = (week_coverage_count / week_enrolled * 100) if week_enrolled > 0 else 0
            coverage_from_registered_data.append(coverage_from_reg_pct)

        # Make coverage from registered monotonic (cumulative max)
        monotonic_coverage_from_reg = []
        max_coverage_from_reg = 0
        for cov in coverage_from_registered_data:
            max_coverage_from_reg = max(max_coverage_from_reg, cov)
            monotonic_coverage_from_reg.append(max_coverage_from_reg)
        coverage_from_registered_data = monotonic_coverage_from_reg

        # Collect per-course WAU data for stacked chart (absolute counts)
        course_wau_datasets = []
        course_colors = ['#e57373', '#64b5f6', '#81c784', '#ffb74d', '#ba68c8', '#4db6ac', '#ff8a65', '#4fc3f7', '#aed581']
        course_idx = 0

        for course_name, metrics in self.courses_metrics.items():
            course_wau_by_week = []
            for week_date in all_weeks:
                found = False
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == week_date:
                        wau_count = int(row.get('wau_count', 0))
                        course_wau_by_week.append(wau_count)
                        found = True
                        break
                if not found:
                    course_wau_by_week.append(0)

            course_wau_datasets.append({
                'label': course_name,
                'data': course_wau_by_week,
                'borderColor': course_colors[course_idx % len(course_colors)],
                'backgroundColor': f'rgba({int(course_colors[course_idx % len(course_colors)][1:3], 16)}, {int(course_colors[course_idx % len(course_colors)][3:5], 16)}, {int(course_colors[course_idx % len(course_colors)][5:7], 16)}, 0.25)',
                'borderWidth': 1,
                'tension': 0.4,
                'fill': True,
                'yAxisID': 'y'
            })
            course_idx += 1

        # Cumulative time
        cumulative_times = []
        running_total = 0
        for time in median_times:
            running_total += time
            cumulative_times.append(running_total)

        # Latest values
        latest = weekly_data[-1] if weekly_data else {}
        latest_wau_pct = latest.get('wau_pct', 0)
        latest_wau_pct_of_active = latest.get('wau_pct_of_active', 0)
        total_enrolled = latest.get('enrolled', 0)
        latest_time = cumulative_times[-1] if cumulative_times else 0
        latest_time_hms = self._format_time_hms(latest_time)
        # Get latest engagement score (already normalized)
        latest_eng_score = eng_scores[-1] if eng_scores and eng_scores[-1] is not None else 0

        # Chart axis ranges use 0-100 scale with expected at 50
        eng_axis_min = 0
        eng_axis_max = 100

        # Course breakdown for engagement and retention
        course_eng_data = []
        course_retention_data = []
        for course_name, metrics in self.courses_metrics.items():
            if len(metrics) > 0:
                latest_course = metrics.iloc[-1]
                cons = latest_course.get('persistent_consistent_pct', 0)
                mod = latest_course.get('persistent_moderate_pct', 0)
                spor = latest_course.get('persistent_sporadic_pct', 0)
                enr = latest_course.get('total_enrolled', 0)
                cov = latest_course.get('coverage_pct', 0)
                cumulative_active = int(latest_course.get('cumulative_active_users', 0))
                coverage_count = int(latest_course.get('coverage_count', 0))

                if enr > 0:
                    score_raw = ((cons / 100) * enr * self.eng_consistent_weight +
                            (mod / 100) * enr * self.eng_moderate_weight +
                            (spor / 100) * enr * self.eng_sporadic_weight) / enr
                    score_normalized = self._normalize_score(
                        score_raw,
                        self.eng_sporadic_weight,
                        expected_score_raw,
                        self.eng_consistent_weight
                    )
                    course_eng_data.append({'name': course_name, 'score': score_normalized})

                    # Use coverage_count directly (count of users active ≥2 weeks)
                    repeating_from_active_pct = (coverage_count / cumulative_active * 100) if cumulative_active > 0 else 0

                    course_retention_data.append({
                        'name': course_name,
                        'retention': cov,
                        'total_active': cumulative_active,
                        'registered': int(enr),
                        'repeating_users': coverage_count,
                        'active_pct': (cumulative_active / enr * 100) if enr > 0 else 0,
                        'repeating_from_active_pct': repeating_from_active_pct
                    })

        course_eng_rows = ""
        for course in sorted(course_eng_data, key=lambda x: x['score'], reverse=True):
            course_eng_rows += f"""
            <tr>
                <td>{course['name']}</td>
                <td style="text-align: center;">{course['score']:.2f}</td>
            </tr>
            """

        # Retention score table
        course_retention_rows = ""
        for course in sorted(course_retention_data, key=lambda x: x['retention'], reverse=True):
            course_retention_rows += f"""
            <tr>
                <td>{course['name']}</td>
                <td style="text-align: center;">{course['registered']}</td>
                <td style="text-align: center;">{course['total_active']}</td>
                <td style="text-align: center;">{course['repeating_users']}</td>
                <td style="text-align: center;">{course['active_pct']:.1f}%</td>
                <td style="text-align: center;">{course['repeating_from_active_pct']:.1f}%</td>
            </tr>
            """

        # Course breakdown for time
        course_time_data = []
        for course_name, metrics in self.courses_metrics.items():
            if len(metrics) > 0:
                times = [row.get('median_weekly_time_minutes', 0) for _, row in metrics.iterrows()]
                times_students = [row.get('median_weekly_time_students_minutes', 0) for _, row in metrics.iterrows()]
                times_lecturers = [row.get('median_weekly_time_lecturers_minutes', 0) for _, row in metrics.iterrows()]
                cumulative = sum(times)
                cumulative_students = sum(times_students)
                cumulative_lecturers = sum(times_lecturers)
                course_time_data.append({
                    'name': course_name,
                    'time': cumulative,
                    'time_students': cumulative_students,
                    'time_lecturers': cumulative_lecturers
                })

        course_time_rows = ""
        for course in sorted(course_time_data, key=lambda x: x['time'], reverse=True):
            time_hms = self._format_time_hms(course['time'])
            time_students_hms = self._format_time_hms(course['time_students'])
            time_lecturers_hms = self._format_time_hms(course['time_lecturers'])
            course_time_rows += f"""
            <tr>
                <td>{course['name']}</td>
                <td style="text-align: center;">{time_hms}</td>
                <td style="text-align: center;">{time_students_hms}</td>
                <td style="text-align: center;">{time_lecturers_hms}</td>
            </tr>
            """

        # Feature usage aggregation
        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

        feature_datasets = []
        for i, feature in enumerate(features):
            weekly_usage = []
            for week_date in all_weeks:
                week_total_wau = 0
                week_feature_users = 0

                for metrics in self.courses_metrics.values():
                    for _, row in metrics.iterrows():
                        if pd.to_datetime(row['from_date']) == week_date:
                            wau = int(row.get('wau_count', 0))
                            usage_pct = row.get(f'feature_usage_{feature}', 0)
                            week_total_wau += wau
                            week_feature_users += int((usage_pct / 100) * wau) if wau > 0 else 0
                            break

                usage_pct = (week_feature_users / week_total_wau * 100) if week_total_wau > 0 else 0
                weekly_usage.append(usage_pct)

            feature_datasets.append({
                'label': feature_labels[i],
                'data': weekly_usage,
                'borderColor': colors[i],
                'backgroundColor': 'transparent',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': False
            })

        # Feature scores (normalized to 0-100 where expected = 50) - BASED ON SEMESTER USAGE
        expected_feat_score_raw = (self.feat_high_weight * 2 + self.feat_moderate_weight * 3 + self.feat_low_weight * 2) / len(features)
        feature_scores = []  # Normalized scores (0-100, expected=50)

        for week_date in all_weeks:
            week_total_enrolled = 0
            feature_semester_users = {f: 0 for f in features}

            for metrics in self.courses_metrics.values():
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == week_date:
                        enrolled = int(row.get('total_enrolled', 0))
                        week_total_enrolled += enrolled

                        for feature in features:
                            # Use semester usage data (% of enrolled who used feature >= 2 weeks)
                            semester_pct = row.get(f'feature_semester_{feature}', 0)
                            feature_semester_users[feature] += int((semester_pct / 100) * enrolled) if enrolled > 0 else 0
                        break

            if week_total_enrolled > 0:
                high = sum(1 for f in features if (feature_semester_users[f] / week_total_enrolled * 100) >= self.feat_high_threshold)
                mod = sum(1 for f in features if self.feat_moderate_threshold <= (feature_semester_users[f] / week_total_enrolled * 100) < self.feat_high_threshold)
            else:
                high = 0
                mod = 0
            low = len(features) - high - mod
            score_raw = (high * self.feat_high_weight + mod * self.feat_moderate_weight + low * self.feat_low_weight) / len(features)
            score_normalized = self._normalize_score(
                score_raw,
                self.feat_low_weight,
                expected_feat_score_raw,
                self.feat_high_weight
            )
            feature_scores.append(score_normalized)

        # Chart axis ranges use 0-100 scale with expected at 50
        feat_axis_min = 0
        feat_axis_max = 100

        # Latest feature table
        latest_week_date = all_weeks[-1] if all_weeks else None
        feature_table_rows = ""
        if latest_week_date:
            week_total_wau = 0
            week_total_enrolled = 0
            feature_usage = {f: 0 for f in features}
            feature_semester_users = {f: 0 for f in features}

            for metrics in self.courses_metrics.values():
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == latest_week_date:
                        wau = int(row.get('wau_count', 0))
                        enrolled = int(row.get('total_enrolled', 0))
                        week_total_wau += wau
                        week_total_enrolled += enrolled

                        for feature in features:
                            # Weekly usage
                            usage_pct = row.get(f'feature_usage_{feature}', 0)
                            feature_usage[feature] += int((usage_pct / 100) * wau) if wau > 0 else 0

                            # Semester usage (% of enrolled who used feature >= 2 weeks)
                            semester_pct = row.get(f'feature_semester_{feature}', 0)
                            feature_semester_users[feature] += int((semester_pct / 100) * enrolled) if enrolled > 0 else 0
                        break

            for i, feature in enumerate(features):
                usage_pct = (feature_usage[feature] / week_total_wau * 100) if week_total_wau > 0 else 0
                semester_usage = (feature_semester_users[feature] / week_total_enrolled * 100) if week_total_enrolled > 0 else 0
                status = "🟢" if usage_pct >= self.feat_high_threshold else ("🟡" if usage_pct >= self.feat_moderate_threshold else "⚫")
                semester_status = "🟢" if semester_usage >= self.feat_high_threshold else ("🟡" if semester_usage >= self.feat_moderate_threshold else "⚫")
                feature_table_rows += f"<tr><td>{feature_labels[i]}</td><td style='text-align: center;'>{usage_pct:.1f}% {status}</td><td style='text-align: center;'>{semester_usage:.1f}% {semester_status}</td></tr>"

            # Calculate H/M/L counts for semester and weekly usage
            sem_high = sum(1 for f in features if (feature_semester_users[f] / week_total_enrolled * 100) >= self.feat_high_threshold if week_total_enrolled > 0)
            sem_moderate = sum(1 for f in features if self.feat_moderate_threshold <= (feature_semester_users[f] / week_total_enrolled * 100) < self.feat_high_threshold if week_total_enrolled > 0)
            sem_low = len(features) - sem_high - sem_moderate

            weekly_high = sum(1 for f in features if (feature_usage[f] / week_total_wau * 100) >= self.feat_high_threshold if week_total_wau > 0)
            weekly_moderate = sum(1 for f in features if self.feat_moderate_threshold <= (feature_usage[f] / week_total_wau * 100) < self.feat_high_threshold if week_total_wau > 0)
            weekly_low = len(features) - weekly_high - weekly_moderate

            # Calculate weekly feature score
            weekly_score_raw = (weekly_high * self.feat_high_weight + weekly_moderate * self.feat_moderate_weight + weekly_low * self.feat_low_weight) / len(features)
            latest_weekly_feature_score = self._normalize_score(
                weekly_score_raw,
                self.feat_low_weight,
                expected_feat_score_raw,
                self.feat_high_weight
            )
        else:
            sem_high = sem_moderate = sem_low = 0
            weekly_high = weekly_moderate = weekly_low = 0
            latest_weekly_feature_score = 0

        # Calculate retention (coverage) score
        latest_coverage = coverage_data[-1] if coverage_data else 0

        # Calculate per-course activity
        course_activity_data = []
        for course_name, metrics in self.courses_metrics.items():
            if len(metrics) > 0:
                latest_course = metrics.iloc[-1]
                wau_pct = (latest_course.get('wau_count', 0) / latest_course.get('total_enrolled', 1) * 100) if latest_course.get('total_enrolled', 0) > 0 else 0
                course_activity_data.append({'name': course_name, 'activity': wau_pct})

        # Calculate per-course student retention scores (based on at-risk and reactivation)
        course_student_retention_data = []
        for course_name, metrics in self.courses_metrics.items():
            if len(metrics) > 0:
                latest_course = metrics.iloc[-1]
                at_risk = latest_course.get('at_risk_percentage', 0)
                reactivation = latest_course.get('reactivation_rate', 0)
                retention_score = (100 - at_risk) * 0.7 + reactivation * 0.3
                course_student_retention_data.append({'name': course_name, 'retention_score': retention_score})

        # Get latest feature score (already normalized) - this is SEMESTER score
        latest_semester_feature_score = feature_scores[-1] if feature_scores else 0
        latest_feature_score = latest_semester_feature_score  # For backward compatibility with Executive Summary

        # Calculate weekly feature score for the latest week (will be calculated after we have H/M/L counts)

        # Get feature usage percentages for latest week to find top/bottom
        latest_feature_usage = []
        if latest_week_date:
            week_total_wau = 0
            feature_usage = {f: 0 for f in features}

            for metrics in self.courses_metrics.values():
                for _, row in metrics.iterrows():
                    if pd.to_datetime(row['from_date']) == latest_week_date:
                        wau = int(row.get('wau_count', 0))
                        week_total_wau += wau
                        for feature in features:
                            usage_pct = row.get(f'feature_usage_{feature}', 0)
                            feature_usage[feature] += int((usage_pct / 100) * wau) if wau > 0 else 0
                        break

            for i, feature in enumerate(features):
                usage_pct = (feature_usage[feature] / week_total_wau * 100) if week_total_wau > 0 else 0
                latest_feature_usage.append({'name': feature_labels[i], 'usage': usage_pct})

        # Sort and get top/bottom for all 6 categories
        top_activity = sorted(course_activity_data, key=lambda x: x['activity'], reverse=True)[:1]
        bottom_activity = sorted(course_activity_data, key=lambda x: x['activity'])[:1]
        top_coverage = sorted(course_retention_data, key=lambda x: x['retention'], reverse=True)[:1]
        bottom_coverage = sorted(course_retention_data, key=lambda x: x['retention'])[:1]
        top_eng = sorted(course_eng_data, key=lambda x: x['score'], reverse=True)[:1]
        bottom_eng = sorted(course_eng_data, key=lambda x: x['score'])[:1]
        top_time = sorted(course_time_data, key=lambda x: x['time'], reverse=True)[:1]
        bottom_time = sorted(course_time_data, key=lambda x: x['time'])[:1]
        top_feature = sorted(latest_feature_usage, key=lambda x: x['usage'], reverse=True)[:1] if latest_feature_usage else [{'name': 'N/A', 'usage': 0}]
        bottom_feature = sorted(latest_feature_usage, key=lambda x: x['usage'])[:1] if latest_feature_usage else [{'name': 'N/A', 'usage': 0}]
        top_student_retention = sorted(course_student_retention_data, key=lambda x: x['retention_score'], reverse=True)[:1]
        bottom_student_retention = sorted(course_student_retention_data, key=lambda x: x['retention_score'])[:1]

        # Calculate institute-level student retention score
        institute_at_risk_pcts = []
        institute_reactivation_rates = []
        for metrics in self.courses_metrics.values():
            if len(metrics) > 0:
                latest_course = metrics.iloc[-1]
                institute_at_risk_pcts.append(latest_course.get('at_risk_percentage', 0))
                institute_reactivation_rates.append(latest_course.get('reactivation_rate', 0))

        avg_at_risk = sum(institute_at_risk_pcts) / len(institute_at_risk_pcts) if institute_at_risk_pcts else 0
        avg_reactivation = sum(institute_reactivation_rates) / len(institute_reactivation_rates) if institute_reactivation_rates else 0
        institute_retention_score = (100 - avg_at_risk) * 0.7 + avg_reactivation * 0.3

        # Calculate 6-box metrics for latest week
        latest_week_consistent = consistent_data[-1] if consistent_data else 0
        latest_week_moderate = moderate_data[-1] if moderate_data else 0
        latest_week_sporadic = sporadic_data[-1] if sporadic_data else 0

        # Calculate +/- vs last week for all 6 institute-level metrics
        has_prev_week = len(weekly_data) >= 2
        if has_prev_week:
            prev_weekly = weekly_data[-2]

            # 1. Activity Rate delta
            prev_wau_pct = prev_weekly.get('wau_pct', 0)
            delta_wau_pct = latest_wau_pct - prev_wau_pct

            # 2. Engagement Score delta (already normalized scores)
            prev_eng_score = eng_scores[-2] if len(eng_scores) >= 2 and eng_scores[-2] is not None else latest_eng_score
            delta_eng_score = latest_eng_score - prev_eng_score

            # 3. Cumulative Time delta
            prev_time = cumulative_times[-2] if len(cumulative_times) >= 2 else 0
            delta_time = latest_time - prev_time
            delta_time_hms = self._format_time_hms(delta_time)

            # 4. Coverage delta
            prev_coverage = coverage_data[-2] if len(coverage_data) >= 2 else 0
            delta_coverage = latest_coverage - prev_coverage

            # 5. Feature Score delta (already normalized scores)
            prev_feature_score = feature_scores[-2] if len(feature_scores) >= 2 else latest_feature_score
            delta_feature_score = latest_feature_score - prev_feature_score

            # 6. Student Retention delta
            # Get previous week's institute retention score
            # Need to aggregate from courses for previous week
            prev_week_date = all_weeks[-2] if len(all_weeks) >= 2 else all_weeks[-1]
            prev_at_risk_pcts = []
            prev_reactivation_rates = []
            for metrics in self.courses_metrics.values():
                if len(metrics) >= 2:
                    for _, row in metrics.iterrows():
                        if pd.to_datetime(row['from_date']) == prev_week_date:
                            prev_at_risk_pcts.append(row.get('at_risk_percentage', 0))
                            prev_reactivation_rates.append(row.get('reactivation_rate', 0))
                            break

            prev_avg_at_risk = sum(prev_at_risk_pcts) / len(prev_at_risk_pcts) if prev_at_risk_pcts else avg_at_risk
            prev_avg_reactivation = sum(prev_reactivation_rates) / len(prev_reactivation_rates) if prev_reactivation_rates else avg_reactivation
            prev_institute_retention_score = (100 - prev_avg_at_risk) * 0.7 + prev_avg_reactivation * 0.3
            delta_retention_score = institute_retention_score - prev_institute_retention_score
        else:
            delta_wau_pct = 0
            delta_eng_score = 0
            delta_time = 0
            delta_time_hms = "0:00:00"
            delta_coverage = 0
            delta_feature_score = 0
            delta_retention_score = 0

        # Get date range for title
        first_date = all_weeks[0].strftime('%b %d, %Y') if all_weeks else 'N/A'
        last_date = all_weeks[-1].strftime('%b %d, %Y') if all_weeks else 'N/A'
        num_weeks = len(all_weeks)

        # Calculate colors for the 6 boxes based on metric values
        activity_bg, activity_color = self._get_metric_color('activity_rate', latest_wau_pct)
        engagement_bg, engagement_color = self._get_metric_color('engagement_score', latest_eng_score)
        coverage_bg, coverage_color = self._get_metric_color('coverage', latest_coverage)
        feature_bg, feature_color = self._get_metric_color('engagement_score', latest_feature_score)  # Use same thresholds
        retention_bg, retention_color = self._get_metric_color('retention', institute_retention_score)

        # JSON data
        date_labels_json = json.dumps(date_labels)
        wau_counts_json = json.dumps(wau_counts)
        wau_pcts_json = json.dumps(wau_pcts)
        wau_pcts_of_active_json = json.dumps(wau_pcts_of_active)
        cumulative_times_json = json.dumps(cumulative_times)
        consistent_json = json.dumps(consistent_data)
        moderate_json = json.dumps(moderate_data)
        sporadic_json = json.dumps(sporadic_data)
        eng_scores_json = json.dumps(eng_scores)
        feature_datasets_json = json.dumps(feature_datasets)
        feature_scores_json = json.dumps(feature_scores)
        coverage_data_json = json.dumps(coverage_data)
        coverage_from_registered_json = json.dumps(coverage_from_registered_data)
        course_wau_datasets_json = json.dumps(course_wau_datasets)

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Institute Dynamics: {self.institute_name} ({first_date} - {last_date})</title>
    {self._get_common_styles()}
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>🏛️ Institute Dynamics Report</h1>
        <p><strong>{self.institute_name}</strong></p>
        <p>{num_weeks} Complete Weeks: {first_date} to {last_date}</p>
    </div>

    <div class="executive-summary">
        <h2>📋 Executive Summary</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 20px;">
            <div style="padding: 20px; background: {activity_bg}; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: {activity_color};">{latest_wau_pct_of_active:.1f}%</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Current Activity Rate</div>
                    <div style="font-size: 0.75em; color: #888; margin-top: 3px;">% of Active So Far</div>
                    <div style="font-size: 0.8em; color: #888; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">Total Active So Far: {int(latest.get('cumulative_active_users', 0))}</div>
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_activity[0]['name']} ({top_activity[0]['activity']:.1f}%)</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_activity[0]['name']} ({bottom_activity[0]['activity']:.1f}%)</div>
                </div>
            </div>
            <div style="padding: 20px; background: {coverage_bg}; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: {coverage_color};">{latest_coverage:.1f}%</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Retention (Coverage)</div>
                    {'<div style="font-size: 0.75em; color: ' + ('green' if delta_coverage >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_coverage > 0 else '↓' if delta_coverage < 0 else '—') + f' {delta_coverage:+.1f}% vs last week</div>' if has_prev_week else ''}
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_coverage[0]['name']} ({top_coverage[0]['retention']:.1f}%)</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_coverage[0]['name']} ({bottom_coverage[0]['retention']:.1f}%)</div>
                </div>
            </div>
            <div style="padding: 20px; background: {engagement_bg}; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: {engagement_color};">{latest_eng_score:.2f}</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Consistency Engagement Score</div>
                    {'<div style="font-size: 0.75em; color: ' + ('green' if delta_eng_score >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_eng_score > 0 else '↓' if delta_eng_score < 0 else '—') + f' {delta_eng_score:+.2f} vs last week</div>' if has_prev_week else ''}
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_eng[0]['name']} ({top_eng[0]['score']:.1f})</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_eng[0]['name']} ({bottom_eng[0]['score']:.1f})</div>
                </div>
            </div>
            <div style="padding: 20px; background: #fff3e0; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: #f57c00;">{latest_time_hms}</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Time Spent</div>
                    {'<div style="font-size: 0.75em; color: ' + ('green' if delta_time >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_time > 0 else '↓' if delta_time < 0 else '—') + f' {delta_time_hms} vs last week</div>' if has_prev_week else ''}
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_time[0]['name']} ({self._format_time_hms(top_time[0]['time'])})</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_time[0]['name']} ({self._format_time_hms(bottom_time[0]['time'])})</div>
                </div>
            </div>
            <div style="padding: 20px; background: {feature_bg}; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: {feature_color};">{latest_feature_score:.2f}</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Feature Score</div>
                    {'<div style="font-size: 0.75em; color: ' + ('green' if delta_feature_score >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_feature_score > 0 else '↓' if delta_feature_score < 0 else '—') + f' {delta_feature_score:+.2f} vs last week</div>' if has_prev_week else ''}
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_feature[0]['name']} ({top_feature[0]['usage']:.1f}%)</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_feature[0]['name']} ({bottom_feature[0]['usage']:.1f}%)</div>
                </div>
            </div>
            <div style="padding: 20px; background: {retention_bg}; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: {retention_color};">{institute_retention_score:.1f}</div>
                    <div style="color: #666; font-size: 0.9em; font-weight: 600;">Student Retention</div>
                    {'<div style="font-size: 0.75em; color: ' + ('green' if delta_retention_score >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_retention_score > 0 else '↓' if delta_retention_score < 0 else '—') + f' {delta_retention_score:+.1f} vs last week</div>' if has_prev_week else ''}
                </div>
                <div style="font-size: 0.85em; color: #555; border-top: 1px solid #ddd; padding-top: 8px; margin-top: 8px;">
                    <div style="margin: 3px 0;"><strong>Top:</strong> {top_student_retention[0]['name']} ({top_student_retention[0]['retention_score']:.1f})</div>
                    <div style="margin: 3px 0;"><strong>Bottom:</strong> {bottom_student_retention[0]['name']} ({bottom_student_retention[0]['retention_score']:.1f})</div>
                </div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>1. Cumulative Engagement</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div style="text-align: center; padding: 20px; background: #fff3e0; border-radius: 8px;">
                <div style="font-size: 2.5em; font-weight: bold; color: #f57c00;">{latest_time_hms}</div>
                <div style="color: #666; font-size: 1.1em;">Median Cumulative Time</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{latest_coverage:.1f}%</div>
                <div style="color: #666; font-size: 1.1em;">Repeating Users</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="cumulativeEngagementChart"></canvas>
        </div>

        <details style="margin-top: 20px;">
            <summary>📊 Per-Course Cumulative Time Breakdown (Click to Expand)</summary>
            <table style="margin-top: 15px;">
                <tr>
                    <th>Course</th>
                    <th style="text-align: center;">Cumulative Time (h:m:s)</th>
                    <th style="text-align: center;">Students Median (h:m:s)</th>
                    <th style="text-align: center;">Lecturers Median (h:m:s)</th>
                </tr>
                {course_time_rows}
            </table>
        </details>

        <details style="margin-top: 20px;">
            <summary>📊 Per-Course Retention (Coverage) Breakdown (Click to Expand)</summary>
            <table style="margin-top: 15px;">
                <tr>
                    <th>Course</th>
                    <th style="text-align: center;">Registered</th>
                    <th style="text-align: center;">Active</th>
                    <th style="text-align: center;">Repeated</th>
                    <th style="text-align: center;">% Active from Registered</th>
                    <th style="text-align: center;">% Repeating from Active</th>
                </tr>
                {course_retention_rows}
            </table>
        </details>
    </div>

    <div class="section">
        <h2>2. Institute Active Users Trend</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest.get('wau', 0)}</div>
                <div style="color: #666; font-size: 0.9em;">Active Users (this week)</div>
                <div style="font-size: 0.8em; color: #888; margin-top: 5px;">Active So Far: {int(latest.get('cumulative_active_users', 0))}</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest_wau_pct_of_active:.1f}%</div>
                <div style="color: #666; font-size: 0.9em;">% of Total Active So Far</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest_wau_pct:.1f}%</div>
                <div style="color: #666; font-size: 0.9em;">% of Registered ({total_enrolled})</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="wauChart"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>3. Institute Consistency Engagement Score</h2>
        <div style="padding: 20px; background: #e3f2fd; border-radius: 8px; margin-bottom: 20px;">
            <div style="text-align: center;">
                <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{latest_eng_score:.2f}</div>
                <div style="color: #1565c0; font-weight: 600; font-size: 1.1em;">Consistency Engagement Score</div>
                <div style="font-size: 0.85em; color: {'green' if latest_eng_score >= 50 else 'red'}; margin-top: 8px;">
                    {latest_eng_score:.1f}/100 (Expected: 50)
                </div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="engagementChart"></canvas>
        </div>

        <details style="margin-top: 20px;">
            <summary>📊 Per-Course Engagement Breakdown (Click to Expand)</summary>
            <table style="margin-top: 15px;">
                <tr>
                    <th>Course</th>
                    <th style="text-align: center;">Consistency Engagement Score</th>
                </tr>
                {course_eng_rows}
            </table>
        </details>
    </div>

    <div class="section">
        <h2>4. Feature Usage Trends</h2>
        <div style="padding: 15px; background: #f3f4f6; border-left: 4px solid #667eea; border-radius: 8px; margin-bottom: 20px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Semester Usage Score (≥2 weeks)</div>
                    <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest_feature_score:.2f}/100</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #2e7d32;">{sem_high}</div>
                        <div style="color: #1b5e20; font-weight: 600; font-size: 0.75em;">High</div>
                        <div style="font-size: 0.65em; color: #666;">>={self.feat_high_threshold}%</div>
                    </div>
                    <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #f57c00;">{sem_moderate}</div>
                        <div style="color: #e65100; font-weight: 600; font-size: 0.75em;">Moderate</div>
                        <div style="font-size: 0.65em; color: #666;">{self.feat_moderate_threshold}-{self.feat_high_threshold-1}%</div>
                    </div>
                    <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #c62828;">{sem_low}</div>
                        <div style="color: #b71c1c; font-weight: 600; font-size: 0.75em;">Low</div>
                        <div style="font-size: 0.65em; color: #666;"><{self.feat_moderate_threshold}%</div>
                    </div>
                </div>
            </div>
            <div style="border-top: 1px solid #ddd; padding-top: 15px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Usage % (Status)</div>
                        <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest_weekly_feature_score:.2f}/100</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                        <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #2e7d32;">{weekly_high}</div>
                            <div style="color: #1b5e20; font-weight: 600; font-size: 0.75em;">High</div>
                            <div style="font-size: 0.65em; color: #666;">>={self.feat_high_threshold}%</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #f57c00;">{weekly_moderate}</div>
                            <div style="color: #e65100; font-weight: 600; font-size: 0.75em;">Moderate</div>
                            <div style="font-size: 0.65em; color: #666;">{self.feat_moderate_threshold}-{self.feat_high_threshold-1}%</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: white; border-radius: 4px;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #c62828;">{weekly_low}</div>
                            <div style="color: #b71c1c; font-weight: 600; font-size: 0.75em;">Low</div>
                            <div style="font-size: 0.65em; color: #666;"><{self.feat_moderate_threshold}%</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 20px;">
            <div>
                <h3>Latest Week Usage Rates</h3>
                <table>
                    <tr>
                        <th>Feature</th>
                        <th style="text-align: center;">Usage % (Status)</th>
                        <th style="text-align: center;">Semester Usage (≥2 weeks)</th>
                    </tr>
                    {feature_table_rows}
                </table>
                <p style="font-size: 0.9em; color: #666; margin-top: 15px;">
                    🟢 High: >={self.feat_high_threshold}% | 🟡 Moderate: {self.feat_moderate_threshold}-{self.feat_high_threshold-1}% | ⚫ Low: <{self.feat_moderate_threshold}%
                </p>
            </div>
            <div class="chart-container">
                <canvas id="featureScoreChart"></canvas>
            </div>
        </div>
        <details>
            <summary>📊 Show Detailed Feature Trends (Click to Expand)</summary>
            <div class="chart-container" style="margin-top: 15px;">
                <canvas id="featureDetailChart"></canvas>
            </div>
        </details>
    </div>

    <script>
    // WAU Chart (stacked area by course + percentage line)
    new Chart(document.getElementById('wauChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [
                ...{course_wau_datasets_json},
                {{
                    label: '% of Total Active So Far',
                    data: {wau_pcts_of_active_json},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{ display: true, text: 'Institute Weekly Active Users: Stacked by Course' }},
                legend: {{ display: true, position: 'top' }}
            }},
            scales: {{
                y: {{
                    stacked: true,
                    beginAtZero: true,
                    position: 'left',
                    title: {{ display: true, text: '# WAU (count)' }}
                }},
                y1: {{
                    beginAtZero: true,
                    max: 100,
                    position: 'right',
                    title: {{ display: true, text: '% of Total Active So Far' }},
                    grid: {{
                        drawOnChartArea: false
                    }}
                }},
                x: {{ stacked: true }}
            }},
            interaction: {{
                mode: 'index',
                intersect: false
            }}
        }}
    }});

    // Engagement Chart (stacked areas + score line)
    new Chart(document.getElementById('engagementChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [
                {{
                    label: 'Consistent ≥60%',
                    data: {consistent_json},
                    borderColor: '#81c784',
                    backgroundColor: 'rgba(129, 199, 132, 0.4)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }},
                {{
                    label: 'Moderate 25-59%',
                    data: {moderate_json},
                    borderColor: '#ffb74d',
                    backgroundColor: 'rgba(255, 183, 77, 0.4)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }},
                {{
                    label: 'Sporadic <25%',
                    data: {sporadic_json},
                    borderColor: '#e57373',
                    backgroundColor: 'rgba(229, 115, 115, 0.4)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }},
                {{
                    label: 'Consistency Engagement Score',
                    data: {eng_scores_json},
                    borderColor: '#667eea',
                    backgroundColor: 'transparent',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ title: {{ display: true, text: 'Institute Engagement Persistence & Score' }} }},
            scales: {{
                y: {{
                    stacked: true,
                    beginAtZero: true,
                    max: 100,
                    position: 'left',
                    title: {{ display: true, text: 'Percentage (%)' }}
                }},
                y1: {{
                    min: {eng_axis_min:.1f},
                    max: {eng_axis_max:.1f},
                    position: 'right',
                    title: {{ display: true, text: 'Consistency Engagement Score (0-100, Expected=50)' }},
                    grid: {{
                        drawOnChartArea: true,
                        color: ctx => ctx.tick.value === 50 ? '#667eea' : 'rgba(0,0,0,0.05)',
                        lineWidth: ctx => ctx.tick.value === 50 ? 2 : 1
                    }}
                }},
                x: {{ stacked: true }}
            }}
        }}
    }});

    // Cumulative Engagement Chart (Dual Y-axes)
    new Chart(document.getElementById('cumulativeEngagementChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [
                {{
                    label: 'Median Cumulative Time (minutes)',
                    data: {cumulative_times_json},
                    borderColor: '#f57c00',
                    backgroundColor: 'rgba(245, 124, 0, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y'
                }},
                {{
                    label: 'Repeating Users (% of Active)',
                    data: {coverage_data_json},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }},
                {{
                    label: 'Repeating Users (% of Registered - Potential)',
                    data: {coverage_from_registered_json},
                    borderColor: '#9b59b6',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{ display: true, text: 'Cumulative Engagement & Repeating Users' }},
                legend: {{ display: true, position: 'top' }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    position: 'left',
                    title: {{ display: true, text: 'Cumulative Time (minutes)' }}
                }},
                y1: {{
                    beginAtZero: true,
                    max: 100,
                    position: 'right',
                    title: {{ display: true, text: 'Repeating Users (%)' }},
                    grid: {{ drawOnChartArea: false }}
                }}
            }}
        }}
    }});

    // Feature Score Chart
    new Chart(document.getElementById('featureScoreChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [{{
                label: 'Feature Usage Score (vs Expected)',
                data: {feature_scores_json},
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{ display: true, text: 'Feature Usage Score Over Time' }},
                legend: {{ display: false }}
            }},
            scales: {{
                y: {{
                    min: {feat_axis_min:.1f},
                    max: {feat_axis_max:.1f},
                    title: {{ display: true, text: 'Feature Score (0-100, Expected=50)' }},
                    grid: {{
                        color: ctx => ctx.tick.value === 50 ? '#667eea' : 'rgba(0,0,0,0.1)',
                        lineWidth: ctx => ctx.tick.value === 50 ? 2 : 1
                    }}
                }}
            }}
        }}
    }});

    // Feature Detail Chart
    new Chart(document.getElementById('featureDetailChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: {feature_datasets_json}
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{ display: true, text: 'Individual Feature Usage Rates Over Time' }},
                legend: {{ display: true, position: 'top' }}
            }},
            scales: {{
                y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: 'Usage Rate (%)' }} }}
            }}
        }}
    }});
    </script>

    {self._get_footer()}
</body>
</html>
"""

    def _get_common_styles(self) -> str:
        """Common CSS styles for all reports"""
        return """
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }
        .header p {
            margin: 5px 0;
            font-size: 1.1em;
            opacity: 0.9;
        }
        .executive-summary {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 6px solid #764ba2;
        }
        .executive-summary h2 {
            margin-top: 0;
            color: #2d3436;
            font-size: 1.8em;
        }
        .executive-summary p {
            font-size: 1.15em;
            line-height: 1.8;
            color: #2d3436;
            margin: 15px 0;
        }
        .section {
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #764ba2;
            border-bottom: 2px solid #764ba2;
            padding-bottom: 10px;
            margin-top: 0;
        }
        .section h3 {
            color: #667eea;
            margin-top: 20px;
        }
        .chart-container {
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            position: relative;
            height: 400px;
        }
        .chart-container canvas {
            display: block;
            width: 100% !important;
            height: 100% !important;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th {
            background: #764ba2;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        tr:hover {
            background: #f8f9fa;
        }
        details {
            margin: 20px 0;
        }
        summary {
            cursor: pointer;
            font-weight: 600;
            color: #764ba2;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        summary:hover {
            background: #e3f2fd;
        }
    </style>
"""

    def _get_footer(self) -> str:
        """Common footer for all reports"""
        return f"""
    <div style="text-align: center; color: #666; margin-top: 40px; padding: 20px; border-top: 1px solid #ddd;">
        <p>Generated with New Institute Reports Generator</p>
        <p style="font-size: 0.9em;">Report Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
"""