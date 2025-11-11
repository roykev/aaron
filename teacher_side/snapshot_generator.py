#!/usr/bin/env python3
"""
AaronOwl Teaching Snapshot Generator
Generates teaching excellence snapshots from analysis JSON files
Supports both minimalist and expanded markdown views
"""

import json
import argparse
import os.path
import time
import re
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import yaml

from teacher_side.teacher_utils import get_output_dir
from utils.utils import get_logger


class SnapshotGenerator:
    """Generate teaching snapshots from story.txt, deep.txt, and output.txt"""

    def __init__(self, story_file: str, deep_file: str, output_file: str):
        self.story_data = self._load_json_file(story_file)
        self.deep_data = self._load_json_file(deep_file)
        self.output_data = self._parse_output_file(output_file)
        self.output_dir = os.path.dirname(output_file)
        self.transcript_duration = self._get_transcript_duration()

    def _load_json_file(self, filepath: str) -> List[Dict]:
        """Load JSON data from file (handles both plain JSON and markdown code blocks)"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove markdown code block markers if present
        if content.strip().startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1])  # Remove first and last lines

        return json.loads(content)

    def _parse_output_file(self, filepath: str) -> Dict:
        """Parse the output.txt file with multiple sections"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {}

        # Extract title
        if '### title ###' in content or '### task name ### title' in content:
            title_start = content.find('{', content.find('title'))
            title_end = content.find('}', title_start) + 1
            result['title'] = json.loads(content[title_start:title_end])

        # Extract sections
        if '### sections ###' in content or '### task name ### sections' in content:
            sections_start = content.find('chapter_num', content.find('sections'))
            sections_end = content.find('### ', sections_start + 1)
            if sections_end == -1:
                sections_end = content.find('```', sections_start + 1)
            sections_text = content[sections_start:sections_end].strip()
            result['sections'] = self._parse_csv(sections_text)

        # Extract examples
        if '### examples ###' in content or '### task name ### examples' in content:
            examples_start = content.find('Topic,', content.find('examples'))
            examples_end = content.find('### ', examples_start + 1)
            if examples_end == -1:
                examples_end = content.find('```', examples_start + 1)
            examples_text = content[examples_start:examples_end].strip()
            result['examples'] = self._parse_csv(examples_text)

        # Extract open questions
        if '### open_questions ###' in content or '### task name ### open_questions' in content:
            questions_start = content.find('{', content.find('open_questions'))
            questions_end = content.find('}', questions_start)
            # Find the closing brace, accounting for nested structures
            brace_count = 1
            pos = questions_start + 1
            while brace_count > 0 and pos < len(content):
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            questions_end = pos
            result['open_questions'] = json.loads(content[questions_start:questions_end])

        # Extract interactions
        if '### interaction ###' in content or '### task name ### interaction' in content:
            interaction_start = content.find('Time,', content.find('interaction'))
            interaction_end = content.find('### ', interaction_start + 1)
            if interaction_end == -1:
                interaction_end = content.find('```', interaction_start + 1)
            interaction_text = content[interaction_start:interaction_end].strip()
            result['interactions'] = self._parse_csv(interaction_text)

        # Extract difficult topics
        if '### difficult_topics ###' in content or '### task name ### difficult_topics' in content:
            topics_start = content.find('Topic,', content.find('difficult_topics'))
            topics_end = len(content)
            topics_text = content[topics_start:topics_end].strip()
            if '```' in topics_text:
                topics_text = topics_text[:topics_text.find('```')]
            result['difficult_topics'] = self._parse_csv(topics_text)

        return result

    def _parse_csv(self, csv_text: str) -> List[Dict]:
        """Parse CSV text into list of dictionaries"""
        lines = [line.strip() for line in csv_text.split('\n') if line.strip()]
        if not lines:
            return []

        headers = [h.strip() for h in lines[0].split(',')]
        result = []

        for line in lines[1:]:
            # Handle quoted fields with commas
            fields = []
            current_field = ""
            in_quotes = False

            for char in line:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    fields.append(current_field.strip().strip('"'))
                    current_field = ""
                else:
                    current_field += char

            fields.append(current_field.strip().strip('"'))

            if len(fields) == len(headers):
                result.append(dict(zip(headers, fields)))

        return result

    def _get_transcript_duration(self) -> Optional[str]:
        """Extract duration from transcript file in parent directory"""
        try:
            parent_dir = os.path.dirname(self.output_dir)

            # Look for .vtt or .srt files
            transcript_files = []
            for ext in ['*.vtt', '*.srt']:
                transcript_files.extend(glob.glob(os.path.join(parent_dir, ext)))

            if not transcript_files:
                return None

            # Use the first transcript file found
            transcript_file = transcript_files[0]

            # Read last few lines to find the last timestamp
            with open(transcript_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Search backwards for timestamp pattern (HH:MM:SS.mmm)
            timestamp_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})')

            for line in reversed(lines[-50:]):  # Check last 50 lines
                match = timestamp_pattern.search(line)
                if match:
                    hours, minutes, seconds, _ = match.groups()
                    hours = int(hours)
                    minutes = int(minutes)
                    seconds = int(seconds)

                    # Format as HH:MM:SS or MM:SS depending on duration
                    if hours > 0:
                        return f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        return f"{minutes}:{seconds:02d}"

            return None

        except Exception as e:
            print(f"Warning: Could not extract duration from transcript: {e}")
            return None

    def _calculate_scores(self) -> Tuple[Dict[str, int], Dict[str, int], float]:
        """Calculate scores for storytelling and deep learning dimensions"""

        # Storytelling dimensions from story.txt
        storytelling_scores = {}
        for module in self.story_data:
            module_name = module['module']
            # Simple heuristic: more strengths = higher score
            strengths = len(module['strengths'])
            weaknesses = len(module['weaknesses'])
            score = min(10, max(1, 5 + (strengths * 2) - (weaknesses * 1.5)))
            storytelling_scores[module_name] = int(score)

        # Deep learning dimensions from deep.txt
        deep_scores = {}
        for module in self.deep_data:
            module_name = module['module']
            strengths = len(module['strengths'])
            weaknesses = len(module['weaknesses'])
            score = min(10, max(1, 5 + (strengths * 2) - (weaknesses * 1.5)))
            deep_scores[module_name] = int(score)

        # Overall score
        all_scores = list(storytelling_scores.values()) + list(deep_scores.values())
        overall = sum(all_scores) / len(all_scores) if all_scores else 0

        return storytelling_scores, deep_scores, overall

    def _get_top_strength(self) -> Tuple[str, str]:
        """Extract the top strength from the data"""
        # Look for highest-scoring storytelling dimension
        storytelling_scores, _, _ = self._calculate_scores()
        top_module = max(storytelling_scores, key=storytelling_scores.get)

        # Get the first strength from that module
        for module in self.story_data:
            if module['module'] == top_module:
                return top_module, module['strengths'][0] if module['strengths'] else ""

        return top_module, ""

    def _get_preserve_items(self) -> List[Tuple[str, str]]:
        """Extract items to preserve from all modules"""
        items = []

        # From storytelling
        for module in self.story_data:
            for strength in module['strengths'][:1]:  # Top strength per module
                items.append((module['module'], strength))

        return items[:3]  # Top 3

    def _get_improve_items(self) -> List[Tuple[str, str, str]]:
        """Extract items to improve"""
        items = []

        # From storytelling and deep learning
        all_modules = self.story_data + self.deep_data

        for module in all_modules:
            for i, weakness in enumerate(module['weaknesses'][:1]):  # Top weakness per module
                recommendation = module['recommendations'][i] if i < len(module['recommendations']) else ""
                items.append((module['module'], weakness, recommendation))

        return items[:3]  # Top 3

    def _get_action_items(self) -> List[Tuple[str, str, str]]:
        """Extract actionable recommendations"""
        items = []

        for module in self.story_data + self.deep_data:
            for rec in module['recommendations'][:1]:  # One per module
                items.append((module['module'], rec, "פעולה מומלצת"))

        return items[:4]  # Top 4

    def _get_hot_topics(self) -> List[str]:
        """Extract hot topics from examples and interactions"""
        topics = []

        if 'examples' in self.output_data:
            for example in self.output_data['examples'][:3]:
                if 'Topic' in example:
                    topics.append(example['Topic'])

        return topics

    def _get_top_questions(self) -> List[Tuple[str, str]]:
        """Extract top questions from interactions"""
        questions = []

        if 'interactions' in self.output_data:
            for interaction in self.output_data['interactions']:
                if 'student question' in interaction.get('Type', '').lower():
                    questions.append((
                        interaction.get('Description', ''),
                        interaction.get('Time', '')
                    ))

        return questions[:2]

    def _stars(self, score: int) -> str:
        """Convert numeric score to star rating"""
        full_stars = score // 2
        half_star = 1 if score % 2 == 1 else 0
        return '⭐' * full_stars + ('⭐' if half_star else '')

    def generate_minimalist_markdown(self) -> str:
        """Generate minimalist markdown snapshot (no numbers by default)"""
        title = self.output_data.get('title', {}).get('title', 'שיעור ללא שם')

        # Use transcript duration if available, otherwise fall back to sections
        if self.transcript_duration:
            duration = self.transcript_duration
        else:
            sections = self.output_data.get('sections', [])
            duration = sections[-1].get('to', '60 דקות') if sections else '60 דקות'

        top_module, top_strength = self._get_top_strength()

        # Simple main message without fictional scoring
        main_msg = "שיעור עם נקודות חזקות ותחומים לשיפור"

        md = f"""# Teaching Snapshot

## {title}

<div style='border-left: 3px solid #6b7280; padding: 15px 20px; margin: 20px 0; background: #fafafa;'>
<p style='margin: 0; color: #374151;'><strong>המסר המרכזי:</strong> {main_msg}</p>
<p style='margin: 10px 0 0 0; color: #6b7280;'><strong>משך השיעור:</strong> {duration}</p>
</div>

---

## Outstanding Performance

<div style='background: #f9fafb; border-left: 3px solid #6b7280; padding: 15px; margin: 15px 0;'>
<p style='margin: 0; color: #374151;'><strong>{top_module}:</strong> {top_strength}</p>
</div>

---

## Successful Practices

"""

        # Preserve section - each item expandable with full details
        preserve_items = self._get_preserve_items()
        for i, (module, item) in enumerate(preserve_items, 1):
            # Create a short summary (first 80 chars of the item)
            summary = item[:80] + '...' if len(item) > 80 else item
            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            md += f"<strong style='color: #374151;'>{i}. {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            md += "</summary>\n\n"
            md += f"<div style='padding: 15px; background: #f9fafb; margin-top: 10px;'>\n"
            md += f"<p><strong>חוזקה עיקרית:</strong> {item}</p>\n\n"

            # Find the full module data
            module_data = next((m for m in self.story_data if m['module'] == module), None)
            if module_data and len(module_data['strengths']) > 1:
                md += "<p><strong>חוזקות נוספות:</strong></p>\n<ul>\n"
                for strength in module_data['strengths'][1:]:  # Skip first one, already shown
                    md += f"<li>{strength}</li>\n"
                md += "</ul>\n"

            md += "</div>\n</details>\n\n"

        md += "---\n\n"

        # Improve section - each item expandable with full details
        md += "## Areas for Enhancement\n\n"
        improve_items = self._get_improve_items()
        for i, (module, weakness, recommendation) in enumerate(improve_items, 1):
            # Create a short summary (first 80 chars of the weakness)
            summary = weakness[:80] + '...' if len(weakness) > 80 else weakness
            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            md += f"<strong style='color: #374151;'>{i}. {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            md += "</summary>\n\n"
            md += f"<div style='padding: 15px; background: #f9fafb; margin-top: 10px;'>\n"
            md += f"<p><strong>הבעיה:</strong> {weakness}</p>\n\n"
            md += f"<p><strong>הפתרון:</strong> {recommendation}</p>\n\n"

            # Find the full module data
            module_data = None
            for m in self.story_data + self.deep_data:
                if m['module'] == module:
                    module_data = m
                    break

            if module_data and len(module_data['weaknesses']) > 1:
                md += "<p><strong>תחומים נוספים לשיפור:</strong></p>\n<ul>\n"
                # Skip the first weakness as it's already shown
                for weak in module_data['weaknesses'][1:]:
                    md += f"<li>{weak}</li>\n"
                md += "</ul>\n"

            md += "</div>\n</details>\n\n"

        md += "---\n\n"

        # Action items - each item expandable
        md += "## Recommended Actions for Next Session\n\n"
        action_items = self._get_action_items()
        for i, (module, action, tag) in enumerate(action_items, 1):
            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            md += f"<strong style='color: #374151;'>{i}. {action[:80]}{'...' if len(action) > 80 else ''}</strong>"
            md += "</summary>\n\n"
            md += f"<div style='padding: 15px; background: #f9fafb; margin-top: 10px;'>\n"
            md += f"<p><strong>פעולה מלאה:</strong> {action}</p>\n\n"
            md += f"<p style='font-style: italic; color: #6b7280;'>מתוך: {module}</p>\n\n"

            # Show all recommendations from this module
            module_data = None
            for m in self.story_data + self.deep_data:
                if m['module'] == module:
                    module_data = m
                    break

            if module_data and len(module_data['recommendations']) > 1:
                md += "<p><strong>המלצות נוספות:</strong></p>\n<ul>\n"
                for rec in module_data['recommendations'][1:]:
                    md += f"<li>{rec}</li>\n"
                md += "</ul>\n"

            md += "</div>\n</details>\n\n"

        md += "---\n\n"
        md += f"*נוצר על ידי AaronOwl Teaching Excellence Analyzer | {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"

        return md

    def generate_expanded_markdown(self) -> str:
        """Generate expanded markdown with full details"""
        title = self.output_data.get('title', {}).get('title', 'שיעור ללא שם')

        # Use transcript duration if available, otherwise fall back to sections
        if self.transcript_duration:
            duration = self.transcript_duration
        else:
            sections = self.output_data.get('sections', [])
            duration = sections[-1].get('to', '60 דקות') if sections else '60 דקות'

        sections = self.output_data.get('sections', [])

        md = f"""# 🦉 AaronOwl - ניתוח מפורט

## {title}

**משך השיעור:** {duration}

---

## 📊 ניתוח לפי ממדים

### 📚 Storytelling Dimensions
"""

        for module in self.story_data:
            module_name = module['module']
            md += f"\n#### {module_name}\n\n"

            # Find the module data
            if module['strengths']:
                md += "**חוזקות:**\n"
                for strength in module['strengths']:
                    md += f"- {strength}\n"

            if module['weaknesses']:
                md += "\n**חולשות:**\n"
                for weakness in module['weaknesses']:
                    md += f"- {weakness}\n"

            if module['recommendations']:
                md += "\n**המלצות:**\n"
                for rec in module['recommendations']:
                    md += f"- {rec}\n"

            md += "\n"

        md += "\n### 🎓 Deep Learning Dimensions\n"

        for module in self.deep_data:
            module_name = module['module']
            md += f"\n#### {module_name}\n\n"

            if module['strengths']:
                md += "**חוזקות:**\n"
                for strength in module['strengths']:
                    md += f"- {strength}\n"

            if module['weaknesses']:
                md += "\n**חולשות:**\n"
                for weakness in module['weaknesses']:
                    md += f"- {weakness}\n"

            if module['recommendations']:
                md += "\n**המלצות:**\n"
                for rec in module['recommendations']:
                    md += f"- {rec}\n"

            md += "\n"

        md += "\n---\n\n"

        # Section breakdown
        md += "## 🗂️ מבנה השיעור\n\n"
        if sections:
            for section in sections:
                num = section.get('chapter_num', '')
                title = section.get('chapter_title', '')
                duration = section.get('duration', '')
                md += f"{num}. **{title}** ({duration})\n"

        md += "\n---\n\n"

        # Examples
        md += "## 💡 דוגמאות מהשיעור\n\n"
        if 'examples' in self.output_data:
            for example in self.output_data['examples']:
                topic = example.get('Topic', '')
                ex = example.get('Example', '')
                ref = example.get('reference', '')
                md += f"- **{topic}:** {ex} *({ref})*\n"

        md += "\n---\n\n"

        # Interactions
        md += "## 💬 אינטראקציות\n\n"
        if 'interactions' in self.output_data:
            for interaction in self.output_data['interactions']:
                time = interaction.get('Time', '')
                itype = interaction.get('Type', '')
                desc = interaction.get('Description', '')
                md += f"- **{time}** [{itype}]: {desc}\n"

        md += "\n---\n\n"

        # Questions
        md += "## ❓ שאלות למחשבה\n\n"
        if 'open_questions' in self.output_data:
            questions = self.output_data['open_questions']

            if 'simple' in questions or 'simple_questions' in questions:
                md += "### שאלות פשוטות:\n"
                simple = questions.get('simple', questions.get('simple_questions', []))
                for q in simple:
                    md += f"- {q}\n"

            if 'difficult' in questions or 'difficult_questions' in questions:
                md += "\n### שאלות מורכבות:\n"
                difficult = questions.get('difficult', questions.get('difficult_questions', []))
                for q in difficult:
                    md += f"- {q}\n"

        md += "\n---\n\n"

        # Difficult topics
        md += "## ⚠️ נושאים מאתגרים\n\n"
        if 'difficult_topics' in self.output_data:
            for topic_dict in self.output_data['difficult_topics']:
                topic = topic_dict.get('Topic', '')
                reason = topic_dict.get('Reason for difficulty', '')
                rec = topic_dict.get('Recommendation for improvement', '')
                md += f"### {topic}\n"
                md += f"**למה זה קשה:** {reason}\n\n"
                md += f"**המלצה:** {rec}\n\n"

        md += "---\n\n"
        md += f"*נוצר על ידי AaronOwl Teaching Excellence Analyzer | {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"

        return md


