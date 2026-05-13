"""
StudentFeatureBuilder: builds one row per student with all usage + academic features.
"""
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


class StudentFeatureBuilder:
    def __init__(self, config: dict, course_key: str):
        self.course_cfg = config['courses'][course_key]
        self.feature_tabs = config['events']['feature_tabs']

    def build(
        self,
        events: pd.DataFrame,
        sessions: pd.DataFrame,
        eval_df: Optional[pd.DataFrame],
        quiz_df: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        students = sorted(events.dropna(subset=['email'])['email'].unique())
        course_weeks = events['week'].nunique()
        total_lectures = self._count_total_lectures(eval_df, quiz_df, events)

        rows = []
        for email in students:
            row = {'email': email, 'course_id': self.course_cfg['course_id']}
            row.update(self._usage_features(email, events, course_weeks))
            row.update(self._session_features(email, sessions))
            row.update(self._content_features(email, events, total_lectures))
            row.update(self._diversity_features(email, events))
            row.update(self._eval_features(email, eval_df, total_lectures))
            row.update(self._quiz_features(email, quiz_df, total_lectures))
            rows.append(row)

        df = pd.DataFrame(rows).set_index('email')
        df['total_lectures_in_course'] = total_lectures
        df['course_total_weeks'] = course_weeks
        print(f"Feature table built: {len(df)} students × {len(df.columns)} features")
        return df

    # ── usage ────────────────────────────────────────────────────────────────

    def _usage_features(self, email: str, events: pd.DataFrame, course_weeks: int) -> dict:
        ue = events[events['email'] == email]
        active_weeks = ue['week'].nunique()
        return {
            'total_events': len(ue),
            'total_active_events': int(ue['is_active_event'].sum()),
            'active_days': ue['datetime'].dt.date.nunique(),
            'active_weeks': active_weeks,
            'active_weeks_ratio': active_weeks / course_weeks if course_weeks > 0 else 0,
            'longest_streak_weeks': self._longest_streak(ue['week']),
            # granular active event counts
            'quiz_starts': int((ue['event'] == 'quiz_start').sum()),
            'quiz_completes': int((ue['event'] == 'quiz_complete').sum()),
            'eval_starts': int((ue['event'] == 'evaluation_start').sum()),
            'eval_completes': int((ue['event'] == 'evaluation_complete').sum()),
            'quiz_answer_clicks': int((ue['event'] == 'quiz_answer_click').sum()),
            'eval_answer_clicks': int((ue['event'] == 'evaluation_answer_click').sum()),
            'concept_selects': int((ue['event'] == 'concept_select').sum()),
            'lecture_changes': int((ue['event'] == 'lecture_change').sum()),
            'logins': int((ue['event'] == 'Login').sum()),
        }

    def _longest_streak(self, weeks: pd.Series) -> int:
        if weeks.empty:
            return 0
        sorted_weeks = sorted(set(weeks))
        max_streak = streak = 1
        for i in range(1, len(sorted_weeks)):
            if (sorted_weeks[i] - sorted_weeks[i - 1]).n == 1:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 1
        return max_streak

    # ── sessions ─────────────────────────────────────────────────────────────

    def _session_features(self, email: str, sessions: pd.DataFrame) -> dict:
        if len(sessions) == 0:
            return self._empty_session_features()
        us = sessions[sessions['email'] == email]
        if us.empty:
            return self._empty_session_features()
        meaningful = us['is_meaningful'].sum()
        total = len(us)
        return {
            'sessions_count': total,
            'meaningful_sessions_count': int(meaningful),
            'meaningful_sessions_ratio': meaningful / total if total > 0 else 0,
            'total_time_minutes': round(us['duration_minutes'].sum(), 2),
            'avg_session_duration_minutes': round(us['duration_minutes'].mean(), 2),
            'median_session_duration_minutes': round(us['duration_minutes'].median(), 2),
            'avg_events_per_session': round(us['event_count'].mean(), 2),
            'avg_active_events_per_session': round(us['active_event_count'].mean(), 2),
        }

    def _empty_session_features(self) -> dict:
        return {k: 0 for k in [
            'sessions_count', 'meaningful_sessions_count', 'meaningful_sessions_ratio',
            'total_time_minutes', 'avg_session_duration_minutes',
            'median_session_duration_minutes', 'avg_events_per_session',
            'avg_active_events_per_session',
        ]}

    # ── content ───────────────────────────────────────────────────────────────

    def _content_features(self, email: str, events: pd.DataFrame, total_lectures: int) -> dict:
        ue = events[events['email'] == email]
        unique_lectures = ue['lecture'].dropna().nunique()
        return {
            'unique_lectures_viewed': unique_lectures,
            'lecture_coverage_pct': unique_lectures / total_lectures * 100 if total_lectures > 0 else 0,
        }

    # ── feature diversity ─────────────────────────────────────────────────────

    def _diversity_features(self, email: str, events: pd.DataFrame) -> dict:
        ue = events[events['email'] == email]
        tabs_used = set(ue['tab'].dropna().unique())
        result = {f'used_{t}': int(t in tabs_used) for t in self.feature_tabs}
        result['feature_diversity_count'] = sum(result.values())
        return result

    # ── eval ─────────────────────────────────────────────────────────────────

    def _eval_features(self, email: str, eval_df: Optional[pd.DataFrame], total_lectures: int) -> dict:
        empty = {
            'eval_attempts': 0, 'eval_avg_score': np.nan,
            'eval_max_score': np.nan, 'eval_submission_rate': 0,
            'eval_improvement': np.nan, 'eval_score_std': np.nan,
        }
        if eval_df is None or eval_df.empty:
            return empty
        se = eval_df[eval_df['email'] == email]
        if se.empty:
            return empty
        scores = se['score'].dropna()
        lectures_attempted = se['lecture_id'].nunique()
        improvement = float(scores.iloc[-1] - scores.iloc[0]) if len(scores) >= 2 else np.nan
        return {
            'eval_attempts': len(se),
            'eval_avg_score': round(float(scores.mean()), 2),
            'eval_max_score': round(float(scores.max()), 2),
            'eval_submission_rate': lectures_attempted / total_lectures * 100 if total_lectures > 0 else 0,
            'eval_improvement': round(improvement, 2) if not np.isnan(improvement) else np.nan,
            'eval_score_std': round(float(scores.std()), 2) if len(scores) >= 2 else np.nan,
        }

    # ── quiz ──────────────────────────────────────────────────────────────────

    def _quiz_features(self, email: str, quiz_df: Optional[pd.DataFrame], total_lectures: int) -> dict:
        empty = {
            'quiz_attempts': 0, 'quiz_avg_score': np.nan,
            'quiz_max_score': np.nan, 'quiz_submission_rate': 0,
        }
        if quiz_df is None or quiz_df.empty:
            return empty
        sq = quiz_df[quiz_df['email'] == email]
        if sq.empty:
            return empty
        scores = sq['score'].dropna()
        lectures_attempted = sq['lecture_id'].nunique()
        return {
            'quiz_attempts': len(sq),
            'quiz_avg_score': round(float(scores.mean()), 2),
            'quiz_max_score': round(float(scores.max()), 2),
            'quiz_submission_rate': lectures_attempted / total_lectures * 100 if total_lectures > 0 else 0,
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _count_total_lectures(self, eval_df, quiz_df, events) -> int:
        # Union of lecture IDs from eval/quiz CSVs and Mixpanel events.
        # Using only eval/quiz underestimates when some lectures have no assessment.
        lecture_ids = set()
        if eval_df is not None and 'lecture_id' in eval_df.columns:
            lecture_ids |= set(eval_df['lecture_id'].dropna())
        if quiz_df is not None and 'lecture_id' in quiz_df.columns:
            lecture_ids |= set(quiz_df['lecture_id'].dropna())
        event_lecture_ids = set(events['lecture'].dropna().unique())
        lecture_ids |= event_lecture_ids
        return len(lecture_ids)


def load_academic_csv(path: str, sheet: str = None) -> Optional[pd.DataFrame]:
    """Load eval or quiz data from CSV or Excel (.xlsx), normalize column names."""
    p = Path(path)
    if not p.exists():
        print(f"Warning: academic file not found: {path}")
        return None
    if p.suffix.lower() in ('.xlsx', '.xls'):
        df = pd.read_excel(p, sheet_name=sheet)
    else:
        df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    if 'name.1' in df.columns:
        df = df.rename(columns={'name.1': 'lecture_name'})
    df['email'] = df['email'].str.lower().str.strip()
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df['time'] = pd.to_datetime(df['time'], utc=True, errors='coerce')
    df = df.sort_values('time').reset_index(drop=True)
    return df
