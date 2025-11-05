"""
Main Teacher Report Generator

This script orchestrates the complete teacher report generation pipeline:
1. Generates basic report with sections, examples, interactions, and difficult topics (teacher_report.py)
2. Generates deep analysis report covering communication, content, pedagogy, and engagement (teacher_report_deep.py)
3. Generates storytelling analysis report (teacher_report_storytelling.py)
4. Generates markdown reports from the analysis outputs (teacher_utils.py)
"""

import os
import time
from warnings import catch_warnings

import yaml
import argparse
from pathlib import Path

from teacher_side.teacher_report import TeacherReport
from teacher_side.teacher_report_deep import TeacherReportDeep
from teacher_side.teacher_report_storytelling import TeacherReportStoryTelling
from teacher_side.teacher_utils import generate_report, generate_deep_report, generate_story_report, get_output_dir
from utils.utils import get_logger


def read_transcript_once(config, logger):
    """
    Read the transcript file once and return the content.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        Transcript content as string
    """
    logger.info("Reading transcript file...")
    t0 = time.time()

    # Use TeacherReport to read the transcript using existing logic
    temp_report = TeacherReport(config)
    temp_report.read_transcript()
    transcript = temp_report.transcript

    logger.info(f"Transcript read successfully in {time.time() - t0:.2f}s")
    logger.info(f"Transcript length: {len(transcript)} characters")

    return transcript




def run_basic_report(config, logger, transcript, language="English"):
    """
    Generate basic teacher report with sections, examples, interactions, and difficult topics.

    Args:
        config: Configuration dictionary
        logger: Logger instance
        transcript: Pre-loaded transcript content
        language: Output language (default: "English")

    Returns:
        Path to output.txt file
    """
    logger.info("=" * 80)
    logger.info("STEP 1: Generating Basic Teacher Report")
    logger.info("=" * 80)

    t0 = time.time()
    llmproxy = TeacherReport(config)
    llmproxy.transcript = transcript  # Use pre-loaded transcript
    llmproxy.prepare_content(lan=language)
    output = llmproxy.call_api()

    output_dir = get_output_dir(config)
    output_file = os.path.join(output_dir, "output.txt")
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(output)

    logger.info(f"Basic report saved to: {output_file}")
    logger.info(f"Step 1 completed in {time.time() - t0:.2f}s")

    return output_file


def run_deep_analysis(config, logger, transcript, language="English", course_name="", class_level=""):
    """
    Generate deep analysis report covering communication, content, pedagogy, and engagement.

    Args:
        config: Configuration dictionary
        logger: Logger instance
        transcript: Pre-loaded transcript content
        language: Output language (default: "English")
        course_name: Name of the course
        class_level: Academic level of the class

    Returns:
        Path to deep.txt file
    """
    logger.info("=" * 80)
    logger.info("STEP 2: Generating Deep Analysis Report")
    logger.info("=" * 80)

    t0 = time.time()
    llmproxy = TeacherReportDeep(config)
    llmproxy.transcript = transcript  # Use pre-loaded transcript
    llmproxy.course_name = course_name
    llmproxy.class_level = class_level

    llmproxy.prepare_content(lan=language)
    output = llmproxy.call_api()

    output_dir = get_output_dir(config)
    output_file = os.path.join(output_dir, "deep.txt")
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(output)

    logger.info(f"Deep analysis saved to: {output_file}")
    logger.info(f"Step 2 completed in {time.time() - t0:.2f}s")

    return output_file


def run_storytelling_analysis(config, logger, transcript, language="English", course_name="", class_level=""):
    """
    Generate storytelling analysis report.

    Args:
        config: Configuration dictionary
        logger: Logger instance
        transcript: Pre-loaded transcript content
        language: Output language (default: "English")
        course_name: Name of the course
        class_level: Academic level of the class

    Returns:
        Path to story.txt file
    """
    logger.info("=" * 80)
    logger.info("STEP 3: Generating Storytelling Analysis Report")
    logger.info("=" * 80)

    t0 = time.time()
    llmproxy = TeacherReportStoryTelling(config)
    llmproxy.transcript = transcript  # Use pre-loaded transcript
    llmproxy.course_name = course_name
    llmproxy.class_level = class_level

    llmproxy.prepare_content(lan=language)
    output = llmproxy.call_api()

    output_dir = get_output_dir(config)
    output_file = os.path.join(output_dir, "story.txt")
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(output)

    logger.info(f"Storytelling analysis saved to: {output_file}")
    logger.info(f"Step 3 completed in {time.time() - t0:.2f}s")

    return output_file


