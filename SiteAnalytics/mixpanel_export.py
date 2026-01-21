#!/usr/bin/env python3
"""
Mixpanel Event Export Script
Exports all events between specified dates using Mixpanel's Export API
Bypasses the 100-entry limit in the web interface
"""

import requests
import json
import base64
import gzip
import time
import os
from datetime import datetime, timedelta
import pandas as pd
import argparse
from typing import List, Dict, Set
import sys
import yaml
from pathlib import Path
from utils import get_mixpanel_secret, load_config

class MixpanelExporter:
    """
    Exports events from Mixpanel using their Raw Data Export API
    """

    def __init__(self, api_secret: str, project_id: str = None,
                 blacklist_user_ids: Set[str] = None,
                 blacklist_course_ids: Set[str] = None):
        """
        Initialize the Mixpanel exporter

        Args:
            api_secret: Your Mixpanel API Secret (from Project Settings)
            project_id: Your Mixpanel Project ID (optional, for newer API)
            blacklist_user_ids: Set of user IDs to exclude from export
            blacklist_course_ids: Set of course IDs to exclude from export
        """
        self.api_secret = api_secret
        self.project_id = project_id
        self.base_url = "https://data.mixpanel.com/api/2.0/export"

        # Initialize blacklists
        self.blacklist_user_ids = blacklist_user_ids or set()
        self.blacklist_course_ids = blacklist_course_ids or set()

        # Create authentication header
        auth_string = f"{api_secret}:"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Accept-Encoding': 'gzip'
        }

    def _is_event_blacklisted(self, event: Dict) -> bool:
        """
        Check if an event should be filtered out based on blacklists

        Args:
            event: Event dictionary from Mixpanel

        Returns:
            True if event should be excluded, False otherwise
        """
        properties = event.get('properties', {})

        # Check user_id blacklist (check both distinct_id and user_id)
        user_id = properties.get('distinct_id') or properties.get('user_id')
        if user_id and str(user_id) in self.blacklist_user_ids:
            return True

        # Check course_id blacklist
        course_id = properties.get('course_id')
        if course_id and str(course_id) in self.blacklist_course_ids:
            return True

        return False

    def filter_blacklisted_events(self, events: List[Dict]) -> List[Dict]:
        """
        Filter out blacklisted events

        Args:
            events: List of events from Mixpanel

        Returns:
            Filtered list of events
        """
        if not self.blacklist_user_ids and not self.blacklist_course_ids:
            return events

        original_count = len(events)
        filtered_events = [e for e in events if not self._is_event_blacklisted(e)]
        filtered_count = original_count - len(filtered_events)

        if filtered_count > 0:
            print(f"Filtered out {filtered_count} events based on blacklist")

        return filtered_events

    def export_events(
            self,
            from_date: str,
            to_date: str,
            event: str = None,
            where: str = None,
            output_format: str = 'json'
    ) -> List[Dict]:
        """
        Export events from Mixpanel

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            event: Optional - specific event name to filter
            where: Optional - filter expression (e.g., 'properties["$browser"] == "Chrome"')
            output_format: 'json' or 'csv'

        Returns:
            List of event dictionaries
        """

        # Validate dates
        try:
            datetime.strptime(from_date, '%Y-%m-%d')
            datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in YYYY-MM-DD format")

        # Build parameters
        params = {
            'from_date': from_date,
            'to_date': to_date
        }

        if event:
            params['event'] = json.dumps([event])

        if where:
            params['where'] = where

        print(f"Exporting events from {from_date} to {to_date}...")
        print(f"API URL: {self.base_url}")
        print(f"Parameters: {params}")

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=300  # 5 minute timeout for large exports
            )

            response.raise_for_status()

            # Parse the response - Mixpanel returns newline-delimited JSON
            events = []
            content = response.text

            for line in content.strip().split('\n'):
                if line:
                    try:
                        event_data = json.loads(line)
                        events.append(event_data)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Could not parse line: {line[:100]}...")
                        continue

            print(f"Successfully exported {len(events)} events")

            # Apply blacklist filtering
            events = self.filter_blacklisted_events(events)

            return events

        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise

    def export_to_csv(
            self,
            from_date: str,
            to_date: str,
            output_file: str = 'mixpanel_export.csv',
            event: str = None
    ):
        """
        Export events and save to CSV file

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            output_file: Output CSV filename
            event: Optional - specific event name to filter
        """
        events = self.export_events(from_date, to_date, event=event)

        if not events:
            print("No events found for the specified date range")
            return

        # Flatten the event structure for CSV
        flattened_events = []
        for event in events:
            flat_event = {
                'event': event.get('event'),
                'time': event.get('properties', {}).get('time'),
                'distinct_id': event.get('properties', {}).get('distinct_id'),
            }

            # Add all other properties
            if 'properties' in event:
                for key, value in event['properties'].items():
                    if key not in ['time', 'distinct_id']:
                        # Handle nested objects/arrays by converting to JSON string
                        if isinstance(value, (dict, list)):
                            flat_event[key] = json.dumps(value)
                        else:
                            flat_event[key] = value

            flattened_events.append(flat_event)

        # Convert to DataFrame and save
        df = pd.DataFrame(flattened_events)

        # Convert timestamp to readable format if present
        if 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='s')

        df.to_csv(output_file, index=False)
        print(f"Exported {len(df)} events to {output_file}")

        return df

    def export_by_chunks(
            self,
            from_date: str,
            to_date: str,
            output_file: str = 'mixpanel_export.csv',
            chunk_days: int = 7,
            event: str = None
    ):
        """
        Export events in chunks to handle large date ranges
        Useful for very large datasets

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            output_file: Output CSV filename
            chunk_days: Number of days per chunk
            event: Optional - specific event name to filter
        """
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')

        all_events = []
        current = start

        while current <= end:
            chunk_end = min(current + timedelta(days=chunk_days - 1), end)

            print(f"\nFetching chunk: {current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")

            chunk_events = self.export_events(
                current.strftime('%Y-%m-%d'),
                chunk_end.strftime('%Y-%m-%d'),
                event=event
            )

            all_events.extend(chunk_events)
            print(f"Total events so far: {len(all_events)}")

            current = chunk_end + timedelta(days=1)

            # Be nice to the API
            time.sleep(1)

        print(f"\nTotal events collected: {len(all_events)}")

        # Save to CSV
        if all_events:
            flattened_events = []
            for event in all_events:
                flat_event = {
                    'event': event.get('event'),
                    'time': event.get('properties', {}).get('time'),
                    'distinct_id': event.get('properties', {}).get('distinct_id'),
                }

                if 'properties' in event:
                    for key, value in event['properties'].items():
                        if key not in ['time', 'distinct_id']:
                            if isinstance(value, (dict, list)):
                                flat_event[key] = json.dumps(value)
                            else:
                                flat_event[key] = value

                flattened_events.append(flat_event)

            df = pd.DataFrame(flattened_events)

            if 'time' in df.columns:
                df['datetime'] = pd.to_datetime(df['time'], unit='s')

            df.to_csv(output_file, index=False)
            print(f"Exported {len(df)} events to {output_file}")

            return df

        return None


