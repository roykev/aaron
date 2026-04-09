#!/usr/bin/env python3
"""
Course Reporter Module
Generates HTML and PDF reports from course analysis data
"""

import pandas as pd
import os
from typing import Dict, List, Optional
from datetime import datetime
import json


class CourseReporter:
    """Generates formatted reports (HTML/PDF) from course analysis data"""

    def __init__(self, analysis_data: Dict):
        """
        Initialize the reporter

        Args:
            analysis_data: Dictionary with analysis results
        """
        self.data = analysis_data
        self.metadata = analysis_data.get('metadata', {})

    @staticmethod
    def from_json(json_path: str) -> 'CourseReporter':
        """
        Create reporter from JSON file

        Args:
            json_path: Path to JSON analysis file

        Returns:
            CourseReporter instance
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        return CourseReporter(data)

    def _generate_html_header(self, title: str) -> str:
        """Generate HTML header with styling"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
            margin: 0;
            font-size: 2.5em;
        }}
        .metadata {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .metadata-item {{
            padding: 10px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}
        .metadata-label {{
            font-weight: bold;
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
        }}
        .metadata-value {{
            font-size: 1.5em;
            margin-top: 5px;
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
        .institution-section {{
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 3px 6px rgba(0,0,0,0.12);
            border-left: 6px solid #764ba2;
            border-top: 1px solid #e0e0e0;
        }}
        .institution-section h2 {{
            color: #764ba2;
            border-bottom: 3px solid #764ba2;
            padding-bottom: 12px;
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 2em;
        }}
        .institution-summary {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border: 1px solid #dee2e6;
        }}
        .institution-summary h3 {{
            color: #495057;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 2px solid #adb5bd;
            padding-bottom: 8px;
        }}
        .separator {{
            height: 2px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            margin: 30px 0;
            border-radius: 2px;
        }}
        .courses-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
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
        tr:nth-child(even) {{
            background: #fafafa;
        }}
        tr:nth-child(even):hover {{
            background: #f0f0f0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        .course-card {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 0;
            transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
        }}
        .course-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            border-color: #667eea;
        }}
        .course-card h3 {{
            margin-top: 0;
            color: #667eea;
            font-size: 1.3em;
            padding-bottom: 8px;
            border-bottom: 2px solid #e9ecef;
        }}
        .course-card .course-id {{
            color: #888;
            font-size: 0.85em;
            margin-top: -5px;
            margin-bottom: 15px;
        }}
        .course-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-top: 15px;
            margin-bottom: 15px;
        }}
        .stat-item {{
            text-align: center;
            padding: 12px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 6px;
            border: 1px solid #dee2e6;
        }}
        .stat-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 0.75em;
            color: #666;
            margin-top: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .event-distribution {{
            margin-top: 20px;
            padding-top: 15px;
            border-top: 2px solid #e9ecef;
        }}
        .event-distribution h4 {{
            color: #495057;
            font-size: 1.1em;
            margin-bottom: 15px;
            font-weight: 600;
        }}
        .event-bar {{
            margin-bottom: 10px;
        }}
        .event-bar-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 0.9em;
        }}
        .event-bar-name {{
            font-weight: 600;
            color: #333;
        }}
        .event-bar-percentage {{
            font-weight: bold;
        }}
        .event-bar-bg {{
            background: #e9ecef;
            border-radius: 4px;
            height: 22px;
            overflow: hidden;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
        }}
        .event-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        /* Feature-specific colors */
        .feature-quiz .event-bar-fill {{ background: linear-gradient(90deg, #ff6b6b, #ee5a6f); }}
        .feature-quiz .event-bar-percentage {{ color: #ff6b6b; }}

        .feature-evaluation .event-bar-fill {{ background: linear-gradient(90deg, #f06595, #e64980); }}
        .feature-evaluation .event-bar-percentage {{ color: #f06595; }}

        .feature-mind_map .event-bar-fill {{ background: linear-gradient(90deg, #51cf66, #37b24d); }}
        .feature-mind_map .event-bar-percentage {{ color: #51cf66; }}

        .feature-search .event-bar-fill {{ background: linear-gradient(90deg, #4dabf7, #339af0); }}
        .feature-search .event-bar-percentage {{ color: #4dabf7; }}

        .feature-short_summary .event-bar-fill {{ background: linear-gradient(90deg, #ffd43b, #fcc419); }}
        .feature-short_summary .event-bar-percentage {{ color: #f59f00; }}

        .feature-long_summary .event-bar-fill {{ background: linear-gradient(90deg, #ff922b, #fd7e14); }}
        .feature-long_summary .event-bar-percentage {{ color: #ff922b; }}

        .feature-concepts .event-bar-fill {{ background: linear-gradient(90deg, #845ef7, #7048e8); }}
        .feature-concepts .event-bar-percentage {{ color: #845ef7; }}

        /* Collapsible sections */
        .collapsible-header {{
            cursor: pointer;
            user-select: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 0;
            margin-bottom: 5px;
        }}
        .collapsible-header:hover h4 {{
            color: #667eea;
        }}
        .collapsible-icon {{
            font-size: 1.2em;
            transition: transform 0.3s ease;
            color: #667eea;
            font-weight: bold;
        }}
        .collapsible-icon.expanded {{
            transform: rotate(180deg);
        }}
        .collapsible-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s ease;
        }}
        .collapsible-content.expanded {{
            max-height: 3000px;
        }}
    </style>
    <script>
        function toggleCollapse(id) {{
            const content = document.getElementById(id);
            const icon = document.getElementById(id + '-icon');

            if (content.classList.contains('expanded')) {{
                content.classList.remove('expanded');
                icon.classList.remove('expanded');
            }} else {{
                content.classList.add('expanded');
                icon.classList.add('expanded');
            }}
        }}
    </script>
</head>
<body>
"""

    def _generate_html_footer(self) -> str:
        """Generate HTML footer"""
        return """
    <div class="footer">
        <p>Generated by AaronOwl Analytics</p>
    </div>
</body>
</html>
"""

    def _format_number(self, num) -> str:
        """Format number with commas"""
        if isinstance(num, (int, float)):
            return f"{num:,}"
        return str(num)

    def _format_time_minutes(self, minutes: float) -> str:
        """
        Format time value as h:mm:ss

        Note: Despite the function name, the input is actually in SECONDS (not minutes)
        from the raw data. This formats seconds into h:mm:ss display format.

        Args:
            minutes: Time in SECONDS (historical naming, actually seconds from raw data)

        Returns:
            Formatted string like "1:23:45" or "0:05:30"
        """
        if not minutes or minutes == 0:
            return "0:00:00"

        # Input is actually in seconds, not minutes
        total_seconds = int(minutes)
        hours = total_seconds // 3600
        remaining_seconds = total_seconds % 3600
        mins = remaining_seconds // 60
        secs = remaining_seconds % 60

        return f"{hours}:{mins:02d}:{secs:02d}"

    def _calculate_weeks_in_period(self, from_date: str, to_date: str) -> float:
        """
        Calculate number of weeks between two dates

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format

        Returns:
            Number of weeks (as float) between the dates
        """
        try:
            start = datetime.strptime(from_date, '%Y-%m-%d')
            end = datetime.strptime(to_date, '%Y-%m-%d')
            days = (end - start).days + 1  # +1 to include both start and end date
            return days / 7.0
        except:
            return 1.0  # Default to 1 week if parsing fails

    def _group_courses_by_institution(self, usage_data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group courses by institution, filtering out courses without institution data

        Args:
            usage_data: List of course usage dictionaries

        Returns:
            Dictionary mapping institution names to lists of courses
        """
        import pandas as pd

        grouped = {}
        filtered_count = 0

        for course in usage_data:
            # Try both 'course_institute' (from normalized CSV) and 'course_institution' (legacy)
            institution = course.get('course_institute') or course.get('course_institution')

            # Filter out courses with NaN/None institution (not in courses.csv or missing data)
            if institution is None or (isinstance(institution, float) and pd.isna(institution)):
                filtered_count += 1
                continue  # Skip this course

            institution = str(institution)  # Ensure it's a string

            if institution not in grouped:
                grouped[institution] = []
            grouped[institution].append(course)

        if filtered_count > 0:
            print(f"Filtered out {filtered_count} course(s) without institution data")

        return grouped

    def _get_top_events_for_course(self, course_id: str, limit: int = 5) -> List[Dict]:
        """
        Get top N event types for a specific course

        Args:
            course_id: The course ID to filter by
            limit: Number of top events to return

        Returns:
            List of event dictionaries with event_type, count, and percentage
        """
        distribution_data = self.data.get('event_type_distribution', [])
        course_events = [
            event for event in distribution_data
            if event.get('course_id') == course_id
        ]
        # Sort by count descending and take top N
        course_events.sort(key=lambda x: x.get('count', 0), reverse=True)
        return course_events[:limit]

    def _generate_dual_metric_feature_bars(self, engagement_data: Dict) -> str:
        """
        Generate feature engagement visualization with dual metrics:
        - Horizontal bar for user percentage (primary)
        - Line overlay for average time (secondary)

        Args:
            engagement_data: Dictionary with feature engagement metrics

        Returns:
            HTML string with the dual-metric visualization
        """
        features = [
            ('quiz', 'Quiz'),
            ('evaluation', 'Evaluation'),
            ('mind_map', 'Mind Map'),
            ('search', 'Search'),
            ('short_summary', 'Short Summary'),
            ('long_summary', 'Long Summary'),
            ('concepts', 'Concepts')
        ]

        # Find max time for scaling the line chart
        max_time = 0
        for feature_key, _ in features:
            time_val = engagement_data.get(f'avg_time_{feature_key}_minutes', 0)
            if time_val > max_time:
                max_time = time_val

        # Avoid division by zero
        if max_time == 0:
            max_time = 1

        html = ""
        for feature_key, feature_label in features:
            users = engagement_data.get(f'users_{feature_key}', 0)
            percentage = engagement_data.get(f'users_{feature_key}_pct', 0)
            avg_time = engagement_data.get(f'avg_time_{feature_key}_minutes', 0)

            # Calculate position for time marker (scaled to 0-100% of bar width)
            time_position = (avg_time / max_time) * 100 if max_time > 0 else 0

            html += f"""
            <div class="event-bar feature-{feature_key}" style="position: relative; margin-bottom: 18px;">
                <div class="event-bar-label">
                    <span class="event-bar-name">{feature_label}</span>
                    <span class="event-bar-percentage">{percentage}% users • {self._format_time_minutes(avg_time)} avg</span>
                </div>
                <div class="event-bar-bg" style="position: relative;">
                    <div class="event-bar-fill" style="width: {percentage}%;"></div>
                    <div style="position: absolute; left: {time_position}%; top: 50%; transform: translate(-50%, -50%);
                                width: 12px; height: 12px; background: white; border: 3px solid #333;
                                border-radius: 50%; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></div>
                </div>
                <div style="font-size: 0.75em; color: #666; margin-top: 3px; display: flex; justify-content: space-between;">
                    <span>👥 {percentage}% adoption</span>
                    <span>⏱️ {self._format_time_minutes(avg_time)} time</span>
                </div>
            </div>
"""

        return html

    def _calculate_institution_feature_engagement(self, courses: List[Dict]) -> Dict:
        """
        Calculate aggregate feature engagement for an institution

        Args:
            courses: List of course dictionaries for the institution

        Returns:
            Dictionary with feature engagement metrics including time spent
        """
        import numpy as np

        # Aggregate unique users across all courses
        total_users = sum(course.get('total_users', 0) for course in courses)

        if total_users == 0:
            return {
                'users_quiz': 0, 'users_quiz_pct': 0.0, 'avg_time_quiz_minutes': 0,
                'users_evaluation': 0, 'users_evaluation_pct': 0.0, 'avg_time_evaluation_minutes': 0,
                'users_mind_map': 0, 'users_mind_map_pct': 0.0, 'avg_time_mind_map_minutes': 0,
                'users_search': 0, 'users_search_pct': 0.0, 'avg_time_search_minutes': 0,
                'users_short_summary': 0, 'users_short_summary_pct': 0.0, 'avg_time_short_summary_minutes': 0,
                'users_long_summary': 0, 'users_long_summary_pct': 0.0, 'avg_time_long_summary_minutes': 0,
                'users_concepts': 0, 'users_concepts_pct': 0.0, 'avg_time_concepts_minutes': 0,
            }

        features = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
        engagement = {}

        for feature in features:
            # Sum users across all courses for this feature
            total_feature_users = sum(course.get(f'users_{feature}', 0) for course in courses)
            percentage = round((total_feature_users / total_users) * 100, 2)

            # Calculate average time across courses (weighted by users who actually used the feature)
            time_values = []
            for course in courses:
                avg_time = course.get(f'avg_time_{feature}_minutes', 0)
                if avg_time > 0:
                    time_values.append(avg_time)

            avg_time = round(np.mean(time_values), 2) if time_values else 0

            engagement[f'users_{feature}'] = total_feature_users
            engagement[f'users_{feature}_pct'] = percentage
            engagement[f'avg_time_{feature}_minutes'] = avg_time

        return engagement

    def _calculate_institution_aggregate_metrics(self, courses: List[Dict], to_date: str = None) -> Dict:
        """
        Calculate aggregate time and session metrics for an institution

        Args:
            courses: List of course dictionaries for the institution
            to_date: End date for calculating weeks (optional)

        Returns:
            Dictionary with aggregate metrics including average weeks based on course start dates
        """
        import numpy as np
        from datetime import datetime

        # Collect all time and session values across courses
        avg_time_values = []
        median_time_values = []
        avg_session_values = []
        median_session_values = []

        for course in courses:
            if course.get('avg_time_per_user_minutes', 0) > 0:
                avg_time_values.append(course['avg_time_per_user_minutes'])
            if course.get('median_time_per_user_minutes', 0) > 0:
                median_time_values.append(course['median_time_per_user_minutes'])
            if course.get('avg_session_length_minutes', 0) > 0:
                avg_session_values.append(course['avg_session_length_minutes'])
            if course.get('median_session_length_minutes', 0) > 0:
                median_session_values.append(course['median_session_length_minutes'])

        # Calculate total registered students
        total_registered = sum(
            course.get('course_registered', course.get('registered', 0)) or 0
            for course in courses
        )

        # Calculate average weeks based on each course's actual activity period
        avg_weeks = 0
        if to_date:
            weeks_list = []
            try:
                end_date = datetime.strptime(to_date, '%Y-%m-%d')
                for course in courses:
                    # Get first_activity from course data
                    first_activity = course.get('first_activity')
                    if first_activity:
                        # Parse first_activity - could be datetime string or timestamp
                        try:
                            if isinstance(first_activity, str):
                                start_date = datetime.fromisoformat(first_activity.replace('Z', '+00:00'))
                            else:
                                start_date = datetime.fromtimestamp(first_activity)

                            days = (end_date - start_date).days + 1
                            weeks = max(days / 7.0, 0.14)  # Minimum 1 day = 0.14 weeks
                            weeks_list.append(weeks)
                        except:
                            pass

                if weeks_list:
                    avg_weeks = round(np.mean(weeks_list), 2)
            except:
                pass

        return {
            'total_users': sum(course.get('total_users', 0) for course in courses),
            'total_registered': total_registered,
            'avg_time_per_user_minutes': round(np.mean(avg_time_values), 2) if avg_time_values else 0,
            'median_time_per_user_minutes': round(np.mean(median_time_values), 2) if median_time_values else 0,
            'avg_session_length_minutes': round(np.mean(avg_session_values), 2) if avg_session_values else 0,
            'median_session_length_minutes': round(np.mean(median_session_values), 2) if median_session_values else 0,
            'avg_weeks': avg_weeks,
        }

    def generate_html_report(self, output_path: str, split_by_institution = False, report_type: str = 'semester') -> str:
        """
        Generate comprehensive HTML report

        Args:
            output_path: Path to save HTML file
            split_by_institution: Report generation mode
                - False: unified report only (default)
                - True: split reports only (one per institution)
                - "both": generate both unified and split reports
            report_type: Type of report - 'semester' or 'weekly'

        Returns:
            Path to generated HTML file (or base path if split)
        """
        from_date = self.metadata.get('from_date', 'N/A')
        to_date = self.metadata.get('to_date', 'N/A')
        usage_data = self.data.get('course_usage_summary', [])

        if not usage_data:
            print("No course data available for report")
            return output_path

        # Group courses by institution
        institutions = self._group_courses_by_institution(usage_data)

        # Handle "both" option
        if split_by_institution == "both":
            # Generate unified report
            html = self._generate_unified_report(institutions, from_date, to_date, report_type)
            with open(output_path, 'w') as f:
                f.write(html)
            print(f"Unified HTML report generated: {output_path}")

            # Generate separate reports for each institution
            base_path = output_path.replace('.html', '')
            for institution, courses in institutions.items():
                safe_name = institution.replace(' ', '_').replace('/', '_')
                inst_path = f"{base_path}_{safe_name}.html"

                html = self._generate_institution_report(institution, courses, from_date, to_date, report_type)
                with open(inst_path, 'w') as f:
                    f.write(html)
                print(f"Split HTML report generated for {institution}: {inst_path}")

            return output_path

        elif split_by_institution:
            # Generate separate report for each institution only
            base_path = output_path.replace('.html', '')
            generated_files = []

            for institution, courses in institutions.items():
                # Create safe filename from institution name
                safe_name = institution.replace(' ', '_').replace('/', '_')
                inst_path = f"{base_path}_{safe_name}.html"

                html = self._generate_institution_report(institution, courses, from_date, to_date, report_type)

                with open(inst_path, 'w') as f:
                    f.write(html)
                generated_files.append(inst_path)
                print(f"HTML report generated for {institution}: {inst_path}")

            return base_path
        else:
            # Generate unified report only
            html = self._generate_unified_report(institutions, from_date, to_date, report_type)

            with open(output_path, 'w') as f:
                f.write(html)

            print(f"HTML report generated: {output_path}")
            return output_path

    def _generate_course_card_html(self, course: Dict, card_index: int = 0) -> str:
        """Generate HTML for a single course card"""
        course_name = course.get('course_name', course.get('course_id', 'Unknown'))
        course_id = course.get('course_id', 'N/A')

        # Get registered student count and calculate percentage
        registered = course.get('course_registered', course.get('registered', 0))
        total_users = course.get('total_users', 0)

        # Calculate percentage of registered students who are active
        if registered and registered > 0:
            usage_pct = round((total_users / registered) * 100, 1)
            user_display = f"{self._format_number(total_users)} ({usage_pct}%)"
        else:
            user_display = self._format_number(total_users)

        # Get top 5 events for this course
        top_events = self._get_top_events_for_course(course_id, limit=5)

        # Generate unique IDs for collapsible sections
        fe_id = f"feature-engagement-{card_index}"
        events_id = f"top-events-{card_index}"

        html = f"""
        <div class="course-card">
            <h3>{course_name}</h3>
            <p class="course-id">Course ID: {course_id}</p>

            <!-- User Stats -->
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
                <div class="stat-item">
                    <div class="stat-value">{user_display}</div>
                    <div class="stat-label">Active Users{' / Registered' if registered else ''}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_number(int(registered)) if registered else 'N/A'}</div>
                    <div class="stat-label">Registered</div>
                </div>
            </div>

            <!-- Time / User / Semester -->
            <h4 style="font-size: 0.85em; color: #888; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Time / User / Semester</h4>
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(course.get('avg_time_per_user_minutes', 0))}</div>
                    <div class="stat-label">Average</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(course.get('median_time_per_user_minutes', 0))}</div>
                    <div class="stat-label">Median</div>
                </div>
            </div>

            <!-- Session Length -->
            <h4 style="font-size: 0.85em; color: #888; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Session Length</h4>
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr);">
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(course.get('avg_session_length_minutes', 0))}</div>
                    <div class="stat-label">Average</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(course.get('median_session_length_minutes', 0))}</div>
                    <div class="stat-label">Median</div>
                </div>
            </div>
"""

        # Add feature engagement section with collapse using dual-metric visualization
        html += f"""
            <div class="event-distribution">
                <div class="collapsible-header" onclick="toggleCollapse('{fe_id}')">
                    <h4 style="margin: 0;">Feature Engagement</h4>
                    <span class="collapsible-icon" id="{fe_id}-icon">▼</span>
                </div>
                <div class="collapsible-content" id="{fe_id}">
{self._generate_dual_metric_feature_bars(course)}
                </div>
            </div>
"""

        # Add top 5 event types distribution with collapse
        if top_events:
            html += f"""
            <div class="event-distribution">
                <div class="collapsible-header" onclick="toggleCollapse('{events_id}')">
                    <h4 style="margin: 0;">Top 5 Event Types</h4>
                    <span class="collapsible-icon" id="{events_id}-icon">▼</span>
                </div>
                <div class="collapsible-content" id="{events_id}">
"""
            for event in top_events:
                event_type = event.get('event_type', 'Unknown')
                percentage = event.get('percentage', 0)
                count = event.get('count', 0)

                html += f"""
                    <div class="event-bar">
                        <div class="event-bar-label">
                            <span class="event-bar-name">{event_type}</span>
                            <span class="event-bar-percentage" style="color: #667eea;">{percentage}% ({self._format_number(count)})</span>
                        </div>
                        <div class="event-bar-bg">
                            <div class="event-bar-fill" style="width: {percentage}%; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);"></div>
                        </div>
                    </div>
"""
            html += """
                </div>
            </div>
"""

        html += """
        </div>
"""
        return html

    def _generate_unified_report(self, institutions: Dict[str, List[Dict]], from_date: str, to_date: str, report_type: str = 'semester') -> str:
        """Generate unified report with all institutions"""

        # Determine title and header color based on report type
        if report_type == 'weekly':
            title = "Weekly Report"
            header_bg = "linear-gradient(135deg, #51cf66 0%, #37b24d 100%)"  # Green
        else:  # semester
            title = "Semester Report"
            header_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"  # Purple

        html = self._generate_html_header(f"{title}: {from_date} to {to_date}")

        # Header with dynamic background
        html += f"""
    <div class="header" style="background: {header_bg};">
        <h1>{title}</h1>
        <p style="font-size: 1.2em; margin: 10px 0 0 0;">
            Period: {from_date} to {to_date}
        </p>
    </div>
"""

        # Metadata section
        total_courses = sum(len(courses) for courses in institutions.values())
        html += f"""
    <div class="metadata">
        <h2 style="margin-top: 0;">Overview</h2>
        <div class="metadata-grid">
            <div class="metadata-item">
                <div class="metadata-label">Total Institutions</div>
                <div class="metadata-value">{len(institutions)}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Total Courses</div>
                <div class="metadata-value">{total_courses}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Report Generated</div>
                <div class="metadata-value" style="font-size: 1em;">
                    {datetime.fromisoformat(self.metadata.get('generated_at', datetime.now().isoformat())).strftime('%Y-%m-%d %H:%M')}
                </div>
            </div>
        </div>
    </div>
"""

        # Calculate overall metrics across all institutions
        all_courses = []
        for courses in institutions.values():
            all_courses.extend(courses)

        overall_metrics = self._calculate_institution_aggregate_metrics(all_courses)
        overall_engagement = self._calculate_institution_feature_engagement(all_courses)

        # Calculate number of weeks and weekly averages
        num_weeks = self._calculate_weeks_in_period(from_date, to_date)
        weekly_avg_users = overall_metrics['total_users'] / num_weeks if num_weeks > 0 else 0
        weekly_avg_time = overall_metrics['avg_time_per_user_minutes'] / num_weeks if num_weeks > 0 else 0
        weekly_median_time = overall_metrics['median_time_per_user_minutes'] / num_weeks if num_weeks > 0 else 0

        # Calculate overall usage percentage
        total_registered = overall_metrics.get('total_registered', 0)
        if total_registered and total_registered > 0:
            overall_usage_pct = round((overall_metrics['total_users'] / total_registered) * 100, 1)
            users_display = f"{self._format_number(overall_metrics['total_users'])} ({overall_usage_pct}%)"
        else:
            users_display = self._format_number(overall_metrics['total_users'])

        # Add Total Metrics Section
        html += f"""
    <div class="section">
        <h2>Overall Metrics</h2>
        <p style="color: #666; margin-top: -5px; margin-bottom: 15px;">Period: {from_date} to {to_date} ({num_weeks:.1f} weeks)</p>

        <!-- User Stats -->
        <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-top: 20px; margin-bottom: 10px;">
            <div class="stat-item">
                <div class="stat-value">{users_display}</div>
                <div class="stat-label">Active Users{' / Registered' if total_registered else ''}</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{self._format_number(int(total_registered)) if total_registered else 'N/A'}</div>
                <div class="stat-label">Registered</div>
            </div>
        </div>

        <!-- Time / User / Semester -->
        <h4 style="font-size: 0.85em; color: #888; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Time / User / Semester</h4>
        <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(overall_metrics['avg_time_per_user_minutes'])}</div>
                <div class="stat-label">Average</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(overall_metrics['median_time_per_user_minutes'])}</div>
                <div class="stat-label">Median</div>
            </div>
        </div>

        <!-- Time / User / Week -->
        <h4 style="font-size: 0.85em; color: #888; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Time / User / Week</h4>
        <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(weekly_avg_time)}</div>
                <div class="stat-label">Average</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(weekly_median_time)}</div>
                <div class="stat-label">Median</div>
            </div>
        </div>

        <!-- Session Length -->
        <h4 style="font-size: 0.85em; color: #888; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Session Length</h4>
        <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 25px;">
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(overall_metrics['avg_session_length_minutes'])}</div>
                <div class="stat-label">Average</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{self._format_time_minutes(overall_metrics['median_session_length_minutes'])}</div>
                <div class="stat-label">Median</div>
            </div>
        </div>

        <h3 style="color: #495057; margin-top: 25px; margin-bottom: 15px; font-size: 1.2em; border-bottom: 2px solid #e9ecef; padding-bottom: 8px;">Overall Feature Engagement</h3>
        <div class="event-distribution" style="border-top: none; padding-top: 0;">
{self._generate_dual_metric_feature_bars(overall_engagement)}
        </div>
    </div>
"""

        # Add Institution Comparison Section
        html += """
    <div class="section">
        <h2>Institution Comparison</h2>
        <table style="margin-top: 20px; font-size: 0.85em;">
            <thead>
                <tr>
                    <th>Institution</th>
                    <th style="text-align: right;">Users</th>
                    <th style="text-align: right;">% Active</th>
                    <th style="text-align: right;">Users/Week</th>
                    <th style="text-align: right;">Courses</th>
                    <th style="text-align: right;">Avg Time/User</th>
                    <th style="text-align: right;">Median Time/User</th>
                    <th style="text-align: right;">Avg Time/Week</th>
                    <th style="text-align: right;">Median Time/Week</th>
                    <th style="text-align: right;">Avg Session</th>
                    <th style="text-align: right;">Median Session</th>
                    <th style="text-align: right;">Quiz %</th>
                    <th style="text-align: right;">Eval %</th>
                    <th style="text-align: right;">Mind Map %</th>
                </tr>
            </thead>
            <tbody>
"""

        for institution, courses in sorted(institutions.items()):
            inst_metrics = self._calculate_institution_aggregate_metrics(courses, to_date)
            inst_engagement = self._calculate_institution_feature_engagement(courses)

            # Use course-based average weeks (based on each course's start date)
            inst_avg_weeks = inst_metrics.get('avg_weeks', num_weeks)
            if inst_avg_weeks == 0:
                inst_avg_weeks = num_weeks  # Fallback to global if calculation failed

            # Calculate weekly averages for this institution using course-based weeks
            inst_weekly_users = inst_metrics['total_users'] / inst_avg_weeks if inst_avg_weeks > 0 else 0
            inst_weekly_avg_time = inst_metrics['avg_time_per_user_minutes'] / inst_avg_weeks if inst_avg_weeks > 0 else 0
            inst_weekly_median_time = inst_metrics['median_time_per_user_minutes'] / inst_avg_weeks if inst_avg_weeks > 0 else 0

            # Calculate percentage of active users from registered
            inst_registered = inst_metrics.get('total_registered', 0)
            if inst_registered and inst_registered > 0:
                active_pct = round((inst_metrics['total_users'] / inst_registered) * 100, 1)
                active_pct_display = f"{active_pct}%"
            else:
                active_pct_display = "N/A"

            html += f"""
                <tr>
                    <td style="font-weight: 600;">{institution}</td>
                    <td style="text-align: right;">{self._format_number(inst_metrics['total_users'])}</td>
                    <td style="text-align: right;">{active_pct_display}</td>
                    <td style="text-align: right;">{self._format_number(int(inst_weekly_users))}</td>
                    <td style="text-align: right;">{len(courses)}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_metrics['avg_time_per_user_minutes'])}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_metrics['median_time_per_user_minutes'])}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_weekly_avg_time)}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_weekly_median_time)}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_metrics['avg_session_length_minutes'])}</td>
                    <td style="text-align: right;">{self._format_time_minutes(inst_metrics['median_session_length_minutes'])}</td>
                    <td style="text-align: right;">{inst_engagement.get('users_quiz_pct', 0)}%</td>
                    <td style="text-align: right;">{inst_engagement.get('users_evaluation_pct', 0)}%</td>
                    <td style="text-align: right;">{inst_engagement.get('users_mind_map_pct', 0)}%</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
    </div>
"""

        # Generate sections for each institution
        card_counter = 0  # Global card counter for unique IDs
        for institution, courses in sorted(institutions.items()):
            # Calculate institution-level metrics
            inst_engagement = self._calculate_institution_feature_engagement(courses)
            inst_metrics = self._calculate_institution_aggregate_metrics(courses, to_date)
            total_events = sum(course.get('total_events', 0) for course in courses)

            html += f"""
    <div class="institution-section">
        <h2>{institution}</h2>
        <p style="color: #666; margin-top: -5px; margin-bottom: 20px;">{len(courses)} course(s) • {self._format_number(inst_metrics['total_users'])} users • {self._format_number(total_events)} events</p>

        <div class="institution-summary">
            <h3>Institution-Level Metrics</h3>

            <!-- User Stats -->
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
                <div class="stat-item">
                    <div class="stat-value">{self._format_number(inst_metrics['total_users'])}{' (' + str(round((inst_metrics['total_users'] / inst_metrics['total_registered']) * 100, 1)) + '%)' if inst_metrics.get('total_registered', 0) > 0 else ''}</div>
                    <div class="stat-label">Active Users{' / Registered' if inst_metrics.get('total_registered', 0) > 0 else ''}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_number(inst_metrics.get('total_registered', 0)) if inst_metrics.get('total_registered', 0) > 0 else 'N/A'}</div>
                    <div class="stat-label">Registered</div>
                </div>
            </div>

            <!-- Time / User / Semester -->
            <h4 style="font-size: 0.85em; color: #666; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Time / User / Semester</h4>
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['avg_time_per_user_minutes'])}</div>
                    <div class="stat-label">Average</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['median_time_per_user_minutes'])}</div>
                    <div class="stat-label">Median</div>
                </div>
            </div>

            <!-- Time / User / Week -->
            <h4 style="font-size: 0.85em; color: #666; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Time / User / Week</h4>
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 10px;">
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['avg_time_per_user_minutes'] / inst_metrics.get('avg_weeks', 1) if inst_metrics.get('avg_weeks', 0) > 0 else 0)}</div>
                    <div class="stat-label">Average</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['median_time_per_user_minutes'] / inst_metrics.get('avg_weeks', 1) if inst_metrics.get('avg_weeks', 0) > 0 else 0)}</div>
                    <div class="stat-label">Median</div>
                </div>
            </div>

            <!-- Session Length -->
            <h4 style="font-size: 0.85em; color: #666; margin: 15px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Session Length</h4>
            <div class="course-stats" style="grid-template-columns: repeat(2, 1fr);">
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['avg_session_length_minutes'])}</div>
                    <div class="stat-label">Average</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{self._format_time_minutes(inst_metrics['median_session_length_minutes'])}</div>
                    <div class="stat-label">Median</div>
                </div>
            </div>

            <h4 style="color: #495057; margin-top: 20px; margin-bottom: 10px; font-size: 1.1em; border-bottom: 1px solid #adb5bd; padding-bottom: 5px;">Feature Engagement</h4>
            <div class="event-distribution" style="margin-top: 10px; padding-top: 0; border-top: none;">
{self._generate_dual_metric_feature_bars(inst_engagement)}
            </div>
        </div>

        <div class="separator"></div>

        <h3 style="color: #495057; margin-bottom: 15px;">Courses</h3>
        <div class="courses-grid">
"""
            for course in courses:
                html += self._generate_course_card_html(course, card_index=card_counter)
                card_counter += 1

            html += """
        </div>
    </div>
"""

        html += self._generate_html_footer()
        return html

    def _generate_institution_report(self, institution: str, courses: List[Dict], from_date: str, to_date: str, report_type: str = 'semester') -> str:
        """Generate report for a single institution"""

        # Determine title and header color based on report type
        if report_type == 'weekly':
            title = "Weekly Report"
            header_bg = "linear-gradient(135deg, #51cf66 0%, #37b24d 100%)"  # Green
        else:  # semester
            title = "Semester Report"
            header_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"  # Purple

        html = self._generate_html_header(f"{institution} - {title}: {from_date} to {to_date}")

        # Header with dynamic background
        html += f"""
    <div class="header" style="background: {header_bg};">
        <h1>{institution}</h1>
        <h2 style="margin: 10px 0 0 0; font-size: 1.5em;">{title}</h2>
        <p style="font-size: 1.2em; margin: 10px 0 0 0;">
            Period: {from_date} to {to_date}
        </p>
    </div>
"""

        # Metadata section for this institution
        total_events = sum(course.get('total_events', 0) for course in courses)
        total_users = sum(course.get('total_users', 0) for course in courses)

        html += f"""
    <div class="metadata">
        <h2 style="margin-top: 0;">Overview</h2>
        <div class="metadata-grid">
            <div class="metadata-item">
                <div class="metadata-label">Total Events</div>
                <div class="metadata-value">{self._format_number(total_events)}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Total Courses</div>
                <div class="metadata-value">{len(courses)}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Total Users</div>
                <div class="metadata-value">{self._format_number(total_users)}</div>
            </div>
            <div class="metadata-item">
                <div class="metadata-label">Report Generated</div>
                <div class="metadata-value" style="font-size: 1em;">
                    {datetime.fromisoformat(self.metadata.get('generated_at', datetime.now().isoformat())).strftime('%Y-%m-%d %H:%M')}
                </div>
            </div>
        </div>
    </div>
"""

        # Course cards
        html += """
    <div class="section">
        <h2>Courses</h2>
"""
        for course in courses:
            html += self._generate_course_card_html(course)

        html += """
    </div>
"""

        html += self._generate_html_footer()
        return html

    def generate_pdf_report(self, output_path: str) -> str:
        """
        Generate PDF report from HTML

        Args:
            output_path: Path to save PDF file

        Returns:
            Path to generated PDF file
        """
        # First generate HTML
        html_path = output_path.replace('.pdf', '.html')
        self.generate_html_report(html_path)

        # Try to convert to PDF using weasyprint
        try:
            from weasyprint import HTML
            HTML(html_path).write_pdf(output_path)
            print(f"PDF report generated: {output_path}")
            return output_path
        except ImportError:
            print("weasyprint not installed. Install with: pip install weasyprint")
            print(f"HTML report available at: {html_path}")
            return html_path

    def print_console_summary(self):
        """Print a formatted summary to console"""
        print("\n" + "=" * 80)
        print("COURSE ANALYTICS SUMMARY")
        print("=" * 80)

        # Metadata
        print(f"\nPeriod: {self.metadata.get('from_date', 'N/A')} to {self.metadata.get('to_date', 'N/A')}")
        print(f"Total Events: {self._format_number(self.metadata.get('total_events', 0))}")
        print(f"Total Courses: {self._format_number(self.metadata.get('total_courses', 0))}")

        # Course usage
        usage_data = self.data.get('course_usage_summary', [])
        if usage_data:
            print("\n" + "-" * 80)
            print("COURSE USAGE BREAKDOWN")
            print("-" * 80)

            for course in usage_data:
                course_name = course.get('course_name', course.get('course_id', 'Unknown'))
                print(f"\nCourse: {course_name}")
                print(f"  ID: {course.get('course_id', 'N/A')}")
                print(f"  Users: {self._format_number(course.get('total_users', 0))}")
                print(f"  Events: {self._format_number(course.get('total_events', 0))}")
                print(f"  Events/User: {course.get('events_per_user', 0)}")
                print(f"  Days Active: {course.get('date_span_days', 0)}")

        print("\n" + "=" * 80)


def main():
    """Example usage of the reporter"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate course analytics reports')
    parser.add_argument('json_file', help='Path to JSON analysis file')
    parser.add_argument('--format', choices=['html', 'pdf', 'both'], default='html',
                        help='Report format (default: html)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--split-by-institution', action='store_true',
                        help='Generate separate reports per institution (default: unified report)')

    args = parser.parse_args()

    # Load data
    reporter = CourseReporter.from_json(args.json_file)

    # Print console summary
    reporter.print_console_summary()

    # Generate report
    base_path = args.output or args.json_file.replace('.json', '')

    if args.format in ['html', 'both']:
        reporter.generate_html_report(f"{base_path}.html", split_by_institution=args.split_by_institution)

    if args.format in ['pdf', 'both']:
        reporter.generate_pdf_report(f"{base_path}.pdf")


if __name__ == '__main__':
    main()