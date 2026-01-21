#!/usr/bin/env python3
"""
Weekly Progress Analyzer
Calculates week-by-week engagement metrics for semester-long courses
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


class WeeklyProgressAnalyzer:
    """Analyzes weekly progression of course engagement throughout a semester"""

    def __init__(self, weekly_files: List[str], semester_start: str, semester_end: str = None, course_id: Optional[str] = None, config: dict = None):
        """
        Initialize the analyzer

        Args:
            weekly_files: List of paths to weekly CSV files
            semester_start: Semester start date (YYYY-MM-DD)
            semester_end: Semester end date (YYYY-MM-DD), defaults to today
            course_id: Optional specific course to analyze (None = all courses combined)
            config: Configuration dictionary with scoring parameters
        """
        self.weekly_files = sorted(weekly_files)
        self.semester_start = pd.to_datetime(semester_start)
        self.semester_end = pd.to_datetime(semester_end) if semester_end else pd.to_datetime(datetime.now())
        self.course_id = course_id
        self.weekly_data = []
        self.user_engagement = {}  # Track user engagement for leaderboards
        self.user_feature_weeks = {}  # Track which weeks each user used each feature
        self.concept_tracker = {}  # Track concept usage: {concept_name: {week_num: count}}
        self.cumulative_concepts = {}  # Track cumulative concept counts across all weeks

        # Load scoring configuration
        report_config = config.get('report', {}) if config else {}
        engagement_config = report_config.get('engagement_scoring', {})
        feature_config = report_config.get('feature_scoring', {})

        # Session timeout for time calculations
        self.session_timeout_minutes = report_config.get('session_timeout_minutes', 15)

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

        # Load registered student counts from courses.csv
        self.registered_counts = {}
        if config:
            info_config = config.get('info', {})
            course_list_path = info_config.get('course_list', '')
            if course_list_path:
                try:
                    courses_df = pd.read_csv(course_list_path)
                    for _, row in courses_df.iterrows():
                        course_id_from_csv = row['Course ID']
                        registered = int(row['registered'])
                        self.registered_counts[course_id_from_csv] = registered
                    print(f"Loaded registered counts for {len(self.registered_counts)} courses from {course_list_path}")
                except Exception as e:
                    print(f"Warning: Could not load courses.csv from {course_list_path}: {e}")

        # Load teachers list and filter by blacklist
        self.teacher_ids = set()
        if config:
            # Get blacklist user IDs
            blacklist_config = config.get('blacklist', {})
            blacklisted_users = set(blacklist_config.get('user_ids', []))

            # Derive teachers.csv path from course_list path
            info_config = config.get('info', {})
            course_list_path = info_config.get('course_list', '')
            if course_list_path:
                import os
                teachers_path = os.path.join(os.path.dirname(course_list_path), 'teachers.csv')
                try:
                    teachers_df = pd.read_csv(teachers_path)
                    # Extract teacher IDs and filter out blacklisted users
                    if '$distinct_id' in teachers_df.columns:
                        all_teacher_ids = set(teachers_df['$distinct_id'].dropna().unique())
                        self.teacher_ids = all_teacher_ids - blacklisted_users
                        print(f"Loaded {len(self.teacher_ids)} teachers from {teachers_path} (filtered {len(all_teacher_ids) - len(self.teacher_ids)} blacklisted)")
                    else:
                        print(f"Warning: teachers.csv missing '$distinct_id' column")
                except Exception as e:
                    print(f"Warning: Could not load teachers.csv from {teachers_path}: {e}")

        # Load all weekly data
        self._load_weekly_data()

    def _load_weekly_data(self):
        """Load all weekly CSV files, excluding incomplete current week"""
        today = datetime.now().date()

        for week_file in self.weekly_files:
            try:
                # Load with low_memory=False to avoid dtype warnings
                df = pd.read_csv(week_file, low_memory=False)

                # Extract dates from filename (e.g., week_2025-10-16_2025-10-22.csv)
                # No week number in filename - calculate from semester start
                import os
                filename = os.path.basename(week_file)
                parts = filename.split('_')
                from_date = parts[1]
                to_date = parts[2].replace('.csv', '')

                # Calculate week number from semester start date
                from_dt = pd.to_datetime(from_date)
                days_from_start = (from_dt - self.semester_start).days
                week_num = (days_from_start // 7) + 1

                # Check if this week is complete
                # Weeks are Sat-Fri, so a week is complete if today > Friday (to_date)
                week_end_date = pd.to_datetime(to_date).date()

                if today <= week_end_date:
                    print(f"Skipping incomplete week {week_num} (ends {to_date}, today is {today})")
                    continue

                # Filter by course if specified
                # Raw event data uses 'course' column, not 'course_id'
                if self.course_id:
                    if 'course' in df.columns:
                        df = df[df['course'] == self.course_id]
                    elif 'course_id' in df.columns:
                        df = df[df['course_id'] == self.course_id]

                if len(df) > 0:
                    self.weekly_data.append({
                        'week_number': week_num,
                        'from_date': from_date,
                        'to_date': to_date,
                        'data': df
                    })
            except Exception as e:
                print(f"Error loading {week_file}: {e}")

        print(f"Loaded {len(self.weekly_data)} complete weeks of data")

    def calculate_weekly_metrics(self) -> pd.DataFrame:
        """
        Calculate all weekly metrics from raw event data

        Returns:
            DataFrame with one row per week containing all metrics
        """
        metrics = []

        # Track cumulative user activity across weeks
        all_users = set()
        user_active_weeks = {}  # user_id -> list of weeks they were active

        for week_info in self.weekly_data:
            week_num = week_info['week_number']
            from_date = week_info['from_date']
            to_date = week_info['to_date']
            df = week_info['data']

            # Extract active users from raw event data
            # User ID column can be '$user_id' or 'distinct_id'
            user_col = None
            if '$user_id' in df.columns:
                user_col = '$user_id'
            elif 'distinct_id' in df.columns:
                user_col = 'distinct_id'

            if user_col:
                # Get unique active users this week
                active_users = set(df[user_col].dropna().unique())
                wau_count = len(active_users)

                # Track cumulative enrollment (all users who have ever been active)
                for user in active_users:
                    all_users.add(user)
                    if user not in user_active_weeks:
                        user_active_weeks[user] = []
                    # Only add week if not already tracked (avoid duplicates)
                    if week_num not in user_active_weeks[user]:
                        user_active_weeks[user].append(week_num)

                    # Initialize user engagement tracking
                    if user not in self.user_engagement:
                        self.user_engagement[user] = {
                            'total_events': 0,
                            'weeks_active': [],
                            'last_active_week': 0
                        }

                    # Update user engagement data
                    user_events = df[df[user_col] == user]
                    self.user_engagement[user]['total_events'] += len(user_events)
                    if week_num not in self.user_engagement[user]['weeks_active']:
                        self.user_engagement[user]['weeks_active'].append(week_num)
                    self.user_engagement[user]['last_active_week'] = max(
                        self.user_engagement[user]['last_active_week'],
                        week_num
                    )

                # Get registered count from courses.csv, fallback to cumulative active users if not found
                if self.course_id and self.course_id in self.registered_counts:
                    total_enrolled = self.registered_counts[self.course_id]
                else:
                    total_enrolled = len(all_users)  # Fallback to cumulative unique active users
            else:
                # No user data available
                active_users = set()
                wau_count = 0
                total_enrolled = 0

            # Calculate metrics
            week_metrics = self._calculate_week_metrics(
                week_num=week_num,
                from_date=from_date,
                to_date=to_date,
                df=df,
                wau_count=wau_count,
                total_enrolled=total_enrolled,
                cumulative_active_users=len(all_users),
                user_active_weeks=user_active_weeks,
                all_weeks_so_far=week_num,
                active_users=active_users
            )

            metrics.append(week_metrics)

        return pd.DataFrame(metrics)

    def _calculate_week_metrics(
        self,
        week_num: int,
        from_date: str,
        to_date: str,
        df: pd.DataFrame,
        wau_count: int,
        total_enrolled: int,
        cumulative_active_users: int,
        user_active_weeks: Dict,
        all_weeks_so_far: int,
        active_users: set
    ) -> Dict:
        """Calculate all metrics for a single week from raw event data"""

        metrics = {
            'week_number': week_num,
            'from_date': from_date,
            'to_date': to_date,
        }

        # 1. STUDENT ACTIVITY METRICS

        # 1.1 Weekly Active Users (WAU)
        metrics['wau_count'] = wau_count
        metrics['wau_percentage'] = (wau_count / total_enrolled * 100) if total_enrolled > 0 else 0
        metrics['wau_percentage_of_active'] = (wau_count / cumulative_active_users * 100) if cumulative_active_users > 0 else 0
        metrics['total_enrolled'] = total_enrolled
        metrics['cumulative_active_users'] = cumulative_active_users

        # 1.2 Engagement Persistence Score
        persistence = self._calculate_persistence(user_active_weeks, all_weeks_so_far)
        metrics['persistent_consistent_pct'] = persistence['consistent_pct']
        metrics['persistent_moderate_pct'] = persistence['moderate_pct']
        metrics['persistent_sporadic_pct'] = persistence['sporadic_pct']

        # 1.3 Coverage (% of enrolled users active in ≥2 weeks)
        coverage = self._calculate_coverage(user_active_weeks, total_enrolled)
        metrics['coverage_pct'] = coverage['coverage_pct']
        metrics['coverage_count'] = coverage['coverage_count']

        # 1.4 At-Risk Student Count
        at_risk = self._calculate_at_risk(user_active_weeks, week_num)
        metrics['at_risk_count'] = at_risk['count']
        metrics['at_risk_percentage'] = at_risk['percentage']

        # 1.5 Reactivation Rate
        if week_num > 2:
            reactivation = self._calculate_reactivation(user_active_weeks, week_num)
            metrics['reactivation_rate'] = reactivation['rate']
            metrics['reactivated_count'] = reactivation['count']
        else:
            metrics['reactivation_rate'] = 0
            metrics['reactivated_count'] = 0

        # 1.6 Median Weekly Time Per Student and Lecturer
        time_metrics = self._calculate_weekly_time(df, active_users)
        metrics['median_weekly_time_minutes'] = time_metrics['median_time']
        metrics['total_weekly_time_minutes'] = time_metrics['total_time']
        metrics['median_weekly_time_students_minutes'] = time_metrics['median_time_students']
        metrics['median_weekly_time_lecturers_minutes'] = time_metrics['median_time_lecturers']

        # 2. FEATURE USAGE METRICS

        # 2.1 Feature Usage Rates and Time
        feature_metrics = self._calculate_feature_usage(df, wau_count, week_num)
        for feature, data in feature_metrics.items():
            metrics[f'feature_usage_{feature}'] = data['percentage']
            metrics[f'feature_time_{feature}_minutes'] = data['time_minutes']

        # 2.2 Feature Diversity Score
        diversity = self._calculate_feature_diversity(df)
        metrics['diversity_explorers_pct'] = diversity['explorers_pct']
        metrics['diversity_regulars_pct'] = diversity['regulars_pct']
        metrics['diversity_minimal_pct'] = diversity['minimal_pct']

        # 2.3 Semester-wide feature usage (% of active users >=2 weeks who used feature >= 2 times)
        coverage_count = metrics['coverage_count']
        for feature_name in ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']:
            semester_users = 0
            if feature_name in self.user_feature_weeks:
                for user, weeks in self.user_feature_weeks[feature_name].items():
                    if len(weeks) >= 2:
                        semester_users += 1
            # Divide by coverage_count (users active >=2 weeks), not total_enrolled
            metrics[f'feature_semester_{feature_name}'] = (semester_users / coverage_count * 100) if coverage_count > 0 else 0

        # 3. CONCEPT USAGE METRICS
        concept_data = self._calculate_concept_usage(df, week_num)
        metrics['top_concepts_this_week'] = concept_data['top_concepts_this_week']
        metrics['top_concepts_cumulative'] = concept_data['top_concepts_cumulative']

        return metrics

    def _calculate_persistence(self, user_active_weeks: Dict, total_weeks: int) -> Dict:
        """Calculate engagement persistence categories"""
        if total_weeks == 0 or len(user_active_weeks) == 0:
            return {'consistent_pct': 0, 'moderate_pct': 0, 'sporadic_pct': 0}

        consistent = 0
        moderate = 0
        sporadic = 0

        for user, weeks in user_active_weeks.items():
            persistence_rate = len(weeks) / total_weeks * 100

            if persistence_rate >= 60:
                consistent += 1
            elif persistence_rate >= 25:
                moderate += 1
            else:
                sporadic += 1

        total_users = len(user_active_weeks)

        return {
            'consistent_pct': consistent / total_users * 100 if total_users > 0 else 0,
            'moderate_pct': moderate / total_users * 100 if total_users > 0 else 0,
            'sporadic_pct': sporadic / total_users * 100 if total_users > 0 else 0,
        }

    def _calculate_coverage(self, user_active_weeks: Dict, total_enrolled: int) -> Dict:
        """
        Calculate coverage: % of enrolled users active in ≥2 weeks

        Args:
            user_active_weeks: Dictionary mapping user_id to list of active weeks
            total_enrolled: Total number of enrolled users

        Returns:
            Dictionary with coverage_pct and coverage_count
        """
        if total_enrolled == 0 or len(user_active_weeks) == 0:
            return {'coverage_pct': 0, 'coverage_count': 0}

        # Count users active in 2 or more weeks
        covered_users = 0
        for user, weeks in user_active_weeks.items():
            if len(weeks) >= 2:
                covered_users += 1

        return {
            'coverage_pct': (covered_users / total_enrolled * 100) if total_enrolled > 0 else 0,
            'coverage_count': covered_users
        }

    def _calculate_at_risk(self, user_active_weeks: Dict, current_week: int) -> Dict:
        """Calculate at-risk students (inactive for 3+ weeks)"""
        if current_week < 4:
            return {'count': 0, 'percentage': 0}

        at_risk = 0

        for user, weeks in user_active_weeks.items():
            if len(weeks) > 0:
                last_active_week = max(weeks)
                weeks_inactive = current_week - last_active_week

                if weeks_inactive >= 3:
                    at_risk += 1

        total_users = len(user_active_weeks)

        return {
            'count': at_risk,
            'percentage': at_risk / total_users * 100 if total_users > 0 else 0
        }

    def _calculate_reactivation(self, user_active_weeks: Dict, current_week: int) -> Dict:
        """Calculate reactivation rate"""
        # Find users who were inactive for 2+ weeks before this week
        inactive_pool = set()
        reactivated = set()

        for user, weeks in user_active_weeks.items():
            # Check if they were inactive before this week
            weeks_before_now = [w for w in weeks if w < current_week]

            if len(weeks_before_now) > 0:
                last_active = max(weeks_before_now)
                weeks_inactive = current_week - last_active - 1  # Don't count current week

                if weeks_inactive >= 2:
                    inactive_pool.add(user)

                    # Did they come back this week?
                    if current_week in weeks:
                        reactivated.add(user)

        rate = len(reactivated) / len(inactive_pool) * 100 if len(inactive_pool) > 0 else 0

        return {
            'rate': rate,
            'count': len(reactivated)
        }

    def _calculate_weekly_time(self, df: pd.DataFrame, active_users: set) -> Dict:
        """
        Calculate median weekly time per student and lecturer separately
        For each user:
          1. Detect all sessions (time gap > session_timeout_minutes = new session)
          2. For each session: time = (last_event - first_event) + timeout
          3. Sum all session times for that user
        Show median of these user sums, separated by student/lecturer

        Args:
            df: Weekly event data
            active_users: Set of active user IDs this week

        Returns:
            Dict with median_time, total_time, median_time_students, median_time_lecturers in minutes
        """
        if len(active_users) == 0:
            return {
                'median_time': 0,
                'total_time': 0,
                'median_time_students': 0,
                'median_time_lecturers': 0
            }

        # Get user ID and time columns
        user_col = '$user_id' if '$user_id' in df.columns else 'distinct_id' if 'distinct_id' in df.columns else None
        time_col = 'time' if 'time' in df.columns else None

        if not user_col or not time_col:
            return {
                'median_time': 0,
                'total_time': 0,
                'median_time_students': 0,
                'median_time_lecturers': 0
            }

        # Convert time column to datetime if it's Unix timestamp
        df_copy = df.copy()
        if pd.api.types.is_numeric_dtype(df_copy[time_col]):
            df_copy['datetime'] = pd.to_datetime(df_copy[time_col], unit='s')
        else:
            df_copy['datetime'] = pd.to_datetime(df_copy[time_col])

        # Sort by user and time
        df_copy = df_copy.sort_values([user_col, 'datetime'])

        # Calculate time for each user (sum of all their sessions)
        # Separate students and lecturers
        user_times_all = []
        user_times_students = []
        user_times_lecturers = []

        for user in active_users:
            user_data = df_copy[df_copy[user_col] == user].copy()
            if len(user_data) == 0:
                continue

            # Detect sessions based on time gaps
            user_data = user_data.sort_values('datetime')
            time_diffs = user_data['datetime'].diff()

            # New session when gap > session_timeout_minutes OR first event
            new_session = (time_diffs > pd.Timedelta(minutes=self.session_timeout_minutes)) | time_diffs.isna()
            user_data['session_id'] = new_session.cumsum()

            # Calculate time for each session
            user_total_time = 0
            for session_id in user_data['session_id'].unique():
                session_data = user_data[user_data['session_id'] == session_id]
                first = session_data['datetime'].min()
                last = session_data['datetime'].max()

                # Session time = (last - first) + timeout
                session_duration = (last - first).total_seconds() / 60
                session_time = session_duration + self.session_timeout_minutes
                user_total_time += session_time

            # Add to appropriate lists
            user_times_all.append(user_total_time)
            if user in self.teacher_ids:
                user_times_lecturers.append(user_total_time)
            else:
                user_times_students.append(user_total_time)

        # Calculate medians
        median_all = np.median(user_times_all) if len(user_times_all) > 0 else 0
        median_students = np.median(user_times_students) if len(user_times_students) > 0 else 0
        median_lecturers = np.median(user_times_lecturers) if len(user_times_lecturers) > 0 else 0

        return {
            'median_time': median_all,
            'total_time': sum(user_times_all),
            'median_time_students': median_students,
            'median_time_lecturers': median_lecturers
        }

    def _calculate_feature_usage(self, df: pd.DataFrame, wau_count: int, week_num: int = None) -> Dict:
        """
        Calculate feature usage rates and time from raw event data

        For each feature:
        - percentage: % of WAU who used this feature
        - time_minutes: total time spent using this feature (session-based with timeout)

        Uses same logic as semester report:
        - quiz, evaluation: check event names
        - mind_map, search, short_summary, long_summary, concepts: check 'tab' column
        """
        # Define feature patterns matching semester report logic
        feature_patterns = {
            'quiz': {'check_type': 'event', 'patterns': ['quiz']},
            'evaluation': {'check_type': 'event', 'patterns': ['evaluation']},
            'mind_map': {'check_type': 'tab', 'patterns': ['mindmap']},
            'search': {'check_type': 'tab', 'patterns': ['search']},
            'short_summary': {'check_type': 'tab', 'patterns': ['short_summary']},
            'long_summary': {'check_type': 'tab', 'patterns': ['long_summary']},
            'concepts': {'check_type': 'tab', 'patterns': ['concepts']}
        }

        usage = {}

        # Get user ID and time columns
        user_col = '$user_id' if '$user_id' in df.columns else 'distinct_id' if 'distinct_id' in df.columns else None
        time_col = 'time' if 'time' in df.columns else None

        if user_col:
            for feature_name, config in feature_patterns.items():
                check_type = config['check_type']
                patterns = config['patterns']

                if check_type == 'event':
                    # Check event names
                    if 'event' in df.columns:
                        events = df['event'].astype(str).str.lower()
                        # Match any of the patterns
                        feature_mask = events.str.contains('|'.join(patterns), case=False, na=False)
                        feature_df = df[feature_mask].copy()
                    else:
                        feature_df = pd.DataFrame()
                else:  # check_type == 'tab'
                    # Check 'tab' column
                    if 'tab' in df.columns:
                        tabs = df['tab'].astype(str).str.lower()
                        # Match any of the patterns
                        feature_mask = tabs.str.contains('|'.join(patterns), case=False, na=False)
                        feature_df = df[feature_mask].copy()
                    else:
                        feature_df = pd.DataFrame()

                # Calculate percentage and time
                if len(feature_df) > 0 and user_col in feature_df.columns:
                    feature_users = feature_df[user_col].nunique()
                    percentage = (feature_users / wau_count * 100) if wau_count > 0 else 0

                    # Track user-feature-weeks for semester-wide stats
                    if week_num is not None:
                        if feature_name not in self.user_feature_weeks:
                            self.user_feature_weeks[feature_name] = {}
                        for user in feature_df[user_col].unique():
                            if pd.notna(user):
                                if user not in self.user_feature_weeks[feature_name]:
                                    self.user_feature_weeks[feature_name][user] = []
                                if week_num not in self.user_feature_weeks[feature_name][user]:
                                    self.user_feature_weeks[feature_name][user].append(week_num)

                    # Calculate time spent on this feature
                    time_minutes = self._calculate_feature_time(feature_df, user_col, time_col)

                    usage[feature_name] = {
                        'percentage': percentage,
                        'time_minutes': time_minutes
                    }
                else:
                    usage[feature_name] = {
                        'percentage': 0,
                        'time_minutes': 0
                    }
        else:
            # No user data, return zeros
            for feature_name in feature_patterns.keys():
                usage[feature_name] = {
                    'percentage': 0,
                    'time_minutes': 0
                }

        return usage

    def _calculate_feature_time(self, feature_df: pd.DataFrame, user_col: str, time_col: str) -> float:
        """
        Calculate total time spent on a feature across all users
        Uses session-based calculation with timeout

        Args:
            feature_df: DataFrame with only events for this feature
            user_col: User ID column name
            time_col: Time column name

        Returns:
            Total time in minutes
        """
        if len(feature_df) == 0 or not time_col or time_col not in feature_df.columns:
            return 0

        # Convert time column to datetime if it's Unix timestamp
        df_copy = feature_df.copy()
        if pd.api.types.is_numeric_dtype(df_copy[time_col]):
            df_copy['datetime'] = pd.to_datetime(df_copy[time_col], unit='s')
        else:
            df_copy['datetime'] = pd.to_datetime(df_copy[time_col])

        # Sort by user and time
        df_copy = df_copy.sort_values([user_col, 'datetime'])

        total_time = 0
        for user in df_copy[user_col].unique():
            user_data = df_copy[df_copy[user_col] == user].copy()
            if len(user_data) == 0:
                continue

            # Detect sessions based on time gaps
            user_data = user_data.sort_values('datetime')
            time_diffs = user_data['datetime'].diff()

            # New session when gap > session_timeout_minutes OR first event
            new_session = (time_diffs > pd.Timedelta(minutes=self.session_timeout_minutes)) | time_diffs.isna()
            user_data['session_id'] = new_session.cumsum()

            # Calculate time for each session
            for session_id in user_data['session_id'].unique():
                session_data = user_data[user_data['session_id'] == session_id]
                first = session_data['datetime'].min()
                last = session_data['datetime'].max()

                # Session time = (last - first) + timeout
                session_duration = (last - first).total_seconds() / 60
                session_time = session_duration + self.session_timeout_minutes
                total_time += session_time

        return total_time

    def _calculate_feature_diversity(self, df: pd.DataFrame) -> Dict:
        """Calculate feature diversity distribution"""
        # This requires user-level data which we don't have in aggregated weekly files
        # For now, return placeholder
        return {
            'explorers_pct': 0,
            'regulars_pct': 0,
            'minimal_pct': 0
        }

    def _calculate_concept_usage(self, df: pd.DataFrame, week_num: int) -> Dict:
        """
        Calculate top concepts used this week and cumulatively

        Args:
            df: Weekly event data
            week_num: Current week number

        Returns:
            Dict with top_concepts_this_week and top_concepts_cumulative
            Each is a list of tuples: [(concept_name, count), ...]
        """
        top_concepts_this_week = []
        top_concepts_cumulative = []

        if 'concept' not in df.columns:
            return {
                'top_concepts_this_week': top_concepts_this_week,
                'top_concepts_cumulative': top_concepts_cumulative
            }

        # Get concepts from this week (filter out empty/null values)
        concepts_this_week = df['concept'].dropna()
        concepts_this_week = concepts_this_week[concepts_this_week != '']
        concepts_this_week = concepts_this_week.astype(str).str.strip()
        concepts_this_week = concepts_this_week[concepts_this_week != '']

        if len(concepts_this_week) > 0:
            # Count concepts for this week
            concept_counts_week = concepts_this_week.value_counts()

            # Track in concept_tracker for cumulative calculation
            for concept, count in concept_counts_week.items():
                if concept not in self.concept_tracker:
                    self.concept_tracker[concept] = {}
                self.concept_tracker[concept][week_num] = count

                # Update cumulative counts
                if concept not in self.cumulative_concepts:
                    self.cumulative_concepts[concept] = 0
                self.cumulative_concepts[concept] += count

            # Get top 5 concepts this week with counts
            top_concepts_this_week = [(concept, int(count)) for concept, count in concept_counts_week.head(5).items()]

        # Get top 5 cumulative concepts with counts
        if self.cumulative_concepts:
            sorted_cumulative = sorted(self.cumulative_concepts.items(), key=lambda x: x[1], reverse=True)
            top_concepts_cumulative = [(concept, int(count)) for concept, count in sorted_cumulative[:5]]

        return {
            'top_concepts_this_week': top_concepts_this_week,
            'top_concepts_cumulative': top_concepts_cumulative
        }

    def calculate_trend_metrics(self, weekly_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Add trend metrics to weekly data

        Args:
            weekly_metrics: DataFrame from calculate_weekly_metrics()

        Returns:
            Enhanced DataFrame with trend metrics
        """
        df = weekly_metrics.copy()

        # 3.1 Week-over-Week Change
        df['wau_wow_change'] = df['wau_count'].diff()
        df['wau_wow_change_pct'] = df['wau_count'].pct_change() * 100

        # 3.2 Trend vs Baseline (Weeks 1-2)
        baseline_weeks = df[df['week_number'].isin([1, 2])]
        if len(baseline_weeks) > 0:
            baseline_wau = baseline_weeks['wau_percentage'].mean()
            df['wau_vs_baseline'] = df['wau_percentage'] - baseline_wau
            df['wau_vs_baseline_pct'] = (df['wau_percentage'] / baseline_wau - 1) * 100
        else:
            df['wau_vs_baseline'] = 0
            df['wau_vs_baseline_pct'] = 0

        # 3.3 Feature Momentum (3-week moving average)
        if len(df) >= 3:
            for feature in ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']:
                col = f'feature_usage_{feature}'
                if col in df.columns:
                    df[f'{col}_ma3'] = df[col].rolling(window=3, min_periods=1).mean()
                    df[f'{col}_momentum'] = df[f'{col}_ma3'].diff()

        # 3.4 Drop Risk Velocity
        df['drop_risk_velocity'] = 0.0
        for i in range(1, len(df)):
            if df.iloc[i-1]['wau_count'] > 0:
                new_at_risk = df.iloc[i]['at_risk_count'] - df.iloc[i-1].get('at_risk_count', 0)
                df.loc[df.index[i], 'drop_risk_velocity'] = (new_at_risk / df.iloc[i-1]['wau_count']) * 100

        return df

    def calculate_semester_phase_metrics(self, weekly_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Add semester phase analysis

        Args:
            weekly_metrics: DataFrame with trend metrics

        Returns:
            Enhanced DataFrame with phase metrics
        """
        df = weekly_metrics.copy()

        # Calculate total semester weeks
        total_semester_weeks = int((self.semester_end - self.semester_start).days / 7) + 1

        # Define semester phases based on actual calendar dates
        # Launch: first 2 weeks from semester_start
        # Pre-Exam: last 2 weeks before semester_end
        # Valley: everything in between
        launch_end = self.semester_start + pd.Timedelta(days=14)  # First 2 weeks
        preexam_start = self.semester_end - pd.Timedelta(days=14)  # Last 2 weeks

        def get_phase(from_date_str):
            from_date = pd.to_datetime(from_date_str)
            if from_date < launch_end:
                return 'Launch'
            elif from_date >= preexam_start:
                return 'Pre-Exam'
            else:
                return 'Valley'

        df['semester_phase'] = df['from_date'].apply(get_phase)

        # Expected WAU ranges by phase
        def get_expected_range(phase):
            if phase == 'Launch':
                return (70, 100)
            elif phase == 'Valley':
                return (20, 40)
            else:  # Pre-Exam
                return (60, 80)

        df['expected_wau_min'] = df['semester_phase'].apply(lambda p: get_expected_range(p)[0])
        df['expected_wau_max'] = df['semester_phase'].apply(lambda p: get_expected_range(p)[1])

        # Phase performance status
        def get_status(row):
            wau = row['wau_percentage']
            min_expected = row['expected_wau_min']
            max_expected = row['expected_wau_max']

            # On Track: within expected range
            if wau >= min_expected and wau <= max_expected:
                return 'On Track'
            # Above Expected: above max
            elif wau > max_expected:
                return 'Above Expected'
            # Below Expected: below min but not critically low
            elif wau >= min_expected * 0.8:
                return 'Below Expected'
            # Critical: significantly below minimum
            else:
                return 'Critical'

        df['phase_status'] = df.apply(get_status, axis=1)

        # 4.2 Recovery Indicator (Week 9+)
        if len(df) >= 9:
            valley_weeks = df[df['week_number'].between(4, 8)]
            if len(valley_weeks) > 0:
                valley_lowest = valley_weeks['wau_percentage'].min()

                df['recovery_from_valley'] = 0.0
                df['recovery_status'] = ''

                for i in df[df['week_number'] >= 9].index:
                    current_wau = df.loc[i, 'wau_percentage']
                    recovery_pct = (current_wau / valley_lowest * 100) if valley_lowest > 0 else 100

                    df.loc[i, 'recovery_from_valley'] = recovery_pct

                    if recovery_pct >= 110:
                        df.loc[i, 'recovery_status'] = 'Recovering'
                    elif recovery_pct >= 90:
                        df.loc[i, 'recovery_status'] = 'Flat'
                    else:
                        df.loc[i, 'recovery_status'] = 'Still Declining'

        return df

    def generate_executive_summary(self, weekly_metrics: pd.DataFrame) -> str:
        """
        Generate executive summary for the latest complete week - one liner per section

        Args:
            weekly_metrics: DataFrame with all metrics

        Returns:
            HTML-formatted executive summary
        """
        if len(weekly_metrics) == 0:
            return "<p>No data available for summary.</p>"

        latest = weekly_metrics.iloc[-1]
        week_num = int(latest['week_number'])
        from_date = latest['from_date']
        to_date = latest['to_date']
        phase = latest.get('semester_phase', 'Unknown')
        wau_pct = latest['wau_percentage']
        wau_count = int(latest['wau_count'])
        total_enrolled = int(latest['total_enrolled'])
        phase_status = latest.get('phase_status', 'Unknown')

        # Get metrics for one-liners
        consistent_pct = latest.get('persistent_consistent_pct', 0)
        moderate_pct = latest.get('persistent_moderate_pct', 0)
        sporadic_pct = latest.get('persistent_sporadic_pct', 0)
        at_risk_count = int(latest.get('at_risk_count', 0))
        at_risk_pct = latest.get('at_risk_percentage', 0)

        # Top features (exclude moving averages and momentum columns)
        feature_cols = [col for col in latest.index if col.startswith('feature_usage_') and not col.endswith('_ma3') and not col.endswith('_momentum')]
        top_features = []
        for col in feature_cols:
            if latest[col] > 0:
                feature_name = col.replace('feature_usage_', '').replace('_', ' ').title()
                top_features.append((feature_name, latest[col]))
        top_features.sort(key=lambda x: x[1], reverse=True)
        top_3_features = top_features[:3] if len(top_features) >= 3 else top_features

        # Build one-liner summary
        summary_html = f"<h3>Week {week_num}: {from_date} to {to_date} ({phase} phase)</h3>"
        summary_html += "<p style='font-size: 1.1em; line-height: 2.0;'>"

        # WAU one-liner
        if phase_status == 'On Track':
            status_color = 'green'
        elif phase_status == 'Above Expected':
            status_color = 'blue'
        elif phase_status == 'Below Expected':
            status_color = 'orange'
        else:  # Critical
            status_color = 'red'
        summary_html += f"<strong>WAU:</strong> {wau_count}/{total_enrolled} students ({wau_pct:.0f}%) - <span style='color: {status_color};'>{phase_status}</span><br>"

        # Calculate Engagement Score
        if total_enrolled > 0:
            consistent_count = (consistent_pct / 100) * total_enrolled
            moderate_count = (moderate_pct / 100) * total_enrolled
            sporadic_count = (sporadic_pct / 100) * total_enrolled
            eng_score = (consistent_count * self.eng_consistent_weight +
                        moderate_count * self.eng_moderate_weight +
                        sporadic_count * self.eng_sporadic_weight) / total_enrolled
            eng_expected = ((self.eng_expected_consistent / 100) * self.eng_consistent_weight +
                           (self.eng_expected_moderate / 100) * self.eng_moderate_weight +
                           (self.eng_expected_sporadic / 100) * self.eng_sporadic_weight)
            eng_delta = eng_score - eng_expected
            eng_status = "above" if eng_delta > 0 else "below" if eng_delta < 0 else "at"
            eng_color = "green" if eng_delta > 0 else "red" if eng_delta < 0 else "gray"
        else:
            eng_score = 0
            eng_delta = 0
            eng_status = "at"
            eng_color = "gray"

        # Persistence one-liner with score
        summary_html += f"<strong>Engagement:</strong> {consistent_pct:.0f}% consistent, {moderate_pct:.0f}% moderate, {sporadic_pct:.0f}% sporadic | Score: {eng_score:.2f} (<span style='color: {eng_color};'>{eng_delta:+.2f} {eng_status} expected</span>)<br>"

        # Calculate Feature Usage Score
        num_features = 7
        high_count = sum(1 for col in feature_cols if latest[col] >= self.feat_high_threshold) if feature_cols else 0
        moderate_count = sum(1 for col in feature_cols if self.feat_moderate_threshold <= latest[col] < self.feat_high_threshold) if feature_cols else 0
        low_count = num_features - high_count - moderate_count

        feat_score = (high_count * self.feat_high_weight +
                     moderate_count * self.feat_moderate_weight +
                     low_count * self.feat_low_weight) / num_features

        # Top features one-liner with score
        if top_3_features:
            features_str = ", ".join([f"{name} ({val:.0f}%)" for name, val in top_3_features])
            summary_html += f"<strong>Top Features:</strong> {features_str} | Score: {feat_score:.2f}/{self.feat_high_weight:.0f}<br>"
        else:
            summary_html += f"<strong>Feature Usage Score:</strong> {feat_score:.2f}/{self.feat_high_weight:.0f}<br>"

        # At-risk one-liner
        risk_color = 'red' if at_risk_pct > 30 else ('orange' if at_risk_pct > 20 else 'green')
        summary_html += f"<strong>At-Risk:</strong> <span style='color: {risk_color};'>{at_risk_count} students ({at_risk_pct:.0f}%)</span> inactive 3+ weeks<br>"

        # Reactivation one-liner (if available)
        reactivation_rate = latest.get('reactivation_rate', 0)
        if reactivation_rate > 0:
            summary_html += f"<strong>Reactivation:</strong> {reactivation_rate:.0f}% of inactive students returned this week<br>"

        # WoW trend one-liner
        wow_change_pct = latest.get('wau_wow_change_pct', 0)
        if not pd.isna(wow_change_pct) and wow_change_pct != 0:
            trend_direction = "↑" if wow_change_pct > 0 else "↓"
            trend_color = "green" if wow_change_pct > 0 else "red"
            summary_html += f"<strong>Week-over-Week:</strong> <span style='color: {trend_color};'>{trend_direction} {abs(wow_change_pct):.1f}%</span> change from last week<br>"

        # Feature diversity one-liner (if we have the data)
        explorers_pct = latest.get('diversity_explorers_pct', 0)
        regulars_pct = latest.get('diversity_regulars_pct', 0)
        minimal_pct = latest.get('diversity_minimal_pct', 0)
        if explorers_pct > 0 or regulars_pct > 0 or minimal_pct > 0:
            summary_html += f"<strong>Feature Diversity:</strong> {explorers_pct:.0f}% explorers, {regulars_pct:.0f}% regulars, {minimal_pct:.0f}% minimal users"

        summary_html += "</p>"

        return summary_html

    def get_student_leaderboards(self, current_week: int, top_n: int = 10) -> Dict:
        """
        Generate student leaderboards for most engaged and at-risk students

        Args:
            current_week: Current week number
            top_n: Number of students to show in each leaderboard

        Returns:
            Dictionary with 'top_engaged' and 'at_risk' lists
        """
        if not self.user_engagement:
            return {'top_engaged': [], 'at_risk': []}

        # Calculate engagement scores for each student
        student_scores = []
        for user_id, data in self.user_engagement.items():
            weeks_active = len(data['weeks_active'])
            total_events = data['total_events']
            last_active = data['last_active_week']
            weeks_inactive = current_week - last_active

            # Engagement score: combination of weeks active % and total events
            # Higher weight on consistency (weeks active)
            persistence_pct = (weeks_active / current_week * 100) if current_week > 0 else 0
            engagement_score = (persistence_pct * 0.7) + (min(total_events / 100, 100) * 0.3)

            student_scores.append({
                'user_id': user_id,
                'engagement_score': engagement_score,
                'weeks_active': weeks_active,
                'persistence_pct': persistence_pct,
                'total_events': total_events,
                'last_active_week': last_active,
                'weeks_inactive': weeks_inactive
            })

        # Sort by engagement score descending for top engaged
        top_engaged = sorted(student_scores, key=lambda x: x['engagement_score'], reverse=True)[:top_n]

        # Get at-risk students (inactive 3+ weeks) sorted by weeks inactive descending
        at_risk = [s for s in student_scores if s['weeks_inactive'] >= 3]
        at_risk = sorted(at_risk, key=lambda x: x['weeks_inactive'], reverse=True)[:top_n]

        return {
            'top_engaged': top_engaged,
            'at_risk': at_risk
        }