def main():
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))

    # Load configuration
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)
    # Start pipeline
    total_start = time.time()
    output_dir = get_output_dir(config)
    story_path = os.path.join(output_dir,"story.txt")
    deep_path = os.path.join(output_dir,"deep.txt")
    basic_path = os.path.join(output_dir,"output.txt")

    # Generate snapshot
    generator = SnapshotGenerator(story_path, deep_path, basic_path)

    # Generate both minimalist and expanded by default
    minimalist_markdown = generator.generate_minimalist_markdown()
    expanded_markdown = generator.generate_expanded_markdown()

    # Write minimalist version
    minimalist_path = Path(os.path.join(output_dir, 'teaching_snapshot.md'))
    minimalist_path.write_text(minimalist_markdown, encoding='utf-8')
    print(f"✅ Generated minimalist: {minimalist_path}")

    # Write expanded version
    expanded_path = Path(os.path.join(output_dir, 'teaching_snapshot_expanded.md'))
    expanded_path.write_text(expanded_markdown, encoding='utf-8')
    print(f"✅ Generated expanded: {expanded_path}")

    # Also print minimalist to console
    print("\n" + "=" * 80 + "\n")
    print("MINIMALIST VERSION:")
    print("=" * 80 + "\n")
    print(minimalist_markdown)


if __name__ == '__main__':
    main()