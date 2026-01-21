#!/usr/bin/env python3
"""
Course Analysis Module
Contains logic for analyzing Mixpanel course usage data
Exports results to CSV or JSON
"""

import pandas as pd
import numpy as np
import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class CourseAnalysis:
    """Analyzes Mixpanel event data and generates course usage metrics"""

    def __init__(self, export_df: pd.DataFrame, course_info_df: Optional[pd.DataFrame] = None):
        """
        Initialize the course analyzer

        Args:
            export_df: DataFrame from Mixpanel export
            course_info_df: Optional DataFrame with course metadata
        """
        self.df = export_df.copy()
        self.course_info = course_info_df

        # Ensure datetime column exists and is properly converted
        if 'datetime' not in self.df.columns:
            if 'time' in self.df.columns:
                self.df['datetime'] = pd.to_datetime(self.df['time'], unit='s')
            else:
                raise ValueError("No datetime or time column found in data")
        else:
            # Convert datetime column to datetime type if it's not already
            if not pd.api.types.is_datetime64_any_dtype(self.df['datetime']):
                self.df['datetime'] = pd.to_datetime(self.df['datetime'])

        # Identify key columns
        self.course_col = self._identify_column(['course', 'course_id', 'courseId', 'Course'])
        self.user_col = self._identify_column(['distinct_id', 'user_id', 'User ID', 'userId'])
        self.event_col = self._identify_column(['event', 'Event Name', 'event_name', 'EventName'])

        print(f"Initialized with {len(self.df)} events")
        if self.course_col:
            print(f"Found {self.df[self.course_col].nunique()} unique courses")

    def _identify_column(self, possible_names: List[str]) -> Optional[str]:
        """Find which column name exists in the dataframe"""
        for name in possible_names:
            if name in self.df.columns:
                return name
        return None

    def get_course_usage_summary(self) -> pd.DataFrame:
        """
        Generate comprehensive usage summary per course

        Returns:
            DataFrame with course usage metrics
        """
        if not self.course_col:
            print("Warning: No course column found")
            return pd.DataFrame()

        reports = []

        for course_id in self.df[self.course_col].dropna().unique():
            course_data = self.df[self.df[self.course_col] == course_id]

            report = {
                'course_id': course_id,
                'total_events': len(course_data),
                'first_activity': course_data['datetime'].min(),
                'last_activity': course_data['datetime'].max(),
                'date_span_days': (course_data['datetime'].max() - course_data['datetime'].min()).days,
            }

            # User metrics with time analysis
            if self.user_col:
                report['total_users'] = course_data[self.user_col].nunique()
                if report['total_users'] > 0:
                    report['events_per_user'] = round(report['total_events'] / report['total_users'], 2)
                    report['avg_events_per_day'] = round(
                        report['total_events'] / max(report['date_span_days'], 1), 2
                    )

                    # Calculate time per user (total session time by each user)
                    user_total_session_times = []  # Sum of all sessions per user
                    user_session_lengths = []  # All individual session lengths

                    for user_id in course_data[self.user_col].dropna().unique():
                        user_data = course_data[course_data[self.user_col] == user_id].sort_values('datetime')

                        if len(user_data) > 1:
                            # Calculate sessions for this user
                            # Session = consecutive events within reasonable timeframe
                            time_diffs = user_data['datetime'].diff().dt.total_seconds() / 60
                            # Session breaks are gaps > 30 minutes
                            session_breaks = (time_diffs > 30) | time_diffs.isna()
                            user_data_copy = user_data.copy()
                            user_data_copy['session'] = session_breaks.cumsum()

                            user_session_time_total = 0
                            for session_id in user_data_copy['session'].unique():
                                session_data = user_data_copy[user_data_copy['session'] == session_id]
                                if len(session_data) > 1:
                                    # Calculate time from first to last event
                                    session_length = (session_data['datetime'].max() - session_data['datetime'].min()).total_seconds()

                                    # Add estimated time for last event based on median gap in this session
                                    time_gaps = session_data['datetime'].diff().dt.total_seconds().dropna()
                                    if len(time_gaps) > 0:
                                        median_gap = np.median(time_gaps)
                                        # Cap the estimate at 10 minutes (600 seconds) to avoid outliers
                                        estimated_last_event_time = min(median_gap, 600)
                                        session_length += estimated_last_event_time

                                    user_session_lengths.append(session_length)
                                    user_session_time_total += session_length

                            # Store total session time for this user
                            if user_session_time_total > 0:
                                user_total_session_times.append(user_session_time_total)

                    if user_total_session_times:
                        report['avg_time_per_user_minutes'] = round(np.mean(user_total_session_times), 2)
                        report['median_time_per_user_minutes'] = round(np.median(user_total_session_times), 2)
                    else:
                        report['avg_time_per_user_minutes'] = 0
                        report['median_time_per_user_minutes'] = 0

                    if user_session_lengths:
                        report['avg_session_length_minutes'] = round(np.mean(user_session_lengths), 2)
                        report['median_session_length_minutes'] = round(np.median(user_session_lengths), 2)
                    else:
                        report['avg_session_length_minutes'] = 0
                        report['median_session_length_minutes'] = 0
            else:
                report['total_users'] = 0
                report['avg_time_per_user_minutes'] = 0
                report['median_time_per_user_minutes'] = 0
                report['avg_session_length_minutes'] = 0
                report['median_session_length_minutes'] = 0

            # Event type breakdown
            if self.event_col:
                event_types = course_data[self.event_col].value_counts()
                report['unique_event_types'] = len(event_types)
                report['most_common_event'] = event_types.index[0] if len(event_types) > 0 else None
                report['most_common_event_count'] = int(event_types.iloc[0]) if len(event_types) > 0 else 0

                # Feature engagement analysis - count unique users who used each feature
                if self.user_col and report['total_users'] > 0:
                    # Define feature patterns to match against event name or tab property
                    # For quiz and evaluation: check event names
                    # For other features: check 'tab' column in properties
                    feature_patterns = {
                        'quiz': {'check_type': 'event', 'patterns': ['quiz']},
                        'evaluation': {'check_type': 'event', 'patterns': ['evaluation']},
                        'mind_map': {'check_type': 'tab', 'patterns': ['mindmap']},
                        'search': {'check_type': 'tab', 'patterns': ['search']},
                        'short_summary': {'check_type': 'tab', 'patterns': ['short_summary']},
                        'long_summary': {'check_type': 'tab', 'patterns': ['long_summary']},
                        'concepts': {'check_type': 'tab', 'patterns': ['concepts']}
                    }

                    # Count unique users who used each feature AND calculate time spent
                    for feature_name, config in feature_patterns.items():
                        check_type = config['check_type']
                        patterns = config['patterns']

                        if check_type == 'event':
                            # Check event names
                            if self.event_col:
                                events = course_data[self.event_col].astype(str).str.lower()
                                # Match any of the patterns
                                feature_mask = events.str.contains('|'.join(patterns), case=False, na=False)
                                feature_data = course_data[feature_mask]
                            else:
                                feature_data = pd.DataFrame()
                        else:  # check_type == 'tab'
                            # Check 'tab' column
                            if 'tab' in course_data.columns:
                                tabs = course_data['tab'].astype(str).str.lower()
                                # Match any of the patterns
                                feature_mask = tabs.str.contains('|'.join(patterns), case=False, na=False)
                                feature_data = course_data[feature_mask]
                            else:
                                feature_data = pd.DataFrame()

                        if len(feature_data) > 0 and self.user_col in feature_data.columns:
                            unique_users = feature_data[self.user_col].nunique()
                            percentage = round((unique_users / report['total_users']) * 100, 2)

                            # Calculate time spent in this feature per user (session-based)
                            user_feature_times = []
                            for user_id in feature_data[self.user_col].dropna().unique():
                                user_feature_data = feature_data[feature_data[self.user_col] == user_id].sort_values('datetime')

                                if len(user_feature_data) > 1:
                                    # Calculate sessions for this user in this feature
                                    # Session = consecutive events within reasonable timeframe
                                    time_diffs = user_feature_data['datetime'].diff().dt.total_seconds() / 60
                                    # Session breaks are gaps > 30 minutes
                                    session_breaks = (time_diffs > 30) | time_diffs.isna()
                                    user_feature_data_copy = user_feature_data.copy()
                                    user_feature_data_copy['session'] = session_breaks.cumsum()

                                    user_feature_time_total = 0
                                    for session_id in user_feature_data_copy['session'].unique():
                                        session_data = user_feature_data_copy[user_feature_data_copy['session'] == session_id]
                                        if len(session_data) > 1:
                                            # Calculate time from first to last event
                                            session_length = (session_data['datetime'].max() - session_data['datetime'].min()).total_seconds()

                                            # Add estimated time for last event based on median gap in this session
                                            time_gaps = session_data['datetime'].diff().dt.total_seconds().dropna()
                                            if len(time_gaps) > 0:
                                                median_gap = np.median(time_gaps)
                                                # Cap the estimate at 10 minutes (600 seconds) to avoid outliers
                                                estimated_last_event_time = min(median_gap, 600)
                                                session_length += estimated_last_event_time

                                            user_feature_time_total += session_length

                                    # Only append if user had actual session time
                                    if user_feature_time_total > 0:
                                        user_feature_times.append(user_feature_time_total)
                                elif len(user_feature_data) == 1:
                                    # Single event - don't count time for single events
                                    pass

                            avg_time = round(np.mean(user_feature_times), 2) if user_feature_times else 0
                            total_time = round(sum(user_feature_times), 2) if user_feature_times else 0
                        else:
                            unique_users = 0
                            percentage = 0.0
                            avg_time = 0
                            total_time = 0

                        report[f'users_{feature_name}'] = unique_users
                        report[f'users_{feature_name}_pct'] = percentage
                        report[f'avg_time_{feature_name}_minutes'] = avg_time
                        report[f'total_time_{feature_name}_minutes'] = total_time
                else:
                    # If no event column or no users, set all to 0
                    feature_names = ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']
                    for feature_name in feature_names:
                        report[f'users_{feature_name}'] = 0
                        report[f'users_{feature_name}_pct'] = 0.0
                        report[f'avg_time_{feature_name}_minutes'] = 0
                        report[f'total_time_{feature_name}_minutes'] = 0

            # Enrich with course information if available
            if self.course_info is not None and 'course_id' in self.course_info.columns:
                match = self.course_info[self.course_info['course_id'] == str(course_id)]
                if len(match) > 0:
                    for col in self.course_info.columns:
                        if col != 'course_id':
                            # Don't add 'course_' prefix if column already starts with 'course_'
                            # This avoids 'course_course_name' and similar duplications
                            if col.startswith('course_'):
                                report[col] = match.iloc[0][col]
                            else:
                                report[f'course_{col}'] = match.iloc[0][col]

            reports.append(report)

        df = pd.DataFrame(reports).sort_values('total_events', ascending=False)
        return df

    def get_user_breakdown_by_course(self) -> pd.DataFrame:
        """
        Get user-level breakdown for each course

        Returns:
            DataFrame with user metrics per course
        """
        if not self.course_col or not self.user_col:
            print("Warning: Missing course or user column")
            return pd.DataFrame()

        user_stats = []

        for course_id in self.df[self.course_col].dropna().unique():
            course_data = self.df[self.df[self.course_col] == course_id]

            for user_id in course_data[self.user_col].dropna().unique():
                user_course_data = course_data[course_data[self.user_col] == user_id]

                stats = {
                    'course_id': course_id,
                    'user_id': user_id,
                    'total_events': len(user_course_data),
                    'first_activity': user_course_data['datetime'].min(),
                    'last_activity': user_course_data['datetime'].max(),
                    'days_active': (user_course_data['datetime'].max() -
                                  user_course_data['datetime'].min()).days,
                }

                # Event type breakdown for this user
                if self.event_col:
                    event_counts = user_course_data[self.event_col].value_counts()
                    stats['unique_event_types'] = len(event_counts)

                user_stats.append(stats)

        return pd.DataFrame(user_stats).sort_values(['course_id', 'total_events'], ascending=[True, False])

    def get_event_timeline(self) -> pd.DataFrame:
        """
        Get daily event counts per course

        Returns:
            DataFrame with daily event counts
        """
        if not self.course_col:
            return pd.DataFrame()

        # Extract date from datetime
        self.df['date'] = self.df['datetime'].dt.date

        timeline = self.df.groupby([self.course_col, 'date']).size().reset_index(name='event_count')
        timeline.columns = ['course_id', 'date', 'event_count']

        return timeline.sort_values(['course_id', 'date'])

    def get_event_type_distribution(self) -> pd.DataFrame:
        """
        Get event type distribution per course

        Returns:
            DataFrame with event type counts per course
        """
        if not self.course_col or not self.event_col:
            return pd.DataFrame()

        distribution = self.df.groupby([self.course_col, self.event_col]).size().reset_index(name='count')
        distribution.columns = ['course_id', 'event_type', 'count']

        # Add percentage per course
        course_totals = distribution.groupby('course_id')['count'].transform('sum')
        distribution['percentage'] = round((distribution['count'] / course_totals) * 100, 2)

        return distribution.sort_values(['course_id', 'count'], ascending=[True, False])

    def export_to_csv(self, output_dir: str, from_date: str, to_date: str) -> Dict[str, str]:
        """
        Export all analysis results to CSV files

        Args:
            output_dir: Directory to save CSV files
            from_date: Start date for naming
            to_date: End date for naming

        Returns:
            Dictionary with file paths
        """
        os.makedirs(output_dir, exist_ok=True)

        files = {}

        # Course usage summary
        usage = self.get_course_usage_summary()
        if len(usage) > 0:
            path = os.path.join(output_dir, f"{from_date}_{to_date}_course_usage_summary.csv")
            usage.to_csv(path, index=False)
            files['usage_summary'] = path
            print(f"Exported: {path}")

        # User breakdown
        users = self.get_user_breakdown_by_course()
        if len(users) > 0:
            path = os.path.join(output_dir, f"{from_date}_{to_date}_user_breakdown.csv")
            users.to_csv(path, index=False)
            files['user_breakdown'] = path
            print(f"Exported: {path}")

        # Event timeline
        timeline = self.get_event_timeline()
        if len(timeline) > 0:
            path = os.path.join(output_dir, f"{from_date}_{to_date}_event_timeline.csv")
            timeline.to_csv(path, index=False)
            files['event_timeline'] = path
            print(f"Exported: {path}")

        # Event type distribution
        distribution = self.get_event_type_distribution()
        if len(distribution) > 0:
            path = os.path.join(output_dir, f"{from_date}_{to_date}_event_distribution.csv")
            distribution.to_csv(path, index=False)
            files['event_distribution'] = path
            print(f"Exported: {path}")

        return files

    def export_to_json(self, output_dir: str, from_date: str, to_date: str) -> str:
        """
        Export all analysis results to a single JSON file

        Args:
            output_dir: Directory to save JSON file
            from_date: Start date for naming
            to_date: End date for naming

        Returns:
            Path to JSON file
        """
        os.makedirs(output_dir, exist_ok=True)

        data = {
            'metadata': {
                'from_date': from_date,
                'to_date': to_date,
                'generated_at': datetime.now().isoformat(),
                'total_events': len(self.df),
                'total_courses': self.df[self.course_col].nunique() if self.course_col else 0,
            },
            'course_usage_summary': self.get_course_usage_summary().to_dict('records'),
            'user_breakdown': self.get_user_breakdown_by_course().to_dict('records'),
            'event_timeline': self.get_event_timeline().to_dict('records'),
            'event_type_distribution': self.get_event_type_distribution().to_dict('records'),
        }

        # Convert datetime objects to strings
        def convert_datetime(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif hasattr(obj, 'isoformat'):  # Handles date, time, etc.
                return obj.isoformat()
            elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif pd.isna(obj):
                return None
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        path = os.path.join(output_dir, f"{from_date}_{to_date}_course_analysis.json")
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=convert_datetime)

        print(f"Exported: {path}")
        return path

    def get_summary_stats(self) -> Dict:
        """
        Get high-level summary statistics

        Returns:
            Dictionary with summary stats
        """
        stats = {
            'total_events': len(self.df),
            'date_range': {
                'start': self.df['datetime'].min().isoformat(),
                'end': self.df['datetime'].max().isoformat(),
                'days': (self.df['datetime'].max() - self.df['datetime'].min()).days,
            }
        }

        if self.course_col:
            stats['total_courses'] = int(self.df[self.course_col].nunique())

        if self.user_col:
            stats['total_users'] = int(self.df[self.user_col].nunique())

        if self.event_col:
            stats['total_event_types'] = int(self.df[self.event_col].nunique())

        return stats