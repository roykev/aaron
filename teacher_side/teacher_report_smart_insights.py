#!/usr/bin/env python3
"""
AaronOwl Smart Insights Generator
Uses LLM to analyze deep.txt and story.txt outputs and identify the MOST IMPORTANT
insights and recommendations for teacher improvement.
"""

import os
import time
from typing import Dict, Any
import yaml

from utils.kimi_utils import OpenRouterProxy
from utils.utils import get_logger


class TeacherReportSmartInsights(OpenRouterProxy):
    """
    Analyzes existing teacher report outputs (deep.txt and story.txt) using an LLM
    to identify and synthesize the most important insights and recommendations.
    """

    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(config, api_key, base_url)
        self.deep_analysis = None
        self.story_analysis = None
        self.output_analysis = None

    def load_analysis_files(self, output_dir: str):
        """
        Load the analysis files from the output directory.

        Args:
            output_dir: Directory containing output.txt, deep.txt, and story.txt
        """
        # Load deep.txt
        deep_path = os.path.join(output_dir, "deep.txt")
        with open(deep_path, 'r', encoding='utf-8') as f:
            self.deep_analysis = f.read()

        # Load story.txt
        story_path = os.path.join(output_dir, "story.txt")
        with open(story_path, 'r', encoding='utf-8') as f:
            self.story_analysis = f.read()

        # Load output.txt (optional - for context about examples, questions, etc.)
        output_path = os.path.join(output_dir, "output.txt")
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                self.output_analysis = f.read()

    def compose_system_prompt(self, lan="English"):
        """Compose the system prompt for LLM analysis."""
        system_prompt = (
            f"You are an expert educational consultant specializing in teaching excellence. "
            f"Your task is to analyze comprehensive teaching reports and synthesize the MOST IMPORTANT "
            f"insights and recommendations that will have the greatest impact on teaching improvement.\n\n"

            f"You will receive two detailed analyses:\n"
            f"1. **Deep Pedagogical Analysis** - covering communication, engagement, pedagogical approach, and content delivery\n"
            f"2. **Storytelling Analysis** - covering narrative structure, character development, curiosity, emotional engagement, and coherence\n\n"

            f"Your role is to:\n"
            f"1. Identify the TOP 3-5 most significant strengths that should be preserved and amplified\n"
            f"2. Identify the TOP 3-5 most critical weaknesses that need immediate attention\n"
            f"3. Provide the MOST IMPACTFUL recommendations that will drive real improvement\n"
            f"4. Prioritize based on:\n"
            f"   - Impact on student learning outcomes\n"
            f"   - Feasibility of implementation\n"
            f"   - Alignment with teaching best practices\n"
            f"   - Evidence strength from the analyses\n\n"

            f"Here are the detailed analyses:\n\n"
            f"<deep_analysis>\n{self.deep_analysis}\n</deep_analysis>\n\n"
            f"<storytelling_analysis>\n{self.story_analysis}\n</storytelling_analysis>\n\n"
        )

        if self.output_analysis:
            system_prompt += f"<class_details>\n{self.output_analysis}\n</class_details>\n\n"

        system_prompt += (
            f"Output specifications:\n"
            f"- Language: {lan}\n"
            f"- Format: JSON only (no markdown, no extra text)\n"
            f"- Focus on actionable, specific, evidence-based insights\n"
            f"- Avoid generic advice - be specific to this instructor's context\n"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English"):
        """Compose the user prompt requesting smart insights."""
        self.user_prompt = (
            f"Analyze the provided teaching reports and create a smart insights summary.\n\n"

            f"Return a JSON object with this EXACT structure:\n"
            f"{{\n"
            f'  "overall_assessment": "One paragraph summarizing the instructor\'s overall performance",\n'
            f'  "key_message": "One sentence capturing the most important takeaway",\n'
            f'  "top_strength": {{\n'
            f'    "dimension": "Name of the dimension (e.g., Curiosity, Engagement)",\n'
            f'    "description": "What they did exceptionally well",\n'
            f'    "evidence": "Specific quote or example from the analysis"\n'
            f'  }},\n'
            f'  "preserve": [\n'
            f'    {{\n'
            f'      "dimension": "Dimension name",\n'
            f'      "strength": "What to keep doing",\n'
            f'      "why_important": "Why this matters for student learning",\n'
            f'      "evidence": "Supporting evidence"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "improve": [\n'
            f'    {{\n'
            f'      "dimension": "Dimension name",\n'
            f'      "weakness": "What needs improvement",\n'
            f'      "impact": "How this affects students",\n'
            f'      "recommendation": "Specific, actionable solution",\n'
            f'      "evidence": "Supporting evidence"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "priority_actions": [\n'
            f'    {{\n'
            f'      "action": "Specific action to take in next class",\n'
            f'      "expected_outcome": "What improvement this will bring",\n'
            f'      "difficulty": "easy/medium/hard"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "long_term_focus": "The ONE area that would have the biggest long-term impact if improved"\n'
            f"}}\n\n"

            f"Requirements:\n"
            f"- Include 3-4 items in 'preserve' array\n"
            f"- Include 3-4 items in 'improve' array\n"
            f"- Include 4-5 items in 'priority_actions' array\n"
            f"- Rank items by importance (most important first)\n"
            f"- Be specific and evidence-based\n"
            f"- Use language: {lan}\n"
            f"- Return ONLY valid JSON, no markdown fences\n"
        )

    def prepare_content(self, output_dir: str, lan="English"):
        """
        Prepare the content for LLM analysis.

        Args:
            output_dir: Directory containing the analysis files
            lan: Language for the output
        """
        self.load_analysis_files(output_dir)
        self.compose_system_prompt(lan)
        self.compose_user_prompt(lan)


def main():
    """Main entry point for testing."""
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Get language from config
    language = config.get("language", "English")

    # Get output directory
    from teacher_side.teacher_utils import get_output_dir
    output_dir = get_output_dir(config)

    logger.info(f"Generating smart insights from: {output_dir}")

    # Process analysis files
    t0 = time.time()
    llmproxy = TeacherReportSmartInsights(config)
    llmproxy.prepare_content(output_dir, lan=language)

    logger.info("Calling LLM to generate smart insights...")
    output = llmproxy.call_api()

    # Save output
    output_file = os.path.join(output_dir, "smart_insights.json")
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(output)

    logger.info(f"✅ Smart insights saved to: {output_file}")
    logger.info(f"Pipeline completed in {time.time() - t0:.3f}s")

    print("\n" + "="*80)
    print("SMART INSIGHTS:")
    print("="*80)
    print(output)


if __name__ == '__main__':
    main()
