#!/usr/bin/env python3
"""
Institute Progress Reporter
Generates HTML reports for institute-level weekly progression analysis
Aggregates data from multiple courses within an institute
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json


class InstituteProgressReporter:
    """Generates HTML reports for institute-level weekly progress metrics"""

    def __init__(self, course_metrics: Dict[str, pd.DataFrame], course_names: Dict[str, str],
                 semester_start: str = None, semester_end: str = None, config: dict = None):
        """
        Initialize reporter

        Args:
            course_metrics: Dict mapping course_id -> weekly_metrics DataFrame
            course_names: Dict mapping course_id -> course_name for display
            semester_start: Semester start date (YYYY-MM-DD)
            semester_end: Semester end date (YYYY-MM-DD)
            config: Configuration dictionary with scoring parameters
        """
        self.course_metrics = course_metrics
        self.course_names = course_names
        self.semester_start = pd.to_datetime(semester_start) if semester_start else None
        self.semester_end = pd.to_datetime(semester_end) if semester_end else None

        # Load scoring configuration with defaults
        report_config = config.get('report', {}) if config else {}
        engagement_config = report_config.get('engagement_scoring', {})
        feature_config = report_config.get('feature_scoring', {})

        # Engagement scoring parameters
        self.eng_consistent_weight = engagement_config.get('consistent_weight', 10)
        self.eng_moderate_weight = engagement_config.get('moderate_weight', 3)
        self.eng_sporadic_weight = engagement_config.get('sporadic_weight', 1)
        self.eng_expected_consistent = engagement_config.get('expected_consistent_pct', 5)
        self.eng_expected_moderate = engagement_config.get('expected_moderate_pct', 25)
        self.eng_expected_sporadic = engagement_config.get('expected_sporadic_pct', 70)
        self.eng_excellent_threshold = engagement_config.get('excellent_threshold', 5.0)
        self.eng_good_threshold = engagement_config.get('good_threshold', 2.5)
        self.eng_moderate_threshold = engagement_config.get('moderate_threshold', 1.7)

        # Feature scoring parameters
        self.feat_high_weight = feature_config.get('high_weight', 5)
        self.feat_moderate_weight = feature_config.get('moderate_weight', 3)
        self.feat_low_weight = feature_config.get('low_weight', 1)
        self.feat_high_threshold = feature_config.get('high_threshold', 40)
        self.feat_moderate_threshold = feature_config.get('moderate_threshold', 20)
        self.feat_expected_high = feature_config.get('expected_high_count', 2)
        self.feat_expected_moderate = feature_config.get('expected_moderate_count', 3)
        self.feat_expected_low = feature_config.get('expected_low_count', 2)

    def _aggregate_wau_metrics(self, metrics_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Aggregate WAU metrics across multiple courses

        Args:
            metrics_list: List of course weekly_metrics DataFrames

        Returns:
            Aggregated DataFrame with total WAU across courses
        """
        if not metrics_list:
            return pd.DataFrame()

        # Get all unique weeks across all courses
        all_weeks = set()
        for df in metrics_list:
            all_weeks.update(df['week_number'].unique())

        aggregated_data = []
        for week_num in sorted(all_weeks):
            total_wau = 0
            total_enrolled = 0
            from_date = None
            to_date = None

            for df in metrics_list:
                week_data = df[df['week_number'] == week_num]
                if len(week_data) > 0:
                    row = week_data.iloc[0]
                    total_wau += int(row.get('wau_count', 0))
                    total_enrolled += int(row.get('total_enrolled', 0))
                    if from_date is None:
                        from_date = row['from_date']
                        to_date = row['to_date']

            wau_pct = (total_wau / total_enrolled * 100) if total_enrolled > 0 else 0

            aggregated_data.append({
                'week_number': week_num,
                'from_date': from_date,
                'to_date': to_date,
                'wau_count': total_wau,
                'total_enrolled': total_enrolled,
                'wau_percentage': wau_pct
            })

        return pd.DataFrame(aggregated_data)

    def _aggregate_engagement_metrics(self, metrics_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Aggregate engagement persistence metrics across multiple courses

        Uses proper aggregation: sum all students in each category across courses,
        then calculate percentages based on total enrolled.

        Args:
            metrics_list: List of course weekly_metrics DataFrames

        Returns:
            Aggregated DataFrame with engagement persistence
        """
        if not metrics_list:
            return pd.DataFrame()

        all_weeks = set()
        for df in metrics_list:
            all_weeks.update(df['week_number'].unique())

        aggregated_data = []
        for week_num in sorted(all_weeks):
            # Sum absolute counts across courses
            total_enrolled = 0
            total_consistent_students = 0
            total_moderate_students = 0
            total_sporadic_students = 0

            for df in metrics_list:
                week_data = df[df['week_number'] == week_num]
                if len(week_data) > 0:
                    row = week_data.iloc[0]
                    enrolled = int(row.get('total_enrolled', 0))

                    if enrolled > 0:
                        total_enrolled += enrolled

                        # Convert percentages to absolute counts
                        consistent_pct = row.get('persistent_consistent_pct', 0)
                        moderate_pct = row.get('persistent_moderate_pct', 0)
                        sporadic_pct = row.get('persistent_sporadic_pct', 0)

                        total_consistent_students += int(round((consistent_pct / 100) * enrolled))
                        total_moderate_students += int(round((moderate_pct / 100) * enrolled))
                        total_sporadic_students += int(round((sporadic_pct / 100) * enrolled))

            # Convert back to percentages based on total enrolled
            consistent_pct = (total_consistent_students / total_enrolled * 100) if total_enrolled > 0 else 0
            moderate_pct = (total_moderate_students / total_enrolled * 100) if total_enrolled > 0 else 0
            sporadic_pct = (total_sporadic_students / total_enrolled * 100) if total_enrolled > 0 else 0

            aggregated_data.append({
                'week_number': week_num,
                'total_enrolled': total_enrolled,
                'persistent_consistent_pct': consistent_pct,
                'persistent_moderate_pct': moderate_pct,
                'persistent_sporadic_pct': sporadic_pct
            })

        return pd.DataFrame(aggregated_data)

    def _aggregate_feature_metrics(self, metrics_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Aggregate feature usage metrics across multiple courses

        Uses proper aggregation: sum all users of each feature across courses,
        then calculate percentages based on total WAU.

        Args:
            metrics_list: List of course weekly_metrics DataFrames

        Returns:
            Aggregated DataFrame with feature usage
        """
        if not metrics_list:
            return pd.DataFrame()

        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        all_weeks = set()
        for df in metrics_list:
            all_weeks.update(df['week_number'].unique())

        aggregated_data = []
        for week_num in sorted(all_weeks):
            total_wau = 0
            feature_user_counts = {f: 0 for f in features}

            for df in metrics_list:
                week_data = df[df['week_number'] == week_num]
                if len(week_data) > 0:
                    row = week_data.iloc[0]
                    wau = int(row.get('wau_count', 0))

                    if wau > 0:
                        total_wau += wau

                        # Convert percentages to absolute counts
                        for feature in features:
                            col = f'feature_usage_{feature}'
                            if col in df.columns:
                                feature_pct = row.get(col, 0)
                                feature_user_counts[feature] += int(round((feature_pct / 100) * wau))

            # Convert back to percentages based on total WAU
            week_data = {'week_number': week_num}
            for feature in features:
                pct = (feature_user_counts[feature] / total_wau * 100) if total_wau > 0 else 0
                week_data[f'feature_usage_{feature}'] = pct

            aggregated_data.append(week_data)

        return pd.DataFrame(aggregated_data)

    def generate_html_report(self, output_path: str, institute_name: str, executive_summary: str = None):
        """
        Generate complete HTML report for an institute

        Args:
            output_path: Path to save HTML file
            institute_name: Name of the institute
            executive_summary: Deprecated - summary is now auto-generated from aggregated data
        """
        # Aggregate metrics across all courses
        metrics_list = list(self.course_metrics.values())

        agg_wau = self._aggregate_wau_metrics(metrics_list)
        agg_engagement = self._aggregate_engagement_metrics(metrics_list)
        agg_features = self._aggregate_feature_metrics(metrics_list)

        # Get last week info for header
        if len(agg_wau) > 0:
            latest_week = agg_wau.iloc[-1]
            week_num = int(latest_week['week_number'])
            from_date = pd.to_datetime(latest_week['from_date']).strftime('%b %d, %Y')
            to_date = pd.to_datetime(latest_week['to_date']).strftime('%b %d, %Y')
            week_info = f"Week {week_num} ({from_date} - {to_date})"
        else:
            week_info = ""

        # Calculate engagement and feature scores for executive summary
        engagement_score = 0
        feature_score = 0
        expected_eng_score = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                              (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                              (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)

        features_list = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = {'quiz': 'Quiz', 'evaluation': 'Evaluation', 'mind_map': 'Mind Map',
                         'search': 'Search', 'short_summary': 'Short Summary',
                         'long_summary': 'Long Summary', 'concepts': 'Concepts'}
        expected_feat_score = (self.feat_expected_high * self.feat_high_weight +
                              self.feat_expected_moderate * self.feat_moderate_weight +
                              self.feat_expected_low * self.feat_low_weight) / len(features_list)

        # Calculate per-course engagement scores for this week
        course_eng_scores_this_week = {}
        course_eng_scores_avg = {}

        if len(agg_engagement) > 0 and len(agg_wau) > 0:
            latest_eng = agg_engagement.iloc[-1]
            latest_wau_for_eng = agg_wau.iloc[-1]

            consistent = latest_eng.get('persistent_consistent_pct', 0)
            moderate = latest_eng.get('persistent_moderate_pct', 0)
            sporadic = latest_eng.get('persistent_sporadic_pct', 0)
            total_enrolled = int(latest_wau_for_eng.get('total_enrolled', 0))

            if total_enrolled > 0:
                consistent_count = (consistent / 100) * total_enrolled
                moderate_count = (moderate / 100) * total_enrolled
                sporadic_count = (sporadic / 100) * total_enrolled

                engagement_score = (consistent_count * self.eng_consistent_weight +
                                  moderate_count * self.eng_moderate_weight +
                                  sporadic_count * self.eng_sporadic_weight) / total_enrolled

            # Calculate per-course engagement scores
            for course_id, metrics_df in self.course_metrics.items():
                if len(metrics_df) > 0:
                    # This week's score
                    latest_course = metrics_df.iloc[-1]
                    cons = latest_course.get('persistent_consistent_pct', 0)
                    mod = latest_course.get('persistent_moderate_pct', 0)
                    spor = latest_course.get('persistent_sporadic_pct', 0)
                    enr = latest_course.get('total_enrolled', 0)

                    if enr > 0:
                        cons_cnt = (cons / 100) * enr
                        mod_cnt = (mod / 100) * enr
                        spor_cnt = (spor / 100) * enr
                        score = (cons_cnt * self.eng_consistent_weight +
                                mod_cnt * self.eng_moderate_weight +
                                spor_cnt * self.eng_sporadic_weight) / enr
                        course_eng_scores_this_week[course_id] = score

                    # Average score
                    scores = []
                    for _, row in metrics_df.iterrows():
                        cons = row.get('persistent_consistent_pct', 0)
                        mod = row.get('persistent_moderate_pct', 0)
                        spor = row.get('persistent_sporadic_pct', 0)
                        enr = row.get('total_enrolled', 0)
                        if enr > 0:
                            cons_cnt = (cons / 100) * enr
                            mod_cnt = (mod / 100) * enr
                            spor_cnt = (spor / 100) * enr
                            sc = (cons_cnt * self.eng_consistent_weight +
                                 mod_cnt * self.eng_moderate_weight +
                                 spor_cnt * self.eng_sporadic_weight) / enr
                            scores.append(sc)
                    if scores:
                        course_eng_scores_avg[course_id] = sum(scores) / len(scores)

        # Calculate per-feature usage scores
        feature_usage_this_week = {}
        feature_usage_avg = {}

        if len(agg_features) > 0:
            latest_feat = agg_features.iloc[-1]
            high_count = 0
            moderate_count = 0
            low_count = 0

            for feature in features_list:
                col = f'feature_usage_{feature}'
                if col in agg_features.columns:
                    usage = latest_feat.get(col, 0)
                    feature_usage_this_week[feature] = usage
                    if usage >= self.feat_high_threshold:
                        high_count += 1
                    elif usage >= self.feat_moderate_threshold:
                        moderate_count += 1
                    else:
                        low_count += 1

                    # Calculate average
                    avg_usage = agg_features[col].mean() if col in agg_features.columns else 0
                    feature_usage_avg[feature] = avg_usage

            feature_score = (high_count * self.feat_high_weight +
                           moderate_count * self.feat_moderate_weight +
                           low_count * self.feat_low_weight) / len(features_list)

        # Find top and bottom courses for engagement
        top_eng_course = None
        bottom_eng_course = None
        top_eng_score_week = 0
        bottom_eng_score_week = float('inf')
        top_eng_score_avg = 0
        bottom_eng_score_avg = float('inf')

        if course_eng_scores_this_week:
            for course_id in course_eng_scores_this_week:
                score_week = course_eng_scores_this_week.get(course_id, 0)
                score_avg = course_eng_scores_avg.get(course_id, 0)

                if score_week > top_eng_score_week:
                    top_eng_score_week = score_week
                    top_eng_course = self.course_names.get(course_id, course_id)
                    top_eng_score_avg = score_avg

                if score_week < bottom_eng_score_week:
                    bottom_eng_score_week = score_week
                    bottom_eng_course = self.course_names.get(course_id, course_id)
                    bottom_eng_score_avg = score_avg

        # Find top and bottom features
        top_feature = None
        bottom_feature = None
        top_feat_usage_week = 0
        bottom_feat_usage_week = float('inf')
        top_feat_usage_avg = 0
        bottom_feat_usage_avg = float('inf')

        if feature_usage_this_week:
            for feature in features_list:
                usage_week = feature_usage_this_week.get(feature, 0)
                usage_avg = feature_usage_avg.get(feature, 0)

                if usage_week > top_feat_usage_week:
                    top_feat_usage_week = usage_week
                    top_feature = feature_labels.get(feature, feature)
                    top_feat_usage_avg = usage_avg

                if usage_week < bottom_feat_usage_week:
                    bottom_feat_usage_week = usage_week
                    bottom_feature = feature_labels.get(feature, feature)
                    bottom_feat_usage_avg = usage_avg

        # Generate executive summary from aggregated data
        exec_summary_html = self._generate_executive_summary_from_agg(
            agg_wau, len(self.course_metrics), engagement_score, feature_score,
            expected_eng_score, expected_feat_score,
            top_eng_course, top_eng_score_week, top_eng_score_avg,
            bottom_eng_course, bottom_eng_score_week, bottom_eng_score_avg,
            top_feature, top_feat_usage_week, top_feat_usage_avg,
            bottom_feature, bottom_feat_usage_week, bottom_feat_usage_avg
        )

        html = self._generate_html_header(institute_name, week_info)
        html += self._generate_executive_summary_section(exec_summary_html)
        html += self._generate_wau_trend_section(agg_wau)
        html += self._generate_engagement_persistence_section(agg_engagement, agg_wau)
        html += self._generate_feature_usage_section(agg_features, agg_wau)
        html += self._generate_html_footer()

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Institute weekly progress report generated: {output_path}")

    def _generate_html_header(self, institute_name: str, week_info: str = "") -> str:
        """Generate HTML header with CSS"""
        week_subtitle = f"<p style='font-size: 1.2em; margin-top: 15px;'><strong>Last Full {week_info}</strong></p>" if week_info else ""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{institute_name} - Institute Weekly Progress Report ({week_info})</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 5px 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .executive-summary {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 6px solid #764ba2;
        }}
        .executive-summary h2 {{
            margin-top: 0;
            color: #2d3436;
            font-size: 1.8em;
        }}
        .executive-summary p {{
            font-size: 1.15em;
            line-height: 1.8;
            color: #2d3436;
            margin: 15px 0;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #764ba2;
            border-bottom: 2px solid #764ba2;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .section h3 {{
            color: #667eea;
            margin-top: 20px;
        }}
        .chart-container {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            position: relative;
            height: 400px;
        }}
        .chart-container canvas {{
            display: block;
            width: 100% !important;
            height: 100% !important;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #764ba2;
        }}
        details {{
            margin: 20px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }}
        summary {{
            cursor: pointer;
            font-weight: 600;
            color: #764ba2;
            padding: 10px;
            user-select: none;
            font-size: 1.1em;
        }}
        summary:hover {{
            color: #667eea;
        }}
        .course-breakdown {{
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 6px;
        }}
        .course-breakdown h4 {{
            color: #667eea;
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 1em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #764ba2;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .tooltip {{
            position: relative;
            display: inline-block;
            cursor: help;
            border-bottom: 1px dotted #666;
        }}
        .tooltip .tooltiptext {{
            visibility: hidden;
            width: 300px;
            background-color: #555;
            color: #fff;
            text-align: left;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1000;
            bottom: 125%;
            left: 50%;
            margin-left: -150px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.85em;
            line-height: 1.4;
        }}
        .tooltip .tooltiptext::after {{
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: #555 transparent transparent transparent;
        }}
        .tooltip:hover .tooltiptext {{
            visibility: visible;
            opacity: 1;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>📊 Institute Weekly Progress Report</h1>
        <p><strong>{institute_name}</strong></p>
        <p>Semester-Long Engagement Analysis</p>
        {week_subtitle}
    </div>
"""

    def _generate_executive_summary_from_agg(self, agg_wau: pd.DataFrame, num_courses: int,
                                              engagement_score: float = 0, feature_score: float = 0,
                                              expected_eng_score: float = 0, expected_feat_score: float = 0,
                                              top_eng_course: str = None, top_eng_week: float = 0, top_eng_avg: float = 0,
                                              bottom_eng_course: str = None, bottom_eng_week: float = 0, bottom_eng_avg: float = 0,
                                              top_feature: str = None, top_feat_week: float = 0, top_feat_avg: float = 0,
                                              bottom_feature: str = None, bottom_feat_week: float = 0, bottom_feat_avg: float = 0) -> str:
        """Generate executive summary from aggregated data with tooltips and top/bottom breakdowns"""
        if len(agg_wau) == 0:
            return "No data available for this institute."

        latest = agg_wau.iloc[-1]
        week_num = int(latest['week_number'])
        total_wau = int(latest['wau_count'])
        total_enrolled = int(latest['total_enrolled'])
        wau_pct = latest['wau_percentage']

        # Prepare engagement tooltip
        eng_tooltip = f"Weighted score based on student persistence patterns. Expected: {expected_eng_score:.2f}. Higher scores indicate more consistent engagement over the semester."

        # Prepare feature tooltip
        feat_tooltip = f"Weighted score based on feature adoption rates. Expected: {expected_feat_score:.2f}. Higher scores indicate broader feature usage."

        # Engagement breakdown
        eng_breakdown = ""
        if top_eng_course:
            eng_breakdown = f"""
            <div style="margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 4px; font-size: 0.85em;">
                <div style="color: #2e7d32; font-weight: 600;">🔝 Top: {top_eng_course}</div>
                <div style="color: #666; margin-left: 20px;">This week: {top_eng_week:.2f} | Avg: {top_eng_avg:.2f}</div>
                <div style="color: #c62828; font-weight: 600; margin-top: 5px;">📉 Last: {bottom_eng_course}</div>
                <div style="color: #666; margin-left: 20px;">This week: {bottom_eng_week:.2f} | Avg: {bottom_eng_avg:.2f}</div>
            </div>
            """

        # Feature breakdown
        feat_breakdown = ""
        if top_feature:
            feat_breakdown = f"""
            <div style="margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 4px; font-size: 0.85em;">
                <div style="color: #2e7d32; font-weight: 600;">🔝 Top: {top_feature}</div>
                <div style="color: #666; margin-left: 20px;">This week: {top_feat_week:.1f}% | Avg: {top_feat_avg:.1f}%</div>
                <div style="color: #c62828; font-weight: 600; margin-top: 5px;">📉 Last: {bottom_feature}</div>
                <div style="color: #666; margin-left: 20px;">This week: {bottom_feat_week:.1f}% | Avg: {bottom_feat_avg:.1f}%</div>
            </div>
            """

        return f"""
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0; padding: 20px; background: white; border-radius: 8px;">
            <div style="padding: 15px; background: #e3f2fd; border-radius: 6px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #1565c0;">{total_enrolled}</div>
                <div style="color: #666; font-weight: 600;">Total Enrolled Students</div>
            </div>
            <div style="padding: 15px; background: #e8f5e9; border-radius: 6px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #2e7d32;">{total_wau}</div>
                <div style="color: #666; font-weight: 600;">Active Students (WAU)</div>
            </div>
            <div style="padding: 15px; background: #f3e5f5; border-radius: 6px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #7b1fa2;">{wau_pct:.1f}%</div>
                <div style="color: #666; font-weight: 600;">WAU Percentage</div>
            </div>
            <div style="padding: 15px; background: #fff3e0; border-radius: 6px; text-align: center;">
                <div style="font-size: 2em; font-weight: bold; color: #e65100;">{num_courses}</div>
                <div style="color: #666; font-weight: 600;">Active Courses</div>
            </div>
            <div style="padding: 15px; background: #e1f5fe; border-radius: 6px; text-align: left;">
                <div style="text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #0277bd;">{engagement_score:.2f}</div>
                    <div class="tooltip" style="color: #666; font-weight: 600;">
                        Consistency Engagement Score
                        <span class="tooltiptext">{eng_tooltip}</span>
                    </div>
                    <div style="font-size: 0.8em; color: #666; margin-top: 5px;">Expected: {expected_eng_score:.2f}</div>
                </div>
                {eng_breakdown}
            </div>
            <div style="padding: 15px; background: #f3e5f5; border-radius: 6px; text-align: left;">
                <div style="text-align: center;">
                    <div style="font-size: 2em; font-weight: bold; color: #6a1b9a;">{feature_score:.2f}</div>
                    <div class="tooltip" style="color: #666; font-weight: 600;">
                        Feature Usage Score
                        <span class="tooltiptext">{feat_tooltip}</span>
                    </div>
                    <div style="font-size: 0.8em; color: #666; margin-top: 5px;">Expected: {expected_feat_score:.2f}</div>
                </div>
                {feat_breakdown}
            </div>
        </div>
        """

    def _generate_executive_summary_section(self, executive_summary: str) -> str:
        """Generate executive summary section"""
        return f"""
    <div class="executive-summary">
        <h2>📋 Executive Summary</h2>
        <p>{executive_summary}</p>
    </div>
"""

    def _generate_wau_trend_section(self, agg_wau: pd.DataFrame) -> str:
        """Generate WAU trend chart with predicted ranges and semester markers"""
        if len(agg_wau) == 0:
            return ""

        latest = agg_wau.iloc[-1]
        latest_wau = int(latest['wau_count'])
        latest_pct = latest['wau_percentage']

        # Create date labels and expected ranges (similar to course view)
        if self.semester_start and self.semester_end:
            date_labels = []
            wau_pct = []
            expected_min = []
            expected_max = []

            current_date = self.semester_start
            week_num = 1

            while current_date <= self.semester_end:
                date_labels.append(current_date.strftime('%b %d'))

                # Find matching week
                matching_row = None
                for idx, row in agg_wau.iterrows():
                    row_from_date = pd.to_datetime(row['from_date'])
                    if abs((row_from_date - current_date).days) < 7:
                        matching_row = row
                        break

                if matching_row is not None:
                    wau_pct.append(float(matching_row['wau_percentage']))
                else:
                    wau_pct.append(None)

                # Expected ranges by semester phase
                total_weeks = int((self.semester_end - self.semester_start).days / 7) + 1
                if week_num <= 2:
                    expected_min.append(70)
                    expected_max.append(100)
                elif week_num >= total_weeks - 1:
                    expected_min.append(60)
                    expected_max.append(80)
                else:
                    expected_min.append(20)
                    expected_max.append(40)

                current_date += pd.Timedelta(days=7)
                week_num += 1
        else:
            date_labels = []
            for _, row in agg_wau.iterrows():
                from_date = pd.to_datetime(row['from_date'])
                date_labels.append(from_date.strftime('%b %d'))
            wau_pct = agg_wau['wau_percentage'].tolist()
            expected_min = []
            expected_max = []

        # Generate per-course WAU data for collapsible section
        per_course_wau = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#e67e22', '#95a5a6']

        for i, (course_id, df) in enumerate(self.course_metrics.items()):
            course_name = self.course_names.get(course_id, course_id)
            color = colors[i % len(colors)]

            wau_data = []
            for label in date_labels:
                matching_row = None
                for _, row in df.iterrows():
                    row_date = pd.to_datetime(row['from_date']).strftime('%b %d')
                    if row_date == label:
                        matching_row = row
                        break

                if matching_row is not None:
                    wau_data.append(float(matching_row['wau_percentage']))
                else:
                    wau_data.append(None)

            per_course_wau.append({
                'label': course_name,
                'data': wau_data,
                'borderColor': color,
                'backgroundColor': 'transparent',
                'borderWidth': 2,
                'tension': 0.4
            })

        date_labels_json = json.dumps(date_labels)
        wau_pct_json = json.dumps(wau_pct)
        expected_min_json = json.dumps(expected_min) if expected_min else '[]'
        expected_max_json = json.dumps(expected_max) if expected_max else '[]'
        per_course_wau_json = json.dumps(per_course_wau)

        return f"""
    <div class="section">
        <h2>2. Total Weekly Active Users (WAU) Trend</h2>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 20px 0;">
            <div style="text-align: center;">
                <div class="metric-value">{latest_wau}</div>
                <div style="color: #666; font-size: 0.9em;">Active Students This Week</div>
            </div>
            <div style="text-align: center;">
                <div class="metric-value">{latest_pct:.1f}%</div>
                <div style="color: #666; font-size: 0.9em;">WAU Percentage</div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="wauChart"></canvas>
        </div>

        <details>
            <summary>📊 Show Per-Course WAU Breakdown (Click to Expand)</summary>
            <div class="course-breakdown">
                <div class="chart-container">
                    <canvas id="wauPerCourseChart"></canvas>
                </div>
            </div>
        </details>

        <script>
        // Total WAU Chart
        const wauCtx = document.getElementById('wauChart').getContext('2d');
        new Chart(wauCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: [
                    {{
                        label: 'Institute WAU %',
                        data: {wau_pct_json},
                        borderColor: '#764ba2',
                        backgroundColor: 'rgba(118, 75, 162, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Expected Min',
                        data: {expected_min_json},
                        borderColor: '#ff7675',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        tension: 0,
                        fill: false,
                        pointRadius: 0
                    }},
                    {{
                        label: 'Expected Max',
                        data: {expected_max_json},
                        borderColor: '#00b894',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        tension: 0,
                        fill: false,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Institute Total Weekly Active Users % (with Expected Range)'
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Percentage (%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Week Starting'
                        }}
                    }}
                }}
            }}
        }});

        // Per-Course WAU Chart
        const wauPerCourseCtx = document.getElementById('wauPerCourseChart').getContext('2d');
        new Chart(wauPerCourseCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: {per_course_wau_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'WAU % by Course'
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Percentage (%)'
                        }}
                    }}
                }}
            }}
        }});
        </script>
    </div>
