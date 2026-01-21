#!/usr/bin/env python3
"""
Mixpanel Course Analysis Script - SNAPSHOT REPORT
Main entry point for generating snapshot reports (specific date range)
For semester-wide reports and weekly extraction, use semester_analyzer.py
Integrates with config.yaml for automatic data loading and course information
"""

import pandas as pd
import os
import sys
from typing import Dict, Optional
import subprocess
import argparse
from datetime import timedelta
import numpy as np
import json

# Import from local modules
from utils import load_config, load_course_list
from course_analysis import CourseAnalysis
from course_reporter_old import CourseReporter


class CourseAnalyzer:
    """Analyzes Mixpanel event data by course"""

    def __init__(self, csv_path: str, session_timeout_minutes: int = 30):
        """
        Initialize the course analyzer

        Args:
            csv_path: Path to Mixpanel export CSV
            session_timeout_minutes: Minutes of inactivity to define new session
        """
        self.df = pd.read_csv(csv_path)
        self.session_timeout = session_timeout_minutes

        # Convert timestamp to datetime
        if 'Time' in self.df.columns:
            self.df['datetime'] = pd.to_datetime(self.df['Time'], unit='s')

        # Detect sessions
        self._detect_sessions()

        print(f"Loaded {len(self.df)} events from {csv_path}")
        print(f"Date range: {self.df['datetime'].min()} to {self.df['datetime'].max()}")
        print(f"Courses found: {self.df['course'].nunique()}")

    def _detect_sessions(self):
        """Detect user sessions based on time gaps"""
        self.df = self.df.sort_values(['User ID', 'datetime'])

        def calculate_sessions(user_df):
            user_df = user_df.sort_values('datetime')
            time_diffs = user_df['datetime'].diff()
            new_session = (time_diffs > timedelta(minutes=self.session_timeout)) | time_diffs.isna()
            return new_session.cumsum()

        self.df['session_id'] = self.df.groupby('User ID', group_keys=False).apply(
            calculate_sessions
        ).values

    def _calculate_user_session_time(self, user_data: pd.DataFrame) -> float:
        """
        Calculate total session time for a user using session-based approach

        For each session:
          - time = (last_event - first_event) + timeout
        Sum all sessions

        Args:
            user_data: DataFrame containing events for a single user (must have 'datetime' and 'session_id')

        Returns:
            Total time in minutes
        """
        total_time = 0.0

        for session_id in user_data['session_id'].unique():
            session_data = user_data[user_data['session_id'] == session_id]
            first = session_data['datetime'].min()
            last = session_data['datetime'].max()

            # Session time = duration + timeout
            session_duration = (last - first).total_seconds() / 60
            session_time = session_duration + self.session_timeout
            total_time += session_time

        return total_time

    def get_course_overview(self) -> pd.DataFrame:
        """
        Get overview statistics for each course

        Returns:
            DataFrame with course-level metrics
        """
        course_stats = []

        for course_id in self.df['course'].dropna().unique():
            course_data = self.df[self.df['course'] == course_id]

            stats = {
                'course_id': course_id,
                'total_users': course_data['User ID'].nunique(),
                'total_events': len(course_data),
                'total_sessions': course_data.groupby('User ID')['session_id'].nunique().sum(),
                'unique_lectures': course_data['lecture'].dropna().nunique(),
                'first_activity': course_data['datetime'].min(),
                'last_activity': course_data['datetime'].max(),
            }

            # Calculate time metrics
            span_duration = (stats['last_activity'] - stats['first_activity']).total_seconds() / 60
            stats['span_duration_minutes'] = round(span_duration, 2)

            # Session-based time per user (sum of all session times with timeout)
            session_times = []
            for user_id in course_data['User ID'].unique():
                user_course = course_data[course_data['User ID'] == user_id]
                user_time = self._calculate_user_session_time(user_course)
                session_times.append(user_time)

            stats['avg_session_time_per_user'] = round(np.mean(session_times), 2) if session_times else 0
            stats['total_session_time'] = round(sum(session_times), 2)

            # Engagement metrics
            stats['events_per_user'] = round(stats['total_events'] / stats['total_users'], 2)
            stats['sessions_per_user'] = round(stats['total_sessions'] / stats['total_users'], 2)
            stats['events_per_session'] = round(stats['total_events'] / stats['total_sessions'], 2)

            course_stats.append(stats)

        return pd.DataFrame(course_stats).sort_values('total_events', ascending=False)

    def get_course_user_breakdown(self, course_id: str = None) -> pd.DataFrame:
        """
        Get user-level breakdown for a specific course

        Args:
            course_id: Specific course ID, or None for all courses

        Returns:
            DataFrame with user metrics per course
        """
        if course_id:
            course_data = self.df[self.df['course'] == course_id]
        else:
            course_data = self.df[self.df['course'].notna()]

        user_stats = []

        for (course, user) in course_data.groupby(['course', 'User ID']).groups.keys():
            user_course_data = course_data[
                (course_data['course'] == course) &
                (course_data['User ID'] == user)
                ]

            # Time calculations
            first_event = user_course_data['datetime'].min()
            last_event = user_course_data['datetime'].max()
            span = (last_event - first_event).total_seconds() / 60

            # Session-based time calculation
            session_time = self._calculate_user_session_time(user_course_data)

            stats = {
                'course_id': course,
                'user_id': user,
                'total_events': len(user_course_data),
                'sessions': user_course_data['session_id'].nunique(),
                'lectures_accessed': user_course_data['lecture'].dropna().nunique(),
                'span_duration_minutes': round(span, 2),
                'session_time_minutes': round(session_time, 2),
                'first_activity': first_event,
                'last_activity': last_event,
            }

            # Event type breakdown
            event_counts = user_course_data['Event Name'].value_counts()
            stats['tab_changes'] = event_counts.get('tab_change', 0)
            stats['lecture_changes'] = event_counts.get('lecture_change', 0)
            stats['evaluations_started'] = event_counts.get('evaluation_start', 0)
            stats['evaluations_completed'] = event_counts.get('evaluation_complete', 0)
            stats['quizzes_started'] = event_counts.get('quiz_start', 0)
            stats['quizzes_completed'] = event_counts.get('quiz_complete', 0)

            user_stats.append(stats)

        return pd.DataFrame(user_stats).sort_values(['course_id', 'total_events'], ascending=[True, False])

    def get_course_engagement_metrics(self) -> pd.DataFrame:
        """
        Calculate engagement metrics per course

        Returns:
            DataFrame with detailed engagement metrics
        """
        metrics = []

        for course_id in self.df['course'].dropna().unique():
            course_data = self.df[self.df['course'] == course_id]

            metric = {
                'course_id': course_id,
                'total_users': course_data['User ID'].nunique(),
            }

            # Completion rates
            eval_started = course_data[course_data['Event Name'] == 'evaluation_start']['User ID'].nunique()
            eval_completed = course_data[course_data['Event Name'] == 'evaluation_complete']['User ID'].nunique()
            quiz_started = course_data[course_data['Event Name'] == 'quiz_start']['User ID'].nunique()
            quiz_completed = course_data[course_data['Event Name'] == 'quiz_complete']['User ID'].nunique()

            metric['evaluations_started'] = eval_started
            metric['evaluations_completed'] = eval_completed
            metric['evaluation_completion_rate'] = round(
                (eval_completed / eval_started * 100) if eval_started > 0 else 0, 2
            )

            metric['quizzes_started'] = quiz_started
            metric['quizzes_completed'] = quiz_completed
            metric['quiz_completion_rate'] = round(
                (quiz_completed / quiz_started * 100) if quiz_started > 0 else 0, 2
            )

            # Navigation metrics
            metric['total_tab_changes'] = len(course_data[course_data['Event Name'] == 'tab_change'])
            metric['total_lecture_changes'] = len(course_data[course_data['Event Name'] == 'lecture_change'])
            metric['avg_tab_changes_per_user'] = round(
                metric['total_tab_changes'] / metric['total_users'], 2
            )
            metric['avg_lecture_changes_per_user'] = round(
                metric['total_lecture_changes'] / metric['total_users'], 2
            )

            # Editing metrics
            edits_started = len(course_data[course_data['Event Name'] == 'start_editing'])
            edits_saved = len(course_data[course_data['Event Name'] == 'save_edit'])
            metric['edits_started'] = edits_started
            metric['edits_saved'] = edits_saved
            metric['edit_save_rate'] = round(
                (edits_saved / edits_started * 100) if edits_started > 0 else 0, 2
            )

            metrics.append(metric)

        return pd.DataFrame(metrics).sort_values('total_users', ascending=False)

    def get_course_content_usage(self, course_id: str = None) -> pd.DataFrame:
        """
        Analyze which lectures and tabs are most used in a course

        Args:
            course_id: Specific course ID, or None for all courses

        Returns:
            DataFrame with content usage statistics
        """
        if course_id:
            course_data = self.df[self.df['course'] == course_id]
        else:
            course_data = self.df[self.df['course'].notna()]

        content_stats = []

        for course in course_data['course'].unique():
            course_subset = course_data[course_data['course'] == course]

            # Lecture usage
            lecture_counts = course_subset['lecture'].value_counts()
            for lecture, count in lecture_counts.items():
                if pd.notna(lecture):
                    users = course_subset[course_subset['lecture'] == lecture]['User ID'].nunique()
                    content_stats.append({
                        'course_id': course,
                        'content_type': 'lecture',
                        'content_id': lecture,
                        'total_events': count,
                        'unique_users': users,
                        'events_per_user': round(count / users, 2)
                    })

            # Tab usage
            tab_changes = course_subset[course_subset['Event Name'] == 'tab_change']
            tab_counts = tab_changes['tab'].value_counts()
            for tab, count in tab_counts.items():
                if pd.notna(tab):
                    users = tab_changes[tab_changes['tab'] == tab]['User ID'].nunique()
                    content_stats.append({
                        'course_id': course,
                        'content_type': 'tab',
                        'content_id': tab,
                        'total_events': count,
                        'unique_users': users,
                        'events_per_user': round(count / users, 2)
                    })

        return pd.DataFrame(content_stats).sort_values(['course_id', 'total_events'], ascending=[True, False])

    def get_course_session_analysis(self, course_id: str = None) -> pd.DataFrame:
        """
        Analyze session patterns per course

        Args:
            course_id: Specific course ID, or None for all courses

        Returns:
            DataFrame with session-level metrics
        """
        if course_id:
            course_data = self.df[self.df['course'] == course_id]
        else:
            course_data = self.df[self.df['course'].notna()]

        session_stats = []

        for (course, user, session) in course_data.groupby(['course', 'User ID', 'session_id']).groups.keys():
            session_data = course_data[
                (course_data['course'] == course) &
                (course_data['User ID'] == user) &
                (course_data['session_id'] == session)
                ]

            first = session_data['datetime'].min()
            last = session_data['datetime'].max()
            duration = (last - first).total_seconds() / 60

            # Session time = duration + timeout
            session_time = duration + self.session_timeout

            session_stats.append({
                'course_id': course,
                'user_id': user,
                'session_number': int(session),
                'start_time': first,
                'end_time': last,
                'duration_minutes': round(duration, 2),
                'session_time_minutes': round(session_time, 2),
                'total_events': len(session_data),
                'lectures_accessed': session_data['lecture'].dropna().nunique(),
                'events_per_minute': round(len(session_data) / duration, 2) if duration > 0 else 0
            })

        return pd.DataFrame(session_stats).sort_values(['course_id', 'user_id', 'session_number'])

    def get_course_performance_metrics(self) -> pd.DataFrame:
        """
        Get performance metrics (scores, accuracy) per course

        Returns:
            DataFrame with performance statistics
        """
        perf_stats = []

        for course_id in self.df['course'].dropna().unique():
            course_data = self.df[self.df['course'] == course_id]

            stats = {'course_id': course_id}

            # Evaluation performance
            eval_complete = course_data[course_data['Event Name'] == 'evaluation_complete']
            if len(eval_complete) > 0:
                stats['evaluations_completed'] = len(eval_complete)
                stats['avg_score'] = eval_complete['score'].mean()
                stats['avg_questions_answered'] = eval_complete['answered_questions'].mean()
                stats['avg_total_questions'] = eval_complete['total_questions'].mean()
            else:
                stats['evaluations_completed'] = 0
                stats['avg_score'] = None
                stats['avg_questions_answered'] = None
                stats['avg_total_questions'] = None

            # Answer accuracy
            answers = course_data[course_data['Event Name'].isin([
                'evaluation_answer_click', 'quiz_answer_click'
            ])]
            if len(answers) > 0:
                correct = answers['is_correct'].sum()
                total = len(answers)
                stats['total_answers'] = total
                stats['correct_answers'] = correct
                stats['answer_accuracy'] = round(correct / total * 100, 2)
            else:
                stats['total_answers'] = 0
                stats['correct_answers'] = 0
                stats['answer_accuracy'] = None

            perf_stats.append(stats)

        return pd.DataFrame(perf_stats)

    def compare_courses(self) -> Dict:
        """
        Generate a comprehensive comparison of all courses

        Returns:
            Dictionary with comparison metrics
        """
        overview = self.get_course_overview()
        engagement = self.get_course_engagement_metrics()
        performance = self.get_course_performance_metrics()

        comparison = {
            'overview': overview.to_dict('records'),
            'engagement': engagement.to_dict('records'),
            'performance': performance.to_dict('records'),
            'rankings': {
                'most_users': overview.nlargest(5, 'total_users')[['course_id', 'total_users']].to_dict('records'),
                'most_engaged': overview.nlargest(5, 'avg_session_time_per_user')[
                    ['course_id', 'avg_session_time_per_user']].to_dict('records'),
                'most_events': overview.nlargest(5, 'total_events')[['course_id', 'total_events']].to_dict('records'),
                'best_completion': engagement.nlargest(5, 'evaluation_completion_rate')[
                    ['course_id', 'evaluation_completion_rate']].to_dict('records'),
            }
        }

        return comparison

    def export_course_reports(self, output_dir: str = './course_reports'):
        """
        Export detailed reports for each course

        Args:
            output_dir: Directory to save reports
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Export overview
        overview = self.get_course_overview()
        overview.to_csv(f'{output_dir}/course_overview.csv', index=False)
        print(f"Exported: {output_dir}/course_overview.csv")

        # Export engagement metrics
        engagement = self.get_course_engagement_metrics()
        engagement.to_csv(f'{output_dir}/course_engagement.csv', index=False)
        print(f"Exported: {output_dir}/course_engagement.csv")

        # Export performance metrics
        performance = self.get_course_performance_metrics()
        performance.to_csv(f'{output_dir}/course_performance.csv', index=False)
        print(f"Exported: {output_dir}/course_performance.csv")

        # Export user breakdown
        user_breakdown = self.get_course_user_breakdown()
        user_breakdown.to_csv(f'{output_dir}/course_user_breakdown.csv', index=False)
        print(f"Exported: {output_dir}/course_user_breakdown.csv")

        # Export content usage
        content_usage = self.get_course_content_usage()
        content_usage.to_csv(f'{output_dir}/course_content_usage.csv', index=False)
        print(f"Exported: {output_dir}/course_content_usage.csv")

        # Export session analysis
        sessions = self.get_course_session_analysis()
        sessions.to_csv(f'{output_dir}/course_sessions.csv', index=False)
        print(f"Exported: {output_dir}/course_sessions.csv")

        # Export comparison
        comparison = self.compare_courses()
        with open(f'{output_dir}/course_comparison.json', 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        print(f"Exported: {output_dir}/course_comparison.json")

        print(f"\nAll course reports exported to: {output_dir}/")

    def print_course_summary(self, course_id: str = None):
        """
        Print a formatted summary for a specific course or all courses

        Args:
            course_id: Specific course ID, or None for all courses
        """
        if course_id:
            courses = [course_id]
        else:
            courses = self.df['course'].dropna().unique()

        for course in courses:
            course_data = self.df[self.df['course'] == course]

            print("\n" + "=" * 80)
            print(f"COURSE: {course}")
            print("=" * 80)

            # Basic stats
            print(f"\nBasic Statistics:")
            print(f"  Users: {course_data['User ID'].nunique()}")
            print(f"  Total Events: {len(course_data)}")
            print(f"  Sessions: {course_data.groupby('User ID')['session_id'].nunique().sum()}")
            print(f"  Lectures: {course_data['lecture'].dropna().nunique()}")

            # Time metrics using session-based calculation
            session_times = []
            for user in course_data['User ID'].unique():
                user_data = course_data[course_data['User ID'] == user]
                user_time = self._calculate_user_session_time(user_data)
                session_times.append(user_time)

            print(f"\nTime Metrics:")
            print(f"  Avg Session Time/User: {np.mean(session_times):.1f} minutes")
            print(f"  Total Session Time: {sum(session_times):.1f} minutes")

            # Engagement
            print(f"\nEngagement:")
            print(f"  Tab Changes: {len(course_data[course_data['Event Name'] == 'tab_change'])}")
            print(f"  Lecture Changes: {len(course_data[course_data['Event Name'] == 'lecture_change'])}")

            # Assessments
            eval_started = len(course_data[course_data['Event Name'] == 'evaluation_start'])
            eval_completed = len(course_data[course_data['Event Name'] == 'evaluation_complete'])

            print(f"\nAssessments:")
            print(f"  Evaluations Started: {eval_started}")
            print(f"  Evaluations Completed: {eval_completed}")
            if eval_started > 0:
                print(f"  Completion Rate: {eval_completed / eval_started * 100:.1f}%")

            # Top content
            print(f"\nMost Accessed Lectures:")
            lecture_counts = course_data['lecture'].value_counts().head(5)
            for lecture, count in lecture_counts.items():
                if pd.notna(lecture):
                    print(f"  {lecture[:40]}... : {count} events")


def get_export_path(config: Dict, from_date: str, to_date: str) -> str:
    """Get the expected path to the export file"""
    output_dir = config.get('export', {}).get('output_dir')
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        filename = f"{from_date}_{to_date}_export.csv"
        return os.path.join(output_dir, filename)
    else:
        return config.get('export', {}).get('output_file', 'mixpanel_export.csv')


def run_export_if_needed(config: Dict, from_date: str, to_date: str, force: bool = False) -> bool:
    """Run export if file doesn't exist or force is True"""
    export_path = get_export_path(config, from_date, to_date)

    if os.path.exists(export_path) and not force:
        print(f"Export file exists: {export_path}")
        return True

    print(f"{'Forcing' if force else 'Running'} Mixpanel export...")
    try:
        cmd = ['python3', 'mixpanel_export.py', '--from', from_date, '--to', to_date]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("Export completed successfully")
            return True
        else:
            print(f"Export failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error running export: {e}")
        return False


