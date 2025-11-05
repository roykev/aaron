#!/usr/bin/env python3
"""
Generate Smart Insights using LLM analysis

This script uses an LLM to analyze deep.txt and story.txt outputs and identify
the MOST IMPORTANT insights and recommendations for teaching improvement.

Usage:
    python generate_smart_insights.py [output_dir]

    If no output_dir is provided, uses the videos_dir/output from config.yaml
"""

import os
import sys
import yaml
import json
from pathlib import Path

from teacher_side.teacher_report_smart_insights import TeacherReportSmartInsights
from teacher_side.teacher_utils import get_output_dir
from utils.utils import get_logger


def generate_smart_insights_markdown(insights_json: str, output_path: str):
    """
    Convert smart insights JSON to a beautiful markdown report.

    Args:
        insights_json: JSON string with smart insights
        output_path: Path to save the markdown file
    """
    try:
        # Parse JSON
        insights = json.loads(insights_json)
    except json.JSONDecodeError as e:
        print(f"⚠️  Warning: Could not parse JSON: {e}")
        print("Saving raw output instead...")
        Path(output_path).write_text(insights_json, encoding='utf-8')
        return

    # Build markdown
    md = []
    md.append("# 🦉 AaronOwl Smart Insights Report")
    md.append("")
    md.append("*AI-powered positive analysis celebrating strengths and identifying growth opportunities*")
    md.append("")
    md.append("---")
    md.append("")

    # Overall Assessment
    if "overall_assessment" in insights:
        md.append("## 🌟 Overall Assessment")
        md.append("")
        md.append(insights["overall_assessment"])
        md.append("")

    # Key Message
    if "key_message" in insights:
        md.append("## 💡 Key Message")
        md.append("")
        md.append(f"**{insights['key_message']}**")
        md.append("")

    md.append("---")
    md.append("")

    # Top Strength
    if "top_strength" in insights:
        top = insights["top_strength"]
        md.append("## ⭐ Outstanding Strength")
        md.append("")
        md.append(f"### {top.get('dimension', 'Unknown')}")
        md.append("")
        md.append(f"**What's exceptional:** {top.get('description', '')}")
        md.append("")
        if 'evidence' in top and top['evidence']:
            md.append(f"*Evidence:* {top['evidence']}")
            md.append("")

    md.append("---")
    md.append("")

    # Preserve (Strengths)
    if "preserve" in insights and insights["preserve"]:
        md.append("## 🎯 Continue These Successful Practices")
        md.append("")
        md.append("*These strengths are making a real difference for students:*")
        md.append("")

        for i, item in enumerate(insights["preserve"], 1):
            dimension = item.get('dimension', 'Unknown')
            strength = item.get('strength', '')
            why = item.get('why_important', '')
            evidence = item.get('evidence', '')

            md.append(f"### {i}. {dimension}")
            md.append("")
            md.append(f"**Success:** {strength}")
            md.append("")
            if why:
                md.append(f"**Impact:** {why}")
                md.append("")
            if evidence:
                md.append(f"*Evidence:* {evidence}")
                md.append("")

    md.append("---")
    md.append("")

    # Growth Opportunities (formerly "Improve")
    # Support both old "improve" field and new "growth_opportunities" field
    growth_items = insights.get("growth_opportunities", insights.get("improve", []))
    if growth_items:
        md.append("## 🌱 Opportunities for Growth")
        md.append("")
        md.append("*Areas where small enhancements can create meaningful impact:*")
        md.append("")

        for i, item in enumerate(growth_items, 1):
            dimension = item.get('dimension', 'Unknown')

            # Handle both old and new field names
            opportunity = item.get('opportunity', item.get('weakness', ''))
            benefit = item.get('potential_benefit', item.get('impact', ''))
            suggestion = item.get('suggestion', item.get('recommendation', ''))
            evidence = item.get('evidence', '')

            md.append(f"### {i}. {dimension}")
            md.append("")
            md.append(f"**Opportunity:** {opportunity}")
            md.append("")
            if benefit:
                md.append(f"**Potential benefit:** {benefit}")
                md.append("")
            if suggestion:
                md.append(f"**How to build on this:** {suggestion}")
                md.append("")
            if evidence:
                md.append(f"*Context:* {evidence}")
                md.append("")

    md.append("---")
    md.append("")

    # Priority Actions
    if "priority_actions" in insights and insights["priority_actions"]:
        md.append("## 📋 Suggested Actions for Next Class")
        md.append("")
        md.append("*Try these approaches in your next session:*")
        md.append("")

        for i, action in enumerate(insights["priority_actions"], 1):
            act = action.get('action', '')
            outcome = action.get('expected_outcome', '')
            difficulty = action.get('difficulty', 'medium')

            # Difficulty emoji
            diff_emoji = {
                'easy': '🟢',
                'medium': '🟡',
                'hard': '🔴'
            }.get(difficulty.lower(), '⚪')

            md.append(f"{i}. {diff_emoji} **{act}**")
            md.append("")
            if outcome:
                md.append(f"   *Potential outcome:* {outcome}")
                md.append("")

    md.append("---")
    md.append("")

    # Long-term Opportunity (support both old and new field names)
    long_term = insights.get("long_term_opportunity", insights.get("long_term_focus"))
    if long_term:
        md.append("## 🚀 Long-term Growth Opportunity")
        md.append("")
        md.append(long_term)
        md.append("")

    # Footer
    md.append("---")
    md.append("")
    from datetime import datetime
    md.append(f"*Generated by AaronOwl Smart Insights Analyzer | {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    # Write to file
    Path(output_path).write_text("\n".join(md), encoding='utf-8')


def generate_smart_insights(output_dir: str, config: dict):
    """
    Generate smart insights from existing output files using LLM.

    Args:
        output_dir: Directory containing deep.txt and story.txt
        config: Configuration dictionary

    Raises:
        FileNotFoundError: If required files are missing
    """
    logger = get_logger(__name__, config)

    # Check for required files
    deep_txt_path = os.path.join(output_dir, "deep.txt")
    story_txt_path = os.path.join(output_dir, "story.txt")

    missing_files = []
    if not os.path.exists(deep_txt_path):
        missing_files.append("deep.txt")
    if not os.path.exists(story_txt_path):
        missing_files.append("story.txt")

    if missing_files:
        raise FileNotFoundError(
            f"Missing required files in {output_dir}: {', '.join(missing_files)}\n"
            f"Please ensure you have generated:\n"
            f"  - deep.txt (deep pedagogical analysis)\n"
            f"  - story.txt (storytelling analysis)"
        )

    print(f"🔍 Found required files in: {output_dir}")
    print(f"   ✓ {deep_txt_path}")
    print(f"   ✓ {story_txt_path}")
    print()

    # Get language from config
    language = config.get("language", "English")

    # Create smart insights generator
    print("🤖 Calling LLM to analyze and synthesize insights...")
    print(f"   Language: {language}")
    print(f"   Model: {config.get('llm', {}).get('model', 'default')}")
    print()

    llmproxy = TeacherReportSmartInsights(config)
    llmproxy.prepare_content(output_dir, lan=language)

    # Call API
    output = llmproxy.call_api()

    # Save JSON output
    json_path = os.path.join(output_dir, "smart_insights.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"   ✅ Saved JSON: {json_path}")

    # Generate markdown report
    md_path = os.path.join(output_dir, "smart_insights.md")
    generate_smart_insights_markdown(output, md_path)
    print(f"   ✅ Saved Markdown: {md_path}")

    print()
    print("=" * 80)
    print("✅ Smart insights generation completed successfully!")
    print("=" * 80)
    print(f"📁 Reports saved to: {output_dir}")
    print()
    print("📄 Generated files:")
    print(f"   • smart_insights.json - Raw LLM output")
    print(f"   • smart_insights.md - Formatted insights report")
    print()


def main():
    """Main entry point for the script."""
    # Get output directory from command line or config
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
        # Load config for LLM settings
        config_path = "./config.yaml"
        if not os.path.exists(config_path):
            print(f"Error: {config_path} not found")
            print("Config file is required for LLM API settings")
            sys.exit(1)
        config = yaml.safe_load(open(config_path))
    else:
        # Load from config.yaml
        config_path = "./config.yaml"
        if not os.path.exists(config_path):
            print(f"Error: {config_path} not found")
            print()
            print("Usage: python generate_smart_insights.py [output_dir]")
            print()
            print("Either provide an output directory or ensure config.yaml exists")
            sys.exit(1)

        config = yaml.safe_load(open(config_path))
        output_dir = get_output_dir(config)
        print(f"Using output directory from config.yaml: {output_dir}")
        print()

    # Generate the smart insights
    try:
        generate_smart_insights(output_dir, config)
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
