#!/usr/bin/env python3
"""
AaronOwl Unified Teacher Report
Combines all teacher report analyses (basic, deep, storytelling, active learning) into ONE LLM call
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
from teacher_side.teacher_report_active_learning import tasks_dict as active_tasks_dict
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
        self.include_active = True
        self.transcript = None

    def read_transcript(self, suffix='.txt'):
        """Read transcript file from videos directory."""
        def find_transcript_file(videos_dir: str, suffix='.txt') -> str:
            """Find the transcript file (.txt, .vtt, or .srt) in the videos directory."""
            supported_formats = ['.txt', '.vtt', '.srt']
            search_order = [suffix] + [fmt for fmt in supported_formats if fmt != suffix]

            for fmt in search_order:
                for file in os.listdir(videos_dir):
                    if file.endswith(fmt):
                        return os.path.join(videos_dir, file)

            raise FileNotFoundError(f"No transcript file (.txt, .vtt, or .srt) found in {videos_dir}")

        def parse_transcript_txt(transcript_path: str) -> str:
            """Read and extract the full transcript text from the file."""
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract only the text content, removing speaker labels and timestamps
            lines = content.split('\n')
            transcript_lines = []

            for line in lines:
                line = line.strip()
                if line and not line.startswith('[') and not line.startswith('('):
                    transcript_lines.append(line)

            return ' '.join(transcript_lines)

        trans_path = find_transcript_file(self.config["videos_dir"])
        if suffix == ".txt":
            self.transcript = parse_transcript_txt(trans_path)
        else:
            raise ValueError(f"{trans_path}, suffix not supported!")

    def compose_system_prompt(self, lan="English", include_basic=True, include_deep=True, include_story=True, include_active=True):
        """Compose unified system prompt combining selected analyses."""
        # Store which parts to include
        self.include_basic = include_basic
        self.include_deep = include_deep
        self.include_story = include_story
        self.include_active = include_active

        # Build list of enabled analyses
        enabled_analyses = []
        if include_basic:
            enabled_analyses.append("1. **Basic Analysis** - Class structure, examples, questions, interactions, difficult topics")
        if include_deep:
            enabled_analyses.append("2. **Deep Pedagogical Analysis** - Communication, engagement, pedagogical approach, content delivery")
        if include_story:
            enabled_analyses.append("3. **Storytelling Analysis** - Narrative structure, curiosity, emotional engagement, coherence")
        if include_active:
            enabled_analyses.append("4. **Active Learning Analysis** - Student interaction, short tasks, reflection, collaboration, choice/agency, scaffolding")

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

        if include_active:
            sections.append(
                '  "active": [\n'
                '    {"dimension": "student_interaction", "strengths": [...], "weaknesses": [...], "recommendations": [...], "evidence": [...]},\n'
                '    {"dimension": "short_tasks", ...},\n'
                '    {"dimension": "student_reflection", ...},\n'
                '    {"dimension": "collaboration", ...},\n'
                '    {"dimension": "student_choice", ...},\n'
                '    {"dimension": "learning_scaffolding", ...}\n'
                '  ]'
            )

        system_prompt += ",\n".join(sections)
        system_prompt += (
            f"\n}}\n\n"
            f"Return ONLY valid JSON. No markdown code fences, no extra text.\n"
            f"All output should be in: {lan}\n"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English", include_basic=True, include_deep=True, include_story=True, include_active=True):
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

        # Add active learning tasks if enabled
        if include_active:
            active_tasks = "\n\n".join([
                task(lan=lan, format='JSON')
                for task in active_tasks_dict.values()
            ])
            prompt_parts.append(f"# PART 4: ACTIVE LEARNING ANALYSIS\n{active_tasks}\n\n---\n")

        prompt_parts.append(
            f"\nFINAL INSTRUCTIONS:\n"
            f"- Combine all results into a single JSON object as specified in the system prompt\n"
            f"- Ensure all CSV sections include column headers\n"
            f"- Use {lan} for all text output\n"
            f"- Return ONLY the JSON object, no markdown fences\n"
        )

        self.user_prompt = "\n".join(prompt_parts)

    def prepare_content(self, lan="English", include_basic=True, include_deep=True, include_story=True, include_active=True):
        """Prepare unified content for analysis with selected parts."""
        self.read_transcript()
        self.compose_system_prompt(lan, include_basic, include_deep, include_story, include_active)
        self.compose_user_prompt(lan, include_basic, include_deep, include_story, include_active)


class TeacherReportUnified(TeacherReportUnifiedBase, AnthropicProxy):
    """Unified teacher report using Anthropic Claude (default)."""

    def __init__(self, config: Dict[str, Any], api_key: str = None, logger=None):
        AnthropicProxy.__init__(self, config, api_key, logger)
        TeacherReportUnifiedBase.__init__(self, config)


class TeacherReportUnifiedOR(TeacherReportUnifiedBase, OpenRouterProxy):
    """Unified teacher report using OpenRouter (fallback)."""

    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1", logger=None):
        OpenRouterProxy.__init__(self, config, api_key, base_url, logger)
        TeacherReportUnifiedBase.__init__(self, config)


def repair_truncated_json(output_json: str, logger) -> tuple[str, bool]:
    """
    Attempt to repair truncated JSON by closing open structures.

    Returns:
        tuple: (repaired_json, was_truncated)
    """
    # DEBUG: Log what we received
    logger.info(f"DEBUG: repair_truncated_json received {len(output_json)} chars")
    logger.info(f"DEBUG: Type: {type(output_json)}, repr first 200: {repr(output_json[:200])}")

    original = output_json.strip()

    logger.info(f"DEBUG: After strip(), len={len(original)}, first 200: {repr(original[:200])}")

    # Remove markdown code fences if present (```json ... ``` or ``` ... ```)
    if original.startswith('```'):
        logger.info("DEBUG: Detected markdown code fences, removing them...")
        # Remove opening fence (```json or ```)
        lines = original.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]  # Remove first line
        # Remove closing fence (```)
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]  # Remove last line
        original = '\n'.join(lines)
        logger.info(f"DEBUG: After removing fences, len={len(original)}, first 200: {repr(original[:200])}")

    # Try parsing as-is first
    try:
        json.loads(original)
        logger.info("DEBUG: JSON is valid, returning as-is")
        return original, False
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {e}")
        logger.info("Attempting to repair truncated JSON...")

        # Find the last complete character before truncation
        repaired = original

        # Count unclosed structures
        brace_count = repaired.count('{') - repaired.count('}')
        bracket_count = repaired.count('[') - repaired.count(']')

        # Check for unterminated string
        # Count quotes, excluding escaped ones
        in_string = False
        escape_next = False
        for char in repaired:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string

        # If we're in an unterminated string, close it
        if in_string:
            logger.info("Closing unterminated string")
            repaired += '"'

        # Close any open arrays
        for _ in range(bracket_count):
            logger.info("Closing unclosed array")
            repaired += '\n]'

        # Close any open objects
        for _ in range(brace_count):
            logger.info("Closing unclosed object")
            repaired += '\n}'

        # Try parsing again
        try:
            json.loads(repaired)
            logger.info("✅ Successfully repaired JSON")
            return repaired, True
        except json.JSONDecodeError as e2:
            logger.error(f"Could not repair JSON: {e2}")
            # Return original
            return original, True


def parse_and_save_unified_output(output_json: str, output_dir: str, logger):
    """
    Parse the unified JSON output and save to separate files.

    Args:
        output_json: JSON string from LLM
        output_dir: Directory to save output files
        logger: Logger instance
    """
    try:
        # DEBUG: Log what we received
        logger.info(f"DEBUG: parse_and_save_unified_output received {len(output_json)} chars")
        logger.info(f"DEBUG: First 200 chars: {repr(output_json[:200])}")
        logger.info(f"DEBUG: Last 200 chars: {repr(output_json[-200:])}")

        # First, try to repair any truncated JSON
        repaired_json, was_truncated = repair_truncated_json(output_json, logger)

        # DEBUG: Log what repair function returned
        logger.info(f"DEBUG: repair_truncated_json returned {len(repaired_json)} chars, was_truncated={was_truncated}")
        logger.info(f"DEBUG: First 200 chars of repaired: {repr(repaired_json[:200])}")

        if was_truncated:
            logger.warning("⚠️  JSON was truncated - output may be incomplete")
            # Save the repaired version for reference
            repaired_file = os.path.join(output_dir, "unified_output_repaired.json")
            with open(repaired_file, "w", encoding="utf-8") as f:
                f.write(repaired_json)
            logger.info(f"Repaired JSON saved to: {repaired_file}")

        # Parse JSON
        data = json.loads(repaired_json)

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

        # Save active learning analysis (active.txt)
        if "active" in data:
            active_file = os.path.join(output_dir, "active.txt")
            with open(active_file, "w", encoding="utf-8") as f:
                json.dump(data["active"], f, ensure_ascii=False, indent=2)
            logger.info(f"  ✅ Active learning analysis saved to: {active_file}")

        raw_file = os.path.join(output_dir, "unified_output_raw.txt")
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(output_json)
        logger.error(f"Raw output saved to: {raw_file}")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON output: {e}")
        # Save raw output for debugging

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
