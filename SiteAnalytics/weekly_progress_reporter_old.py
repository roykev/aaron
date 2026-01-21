#!/usr/bin/env python3
"""
Weekly Progress Reporter
Generates HTML reports for weekly semester progression analysis
"""

import pandas as pd
from typing import Dict, Optional


class WeeklyProgressReporter:
    """Generates HTML reports for weekly progress metrics"""

    def __init__(self, weekly_metrics: pd.DataFrame, course_name: str = "Course", semester_start: str = None, semester_end: str = None, config: dict = None):
        """
        Initialize reporter

        Args:
            weekly_metrics: DataFrame with all weekly metrics
            course_name: Name of the course for display
            semester_start: Semester start date (YYYY-MM-DD)
            semester_end: Semester end date (YYYY-MM-DD)
            config: Configuration dictionary with scoring parameters
        """
        self.metrics = weekly_metrics
        self.course_name = course_name
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

    def generate_html_report(self, output_path: str, executive_summary: str, leaderboards: Dict = None):
        """
        Generate complete HTML report

        Args:
            output_path: Path to save HTML file
            executive_summary: Executive summary HTML string
            leaderboards: Optional dict with student leaderboard data
        """
        html = self._generate_html_header()
        html += self._generate_executive_summary_section(executive_summary)
        html += self._generate_wau_trend_section()
        html += self._generate_engagement_persistence_section()
        html += self._generate_feature_usage_section()
        html += self._generate_phase_performance_section()

        # Add leaderboards if available
        if leaderboards:
            html += self._generate_student_leaderboards_section(leaderboards)

        # At-risk section moved to last (after leaderboards)
        html += self._generate_at_risk_section()
        html += self._generate_html_footer()

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Weekly progress report generated: {output_path}")

    def _generate_html_header(self) -> str:
        """Generate HTML header with CSS"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Progress Report: {self.course_name}</title>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            border-left: 6px solid #667eea;
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
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .section h3 {{
            color: #764ba2;
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
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .status-on-track {{
            color: green;
            font-weight: bold;
        }}
        .status-warning {{
            color: orange;
            font-weight: bold;
        }}
        .status-critical {{
            color: red;
            font-weight: bold;
        }}
        .trend-up {{
            color: green;
        }}
        .trend-down {{
            color: red;
        }}
        .trend-stable {{
            color: gray;
        }}
        .phase-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-left: 10px;
        }}
        .phase-launch {{
            background: #74b9ff;
            color: white;
        }}
        .phase-valley {{
            background: #fdcb6e;
            color: #2d3436;
        }}
        .phase-preexam {{
            background: #55efc4;
            color: #2d3436;
        }}
        .sparkline {{
            display: inline-block;
            width: 100px;
            height: 30px;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>📊 Weekly Progress Report</h1>
        <p><strong>{self.course_name}</strong></p>
        <p>Semester-Long Engagement Analysis</p>
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

    def _generate_wau_trend_section(self) -> str:
        """Generate WAU trend chart"""
        # Create date labels from semester start to semester end
        if self.semester_start and self.semester_end:
            # Generate weekly date labels from semester start to end
            date_labels = []
            wau_pct = []
            wau_count = []
            expected_min = []
            expected_max = []

            current_date = self.semester_start
            week_num = 1

            while current_date <= self.semester_end:
                date_labels.append(current_date.strftime('%b %d'))

                # Find matching week by date instead of week_number
                # Convert from_date strings in metrics to datetime for comparison
                matching_row = None
                for idx, row in self.metrics.iterrows():
                    row_from_date = pd.to_datetime(row['from_date'])
                    # Check if this row's week overlaps with current_date
                    # A week overlaps if from_date <= current_date < to_date + 7 days
                    if abs((row_from_date - current_date).days) < 7:
                        matching_row = row
                        break

                if matching_row is not None:
                    wau_pct.append(float(matching_row['wau_percentage']) if pd.notna(matching_row['wau_percentage']) else None)
                    wau_count.append(int(matching_row['wau_count']) if pd.notna(matching_row['wau_count']) else None)
                    if 'expected_wau_min' in self.metrics.columns:
                        expected_min.append(float(matching_row['expected_wau_min']) if pd.notna(matching_row['expected_wau_min']) else None)
                        expected_max.append(float(matching_row['expected_wau_max']) if pd.notna(matching_row['expected_wau_max']) else None)
                else:
                    # Future week or no data - use null
                    wau_pct.append(None)
                    wau_count.append(None)
                    if 'expected_wau_min' in self.metrics.columns:
                        # Still show expected ranges for future weeks
                        # Estimate based on semester phase
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
            # Fallback to original behavior
            date_labels = []
            for _, row in self.metrics.iterrows():
                from_date = pd.to_datetime(row['from_date'])
                date_labels.append(from_date.strftime('%b %d'))

            wau_pct = self.metrics['wau_percentage'].tolist()
            wau_count = self.metrics['wau_count'].tolist()
            expected_min = self.metrics['expected_wau_min'].tolist() if 'expected_wau_min' in self.metrics.columns else []
            expected_max = self.metrics['expected_wau_max'].tolist() if 'expected_wau_max' in self.metrics.columns else []

        latest_wau = int([w for w in wau_count if w is not None][-1]) if any(w is not None for w in wau_count) else 0
        latest_pct = [w for w in wau_pct if w is not None][-1] if any(w is not None for w in wau_pct) else 0

        # Convert to JSON with proper None->null handling
        import json
        wau_pct_json = json.dumps(wau_pct)
        expected_min_json = json.dumps(expected_min) if expected_min else '[]'
        expected_max_json = json.dumps(expected_max) if expected_max else '[]'
        date_labels_json = json.dumps(date_labels)

        return f"""
    <div class="section">
        <h2>1. Weekly Active Users (WAU) Trend</h2>
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

        <script>
        const wauCtx = document.getElementById('wauChart').getContext('2d');
        new Chart(wauCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels_json},
                datasets: [
                    {{
                        label: 'WAU %',
                        data: {wau_pct_json},
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
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
                        text: 'Weekly Active Users % (with Expected Range)'
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
        </script>
    </div>
"""

    def _generate_engagement_persistence_section(self) -> str:
        """Generate engagement persistence metrics with enhanced tooltip"""
        if len(self.metrics) == 0:
            return ""

        latest = self.metrics.iloc[-1]
        consistent = latest.get('persistent_consistent_pct', 0)
        moderate = latest.get('persistent_moderate_pct', 0)
        sporadic = latest.get('persistent_sporadic_pct', 0)
        total_enrolled = int(latest.get('total_enrolled', 0))

        # Calculate engagement score using config weights
        if total_enrolled > 0:
            consistent_count = (consistent / 100) * total_enrolled
            moderate_count = (moderate / 100) * total_enrolled
            sporadic_count = (sporadic / 100) * total_enrolled

            actual_score = (consistent_count * self.eng_consistent_weight +
                          moderate_count * self.eng_moderate_weight +
                          sporadic_count * self.eng_sporadic_weight) / total_enrolled

            # Expected distribution from config
            expected_score = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                            (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                            (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)
            score_delta = actual_score - expected_score

            # Interpretation using config thresholds
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

        status = "On Track" if consistent >= 50 else ("Warning" if consistent >= 30 else "Critical")
        status_class = f"status-{'on-track' if status == 'On Track' else ('warning' if status == 'Warning' else 'critical')}"

        # Create date labels
        date_labels = []
        for _, row in self.metrics.iterrows():
            from_date = pd.to_datetime(row['from_date'])
            date_labels.append(from_date.strftime('%b %d'))

        consistent_data = self.metrics['persistent_consistent_pct'].tolist()
        moderate_data = self.metrics['persistent_moderate_pct'].tolist()
        sporadic_data = self.metrics['persistent_sporadic_pct'].tolist()

        # Calculate engagement score for each week using config weights
        # Display as deviation from expected (expected = 0 reference)
        expected_score = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                         (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                         (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)

        engagement_scores = []
        absolute_scores = []  # For tooltip
        for _, row in self.metrics.iterrows():
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
                absolute_scores.append(score)
                # Store as deviation from expected
                engagement_scores.append(score - expected_score)
            else:
                absolute_scores.append(None)
                engagement_scores.append(None)

        # Calculate dynamic axis range centered at 0 (expected)
        valid_scores = [s for s in engagement_scores if s is not None]
        if valid_scores:
            max_abs_deviation = max(abs(min(valid_scores)), abs(max(valid_scores)))
            score_axis_max = max(1, max_abs_deviation * 1.2)  # 20% padding
            score_axis_min = -score_axis_max  # Symmetric around 0
        else:
            score_axis_max = 3
            score_axis_min = -3

        # Convert to JSON
        import json
        absolute_scores_json = json.dumps(absolute_scores)

        return f"""
    <div class="section">
        <h2>2. Engagement Persistence</h2>

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

        <script>
        const engAbsoluteScores = {absolute_scores_json};
        const persistenceCtx = document.getElementById('persistenceChart').getContext('2d');
        new Chart(persistenceCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels},
                datasets: [
                    {{
                        label: 'Consistent ≥60%',
                        data: {consistent_data},
                        borderColor: '#81c784',
                        backgroundColor: 'rgba(129, 199, 132, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Moderate 25-59%',
                        data: {moderate_data},
                        borderColor: '#ffb74d',
                        backgroundColor: 'rgba(255, 183, 77, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Sporadic <25%',
                        data: {sporadic_data},
                        borderColor: '#e57373',
                        backgroundColor: 'rgba(229, 115, 115, 0.4)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }},
                    {{
                        label: 'Consistency Engagement Score',
                        data: {engagement_scores},
                        borderColor: '#667eea',
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
                        text: 'Engagement Persistence Distribution & Score Over Time'
                    }},
                    tooltip: {{
                        callbacks: {{
                            afterLabel: function(context) {{
                                if (context.dataset.label === 'Consistency Engagement Score' && context.dataIndex < engAbsoluteScores.length) {{
                                    const absScore = engAbsoluteScores[context.dataIndex];
                                    if (absScore !== null) {{
                                        const relScore = context.parsed.y;
                                        return `Absolute: ${{absScore.toFixed(2)}} | Relative: ${{relScore >= 0 ? '+' : ''}}${{relScore.toFixed(2)}}`;
                                    }}
                                }}
                                return '';
                            }}
                        }}
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
                                if (context.tick.value === 0) {{
                                    return '#667eea';  // Highlight zero line (expected)
                                }}
                                return 'rgba(0, 0, 0, 0.05)';
                            }},
                            lineWidth: function(context) {{
                                if (context.tick.value === 0) {{
                                    return 2;  // Thicker zero line
                                }}
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
        </script>
    </div>
"""

    def _generate_at_risk_section(self) -> str:
        """Generate at-risk students section"""
        if len(self.metrics) == 0:
            return ""

        latest = self.metrics.iloc[-1]
        at_risk_count = int(latest.get('at_risk_count', 0))
        at_risk_pct = latest.get('at_risk_percentage', 0)
        reactivation_rate = latest.get('reactivation_rate', 0)

        status = "Good" if at_risk_pct < 20 else ("Warning" if at_risk_pct < 30 else "Critical")
        status_class = f"status-{'on-track' if status == 'Good' else ('warning' if status == 'Warning' else 'critical')}"

        # Create date labels
        date_labels = []
        for _, row in self.metrics.iterrows():
            from_date = pd.to_datetime(row['from_date'])
            date_labels.append(from_date.strftime('%b %d'))

        at_risk_data = self.metrics['at_risk_percentage'].tolist()
        reactivation_data = self.metrics['reactivation_rate'].tolist()

        return f"""
    <div class="section">
        <h2>5. At-Risk Students & Reactivation</h2>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 20px 0;">
            <div style="text-align: center; padding: 20px; background: {'#ffebee' if at_risk_pct >= 20 else '#e8f5e9'}; border-radius: 8px;">
                <div style="font-size: 2.5em; font-weight: bold; color: {'#c62828' if at_risk_pct >= 20 else '#2e7d32'};">{at_risk_count}</div>
                <div style="color: #666; font-size: 1.1em; margin: 5px 0;">Students At-Risk</div>
                <div style="font-size: 0.9em; color: #666;">({at_risk_pct:.1f}% of enrolled)</div>
                <div class="{status_class}" style="margin-top: 10px;">{status}</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <div style="font-size: 2.5em; font-weight: bold; color: #1565c0;">{reactivation_rate:.0f}%</div>
                <div style="color: #666; font-size: 1.1em; margin: 5px 0;">Reactivation Rate</div>
                <div style="font-size: 0.9em; color: #666;">Inactive students who came back</div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
            <div class="chart-container">
                <canvas id="atRiskChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="reactivationChart"></canvas>
            </div>
        </div>

        <script>
        // At-Risk Chart
        const atRiskCtx = document.getElementById('atRiskChart').getContext('2d');
        new Chart(atRiskCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels},
                datasets: [
                    {{
                        label: 'At-Risk %',
                        data: {at_risk_data},
                        borderColor: '#c62828',
                        backgroundColor: 'rgba(198, 40, 40, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'At-Risk Students Over Time'
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

        // Reactivation Chart
        const reactivationCtx = document.getElementById('reactivationChart').getContext('2d');
        new Chart(reactivationCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels},
                datasets: [
                    {{
                        label: 'Reactivation Rate %',
                        data: {reactivation_data},
                        borderColor: '#1565c0',
                        backgroundColor: 'rgba(21, 101, 192, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Student Reactivation Rate'
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

        <p style="margin-top: 20px; padding: 15px; background: #fff3e0; border-left: 4px solid #f57c00; border-radius: 4px;">
            <strong>Note:</strong> At-risk = Inactive for 3+ consecutive weeks. Good: <20%, Warning: 20-30%, Critical: >30%
        </p>
    </div>
"""

    def _generate_feature_usage_section(self) -> str:
        """Generate feature usage trends with scoring and collapsible breakdown"""
        if len(self.metrics) == 0:
            return ""

        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        feature_labels = ['Quiz', 'Evaluation', 'Mind Map', 'Search', 'Short Summary', 'Long Summary', 'Concepts']
        num_features = len(features)

        # Create date labels
        date_labels = []
        for _, row in self.metrics.iterrows():
            from_date = pd.to_datetime(row['from_date'])
            date_labels.append(from_date.strftime('%b %d'))

        # Calculate feature scores for each week using config thresholds
        feature_scores = []
        for _, row in self.metrics.iterrows():
            high_count = 0
            moderate_count = 0
            low_count = 0

            for feature in features:
                col = f'feature_usage_{feature}'
                if col in self.metrics.columns:
                    usage = row.get(col, 0)
                    if usage >= self.feat_high_threshold:
                        high_count += 1
                    elif usage >= self.feat_moderate_threshold:
                        moderate_count += 1
                    else:
                        low_count += 1

            # Calculate weighted score
            score = (high_count * self.feat_high_weight +
                    moderate_count * self.feat_moderate_weight +
                    low_count * self.feat_low_weight) / num_features
            feature_scores.append(score)

        # Calculate latest week score and expected score
        latest = self.metrics.iloc[-1]
        high_count_latest = 0
        moderate_count_latest = 0
        low_count_latest = 0

        for feature in features:
            col = f'feature_usage_{feature}'
            if col in self.metrics.columns:
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

        # Prepare individual feature datasets for collapsible section
        datasets_features = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

        for i, feature in enumerate(features):
            col = f'feature_usage_{feature}'
            if col in self.metrics.columns:
                data = self.metrics[col].tolist()
                datasets_features.append({
                    'label': feature_labels[i],
                    'data': data,
                    'borderColor': colors[i],
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'tension': 0.4,
                    'fill': False
                })

        # Calculate dynamic max for score axis
        valid_scores = [s for s in feature_scores if s is not None]
        if valid_scores:
            max_score = max(valid_scores)
            score_axis_max = max(3, max_score * 1.1)
        else:
            score_axis_max = self.feat_high_weight

        # Convert to JSON
        import json
        datasets_features_json = json.dumps(datasets_features)
        feature_scores_json = json.dumps(feature_scores)

        # Latest week feature usage and WoW difference
        previous = self.metrics.iloc[-2] if len(self.metrics) > 1 else None

        feature_table_rows = ""
        for i, feature in enumerate(features):
            col = f'feature_usage_{feature}'
            if col in self.metrics.columns:
                usage = latest[col]
                status = "✅" if usage >= self.feat_high_threshold else ("⚠️" if usage >= self.feat_moderate_threshold else "❌")

                # Calculate WoW diff with arrow icons
                if previous is not None and col in previous.index:
                    prev_usage = previous[col]
                    wow_diff = usage - prev_usage
                    if wow_diff > 0.5:
                        wow_display = f'<span style="color: green;">↑ +{wow_diff:.1f}%</span>'
                    elif wow_diff < -0.5:
                        wow_display = f'<span style="color: red;">↓ {wow_diff:.1f}%</span>'
                    else:
                        wow_display = f'<span style="color: gray;">— {wow_diff:.1f}%</span>'
                else:
                    wow_display = '<span style="color: gray;">— N/A</span>'

                feature_table_rows += f"""
                <tr>
                    <td>{feature_labels[i]}</td>
                    <td style="text-align: center;">{usage:.1f}% {status}</td>
                    <td style="text-align: center;">{wow_display}</td>
                </tr>
                """

        return f"""
    <div class="section">
        <h2>3. Feature Usage Trends</h2>

        <!-- 2 Metric Boxes -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
            <div style="padding: 20px; background: #e3f2fd; border-radius: 8px; border: 2px solid #667eea;">
                <div style="text-align: center;">
                    <div style="font-size: 2.5em; font-weight: bold; color: #667eea;">{actual_feature_score:.2f}</div>
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
                        <th style="text-align: center;">WoW Change</th>
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

        <!-- Collapsible Detailed Feature Breakdown -->
        <details style="margin-top: 20px;">
            <summary style="cursor: pointer; font-weight: 600; color: #667eea; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                📊 Show Detailed Feature Trends (Click to Expand)
            </summary>
            <div class="chart-container" style="margin-top: 15px;">
                <canvas id="featureDetailChart"></canvas>
            </div>
        </details>

        <script>
        // Feature Score Chart (relative to expected, shown as deviation)
        const featureScoreCtx = document.getElementById('featureScoreChart').getContext('2d');
        const expectedScore = {expected_feature_score:.2f};
        const featureScoresRelative = {feature_scores_json}.map(s => s - expectedScore);

        // Calculate dynamic range for score chart centered at 0
        const validScores = featureScoresRelative.filter(s => s !== null);
        const maxAbsDev = validScores.length > 0 ? Math.max(Math.abs(Math.min(...validScores)), Math.abs(Math.max(...validScores))) : 1;
        const scoreAxisMax = Math.max(1, maxAbsDev * 1.2);
        const scoreAxisMin = -scoreAxisMax;

        new Chart(featureScoreCtx, {{
            type: 'line',
            data: {{
                labels: {date_labels},
                datasets: [{{
                    label: 'Feature Usage Score (vs Expected)',
                    data: featureScoresRelative,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
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
                                if (context.tick.value === 0) return '#667eea';
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
                labels: {date_labels},
                datasets: {datasets_features_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Individual Feature Usage Rates Over Time'
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
        </script>
    </div>
"""

    def _generate_phase_performance_section(self) -> str:
        """Phase performance section removed - now shown as markers in WAU graph"""
        return ""

    def _generate_student_leaderboards_section(self, leaderboards: Dict) -> str:
        """Generate student leaderboards section"""
        if not leaderboards or (not leaderboards.get('top_engaged') and not leaderboards.get('at_risk')):
            return ""

        top_engaged = leaderboards.get('top_engaged', [])
        at_risk = leaderboards.get('at_risk', [])

        # Top engaged table
        top_engaged_rows = ""
        for i, student in enumerate(top_engaged, 1):
            user_id_display = student['user_id'][:8] + '...' if len(student['user_id']) > 8 else student['user_id']
            engagement_score = student['engagement_score']
            weeks_active = student['weeks_active']
            persistence_pct = student['persistence_pct']
            total_events = student['total_events']

            # Medal icons for top 3
            rank_display = f"🥇 {i}" if i == 1 else (f"🥈 {i}" if i == 2 else (f"🥉 {i}" if i == 3 else str(i)))

            top_engaged_rows += f"""
            <tr>
                <td style="text-align: center;">{rank_display}</td>
                <td>{user_id_display}</td>
                <td style="text-align: center;">{engagement_score:.1f}</td>
                <td style="text-align: center;">{weeks_active}</td>
                <td style="text-align: center;">{persistence_pct:.0f}%</td>
                <td style="text-align: center;">{total_events}</td>
            </tr>
            """

        # At-risk table
        at_risk_rows = ""
        for i, student in enumerate(at_risk, 1):
            user_id_display = student['user_id'][:8] + '...' if len(student['user_id']) > 8 else student['user_id']
            weeks_inactive = student['weeks_inactive']
            last_active = student['last_active_week']
            weeks_active = student['weeks_active']
            persistence_pct = student['persistence_pct']

            # Color code by severity
            if weeks_inactive >= 6:
                severity_color = '#c62828'
                severity = 'Critical'
            elif weeks_inactive >= 4:
                severity_color = '#f57c00'
                severity = 'High'
            else:
                severity_color = '#fbc02d'
                severity = 'Moderate'

            at_risk_rows += f"""
            <tr style="background: rgba(198, 40, 40, 0.05);">
                <td style="text-align: center;">{i}</td>
                <td>{user_id_display}</td>
                <td style="text-align: center; color: {severity_color}; font-weight: bold;">{weeks_inactive}</td>
                <td style="text-align: center;">{last_active}</td>
                <td style="text-align: center;">{weeks_active}</td>
                <td style="text-align: center;">{persistence_pct:.0f}%</td>
            </tr>
            """

        return f"""
    <div class="section">
        <h2>4. Student Engagement Leaderboards</h2>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 20px 0;">
            <div>
                <h3 style="color: #2e7d32;">🏆 Top Engaged Students</h3>
                <p style="color: #666; font-size: 0.9em; margin-bottom: 15px;">
                    Students with highest Consistency engagement scores (based on consistency and activity)
                </p>
                <table>
                    <tr>
                        <th style="text-align: center;">Rank</th>
                        <th>Student ID</th>
                        <th style="text-align: center;">Score</th>
                        <th style="text-align: center;">Weeks Active</th>
                        <th style="text-align: center;">Consistency</th>
                        <th style="text-align: center;">Total Events</th>
                    </tr>
                    {top_engaged_rows if top_engaged_rows else '<tr><td colspan="6" style="text-align: center; color: #666;">No data available</td></tr>'}
                </table>
            </div>

            <div>
                <h3 style="color: #c62828;">⚠️ Students Requiring Attention</h3>
                <p style="color: #666; font-size: 0.9em; margin-bottom: 15px;">
                    Students inactive for 3+ consecutive weeks
                </p>
                <table>
                    <tr>
                        <th style="text-align: center;">#</th>
                        <th>Student ID</th>
                        <th style="text-align: center;">Weeks Inactive</th>
                        <th style="text-align: center;">Last Active</th>
                        <th style="text-align: center;">Total Weeks Active</th>
                        <th style="text-align: center;">Consistency</th>
                    </tr>
                    {at_risk_rows if at_risk_rows else '<tr><td colspan="6" style="text-align: center; color: #666;">No at-risk students</td></tr>'}
                </table>
            </div>
        </div>

        <div style="margin-top: 20px; padding: 15px; background: #e3f2fd; border-left: 4px solid #1565c0; border-radius: 4px;">
            <strong>Note:</strong> Consistency Engagement score combines consistency (70% weight) and total activity (30% weight).
            Higher scores indicate more engaged students. At-risk students are those inactive for 3+ consecutive weeks.
        </div>
    </div>
"""

    def _generate_detailed_metrics_table(self) -> str:
        """Generate detailed weekly metrics table"""
        if len(self.metrics) == 0:
            return ""

        rows = ""
        for _, row in self.metrics.iterrows():
            week = int(row['week_number'])
            wau = int(row['wau_count'])
            wau_pct = row['wau_percentage']
            at_risk = int(row.get('at_risk_count', 0))
            reactivation = row.get('reactivation_rate', 0)
            consistent = row.get('persistent_consistent_pct', 0)

            # Trend indicator
            wow_change = row.get('wau_wow_change_pct', 0)
            if wow_change > 5:
                trend = f"<span class='trend-up'>↑ {wow_change:.0f}%</span>"
            elif wow_change < -5:
                trend = f"<span class='trend-down'>↓ {abs(wow_change):.0f}%</span>"
            else:
                trend = f"<span class='trend-stable'>→</span>"

            rows += f"""
            <tr>
                <td>{week}</td>
                <td>{wau} ({wau_pct:.1f}%)</td>
                <td>{trend}</td>
                <td>{consistent:.0f}%</td>
                <td>{at_risk}</td>
                <td>{reactivation:.0f}%</td>
            </tr>
            """

        return f"""
    <div class="section">
        <h2>7. Detailed Weekly Metrics</h2>
        <table>
            <tr>
                <th>Week</th>
                <th>WAU</th>
                <th>WoW Change</th>
                <th>Consistent %</th>
                <th>At-Risk</th>
                <th>Reactivation</th>
            </tr>
            {rows}
        </table>
    </div>
"""

    def _generate_html_footer(self) -> str:
        """Generate HTML footer"""
        return """
    <div style="text-align: center; color: #666; margin-top: 40px; padding: 20px; border-top: 1px solid #ddd;">
        <p>Generated with Weekly Progress Analyzer</p>
        <p style="font-size: 0.9em;">Report Date: """ + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M') + """</p>
    </div>
</body>
</html>
"""