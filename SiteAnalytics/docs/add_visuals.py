#!/usr/bin/env python3
"""Add visual mockups to both guide files"""

# Additional CSS for visual mockups
additional_css = """
        /* Visual Mockups */
        .visual-mockup {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin: 20px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .mock-exec-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .mock-metric-card {
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            position: relative;
        }

        .mock-metric-card.green-bg { background: #c8e6c9; }
        .mock-metric-card.yellow-bg { background: #fff9c4; }
        .mock-metric-card.red-bg { background: #ffcdd2; }
        .mock-metric-card.blue-bg { background: #e3f2fd; }
        .mock-metric-card.purple-bg { background: #f3e5f5; }
        .mock-metric-card.orange-bg { background: #fff3e0; }

        .mock-value {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .mock-value.green-text { color: #1b5e20; }
        .mock-value.yellow-text { color: #f57f17; }
        .mock-value.red-text { color: #b71c1c; }
        .mock-value.blue-text { color: #667eea; }
        .mock-value.purple-text { color: #764ba2; }
        .mock-value.orange-text { color: #f57c00; }

        .mock-label {
            color: #666;
            font-size: 0.9em;
            font-weight: 600;
            margin: 5px 0;
        }

        .mock-sublabel {
            font-size: 0.75em;
            color: #888;
            margin-top: 3px;
        }

        .mock-detail {
            font-size: 0.8em;
            color: #888;
            margin-top: 8px;
            border-top: 1px solid rgba(0,0,0,0.1);
            padding-top: 8px;
        }

        .mock-delta {
            font-size: 0.75em;
            margin-top: 5px;
        }

        .mock-delta.positive { color: green; }
        .mock-delta.negative { color: red; }

        .mock-chart-container {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            height: 250px;
            position: relative;
        }

        .mock-chart-title {
            font-size: 0.9em;
            font-weight: 600;
            color: #555;
            margin-bottom: 15px;
        }

        .mock-line-chart {
            width: 100%;
            height: 180px;
        }

        .mock-feature-box {
            background: #f3f4f6;
            border-left: 4px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }

        .mock-feature-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 15px;
        }

        .mock-feature-score {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .mock-hml-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .mock-hml-box {
            text-align: center;
            padding: 12px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .mock-hml-value {
            font-size: 1.8em;
            font-weight: bold;
        }

        .mock-hml-value.high-val { color: #2e7d32; }
        .mock-hml-value.mod-val { color: #f57c00; }
        .mock-hml-value.low-val { color: #c62828; }

        .mock-hml-label {
            font-weight: 600;
            font-size: 0.85em;
            margin: 3px 0;
        }

        .mock-hml-threshold {
            font-size: 0.7em;
            color: #666;
        }

        .chart-legend {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 10px;
            flex-wrap: wrap;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.85em;
        }

        .legend-color {
            width: 20px;
            height: 12px;
            border-radius: 2px;
        }

        @media (max-width: 768px) {
            .mock-exec-grid {
                grid-template-columns: 1fr;
            }

            .mock-feature-grid {
                grid-template-columns: 1fr;
            }
        }
"""

