"""
Course-Level Layer 3: LLM Narrative Generation

Converts structured Layer 2 course evidence into human-readable markdown panels.
Generates a 5-panel course dashboard:
1. Course Snapshot - overall engagement and performance
2. What Students Struggle With - recurring concepts + problematic lessons
3. What Consistently Worked - successful topics + good lessons
4. Teaching vs Learning Gap - systemic gaps
5. Prerequisite & Knowledge Gaps - foundational gaps

Outputs: JSON, Markdown, and HTML
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

from ..common.config import LearningDashboardConfig
from .layer2_ranking import CourseLayer2Output


class CoursePromptBuilder:
    """Builds the LLM prompt for course-level narrative from Layer 2 output."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config

    def build_system_prompt(self, language: str = "Hebrew") -> str:
        """Build the system prompt for course-level LLM generation."""
        return f"""You are a teaching assistant generating a COURSE-LEVEL report for a university lecturer.
You write in {language}.
You receive structured evidence aggregated across MULTIPLE LECTURES in the course.
Your job is to surface only significant cross-lesson patterns using POSITIVE, GROWTH-ORIENTED language that teachers will embrace.

CRITICAL OUTPUT FORMAT: You MUST return a valid JSON object with this exact structure:
{{
  "course_snapshot": {{
    "summary": "2-3 sentence summary with POSITIVE, STRENGTHS-FIRST framing...",
    "cross_segment_analysis": "Optional: Analysis of which segments struggle with concepts (only if engagement data available)"
  }},
  "struggles": {{
    "overview": "Optional: Segment-specific support needs overview (only if engagement data available)",
    "recurring_concepts": [
      {{
        "topic": "concept name",
        "lectures": ["lecture1", "lecture2"],
        "evidence": "X queries, Y revisits, eval failures...",
        "recommendation": "1 sentence recommendation"
      }}
    ],
    "problematic_lessons": [
      {{
        "lesson_number": "שיעור 4",
        "topic": "lecture name/topic",
        "eval_avg": "lesson eval vs course eval",
        "evidence": "low eval, high queries, surface learning...",
        "recommendation": "1 sentence recommendation"
      }}
    ]
  }},
  "successes": {{
    "successful_topics": [
      {{
        "topic": "concept name",
        "lectures": ["lecture1", "lecture2"],
        "success_rate": "85%",
        "why_it_worked": "explanation of pedagogy"
      }}
    ],
    "good_lessons": [
      {{
        "lesson_number": "שיעור 3",
        "topic": "lesson name",
        "eval_avg": "lesson eval vs course eval",
        "positive_signals": "high eval, low queries, deep learning...",
        "what_to_repeat": "teaching pattern to replicate"
      }}
    ]
  }},
  "gaps": {{
    "systemic_gaps": [
      {{
        "name": "gap name",
        "description": "1-2 paragraphs with CONCRETE EXAMPLES: which lectures, specific topics, numbers...",
        "recommendation": "how to address"
      }}
    ]
  }},
  "prerequisites": {{
    "prerequisite_gaps": [
      {{
        "topic": "gap topic",
        "students": "N students",
        "lectures": "appeared in X lectures",
        "examples": ["query1", "query2"],
        "recommendation": "what to address"
      }}
    ]
  }}
}}

Rules:
- Output ONLY valid JSON, no markdown formatting
- Never invent signals not in the evidence object
- Use POSITIVE, SUPPORTIVE tone - frame challenges as growth opportunities, not failures
- Write in NATURAL LANGUAGE - no technical terms like "recurrence_score" or "problem_signal_count"
- Instead write: "appeared in 3 lectures", "students sought clarification", "engaged deeply", etc.
- Focus on PATTERNS ACROSS LECTURES, not single-lesson issues
- Always start with strengths before discussing areas for improvement
- Frame struggles as "areas where students need additional support" not "problems"
- Frame gaps as "opportunities to deepen understanding" not "failures"
- Each recurring concept must mention which lectures it appeared in
- Each problematic lesson must explain evidence sources (queries, eval, quiz, revisits)
- Each good lesson must explain WHY it succeeded (positive signals)
- Consistent successes must show CROSS-LESSON patterns (≥2 lectures)
- Systemic gaps are COURSE-WIDE patterns - explain using quiz vs eval, teaching time vs results
- Prerequisite gaps indicate missing foundations students lack
- If no data for a section, use empty arrays [] or appropriate default text
- Keep it concise, actionable, and STRATEGIC (course-level, not lesson-level).
- IMPORTANT: Generate COMPLETE output for all 5 panels. Do not truncate or cut off sections.
"""

    def build_user_prompt(self, layer2_output: CourseLayer2Output) -> str:
        """Build the user prompt with Layer 2 evidence."""
        # Convert to dict for JSON serialization
        evidence_json = json.dumps(layer2_output.to_dict(), ensure_ascii=False, indent=2)

        # Build context about the course for the LLM
        context_info = f"""**Course Context**:
- Progress: {layer2_output.lectures_covered}/{layer2_output.total_lectures} lectures analyzed
- Engaged Students: {layer2_output.engaged_n} students
- Course Averages: Quiz {layer2_output.course_quiz_avg:.1f} · Eval {layer2_output.course_eval_avg:.1f}
"""

        if layer2_output.engagement:
            context_info += f"""- Engagement Rate: {layer2_output.engagement['engagement_rate']*100:.1f}%
- EXCEL: {layer2_output.engagement['excel_n']} students ({layer2_output.engagement['excel_pct']*100:.1f}%)
- MIDDLE: {layer2_output.engagement['middle_n']} students ({layer2_output.engagement['middle_pct']*100:.1f}%)
- STRUGGLES: {layer2_output.engagement['struggles_n']} students ({layer2_output.engagement['struggles_pct']*100:.1f}%)
"""

        prompt = f"""{context_info}

**Layer 2 Evidence Data**:

{evidence_json}

Generate a valid JSON object following the structure defined in the system prompt. Analyze all the data above and create narratives for all 5 panels."""

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
        """Call LLM via OpenRouter with retry logic."""
        for attempt in range(max_retries):
            try:
                if self.config.verbose:
                    print(f"Calling LLM via OpenRouter (attempt {attempt + 1}/{max_retries})...")

                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://aarontheowl.com",
                        "X-Title": "Aaron Learning Dashboard - Course Report",
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


