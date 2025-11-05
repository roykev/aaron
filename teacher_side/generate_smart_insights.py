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

    # Build markdown with beautiful, expandable sections
    md = []

    # Header with gradient-style decorative elements
    md.append("# 🦉 AaronOwl Smart Insights")
    md.append("")
    md.append("<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>")
    md.append("<h3 style='margin: 0; color: white;'>✨ AI-Powered Teaching Excellence Analysis</h3>")
    md.append("<p style='margin: 10px 0 0 0; opacity: 0.9;'>Celebrating your strengths and identifying exciting growth opportunities</p>")
    md.append("</div>")
    md.append("")

    # Key Message Box (always visible - most important)
    if "key_message" in insights:
        md.append("<div style='background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 5px;'>")
        md.append(f"<strong>💡 Key Message:</strong> {insights['key_message']}")
        md.append("</div>")
        md.append("")

    # Overall Assessment (expandable)
    if "overall_assessment" in insights:
        md.append("<details>")
        md.append("<summary><h2 style='display: inline;'>🌟 Overall Assessment</h2></summary>")
        md.append("")
        md.append(f"<div style='padding: 15px; background: #fefce8; border-radius: 5px; margin-top: 10px;'>")
        md.append(insights["overall_assessment"])
        md.append("</div>")
        md.append("")
        md.append("</details>")
        md.append("")

    md.append("---")
    md.append("")

    # Top Strength (prominent, always visible)
    if "top_strength" in insights:
        top = insights["top_strength"]
        md.append("## ⭐ Outstanding Strength")
        md.append("")
        md.append(f"<div style='background: #ecfdf5; border: 2px solid #10b981; padding: 20px; border-radius: 10px; margin: 15px 0;'>")
        md.append(f"<h3 style='margin-top: 0; color: #059669;'>{top.get('dimension', 'Unknown')}</h3>")
        md.append(f"<p><strong>What's exceptional:</strong> {top.get('description', '')}</p>")
        if 'evidence' in top and top['evidence']:
            md.append("<details>")
            md.append("<summary><em>📝 View evidence</em></summary>")
            md.append(f"<p style='margin-top: 10px; padding: 10px; background: white; border-radius: 5px;'>{top['evidence']}</p>")
            md.append("</details>")
        md.append("</div>")
        md.append("")

    md.append("---")
    md.append("")

    # Preserve (Strengths) - Minimal with expandable details
    if "preserve" in insights and insights["preserve"]:
        md.append("## 🎯 Continue These Successful Practices")
        md.append("")
        md.append("<p style='color: #059669; font-style: italic;'>These strengths are making a real difference for students</p>")
        md.append("")

        for i, item in enumerate(insights["preserve"], 1):
            dimension = item.get('dimension', 'Unknown')
            strength = item.get('strength', '')
            why = item.get('why_important', '')
            evidence = item.get('evidence', '')

            # Create short summary (first 100 chars)
            summary = strength[:100] + '...' if len(strength) > 100 else strength

            md.append(f"<details style='margin: 10px 0;'>")
            md.append(f"<summary style='cursor: pointer; padding: 12px; background: #f0fdf4; border-radius: 8px; border-left: 4px solid #22c55e;'>")
            md.append(f"<strong>{i}. {dimension}:</strong> {summary}")
            md.append("</summary>")
            md.append("")
            md.append(f"<div style='padding: 15px; background: #f9fafb; border-radius: 5px; margin-top: 10px;'>")
            md.append(f"<p><strong>✅ Success:</strong> {strength}</p>")
            if why:
                md.append(f"<p><strong>💫 Impact:</strong> {why}</p>")
            if evidence:
                md.append(f"<p style='font-style: italic; color: #6b7280;'><strong>📝 Evidence:</strong> {evidence}</p>")
            md.append("</div>")
            md.append("")
            md.append("</details>")
            md.append("")

    md.append("---")
    md.append("")

    # Growth Opportunities - Minimal with expandable details
    growth_items = insights.get("growth_opportunities", insights.get("improve", []))
    if growth_items:
        md.append("## 🌱 Opportunities for Growth")
        md.append("")
        md.append("<p style='color: #0891b2; font-style: italic;'>Areas where small enhancements can create meaningful impact</p>")
        md.append("")

        for i, item in enumerate(growth_items, 1):
            dimension = item.get('dimension', 'Unknown')

            # Handle both old and new field names
            opportunity = item.get('opportunity', item.get('weakness', ''))
            benefit = item.get('potential_benefit', item.get('impact', ''))
            suggestion = item.get('suggestion', item.get('recommendation', ''))
            evidence = item.get('evidence', '')

            # Create short summary (first 100 chars)
            summary = opportunity[:100] + '...' if len(opportunity) > 100 else opportunity

            md.append(f"<details style='margin: 10px 0;'>")
            md.append(f"<summary style='cursor: pointer; padding: 12px; background: #f0f9ff; border-radius: 8px; border-left: 4px solid #0ea5e9;'>")
            md.append(f"<strong>{i}. {dimension}:</strong> {summary}")
            md.append("</summary>")
            md.append("")
            md.append(f"<div style='padding: 15px; background: #f9fafb; border-radius: 5px; margin-top: 10px;'>")
            md.append(f"<p><strong>🎯 Opportunity:</strong> {opportunity}</p>")
            if benefit:
                md.append(f"<p><strong>✨ Potential benefit:</strong> {benefit}</p>")
            if suggestion:
                md.append(f"<p><strong>💡 How to build on this:</strong> {suggestion}</p>")
            if evidence:
                md.append(f"<p style='font-style: italic; color: #6b7280;'><strong>📋 Context:</strong> {evidence}</p>")
            md.append("</div>")
            md.append("")
            md.append("</details>")
            md.append("")

    md.append("---")
    md.append("")

    # Priority Actions - Clean list with expandable outcomes
    if "priority_actions" in insights and insights["priority_actions"]:
        md.append("## 📋 Suggested Actions for Next Class")
        md.append("")
        md.append("<p style='color: #7c3aed; font-style: italic;'>Try these approaches in your next session</p>")
        md.append("")

        for i, action in enumerate(insights["priority_actions"], 1):
            act = action.get('action', '')
            outcome = action.get('expected_outcome', '')
            difficulty = action.get('difficulty', 'medium')

            # Difficulty badge
            diff_config = {
                'easy': ('🟢', '#10b981', 'Easy'),
                'medium': ('🟡', '#f59e0b', 'Medium'),
                'hard': ('🔴', '#ef4444', 'Challenging')
            }
            emoji, color, label = diff_config.get(difficulty.lower(), ('⚪', '#6b7280', 'Unknown'))

            md.append(f"<details style='margin: 10px 0;'>")
            md.append(f"<summary style='cursor: pointer; padding: 12px; background: #faf5ff; border-radius: 8px; border-left: 4px solid #a855f7;'>")
            md.append(f"{emoji} <strong>{i}. {act}</strong> ")
            md.append(f"<span style='font-size: 0.85em; color: {color}; background: white; padding: 2px 8px; border-radius: 12px; margin-left: 8px;'>{label}</span>")
            md.append("</summary>")
            md.append("")
            if outcome:
                md.append(f"<div style='padding: 15px; background: #f9fafb; border-radius: 5px; margin-top: 10px;'>")
                md.append(f"<p><strong>🎯 Potential outcome:</strong> {outcome}</p>")
                md.append("</div>")
            md.append("")
            md.append("</details>")
            md.append("")

    md.append("---")
    md.append("")

    # Long-term Opportunity - Highlighted box
    long_term = insights.get("long_term_opportunity", insights.get("long_term_focus"))
    if long_term:
        md.append("## 🚀 Long-term Growth Opportunity")
        md.append("")
        md.append(f"<div style='background: #fef3c7; border: 2px solid #f59e0b; padding: 20px; border-radius: 10px; margin: 15px 0;'>")
        md.append(f"<p style='margin: 0; font-size: 1.05em;'>{long_term}</p>")
        md.append("</div>")
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