# Visual examples HTML for Course report
course_visual_html = """
                    <h3>📊 Visual Example: Executive Summary Boxes</h3>
                    <div class="visual-mockup">
                        <p style="margin-bottom: 20px;"><strong>This is what the Executive Summary looks like in your report:</strong></p>

                        <div class="mock-exec-grid">
                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">45.2%</div>
                                <div class="mock-label">Current Activity Rate</div>
                                <div class="mock-sublabel">% of Active So Far</div>
                                <div class="mock-detail">Total Active So Far: 84</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">62.4%</div>
                                <div class="mock-label">Retention (Coverage)</div>
                                <div class="mock-delta positive">↑ +2.3% vs last week</div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">57.32</div>
                                <div class="mock-label">Consistency Engagement Score</div>
                                <div class="mock-delta positive">↑ +2.15 vs last week</div>
                            </div>

                            <div class="mock-metric-card orange-bg">
                                <div class="mock-value orange-text">3:45:23</div>
                                <div class="mock-label">Time Spent</div>
                                <div class="mock-delta positive">↑ +0:32:18 vs last week</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">64.29</div>
                                <div class="mock-label">Feature Score</div>
                                <div class="mock-delta positive">↑ +3.12 vs last week</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">68.5</div>
                                <div class="mock-label">Student Retention</div>
                                <div class="mock-delta positive">↑ +1.2 vs last week</div>
                            </div>
                        </div>
                    </div>

                    <h3>📈 Visual Example: Active Users Trend Chart</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">Weekly Active Users Over Time</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid lines -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- WAU count area (blue) -->
                                <path d="M 50 140 L 120 130 L 190 120 L 260 110 L 330 125 L 400 115 L 470 105 L 540 100 L 580 95 L 580 160 L 50 160 Z"
                                      fill="rgba(102, 126, 234, 0.2)" stroke="none"/>

                                <!-- WAU count line -->
                                <polyline points="50,140 120,130 190,120 260,110 330,125 400,115 470,105 540,100 580,95"
                                          fill="none" stroke="#667eea" stroke-width="3"/>

                                <!-- % of Active So Far line (purple) -->
                                <polyline points="50,120 120,115 190,110 260,108 330,120 400,112 470,105 540,102 580,100"
                                          fill="none" stroke="#764ba2" stroke-width="2" stroke-dasharray="5,5"/>

                                <!-- Axis -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Labels -->
                                <text x="10" y="45" font-size="10" fill="#666">50</text>
                                <text x="10" y="85" font-size="10" fill="#666">40</text>
                                <text x="10" y="125" font-size="10" fill="#666">30</text>
                                <text x="10" y="165" font-size="10" fill="#666">0</text>

                                <text x="50" y="175" font-size="10" fill="#666">Wk1</text>
                                <text x="190" y="175" font-size="10" fill="#666">Wk3</text>
                                <text x="330" y="175" font-size="10" fill="#666">Wk5</text>
                                <text x="470" y="175" font-size="10" fill="#666">Wk7</text>
                                <text x="550" y="175" font-size="10" fill="#666">Wk9</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>Active Users (count)</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #764ba2;"></div>
                                    <span>% of Active So Far</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <h3>📊 Visual Example: Engagement Stacked Chart</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">Consistency Engagement Over Time</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- Sporadic area (red) -->
                                <path d="M 50 100 L 120 105 L 190 100 L 260 95 L 330 100 L 400 95 L 470 90 L 540 88 L 580 85 L 580 160 L 50 160 Z"
                                      fill="rgba(229, 115, 115, 0.4)"/>

                                <!-- Moderate area (orange) -->
                                <path d="M 50 60 L 120 65 L 190 63 L 260 60 L 330 63 L 400 60 L 470 58 L 540 55 L 580 53 L 580 85 L 540 88 L 470 90 L 400 95 L 330 100 L 260 95 L 190 100 L 120 105 L 50 100 Z"
                                      fill="rgba(255, 183, 77, 0.4)"/>

                                <!-- Consistent area (green) -->
                                <path d="M 50 30 L 120 32 L 190 28 L 260 25 L 330 28 L 400 23 L 470 20 L 540 18 L 580 15 L 580 53 L 540 55 L 470 58 L 400 60 L 330 63 L 260 60 L 190 63 L 120 65 L 50 60 Z"
                                      fill="rgba(129, 199, 132, 0.4)"/>

                                <!-- Engagement score line (purple, right axis 0-100) -->
                                <polyline points="50,90 120,88 190,85 260,82 330,85 400,80 470,75 540,72 580,70"
                                          fill="none" stroke="#667eea" stroke-width="3"/>

                                <!-- Axes -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Y-axis labels (left - percentage) -->
                                <text x="5" y="35" font-size="10" fill="#666">100%</text>
                                <text x="10" y="85" font-size="10" fill="#666">50%</text>
                                <text x="15" y="165" font-size="10" fill="#666">0%</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #81c784;"></div>
                                    <span>Consistent ≥60%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #ffb74d;"></div>
                                    <span>Moderate 25-59%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #e57373;"></div>
                                    <span>Sporadic <25%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>Engagement Score</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <h3>🔧 Visual Example: Feature Usage Info Box</h3>
                    <div class="visual-mockup">
                        <div class="mock-feature-box">
                            <div class="mock-feature-grid">
                                <div>
                                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Semester Usage Score (≥2 weeks)</div>
                                    <div class="mock-feature-score">64.29/100</div>
                                </div>
                                <div class="mock-hml-grid">
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value high-val">3</div>
                                        <div class="mock-hml-label" style="color: #1b5e20;">High</div>
                                        <div class="mock-hml-threshold">≥40%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value mod-val">2</div>
                                        <div class="mock-hml-label" style="color: #e65100;">Moderate</div>
                                        <div class="mock-hml-threshold">20-39%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value low-val">2</div>
                                        <div class="mock-hml-label" style="color: #b71c1c;">Low</div>
                                        <div class="mock-hml-threshold"><20%</div>
                                    </div>
                                </div>
                            </div>

                            <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px;">
                                <div class="mock-feature-grid">
                                    <div>
                                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Usage % (Status)</div>
                                        <div class="mock-feature-score">58.12/100</div>
                                    </div>
                                    <div class="mock-hml-grid">
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value high-val">2</div>
                                            <div class="mock-hml-label" style="color: #1b5e20;">High</div>
                                            <div class="mock-hml-threshold">≥40%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value mod-val">3</div>
                                            <div class="mock-hml-label" style="color: #e65100;">Moderate</div>
                                            <div class="mock-hml-threshold">20-39%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value low-val">2</div>
                                            <div class="mock-hml-label" style="color: #b71c1c;">Low</div>
                                            <div class="mock-hml-threshold"><20%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
"""