"""

    def _generate_engagement_persistence_section(self, agg_engagement: pd.DataFrame, agg_wau: pd.DataFrame) -> str:
        """Generate engagement persistence metrics with single graph for course scores"""
        if len(agg_engagement) == 0 or len(agg_wau) == 0:
            return ""

        latest_eng = agg_engagement.iloc[-1]
        latest_wau = agg_wau.iloc[-1]

        consistent = latest_eng.get('persistent_consistent_pct', 0)
        moderate = latest_eng.get('persistent_moderate_pct', 0)
        sporadic = latest_eng.get('persistent_sporadic_pct', 0)
        total_enrolled = int(latest_wau.get('total_enrolled', 0))

        # Calculate engagement score
        if total_enrolled > 0:
            consistent_count = (consistent / 100) * total_enrolled
            moderate_count = (moderate / 100) * total_enrolled
            sporadic_count = (sporadic / 100) * total_enrolled

            actual_score = (consistent_count * self.eng_consistent_weight +
                          moderate_count * self.eng_moderate_weight +
                          sporadic_count * self.eng_sporadic_weight) / total_enrolled

            expected_score = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                            (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                            (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)
            score_delta = actual_score - expected_score

            if actual_score >= self.eng_excellent_threshold:
                interpretation = "Excellent engagement"
                interp_color = "#2e7d32"
            elif actual_score >= self.eng_good_threshold:
                interpretation = "Good engagement"
                interp_color = "#388e3c"
            elif actual_score >= self.eng_moderate_threshold:
                interpretation = "Moderate engagement"
                interp_color = "#f57c00"
            else:
                interpretation = "Poor engagement"
                interp_color = "#c62828"
        else:
            actual_score = 0
            expected_score = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                            (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                            (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)
            score_delta = -expected_score
            interpretation = "No data"
            interp_color = "#666"

        # Create date labels
        date_labels = []
        for _, row in agg_engagement.iterrows():
            week_num = row['week_number']
            matching_wau = agg_wau[agg_wau['week_number'] == week_num]
            if len(matching_wau) > 0:
                from_date = pd.to_datetime(matching_wau.iloc[0]['from_date'])
                date_labels.append(from_date.strftime('%b %d'))

        consistent_data = agg_engagement['persistent_consistent_pct'].tolist()
        moderate_data = agg_engagement['persistent_moderate_pct'].tolist()
        sporadic_data = agg_engagement['persistent_sporadic_pct'].tolist()

        # Calculate engagement score for each week
        expected_score_val = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                         (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                         (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)

        engagement_scores = []
        for idx, row in agg_engagement.iterrows():
            cons_pct = row.get('persistent_consistent_pct', 0)
            mod_pct = row.get('persistent_moderate_pct', 0)
            spor_pct = row.get('persistent_sporadic_pct', 0)
            enrolled = row.get('total_enrolled', 0)

            if enrolled > 0:
                cons_count = (cons_pct / 100) * enrolled
                mod_count = (mod_pct / 100) * enrolled
                spor_count = (spor_pct / 100) * enrolled
                score = (cons_count * self.eng_consistent_weight +
                        mod_count * self.eng_moderate_weight +
                        spor_count * self.eng_sporadic_weight) / enrolled
                engagement_scores.append(score - expected_score_val)
            else:
                engagement_scores.append(None)

        # Generate per-course engagement SCORES (not full breakdown)
        per_course_eng_scores = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

        for i, (course_id, df) in enumerate(self.course_metrics.items()):
            course_name = self.course_names.get(course_id, course_id)
            color = colors[i % len(colors)]

            course_scores = []
            for label in date_labels:
                matching_row = None
                for _, row in df.iterrows():
                    row_date = pd.to_datetime(row['from_date']).strftime('%b %d')
                    if row_date == label:
                        matching_row = row
                        break

                if matching_row is not None:
                    cons = matching_row.get('persistent_consistent_pct', 0)
                    mod = matching_row.get('persistent_moderate_pct', 0)
                    spor = matching_row.get('persistent_sporadic_pct', 0)
                    enr = matching_row.get('total_enrolled', 0)

                    if enr > 0:
                        cons_cnt = (cons / 100) * enr
                        mod_cnt = (mod / 100) * enr
                        spor_cnt = (spor / 100) * enr
                        sc = (cons_cnt * self.eng_consistent_weight +
                              mod_cnt * self.eng_moderate_weight +
                              spor_cnt * self.eng_sporadic_weight) / enr
                        course_scores.append(sc - expected_score_val)
                    else:
                        course_scores.append(None)
                else:
                    course_scores.append(None)

            per_course_eng_scores.append({
                'label': course_name,
                'data': course_scores,
                'borderColor': color,
                'backgroundColor': 'transparent',
                'borderWidth': 2,
                'tension': 0.4
            })

        # Calculate dynamic axis range
        valid_scores = [s for s in engagement_scores if s is not None]
        if valid_scores:
            max_abs_deviation = max(abs(min(valid_scores)), abs(max(valid_scores)))
            score_axis_max = max(1, max_abs_deviation * 1.2)
            score_axis_min = -score_axis_max
        else:
            score_axis_max = 3
            score_axis_min = -3

        date_labels_json = json.dumps(date_labels)
        consistent_data_json = json.dumps(consistent_data)
        moderate_data_json = json.dumps(moderate_data)
        sporadic_data_json = json.dumps(sporadic_data)
        engagement_scores_json = json.dumps(engagement_scores)
        per_course_eng_scores_json = json.dumps(per_course_eng_scores)

        return f"""
    <div class="section">
        <h2>3. Engagement Persistence</h2>

        <!-- 2 Metric Boxes -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
            <div style="padding: 20px; background: #e3f2fd; border-radius: 8px; border: 2px solid {interp_color};">
                <div style="text-align: center;">
                    <div style="font-size: 2.5em; font-weight: bold; color: {interp_color};">{actual_score:.2f}</div>
                    <div style="color: #1565c0; font-weight: 600; font-size: 1.1em; margin: 5px 0;">Consistency Engagement Score</div>
                    <div style="font-size: 0.9em; color: #666;">{interpretation}</div>
                    <div style="font-size: 0.85em; color: {'green' if score_delta >= 0 else 'red'}; margin-top: 8px;">
                        {'↑' if score_delta > 0 else '↓' if score_delta < 0 else '—'} {score_delta:+.2f} vs expected
                    </div>
                </div>
            </div>
            <div style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 2px solid #ddd;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #2e7d32;">{consistent:.0f}%</div>
                        <div style="color: #1b5e20; font-weight: 600; font-size: 0.9em;">Consistent</div>
                        <div style="font-size: 0.75em; color: #666;">≥60% weeks</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #f57c00;">{moderate:.0f}%</div>
                        <div style="color: #e65100; font-weight: 600; font-size: 0.9em;">Moderate</div>
                        <div style="font-size: 0.75em; color: #666;">25-59% weeks</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #c62828;">{sporadic:.0f}%</div>
                        <div style="color: #b71c1c; font-weight: 600; font-size: 0.9em;">Sporadic</div>
                        <div style="font-size: 0.75em; color: #666;"><25% weeks</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="persistenceChart"></canvas>
        </div>

        <details>
            <summary>📊 Show Consistency Engagement Score by Course (Click to Expand)</summary>
            <div class="course-breakdown">
                <div class="chart-container">
                    <canvas id="engScorePerCourseChart"></canvas>
                </div>
            </div>
        </details>

        <script>
        // Total Engagement Chart
        const persistenceCtx = document.getElementById('persistenceChart').getContext('2d');
        new Chart(persistenceCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: [
                    {{
                        label: 'Consistent ≥60%',
                        data: {consistent_data_json},
                        borderColor: '#81c784',
                        backgroundColor: 'rgba(129, 199, 132, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Moderate 25-59%',
                        data: {moderate_data_json},
                        borderColor: '#ffb74d',
                        backgroundColor: 'rgba(255, 183, 77, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Sporadic <25%',
                        data: {sporadic_data_json},
                        borderColor: '#e57373',
                        backgroundColor: 'rgba(229, 115, 115, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Institute Eng. Score',
                        data: {engagement_scores_json},
                        borderColor: '#764ba2',
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: false,
                        yAxisID: 'y1',
                        type: 'line'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Institute Engagement Persistence Distribution & Score Over Time'
                    }}
                }},
                scales: {{
                    y: {{
                        stacked: true,
                        beginAtZero: true,
                        max: 100,
                        position: 'left',
                        title: {{
                            display: true,
                            text: 'Percentage of Students (%)'
                        }}
                    }},
                    y1: {{
                        min: {score_axis_min:.1f},
                        max: {score_axis_max:.1f},
                        position: 'right',
                        title: {{
                            display: true,
                            text: 'Consistency Engagement Score (Deviation from Expected)'
                        }},
                        grid: {{
                            drawOnChartArea: true,
                            color: function(context) {{
                                if (context.tick.value === 0) return '#764ba2';
                                return 'rgba(0, 0, 0, 0.05)';
                            }},
                            lineWidth: function(context) {{
                                if (context.tick.value === 0) return 2;
                                return 1;
                            }}
                        }}
                    }},
                    x: {{
                        stacked: true
                    }}
                }}
            }}
        }});

        // Per-Course Consistency Engagement Scores Chart
        const engScorePerCourseCtx = document.getElementById('engScorePerCourseChart').getContext('2d');
        new Chart(engScorePerCourseCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: {per_course_eng_scores_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Consistency Engagement Score by Course (Deviation from Expected)'
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        min: {score_axis_min:.1f},
                        max: {score_axis_max:.1f},
                        title: {{
                            display: true,
                            text: 'Score (Deviation from Expected)'
                        }},
                        grid: {{
                            color: function(context) {{
                                if (context.tick.value === 0) return '#764ba2';
                                return 'rgba(0, 0, 0, 0.1)';
                            }},
                            lineWidth: function(context) {{
                                if (context.tick.value === 0) return 2;
                                return 1;
                            }}
                        }}
                    }}
                }}
            }}
        }});
        </script>
    </div>
