# Temporary feature usage section implementation - copy the return statement content

def _generate_feature_usage_section(self) -> str:
    """Generate feature usage trends with scoring"""
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

    # Prepare individual feature datasets (semi-transparent)
    datasets = []
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

    for i, feature in enumerate(features):
        col = f'feature_usage_{feature}'
        if col in self.metrics.columns:
            data = self.metrics[col].tolist()
            # Make feature lines semi-transparent
            rgba_color = colors[i].replace('#', '')
            r, g, b = tuple(int(rgba_color[j:j+2], 16) for j in (0, 2, 4))
            datasets.append({
                'label': feature_labels[i],
                'data': data,
                'borderColor': f'rgba({r}, {g}, {b}, 0.3)',  # Semi-transparent
                'backgroundColor': 'transparent',
                'borderWidth': 1,
                'tension': 0.4,
                'fill': False,
                'pointRadius': 0
            })

    # Add Feature Score dataset (prominent)
    datasets.append({
        'label': 'Feature Usage Score',
        'data': feature_scores,
        'borderColor': '#667eea',
        'backgroundColor': 'rgba(102, 126, 234, 0.1)',
        'borderWidth': 4,
        'tension': 0.4,
        'fill': False,
        'yAxisID': 'y1',
        'pointRadius': 3,
        'pointHoverRadius': 5
    })

    # Calculate dynamic max for secondary axis
    valid_scores = [s for s in feature_scores if s is not None]
    if valid_scores:
        max_score = max(valid_scores)
        score_axis_max = max(3, max_score * 1.1)
    else:
        score_axis_max = self.feat_high_weight

    # Convert to JSON
    import json
    datasets_json = json.dumps(datasets)

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

    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0;">
        <div style="text-align: center; padding: 15px; background: #e8f5e9; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #2e7d32;">{high_count_latest}</div>
            <div style="color: #1b5e20; font-weight: 600;">High Usage</div>
            <div style="font-size: 0.85em; color: #666;">>={self.feat_high_threshold}%</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #fff3e0; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #f57c00;">{moderate_count_latest}</div>
            <div style="color: #e65100; font-weight: 600;">Moderate Usage</div>
            <div style="font-size: 0.85em; color: #666;">{self.feat_moderate_threshold}-{self.feat_high_threshold-1}%</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #ffebee; border-radius: 8px;">
            <div style="font-size: 2em; font-weight: bold; color: #c62828;">{low_count_latest}</div>
            <div style="color: #b71c1c; font-weight: 600;">Low Usage</div>
            <div style="font-size: 0.85em; color: #666;"><{self.feat_moderate_threshold}%</div>
        </div>
        <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 8px; border: 2px solid #667eea;">
            <div style="font-size: 2em; font-weight: bold; color: #667eea;">{actual_feature_score:.2f}</div>
            <div style="color: #1565c0; font-weight: 600;">Feature Usage Score</div>
            <div style="font-size: 0.85em; color: #666;">Out of {self.feat_high_weight:.0f}</div>
            <div style="font-size: 0.8em; color: {'green' if score_delta >= 0 else 'red'}; margin-top: 5px;">
                {'↑' if score_delta > 0 else '↓' if score_delta < 0 else '—'} {score_delta:+.2f} vs expected
            </div>
        </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
        <div class="chart-container">
            <canvas id="featureChart"></canvas>
        </div>

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
    </div>

    <script>
    const featureCtx = document.getElementById('featureChart').getContext('2d');
    new Chart(featureCtx, {{
        type: 'line',
        data: {{
            labels: {date_labels},
            datasets: {datasets_json}
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{
                    display: true,
                    text: 'Feature Usage Over Time & Usage Score'
                }},
                legend: {{
                    display: true,
                    position: 'top',
                    labels: {{
                        filter: function(item, chart) {{
                            // Emphasize Feature Usage Score in legend
                            if (item.text === 'Feature Usage Score') {{
                                item.fontStyle = 'bold';
                            }}
                            return true;
                        }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    max: 100,
                    position: 'left',
                    title: {{
                        display: true,
                        text: 'Feature Usage (%)'
                    }}
                }},
                y1: {{
                    beginAtZero: true,
                    max: {score_axis_max:.1f},
                    position: 'right',
                    title: {{
                        display: true,
                        text: 'Feature Usage Score'
                    }},
                    grid: {{
                        drawOnChartArea: false
                    }}
                }}
            }}
        }}
    }});
    </script>
</div>
"""