# Read course guide
with open('course_dynamics_guide.html', 'r', encoding='utf-8') as f:
    course_content = f.read()

# Insert additional CSS before closing </style>
course_content = course_content.replace('        .lang-content.active {', additional_css + '\n        .lang-content.active {')

# Insert visual examples after the color legend in exec summary
insert_marker = '                    <h3>Metric 1: Current Activity Rate</h3>'
course_content = course_content.replace(insert_marker, course_visual_html + '\n\n' + insert_marker)

# Insert Hebrew visual examples
course_visual_html_he = """
                    <h3>📊 דוגמה ויזואלית: תיבות תקציר מנהלים</h3>
                    <div class="visual-mockup">
                        <p style="margin-bottom: 20px;"><strong>כך נראה תקציר המנהלים בדוח שלך:</strong></p>

                        <div class="mock-exec-grid">
                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">45.2%</div>
                                <div class="mock-label">שיעור פעילות נוכחי</div>
                                <div class="mock-sublabel">% מפעילים עד כה</div>
                                <div class="mock-detail">סה"כ פעילים עד כה: 84</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">62.4%</div>
                                <div class="mock-label">שימור (כיסוי)</div>
                                <div class="mock-delta positive">↑ +2.3% לעומת השבוע שעבר</div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">57.32</div>
                                <div class="mock-label">ציון מעורבות עקביות</div>
                                <div class="mock-delta positive">↑ +2.15 לעומת השבוע שעבר</div>
                            </div>

                            <div class="mock-metric-card orange-bg">
                                <div class="mock-value orange-text">3:45:23</div>
                                <div class="mock-label">זמן שהושקע</div>
                                <div class="mock-delta positive">↑ +0:32:18 לעומת השבוע שעבר</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">64.29</div>
                                <div class="mock-label">ציון פיצ'רים</div>
                                <div class="mock-delta positive">↑ +3.12 לעומת השבוע שעבר</div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">68.5</div>
                                <div class="mock-label">שימור סטודנטים</div>
                                <div class="mock-delta positive">↑ +1.2 לעומת השבוע שעבר</div>
                            </div>
                        </div>
                    </div>

                    <h3>📈 דוגמה ויזואלית: גרף מגמת משתמשים פעילים</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">משתמשים פעילים שבועיים לאורך זמן</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid lines -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- WAU count area (blue) -->
                                <path d="M 50 140 L 120 130 L 190 120 L 260 110 L 330 125 L 400 115 L 470 105 L 540 100 L 580 95 L 580 160 L 50 160 Z"
                                      fill="rgba(102, 126, 234, 0.2)" stroke="none"/>

                                <!-- WAU count line -->
                                <polyline points="50,140 120,130 190,120 260,110 330,125 400,115 470,105 540,100 580,95"
                                          fill="none" stroke="#667eea" stroke-width="3"/>

                                <!-- % of Active So Far line (purple) -->
                                <polyline points="50,120 120,115 190,110 260,108 330,120 400,112 470,105 540,102 580,100"
                                          fill="none" stroke="#764ba2" stroke-width="2" stroke-dasharray="5,5"/>

                                <!-- Axis -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Labels -->
                                <text x="10" y="45" font-size="10" fill="#666">50</text>
                                <text x="10" y="85" font-size="10" fill="#666">40</text>
                                <text x="10" y="125" font-size="10" fill="#666">30</text>
                                <text x="10" y="165" font-size="10" fill="#666">0</text>

                                <text x="50" y="175" font-size="10" fill="#666">ש1</text>
                                <text x="190" y="175" font-size="10" fill="#666">ש3</text>
                                <text x="330" y="175" font-size="10" fill="#666">ש5</text>
                                <text x="470" y="175" font-size="10" fill="#666">ש7</text>
                                <text x="550" y="175" font-size="10" fill="#666">ש9</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>משתמשים פעילים (ספירה)</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #764ba2;"></div>
                                    <span>% מפעילים עד כה</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <h3>📊 דוגמה ויזואלית: גרף מעורבות מוערם</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">מעורבות עקביות לאורך זמן</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- Sporadic area (red) -->
                                <path d="M 50 100 L 120 105 L 190 100 L 260 95 L 330 100 L 400 95 L 470 90 L 540 88 L 580 85 L 580 160 L 50 160 Z"
                                      fill="rgba(229, 115, 115, 0.4)"/>

                                <!-- Moderate area (orange) -->
                                <path d="M 50 60 L 120 65 L 190 63 L 260 60 L 330 63 L 400 60 L 470 58 L 540 55 L 580 53 L 580 85 L 540 88 L 470 90 L 400 95 L 330 100 L 260 95 L 190 100 L 120 105 L 50 100 Z"
                                      fill="rgba(255, 183, 77, 0.4)"/>

                                <!-- Consistent area (green) -->
                                <path d="M 50 30 L 120 32 L 190 28 L 260 25 L 330 28 L 400 23 L 470 20 L 540 18 L 580 15 L 580 53 L 540 55 L 470 58 L 400 60 L 330 63 L 260 60 L 190 63 L 120 65 L 50 60 Z"
                                      fill="rgba(129, 199, 132, 0.4)"/>

                                <!-- Engagement score line (purple, right axis 0-100) -->
                                <polyline points="50,90 120,88 190,85 260,82 330,85 400,80 470,75 540,72 580,70"
                                          fill="none" stroke="#667eea" stroke-width="3"/>

                                <!-- Axes -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Y-axis labels (left - percentage) -->
                                <text x="5" y="35" font-size="10" fill="#666">100%</text>
                                <text x="10" y="85" font-size="10" fill="#666">50%</text>
                                <text x="15" y="165" font-size="10" fill="#666">0%</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #81c784;"></div>
                                    <span>עקבי ≥60%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #ffb74d;"></div>
                                    <span>בינוני 25-59%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #e57373;"></div>
                                    <span>ספורדי <25%</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>ציון מעורבות</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <h3>🔧 דוגמה ויזואלית: תיבת מידע שימוש בפיצ'רים</h3>
                    <div class="visual-mockup">
                        <div class="mock-feature-box">
                            <div class="mock-feature-grid">
                                <div>
                                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">ציון שימוש סמסטריאלי (≥2 שבועות)</div>
                                    <div class="mock-feature-score">64.29/100</div>
                                </div>
                                <div class="mock-hml-grid">
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value high-val">3</div>
                                        <div class="mock-hml-label" style="color: #1b5e20;">גבוה</div>
                                        <div class="mock-hml-threshold">≥40%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value mod-val">2</div>
                                        <div class="mock-hml-label" style="color: #e65100;">בינוני</div>
                                        <div class="mock-hml-threshold">20-39%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value low-val">2</div>
                                        <div class="mock-hml-label" style="color: #b71c1c;">נמוך</div>
                                        <div class="mock-hml-threshold"><20%</div>
                                    </div>
                                </div>
                            </div>

                            <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px;">
                                <div class="mock-feature-grid">
                                    <div>
                                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">אחוז שימוש (סטטוס)</div>
                                        <div class="mock-feature-score">58.12/100</div>
                                    </div>
                                    <div class="mock-hml-grid">
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value high-val">2</div>
                                            <div class="mock-hml-label" style="color: #1b5e20;">גבוה</div>
                                            <div class="mock-hml-threshold">≥40%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value mod-val">3</div>
                                            <div class="mock-hml-label" style="color: #e65100;">בינוני</div>
                                            <div class="mock-hml-threshold">20-39%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value low-val">2</div>
                                            <div class="mock-hml-label" style="color: #b71c1c;">נמוך</div>
                                            <div class="mock-hml-threshold"><20%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
"""

