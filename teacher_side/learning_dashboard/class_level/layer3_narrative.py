"""
Layer 3: LLM Narrative Generation
Converts structured Layer 2 evidence into human-readable markdown panels.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.utils import source_key

from ..common.models import Layer2Output
from ..common.config import LearningDashboardConfig
from .html_renderer import render_html_dashboard


class PromptBuilder:
    """Builds the LLM prompt from Layer 2 output."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def build_system_prompt(self, language: str = "Hebrew") -> str:
        """
        Build the system prompt for the LLM.

        Args:
            language: Output language (Hebrew or English)

        Returns:
            System prompt string
        """
        return f"""You are a teaching assistant generating a class report for a university lecturer.
You write in {language}.
You receive structured evidence from student data.
Your job is to surface only significant observations — not to fill every slot.

Rules:
- Never invent signals not in the evidence object.
- Write in NATURAL LANGUAGE - no technical terms like "SignalType.EVAL_FAILURE" or "evidence_strength: moderate"
- Instead write: "low evaluation scores", "many student queries", "weak answers", "confusion signals", etc.
- Evidence types to translate:
  * eval_failure_signals → "low evaluation scores" or "failed eval questions"
  * query_signals → "student queries to search/bot" or "many questions asked"
  * inclass_question_signals → "in-class questions" or "student confusion during lecture"
  * surface_learning_rate → "weak/shallow understanding" or "memorization without depth"
  * misconception_signals → "conceptual misunderstandings" or "wrong mental models"
- Each issue must include one specific, actionable next-lesson suggestion.
- Worked-well items must say WHY it worked (what signal supports it), not just that it did.
- Gap items must state direction clearly: over-invested, under-taught, or assessed-not-absorbed.
- Do not repeat the same concept across Issues and Gap unless the insight is genuinely different:
    Issues = what students failed to learn
    Gap    = where teaching investment and learning outcome diverged
- If issues=[] → write "No significant issues detected in available data."
- If worked_well=[] → write "Insufficient data to confirm what worked this lesson."
- If gaps=[] → write "No significant teaching-learning mismatches detected."
- If out_of_scope is non-empty → include a brief note in Quick Snapshot only.
- Keep it concise and actionable. Focus on what the teacher needs to know.
"""

    def build_user_prompt(self, layer2_output: Layer2Output) -> str:
        """
        Build the user prompt with Layer 2 evidence.

        Args:
            layer2_output: Layer 2 output object

        Returns:
            User prompt string
        """
        # Convert to dict for JSON serialization
        evidence_json = json.dumps(layer2_output.to_dict(), ensure_ascii=False, indent=2)

        prompt = f"""Here is the evidence object for this lesson:

{evidence_json}

Generate the 4 panels in this exact markdown format:

## Quick Snapshot
**Lesson**: {layer2_output.lecture_name}
**Data**: {layer2_output.reliability.eval_participants} students evaluated · {layer2_output.reliability.query_participants} searched · Reliability: {layer2_output.reliability.flag}
**Shape**: {layer2_output.lesson_shape.concept_count} concepts · {layer2_output.lesson_shape.total_minutes:.0f} min · quiz avg {layer2_output.lesson_shape.lesson_quiz_avg:.0f} → eval avg {layer2_output.lesson_shape.lesson_eval_avg:.0f} ({layer2_output.lesson_shape.lesson_gap_flag})
> [one-line characterization of what this lesson's data shows overall]
{f"**Also noted**: students searched for {len(layer2_output.out_of_scope)} topics not covered in this lesson" if layer2_output.out_of_scope else ""}

## Issues & What To Do
{"No significant issues detected in available data." if not layer2_output.issues else ""}
{'''| Issue | Why we think so | What to do |
| ----- | --------------- | ---------- |
| [use issue_title field] | [translate evidence to natural language - eval failures + queries + inclass questions, mention difficult_eval_questions if available] | [specific actionable suggestion] |''' if layer2_output.issues else ""}

## What Worked Well
{"Insufficient data to confirm what worked this lesson." if not layer2_output.worked_well else "[for each:]"}
{'''### [concept]
[why signal + what to repeat]''' if layer2_output.worked_well else ""}

## Teaching vs Learning Gap
{"No significant teaching-learning mismatches detected." if not layer2_output.gaps else "[for each:]"}
{'''### [concept] — [direction]
[2 sentences: investment vs outcome, what it implies]''' if layer2_output.gaps else ""}
"""

        return prompt


