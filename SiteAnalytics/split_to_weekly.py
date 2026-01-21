#!/usr/bin/env python3
"""
Split existing semester CSV into weekly files
This is a one-time utility to convert a large semester file into weekly chunks
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple


def calculate_week_ranges(start_date: str, end_date: str) -> List[Tuple[str, str]]:
    """
    Calculate weekly date ranges from semester start to end date
    Weeks run from Saturday to Saturday (7 days)

    Args:
        start_date: Semester start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of (from_date, to_date) tuples for each week
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    weeks = []

    # Find the first Saturday on or after start_date
    # weekday(): Monday=0, Sunday=6, so Saturday=5
    days_until_saturday = (5 - start.weekday()) % 7
    current_week_start = start + timedelta(days=days_until_saturday)

    # If the first Saturday is after end date, use start date for first week
    if current_week_start > end:
        weeks.append((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
        return weeks

    # Include partial week from start_date to first Saturday if needed
    if current_week_start > start:
        weeks.append((
            start.strftime('%Y-%m-%d'),
            (current_week_start - timedelta(days=1)).strftime('%Y-%m-%d')
        ))

    while current_week_start <= end:
        # Week runs from Saturday to next Friday (7 days)
        week_end = current_week_start + timedelta(days=6)

        # Don't go past the end date
        if week_end > end:
            week_end = end

        weeks.append((
            current_week_start.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        ))

        # Move to next Saturday
        current_week_start = week_end + timedelta(days=1)

    return weeks


def split_semester_to_weekly(semester_file: str, output_dir: str, start_date: str, end_date: str):
    """
    Split a large semester CSV file into weekly chunks

    Args:
        semester_file: Path to the large semester CSV file
        output_dir: Directory to save weekly files
        start_date: Semester start date (YYYY-MM-DD)
        end_date: Semester end date (YYYY-MM-DD)
    """
    print(f"\n{'='*80}")
    print(f"SPLITTING SEMESTER FILE INTO WEEKLY CHUNKS")
    print(f"{'='*80}")
    print(f"Input file: {semester_file}")
    print(f"Output directory: {output_dir}")
    print(f"Period: {start_date} to {end_date}")
    print(f"{'='*80}\n")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Load the big file
    print("Loading semester file...")
    df = pd.read_csv(semester_file)
    print(f"Loaded {len(df)} events")

    # Ensure datetime column exists
    if 'datetime' not in df.columns:
        if 'time' in df.columns:
            print("Converting 'time' column to 'datetime'...")
            df['datetime'] = pd.to_datetime(df['time'], unit='s')
        else:
            print("Error: No 'time' or 'datetime' column found")
            return
    else:
        df['datetime'] = pd.to_datetime(df['datetime'])

    # Calculate week ranges
    weeks = calculate_week_ranges(start_date, end_date)
    print(f"Calculated {len(weeks)} weeks\n")

    # Split into weekly files
    total_events = 0
    for week_num, (from_date, to_date) in enumerate(weeks, 1):
        # Convert dates to datetime
        from_dt = pd.to_datetime(from_date)
        to_dt = pd.to_datetime(to_date) + timedelta(days=1)  # Include entire end day

        # Filter events for this week
        week_df = df[(df['datetime'] >= from_dt) & (df['datetime'] < to_dt)]

        if len(week_df) == 0:
            print(f"Week {week_num:02d}: {from_date} to {to_date} - No events, skipping")
            continue

        # Save to file (no week number in filename - date range is unique identifier)
        week_file = os.path.join(output_dir, f"week_{from_date}_{to_date}.csv")
        week_df.to_csv(week_file, index=False)

        total_events += len(week_df)
        print(f"Week {week_num:02d}: {from_date} to {to_date} - Saved {len(week_df)} events")

    print(f"\n{'='*80}")
    print(f"Split complete!")
    print(f"Total events written: {total_events}")
    print(f"Original file events: {len(df)}")
    print(f"Weekly files saved to: {output_dir}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Split semester CSV into weekly files')
    parser.add_argument('--semester-file', required=True, help='Path to semester CSV file')
    parser.add_argument('--output-dir', required=True, help='Directory to save weekly files')
    parser.add_argument('--start-date', required=True, help='Semester start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', required=True, help='Semester end date (YYYY-MM-DD)')

    args = parser.parse_args()

    split_semester_to_weekly(
        args.semester_file,
        args.output_dir,
        args.start_date,
        args.end_date
    )