insert_marker_he = '                    <h3>מדד 1: שיעור פעילות נוכחי</h3>'
course_content = course_content.replace(insert_marker_he, course_visual_html_he + '\n\n' + insert_marker_he)

# Write updated course guide
with open('course_dynamics_guide.html', 'w', encoding='utf-8') as f:
    f.write(course_content)

print("✓ Updated course_dynamics_guide.html with visual mockups (English + Hebrew)")

# Now do the same for institute guide
institute_visual_html = """
                    <h3>📊 Visual Example: Executive Summary Boxes (Institute)</h3>
                    <div class="visual-mockup">
                        <p style="margin-bottom: 20px;"><strong>This is what the Executive Summary looks like in your institute report:</strong></p>

                        <div class="mock-exec-grid">
                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">48.5%</div>
                                <div class="mock-label">Current Activity Rate</div>
                                <div class="mock-sublabel">% of Active So Far</div>
                                <div class="mock-detail">Total Active So Far: 312</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> ML (68.2%)</div>
                                    <div><strong>Bottom:</strong> Intro CS (32.4%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">58.7%</div>
                                <div class="mock-label">Retention (Coverage)</div>
                                <div class="mock-delta positive">↑ +2.3% vs last week</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> Data Science (78.5%)</div>
                                    <div><strong>Bottom:</strong> Web Dev (41.2%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">52.18</div>
                                <div class="mock-label">Consistency Engagement Score</div>
                                <div class="mock-delta positive">↑ +1.85 vs last week</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> Advanced Algo (61.3)</div>
                                    <div><strong>Bottom:</strong> Intro CS (38.7)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card orange-bg">
                                <div class="mock-value orange-text">4:12:45</div>
                                <div class="mock-label">Time Spent</div>
                                <div class="mock-delta positive">↑ +0:28:15 vs last week</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> OS (6:45:30)</div>
                                    <div><strong>Bottom:</strong> HTML (1:15:20)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">58.42</div>
                                <div class="mock-label">Feature Score</div>
                                <div class="mock-delta positive">↑ +2.35 vs last week</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> Quiz (72.3%)</div>
                                    <div><strong>Bottom:</strong> Mind Map (18.5%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">64.3</div>
                                <div class="mock-label">Student Retention</div>
                                <div class="mock-delta positive">↑ +0.8 vs last week</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>Top:</strong> Cloud (75.2)</div>
                                    <div><strong>Bottom:</strong> Discrete Math (48.9)</div>
                                </div>
                            </div>
                        </div>

                        <div class="note">
                            <strong>💡 Notice:</strong> Institute boxes show <strong>Top and Bottom performing courses</strong> for each metric, helping you identify which courses need attention.
                        </div>
                    </div>

                    <h3>📈 Visual Example: Stacked Area Chart (By Course)</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">Institute Weekly Active Users: Stacked by Course</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid lines -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- Course 1 (bottom - blue) -->
                                <path d="M 50 160 L 120 155 L 190 150 L 260 148 L 330 152 L 400 147 L 470 145 L 540 143 L 580 140 L 580 160 L 50 160 Z"
                                      fill="rgba(100, 181, 246, 0.6)" stroke="rgba(100, 181, 246, 0.8)" stroke-width="1"/>

                                <!-- Course 2 (green) -->
                                <path d="M 50 125 L 120 122 L 190 118 L 260 115 L 330 120 L 400 115 L 470 112 L 540 110 L 580 108 L 580 140 L 540 143 L 470 145 L 400 147 L 330 152 L 260 148 L 190 150 L 120 155 L 50 160 Z"
                                      fill="rgba(129, 199, 132, 0.6)" stroke="rgba(129, 199, 132, 0.8)" stroke-width="1"/>

                                <!-- Course 3 (orange) -->
                                <path d="M 50 95 L 120 93 L 190 90 L 260 88 L 330 92 L 400 87 L 470 85 L 540 83 L 580 80 L 580 108 L 540 110 L 470 112 L 400 115 L 330 120 L 260 115 L 190 118 L 120 122 L 50 125 Z"
                                      fill="rgba(255, 183, 77, 0.6)" stroke="rgba(255, 183, 77, 0.8)" stroke-width="1"/>

                                <!-- % of Active So Far line (purple, dashed) -->
                                <polyline points="50,110 120,108 190,105 260,103 330,108 400,102 470,98 540,95 580,93"
                                          fill="none" stroke="#667eea" stroke-width="3" stroke-dasharray="5,5"/>

                                <!-- Axis -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Labels -->
                                <text x="5" y="45" font-size="10" fill="#666">120</text>
                                <text x="10" y="85" font-size="10" fill="#666">80</text>
                                <text x="10" y="125" font-size="10" fill="#666">40</text>
                                <text x="15" y="165" font-size="10" fill="#666">0</text>

                                <text x="50" y="175" font-size="10" fill="#666">Wk1</text>
                                <text x="190" y="175" font-size="10" fill="#666">Wk3</text>
                                <text x="330" y="175" font-size="10" fill="#666">Wk5</text>
                                <text x="470" y="175" font-size="10" fill="#666">Wk7</text>
                                <text x="550" y="175" font-size="10" fill="#666">Wk9</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #64b5f6;"></div>
                                    <span>Machine Learning</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #81c784;"></div>
                                    <span>Data Science</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #ffb74d;"></div>
                                    <span>Web Development</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>% of Active So Far</span>
                                </div>
                            </div>
                        </div>

                        <div class="note">
                            <strong>💡 Key Insight:</strong> In stacked charts, you can see which courses contribute the most to institute totals. If one course's area shrinks, it's a course-specific problem. If all shrink proportionally, it's an institute-wide trend.
                        </div>
                    </div>

                    <h3>🔧 Visual Example: Feature Usage Info Box (Institute)</h3>
                    <div class="visual-mockup">
                        <div class="mock-feature-box">
                            <div class="mock-feature-grid">
                                <div>
                                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Semester Usage Score (≥2 weeks)</div>
                                    <div class="mock-feature-score">58.42/100</div>
                                </div>
                                <div class="mock-hml-grid">
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value high-val">2</div>
                                        <div class="mock-hml-label" style="color: #1b5e20;">High</div>
                                        <div class="mock-hml-threshold">≥40%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value mod-val">3</div>
                                        <div class="mock-hml-label" style="color: #e65100;">Moderate</div>
                                        <div class="mock-hml-threshold">20-39%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value low-val">2</div>
                                        <div class="mock-hml-label" style="color: #b71c1c;">Low</div>
                                        <div class="mock-hml-threshold"><20%</div>
                                    </div>
                                </div>
                            </div>

                            <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px;">
                                <div class="mock-feature-grid">
                                    <div>
                                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">Usage % (Status)</div>
                                        <div class="mock-feature-score">52.18/100</div>
                                    </div>
                                    <div class="mock-hml-grid">
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value high-val">2</div>
                                            <div class="mock-hml-label" style="color: #1b5e20;">High</div>
                                            <div class="mock-hml-threshold">≥40%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value mod-val">2</div>
                                            <div class="mock-hml-label" style="color: #e65100;">Moderate</div>
                                            <div class="mock-hml-threshold">20-39%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value low-val">3</div>
                                            <div class="mock-hml-label" style="color: #b71c1c;">Low</div>
                                            <div class="mock-hml-threshold"><20%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <p style="margin-top: 15px; font-size: 0.9em; color: #666;"><em>This shows aggregated feature usage across all courses in the institute.</em></p>
                    </div>
"""

