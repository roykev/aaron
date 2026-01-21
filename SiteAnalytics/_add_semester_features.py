#!/usr/bin/env python3
"""
Add semester-wide feature usage tracking to WeeklyProgressAnalyzer

This script modifies weekly_progress_analyzer.py to:
1. Track which users use each feature in which weeks
2. Calculate semester-wide feature usage (% of users who used feature >= 2 times)
3. Add cumulative unique user tracking for WAU percentage calculations
"""

file_path = "/media/roy/hdd/git/SiteAnalytics/weekly_progress_analyzer.py"

with open(file_path, 'r') as f:
    content = f.read()

# 1. Update _calculate_feature_usage to track user-feature-weeks
old_calc_feat = '''    def _calculate_feature_usage(self, df: pd.DataFrame, wau_count: int) -> Dict:
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

        return usage'''

new_calc_feat = '''    def _calculate_feature_usage(self, df: pd.DataFrame, wau_count: int, week_num: int = None) -> Dict:
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

        return usage'''

content = content.replace(old_calc_feat, new_calc_feat)

# 2. Update the call to _calculate_feature_usage to include week_num
old_call = """        # 2. FEATURE USAGE METRICS

        # 2.1 Feature Usage Rates and Time
        feature_metrics = self._calculate_feature_usage(df, wau_count)"""

new_call = """        # 2. FEATURE USAGE METRICS

        # 2.1 Feature Usage Rates and Time
        feature_metrics = self._calculate_feature_usage(df, wau_count, week_num)"""

content = content.replace(old_call, new_call)

# 3. Add semester-wide feature usage tracking to metrics
old_metrics_end = """        # 2.2 Feature Diversity Score
        diversity = self._calculate_feature_diversity(df)
        metrics['diversity_explorers_pct'] = diversity['explorers_pct']
        metrics['diversity_regulars_pct'] = diversity['regulars_pct']
        metrics['diversity_minimal_pct'] = diversity['minimal_pct']

        return metrics"""

new_metrics_end = """        # 2.2 Feature Diversity Score
        diversity = self._calculate_feature_diversity(df)
        metrics['diversity_explorers_pct'] = diversity['explorers_pct']
        metrics['diversity_regulars_pct'] = diversity['regulars_pct']
        metrics['diversity_minimal_pct'] = diversity['minimal_pct']

        # 2.3 Semester-wide feature usage (% of total enrolled who used feature >= 2 times)
        for feature_name in ['quiz', 'evaluation', 'mind_map', 'search', 'short_summary', 'long_summary', 'concepts']:
            semester_users = 0
            if feature_name in self.user_feature_weeks:
                for user, weeks in self.user_feature_weeks[feature_name].items():
                    if len(weeks) >= 2:
                        semester_users += 1
            metrics[f'feature_semester_{feature_name}'] = (semester_users / total_enrolled * 100) if total_enrolled > 0 else 0

        return metrics"""

content = content.replace(old_metrics_end, new_metrics_end)

with open(file_path, 'w') as f:
    f.write(content)

print(f"✓ Enhanced {file_path} with semester-wide feature tracking")