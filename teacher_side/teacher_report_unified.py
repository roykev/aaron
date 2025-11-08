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
from teacher_side.teacher_utils import read_transcript
from utils.kimi_utils import OpenRouterProxy, AnthropicProxy
from utils.utils import get_logger


class TeacherReportUnifiedBase:
    """Base class with shared logic for unified report generation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.course_name = config.get("course_name", "Unknown Course")
        self.class_level = config.get("class_level", "Unknown Level")
        # Track which parts to generate
        self.include_basic = True
        self.include_deep = True
        self.include_story = True

    def compose_system_prompt(self, lan="English", include_basic=True, include_deep=True, include_story=True):
        """Compose unified system prompt combining selected analyses."""
        # Store which parts to include
        self.include_basic = include_basic
        self.include_deep = include_deep
        self.include_story = include_story

        # Build list of enabled analyses
        enabled_analyses = []
        if include_basic:
            enabled_analyses.append("1. **Basic Analysis** - Class structure, examples, questions, interactions, difficult topics")
        if include_deep:
            enabled_analyses.append("2. **Deep Pedagogical Analysis** - Communication, engagement, pedagogical approach, content delivery")
        if include_story:
            enabled_analyses.append("3. **Storytelling Analysis** - Narrative structure, curiosity, emotional engagement, coherence")

        analyses_text = "\n".join(enabled_analyses)

        system_prompt = (
            f"You are an expert teaching assistant and educational analyst. "
            f"Your task is to perform a comprehensive analysis of a university class based on its transcript.\n\n"

            f"You will analyze the class across the following area(s):\n"
            f"{analyses_text}\n\n"

            f"Course Information:\n"
            f"- Course: {self.course_name}\n"
            f"- Level: {self.class_level}\n"
            f"- Analysis Language: {lan}\n\n"

            f"Here is the transcript:\n"
            f"<transcript>{self.transcript}</transcript>\n\n"

            f"IMPORTANT OUTPUT FORMAT:\n"
            f"Return a JSON object with the requested section(s):\n"
            f"{{\n"
        )

        # Add JSON structure for enabled parts only
        sections = []
        if include_basic:
            sections.append(
                '  "basic": {\n'
                '    "title": {"title": "extracted title"},\n'
                '    "sections": "CSV format with headers",\n'
                '    "examples": "CSV format with headers",\n'
                '    "open_questions": {"simple": [...], "difficult": [...]},\n'
                '    "interaction": "CSV format with headers",\n'
                '    "difficult_topics": "CSV format with headers"\n'
                '  }'
            )

        if include_deep:
            sections.append(
                '  "deep": [\n'
                '    {"module": "communication", "strengths": [...], "weaknesses": [...], "recommendations": [...], "evidence": [...]},\n'
                '    {"module": "engagement", ...},\n'
                '    {"module": "pedagogical", ...},\n'
                '    {"module": "content", ...}\n'
                '  ]'
            )

        if include_story:
            sections.append(
                '  "story": [\n'
                '    {"module": "curiosity", "strengths": [...], "weaknesses": [...], "recommendations": [...], "evidence": [...]},\n'
                '    {"module": "coherence", ...},\n'
                '    {"module": "emotional", ...},\n'
                '    {"module": "narrative", ...},\n'
                '    {"module": "concrete2abstract", ...},\n'
                '    {"module": "characters", ...}\n'
                '  ]'
            )

        system_prompt += ",\n".join(sections)
        system_prompt += (
            f"\n}}\n\n"
            f"Return ONLY valid JSON. No markdown code fences, no extra text.\n"
            f"All output should be in: {lan}\n"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English", include_basic=True, include_deep=True, include_story=True):
        """Compose unified user prompt with selected tasks."""

        prompt_parts = []
        prompt_parts.append("Perform the following analyses on the provided transcript:\n")

        # Add basic tasks if enabled
        if include_basic:
            basic_tasks = get_tasks(lan)
            prompt_parts.append(f"# PART 1: BASIC ANALYSIS\n{basic_tasks}\n\n---\n")

        # Add deep analysis tasks if enabled
        if include_deep:
            deep_tasks = "\n\n".join([
                task(lan=lan, format='JSON')
                for task in deep_tasks_dict.values()
            ])
            prompt_parts.append(f"# PART 2: DEEP PEDAGOGICAL ANALYSIS\n{deep_tasks}\n\n---\n")

        # Add storytelling tasks if enabled
        if include_story:
            story_tasks = "\n\n".join([
                task(lan=lan, format='JSON')
                for task in story_tasks_dict.values()
            ])
            prompt_parts.append(f"# PART 3: STORYTELLING ANALYSIS\n{story_tasks}\n\n---\n")

        prompt_parts.append(
            f"\nFINAL INSTRUCTIONS:\n"
            f"- Combine all results into a single JSON object as specified in the system prompt\n"
            f"- Ensure all CSV sections include column headers\n"
            f"- Use {lan} for all text output\n"
            f"- Return ONLY the JSON object, no markdown fences\n"
        )

        self.user_prompt = "\n".join(prompt_parts)

    def prepare_content(self, lan="English", include_basic=True, include_deep=True, include_story=True):
        """Prepare unified content for analysis with selected parts."""
        self.transcript = read_transcript(self.config["videos_dir"])
        self.compose_system_prompt(lan, include_basic, include_deep, include_story)
        self.compose_user_prompt(lan, include_basic, include_deep, include_story)


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
