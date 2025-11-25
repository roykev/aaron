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
    """Generate teaching snapshots from story.txt, deep.txt, active.txt, and output.txt"""

    def __init__(self, story_file: str, deep_file: str, output_file: str, active_file: str = None, smart_insights_file: str = None):
        self.story_data = self._load_json_file(story_file)
        self.deep_data = self._load_json_file(deep_file)
        self.active_data = self._load_json_file(active_file) if active_file and os.path.exists(active_file) else None

        # Load smart insights if available
        self.smart_insights = None
        if smart_insights_file and os.path.exists(smart_insights_file):
            try:
                self.smart_insights = self._load_json_file(smart_insights_file)
            except:
                pass

        # Ensure story_data and deep_data are lists (defensive programming)
        # The unified mode might save them as dicts or lists depending on structure
        if isinstance(self.story_data, dict):
            # If it's a dict, wrap it in a list or extract the list if present
            if 'story' in self.story_data:
                self.story_data = self.story_data['story']
            else:
                self.story_data = [self.story_data]

        if isinstance(self.deep_data, dict):
            # If it's a dict, wrap it in a list or extract the list if present
            if 'deep' in self.deep_data:
                self.deep_data = self.deep_data['deep']
            else:
                self.deep_data = [self.deep_data]

        if self.active_data and isinstance(self.active_data, dict):
            # If it's a dict, wrap it in a list or extract the list if present
            if 'active' in self.active_data:
                self.active_data = self.active_data['active']
            else:
                self.active_data = [self.active_data]

        self.output_data = self._parse_output_file(output_file)
        self.output_dir = os.path.dirname(output_file)
        self.transcript_duration = self._get_transcript_duration()

    @staticmethod
    def _normalize_header(header: str) -> str:
        """
        Normalize CSV header to a standard English key.
        Supports both Hebrew and English headers.
        """
        header = header.strip().lower()

        # Hebrew → English mappings
        hebrew_to_english = {
            # Topics and examples
            'נושא': 'topic',
            'דוגמה': 'example',
            'דוגמא': 'example',
            'מקור': 'reference',

            # Interactions
            'זמן': 'time',
            'סוג': 'type',
            'תיאור': 'description',

            # Difficult topics
            'סיבת הקושי': 'reason',
            'reason for difficulty': 'reason',
            'המלצה לשיפור': 'recommendation',
            'recommendation for improvement': 'recommendation',

            # Sections - Hebrew
            'מספר_פרק': 'section_number',
            'מספר פרק': 'section_number',
            'כותרת_פרק': 'title',
            'כותרת פרק': 'title',
            'משך': 'duration',
            'מ': 'start',
            'עד': 'end',

            # Sections - English variations
            'section_num': 'section_number',
            'chapter_num': 'section_number',
            'chapter_title': 'title',
            'from': 'start',
            'to': 'end',
        }

        # Check if it's a mapped header
        if header in hebrew_to_english:
            return hebrew_to_english[header]

        # Return as-is (lowercase)
        return header

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
            # Try to find CSV data after "sections" marker - look for Hebrew or English headers
            search_start = content.find('sections')
            sections_start = -1

            # Try multiple header patterns (Hebrew and English)
            for pattern in ['section_num', 'chapter_num', 'מספר_פרק', 'מספר פרק']:
                idx = content.find(pattern, search_start)
                if idx != -1:
                    sections_start = idx
                    break

            if sections_start != -1:
                sections_end = content.find('### ', sections_start + 1)
                if sections_end == -1:
                    sections_end = content.find('```', sections_start + 1)
                sections_text = content[sections_start:sections_end].strip()
                result['sections'] = self._parse_csv(sections_text)

        # Extract examples
        if '### examples ###' in content or '### task name ### examples' in content:
            # Try to find CSV data after "examples" marker - look for Hebrew or English headers
            search_start = content.find('examples')
            examples_start = -1

            # Try multiple header patterns (Hebrew and English)
            for pattern in ['Topic,', 'נושא,', 'נושא ,']:
                idx = content.find(pattern, search_start)
                if idx != -1:
                    examples_start = idx
                    break

            if examples_start != -1:
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
            # Try to find CSV data after "interaction" marker - look for Hebrew or English headers
            search_start = content.find('interaction')
            interaction_start = -1

            # Try multiple header patterns (Hebrew and English)
            for pattern in ['Time,', 'זמן,', 'זמן ,']:
                idx = content.find(pattern, search_start)
                if idx != -1:
                    interaction_start = idx
                    break

            if interaction_start != -1:
                interaction_end = content.find('### ', interaction_start + 1)
                if interaction_end == -1:
                    interaction_end = content.find('```', interaction_start + 1)
                interaction_text = content[interaction_start:interaction_end].strip()
                result['interactions'] = self._parse_csv(interaction_text)

        # Extract difficult topics
        if '### difficult_topics ###' in content or '### task name ### difficult_topics' in content:
            # Try to find CSV data after "difficult_topics" marker - look for Hebrew or English headers
            search_start = content.find('difficult_topics')
            topics_start = -1

            # Try multiple header patterns (Hebrew and English)
            for pattern in ['Topic,', 'נושא,', 'נושא ,']:
                idx = content.find(pattern, search_start)
                if idx != -1:
                    topics_start = idx
                    break

            if topics_start != -1:
                topics_end = len(content)
                topics_text = content[topics_start:topics_end].strip()
                if '```' in topics_text:
                    topics_text = topics_text[:topics_text.find('```')]
                result['difficult_topics'] = self._parse_csv(topics_text)

        return result

    def _parse_csv(self, csv_text: str) -> List[Dict]:
        """Parse CSV text into list of dictionaries with normalized headers"""
        lines = [line.strip() for line in csv_text.split('\n') if line.strip()]
        if not lines:
            return []

        # Normalize headers to English lowercase
        raw_headers = [h.strip() for h in lines[0].split(',')]
        headers = [self._normalize_header(h) for h in raw_headers]
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

    def _calculate_scores(self) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int], float]:
        """Calculate scores for storytelling, deep learning, and active learning dimensions"""

        # Storytelling dimensions from story.txt
        storytelling_scores = {}
        if isinstance(self.story_data, list):
            for module in self.story_data:
                if isinstance(module, dict) and 'module' in module:
                    module_name = module['module']
                    # Simple heuristic: more strengths = higher score
                    strengths = len(module.get('strengths', []))
                    weaknesses = len(module.get('weaknesses', []))
                    score = min(10, max(1, 5 + (strengths * 2) - (weaknesses * 1.5)))
                    storytelling_scores[module_name] = int(score)

        # Deep learning dimensions from deep.txt
        deep_scores = {}
        if isinstance(self.deep_data, list):
            for module in self.deep_data:
                if isinstance(module, dict) and 'module' in module:
                    module_name = module['module']
                    strengths = len(module.get('strengths', []))
                    weaknesses = len(module.get('weaknesses', []))
                    score = min(10, max(1, 5 + (strengths * 2) - (weaknesses * 1.5)))
                    deep_scores[module_name] = int(score)

        # Active learning dimensions from active.txt
        active_scores = {}
        if self.active_data and isinstance(self.active_data, list):
            for module in self.active_data:
                if isinstance(module, dict):
                    module_name = module.get('dimension', module.get('module', 'Unknown'))
                    strengths = len(module.get('strengths', []))
                    weaknesses = len(module.get('weaknesses', []))
                    score = min(10, max(1, 5 + (strengths * 2) - (weaknesses * 1.5)))
                    active_scores[module_name] = int(score)

        # Overall score
        all_scores = list(storytelling_scores.values()) + list(deep_scores.values()) + list(active_scores.values())
        overall = sum(all_scores) / len(all_scores) if all_scores else 0

        return storytelling_scores, deep_scores, active_scores, overall

    def _get_top_strength(self) -> Tuple[str, str, str]:
        """Extract the top strength from ALL vectors (storytelling, deep, active)
        Returns: (vector, dimension, strength) tuple
        """
        # Look for highest-scoring dimension across all vectors
        storytelling_scores, deep_scores, active_scores, _ = self._calculate_scores()

        # Combine all scores with their vectors
        all_scores = []
        for module, score in storytelling_scores.items():
            all_scores.append(("Storytelling", module, score))
        for module, score in deep_scores.items():
            all_scores.append(("Deep Analysis", module, score))
        for module, score in active_scores.items():
            all_scores.append(("Active Learning", module, score))

        if not all_scores:
            return "Unknown", "Unknown", "No data available"

        # Find the highest scoring dimension
        top_vector, top_module, top_score = max(all_scores, key=lambda x: x[2])

        # Get the first strength from that module in the appropriate data source
        if top_vector == "Storytelling" and isinstance(self.story_data, list):
            for module in self.story_data:
                if isinstance(module, dict) and module.get('module') == top_module:
                    strengths = module.get('strengths', [])
                    return top_vector, top_module, strengths[0] if strengths else ""

        elif top_vector == "Deep Analysis" and isinstance(self.deep_data, list):
            for module in self.deep_data:
                if isinstance(module, dict) and module.get('module') == top_module:
                    strengths = module.get('strengths', [])
                    return top_vector, top_module, strengths[0] if strengths else ""

        elif top_vector == "Active Learning" and self.active_data and isinstance(self.active_data, list):
            for module in self.active_data:
                if isinstance(module, dict) and (module.get('dimension') == top_module or module.get('module') == top_module):
                    strengths = module.get('strengths', [])
                    return top_vector, top_module, strengths[0] if strengths else ""

        return top_vector, top_module, ""

    def _find_vector_for_dimension(self, dimension: str) -> str:
        """Find which analysis vector (Storytelling, Deep Analysis, Active Learning) a dimension belongs to"""
        # Check storytelling
        if isinstance(self.story_data, list):
            for module in self.story_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', ''))
                    if module_name.lower() == dimension.lower():
                        return "Storytelling"

        # Check deep analysis
        if isinstance(self.deep_data, list):
            for module in self.deep_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', ''))
                    if module_name.lower() == dimension.lower():
                        return "Deep Analysis"

        # Check active learning
        if self.active_data and isinstance(self.active_data, list):
            for module in self.active_data:
                if isinstance(module, dict):
                    module_name = module.get('dimension', module.get('module', ''))
                    if module_name.lower() == dimension.lower():
                        return "Active Learning"

        # Default fallback - return the dimension itself instead of generic "Analysis"
        return dimension

    def _get_preserve_items(self) -> List[Tuple[str, str, str, str, str]]:
        """Extract items to preserve from smart_insights if available, otherwise from ALL analysis approaches (story, deep, active)
        Returns: List of (vector, dimension, strength, why_important, evidence) tuples
        """
        items = []

        # PRIORITY 1: Use 'preserve' array from smart_insights.json if available
        if self.smart_insights and isinstance(self.smart_insights, dict):
            preserve = self.smart_insights.get('preserve', [])
            if preserve:
                for item in preserve:
                    if isinstance(item, dict):
                        # Extract dimension, strength, why_important, and evidence
                        dimension = item.get('dimension', 'Unknown')
                        strength = item.get('strength', '')
                        why_important = item.get('why_important', '')
                        evidence = item.get('evidence', '')
                        # Find which vector this dimension belongs to
                        vector = self._find_vector_for_dimension(dimension)
                        items.append((vector, dimension, strength, why_important, evidence))
                return items[:5]  # Return top 5 from smart insights

        # FALLBACK: If smart_insights not available, extract from raw analysis files
        # From storytelling
        if isinstance(self.story_data, list):
            for module in self.story_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', 'Unknown'))
                    strengths = module.get('strengths', [])
                    for strength in strengths[:1]:  # Top strength per module
                        items.append(("Storytelling", module_name, strength, "", ""))

        # From deep learning
        if isinstance(self.deep_data, list):
            for module in self.deep_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', 'Unknown'))
                    strengths = module.get('strengths', [])
                    for strength in strengths[:1]:  # Top strength per module
                        items.append(("Deep Analysis", module_name, strength, "", ""))

        # From active learning
        if self.active_data and isinstance(self.active_data, list):
            for module in self.active_data:
                if isinstance(module, dict):
                    module_name = module.get('dimension', module.get('module', 'Unknown'))
                    strengths = module.get('strengths', [])
                    for strength in strengths[:1]:  # Top strength per module
                        items.append(("Active Learning", module_name, strength, "", ""))

        return items[:5]  # Top 5 from all approaches

    def _get_improve_items(self) -> List[Tuple[str, str, str, str, str]]:
        """Extract items to improve from smart_insights if available, otherwise from ALL analysis approaches (story, deep, active)
        Returns: List of (vector, dimension, opportunity, suggestion, potential_benefit) tuples
        """
        items = []

        # PRIORITY 1: Use 'growth_opportunities' array from smart_insights.json if available
        if self.smart_insights and isinstance(self.smart_insights, dict):
            growth_opportunities = self.smart_insights.get('growth_opportunities', [])
            if growth_opportunities:
                for opportunity_obj in growth_opportunities:
                    if isinstance(opportunity_obj, dict):
                        # Extract dimension, opportunity, suggestion, and potential_benefit
                        dimension = opportunity_obj.get('dimension', 'Unknown')
                        opportunity = opportunity_obj.get('opportunity', '')
                        suggestion = opportunity_obj.get('suggestion', '')
                        potential_benefit = opportunity_obj.get('potential_benefit', '')
                        # Find which vector this dimension belongs to
                        vector = self._find_vector_for_dimension(dimension)
                        items.append((vector, dimension, opportunity, suggestion, potential_benefit))
                return items[:5]  # Return top 5 from smart insights

        # FALLBACK: If smart_insights not available, extract from raw analysis files
        # From storytelling
        if isinstance(self.story_data, list):
            for module in self.story_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', 'Unknown'))
                    weaknesses = module.get('weaknesses', [])
                    recommendations = module.get('recommendations', [])
                    for i, weakness in enumerate(weaknesses[:1]):  # Top weakness per module
                        recommendation = recommendations[i] if i < len(recommendations) else ""
                        items.append(("Storytelling", module_name, weakness, recommendation, ""))

        # From deep learning
        if isinstance(self.deep_data, list):
            for module in self.deep_data:
                if isinstance(module, dict):
                    module_name = module.get('module', module.get('dimension', 'Unknown'))
                    weaknesses = module.get('weaknesses', [])
                    recommendations = module.get('recommendations', [])
                    for i, weakness in enumerate(weaknesses[:1]):  # Top weakness per module
                        recommendation = recommendations[i] if i < len(recommendations) else ""
                        items.append(("Deep Analysis", module_name, weakness, recommendation, ""))

        # From active learning
        if self.active_data and isinstance(self.active_data, list):
            for module in self.active_data:
                if isinstance(module, dict):
                    module_name = module.get('dimension', module.get('module', 'Unknown'))
                    weaknesses = module.get('weaknesses', [])
                    recommendations = module.get('recommendations', [])
                    for i, weakness in enumerate(weaknesses[:1]):  # Top weakness per module
                        recommendation = recommendations[i] if i < len(recommendations) else ""
                        items.append(("Active Learning", module_name, weakness, recommendation, ""))

        return items[:5]  # Top 5 from all approaches

    def _get_action_items(self) -> List[Tuple[str, str, str]]:
        """Extract actionable recommendations from smart_insights if available, otherwise from ALL analysis approaches (story, deep, active)"""
        items = []

        # PRIORITY 1: Use 'priority_actions' array from smart_insights.json if available
        if self.smart_insights and isinstance(self.smart_insights, dict):
            priority_actions = self.smart_insights.get('priority_actions', [])
            if priority_actions:
                for action_item in priority_actions:
                    if isinstance(action_item, dict):
                        # Extract action, expected outcome, and difficulty
                        action = action_item.get('action', '')
                        duration = action_item.get('duration', '')
                        difficulty = action_item.get('difficulty', 'unknown')
                        # Use difficulty/duration as the tag
                        tag = f"{difficulty} ({duration})" if duration else difficulty
                        items.append(("Priority Action", action, tag))
                return items[:6]  # Return top 6 from smart insights

        # FALLBACK: Extract from raw analysis files
        all_modules = []
        if isinstance(self.story_data, list):
            all_modules.extend(self.story_data)
        if isinstance(self.deep_data, list):
            all_modules.extend(self.deep_data)
        if self.active_data and isinstance(self.active_data, list):
            all_modules.extend(self.active_data)

        for module in all_modules:
            if isinstance(module, dict):
                module_name = module.get('module', module.get('dimension', 'Unknown'))
                recommendations = module.get('recommendations', [])
                for rec in recommendations[:1]:  # One per module
                    items.append((module_name, rec, "פעולה מומלצת"))

        return items[:6]  # Top 6 from all approaches

    def _get_hot_topics(self) -> List[str]:
        """Extract hot topics from examples and interactions"""
        topics = []

        if 'examples' in self.output_data:
            for example in self.output_data['examples'][:3]:
                if 'topic' in example:
                    topics.append(example['topic'])

        return topics

    def _get_top_questions(self) -> List[Tuple[str, str]]:
        """Extract top questions from interactions"""
        questions = []

        if 'interactions' in self.output_data:
            for interaction in self.output_data['interactions']:
                if 'student question' in interaction.get('type', '').lower():
                    questions.append((
                        interaction.get('description', ''),
                        interaction.get('time', '')
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
            duration = sections[-1].get('end', '60 דקות') if sections else '60 דקות'

        # Get main message from smart insights if available, otherwise use generic message
        if self.smart_insights and isinstance(self.smart_insights, dict):
            main_msg = self.smart_insights.get('overall_assessment',
                                               self.smart_insights.get('key_message',
                                                                      'שיעור עם נקודות חזקות ותחומים לשיפור'))
        else:
            main_msg = "שיעור עם נקודות חזקות ותחומים לשיפור"

        md = f"""# Teaching Snapshot

## {title}

<div style='border-left: 3px solid #6b7280; padding: 15px 20px; margin: 20px 0; background: #fafafa;'>
<p style='margin: 0; color: #374151;'><strong>המסר המרכזי:</strong> {main_msg}</p>
<p style='margin: 10px 0 0 0; color: #6b7280;'><strong>משך השיעור:</strong> {duration}</p>
</div>

---

## Outstanding Performance

"""

        # Use top_strength from smart_insights if available, otherwise use fallback method
        if self.smart_insights and isinstance(self.smart_insights, dict):
            top_strength_obj = self.smart_insights.get('top_strength')
            if top_strength_obj and isinstance(top_strength_obj, dict):
                dimension = top_strength_obj.get('dimension', 'Unknown')
                description = top_strength_obj.get('description', '')
                evidence = top_strength_obj.get('evidence', '')

                # Find which vector this dimension belongs to
                vector = self._find_vector_for_dimension(dimension)

                md += "<div style='background: #f9fafb; border-left: 3px solid #6b7280; padding: 15px; margin: 15px 0;'>\n"
                # Only show vector if it's different from dimension
                if vector.lower() != dimension.lower():
                    md += f"<p style='margin: 0; color: #374151;'><strong>{vector}: {dimension}</strong></p>\n"
                else:
                    md += f"<p style='margin: 0; color: #374151;'><strong>{dimension}</strong></p>\n"
                md += f"<p style='margin: 10px 0 0 0; color: #4b5563;'>{description}</p>\n"
                if evidence:
                    md += f"<p style='margin: 10px 0 0 0; color: #6b7280; font-style: italic;'><strong>Evidence:</strong> {evidence}</p>\n"
                md += "</div>\n\n"
            else:
                # Fallback to old method if top_strength not available
                top_vector, top_module, top_strength = self._get_top_strength()
                md += "<div style='background: #f9fafb; border-left: 3px solid #6b7280; padding: 15px; margin: 15px 0;'>\n"
                md += f"<p style='margin: 0; color: #374151;'><strong>{top_vector}: {top_module}:</strong> {top_strength}</p>\n"
                md += "</div>\n\n"
        else:
            # Fallback to old method if smart_insights not available
            top_vector, top_module, top_strength = self._get_top_strength()
            md += "<div style='background: #f9fafb; border-left: 3px solid #6b7280; padding: 15px; margin: 15px 0;'>\n"
            md += f"<p style='margin: 0; color: #374151;'><strong>{top_vector}: {top_module}:</strong> {top_strength}</p>\n"
            md += "</div>\n\n"

        md += "---\n\n"

        # Long-term opportunity section (if exists in smart_insights)
        if self.smart_insights and isinstance(self.smart_insights, dict):
            long_term_opp = self.smart_insights.get('long_term_opportunity')
            if long_term_opp:
                md += """## Long-Term Growth Opportunity

<div style='background: #eff6ff; border-left: 3px solid #3b82f6; padding: 15px; margin: 15px 0;'>
"""
                md += f"<p style='margin: 0; color: #1e40af;'><strong>Strategic Vision:</strong> {long_term_opp}</p>\n"
                md += "</div>\n\n"
                md += "---\n\n"

        md += "## Successful Practices\n\n"

        # Preserve section - each item expandable with full details
        preserve_items = self._get_preserve_items()
        for i, (vector, module, item, why_important, evidence) in enumerate(preserve_items, 1):
            # Create a short summary (first 80 chars of the item)
            summary = item[:80] + '...' if len(item) > 80 else item
            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            # Only show vector if it's different from the dimension
            if vector.lower() != module.lower():
                md += f"<strong style='color: #374151;'>{i}. {vector}: {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            else:
                md += f"<strong style='color: #374151;'>{i}. {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            md += "</summary>\n\n"
            md += f"<div style='padding: 15px; background: #f9fafb; margin-top: 10px;'>\n"

            # Add why_important if available
            if why_important:
                md += f"<p><strong>למה זה חשוב:</strong> {why_important}</p>\n\n"

            # Add evidence if available
            if evidence:
                md += f"<p style='font-style: italic; color: #6b7280;'><strong>Evidence:</strong> {evidence}</p>\n\n"

            md += "</div>\n</details>\n\n"

        md += "---\n\n"

        # Improve section - each item expandable with full details
        md += "## Opportunities for Enhancement\n\n"
        improve_items = self._get_improve_items()
        for i, (vector, module, opportunity, suggestion, potential_benefit) in enumerate(improve_items, 1):
            # Create a short summary (first 80 chars of the opportunity)
            summary = opportunity[:80] + '...' if len(opportunity) > 80 else opportunity
            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            # Only show vector if it's different from the dimension
            if vector.lower() != module.lower():
                md += f"<strong style='color: #374151;'>{i}. {vector}: {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            else:
                md += f"<strong style='color: #374151;'>{i}. {module}:</strong> <span style='color: #6b7280;'>{summary}</span>"
            md += "</summary>\n\n"
            md += f"<div style='padding: 15px; background: #f9fafb; margin-top: 10px;'>\n"
            md += f"<p><strong>ההזדמנות:</strong> {opportunity}</p>\n\n"
            md += f"<p><strong>הפתרון:</strong> {suggestion}</p>\n\n"

            # Add potential_benefit if available
            if potential_benefit:
                md += f"<p style='color: #059669;'><strong>התועלת הפוטנציאלית:</strong> {potential_benefit}</p>\n\n"

            md += "</div>\n</details>\n\n"

        md += "---\n\n"

        # Action items - each item expandable
        md += "## Recommended Actions for Next Session\n\n"
        action_items = self._get_action_items()
        for i, (module, action, tag) in enumerate(action_items, 1):
            # Determine difficulty icon and color based on tag
            difficulty_icon = ""
            difficulty_color = "#9ca3af"
            if tag and tag != "פעולה מומלצת":
                tag_lower = tag.lower()
                if "easy" in tag_lower or "קל" in tag_lower:
                    difficulty_icon = "🟢 "
                    difficulty_color = "#10b981"  # green
                elif "medium" in tag_lower or "בינוני" in tag_lower:
                    difficulty_icon = "🟡 "
                    difficulty_color = "#f59e0b"  # amber
                elif "hard" in tag_lower or "difficult" in tag_lower or "קשה" in tag_lower:
                    difficulty_icon = "🔴 "
                    difficulty_color = "#ef4444"  # red

            md += f"<details style='margin: 10px 0;'>\n"
            md += f"<summary style='cursor: pointer; padding: 12px; background: #fafafa; border-left: 3px solid #9ca3af;'>"
            # Show action summary with time/difficulty tag and icon
            action_summary = action[:80] + '...' if len(action) > 80 else action
            tag_display = f" <span style='color: {difficulty_color}; font-size: 0.9em;'>{difficulty_icon}[{tag}]</span>" if tag and tag != "פעולה מומלצת" else ""
            md += f"<strong style='color: #374151;'>{i}. {action_summary}</strong>{tag_display}"
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
            duration = sections[-1].get('end', '60 דקות') if sections else '60 דקות'

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

        # Add Active Learning section if available
        if self.active_data and isinstance(self.active_data, list):
            md += "\n### 🎯 Active Learning Dimensions\n"

            for module in self.active_data:
                module_name = module.get('dimension', module.get('module', 'Unknown'))
                md += f"\n#### {module_name}\n\n"

                if module.get('strengths'):
                    md += "**חוזקות:**\n"
                    for strength in module['strengths']:
                        md += f"- {strength}\n"

                if module.get('weaknesses'):
                    md += "\n**חולשות:**\n"
                    for weakness in module['weaknesses']:
                        md += f"- {weakness}\n"

                if module.get('recommendations'):
                    md += "\n**המלצות:**\n"
                    for rec in module['recommendations']:
                        md += f"- {rec}\n"

                md += "\n"

        md += "\n---\n\n"

        # Section breakdown
        md += "## 🗂️ מבנה השיעור\n\n"
        if sections:
            for section in sections:
                num = section.get('section_number', '')
                title = section.get('title', '')
                duration = section.get('duration', '')
                md += f"{num}. **{title}** ({duration})\n"

        md += "\n---\n\n"

        # Examples
        md += "## 💡 דוגמאות מהשיעור\n\n"
        if 'examples' in self.output_data:
            for example in self.output_data['examples']:
                topic = example.get('topic', '')
                ex = example.get('example', '')
                ref = example.get('reference', '')
                md += f"- **{topic}:** {ex} *({ref})*\n"

        md += "\n---\n\n"

        # Interactions
        md += "## 💬 אינטראקציות\n\n"
        if 'interactions' in self.output_data:
            for interaction in self.output_data['interactions']:
                time = interaction.get('time', '')
                itype = interaction.get('type', '')
                desc = interaction.get('description', '')
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
                topic = topic_dict.get('topic', '')
                reason = topic_dict.get('reason', '')
                rec = topic_dict.get('recommendation', '')
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
    active_path = os.path.join(output_dir,"active.txt")
    smart_insights_path = os.path.join(output_dir,"smart_insights.json")

    # Check if active.txt exists
    if not os.path.exists(active_path):
        active_path = None

    # Check if smart_insights.json exists
    if not os.path.exists(smart_insights_path):
        smart_insights_path = None

    # Generate snapshot
    generator = SnapshotGenerator(story_path, deep_path, basic_path, active_path, smart_insights_path)

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