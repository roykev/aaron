# This file contains the improved _generate_engagement_persistence_section and _generate_feature_usage_section methods
# Copy these to replace the existing methods in weekly_progress_reporter.py
import pandas as pd


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

    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0;">
        <div style="text-align: center; padding: 15px; background: #e8f5e9; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #2e7d32;">{consistent:.0f}%</div>
            <div style="color: #1b5e20; font-weight: 600;">Consistent</div>
            <div style="font-size: 0.85em; color: #666;">Active ≥60% of weeks</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #fff3e0; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #f57c00;">{moderate:.0f}%</div>
            <div style="color: #e65100; font-weight: 600;">Moderate</div>
            <div style="font-size: 0.85em; color: #666;">Active 25-59% of weeks</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #ffebee; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #c62828;">{sporadic:.0f}%</div>
            <div style="color: #b71c1c; font-weight: 600;">Sporadic</div>
            <div style="font-size: 0.85em; color: #666;">Active <25% of weeks</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 8px; border: 2px solid {interp_color};">
            <div style="font-size: 2em; font-weight: bold; color: {interp_color};">{actual_score:.2f}</div>
            <div style="color: #1565c0; font-weight: 600;">Consistency Engagement Score</div>
            <div style="font-size: 0.85em; color: #666;">{interpretation}</div>
            <div style="font-size: 0.8em; color: {'green' if score_delta >= 0 else 'red'}; margin-top: 5px;">
                {'↑' if score_delta > 0 else '↓' if score_delta < 0 else '—'} {score_delta:+.2f} vs expected
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
                                    return `Absolute: ${absScore.toFixed(2)} | Relative: ${relScore >= 0 ? '+' : ''}${relScore.toFixed(2)}`;
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
                            return `Score: ${absScore.toFixed(2)} (${relScore >= 0 ? '+' : ''}${relScore.toFixed(2)} vs expected)`;
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