def main():
    parser = argparse.ArgumentParser(
        description='Export events from Mixpanel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using config file (recommended)
  python mixpanel_export.py --config config.yaml

  # Using command-line arguments
  python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25

  # Export specific event type
  python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25 --event "Login"

  # Export large date range in chunks
  python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-01-01 --to 2025-12-31 --chunk-days 7

  # Specify output file
  python mixpanel_export.py --secret YOUR_API_SECRET --from 2025-12-01 --to 2025-12-25 -o my_export.csv
        """
    )

    parser.add_argument(
        '--config',
        help='Path to YAML configuration file (default: config.yaml)',
        default=None
    )

    parser.add_argument(
        '--secret',
        help='Mixpanel API Secret (found in Project Settings > Project Details)'
    )

    parser.add_argument(
        '--from',
        dest='from_date',
        help='Start date in YYYY-MM-DD format'
    )

    parser.add_argument(
        '--to',
        dest='to_date',
        help='End date in YYYY-MM-DD format'
    )

    parser.add_argument(
        '--event',
        help='Filter by specific event name (optional)'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output CSV filename (default: mixpanel_export.csv)'
    )

    parser.add_argument(
        '--chunk-days',
        type=int,
        help='Export in chunks of N days (useful for large date ranges)'
    )

    parser.add_argument(
        '--project-id',
        help='Mixpanel Project ID (optional)'
    )

    args = parser.parse_args()

    # Load configuration from YAML file if specified or if no CLI args provided
    config = None
    if args.config or (not args.secret and not args.from_date):
        config_path = args.config or 'config.yaml'
        try:
            config = load_config(config_path)
            print(f"Loaded configuration from {config_path}")
        except FileNotFoundError as e:
            if args.config:
                # User explicitly specified a config file
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            else:
                # No config file and no CLI args
                print("Error: Either provide --config or specify --secret, --from, and --to arguments", file=sys.stderr)
                sys.exit(1)

    # Determine values from config or CLI args (CLI args take precedence)
    # For API secret, check: CLI args > env var > ~/.bashrc > config file
    if args.secret:
        api_secret = args.secret
    else:
        api_secret = get_mixpanel_secret(config)
        if api_secret:
            print("Using MIXPANEL_SECRET from environment/bashrc")

    project_id = args.project_id or (config.get('mixpanel', {}).get('project_id') if config else None)
    from_date = args.from_date or (config.get('export', {}).get('from_date') if config else None)
    to_date = args.to_date or (config.get('export', {}).get('to_date') if config else None)
    chunk_days = args.chunk_days or (config.get('export', {}).get('chunk_days') if config else None)
    event = args.event or (config.get('export', {}).get('event') if config else None)

    # Validate required parameters
    if not api_secret:
        print("Error: API secret is required (use --secret, set MIXPANEL_SECRET in ~/.bashrc, or config file)", file=sys.stderr)
        sys.exit(1)
    if not from_date or not to_date:
        print("Error: Date range is required (use --from/--to or config file)", file=sys.stderr)
        sys.exit(1)

    # Handle output file and directory
    output_dir = config.get('export', {}).get('output_dir') if config else None

    if args.output:
        # CLI arg takes precedence - use as-is
        output_file = args.output
    elif output_dir:
        # Use output_dir from config and generate filename from dates
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{from_date}_{to_date}_export.csv"
        output_file = os.path.join(output_dir, filename)
    elif config and config.get('export', {}).get('output_file'):
        # Use output_file from config
        output_file = config.get('export', {}).get('output_file')
    else:
        # Default filename
        output_file = 'mixpanel_export.csv'

    # Load blacklists from config
    blacklist_user_ids = set()
    blacklist_course_ids = set()
    if config:
        blacklist_config = config.get('blacklist', {})
        if blacklist_config.get('user_ids'):
            blacklist_user_ids = set(str(uid) for uid in blacklist_config['user_ids'])
        if blacklist_config.get('course_ids'):
            blacklist_course_ids = set(str(cid) for cid in blacklist_config['course_ids'])

        if blacklist_user_ids:
            print(f"Blacklisting {len(blacklist_user_ids)} user IDs")
        if blacklist_course_ids:
            print(f"Blacklisting {len(blacklist_course_ids)} course IDs")

    # Create exporter
    exporter = MixpanelExporter(
        api_secret,
        project_id,
        blacklist_user_ids=blacklist_user_ids,
        blacklist_course_ids=blacklist_course_ids
    )

    try:
        if chunk_days:
            # Export in chunks
            df = exporter.export_by_chunks(
                from_date,
                to_date,
                output_file,
                chunk_days,
                event
            )
        else:
            # Single export
            df = exporter.export_to_csv(
                from_date,
                to_date,
                output_file,
                event
            )

        if df is not None:
            print("\n" + "=" * 60)
            print("Export Summary:")
            print("=" * 60)
            print(f"Total events: {len(df)}")
            print(f"Date range: {from_date} to {to_date}")
            if 'event' in df.columns:
                print(f"\nEvent types:")
                print(df['event'].value_counts())
            print(f"\nOutput file: {output_file}")
            print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()