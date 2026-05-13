"""
SessionBuilder: groups per-user events into sessions.

A new session starts when inactivity exceeds idle_timeout_minutes.
Session duration = (last_event - first_event) + estimated_last_event_time,
capped at max_session_duration_minutes.
Logic extracted from SiteAnalytics/course_analysis.py.
"""
import numpy as np
import pandas as pd


class SessionBuilder:
    def __init__(self, config: dict):
        cfg = config['session']
        self.idle_timeout = cfg['idle_timeout_minutes']
        self.max_duration = cfg['max_session_duration_minutes']
        self.min_duration = cfg['meaningful_session_min_duration_minutes']
        self.min_events = cfg['meaningful_session_min_events']
        self.min_active = cfg['meaningful_session_min_active_events']

    def build(self, events: pd.DataFrame) -> pd.DataFrame:
        """
        Args:
            events: DataFrame with columns [email, datetime, is_active_event, lecture, ...]

        Returns:
            sessions DataFrame, one row per session.
        """
        resolved = events.dropna(subset=['email'])
        sessions = []

        for email, user_events in resolved.groupby('email'):
            user_events = user_events.sort_values('datetime').reset_index(drop=True)

            time_diffs = user_events['datetime'].diff().dt.total_seconds() / 60
            session_breaks = (time_diffs > self.idle_timeout) | time_diffs.isna()
            user_events = user_events.copy()
            user_events['_session_num'] = session_breaks.cumsum()

            for sess_num, sess in user_events.groupby('_session_num'):
                duration = self._calc_duration(sess)
                is_meaningful = (
                    duration >= self.min_duration
                    and len(sess) >= self.min_events
                    and int(sess['is_active_event'].sum()) >= self.min_active
                )
                sessions.append({
                    'email': email,
                    'session_id': f'{email}__{sess_num}',
                    'start_time': sess['datetime'].iloc[0],
                    'end_time': sess['datetime'].iloc[-1],
                    'duration_minutes': duration,
                    'event_count': len(sess),
                    'active_event_count': int(sess['is_active_event'].sum()),
                    'unique_lectures': sess['lecture'].nunique(),
                    'week': sess['datetime'].iloc[0].to_period('W'),
                    'is_meaningful': is_meaningful,
                })

        df = pd.DataFrame(sessions)
        if len(df) > 0:
            meaningful_n = df['is_meaningful'].sum()
            print(f"Sessions built: {len(df):,} total, {meaningful_n:,} meaningful "
                  f"({meaningful_n/len(df)*100:.1f}%)")
        return df

    def _calc_duration(self, sess: pd.DataFrame) -> float:
        if len(sess) == 1:
            return 0.0
        raw = (sess['datetime'].iloc[-1] - sess['datetime'].iloc[0]).total_seconds() / 60
        gaps = sess['datetime'].diff().dt.total_seconds().dropna()
        last_event_estimate = min(float(np.median(gaps)) / 60, 10.0)
        return min(raw + last_event_estimate, self.max_duration)
