#!/usr/bin/env python3
"""
AaronOwl Teacher Report Pipeline
Main orchestration script that runs the complete teacher report generation pipeline
based on flags in config.yaml
"""

import os
import sys
import time
import yaml
from pathlib import Path

# Add parent directory to Python path so imports work from anywhere
script_dir = Path(__file__).resolve().parent.parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from teacher_side.teacher_report import TeacherReport, TeacherReportOR
from teacher_side.teacher_report_deep import TeacherReportDeep, TeacherReportDeepOR
from teacher_side.teacher_report_storytelling import TeacherReportStoryTelling, TeacherReportStoryTellingOR
from teacher_side.snapshot_generator import SnapshotGenerator
from teacher_side.teacher_report_smart_insights import TeacherReportSmartInsights, TeacherReportSmartInsightsOR
from teacher_side.teacher_report_unified import TeacherReportUnified, TeacherReportUnifiedOR, parse_and_save_unified_output
from teacher_side.teacher_utils import get_output_dir, generate_report, generate_story_report, generate_deep_report, generate_extended_insights
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
    use_unified_mode = teacher_config.get("use_unified_mode", True)  # Default to True for efficiency

    # Get language and course settings
    language = config.get("language", "English")
    course_name = config.get("course_name", "Unknown Course")
    class_level = config.get("class_level", "Unknown Level")
    
    # Determine which LLM backend to use (Anthropic by default, OpenRouter as fallback)
    use_openrouter = config.get("llm", {}).get("use_openrouter", False)
    
    # Select the appropriate classes based on configuration
    if use_openrouter:
        logger.info("Using OpenRouter backend")
        TeacherReportClass = TeacherReportOR
        TeacherDeepClass = TeacherReportDeepOR
        TeacherStoryClass = TeacherReportStoryTellingOR
        TeacherInsightsClass = TeacherReportSmartInsightsOR
    else:
        logger.info("Using Anthropic Claude backend")
        TeacherReportClass = TeacherReport
        TeacherDeepClass = TeacherReportDeep
        TeacherStoryClass = TeacherReportStoryTelling
        TeacherInsightsClass = TeacherReportSmartInsights

    # Get output directory
    output_dir = get_output_dir(config)

    logger.info("=" * 80)
    logger.info("AaronOwl Teacher Report Pipeline Started")
    logger.info("=" * 80)
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Language: {language}")
    logger.info(f"Course: {course_name}")
    logger.info(f"Level: {class_level}")
    # Determine actual mode (unified only works with 2+ parts)
    num_parts = sum([generate_basic, generate_deep, generate_story])
    will_use_unified = use_unified_mode and num_parts >= 2
    mode_str = f"Unified (1 call for {num_parts} parts)" if will_use_unified else "Separate calls"
    logger.info(f"Mode: {mode_str}")
    logger.info(f"Flags: basic={generate_basic}, deep={generate_deep}, story={generate_story}, markdown={generate_markdown}, smart_insights={generate_smart_insights}")
    logger.info("=" * 80)

    total_start = time.time()

    # UNIFIED MODE - Generate selected analyses in ONE LLM call
    # Only use unified mode if generating 2+ parts (efficiency gain)
    num_parts = sum([generate_basic, generate_deep, generate_story])

    if use_unified_mode and num_parts >= 2:
        # Build list of parts being generated
        parts = []
        if generate_basic:
            parts.append("basic")
        if generate_deep:
            parts.append("deep")
        if generate_story:
            parts.append("story")

        parts_str = " + ".join(parts)

        logger.info("=" * 80)
        logger.info(f"🚀 UNIFIED MODE: Generating {parts_str} in ONE LLM call")
        logger.info("=" * 80)
        step_start = time.time()

        # Select unified class
        UnifiedClass = TeacherReportUnifiedOR if use_openrouter else TeacherReportUnified

        logger.info(f"Step 1/2: Calling LLM for unified analysis ({parts_str})...")
        llmproxy = UnifiedClass(config, logger=logger)
        llmproxy.course_name = course_name
        llmproxy.class_level = class_level
        # Pass individual flags to control what gets generated
        llmproxy.prepare_content(
            lan=language,
            include_basic=generate_basic,
            include_deep=generate_deep,
            include_story=generate_story
        )

        # Check if we should use cached response instead of calling API
        use_cached = config.get("llm", {}).get("use_cached_response", False)
        cached_file = os.path.join(output_dir, "unified_output_raw.txt")

        if use_cached and os.path.exists(cached_file):
            logger.info(f"  📁 Loading cached API response from: {cached_file}")
            with open(cached_file, 'r', encoding='utf-8') as f:
                output = f.read()
            logger.info(f"  ✅ Loaded {len(output)} characters from cache")
        else:
            logger.info(f"  Sending unified request to LLM (requesting: {parts_str})...")
            output = llmproxy.call_api()

        logger.info("  Parsing and saving results...")
        success = parse_and_save_unified_output(output, output_dir, logger)

        if success:
            logger.info(f"✅ Unified analysis completed in {time.time() - step_start:.2f}s")
            saved_files = []
            if generate_basic:
                saved_files.append("output.txt")
            if generate_deep:
                saved_files.append("deep.txt")
            if generate_story:
                saved_files.append("story.txt")
            logger.info(f"   Saved: {', '.join(saved_files)}")

            # Mark generated parts as complete
            if generate_basic:
                generate_basic = False
            if generate_deep:
                generate_deep = False
            if generate_story:
                generate_story = False
        else:
            logger.error("❌ Unified analysis failed - falling back to separate mode")
            use_unified_mode = False

    # Step 1: Generate basic report (output.txt)
    if generate_basic:
        logger.info("Step 1/5: Generating basic teacher report (output.txt)...")
        step_start = time.time()

        llmproxy = TeacherReportClass(config)
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

        llmproxy = TeacherDeepClass(config)
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

        llmproxy = TeacherStoryClass(config)
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

    # Step 4: Generate LLM-based smart insights JSON (most important findings)
    if generate_smart_insights:
        logger.info("Step 4/5: Generating AI-powered smart insights...")
        step_start = time.time()

        deep_txt_path = os.path.join(output_dir, "deep.txt")
        story_txt_path = os.path.join(output_dir, "story.txt")

        if os.path.exists(deep_txt_path) and os.path.exists(story_txt_path):
            logger.info("  Calling LLM to analyze and synthesize most important insights...")

            llmproxy = TeacherInsightsClass(config)
            llmproxy.prepare_content(output_dir, lan=language)
            output = llmproxy.call_api()

            # Save JSON output only
            insights_json_path = os.path.join(output_dir, "smart_insights.json")
            with open(insights_json_path, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info(f"  ✅ Smart insights JSON saved to: {insights_json_path}")

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
        insights_json_path = os.path.join(output_dir, "smart_insights.json")

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

        # Generate teaching_snapshot.md (minimalist) if we have deep.txt and story.txt
        if os.path.exists(deep_txt_path) and os.path.exists(story_txt_path) and os.path.exists(output_txt_path):
            logger.info("  Generating teaching_snapshot.md (quick overview)...")
            generator = SnapshotGenerator(story_txt_path, deep_txt_path, output_txt_path)
            minimalist_markdown = generator.generate_minimalist_markdown()
            minimalist_path = Path(os.path.join(output_dir, 'teaching_snapshot.md'))
            minimalist_path.write_text(minimalist_markdown, encoding='utf-8')
            logger.info(f"  ✅ Teaching snapshot saved to: {minimalist_path}")

        # Generate extended_insights.md (comprehensive) if we have the required files
        if os.path.exists(deep_txt_path) or os.path.exists(story_txt_path):
            logger.info("  Generating extended_insights.md (comprehensive analysis)...")
            generate_extended_insights(output_dir)
            logger.info(f"  ✅ Extended insights saved to: {os.path.join(output_dir, 'extended_insights.md')}")

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
