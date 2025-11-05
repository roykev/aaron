#!/usr/bin/env python3
"""Generate markdown reports from story.txt and deep.txt"""

import os
import yaml
from teacher_side.teacher_utils import generate_story_report, generate_deep_report

# Load config
config_path = "./config.yaml"
config = yaml.safe_load(open(config_path))

dir_path = config["videos_dir"]

print(f"Generating markdown reports for: {dir_path}")

# Check if input files exist
story_file = os.path.join(dir_path, "story.txt")
deep_file = os.path.join(dir_path, "deep.txt")

if os.path.exists(story_file):
    print(f"✓ Found story.txt")
    try:
        generate_story_report(dir_path)
        print(f"✓ Generated story.md")
    except Exception as e:
        print(f"✗ Error generating story.md: {e}")
else:
    print(f"✗ story.txt not found")

if os.path.exists(deep_file):
    print(f"✓ Found deep.txt")
    try:
        generate_deep_report(dir_path)
        print(f"✓ Generated deep.md")
    except Exception as e:
        print(f"✗ Error generating deep.md: {e}")
else:
    print(f"✗ deep.txt not found")

print("\nDone!")