#!/usr/bin/env python3
"""
Generate Smart Snapshot Report from existing teacher report outputs

This script takes deep.txt and story.txt (and optionally output.txt) to create
a smart report highlighting the most important insights and recommendations.

Usage:
    python generate_smart_snapshot.py [output_dir]

    If no output_dir is provided, uses the videos_dir/output from config.yaml
"""

import os
import sys
import yaml
from pathlib import Path

from teacher_side.snapshot_generator import SnapshotGenerator
from teacher_side.teacher_utils import get_output_dir


def generate_smart_snapshot(output_dir: str):
    """
    Generate smart snapshot report from existing output files.

    Args:
        output_dir: Directory containing output.txt, deep.txt, story.txt, and optionally active.txt

    Raises:
        FileNotFoundError: If required files are missing
    """
    # Check for required files
    output_txt_path = os.path.join(output_dir, "output.txt")
    deep_txt_path = os.path.join(output_dir, "deep.txt")
    story_txt_path = os.path.join(output_dir, "story.txt")
    active_txt_path = os.path.join(output_dir, "active.txt")

    missing_files = []
    if not os.path.exists(output_txt_path):
        missing_files.append("output.txt")
    if not os.path.exists(deep_txt_path):
        missing_files.append("deep.txt")
    if not os.path.exists(story_txt_path):
        missing_files.append("story.txt")

    if missing_files:
        raise FileNotFoundError(
            f"Missing required files in {output_dir}: {', '.join(missing_files)}\n"
            f"Please ensure you have generated:\n"
            f"  - output.txt (basic report)\n"
            f"  - deep.txt (deep pedagogical analysis)\n"
            f"  - story.txt (storytelling analysis)"
        )

    print(f"🔍 Found all required files in: {output_dir}")
    print(f"   ✓ {output_txt_path}")
    print(f"   ✓ {deep_txt_path}")
    print(f"   ✓ {story_txt_path}")

    # Check for optional active.txt
    if os.path.exists(active_txt_path):
        print(f"   ✓ {active_txt_path} (active learning analysis)")
    else:
        print(f"   ⊘ {active_txt_path} (optional - not found)")
        active_txt_path = None
    print()

    # Create snapshot generator
    print("📊 Creating smart snapshot report...")
    generator = SnapshotGenerator(story_txt_path, deep_txt_path, output_txt_path, active_txt_path)

    # Generate minimalist snapshot (smart report with key insights)
    print("   Generating minimalist snapshot (key insights)...")
    minimalist_markdown = generator.generate_minimalist_markdown()
    minimalist_path = Path(os.path.join(output_dir, 'teaching_snapshot.md'))
    minimalist_path.write_text(minimalist_markdown, encoding='utf-8')
    print(f"   ✅ Saved: {minimalist_path}")

    # Generate expanded snapshot (detailed report)
    print("   Generating expanded snapshot (full details)...")
    expanded_markdown = generator.generate_expanded_markdown()
    expanded_path = Path(os.path.join(output_dir, 'teaching_snapshot_expanded.md'))
    expanded_path.write_text(expanded_markdown, encoding='utf-8')
    print(f"   ✅ Saved: {expanded_path}")

    print()
    print("=" * 80)
    print("✅ Smart snapshot generation completed successfully!")
    print("=" * 80)
    print(f"📁 Reports saved to: {output_dir}")
    print()
    print("📄 Generated files:")
    print(f"   • teaching_snapshot.md - Smart report with most important insights")
    print(f"   • teaching_snapshot_expanded.md - Detailed comprehensive report")
    print()


def main():
    """Main entry point for the script."""
    # Get output directory from command line or config
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        # Load from config.yaml
        config_path = "./config.yaml"
        if not os.path.exists(config_path):
            print(f"Error: {config_path} not found")
            print()
            print("Usage: python generate_smart_snapshot.py [output_dir]")
            print()
            print("Either provide an output directory or ensure config.yaml exists")
            sys.exit(1)

        config = yaml.safe_load(open(config_path))
        output_dir = get_output_dir(config)
        print(f"Using output directory from config.yaml: {output_dir}")
        print()

    # Generate the smart snapshot
    try:
        generate_smart_snapshot(output_dir)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