class JSONParser:
    """Parses LLM JSON output into structured data."""

    def parse_json(self, json_text: str) -> dict:
        """
        Parse JSON output from LLM.

        Args:
            json_text: Raw LLM response (may include markdown code blocks)

        Returns:
            Parsed JSON dictionary
        """
        import re

        # Remove markdown code blocks if present
        # LLMs sometimes wrap JSON in ```json ... ```
        cleaned = json_text.strip()
        if cleaned.startswith('```'):
            # Extract content between ``` markers
            match = re.search(r'```(?:json)?\s*\n(.*?)```', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()

        # Parse JSON
        try:
            data = json.loads(cleaned)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM JSON output: {e}\nOutput was: {cleaned[:500]}...")


class MarkdownGenerator:
    """Generates Markdown from structured JSON data."""

    def __init__(self, layer2_output: CourseLayer2Output):
        self.layer2_output = layer2_output

    def generate_markdown(self, data: dict) -> str:
        """Generate complete markdown dashboard from JSON data."""
        sections = []

        # Course Snapshot
        sections.append(self._generate_snapshot(data.get('course_snapshot', {})))

        # Struggles
        sections.append(self._generate_struggles(data.get('struggles', {})))

        # Successes
        sections.append(self._generate_successes(data.get('successes', {})))

        # Gaps
        sections.append(self._generate_gaps(data.get('gaps', {})))

        # Prerequisites
        sections.append(self._generate_prerequisites(data.get('prerequisites', {})))

        return '\n\n'.join(sections)

    def _generate_snapshot(self, snapshot: dict) -> str:
        """Generate Course Snapshot section."""
        lines = ['## Course Snapshot']
        lines.append(f"**Course Progress**: {self.layer2_output.lectures_covered}/{self.layer2_output.total_lectures} lectures analyzed")
        lines.append(f"**Engaged Students**: {self.layer2_output.engaged_n} students")
        lines.append(f"**Course Averages**: Quiz {self.layer2_output.course_quiz_avg:.1f} · Eval {self.layer2_output.course_eval_avg:.1f}")

        # Add engagement table if available
        if self.layer2_output.engagement:
            eng = self.layer2_output.engagement
            lines.append(f"**Engagement Rate**: {eng['engagement_rate']*100:.1f}%")
            lines.append("")
            lines.append("**Student Segments**:")
            lines.append("")
            lines.append("| סגמנט (Segment) | מספר תלמידים (Students) | אחוז (Percentage) | טווח ציונים (Score Range) |")
            lines.append("|-----------------|-------------------------|-------------------|---------------------------|")
            lines.append(f"| EXCEL | {eng['excel_n']} | {eng['excel_pct']*100:.1f}% | ≥75% |")
            lines.append(f"| MIDDLE | {eng['middle_n']} | {eng['middle_pct']*100:.1f}% | 45-75% |")
            lines.append(f"| STRUGGLES | {eng['struggles_n']} | {eng['struggles_pct']*100:.1f}% | <45% |")

        lines.append("")
        lines.append(f"> {snapshot.get('summary', 'אין מידע זמין')}")

        if snapshot.get('cross_segment_analysis'):
            lines.append("")
            lines.append("### Cross-Segment Analysis")
            lines.append(snapshot['cross_segment_analysis'])

        return '\n'.join(lines)

    def _generate_struggles(self, struggles: dict) -> str:
        """Generate Struggles section."""
        lines = ['## Areas Where Students Need Additional Support']

        if struggles.get('overview'):
            lines.append("")
            lines.append("### Overview")
            lines.append(struggles['overview'])

        # Recurring concepts
        recurring = struggles.get('recurring_concepts', [])
        if recurring:
            lines.append("")
            lines.append("### Recurring Concepts (Cross-Lesson)")
            lines.append("")
            lines.append("| נושא (Topic) | שיעורים (Lectures) | עדות (Evidence) | המלצה (Recommendation) |")
            lines.append("|--------------|-------------------|----------------|----------------------|")
            for concept in recurring:
                topic = concept.get('topic', '')
                lectures = ', '.join(concept.get('lectures', []))
                evidence = concept.get('evidence', '')
                recommendation = concept.get('recommendation', '')
                lines.append(f"| {topic} | {lectures} | {evidence} | {recommendation} |")
        else:
            lines.append("")
            lines.append("Students are engaging well with all course concepts.")

        # Problematic lessons
        problematic = struggles.get('problematic_lessons', [])
        if problematic:
            lines.append("")
            lines.append("### Lessons Needing Enhancement")
            lines.append("")
            lines.append("| שיעור (Lesson) | נושא (Topic) | ממוצע הערכה (Eval) | עדות (Evidence) | המלצה (Recommendation) |")
            lines.append("|---------------|-------------|-------------------|----------------|----------------------|")
            for lesson in problematic:
                lesson_num = lesson.get('lesson_number', '')
                topic = lesson.get('topic', '')
                eval_avg = lesson.get('eval_avg', '')
                evidence = lesson.get('evidence', '')
                recommendation = lesson.get('recommendation', '')
                lines.append(f"| {lesson_num} | {topic} | {eval_avg} | {evidence} | {recommendation} |")

        return '\n'.join(lines)

    def _generate_successes(self, successes: dict) -> str:
        """Generate Successes section."""
        lines = ['## What Consistently Worked']

        # Successful topics
        topics = successes.get('successful_topics', [])
        if topics:
            lines.append("")
            lines.append("### Successful Topics (Cross-Lesson)")
            lines.append("")
            lines.append("| נושא (Topic) | שיעורים (Lectures) | אחוז הצלחה (Success Rate) | למה זה עבד (Why It Worked) |")
            lines.append("|--------------|-------------------|--------------------------|---------------------------|")
            for topic in topics:
                name = topic.get('topic', '')
                lectures = ', '.join(topic.get('lectures', []))
                rate = topic.get('success_rate', '')
                why = topic.get('why_it_worked', '')
                lines.append(f"| {name} | {lectures} | {rate} | {why} |")

        # Good lessons
        lessons = successes.get('good_lessons', [])
        if lessons:
            lines.append("")
            lines.append("### Good Lessons")
            lines.append("")
            lines.append("| שיעור (Lesson) | נושא (Topic) | ממוצע הערכה (Eval) | איתותים חיוביים (Positive Signals) | מה לחזור על (What to Repeat) |")
            lines.append("|---------------|-------------|-------------------|-----------------------------------|------------------------------|")
            for lesson in lessons:
                lesson_num = lesson.get('lesson_number', '')
                topic = lesson.get('topic', '')
                eval_avg = lesson.get('eval_avg', '')
                signals = lesson.get('positive_signals', '')
                repeat = lesson.get('what_to_repeat', '')
                lines.append(f"| {lesson_num} | {topic} | {eval_avg} | {signals} | {repeat} |")

        if not topics and not lessons:
            lines.append("")
            lines.append("Insufficient data to identify cross-lesson teaching successes.")

        return '\n'.join(lines)

    def _generate_gaps(self, gaps: dict) -> str:
        """Generate Systemic Gaps section."""
        lines = ['## Opportunities to Align Teaching Emphasis with Learning Outcomes']

        systemic = gaps.get('systemic_gaps', [])
        if systemic:
            for gap in systemic:
                lines.append("")
                lines.append(f"**{gap.get('name', '')}**: {gap.get('description', '')}")
                if gap.get('recommendation'):
                    lines.append(f"\n**המלצה**: {gap['recommendation']}")
        else:
            lines.append("")
            lines.append("Teaching emphasis aligns well with student learning outcomes.")

        return '\n'.join(lines)

    def _generate_prerequisites(self, prerequisites: dict) -> str:
        """Generate Prerequisites section."""
        lines = ['## Prerequisite & Knowledge Gaps']

        gaps = prerequisites.get('prerequisite_gaps', [])
        if gaps:
            lines.append("")
            lines.append("| נושא (Topic) | מספר תלמידים (Students) | שיעורים (Lectures) | דוגמאות (Examples) | המלצה (Recommendation) |")
            lines.append("|--------------|------------------------|-------------------|-------------------|----------------------|")
            for gap in gaps:
                topic = gap.get('topic', '')
                students = gap.get('students', '')
                lectures = gap.get('lectures', '')
                examples = ', '.join(gap.get('examples', []))
                recommendation = gap.get('recommendation', '')
                lines.append(f"| {topic} | {students} | {lectures} | {examples} | {recommendation} |")
        else:
            lines.append("")
            lines.append("No significant prerequisite knowledge gaps detected.")

        return '\n'.join(lines)


class HTMLGenerator:
    """Generates HTML from structured JSON data."""

    def __init__(self, layer2_output: CourseLayer2Output):
        self.layer2_output = layer2_output

    def generate_html(self, data: dict) -> str:
        """Generate complete HTML dashboard from JSON data."""
        # Generate HTML for each panel
        snapshot_html = self._generate_snapshot_html(data.get('course_snapshot', {}))
        struggles_html = self._generate_struggles_html(data.get('struggles', {}))
        successes_html = self._generate_successes_html(data.get('successes', {}))
        gaps_html = self._generate_gaps_html(data.get('gaps', {}))
        prerequisites_html = self._generate_prerequisites_html(data.get('prerequisites', {}))

        html_content = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Dashboard - Run {self.layer2_output.run_number}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            direction: rtl;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        .header .stats {{
            display: flex;
            gap: 30px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        .header .stat {{
            background: rgba(255,255,255,0.2);
            padding: 10px 15px;
            border-radius: 5px;
        }}
        .panel {{
            background: white;
            padding: 30px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .panel-title {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin: 0 0 20px 0;
            font-size: 1.5em;
            font-weight: bold;
        }}
        .panel h3 {{
            color: #764ba2;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        .panel h4 {{
            color: #555;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        .panel p {{
            margin: 10px 0;
        }}
        .panel ul, .panel ol {{
            margin: 10px 0;
            padding-right: 25px;
        }}
        .panel li {{
            margin: 5px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: right;
            border: 1px solid #ddd;
        }}
        th {{
            background-color: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        tr:hover {{
            background-color: #f0f0f0;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        blockquote {{
            border-right: 4px solid #667eea;
            padding-right: 15px;
            margin: 20px 0;
            color: #555;
            font-style: italic;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
        }}
        strong {{
            color: #333;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 דוח קורס - ריצה {self.layer2_output.run_number}</h1>
        <div class="stats">
            <div class="stat">
                <strong>{self.layer2_output.lectures_covered}/{self.layer2_output.total_lectures}</strong> שיעורים נותחו
            </div>
            <div class="stat">
                <strong>{self.layer2_output.engaged_n}</strong> סטודנטים מעורבים
            </div>
            <div class="stat">
                ממוצע קוויז: <strong>{self.layer2_output.course_quiz_avg:.1f}</strong>
            </div>
            <div class="stat">
                ממוצע הערכה: <strong>{self.layer2_output.course_eval_avg:.1f}</strong>
            </div>
        </div>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">תאריך: {self.layer2_output.run_date}</p>
    </div>

    <div class="panel">
        <div class="panel-title">📸 תמונת מצב כללית</div>
        {snapshot_html}
    </div>

    <div class="panel">
        <div class="panel-title">⚠️  תחומים שבהם תלמידים זקוקים לתמיכה נוספת</div>
        {struggles_html}
    </div>

    <div class="panel">
        <div class="panel-title">✅ מה עבד באופן עקבי</div>
        {successes_html}
    </div>

    <div class="panel">
        <div class="panel-title">📉 הזדמנויות ליישור הדגש בהוראה עם תוצאות הלמידה</div>
        {gaps_html}
    </div>

    <div class="panel">
        <div class="panel-title">📚 פערי ידע בסיסי</div>
        {prerequisites_html}
    </div>

    <div class="footer">
        <p>נוצר על ידי Aaron Learning Dashboard | {self.layer2_output.run_date}</p>
    </div>
</body>
</html>
"""
        return html_content

    def _generate_snapshot_html(self, snapshot: dict) -> str:
        """Generate HTML for Course Snapshot."""
        lines = []

        # Basic stats
        lines.append(f"<p><strong>Course Progress</strong>: {self.layer2_output.lectures_covered}/{self.layer2_output.total_lectures} lectures analyzed</p>")
        lines.append(f"<p><strong>Engaged Students</strong>: {self.layer2_output.engaged_n} students</p>")
        lines.append(f"<p><strong>Course Averages</strong>: Quiz {self.layer2_output.course_quiz_avg:.1f} · Eval {self.layer2_output.course_eval_avg:.1f}</p>")

        # Engagement table
        if self.layer2_output.engagement:
            eng = self.layer2_output.engagement
            lines.append(f"<p><strong>Engagement Rate</strong>: {eng['engagement_rate']*100:.1f}%</p>")
            lines.append("<p><strong>Student Segments</strong>:</p>")
            lines.append("<table>")
            lines.append("<tr><th>סגמנט (Segment)</th><th>מספר תלמידים (Students)</th><th>אחוז (Percentage)</th><th>טווח ציונים (Score Range)</th></tr>")
            lines.append(f"<tr><td>EXCEL</td><td>{eng['excel_n']}</td><td>{eng['excel_pct']*100:.1f}%</td><td>≥75%</td></tr>")
            lines.append(f"<tr><td>MIDDLE</td><td>{eng['middle_n']}</td><td>{eng['middle_pct']*100:.1f}%</td><td>45-75%</td></tr>")
            lines.append(f"<tr><td>STRUGGLES</td><td>{eng['struggles_n']}</td><td>{eng['struggles_pct']*100:.1f}%</td><td>&lt;45%</td></tr>")
            lines.append("</table>")

        # Summary
        lines.append(f"<blockquote>{snapshot.get('summary', 'אין מידע זמין')}</blockquote>")

        # Cross-segment analysis
        if snapshot.get('cross_segment_analysis'):
            lines.append("<h3>Cross-Segment Analysis</h3>")
            lines.append(f"<p>{snapshot['cross_segment_analysis']}</p>")

        return '\n'.join(lines)

    def _generate_struggles_html(self, struggles: dict) -> str:
        """Generate HTML for Struggles section."""
        lines = []

        if struggles.get('overview'):
            lines.append("<h3>Overview</h3>")
            lines.append(f"<p>{struggles['overview']}</p>")

        # Recurring concepts
        recurring = struggles.get('recurring_concepts', [])
        if recurring:
            lines.append("<h3>Recurring Concepts (Cross-Lesson)</h3>")
            lines.append("<table>")
            lines.append("<tr><th>נושא (Topic)</th><th>שיעורים (Lectures)</th><th>עדות (Evidence)</th><th>המלצה (Recommendation)</th></tr>")
            for concept in recurring:
                topic = concept.get('topic', '')
                lectures = ', '.join(concept.get('lectures', []))
                evidence = concept.get('evidence', '')
                recommendation = concept.get('recommendation', '')
                lines.append(f"<tr><td>{topic}</td><td>{lectures}</td><td>{evidence}</td><td>{recommendation}</td></tr>")
            lines.append("</table>")
        else:
            lines.append("<p>Students are engaging well with all course concepts.</p>")

        # Problematic lessons
        problematic = struggles.get('problematic_lessons', [])
        if problematic:
            lines.append("<h3>Lessons Needing Enhancement</h3>")
            lines.append("<table>")
            lines.append("<tr><th>שיעור (Lesson)</th><th>נושא (Topic)</th><th>ממוצע הערכה (Eval)</th><th>עדות (Evidence)</th><th>המלצה (Recommendation)</th></tr>")
            for lesson in problematic:
                lesson_num = lesson.get('lesson_number', '')
                topic = lesson.get('topic', '')
                eval_avg = lesson.get('eval_avg', '')
                evidence = lesson.get('evidence', '')
                recommendation = lesson.get('recommendation', '')
                lines.append(f"<tr><td>{lesson_num}</td><td>{topic}</td><td>{eval_avg}</td><td>{evidence}</td><td>{recommendation}</td></tr>")
            lines.append("</table>")

        return '\n'.join(lines)

    def _generate_successes_html(self, successes: dict) -> str:
        """Generate HTML for Successes section."""
        lines = []

        # Successful topics
        topics = successes.get('successful_topics', [])
        if topics:
            lines.append("<h3>Successful Topics (Cross-Lesson)</h3>")
            lines.append("<table>")
            lines.append("<tr><th>נושא (Topic)</th><th>שיעורים (Lectures)</th><th>אחוז הצלחה (Success Rate)</th><th>למה זה עבד (Why It Worked)</th></tr>")
            for topic in topics:
                name = topic.get('topic', '')
                lectures = ', '.join(topic.get('lectures', []))
                rate = topic.get('success_rate', '')
                why = topic.get('why_it_worked', '')
                lines.append(f"<tr><td>{name}</td><td>{lectures}</td><td>{rate}</td><td>{why}</td></tr>")
            lines.append("</table>")

        # Good lessons
        lessons = successes.get('good_lessons', [])
        if lessons:
            lines.append("<h3>Good Lessons</h3>")
            lines.append("<table>")
            lines.append("<tr><th>שיעור (Lesson)</th><th>נושא (Topic)</th><th>ממוצע הערכה (Eval)</th><th>איתותים חיוביים (Positive Signals)</th><th>מה לחזור על (What to Repeat)</th></tr>")
            for lesson in lessons:
                lesson_num = lesson.get('lesson_number', '')
                topic = lesson.get('topic', '')
                eval_avg = lesson.get('eval_avg', '')
                signals = lesson.get('positive_signals', '')
                repeat = lesson.get('what_to_repeat', '')
                lines.append(f"<tr><td>{lesson_num}</td><td>{topic}</td><td>{eval_avg}</td><td>{signals}</td><td>{repeat}</td></tr>")
            lines.append("</table>")

        if not topics and not lessons:
            lines.append("<p>Insufficient data to identify cross-lesson teaching successes.</p>")

        return '\n'.join(lines)

    def _generate_gaps_html(self, gaps: dict) -> str:
        """Generate HTML for Systemic Gaps section."""
        lines = []

        systemic = gaps.get('systemic_gaps', [])
        if systemic:
            for gap in systemic:
                lines.append(f"<p><strong>{gap.get('name', '')}</strong>: {gap.get('description', '')}</p>")
                if gap.get('recommendation'):
                    lines.append(f"<p><strong>המלצה</strong>: {gap['recommendation']}</p>")
        else:
            lines.append("<p>Teaching emphasis aligns well with student learning outcomes.</p>")

        return '\n'.join(lines)

    def _generate_prerequisites_html(self, prerequisites: dict) -> str:
        """Generate HTML for Prerequisites section."""
        lines = []

        gaps = prerequisites.get('prerequisite_gaps', [])
        if gaps:
            lines.append("<table>")
            lines.append("<tr><th>נושא (Topic)</th><th>מספר תלמידים (Students)</th><th>שיעורים (Lectures)</th><th>דוגמאות (Examples)</th><th>המלצה (Recommendation)</th></tr>")
            for gap in gaps:
                topic = gap.get('topic', '')
                students = gap.get('students', '')
                lectures = gap.get('lectures', '')
                examples = ', '.join(gap.get('examples', []))
                recommendation = gap.get('recommendation', '')
                lines.append(f"<tr><td>{topic}</td><td>{students}</td><td>{lectures}</td><td>{examples}</td><td>{recommendation}</td></tr>")
            lines.append("</table>")
        else:
            lines.append("<p>No significant prerequisite knowledge gaps detected.</p>")

        return '\n'.join(lines)


class CourseLayer3Pipeline:
    """Main pipeline for Course Layer 3: LLM narrative generation."""

    def __init__(self, config: LearningDashboardConfig):
        self.config = config
        self.prompt_builder = CoursePromptBuilder(config)
        self.llm_caller = LLMCaller(config)
        self.json_parser = JSONParser()

    def run(
        self,
        layer2_output: CourseLayer2Output,
        output_dir: Optional[Path] = None,
    ) -> dict:
        """
        Run the complete Layer 3 pipeline.

        Args:
            layer2_output: Course Layer 2 output object
            output_dir: Directory to save outputs

        Returns:
            Dict with JSON data, markdown, and HTML outputs
        """
        if output_dir is None:
            output_dir = self.config.paths.output_dir / "course_level" / "layer3"

        output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.verbose:
            print("=" * 80)
            print(f"COURSE-LEVEL LAYER 3: LLM Narrative Generation (Run {layer2_output.run_number})")
            print("=" * 80)

        # Build prompts
        if self.config.verbose:
            print("\n[1/5] Building LLM prompts...")

        system_prompt = self.prompt_builder.build_system_prompt(
            language=self.config.llm.output_language
        )
        user_prompt = self.prompt_builder.build_user_prompt(layer2_output)

        # Call LLM
        if self.config.verbose:
            print("\n[2/5] Calling LLM to generate JSON...")

        json_output = self.llm_caller.call_llm(system_prompt, user_prompt)

        # Parse JSON
        if self.config.verbose:
            print("\n[3/5] Parsing JSON output...")

        data = self.json_parser.parse_json(json_output)

        # Generate Markdown from JSON
        if self.config.verbose:
            print("\n[4/5] Generating Markdown from JSON...")

        markdown_gen = MarkdownGenerator(layer2_output)
        markdown_output = markdown_gen.generate_markdown(data)

        # Generate HTML from JSON
        if self.config.verbose:
            print("\n[5/5] Generating HTML from JSON...")

        html_gen = HTMLGenerator(layer2_output)
        html_output = html_gen.generate_html(data)

        # Save outputs
        self._save_outputs(data, markdown_output, html_output, layer2_output, output_dir)

        if self.config.verbose:
            print(f"\n✅ Course Layer 3 complete!")
            print(f"   Outputs saved to: {output_dir}")

        return {
            'json_data': data,
            'markdown': markdown_output,
            'html': html_output,
            'course_snapshot': data.get('course_snapshot', {}),
            'struggles': data.get('struggles', {}),
            'successes': data.get('successes', {}),
            'gaps': data.get('gaps', {}),
            'prerequisites': data.get('prerequisites', {}),
        }

    def _calculate_roi_data(self, output_dir: Path):
        """Calculate ROI data from eval.csv."""
        # Import the ROI calculation function
        from .generate_5box_report import calculate_roi_from_eval_data

        # Get the data directory (go up from layer3 to output base)
        data_dir = output_dir.parent.parent.parent

        try:
            roi_items = calculate_roi_from_eval_data(data_dir, {})
            return roi_items
        except Exception as e:
            if self.config.verbose:
                print(f"⚠️  Could not calculate ROI data: {e}")
            return []

    def _save_outputs(
        self,
        data: dict,
        markdown: str,
        html: str,
        layer2_output: CourseLayer2Output,
        output_dir: Path,
    ):
        """Save Layer 3 outputs (JSON, Markdown, HTML)."""
        # Save LLM JSON output
        json_path = output_dir / "course_dashboard_llm.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"✅ Saved LLM JSON to {json_path}")

        # Save markdown
        markdown_path = output_dir / "course_dashboard.md"
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        if self.config.verbose:
            print(f"✅ Saved markdown to {markdown_path}")

        # Save HTML
        html_path = output_dir / "course_dashboard.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        if self.config.verbose:
            print(f"✅ Saved HTML dashboard to {html_path}")

        # Calculate ROI data
        if self.config.verbose:
            print("Calculating ROI data...")
        roi_data = self._calculate_roi_data(output_dir)

        # Save complete output (Layer 2 + Layer 3 + ROI)
        complete_output = {
            'run_number': layer2_output.run_number,
            'run_date': layer2_output.run_date,
            'lectures_covered': layer2_output.lectures_covered,
            'total_lectures': layer2_output.total_lectures,
            'engaged_n': layer2_output.engaged_n,
            'course_eval_avg': layer2_output.course_eval_avg,
            'course_quiz_avg': layer2_output.course_quiz_avg,
            'layer2_data': layer2_output.to_dict(),
            'llm_json': data,
            'markdown_output': markdown,
            'roi_analysis': roi_data,  # Add ROI data
        }

        complete_path = output_dir / "complete_course_dashboard.json"
        with open(complete_path, 'w', encoding='utf-8') as f:
            json.dump(complete_output, f, ensure_ascii=False, indent=2)

        if self.config.verbose:
            print(f"✅ Saved complete dashboard JSON to {complete_path}")
            if roi_data:
                print(f"   • Included {len(roi_data)} ROI items")