"""
EventLoader: reads weekly Mixpanel CSV files, filters by course, returns clean events DataFrame.
"""
import glob
from pathlib import Path
from typing import Optional

import pandas as pd

KEEP_COLS = [
    'event', 'datetime', 'distinct_id', 'course', 'lecture',
    'tab', 'concept', 'score', 'correct_answers', 'total_questions',
    'answered_questions', 'query', 'results_count', 'is_correct', 'action',
]


class EventLoader:
    def __init__(self, config: dict):
        self.weekly_dir = Path(config['data']['weekly_events_dir'])
        self.active_event_types = set(config['events']['active_event_types'])
        self.active_tab_changes = set(config['events']['active_tab_changes'])
        self.feature_tabs = config['events']['feature_tabs']

    def load(self, course_id: str) -> pd.DataFrame:
        files = sorted(glob.glob(str(self.weekly_dir / 'week_*.csv')))
        if not files:
            raise FileNotFoundError(f"No weekly CSV files found in {self.weekly_dir}")

        chunks = []
        for f in files:
            df = pd.read_csv(f, low_memory=False, usecols=lambda c: c in KEEP_COLS)
            course_events = df[df['course'] == course_id]
            if len(course_events) > 0:
                chunks.append(course_events)

        if not chunks:
            raise ValueError(f"No events found for course_id={course_id}")

        events = pd.concat(chunks, ignore_index=True)
        events['datetime'] = pd.to_datetime(events['datetime'])
        events = events.sort_values('datetime').reset_index(drop=True)
        events['is_active_event'] = self._mark_active(events)
        events['week'] = events['datetime'].dt.to_period('W')

        print(f"Loaded {len(events):,} events for course {course_id} "
              f"({events['distinct_id'].nunique()} users, "
              f"{events['week'].nunique()} weeks)")
        return events

    def _mark_active(self, events: pd.DataFrame) -> pd.Series:
        direct_active = events['event'].isin(self.active_event_types)
        active_tab_nav = (
            (events['event'] == 'tab_change') &
            events['tab'].isin(self.active_tab_changes)
        )
        return direct_active | active_tab_nav
