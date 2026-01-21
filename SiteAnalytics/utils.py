#!/usr/bin/env python3
"""
Utility functions for Site Analytics
"""

import os
import re
import yaml
import pandas as pd
from pathlib import Path
from typing import Optional, Dict


def load_config(config_path: str = 'config.yaml') -> Dict:
    """
    Load configuration from YAML file

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary containing configuration
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    return config


def read_env_from_bashrc(var_name: str, bashrc_path: str = None) -> Optional[str]:
    """
    Read an environment variable from ~/.bashrc file

    Args:
        var_name: Name of the environment variable to read (e.g., 'MIXPANEL_SECRET')
        bashrc_path: Path to bashrc file (default: ~/.bashrc)

    Returns:
        Value of the environment variable, or None if not found
    """
    # Default to ~/.bashrc if no path provided
    if bashrc_path is None:
        bashrc_path = os.path.expanduser('~/.bashrc')

    bashrc_file = Path(bashrc_path)

    if not bashrc_file.exists():
        return None

    try:
        with open(bashrc_file, 'r') as f:
            content = f.read()

        # Look for export statements like: export VARNAME="value" or export VARNAME=value
        # Also support just VARNAME="value" or VARNAME=value
        patterns = [
            rf'^export\s+{var_name}=["\']?([^"\'\n]+)["\']?',  # export VAR="value"
            rf'^{var_name}=["\']?([^"\'\n]+)["\']?',            # VAR="value"
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                value = match.group(1).strip()
                # Remove surrounding quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                return value

        return None

    except Exception as e:
        print(f"Warning: Could not read {bashrc_path}: {e}")
        return None


def get_mixpanel_secret(config: dict = None) -> Optional[str]:
    """
    Get Mixpanel secret from multiple sources in order of precedence:
    1. Environment variable MIXPANEL_SECRET
    2. ~/.bashrc file
    3. Config dictionary (if provided)

    Args:
        config: Optional configuration dictionary

    Returns:
        Mixpanel API secret, or None if not found
    """
    # First check if it's already in environment
    secret = os.environ.get('MIXPANEL_SECRET')
    if secret:
        return secret

    # Then try to read from ~/.bashrc
    secret = read_env_from_bashrc('MIXPANEL_SECRET')
    if secret:
        return secret

    # Finally check config if provided
    if config:
        secret = config.get('mixpanel', {}).get('api_secret')
        if secret and secret != 'YOUR_API_SECRET_HERE':
            return secret

    return None


def load_course_list(config: dict) -> Optional[pd.DataFrame]:
    """
    Load course list from CSV file specified in config

    Args:
        config: Configuration dictionary containing info.course_list path

    Returns:
        DataFrame with course information, or None if not found/error
    """
    if not config:
        print("Warning: No config provided to load_course_list")
        return None

    course_list_path = config.get('info', {}).get('course_list')
    if not course_list_path:
        print("Warning: course_list path not found in config")
        return None

    course_list_path = os.path.expanduser(course_list_path)
    print(f"Attempting to load course list from: {course_list_path}")

    if not os.path.exists(course_list_path):
        print(f"Warning: Course list file not found: {course_list_path}")
        return None

    try:
        df = pd.read_csv(course_list_path)
        print(f"Loaded {len(df)} courses from {course_list_path}")
        print(f"Course CSV columns (original): {list(df.columns)}")

        # Normalize column names to lowercase and replace spaces with underscores
        df.columns = df.columns.str.lower().str.replace(' ', '_')
        print(f"Course CSV columns (normalized): {list(df.columns)}")

        if len(df) > 0:
            print(f"First course sample: {df.iloc[0].to_dict()}")
        return df
    except Exception as e:
        print(f"Error loading course list: {e}")
        return None