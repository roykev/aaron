"""
IdentityResolver: maps Mixpanel distinct_id → email using the user export CSV.
"""
from pathlib import Path

import pandas as pd


class IdentityResolver:
    def __init__(self, config: dict):
        self.user_export_path = Path(config['data']['user_export_csv'])
        self._mapping: dict[str, str] = {}

    def load(self) -> None:
        df = pd.read_csv(self.user_export_path)
        # Mixpanel export uses $distinct_id and $email column names
        id_col = '$distinct_id' if '$distinct_id' in df.columns else 'distinct_id'
        email_col = '$email' if '$email' in df.columns else 'email'

        valid = df[[id_col, email_col]].dropna(subset=[email_col])
        self._mapping = dict(zip(valid[id_col], valid[email_col].str.lower().str.strip()))
        print(f"Identity resolver loaded: {len(self._mapping):,} distinct_id → email mappings")

    def resolve(self, events: pd.DataFrame) -> pd.DataFrame:
        if not self._mapping:
            self.load()
        events = events.copy()
        events['email'] = events['distinct_id'].map(self._mapping)
        resolved = events['email'].notna().sum()
        total = len(events)
        print(f"Identity resolution: {resolved:,}/{total:,} events resolved "
              f"({resolved/total*100:.1f}%)")
        return events
