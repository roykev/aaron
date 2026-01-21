#!/usr/bin/env python3
"""
Quick script to run ONLY the new reports (A, B, C, D)
without extracting data from Mixpanel or generating old reports
"""

from semester_analyzer import run_new_reports
from utils import load_config

if __name__ == '__main__':
    # Load configuration
    config = load_config('config.yaml')

    # Run only new reports
    run_new_reports(config)