# Read institute guide
with open('institute_dynamics_guide.html', 'r', encoding='utf-8') as f:
    institute_content = f.read()

# Insert additional CSS before closing </style>
institute_content = institute_content.replace('        .lang-content.active {', additional_css + '\n        .lang-content.active {')

# Insert visual examples after the color legend in exec summary
insert_marker_inst = '                    <h3>Metric 1: Current Activity Rate</h3>'
institute_content = institute_content.replace(insert_marker_inst, institute_visual_html + '\n\n' + insert_marker_inst)

# Insert Hebrew visual examples for institute
institute_visual_html_he = """
                    <h3>📊 דוגמה ויזואלית: תיבות תקציר מנהלים (מכון)</h3>
                    <div class="visual-mockup">
                        <p style="margin-bottom: 20px;"><strong>כך נראה תקציר המנהלים בדוח המכון שלך:</strong></p>

                        <div class="mock-exec-grid">
                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">48.5%</div>
                                <div class="mock-label">שיעור פעילות נוכחי</div>
                                <div class="mock-sublabel">% מפעילים עד כה</div>
                                <div class="mock-detail">סה"כ פעילים עד כה: 312</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> למידת מכונה (68.2%)</div>
                                    <div><strong>הכי נמוך:</strong> מבוא למדעי המחשב (32.4%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">58.7%</div>
                                <div class="mock-label">שימור (כיסוי)</div>
                                <div class="mock-delta positive">↑ +2.3% לעומת השבוע שעבר</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> מדעי הנתונים (78.5%)</div>
                                    <div><strong>הכי נמוך:</strong> פיתוח ווב (41.2%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">52.18</div>
                                <div class="mock-label">ציון מעורבות עקביות</div>
                                <div class="mock-delta positive">↑ +1.85 לעומת השבוע שעבר</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> אלגוריתמים מתקדמים (61.3)</div>
                                    <div><strong>הכי נמוך:</strong> מבוא למדעי המחשב (38.7)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card orange-bg">
                                <div class="mock-value orange-text">4:12:45</div>
                                <div class="mock-label">זמן שהושקע</div>
                                <div class="mock-delta positive">↑ +0:28:15 לעומת השבוע שעבר</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> מערכות הפעלה (6:45:30)</div>
                                    <div><strong>הכי נמוך:</strong> HTML (1:15:20)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card yellow-bg">
                                <div class="mock-value yellow-text">58.42</div>
                                <div class="mock-label">ציון פיצ'רים</div>
                                <div class="mock-delta positive">↑ +2.35 לעומת השבוע שעבר</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> בוחן (72.3%)</div>
                                    <div><strong>הכי נמוך:</strong> מפת חשיבה (18.5%)</div>
                                </div>
                            </div>

                            <div class="mock-metric-card green-bg">
                                <div class="mock-value green-text">64.3</div>
                                <div class="mock-label">שימור סטודנטים</div>
                                <div class="mock-delta positive">↑ +0.8 לעומת השבוע שעבר</div>
                                <div style="border-top: 1px solid rgba(0,0,0,0.1); margin-top: 8px; padding-top: 8px; font-size: 0.75em;">
                                    <div><strong>הכי גבוה:</strong> ענן (75.2)</div>
                                    <div><strong>הכי נמוך:</strong> מתמטיקה בדידה (48.9)</div>
                                </div>
                            </div>
                        </div>

                        <div class="note">
                            <strong>💡 שים לב:</strong> תיבות המכון מציגות את <strong>הקורסים הטובים והחלשים ביותר</strong> עבור כל מדד, עוזרות לך לזהות אילו קורסים זקוקים לתשומת לב.
                        </div>
                    </div>

                    <h3>📈 דוגמה ויזואלית: גרף שטח מוערם (לפי קורס)</h3>
                    <div class="visual-mockup">
                        <div class="mock-chart-container">
                            <div class="mock-chart-title">משתמשים פעילים שבועיים במכון: מוערם לפי קורס</div>
                            <svg class="mock-line-chart" viewBox="0 0 600 180">
                                <!-- Grid lines -->
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="120" x2="580" y2="120" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="80" x2="580" y2="80" stroke="#ddd" stroke-width="1"/>
                                <line x1="50" y1="40" x2="580" y2="40" stroke="#ddd" stroke-width="1"/>

                                <!-- Course 1 (bottom - blue) -->
                                <path d="M 50 160 L 120 155 L 190 150 L 260 148 L 330 152 L 400 147 L 470 145 L 540 143 L 580 140 L 580 160 L 50 160 Z"
                                      fill="rgba(100, 181, 246, 0.6)" stroke="rgba(100, 181, 246, 0.8)" stroke-width="1"/>

                                <!-- Course 2 (green) -->
                                <path d="M 50 125 L 120 122 L 190 118 L 260 115 L 330 120 L 400 115 L 470 112 L 540 110 L 580 108 L 580 140 L 540 143 L 470 145 L 400 147 L 330 152 L 260 148 L 190 150 L 120 155 L 50 160 Z"
                                      fill="rgba(129, 199, 132, 0.6)" stroke="rgba(129, 199, 132, 0.8)" stroke-width="1"/>

                                <!-- Course 3 (orange) -->
                                <path d="M 50 95 L 120 93 L 190 90 L 260 88 L 330 92 L 400 87 L 470 85 L 540 83 L 580 80 L 580 108 L 540 110 L 470 112 L 400 115 L 330 120 L 260 115 L 190 118 L 120 122 L 50 125 Z"
                                      fill="rgba(255, 183, 77, 0.6)" stroke="rgba(255, 183, 77, 0.8)" stroke-width="1"/>

                                <!-- % of Active So Far line (purple, dashed) -->
                                <polyline points="50,110 120,108 190,105 260,103 330,108 400,102 470,98 540,95 580,93"
                                          fill="none" stroke="#667eea" stroke-width="3" stroke-dasharray="5,5"/>

                                <!-- Axis -->
                                <line x1="50" y1="0" x2="50" y2="160" stroke="#333" stroke-width="2"/>
                                <line x1="50" y1="160" x2="580" y2="160" stroke="#333" stroke-width="2"/>

                                <!-- Labels -->
                                <text x="5" y="45" font-size="10" fill="#666">120</text>
                                <text x="10" y="85" font-size="10" fill="#666">80</text>
                                <text x="10" y="125" font-size="10" fill="#666">40</text>
                                <text x="15" y="165" font-size="10" fill="#666">0</text>

                                <text x="50" y="175" font-size="10" fill="#666">ש1</text>
                                <text x="190" y="175" font-size="10" fill="#666">ש3</text>
                                <text x="330" y="175" font-size="10" fill="#666">ש5</text>
                                <text x="470" y="175" font-size="10" fill="#666">ש7</text>
                                <text x="550" y="175" font-size="10" fill="#666">ש9</text>
                            </svg>

                            <div class="chart-legend">
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #64b5f6;"></div>
                                    <span>למידת מכונה</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #81c784;"></div>
                                    <span>מדעי הנתונים</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #ffb74d;"></div>
                                    <span>פיתוח ווב</span>
                                </div>
                                <div class="legend-item">
                                    <div class="legend-color" style="background: #667eea;"></div>
                                    <span>% מפעילים עד כה</span>
                                </div>
                            </div>
                        </div>

                        <div class="note">
                            <strong>💡 תובנה מרכזית:</strong> בגרפים מוערמים, אתה יכול לראות אילו קורסים תורמים הכי הרבה לסכומים של המכון. אם השטח של קורס אחד מתכווץ, זו בעיה ספציפית לקורס. אם כולם מתכווצים באופן פרופורציונלי, זו מגמה כלל-מכונית.
                        </div>
                    </div>

                    <h3>🔧 דוגמה ויזואלית: תיבת מידע שימוש בפיצ'רים (מכון)</h3>
                    <div class="visual-mockup">
                        <div class="mock-feature-box">
                            <div class="mock-feature-grid">
                                <div>
                                    <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">ציון שימוש סמסטריאלי (≥2 שבועות)</div>
                                    <div class="mock-feature-score">58.42/100</div>
                                </div>
                                <div class="mock-hml-grid">
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value high-val">2</div>
                                        <div class="mock-hml-label" style="color: #1b5e20;">גבוה</div>
                                        <div class="mock-hml-threshold">≥40%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value mod-val">3</div>
                                        <div class="mock-hml-label" style="color: #e65100;">בינוני</div>
                                        <div class="mock-hml-threshold">20-39%</div>
                                    </div>
                                    <div class="mock-hml-box">
                                        <div class="mock-hml-value low-val">2</div>
                                        <div class="mock-hml-label" style="color: #b71c1c;">נמוך</div>
                                        <div class="mock-hml-threshold"><20%</div>
                                    </div>
                                </div>
                            </div>

                            <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px;">
                                <div class="mock-feature-grid">
                                    <div>
                                        <div style="font-size: 0.9em; color: #666; margin-bottom: 5px;">אחוז שימוש (סטטוס)</div>
                                        <div class="mock-feature-score">52.18/100</div>
                                    </div>
                                    <div class="mock-hml-grid">
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value high-val">2</div>
                                            <div class="mock-hml-label" style="color: #1b5e20;">גבוה</div>
                                            <div class="mock-hml-threshold">≥40%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value mod-val">2</div>
                                            <div class="mock-hml-label" style="color: #e65100;">בינוני</div>
                                            <div class="mock-hml-threshold">20-39%</div>
                                        </div>
                                        <div class="mock-hml-box">
                                            <div class="mock-hml-value low-val">3</div>
                                            <div class="mock-hml-label" style="color: #b71c1c;">נמוך</div>
                                            <div class="mock-hml-threshold"><20%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <p style="margin-top: 15px; font-size: 0.9em; color: #666;"><em>זה מציג שימוש מצטבר בפיצ'רים בכל הקורסים במכון.</em></p>
                    </div>
"""

insert_marker_inst_he = '                    <h3>מדד 1: שיעור פעילות נוכחי</h3>'
institute_content = institute_content.replace(insert_marker_inst_he, institute_visual_html_he + '\n\n' + insert_marker_inst_he)

# Write updated institute guide
with open('institute_dynamics_guide.html', 'w', encoding='utf-8') as f:
    f.write(institute_content)

print("✓ Updated institute_dynamics_guide.html with visual mockups (English + Hebrew)")
print("\n✅ Both guides now include self-contained visual mockups in English and Hebrew!")
print("   - Executive Summary metric boxes")
print("   - Line and stacked area charts")
print("   - Feature usage info boxes")
print("\nOpen the HTML files in a browser and switch languages to see the visual examples!")