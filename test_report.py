#!/usr/bin/env python3
"""Test script to generate HTML report from deep.txt and story.txt"""

import os
from teacher_side.generate_report import generate_teacher_report_html

# Use the directory from config.yaml
dir_name = "/home/roy/FS/Dropbox/WORK/Ideas/aaron/tal/"
date = "20/10/2025"  # Format: DD/MM/YYYY

print(f"Generating report for: {dir_name}")
print(f"Date: {date}")

# Check if files exist
files_to_check = ['story.txt', 'deep.txt', 'title.csv', 'sections.csv']
for file in files_to_check:
    path = os.path.join(dir_name, file)
    exists = "✓" if os.path.exists(path) else "✗"
    print(f"{exists} {file}")

print("\nGenerating HTML report...")
try:
    html_report = generate_teacher_report_html(dir_name, date)

    # Save the report
    output_html = os.path.join(dir_name, "teacher_report.html")
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_report)

    print(f"✓ HTML report saved to: {output_html}")

    # Print statistics
    print(f"\nReport statistics:")
    print(f"  - Total length: {len(html_report)} characters")
    print(f"  - Has Summary section: {'Class Summary' in html_report}")
    print(f"  - Has Storytelling Analysis: {'Storytelling Analysis' in html_report}")
    print(f"  - Has Deep Analysis: {'Deep Pedagogical Analysis' in html_report}")
    print(f"  - Has Strengths/Weaknesses: {'Strengths' in html_report and 'Weaknesses' in html_report}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()