#!/usr/bin/env python3
"""
AaronOwl Unified Teacher Report
Combines all teacher report analyses (basic, deep, storytelling) into ONE LLM call
for maximum efficiency and cost savings.
"""

import os
import time
import json
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import get_tasks
from teacher_side.teacher_report_deep import tasks_dict as deep_tasks_dict
from teacher_side.teacher_report_storytelling import tasks_dict as story_tasks_dict
from utils.kimi_utils import OpenRouterProxy, AnthropicProxy
from utils.utils import get_logger


class TeacherReportUnifiedBase:
    """Base class with shared logic for unified report generation."""

    def __init__(self, config: Dict[str, Any]):
        self.course_name = config.get("course_name", "Unknown Course")
        self.class_level = config.get("class_level", "Unknown Level")

    def compose_system_prompt(self, lan="English"):
        """Compose unified system prompt combining all analyses."""
        system_prompt = (
            f"You are an expert teaching assistant and educational analyst. "
            f"Your task is to perform a comprehensive analysis of a university class based on its transcript.\n\n"

            f"You will analyze the class across THREE major areas:\n"
            f"1. **Basic Analysis** - Class structure, examples, questions, interactions, difficult topics\n"
            f"2. **Deep Pedagogical Analysis** - Communication, engagement, pedagogical approach, content delivery\n"
            f"3. **Storytelling Analysis** - Narrative structure, curiosity, emotional engagement, coherence\n\n"

            f"Course Information:\n"
            f"- Course: {self.course_name}\n"
            f"- Level: {self.class_level}\n"
            f"- Analysis Language: {lan}\n\n"

            f"Here is the transcript:\n"
            f"<transcript>{self.transcript}</transcript>\n\n"

            f"IMPORTANT OUTPUT FORMAT:\n"
            f"Return a JSON object with THREE main sections:\n"
            f"{{\n"
            f'  "basic": {{\n'
            f'    "title": {{"title": "extracted title"}},\n'
            f'    "sections": "CSV format with headers",\n'
            f'    "examples": "CSV format with headers",\n'
            f'    "open_questions": {{"simple": [...], "difficult": [...]}},\n'
            f'    "interaction": "CSV format with headers",\n'
            f'    "difficult_topics": "CSV format with headers"\n'
            f'  }},\n'
            f'  "deep": [\n'
            f'    {{"module": "communication", "strengths": [...], "weaknesses": [...], "recommendations": [...], "evidence": [...]}},\n'
            f'    {{"module": "engagement", ...}},\n'
            f'    {{"module": "pedagogical", ...}},\n'
            f'    {{"module": "content", ...}}\n'
            f'  ],\n'
            f'  "story": [\n'
            f'    {{"module": "curiosity", "strengths": [...], "weaknesses": [...], "recommendations": [...], "evidence": [...]}},\n'
            f'    {{"module": "coherence", ...}},\n'
            f'    {{"module": "emotional", ...}},\n'
            f'    {{"module": "narrative", ...}},\n'
            f'    {{"module": "concrete2abstract", ...}},\n'
            f'    {{"module": "characters", ...}}\n'
            f'  ]\n'
            f"}}\n\n"

            f"Return ONLY valid JSON. No markdown code fences, no extra text.\n"
            f"All output should be in: {lan}\n"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English"):
        """Compose unified user prompt with all tasks."""

        # Get basic tasks
        basic_tasks = get_tasks(lan)

        # Build deep analysis tasks
        deep_tasks = "\n\n".join([
            task(lan=lan, format='JSON')
            for task in deep_tasks_dict.values()
        ])

        # Build storytelling tasks
        story_tasks = "\n\n".join([
            task(lan=lan, format='JSON')
            for task in story_tasks_dict.values()
        ])

        self.user_prompt = (
            f"Perform ALL of the following analyses on the provided transcript:\n\n"

            f"# PART 1: BASIC ANALYSIS\n"
            f"{basic_tasks}\n\n"

            f"---\n\n"

            f"# PART 2: DEEP PEDAGOGICAL ANALYSIS\n"
            f"{deep_tasks}\n\n"

            f"---\n\n"

            f"# PART 3: STORYTELLING ANALYSIS\n"
            f"{story_tasks}\n\n"

            f"---\n\n"

            f"FINAL INSTRUCTIONS:\n"
            f"- Combine all results into a single JSON object as specified in the system prompt\n"
            f"- Ensure all CSV sections include column headers\n"
            f"- Use {lan} for all text output\n"
            f"- Return ONLY the JSON object, no markdown fences\n"
        )

    def prepare_content(self, lan="English"):
        """Prepare unified content for analysis."""
        self.read_transcript()
        self.compose_system_prompt(lan)
        self.compose_user_prompt(lan)


class TeacherReportUnified(TeacherReportUnifiedBase, AnthropicProxy):
    """Unified teacher report using Anthropic Claude (default)."""

    def __init__(self, config: Dict[str, Any], api_key: str = None):
        AnthropicProxy.__init__(self, config, api_key)
        TeacherReportUnifiedBase.__init__(self, config)


class TeacherReportUnifiedOR(TeacherReportUnifiedBase, OpenRouterProxy):
    """Unified teacher report using OpenRouter (fallback)."""

    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        OpenRouterProxy.__init__(self, config, api_key, base_url)
        TeacherReportUnifiedBase.__init__(self, config)


def parse_and_save_unified_output(output_json: str, output_dir: str, logger):
    """
    Parse the unified JSON output and save to separate files.

    Args:
        output_json: JSON string from LLM
        output_dir: Directory to save output files
        logger: Logger instance
    """
    try:
        # Parse JSON
        data = json.loads(output_json)

        # Save basic analysis (output.txt)
        if "basic" in data:
            basic = data["basic"]
            output_txt_lines = []

            # Title
            if "title" in basic:
                output_txt_lines.append("### title ###")
                output_txt_lines.append(json.dumps(basic["title"], ensure_ascii=False))
                output_txt_lines.append("")

            # Sections
            if "sections" in basic:
                output_txt_lines.append("### sections ###")
                output_txt_lines.append(basic["sections"])
                output_txt_lines.append("")

            # Examples
            if "examples" in basic:
                output_txt_lines.append("### examples ###")
                output_txt_lines.append(basic["examples"])
                output_txt_lines.append("")

            # Open questions
            if "open_questions" in basic:
                output_txt_lines.append("### open_questions ###")
                output_txt_lines.append(json.dumps(basic["open_questions"], ensure_ascii=False))
                output_txt_lines.append("")

            # Interactions
            if "interaction" in basic:
                output_txt_lines.append("### interaction ###")
                output_txt_lines.append(basic["interaction"])
                output_txt_lines.append("")

            # Difficult topics
            if "difficult_topics" in basic:
                output_txt_lines.append("### difficult_topics ###")
                output_txt_lines.append(basic["difficult_topics"])
                output_txt_lines.append("")

            output_file = os.path.join(output_dir, "output.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(output_txt_lines))
            logger.info(f"  ✅ Basic analysis saved to: {output_file}")

        # Save deep analysis (deep.txt)
        if "deep" in data:
            deep_file = os.path.join(output_dir, "deep.txt")
            with open(deep_file, "w", encoding="utf-8") as f:
                json.dump(data["deep"], f, ensure_ascii=False, indent=2)
            logger.info(f"  ✅ Deep analysis saved to: {deep_file}")

        # Save storytelling analysis (story.txt)
        if "story" in data:
            story_file = os.path.join(output_dir, "story.txt")
            with open(story_file, "w", encoding="utf-8") as f:
                json.dump(data["story"], f, ensure_ascii=False, indent=2)
            logger.info(f"  ✅ Storytelling analysis saved to: {story_file}")

        return True

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON output: {e}")
        # Save raw output for debugging
        raw_file = os.path.join(output_dir, "unified_output_raw.txt")
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(output_json)
        logger.error(f"Raw output saved to: {raw_file}")
        return False


def main():
    """Test unified report generation."""
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    language = config.get("language", "English")

    from teacher_side.teacher_utils import get_output_dir
    output_dir = get_output_dir(config)

    logger.info("Testing unified teacher report generation...")

    t0 = time.time()
    llmproxy = TeacherReportUnified(config)
    llmproxy.prepare_content(lan=language)

    logger.info("Calling LLM for unified analysis...")
    output = llmproxy.call_api()

    # Save and parse
    logger.info("Parsing and saving results...")
    success = parse_and_save_unified_output(output, output_dir, logger)

    if success:
        logger.info(f"✅ Unified analysis completed in {time.time() - t0:.2f}s")
    else:
        logger.error(f"❌ Failed to parse unified output")


if __name__ == '__main__':
    main()