def generate_markdown_reports(config, logger):
    """
    Generate markdown reports from all analysis outputs.

    Args:
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        List of paths to generated markdown files
    """
    logger.info("=" * 80)
    logger.info("STEP 4: Generating Markdown Reports")
    logger.info("=" * 80)

    t0 = time.time()
    output_dir = get_output_dir(config)

    output_files = []

    try:
        # Generate basic markdown report (output.md)
            if os.path.exists(os.path.join(output_dir, "output.txt")):
                logger.info("Generating output.md from output.txt...")
                generate_report(output_dir)
                output_files.append(os.path.join(output_dir, "output.md"))
            else:
                logger.warning("output.txt not found, skipping output.md generation")
    except Exception as e:
        logger.error(f"Error generating basic report: {e}", exc_info=True)

    try:
        # Generate deep analysis markdown report (deep.md)
        if os.path.exists(os.path.join(output_dir, "deep.txt")):
            logger.info("Generating deep.md from deep.txt...")
            generate_deep_report(output_dir)
            output_files.append(os.path.join(output_dir, "deep.md"))
        else:
            logger.warning("deep.txt not found, skipping deep.md generation")
    except Exception as e:
        logger.error(f"Error generating deep report: {e}", exc_info=True)

    try:
        # Generate storytelling markdown report (story.md)
        if os.path.exists(os.path.join(output_dir, "story.txt")):
            logger.info("Generating story.md from story.txt...")
            generate_story_report(output_dir)
            output_files.append(os.path.join(output_dir, "story.md"))
        else:
            logger.warning("story.txt not found, skipping story.md generation")
    except Exception as e:
        logger.error(f"Error generating story report: {e}", exc_info=True)

    logger.info(f"Step 4 completed in {time.time() - t0:.2f}s")
    logger.info(f"Generated {len(output_files)} markdown reports")

    return output_files


def main():
    """Main execution function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate comprehensive teacher reports")
    parser.add_argument("--config", default="./config.yaml", help="Path to config file")
    parser.add_argument("--language", help="Output language (overrides config)")
    parser.add_argument("--course-name", default="", help="Name of the course")
    parser.add_argument("--class-level", default="", help="Academic level of the class")
    parser.add_argument("--skip-basic", action="store_true", help="Skip basic report generation")
    parser.add_argument("--skip-deep", action="store_true", help="Skip deep analysis")
    parser.add_argument("--skip-story", action="store_true", help="Skip storytelling analysis")
    parser.add_argument("--skip-markdown", action="store_true", help="Skip markdown report generation")

    args = parser.parse_args()

    # Load configuration
    config_path = args.config
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Get language from args or config
    language = args.language or config.get("language", "English")
    course_name = args.course_name or config.get("course_name", "")
    class_level = args.class_level or config.get("class_level", "")

    # Get report generation flags from config
    teacher_reports = config.get("teacher_reports", {})
    skip_basic = args.skip_basic or not teacher_reports.get("generate_basic", True)
    skip_deep = args.skip_deep or not teacher_reports.get("generate_deep", True)
    skip_story = args.skip_story or not teacher_reports.get("generate_story", True)
    skip_markdown = args.skip_markdown or not teacher_reports.get("generate_markdown", True)

    # Start pipeline
    total_start = time.time()
    output_dir = get_output_dir(config)

    logger.info("=" * 80)
    logger.info("TEACHER REPORT GENERATION PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Videos directory: {config['videos_dir']}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Language: {language}")
    logger.info(f"Course name: {course_name or 'Not specified'}")
    logger.info(f"Class level: {class_level or 'Not specified'}")
    logger.info("")

    # Step 0: Read transcript once
    transcript = None
    if not (skip_basic and skip_deep and skip_story):
        try:
            transcript = read_transcript_once(config, logger)
        except Exception as e:
            logger.error(f"Error reading transcript: {e}", exc_info=True)
            logger.error("Cannot proceed without transcript. Exiting.")
            return

    # Step 1: Basic report
    if not skip_basic:
        try:
            run_basic_report(config, logger, transcript, language)
        except Exception as e:
            logger.error(f"Error generating basic report: {e}", exc_info=True)
    else:
        logger.info("Skipping basic report generation")

    # Step 2: Deep analysis
    if not skip_deep:
        try:
            run_deep_analysis(config, logger, transcript, language, course_name, class_level)
        except Exception as e:
            logger.error(f"Error generating deep analysis: {e}", exc_info=True)
    else:
        logger.info("Skipping deep analysis")

    # Step 3: Storytelling analysis
    if not skip_story:
        try:
            run_storytelling_analysis(config, logger, transcript, language, course_name, class_level)
        except Exception as e:
            logger.error(f"Error generating storytelling analysis: {e}", exc_info=True)
    else:
        logger.info("Skipping storytelling analysis")

    # Step 4: Generate markdown reports
    if not skip_markdown:
        try:
            markdown_files = generate_markdown_reports(config, logger)
            logger.info(f"Generated markdown reports: {markdown_files}")
        except Exception as e:
            logger.error(f"Error generating markdown reports: {e}", exc_info=True)
    else:
        logger.info("Skipping markdown report generation")

    # Summary
    total_time = time.time() - total_start
    logger.info("=" * 80)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
    logger.info(f"Output directory: {output_dir}")
    logger.info("")
    logger.info("Generated files:")

    # List all generated files
    for filename in ["output.txt", "output.md", "deep.txt", "deep.md", "story.txt", "story.md"]:
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            logger.info(f"  ✓ {filename}")
        else:
            logger.info(f"  ✗ {filename} (not generated)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()