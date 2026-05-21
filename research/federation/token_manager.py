#!/usr/bin/env python3
"""
Aaron Owl — Token Manager
==========================
Generates a unique URL for each teacher and prints the Streamlit secrets snippet to add.

Usage:
    python federation/token_manager.py --course bio
    python federation/token_manager.py --course bio --app-url https://aaron-owl.streamlit.app

Output:
    - Teacher URL  (share this with the teacher)
    - TOML snippet (paste into Streamlit dashboard → Settings → Secrets)

Run this AFTER pipeline.py has produced the federation CSV for the course.
"""
import argparse
import base64
import secrets
import sys
from pathlib import Path

import yaml


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).parent.parent / p
    with open(p) as f:
        return yaml.safe_load(f)


def _fed_dir(config: dict, course_key: str) -> Path:
    course_cfg = config["courses"][course_key]
    return Path(course_cfg.get("federation_dir") or config["data"]["federation_dir"])


def generate_token(config: dict, course_key: str, app_url: str) -> str:
    course_cfg = config["courses"][course_key]
    course_name = course_cfg["name"]
    fed_dir = _fed_dir(config, course_key)

    features_path = fed_dir / f"student_features_{course_key}_federation.csv"
    if not features_path.exists():
        print(f"ERROR: Federation CSV not found: {features_path}")
        print("Run pipeline.py first, then re-run this script.")
        sys.exit(1)

    usage_path = fed_dir / f"usage_report_{course_key}.html"

    features_b64 = base64.b64encode(features_path.read_bytes()).decode("ascii")
    token = f"{course_key}_{secrets.token_hex(6)}"
    url = f"{app_url.rstrip('/')}/?token={token}"

    print(f"\n{'=' * 62}")
    print(f"  Token generated for: {course_name}")
    print(f"{'=' * 62}")
    print(f"\n  Teacher URL (send this link):\n  {url}\n")
    print("  ─ Streamlit secrets snippet ─────────────────────────────────")
    print(f"  Paste into: Streamlit dashboard → your app → Settings → Secrets\n")
    print(f"[tokens.{token}]")
    print(f'course_name = "{course_name}"')
    print(f'features_b64 = "{features_b64}"')

    if usage_path.exists():
        usage_b64 = base64.b64encode(usage_path.read_bytes()).decode("ascii")
        print(f'usage_b64 = "{usage_b64}"')
        usage_kb = usage_path.stat().st_size // 1024
    else:
        print(f"# usage_b64 not included — {usage_path} not found")
        usage_b64 = None
        usage_kb = 0

    print()
    print("  ─────────────────────────────────────────────────────────────")
    print(f"  Features: {len(features_b64) // 1024:.0f} KB base64 "
          f"({features_path.stat().st_size // 1024} KB original)")
    if usage_b64:
        print(f"  Usage HTML: {len(usage_b64) // 1024:.0f} KB base64 ({usage_kb} KB original)")
    print()

    return token


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a teacher web-analysis token")
    parser.add_argument("--course", required=True, help="Course key from config.yaml")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--app-url",
        default="https://your-app.streamlit.app",
        help="Base URL of the deployed Streamlit app",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.course not in config["courses"]:
        print(f"Unknown course: {args.course!r}. Available: {list(config['courses'].keys())}")
        sys.exit(1)

    generate_token(config, args.course, args.app_url)


if __name__ == "__main__":
    main()