"""

    def _generate_feature_usage_section(self, agg_features: pd.DataFrame, agg_wau: pd.DataFrame) -> str:
        """Generate feature usage trends with single graph for course scores"""
        if len(agg_features) == 0 or len(agg_wau) == 0:
            return ""

        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']
        num_features = len(features)

        # Create date labels
        date_labels = []
        for _, row in agg_features.iterrows():
            week_num = row['week_number']
            matching_wau = agg_wau[agg_wau['week_number'] == week_num]
            if len(matching_wau) > 0:
                from_date = pd.to_datetime(matching_wau.iloc[0]['from_date'])
                date_labels.append(from_date.strftime('%b %d'))

        # Calculate feature scores for each week
        feature_scores = []
        for _, row in agg_features.iterrows():
            high_count = 0
            moderate_count = 0
            low_count = 0

            for feature in features:
                col = f'feature_usage_{feature}'
                if col in agg_features.columns:
                    usage = row.get(col, 0)
                    if usage >= self.feat_high_threshold:
                        high_count += 1
                    elif usage >= self.feat_moderate_threshold:
                        moderate_count += 1
                    else:
                        low_count += 1

            score = (high_count * self.feat_high_weight +
                    moderate_count * self.feat_moderate_weight +
                    low_count * self.feat_low_weight) / num_features
            feature_scores.append(score)

        # Latest week metrics
        latest = agg_features.iloc[-1]
        high_count_latest = 0
        moderate_count_latest = 0
        low_count_latest = 0

        for feature in features:
            col = f'feature_usage_{feature}'
            if col in agg_features.columns:
                usage = latest.get(col, 0)
                if usage >= self.feat_high_threshold:
                    high_count_latest += 1
                elif usage >= self.feat_moderate_threshold:
                    moderate_count_latest += 1
                else:
                    low_count_latest += 1

        actual_feature_score = (high_count_latest * self.feat_high_weight +
                                moderate_count_latest * self.feat_moderate_weight +
                                low_count_latest * self.feat_low_weight) / num_features

        expected_feature_score = (self.feat_expected_high * self.feat_high_weight +
                                 self.feat_expected_moderate * self.feat_moderate_weight +
                                 self.feat_expected_low * self.feat_low_weight) / num_features

        score_delta = actual_feature_score - expected_feature_score

        # Prepare individual feature datasets for detailed chart
        datasets_features = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

        for i, feature in enumerate(features):
            col = f'feature_usage_{feature}'
            if col in agg_features.columns:
                data = agg_features[col].tolist()
                datasets_features.append({
                    'label': feature_labels[i],
                    'data': data,
                    'borderColor': colors[i],
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'tension': 0.4,
                    'fill': False
                })

        # Generate per-course feature SCORES (not full breakdown)
        per_course_feat_scores = []

        for i, (course_id, df) in enumerate(self.course_metrics.items()):
            course_name = self.course_names.get(course_id, course_id)
            color = colors[i % len(colors)]

            course_scores = []
            for label in date_labels:
                matching_row = None
                for _, row in df.iterrows():
                    row_date = pd.to_datetime(row['from_date']).strftime('%b %d')
                    if row_date == label:
                        matching_row = row
                        break

                if matching_row is not None:
                    high = 0
                    mod = 0
                    low = 0
                    for feature in features:
                        col = f'feature_usage_{feature}'
                        if col in df.columns:
                            usage = matching_row.get(col, 0)
                            if usage >= self.feat_high_threshold:
                                high += 1
                            elif usage >= self.feat_moderate_threshold:
                                mod += 1
                            else:
                                low += 1
                    sc = (high * self.feat_high_weight +
                          mod * self.feat_moderate_weight +
                          low * self.feat_low_weight) / num_features
                    course_scores.append(sc - expected_feature_score)
                else:
                    course_scores.append(None)

            per_course_feat_scores.append({
                'label': course_name,
                'data': course_scores,
                'borderColor': color,
                'backgroundColor': 'transparent',
                'borderWidth': 2,
                'tension': 0.4
            })

        # Calculate dynamic max for score axis
        valid_scores = [s for s in feature_scores if s is not None]
        if valid_scores:
            max_score = max(valid_scores)
            min_score = min(valid_scores)
            score_axis_max = max(3, max_score * 1.1)
            score_axis_min = min(score_axis_max * -1, min_score * 1.1)
        else:
            score_axis_max = self.feat_high_weight
            score_axis_min = -self.feat_high_weight

        date_labels_json = json.dumps(date_labels)
        datasets_features_json = json.dumps(datasets_features)
        feature_scores_json = json.dumps(feature_scores)
        per_course_feat_scores_json = json.dumps(per_course_feat_scores)

        # Latest week feature usage table
        feature_table_rows = ""
        for i, feature in enumerate(features):
            col = f'feature_usage_{feature}'
            if col in agg_features.columns:
                usage = latest[col]
                status = "✅" if usage >= self.feat_high_threshold else ("⚠️" if usage >= self.feat_moderate_threshold else "❌")

                feature_table_rows += f"""
                <tr>
                    <td>{feature_labels[i]}</td>
                    <td style="text-align: center;">{usage:.1f}% {status}</td>
                </tr>
                """

        return f"""
    <div class="section">
        <h2>4. Feature Usage Trends</h2>

        <!-- 2 Metric Boxes -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
            <div style="padding: 20px; background: #e3f2fd; border-radius: 8px; border: 2px solid #764ba2;">
                <div style="text-align: center;">
                    <div style="font-size: 2.5em; font-weight: bold; color: #764ba2;">{actual_feature_score:.2f}</div>
                    <div style="color: #1565c0; font-weight: 600; font-size: 1.1em; margin: 5px 0;">Feature Usage Score</div>
                    <div style="font-size: 0.9em; color: #666;">Out of {self.feat_high_weight:.0f}</div>
                    <div style="font-size: 0.85em; color: {'green' if score_delta >= 0 else 'red'}; margin-top: 8px;">
                        {'↑' if score_delta > 0 else '↓' if score_delta < 0 else '—'} {score_delta:+.2f} vs expected
                    </div>
                </div>
            </div>
            <div style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 2px solid #ddd;">
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #2e7d32;">{high_count_latest}</div>
                        <div style="color: #1b5e20; font-weight: 600; font-size: 0.9em;">High</div>
                        <div style="font-size: 0.75em; color: #666;">>={self.feat_high_threshold}%</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #f57c00;">{moderate_count_latest}</div>
                        <div style="color: #e65100; font-weight: 600; font-size: 0.9em;">Moderate</div>
                        <div style="font-size: 0.75em; color: #666;">{self.feat_moderate_threshold}-{self.feat_high_threshold-1}%</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold; color: #c62828;">{low_count_latest}</div>
                        <div style="color: #b71c1c; font-weight: 600; font-size: 0.9em;">Low</div>
                        <div style="font-size: 0.75em; color: #666;"><{self.feat_moderate_threshold}%</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Top Row: Table (left) + Score Chart (right) -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 20px;">
            <div>
                <h3>Latest Week Usage Rates</h3>
                <table>
                    <tr>
                        <th>Feature</th>
                        <th style="text-align: center;">Usage % (Status)</th>
                    </tr>
                    {feature_table_rows}
                </table>
                <p style="font-size: 0.9em; color: #666; margin-top: 15px;">
                    ✅ High: >={self.feat_high_threshold}% | ⚠️ Moderate: {self.feat_moderate_threshold}-{self.feat_high_threshold-1}% | ❌ Low: <{self.feat_moderate_threshold}%
                </p>
            </div>

            <div class="chart-container">
                <canvas id="featureScoreChart"></canvas>
            </div>
        </div>

        <!-- Collapsible Total Feature Trends -->
        <details open>
            <summary>📊 Show Institute Feature Trends (Click to Collapse)</summary>
            <div class="course-breakdown">
                <div class="chart-container">
                    <canvas id="featureDetailChart"></canvas>
                </div>
            </div>
        </details>

        <!-- Collapsible Per-Course Feature Scores -->
        <details>
            <summary>📊 Show Feature Score by Course (Click to Expand)</summary>
            <div class="course-breakdown">
                <div class="chart-container">
                    <canvas id="featScorePerCourseChart"></canvas>
                </div>
            </div>
        </details>

        <script>
        // Feature Score Chart
        const featureScoreCtx = document.getElementById('featureScoreChart').getContext('2d');
        const expectedScore = {expected_feature_score:.2f};
        const featureScoresRelative = {feature_scores_json}.map(s => s - expectedScore);

        const validScores = featureScoresRelative.filter(s => s !== null);
        const maxAbsDev = validScores.length > 0 ? Math.max(Math.abs(Math.min(...validScores)), Math.abs(Math.max(...validScores))) : 1;
        const scoreAxisMax = Math.max(1, maxAbsDev * 1.2);
        const scoreAxisMin = -scoreAxisMax;

        new Chart(featureScoreCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: [{{
                    label: 'Feature Usage Score (vs Expected)',
                    data: featureScoresRelative,
                    borderColor: '#764ba2',
                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Feature Usage Score Over Time'
                    }},
                    legend: {{
                        display: false
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                const relScore = context.parsed.y;
                                const absScore = {feature_scores_json}[context.dataIndex];
                                return `Score: ${{absScore.toFixed(2)}} (${{relScore >= 0 ? '+' : ''}}${{relScore.toFixed(2)}} vs expected)`;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        min: scoreAxisMin,
                        max: scoreAxisMax,
                        title: {{
                            display: true,
                            text: 'Score (Deviation from Expected)'
                        }},
                        grid: {{
                            color: function(context) {{
                                if (context.tick.value === 0) return '#764ba2';
                                return 'rgba(0, 0, 0, 0.1)';
                            }},
                            lineWidth: function(context) {{
                                if (context.tick.value === 0) return 2;
                                return 1;
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Detailed Feature Chart (collapsible)
        const featureDetailCtx = document.getElementById('featureDetailChart').getContext('2d');
        new Chart(featureDetailCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: {datasets_features_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Institute Feature Usage Rates Over Time'
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Usage Rate (%)'
                        }}
                    }}
                }}
            }}
        }});

        // Per-Course Feature Scores Chart
        const featScorePerCourseCtx = document.getElementById('featScorePerCourseChart').getContext('2d');
        new Chart(featScorePerCourseCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: {per_course_feat_scores_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Feature Usage Score by Course (Deviation from Expected)'
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        min: {score_axis_min:.1f},
                        max: {score_axis_max:.1f},
                        title: {{
                            display: true,
                            text: 'Score (Deviation from Expected)'
                        }},
                        grid: {{
                            color: function(context) {{
                                if (context.tick.value === 0) return '#764ba2';
                                return 'rgba(0, 0, 0, 0.1)';
                            }},
                            lineWidth: function(context) {{
                                if (context.tick.value === 0) return 2;
                                return 1;
                            }}
                        }}
                    }}
                }}
            }}
        }});
        </script>
    </div>
"""

    def _generate_html_footer(self) -> str:
        """Generate HTML footer"""
        return """
    <div style="text-align: center; color: #666; margin-top: 40px; padding: 20px; border-top: 1px solid #ddd;">
        <p>Generated with Institute Weekly Progress Analyzer</p>
        <p style="font-size: 0.9em;">Report Date: """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M') + """</p>
    </div>
</body>
</html>
"""