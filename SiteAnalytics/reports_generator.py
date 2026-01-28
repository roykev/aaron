#!/usr/bin/env python3
"""
New Weekly Reports Generator - Per Course
Generates Report A (Snapshot) and Report C (Dynamics) for individual courses
Saves to report/new/{institute}/
"""

import pandas as pd
import os
from typing import Dict
import json


class NewWeeklyReportsGenerator:
    """Generates per-course weekly reports (A & C)"""

    def __init__(self, weekly_metrics: pd.DataFrame, course_name: str, institute_name: str, config: dict = None):
        """
        Initialize report generator

        Args:
            weekly_metrics: DataFrame with all weekly metrics
            course_name: Name of the course
            institute_name: Name of the institute (for folder structure)
            config: Configuration dictionary
        """
        self.metrics = weekly_metrics
        self.course_name = course_name
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

    def generate_snapshot_report(self, output_dir: str):
        """Generate Report A: Weekly Snapshot (Last complete week only)"""
        if len(self.metrics) == 0:
            print(f"No data for {self.course_name}, skipping snapshot report")
            return

        latest = self.metrics.iloc[-1]
        report_dir = os.path.join(output_dir, "new", self.institute_name)
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, f"{self.course_name}_snapshot.html")

        html = self._generate_snapshot_html(latest)

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Snapshot report generated: {output_path}")

    def generate_dynamics_report(self, output_dir: str):
        """Generate Report C: Dynamics/Cumulative (All complete weeks)"""
        if len(self.metrics) == 0:
            print(f"No data for {self.course_name}, skipping dynamics report")
            return

        report_dir = os.path.join(output_dir, "new", self.institute_name)
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, f"{self.course_name}_dynamics.html")

        html = self._generate_dynamics_html()

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Dynamics report generated: {output_path}")

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

        Args:
            score: Raw score to normalize
            min_val: Minimum possible score
            expected_val: Expected score (will map to 50)
            max_val: Maximum possible score

        Returns:
            Normalized score (0-100)
        """
        if score <= min_val:
            return 0.0
        elif score >= max_val:
            return 100.0
        elif score < expected_val:
            # Map [min_val, expected_val] to [0, 50]
            return ((score - min_val) / (expected_val - min_val)) * 50
        else:
            # Map [expected_val, max_val] to [50, 100]
            return 50 + ((score - expected_val) / (max_val - expected_val)) * 50

    def _get_metric_color(self, metric_type: str, value: float) -> tuple:
        """
        Determine background and text color based on metric type and value
        Returns (bg_color, text_color) tuple

        Green: Good performance (>60)
        Yellow: Moderate performance (26-60)
        Red: Poor performance (0-25)
        """
        if metric_type == 'activity_rate':
            # Percentage metric: higher is better
            if value > 60:
                return ('#c8e6c9', '#1b5e20')  # Light green bg, dark green text
            elif value >= 26:
                return ('#fff9c4', '#f57f17')  # Light yellow bg, dark yellow text
            else:
                return ('#ffcdd2', '#b71c1c')  # Light red bg, dark red text

        elif metric_type == 'engagement_score':
            # Normalized 0-100 score: higher is better
            if value > 60:
                return ('#c8e6c9', '#1b5e20')
            elif value >= 26:
                return ('#fff9c4', '#f57f17')
            else:
                return ('#ffcdd2', '#b71c1c')

        elif metric_type == 'coverage':
            # Percentage metric: higher is better
            if value > 60:
                return ('#c8e6c9', '#1b5e20')
            elif value >= 26:
                return ('#fff9c4', '#f57f17')
            else:
                return ('#ffcdd2', '#b71c1c')

        elif metric_type == 'retention':
            # Normalized 0-100 score: higher is better
            if value > 60:
                return ('#c8e6c9', '#1b5e20')
            elif value >= 26:
                return ('#fff9c4', '#f57f17')
            else:
                return ('#ffcdd2', '#b71c1c')

        # Default: no color coding (keep original styling)
        return ('#e3f2fd', '#667eea')

    def _generate_snapshot_html(self, latest: pd.Series) -> str:
        """Generate HTML for Report A: Weekly Snapshot"""
        wau_count = int(latest.get('wau_count', 0))
        wau_pct = latest.get('wau_percentage', 0)
        total_enrolled = int(latest.get('total_enrolled', 0))
        median_time = latest.get('median_weekly_time_minutes', 0)
        median_time_hms = self._format_time_hms(median_time)

        # Feature usage - use old report widget style
        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']

        # Calculate feature score
        high_count = 0
        moderate_count = 0
        low_count = 0
        feature_table_rows = ""

        for i, feature in enumerate(features):
            usage_col = f'feature_usage_{feature}'
            time_col = f'feature_time_{feature}_minutes'
            usage_pct = latest.get(usage_col, 0)
            time_min = latest.get(time_col, 0)

            if usage_pct >= self.feat_high_threshold:
                high_count += 1
                status = "🟢"
            elif usage_pct >= self.feat_moderate_threshold:
                moderate_count += 1
                status = "🟡"
            else:
                low_count += 1
                status = "⚫"

            feature_table_rows += f"""
            <tr>
                <td>{feature_labels[i]}</td>
                <td style="text-align: center;">{usage_pct:.1f}% {status}</td>
                <td style="text-align: center;">{time_min:.1f} min</td>
            </tr>
            """

        # Calculate expected and normalize feature score (expected = 50)
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

        from_date = pd.to_datetime(latest['from_date']).strftime('%b %d, %Y')
        to_date = pd.to_datetime(latest['to_date']).strftime('%b %d, %Y')
        week_num = int(latest.get('week_number', 0))

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Snapshot: {self.course_name} - Week {week_num} ({from_date} - {to_date})</title>
    {self._get_common_styles()}
</head>
<body>
    <div class="header">
        <h1>📊 Weekly Snapshot Report</h1>
        <p><strong>{self.course_name} (Registered: {total_enrolled})</strong></p>
        <p>Week {week_num}: {from_date} to {to_date}</p>
    </div>

    <div class="section">
        <h2>1. Active Users</h2>
        <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
            <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{wau_pct:.1f}%</div>
            <div style="color: #666; font-size: 1.1em; margin: 5px 0;">Activity Rate</div>
            <div style="color: #999; font-size: 0.9em;">Registered: {total_enrolled}</div>
        </div>
    </div>

    <div class="section">
        <h2>2. Median Weekly Time Per Student</h2>
        <div style="text-align: center; padding: 30px; background: #f3e5f5; border-radius: 8px;">
            <div style="font-size: 3em; font-weight: bold; color: #764ba2;">{median_time_hms}</div>
            <div style="color: #666; font-size: 1.2em;">Minutes per student THIS week (median)</div>
        </div>
    </div>

    <div class="section">
        <h2>3. Feature Usage</h2>
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
                <th style="text-align: center;">Time</th>
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
        """Generate HTML for Report C: Course Dynamics"""
        # Prepare chart data
        date_labels = []
        wau_counts = []
        wau_pcts = []
        wau_pcts_of_active = []
        median_times = []
        consistent_data = []
        moderate_data = []
        sporadic_data = []

        for _, row in self.metrics.iterrows():
            from_date = pd.to_datetime(row['from_date'])
            date_labels.append(from_date.strftime('%b %d'))
            wau_counts.append(row.get('wau_count', 0))
            wau_pcts.append(row.get('wau_percentage', 0))
            wau_pcts_of_active.append(row.get('wau_percentage_of_active', 0))
            median_times.append(row.get('median_weekly_time_minutes', 0))
            consistent_data.append(row.get('persistent_consistent_pct', 0))
            moderate_data.append(row.get('persistent_moderate_pct', 0))
            sporadic_data.append(row.get('persistent_sporadic_pct', 0))

        # Calculate cumulative time
        cumulative_times = []
        running_total = 0
        for time in median_times:
            running_total += time
            cumulative_times.append(running_total)

        # Calculate coverage data (% of enrolled users active in ≥2 weeks)
        coverage_data = []
        for _, row in self.metrics.iterrows():
            coverage_data.append(row.get('coverage_pct', 0))

        # Calculate repeating % from active (for each week)
        repeating_from_active_data = []
        for _, row in self.metrics.iterrows():
            cov_count = row.get('coverage_count', 0)
            cum_active = row.get('cumulative_active_users', 1)
            repeating_pct = (cov_count / cum_active * 100) if cum_active > 0 else 0
            repeating_from_active_data.append(repeating_pct)

        # Latest metrics
        latest = self.metrics.iloc[-1]
        latest_wau_pct = latest.get('wau_percentage', 0)
        latest_wau_pct_of_active = latest.get('wau_percentage_of_active', 0)
        total_enrolled = int(latest.get('total_enrolled', 0))
        latest_time = cumulative_times[-1] if cumulative_times else 0
        latest_time_hms = self._format_time_hms(latest_time)
        latest_coverage = coverage_data[-1] if coverage_data else 0

        # Calculate engagement scores (normalized to 0-100 where expected = 50)
        expected_score_raw = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                             (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                             (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)

        eng_scores = []  # Normalized scores (0-100, expected=50)
        for _, row in self.metrics.iterrows():
            cons = row.get('persistent_consistent_pct', 0)
            mod = row.get('persistent_moderate_pct', 0)
            spor = row.get('persistent_sporadic_pct', 0)
            enrolled = row.get('total_enrolled', 0)

            if enrolled > 0:
                cons_cnt = (cons / 100) * enrolled
                mod_cnt = (mod / 100) * enrolled
                spor_cnt = (spor / 100) * enrolled
                score_raw = (cons_cnt * self.eng_consistent_weight +
                            mod_cnt * self.eng_moderate_weight +
                            spor_cnt * self.eng_sporadic_weight) / enrolled
                score_normalized = self._normalize_score(
                    score_raw,
                    self.eng_sporadic_weight,
                    expected_score_raw,
                    self.eng_consistent_weight
                )
                eng_scores.append(score_normalized)
            else:
                eng_scores.append(None)

        latest_eng_score = eng_scores[-1] if eng_scores and eng_scores[-1] is not None else 0

        # At-risk and reactivation
        at_risk_pcts = []
        reactivation_rates = []
        for _, row in self.metrics.iterrows():
            at_risk_pcts.append(row.get('at_risk_percentage', 0))
            reactivation_rates.append(row.get('reactivation_rate', 0))

        latest_at_risk = at_risk_pcts[-1] if at_risk_pcts else 0
        latest_reactivation = reactivation_rates[-1] if reactivation_rates else 0
        combined_score = (100 - latest_at_risk) * 0.7 + latest_reactivation * 0.3

        # Feature usage
        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

        feature_datasets = []
        for i, feature in enumerate(features):
            col = f'feature_usage_{feature}'
            if col in self.metrics.columns:
                data = self.metrics[col].tolist()
                feature_datasets.append({
                    'label': feature_labels[i],
                    'data': data,
                    'borderColor': colors[i],
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'tension': 0.4,
                    'fill': False
                })

        # Feature scores (normalized to 0-100 where expected = 50) - BASED ON SEMESTER USAGE
        expected_feat_score_raw = (self.feat_high_weight * 2 + self.feat_moderate_weight * 3 + self.feat_low_weight * 2) / len(features)
        feature_scores = []  # Normalized scores (0-100, expected=50)

        for _, row in self.metrics.iterrows():
            # Use semester usage data instead of weekly usage
            high = sum(1 for f in features if row.get(f'feature_semester_{f}', 0) >= self.feat_high_threshold)
            mod = sum(1 for f in features if self.feat_moderate_threshold <= row.get(f'feature_semester_{f}', 0) < self.feat_high_threshold)
            low = sum(1 for f in features if row.get(f'feature_semester_{f}', 0) < self.feat_moderate_threshold)
            score_raw = (high * self.feat_high_weight + mod * self.feat_moderate_weight + low * self.feat_low_weight) / len(features)
            score_normalized = self._normalize_score(
                score_raw,
                self.feat_low_weight,
                expected_feat_score_raw,
                self.feat_high_weight
            )
            feature_scores.append(score_normalized)

        # Latest feature metrics (weekly usage)
        high_count = sum(1 for f in features if latest.get(f'feature_usage_{f}', 0) >= self.feat_high_threshold)
        mod_count = sum(1 for f in features if self.feat_moderate_threshold <= latest.get(f'feature_usage_{f}', 0) < self.feat_high_threshold)
        low_count = sum(1 for f in features if latest.get(f'feature_usage_{f}', 0) < self.feat_moderate_threshold)

        # Latest semester feature metrics (semester usage ≥2 weeks)
        sem_high_count = sum(1 for f in features if latest.get(f'feature_semester_{f}', 0) >= self.feat_high_threshold)
        sem_mod_count = sum(1 for f in features if self.feat_moderate_threshold <= latest.get(f'feature_semester_{f}', 0) < self.feat_high_threshold)
        sem_low_count = sum(1 for f in features if latest.get(f'feature_semester_{f}', 0) < self.feat_moderate_threshold)

        # Calculate semester feature score (normalized to 0-100 where expected = 50)
        raw_sem_feature_score = (sem_high_count * self.feat_high_weight + sem_mod_count * self.feat_moderate_weight + sem_low_count * self.feat_low_weight) / len(features)
        sem_feature_score = self._normalize_score(
            raw_sem_feature_score,
            self.feat_low_weight,
            expected_feat_score_raw,
            self.feat_high_weight
        )

        feature_table_rows = ""
        feature_usage_list = []
        for i, feature in enumerate(features):
            usage_pct = latest.get(f'feature_usage_{feature}', 0)
            semester_usage = latest.get(f'feature_semester_{feature}', 0)
            status = "🟢" if usage_pct >= self.feat_high_threshold else ("🟡" if usage_pct >= self.feat_moderate_threshold else "⚫")
            semester_status = "🟢" if semester_usage >= self.feat_high_threshold else ("🟡" if semester_usage >= self.feat_moderate_threshold else "⚫")
            feature_table_rows += f"<tr><td>{feature_labels[i]}</td><td style='text-align: center;'>{usage_pct:.1f}% {status}</td><td style='text-align: center;'>{semester_usage:.1f}% {semester_status}</td></tr>"
            feature_usage_list.append({'name': feature_labels[i], 'usage': usage_pct, 'status': status})

        # Sort features by usage to get top and bottom
        sorted_features = sorted(feature_usage_list, key=lambda x: x['usage'], reverse=True)
        top_feature = sorted_features[0]
        bottom_feature = sorted_features[-1]

        # Calculate latest feature score (normalized to 0-100 where expected = 50)
        raw_latest_feature_score = (high_count * self.feat_high_weight + mod_count * self.feat_moderate_weight + low_count * self.feat_low_weight) / len(features)
        latest_feature_score = self._normalize_score(
            raw_latest_feature_score,
            self.feat_low_weight,
            expected_feat_score_raw,
            self.feat_high_weight
        )

        # Calculate repeating % from active (instead of from enrolled) - MUST BE BEFORE DELTA CALCULATIONS
        cumulative_active = int(latest.get('cumulative_active_users', 1))
        coverage_count = int(latest.get('coverage_count', 0))
        latest_repeating_from_active = (coverage_count / cumulative_active * 100) if cumulative_active > 0 else 0

        # Calculate +/- vs last week for all 6 metrics
        has_prev_week = len(self.metrics) >= 2
        if has_prev_week:
            prev = self.metrics.iloc[-2]

            # 1. Activity Rate delta
            prev_wau_pct = prev.get('wau_percentage', 0)
            delta_wau_pct = latest_wau_pct - prev_wau_pct

            # 2. Engagement Score delta
            prev_eng_score = eng_scores[-2] if len(eng_scores) >= 2 and eng_scores[-2] is not None else latest_eng_score
            delta_eng_score = latest_eng_score - prev_eng_score

            # 3. Cumulative Time delta
            prev_time = cumulative_times[-2] if len(cumulative_times) >= 2 else 0
            delta_time = latest_time - prev_time
            delta_time_hms = self._format_time_hms(delta_time)

            # 4. Repeating Users delta (% of active)
            prev_repeating = repeating_from_active_data[-2] if len(repeating_from_active_data) >= 2 else 0
            delta_coverage = latest_repeating_from_active - prev_repeating

            # 5. Retention Score delta
            prev_at_risk = at_risk_pcts[-2] if len(at_risk_pcts) >= 2 else latest_at_risk
            prev_reactivation = reactivation_rates[-2] if len(reactivation_rates) >= 2 else latest_reactivation
            prev_combined_score = (100 - prev_at_risk) * 0.7 + prev_reactivation * 0.3
            delta_combined_score = combined_score - prev_combined_score

            # 6. Top/Bottom Feature Usage delta
            # Find matching feature index for top and bottom
            top_feature_key = None
            bottom_feature_key = None
            for i, label in enumerate(feature_labels):
                if label == top_feature['name']:
                    top_feature_key = features[i]
                if label == bottom_feature['name']:
                    bottom_feature_key = features[i]

            prev_top_usage = prev.get(f'feature_usage_{top_feature_key}', top_feature['usage']) if top_feature_key else top_feature['usage']
            prev_bottom_usage = prev.get(f'feature_usage_{bottom_feature_key}', bottom_feature['usage']) if bottom_feature_key else bottom_feature['usage']
            delta_top_usage = top_feature['usage'] - prev_top_usage
            delta_bottom_usage = bottom_feature['usage'] - prev_bottom_usage
        else:
            delta_wau_pct = 0
            delta_eng_score = 0
            delta_time = 0
            delta_time_hms = "0:00:00"
            delta_coverage = 0
            delta_combined_score = 0
            delta_top_usage = 0
            delta_bottom_usage = 0

        # Get date range for title
        first_week = self.metrics.iloc[0]
        last_week = self.metrics.iloc[-1]
        first_date = pd.to_datetime(first_week['from_date']).strftime('%b %d, %Y')
        # Always calculate ending date as from_date + 7 days (full week)
        last_date_dt = pd.to_datetime(last_week['from_date']) + pd.Timedelta(days=7)
        last_date = last_date_dt.strftime('%b %d, %Y')
        num_weeks = len(self.metrics)

        # Calculate colors for the 6 boxes based on metric values
        activity_bg, activity_color = self._get_metric_color('activity_rate', latest_wau_pct)
        engagement_bg, engagement_color = self._get_metric_color('engagement_score', latest_eng_score)
        coverage_bg, coverage_color = self._get_metric_color('coverage', latest_repeating_from_active)
        retention_bg, retention_color = self._get_metric_color('retention', combined_score)

        # Generate concept tables
        concept_table_rows_week = ""
        concept_table_rows_semester = ""

        # Get top concepts for this week (list of tuples: [(concept, count), ...])
        top_concepts_this_week = latest.get('top_concepts_this_week', [])
        top_concepts_cumulative = latest.get('top_concepts_cumulative', [])

        # Get previous week's concepts for trend calculation
        prev_concepts = []
        if has_prev_week:
            prev = self.metrics.iloc[-2]
            prev_concepts = prev.get('top_concepts_this_week', [])

        # Calculate max count for bar normalization (this week)
        max_count_week = top_concepts_this_week[0][1] if top_concepts_this_week else 1

        # Generate this week's top 5 table with trends and popularity bars
        for i, (concept, count) in enumerate(top_concepts_this_week[:5], 1):
            # Calculate bar width (percentage of max)
            bar_width = (count / max_count_week * 100) if max_count_week > 0 else 0

            # Calculate trend vs last week
            trend_symbol = "—"  # no change/new
            if prev_concepts:
                prev_concept_names = [c[0] if isinstance(c, tuple) else c for c in prev_concepts]
                if concept in prev_concept_names:
                    prev_rank = prev_concept_names.index(concept) + 1
                    if prev_rank > i:
                        trend_symbol = f"↑ +{prev_rank - i}"  # moved up
                    elif prev_rank < i:
                        trend_symbol = f"↓ -{i - prev_rank}"  # moved down
                    else:
                        trend_symbol = "="  # same position
                else:
                    trend_symbol = "🆕 New"  # new entry

            concept_table_rows_week += f"""
                <tr>
                    <td>{concept}</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="flex-grow: 1; background: #e0e0e0; height: 20px; border-radius: 4px; overflow: hidden;">
                                <div style="width: {bar_width:.1f}%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); height: 100%;"></div>
                            </div>
                            <div style="min-width: 40px; text-align: right; font-size: 0.85em; color: #666;">{count}</div>
                        </div>
                    </td>
                    <td style='text-align: center;'>{trend_symbol}</td>
                </tr>
            """

        # If less than 5 concepts, show empty rows
        for i in range(len(top_concepts_this_week[:5]), 5):
            concept_table_rows_week += f"""
                <tr>
                    <td style='color: #999;'>—</td>
                    <td>—</td>
                    <td style='text-align: center;'>—</td>
                </tr>
            """

        # Calculate max count for bar normalization (semester)
        max_count_semester = top_concepts_cumulative[0][1] if top_concepts_cumulative else 1

        # Generate semester top 5 table with popularity bars
        for i, (concept, count) in enumerate(top_concepts_cumulative[:5], 1):
            # Calculate bar width (percentage of max)
            bar_width = (count / max_count_semester * 100) if max_count_semester > 0 else 0

            concept_table_rows_semester += f"""
                <tr>
                    <td>{concept}</td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="flex-grow: 1; background: #e0e0e0; height: 20px; border-radius: 4px; overflow: hidden;">
                                <div style="width: {bar_width:.1f}%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); height: 100%;"></div>
                            </div>
                            <div style="min-width: 40px; text-align: right; font-size: 0.85em; color: #666;">{count}</div>
                        </div>
                    </td>
                </tr>
            """

        # If less than 5 concepts, show empty rows
        for i in range(len(top_concepts_cumulative[:5]), 5):
            concept_table_rows_semester += f"""
                <tr>
                    <td style='color: #999;'>—</td>
                    <td>—</td>
                </tr>
            """

        # JSON data
        date_labels_json = json.dumps(date_labels)
        wau_counts_json = json.dumps(wau_counts)
        wau_pcts_json = json.dumps(wau_pcts)
        wau_pcts_of_active_json = json.dumps(wau_pcts_of_active)
        cumulative_times_json = json.dumps(cumulative_times)
        coverage_data_json = json.dumps(coverage_data)
        repeating_from_active_json = json.dumps(repeating_from_active_data)
        consistent_json = json.dumps(consistent_data)
        moderate_json = json.dumps(moderate_data)
        sporadic_json = json.dumps(sporadic_data)
        eng_scores_json = json.dumps(eng_scores)  # Use normalized scores for chart
        at_risk_json = json.dumps(at_risk_pcts)
        reactivation_json = json.dumps(reactivation_rates)
        feature_datasets_json = json.dumps(feature_datasets)
        feature_scores_json = json.dumps(feature_scores)  # Use normalized scores for chart

        # Chart axis ranges use 0-100 scale with expected at 50
        eng_axis_min = 0
        eng_axis_max = 100
        feat_axis_min = 0
        feat_axis_max = 100

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Dynamics: {self.course_name} ({first_date} - {last_date})</title>
    {self._get_common_styles()}
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>📈 Course Dynamics Report</h1>
        <p><strong>{self.course_name} (Registered: {total_enrolled})</strong></p>
        <p>{num_weeks} Complete Weeks: {first_date} to {last_date}</p>
    </div>

    <div class="section">
        <h2>📋 Executive Summary</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
            <div style="text-align: center; padding: 20px; background: {activity_bg}; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: {activity_color};">{latest_wau_pct_of_active:.1f}%</div>
                <div style="color: #666; font-size: 0.9em;">Current Activity Rate</div>
                <div style="font-size: 0.75em; color: #888; margin-top: 3px;">% of Active So Far</div>
                <div style="font-size: 0.8em; color: #888; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">Total Active So Far: {int(latest.get('cumulative_active_users', 0))}</div>
                <div style="font-size: 0.8em; color: #888; margin-top: 5px;">{int(latest.get('wau_count', 0))}/{total_enrolled}</div>
            </div>
            <div style="text-align: center; padding: 20px; background: {engagement_bg}; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: {engagement_color};">{latest_eng_score:.2f}</div>
                <div style="color: #666; font-size: 0.9em;">Consistency Engagement Score</div>
                {'<div style="font-size: 0.75em; color: ' + ('green' if delta_eng_score >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_eng_score > 0 else '↓' if delta_eng_score < 0 else '—') + f' {delta_eng_score:+.1f} vs last week</div>' if has_prev_week else ''}
            </div>
            <div style="text-align: center; padding: 20px; background: #fff3e0; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #f57c00;">{latest_time_hms}</div>
                <div style="color: #666; font-size: 0.9em;">Cumulative Time</div>
                {'<div style="font-size: 0.75em; color: ' + ('green' if delta_time >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_time > 0 else '↓' if delta_time < 0 else '—') + f' {delta_time_hms} vs last week</div>' if has_prev_week else ''}
            </div>
            <div style="text-align: center; padding: 20px; background: {coverage_bg}; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: {coverage_color};">{latest_repeating_from_active:.1f}%</div>
                <div style="color: #666; font-size: 0.9em;">Repeating Users</div>
                {'<div style="font-size: 0.75em; color: ' + ('green' if delta_coverage >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_coverage > 0 else '↓' if delta_coverage < 0 else '—') + f' {delta_coverage:+.1f}% vs last week</div>' if has_prev_week else ''}
                <div style="font-size: 0.8em; color: #888; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">{cumulative_active}, {coverage_count}, {latest_repeating_from_active:.1f}%</div>
            </div>
            <div style="text-align: center; padding: 20px; background: {retention_bg}; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: {retention_color};">{combined_score:.1f}</div>
                <div style="color: #666; font-size: 0.9em;">Retention Score</div>
                {'<div style="font-size: 0.75em; color: ' + ('green' if delta_combined_score >= 0 else 'red') + '; margin-top: 5px;">' + ('↑' if delta_combined_score > 0 else '↓' if delta_combined_score < 0 else '—') + f' {delta_combined_score:+.1f} vs last week</div>' if has_prev_week else ''}
            </div>
            <div style="text-align: center; padding: 20px; background: #e8f5e9; border-radius: 8px;">
                <div style="font-size: 1.3em; font-weight: bold; color: #2e7d32;">{top_feature['status']} {top_feature['name']} ({top_feature['usage']:.1f}%)</div>
                {'<div style="font-size: 0.7em; color: ' + ('green' if delta_top_usage >= 0 else 'red') + ';">' + ('↑' if delta_top_usage > 0 else '↓' if delta_top_usage < 0 else '—') + f' {delta_top_usage:+.1f}%</div>' if has_prev_week else ''}
                <div style="font-size: 1.3em; font-weight: bold; color: #c62828; margin-top: 8px;">{bottom_feature['status']} {bottom_feature['name']} ({bottom_feature['usage']:.1f}%)</div>
                {'<div style="font-size: 0.7em; color: ' + ('green' if delta_bottom_usage >= 0 else 'red') + ';">' + ('↑' if delta_bottom_usage > 0 else '↓' if delta_bottom_usage < 0 else '—') + f' {delta_bottom_usage:+.1f}%</div>' if has_prev_week else ''}
                <div style="color: #666; font-size: 0.9em; margin-top: 5px;">Top / Bottom Features</div>
                <div style="font-size: 0.8em; color: #888; margin-top: 8px; border-top: 1px solid #ddd; padding-top: 8px;">Semester Score: {sem_feature_score:.2f}/100 | H:{sem_high_count} M:{sem_mod_count} L:{sem_low_count}</div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
            <div style="padding: 15px; background: #fce4ec; border-radius: 8px;">
                <div style="font-weight: bold; color: #c2185b; font-size: 1em; margin-bottom: 10px;">📚 Top Concepts This Week</div>
                <div style="font-size: 0.85em; color: #666;">
                    {', '.join([c[0] if isinstance(c, tuple) else c for c in top_concepts_this_week[:3]]) if top_concepts_this_week else 'No data yet'}
                </div>
            </div>
            <div style="padding: 15px; background: #f3e5f5; border-radius: 8px;">
                <div style="font-weight: bold; color: #7b1fa2; font-size: 1em; margin-bottom: 10px;">🎓 Top Concepts This Semester</div>
                <div style="font-size: 0.85em; color: #666;">
                    {', '.join([c[0] if isinstance(c, tuple) else c for c in top_concepts_cumulative[:3]]) if top_concepts_cumulative else 'No data yet'}
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
                <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{latest_repeating_from_active:.1f}%</div>
                <div style="color: #666; font-size: 1.1em;">Repeating Users</div>
                <div style="font-size: 0.8em; color: #888; margin-top: 8px;">% of Active Users</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="cumulativeEngagementChart"></canvas>
        </div>
    </div>

    <div class="section">
        <h2>2. Active Users Trend</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #667eea;">{int(latest.get('wau_count', 0))}</div>
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
        <h2>3. Top Concepts</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
            <div>
                <h3>This Week's Top 5</h3>
                <table>
                    <tr>
                        <th>Concept</th>
                        <th>Popularity</th>
                        <th style="text-align: center;">Trend</th>
                    </tr>
                    {concept_table_rows_week}
                </table>
            </div>
            <div>
                <h3>Semester Top 5</h3>
                <table>
                    <tr>
                        <th>Concept</th>
                        <th>Popularity</th>
                    </tr>
                    {concept_table_rows_semester}
                </table>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>4. Consistency Engagement Score</h2>
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
    </div>

    <div class="section">
        <h2>5. Feature Usage Trends</h2>
        <div style="padding: 15px; background: #f3f4f6; border-left: 4px solid #667eea; border-radius: 8px; margin-bottom: 20px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Semester Usage Score (≥2 weeks)</div>
                    <div style="font-size: 2em; font-weight: bold; color: #667eea;">{sem_feature_score:.2f}/100</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #2e7d32;">{sem_high_count}</div>
                        <div style="color: #1b5e20; font-weight: 600; font-size: 0.8em;">High</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #f57c00;">{sem_mod_count}</div>
                        <div style="color: #e65100; font-weight: 600; font-size: 0.8em;">Moderate</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.5em; font-weight: bold; color: #c62828;">{sem_low_count}</div>
                        <div style="color: #b71c1c; font-weight: 600; font-size: 0.8em;">Low</div>
                    </div>
                </div>
            </div>
            <div style="border-top: 1px solid #ddd; padding-top: 15px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Usage % (Status)</div>
                        <div style="font-size: 2em; font-weight: bold; color: #667eea;">{latest_feature_score:.2f}/100</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                        <div style="text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #2e7d32;">{high_count}</div>
                            <div style="color: #1b5e20; font-weight: 600; font-size: 0.8em;">High</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #f57c00;">{mod_count}</div>
                            <div style="color: #e65100; font-weight: 600; font-size: 0.8em;">Moderate</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #c62828;">{low_count}</div>
                            <div style="color: #b71c1c; font-weight: 600; font-size: 0.8em;">Low</div>
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

    <div class="section">
        <h2>6. Student Retention Score</h2>
        <div style="text-align: center; padding: 20px; background: #e8eaf6; border-radius: 8px; margin-bottom: 20px;">
            <div style="font-size: 2.5em; font-weight: bold; color: #5e35b1;">{combined_score:.1f}</div>
            <div style="color: #666; font-size: 1.1em;">Current Retention Score (out of 100)</div>
            <div style="font-size: 0.9em; color: #666; margin-top: 10px;">
                ⚠️ High at-risk % is bad | ⚠️ Low reactivation % is bad
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div class="chart-container">
                <canvas id="atRiskChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="reactivationChart"></canvas>
            </div>
        </div>
    </div>

    <script>
    // WAU Chart (dual-axis: count and percentage)
    new Chart(document.getElementById('wauChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [
                {{
                    label: '# WAU (count)',
                    data: {wau_counts_json},
                    borderColor: '#f57c00',
                    backgroundColor: 'rgba(245, 124, 0, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y'
                }},
                {{
                    label: '% of Total Active So Far',
                    data: {wau_pcts_of_active_json},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y1'
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{ display: true, text: 'Weekly Active Users: Count & %' }}
            }},
            scales: {{
                y: {{
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
                }}
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
            plugins: {{ title: {{ display: true, text: 'Engagement Persistence & Score' }} }},
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
                    label: 'Cumulative Time (minutes)',
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
                    data: {repeating_from_active_json},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }},
                {{
                    label: 'Repeating Users (% of Registered - Potential)',
                    data: {coverage_data_json},
                    borderColor: '#9b59b6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: false,
                    borderDash: [5, 5],
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
                    grid: {{
                        drawOnChartArea: false
                    }}
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

    // At-Risk Chart
    new Chart(document.getElementById('atRiskChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [{{
                label: 'At-Risk %',
                data: {at_risk_json},
                borderColor: '#c62828',
                backgroundColor: 'rgba(198, 40, 40, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ title: {{ display: true, text: 'At-Risk Students %' }} }},
            scales: {{
                y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: 'Percentage (%)' }} }}
            }}
        }}
    }});

    // Reactivation Chart
    new Chart(document.getElementById('reactivationChart'), {{
        type: 'line',
        data: {{
            labels: {date_labels_json},
            datasets: [{{
                label: 'Reactivation Rate',
                data: {reactivation_json},
                borderColor: '#1565c0',
                backgroundColor: 'rgba(21, 101, 192, 0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ title: {{ display: true, text: 'Reactivation Rate %' }} }},
            scales: {{
                y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: 'Percentage (%)' }} }}
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
        .section {
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }
        .section h3 {
            color: #764ba2;
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
            background: #667eea;
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
            color: #667eea;
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
        <p>Generated with New Weekly Reports Generator</p>
        <p style="font-size: 0.9em;">Report Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
"""