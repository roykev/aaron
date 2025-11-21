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

from utils.kimi_utils import AnthropicProxy, OpenRouterProxy
from utils.utils import get_logger


class TeacherReportSmartInsights(AnthropicProxy):
    """
    Analyzes existing teacher report outputs (deep.txt and story.txt) using an LLM
    to identify and synthesize the most important insights and recommendations.
    Uses Anthropic's Claude (default).
    """

    def __init__(self, config: Dict[str, Any], api_key: str = None, logger=None):
        super().__init__(config, api_key, logger)
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
            f"You are a supportive educational consultant specializing in teaching excellence. "
            f"Your task is to analyze comprehensive teaching reports and synthesize the MOST IMPORTANT "
            f"insights and recommendations in a positive, constructive manner that celebrates strengths "
            f"and gently guides improvement.\n\n"

            f"You will receive two detailed analyses:\n"
            f"1. **Deep Pedagogical Analysis** - covering communication, engagement, pedagogical approach, and content delivery\n"
            f"2. **Storytelling Analysis** - covering narrative structure, character development, curiosity, emotional engagement, and coherence\n\n"

            f"Your role is to:\n"
            f"1. Celebrate and highlight the TOP 3-5 most significant strengths that are driving student success\n"
            f"2. Identify 3-5 growth opportunities - areas where small improvements can have big impact\n"
            f"3. Frame everything positively: use encouraging language like 'opportunity to enhance', 'can become even stronger', 'potential to elevate'\n"
            f"4. Avoid harsh criticism - use gentle, constructive language\n"
            f"5. Focus on what's working well BEFORE discussing areas for growth\n"
            f"6. Prioritize based on:\n"
            f"   - Positive impact on student learning\n"
            f"   - Realistic feasibility\n"
            f"   - Building on existing strengths\n"
            f"   - Evidence from the analyses\n\n"

            f"IMPORTANT TONE GUIDELINES:\n"
            f"- Start with appreciation and recognition of effort\n"
            f"- Use phrases like: 'opportunity to', 'could be enhanced by', 'would benefit from', 'consider trying'\n"
            f"- Avoid negative words like: 'weakness', 'lacking', 'failure', 'poor', 'inadequate'\n"
            f"- Frame challenges as growth opportunities\n"
            f"- Be specific but kind\n"
            f"- Emphasize the instructor's existing foundation of strengths\n\n"

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
            f"- Tone: Positive, encouraging, supportive, constructive\n"
            f"- Focus on actionable, specific, evidence-based insights\n"
            f"- Avoid generic advice - be specific to this instructor's context\n"
            f"- Never use specific percentages or exact numbers in expected outcomes (avoid: '40% reduction', '5 more questions')\n"
            f"- Use qualitative improvements instead (use: 'noticeably better', 'improved clarity', 'enhanced engagement')\n"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English"):
        """Compose the user prompt requesting smart insights."""
        self.user_prompt = (
            f"Analyze the provided teaching reports and create a smart insights summary with a POSITIVE, ENCOURAGING tone.\n\n"

            f"Return a JSON object with this EXACT structure:\n"
            f"{{\n"
            f'  "overall_assessment": "One warm, appreciative paragraph celebrating the instructor\'s strengths and gently mentioning growth opportunities",\n'
            f'  "key_message": "One positive, actionable sentence capturing the path forward",\n'
            f'  "top_strength": {{\n'
            f'    "dimension": "Name of the dimension (e.g., Curiosity, Engagement)",\n'
            f'    "description": "What they did exceptionally well - be specific and celebratory",\n'
            f'    "evidence": "Specific quote or example from the analysis"\n'
            f'  }},\n'
            f'  "preserve": [\n'
            f'    {{\n'
            f'      "dimension": "Dimension name",\n'
            f'      "strength": "What to keep doing - celebrate this success",\n'
            f'      "why_important": "Why this is making a positive difference for students",\n'
            f'      "evidence": "Supporting evidence"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "growth_opportunities": [\n'
            f'    {{\n'
            f'      "dimension": "Dimension name",\n'
            f'      "opportunity": "Frame this as an opportunity for enhancement (avoid negative language)",\n'
            f'      "potential_benefit": "The positive impact this could have on students",\n'
            f'      "suggestion": "A gentle, specific, actionable way to build on existing strengths",\n'
            f'      "evidence": "Supporting evidence"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "priority_actions": [\n'
            f'    {{\n'
            f'      "action": "Specific action to try in next class - phrase positively",\n'
            f'      "expected_outcome": "What positive change this could bring (use QUALITATIVE language only - NO percentages or specific numbers)",\n'
            f'      "difficulty": "easy/medium/hard"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "long_term_opportunity": "The ONE area that offers the most exciting potential for growth and impact"\n'
            f"}}\n\n"

            f"Requirements:\n"
            f"- Include 3-4 items in 'preserve' array\n"
            f"- Include 3-4 items in 'growth_opportunities' array (NOT 'improve')\n"
            f"- Include 4-5 items in 'priority_actions' array\n"
            f"- Rank items by importance and feasibility (most impactful first)\n"
            f"- Be specific and evidence-based\n"
            f"- Use ONLY positive, constructive language throughout\n"
            f"- NEVER use words like: weakness, lacking, poor, failure, inadequate, insufficient\n"
            f"- ALWAYS use words like: opportunity, enhance, elevate, build on, consider, could benefit from\n"
            f"- For expected_outcome: use qualitative descriptions (e.g., 'clearer understanding', 'more engaged students', 'better retention') "
            f"NEVER exact numbers (avoid: '40% reduction', '5 more questions', 'increase by 30%')\n"
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


class TeacherReportSmartInsightsOR(OpenRouterProxy):
    """
    Smart insights analysis using OpenRouter (secondary option).
    """

    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1", logger=None):
        super().__init__(config, api_key, base_url, logger)
        self.deep_analysis = None
        self.story_analysis = None
        self.output_analysis = None
    
    # Share the same methods with TeacherReportSmartInsights
    load_analysis_files = TeacherReportSmartInsights.load_analysis_files
    compose_system_prompt = TeacherReportSmartInsights.compose_system_prompt
    compose_user_prompt = TeacherReportSmartInsights.compose_user_prompt
    prepare_content = TeacherReportSmartInsights.prepare_content


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
