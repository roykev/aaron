#!/usr/bin/env python3
"""
AaronOwl Teacher Report Pipeline
Main orchestration script that runs the complete teacher report generation pipeline
based on flags in config.yaml
"""

import os
import time
import yaml
from pathlib import Path

from teacher_side.teacher_report import TeacherReport
from teacher_side.teacher_report_deep import TeacherReportDeep
from teacher_side.teacher_report_storytelling import TeacherReportStoryTelling
from teacher_side.teacher_minimal_snapshot_report import SnapshotGenerator
from teacher_side.teacher_report_smart_insights import TeacherReportSmartInsights
from teacher_side.teacher_utils import get_output_dir, generate_report, generate_story_report, generate_deep_report
from teacher_side.generate_smart_insights import generate_smart_insights_markdown
from utils.utils import get_logger


def run_teacher_pipeline(config_path="./config.yaml"):
    """
    Run the complete teacher report pipeline based on config flags.

    Args:
        config_path: Path to the configuration YAML file
    """
    # Load configuration
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Get configuration settings
    teacher_config = config.get("teacher_reports", {})
    generate_basic = teacher_config.get("generate_basic", False)
    generate_deep = teacher_config.get("generate_deep", False)
    generate_story = teacher_config.get("generate_story", False)
    generate_markdown = teacher_config.get("generate_markdown", False)
    generate_smart_insights = teacher_config.get("generate_smart_insights", False)

    # Get language and course settings
    language = config.get("language", "English")
    course_name = config.get("course_name", "Unknown Course")
    class_level = config.get("class_level", "Unknown Level")

    # Get output directory
    output_dir = get_output_dir(config)

    logger.info("=" * 80)
    logger.info("AaronOwl Teacher Report Pipeline Started")
    logger.info("=" * 80)
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Language: {language}")
    logger.info(f"Course: {course_name}")
    logger.info(f"Level: {class_level}")
    logger.info(f"Flags: basic={generate_basic}, deep={generate_deep}, story={generate_story}, markdown={generate_markdown}, smart_insights={generate_smart_insights}")
    logger.info("=" * 80)

    total_start = time.time()

    # Step 1: Generate basic report (output.txt)
    if generate_basic:
        logger.info("Step 1/5: Generating basic teacher report (output.txt)...")
        step_start = time.time()

        llmproxy = TeacherReport(config)
        llmproxy.prepare_content(lan=language)
        output = llmproxy.call_api()

        output_file = os.path.join(output_dir, "output.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)

        logger.info(f"✅ Basic report saved to: {output_file} ({time.time() - step_start:.2f}s)")
    else:
        logger.info("Step 1/5: Skipping basic report generation (generate_basic=false)")

    # Step 2: Generate deep analysis report (deep.txt)
    if generate_deep:
        logger.info("Step 2/5: Generating deep analysis report (deep.txt)...")
        step_start = time.time()

        llmproxy = TeacherReportDeep(config)
        llmproxy.course_name = course_name
        llmproxy.class_level = class_level
        llmproxy.prepare_content(lan=language)
        output = llmproxy.call_api()

        deep_file = os.path.join(output_dir, "deep.txt")
        with open(deep_file, "w", encoding="utf-8") as f:
            f.write(output)

        logger.info(f"✅ Deep analysis saved to: {deep_file} ({time.time() - step_start:.2f}s)")
    else:
        logger.info("Step 2/5: Skipping deep analysis generation (generate_deep=false)")

    # Step 3: Generate storytelling analysis report (story.txt)
    if generate_story:
        logger.info("Step 3/5: Generating storytelling analysis report (story.txt)...")
        step_start = time.time()

        llmproxy = TeacherReportStoryTelling(config)
        llmproxy.course_name = course_name
        llmproxy.class_level = class_level
        llmproxy.prepare_content(lan=language)
        output = llmproxy.call_api()

        story_file = os.path.join(output_dir, "story.txt")
        with open(story_file, "w", encoding="utf-8") as f:
            f.write(output)

        logger.info(f"✅ Storytelling analysis saved to: {story_file} ({time.time() - step_start:.2f}s)")
    else:
        logger.info("Step 3/5: Skipping storytelling analysis generation (generate_story=false)")

    # Step 4: Generate LLM-based smart insights (most important findings)
    if generate_smart_insights:
        logger.info("Step 4/5: Generating AI-powered smart insights...")
        step_start = time.time()

        deep_txt_path = os.path.join(output_dir, "deep.txt")
        story_txt_path = os.path.join(output_dir, "story.txt")

        if os.path.exists(deep_txt_path) and os.path.exists(story_txt_path):
            logger.info("  Calling LLM to analyze and synthesize most important insights...")

            llmproxy = TeacherReportSmartInsights(config)
            llmproxy.prepare_content(output_dir, lan=language)
            output = llmproxy.call_api()

            # Save JSON output
            insights_json_path = os.path.join(output_dir, "smart_insights.json")
            with open(insights_json_path, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info(f"  ✅ Smart insights JSON saved to: {insights_json_path}")

            # Generate markdown report
            insights_md_path = os.path.join(output_dir, "smart_insights.md")
            generate_smart_insights_markdown(output, insights_md_path)
            logger.info(f"  ✅ Smart insights markdown saved to: {insights_md_path}")

            logger.info(f"✅ Smart insights generation completed ({time.time() - step_start:.2f}s)")
        else:
            missing = []
            if not os.path.exists(deep_txt_path):
                missing.append("deep.txt")
            if not os.path.exists(story_txt_path):
                missing.append("story.txt")
            logger.warning(f"  ⚠️  Cannot generate smart insights - missing files: {', '.join(missing)}")
    else:
        logger.info("Step 4/5: Skipping AI smart insights generation (generate_smart_insights=false)")

    # Step 5: Generate markdown reports and mechanical snapshot
    if generate_markdown:
        logger.info("Step 5/5: Generating markdown reports and snapshot...")
        step_start = time.time()

        # Check which files exist
        output_txt_path = os.path.join(output_dir, "output.txt")
        deep_txt_path = os.path.join(output_dir, "deep.txt")
        story_txt_path = os.path.join(output_dir, "story.txt")

        # Generate individual markdown reports if source files exist
        if os.path.exists(output_txt_path):
            logger.info("  Generating output.md from output.txt...")
            generate_report(output_dir)

        if os.path.exists(deep_txt_path):
            logger.info("  Generating deep.md from deep.txt...")
            generate_deep_report(output_dir)

        if os.path.exists(story_txt_path):
            logger.info("  Generating story.md from story.txt...")
            generate_story_report(output_dir)

        # Generate smart snapshot report if we have deep.txt and story.txt
        if os.path.exists(deep_txt_path) and os.path.exists(story_txt_path) and os.path.exists(output_txt_path):
            logger.info("  Generating smart snapshot report with most important insights...")

            # Create snapshot generator
            generator = SnapshotGenerator(story_txt_path, deep_txt_path, output_txt_path)

            # Generate minimalist snapshot (smart report with key insights)
            minimalist_markdown = generator.generate_minimalist_markdown()
            minimalist_path = Path(os.path.join(output_dir, 'teaching_snapshot.md'))
            minimalist_path.write_text(minimalist_markdown, encoding='utf-8')
            logger.info(f"  ✅ Smart snapshot saved to: {minimalist_path}")

            # Generate expanded snapshot (detailed report)
            expanded_markdown = generator.generate_expanded_markdown()
            expanded_path = Path(os.path.join(output_dir, 'teaching_snapshot_expanded.md'))
            expanded_path.write_text(expanded_markdown, encoding='utf-8')
            logger.info(f"  ✅ Expanded snapshot saved to: {expanded_path}")
        else:
            missing = []
            if not os.path.exists(output_txt_path):
                missing.append("output.txt")
            if not os.path.exists(deep_txt_path):
                missing.append("deep.txt")
            if not os.path.exists(story_txt_path):
                missing.append("story.txt")
            logger.warning(f"  ⚠️  Cannot generate smart snapshot - missing files: {', '.join(missing)}")

        logger.info(f"✅ Markdown generation completed ({time.time() - step_start:.2f}s)")
    else:
        logger.info("Step 5/5: Skipping markdown generation (generate_markdown=false)")

    # Final summary
    logger.info("=" * 80)
    logger.info(f"✅ Pipeline completed successfully in {time.time() - total_start:.2f}s")
    logger.info(f"📁 All outputs saved to: {output_dir}")
    logger.info("=" * 80)


if __name__ == '__main__':
    run_teacher_pipeline()