class LLMCaller:
    """Handles LLM API calls via OpenRouter with retry logic."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        # Load OpenRouter API key
        api_key = source_key("OPEN_ROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPEN_ROUTER_API_KEY not found in ~/.bashrc")

        # Initialize OpenAI client pointed at OpenRouter
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> str:
        """
        Call LLM via OpenRouter with retry logic.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            max_retries: Maximum number of retries

        Returns:
            LLM response text

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                if self.config.verbose:
                    print(f"Calling LLM via OpenRouter (attempt {attempt + 1}/{max_retries})...")

                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://aarontheowl.com",
                        "X-Title": "Aaron Learning Dashboard",
                    },
                    model=self.config.llm.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        },
                    ],
                    max_tokens=self.config.llm.max_tokens,
                    temperature=self.config.llm.temperature,
                    top_p=0.8,
                )

                # Extract text from response
                text = completion.choices[0].message.content.strip()

                # Remove thinking tags if present
                import re
                text = re.sub(r'◁think▷.*?◁/think▷', '', text, flags=re.S).strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()

                if self.config.verbose:
                    print(f"✅ LLM call successful ({len(text)} chars)")

                return text

            except Exception as e:
                if self.config.verbose:
                    print(f"❌ LLM call failed: {e}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    if self.config.verbose:
                        print(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"LLM call failed after {max_retries} attempts: {e}")


class MarkdownParser:
    """Parses LLM markdown output into structured panels."""

    def parse_panels(self, markdown_text: str) -> dict:
        """
        Parse markdown output into 4 panels.

        Args:
            markdown_text: Raw markdown from LLM

        Returns:
            Dict with keys: quick_snapshot, issues, worked_well, gaps
        """
        panels = {
            'quick_snapshot': '',
            'issues': '',
            'worked_well': '',
            'gaps': '',
        }

        # Split by ## headers
        sections = markdown_text.split('##')

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract section title and content
            lines = section.split('\n', 1)
            if len(lines) < 2:
                continue

            title = lines[0].strip().lower()
            content = lines[1].strip()

            # Map to panel keys
            if 'quick snapshot' in title or 'snapshot' in title:
                panels['quick_snapshot'] = content
            elif 'issues' in title or 'what to do' in title:
                panels['issues'] = content
            elif 'worked well' in title or 'what worked' in title:
                panels['worked_well'] = content
            elif 'gap' in title or 'teaching vs learning' in title:
                panels['gaps'] = content

        return panels


class Layer3Pipeline:
    """Main pipeline for Layer 3: LLM narrative generation."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.prompt_builder = PromptBuilder(config)
        self.llm_caller = LLMCaller(config)
        self.parser = MarkdownParser()

    def run(
        self,
        layer2_output: Layer2Output,
        output_dir: Optional[Path] = None,
    ) -> dict:
        """
        Run the complete Layer 3 pipeline.

        Args:
            layer2_output: Layer 2 output object
            output_dir: Directory to save outputs

        Returns:
            Dict with:
                - 'markdown': Full markdown output
                - 'panels': Dict of parsed panels
                - 'quick_snapshot': Quick snapshot text
                - 'issues': Issues panel text
                - 'worked_well': Worked well panel text
                - 'gaps': Gaps panel text
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "layer3"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Check reliability flag
        if layer2_output.reliability.flag == "insufficient":
            if self.config.verbose:
                print("⚠️  Insufficient data - skipping LLM call")

            return self._generate_insufficient_data_output(layer2_output, output_dir)

        # Build prompts
        if self.config.verbose:
            print("Building LLM prompts...")

        system_prompt = self.prompt_builder.build_system_prompt(
            language=self.config.llm.output_language
        )
        user_prompt = self.prompt_builder.build_user_prompt(layer2_output)

        # Call LLM
        markdown_output = self.llm_caller.call_llm(system_prompt, user_prompt)

        # Parse panels
        if self.config.verbose:
            print("Parsing markdown output...")

        panels = self.parser.parse_panels(markdown_output)

        # Save outputs
        self._save_outputs(markdown_output, panels, layer2_output, output_dir)

        return {
            'markdown': markdown_output,
            'panels': panels,
            'quick_snapshot': panels['quick_snapshot'],
            'issues': panels['issues'],
            'worked_well': panels['worked_well'],
            'gaps': panels['gaps'],
        }

    def _generate_insufficient_data_output(
        self,
        layer2_output: Layer2Output,
        output_dir: Path,
    ) -> dict:
        """
        Generate output for insufficient data case (no LLM call).

        Args:
            layer2_output: Layer 2 output
            output_dir: Output directory

        Returns:
            Dict with markdown and panels
        """
        markdown = f"""## Quick Snapshot
**Lesson**: {layer2_output.lecture_name}
**Data**: {layer2_output.reliability.eval_participants} students evaluated · {layer2_output.reliability.query_participants} searched · Reliability: {layer2_output.reliability.flag}
> Insufficient evaluation data to generate insights. Need at least 2 students to complete evaluation.

## Issues & What To Do
Data insufficient for analysis.

## What Worked Well
Data insufficient for analysis.

## Teaching vs Learning Gap
Data insufficient for analysis.
"""

        panels = self.parser.parse_panels(markdown)
        self._save_outputs(markdown, panels, layer2_output, output_dir)

        return {
            'markdown': markdown,
            'panels': panels,
            'quick_snapshot': panels['quick_snapshot'],
            'issues': panels['issues'],
            'worked_well': panels['worked_well'],
            'gaps': panels['gaps'],
        }

    def _save_outputs(
        self,
        markdown: str,
        panels: dict,
        layer2_output: Layer2Output,
        output_dir: Path,
    ):
        """Save Layer 3 outputs."""
        # Save full markdown
        markdown_path = output_dir / "dashboard_output.md"
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        if self.config.verbose:
            print(f"Saved markdown to {markdown_path}")

        # Save parsed panels as JSON
        panels_path = output_dir / "dashboard_panels.json"
        with open(panels_path, 'w', encoding='utf-8') as f:
            json.dump(panels, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved panels to {panels_path}")

        # Save complete output (Layer 2 + Layer 3)
        complete_output = {
            'lecture_id': layer2_output.lecture_id,
            'lecture_name': layer2_output.lecture_name,
            'layer2_data': layer2_output.to_dict(),
            'markdown_output': markdown,
            'panels': panels,
        }

        complete_path = output_dir / "complete_dashboard.json"
        with open(complete_path, 'w', encoding='utf-8') as f:
            json.dump(complete_output, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"Saved complete dashboard to {complete_path}")

        # Generate HTML dashboard
        html_path = output_dir / "dashboard.html"
        render_html_dashboard(
            panels=panels,
            lecture_name=layer2_output.lecture_name,
            output_path=html_path,
        )

        if self.config.verbose:
            print(f"Saved HTML dashboard to {html_path}")