def generate_simple_usage_report(df: pd.DataFrame, course_info: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate a simple usage report per course"""
    # Detect course column
    course_col = None
    for col in ['course', 'course_id', 'courseId', 'Course']:
        if col in df.columns:
            course_col = col
            break

    if not course_col:
        print("Warning: No course column found")
        return pd.DataFrame()

    # Detect user column
    user_col = 'distinct_id' if 'distinct_id' in df.columns else 'User ID'

    # Detect event column
    event_col = 'event' if 'event' in df.columns else 'Event Name'

    reports = []
    for course_id in df[course_col].dropna().unique():
        course_data = df[df[course_col] == course_id]

        report = {
            'course_id': course_id,
            'total_users': course_data[user_col].nunique() if user_col in course_data.columns else 0,
            'total_events': len(course_data),
            'first_activity': course_data['datetime'].min(),
            'last_activity': course_data['datetime'].max(),
            'date_span_days': (course_data['datetime'].max() - course_data['datetime'].min()).days,
        }

        if report['total_users'] > 0:
            report['events_per_user'] = round(report['total_events'] / report['total_users'], 2)

        # Enrich with course info if available
        if course_info is not None and 'course_id' in course_info.columns:
            match = course_info[course_info['course_id'] == str(course_id)]
            if len(match) > 0:
                for col in course_info.columns:
                    if col != 'course_id':
                        report[f'course_{col}'] = match.iloc[0][col]

        reports.append(report)

    return pd.DataFrame(reports).sort_values('total_events', ascending=False)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze Mixpanel course usage data and generate reports',
        epilog='Reads from config.yaml by default'
    )
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--from', dest='from_date', help='Override start date')
    parser.add_argument('--to', dest='to_date', help='Override end date')
    parser.add_argument('--force-export', action='store_true', help='Force re-export')
    parser.add_argument('--csv', help='Direct CSV file path (skip export)')
    parser.add_argument('--format', choices=['csv', 'json', 'html', 'pdf'],
                        default='html', help='Output format (default: html)')
    parser.add_argument('--split-by-institution', action='store_true',
                        help='Generate separate reports per institution (default: read from config)')
    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    # Get dates
    from_date = args.from_date or config.get('export', {}).get('from_date')
    to_date = args.to_date or config.get('export', {}).get('to_date')

    if not from_date or not to_date:
        print("Error: Dates not found in config or args")
        sys.exit(1)

    print(f"Analyzing period: {from_date} to {to_date}")

    # Load course info
    course_info = load_course_list(config)

    # Determine export file path
    if args.csv:
        export_path = args.csv
    else:
        # Run export if needed
        if not run_export_if_needed(config, from_date, to_date, args.force_export):
            print("Failed to get export data")
            sys.exit(1)
        export_path = get_export_path(config, from_date, to_date)

    # Load data
    print(f"Loading data from: {export_path}")
    try:
        df = pd.read_csv(export_path)
        if 'datetime' not in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
    except Exception as e:
        print(f"Error loading data: {e}")
        sys.exit(1)

    print(f"Loaded {len(df)} events")

    # Create analysis
    analysis = CourseAnalysis(df, course_info)

    # Get output directory
    output_dir = config.get('export', {}).get('output_dir')
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
    else:
        output_dir = '.'

    # Export based on format
    if args.format == 'csv':
        files = analysis.export_to_csv(output_dir, from_date, to_date)
        print(f"\n{len(files)} CSV files exported")
    elif args.format == 'json':
        json_path = analysis.export_to_json(output_dir, from_date, to_date)
        print(f"\nJSON exported to: {json_path}")
    elif args.format in ['html', 'pdf']:
        # Export to JSON first
        json_path = analysis.export_to_json(output_dir, from_date, to_date)

        # Create reporter and generate report
        analysis_data = {
            'metadata': {
                'from_date': from_date,
                'to_date': to_date,
                'generated_at': pd.Timestamp.now().isoformat(),
                'total_events': len(df),
                'total_courses': analysis.df[analysis.course_col].nunique() if analysis.course_col else 0,
            },
            'course_usage_summary': analysis.get_course_usage_summary().to_dict('records'),
            'event_type_distribution': analysis.get_event_type_distribution().to_dict('records'),
        }

        reporter = CourseReporter(analysis_data)

        # Determine split_by_institution setting
        # Priority: CLI arg > config
        # Supports: False (unified), True (split), "both" (unified + split)
        if args.split_by_institution:
            split_by_institution = True
        else:
            split_by_institution = config.get('report', {}).get('split_by_institution', False)

        if args.format == 'html':
            html_path = os.path.join(output_dir, f"{from_date}_{to_date}_report.html")
            reporter.generate_html_report(html_path, split_by_institution=split_by_institution)
        else:  # pdf
            pdf_path = os.path.join(output_dir, f"{from_date}_{to_date}_report.pdf")
            reporter.generate_pdf_report(pdf_path)

        # Print console summary
        reporter.print_console_summary()
    else:
        # Default: just print summary
        stats = analysis.get_summary_stats()
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Total Events: {stats['total_events']}")
        if 'total_courses' in stats:
            print(f"Total Courses: {stats['total_courses']}")
        if 'total_users' in stats:
            print(f"Total Users: {stats['total_users']}")


if __name__ == '__main__':
    main()