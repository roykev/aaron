import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import extract_teacher_report_results
from teacher_side.teacher_report import TeacherReport, TeacherReportOR
from utils.utils import get_logger


def task_narrative( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>narrative/<name>\n"
        """Analyze the lecture transcript and identify whether it follows a narrative arc structure. Specifically:

1. **Opening Hook** - What does the instructor use to capture attention in the first 3 minutes? Rate its effectiveness (strong/weak/absent) and identify the type (question/paradox/story/problem/none).

2. **Rising Action** - Identify moments where the instructor builds tension or complexity. List the key "building blocks" in chronological order.

3. **Climax/Aha Moment** - Locate the peak revelation or key insight. What timestamp does it occur? Quote the exact moment.

4. **Resolution** - How does the instructor resolve the tension? Is there a clear answer or synthesis?

5. **Connection to Students** - Does the instructor tie the lesson back to students' lives, future careers, or broader implications?"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_characters( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>characters/<name>\n"
"""Evaluate how the instructor uses "characters" (real people, historical figures, or relatable personas) to make concepts memorable:

1. **Real People Mentioned** - List all named individuals referenced in the lecture (scientists, researchers, historical figures)

2. **Character Development** - For each person mentioned, assess:
   - Is their struggle/journey described? (yes/no)
   - Are they humanized with emotions, failures, or breakthroughs? (yes/no)
   - Do we learn WHY they cared about this problem? (yes/no)
   - Quote any character-building language used

3. **Relatable Scenarios** - Identify any "student like you" or "imagine you're a..." constructions
   - Quote these moments
   - Rate their effectiveness

4. **Missing Character Opportunities** - Identify 3 moments where a character story would have strengthened the lesson"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_Concrete2Abstract( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>Concrete2Abstract/<name>\n"
        """Assess how effectively the instructor bridges concrete experiences to abstract concepts:

1. **Analogies & Metaphors** - Extract all analogies used
   - Quote each analogy
   - Rate quality: excellent/good/weak/unclear
   - Identify if it's fully developed or just mentioned

2. **Sensory Language** - Find instances of:
   - Visual imagery ("picture this," "imagine," "visualize")
   - Concrete examples with specific details (dates, names, places)
   - Physical/tangible comparisons

3. **Abstraction Sequence** - For the 3 main concepts taught:
   - Does instruction start concrete then move abstract? Or reverse?
   - Map the progression (concrete → semi-concrete → abstract)

4. **Gaps** - Identify 3 abstract concepts that lack concrete bridges"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt

def task_curiosity( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>Curiosity/<name>\n"
        """Analyze how the instructor creates and maintains intellectual suspense:

1. **Questions Posed** - List all questions asked by the instructor
   - Categorize: rhetorical/genuine inquiry/check for understanding
   - Which ones create curiosity vs. just check knowledge?
   - Are questions answered immediately or left to simmer?

2. **Mystery & Surprises** - Identify moments of:
   - "But here's what's interesting..."
   - "You might think X, but actually Y..."
   - Intentional puzzles or paradoxes presented
   - Surprising facts or counterintuitive results

3. **Stakes** - Find where the instructor establishes:
   - Why this matters
   - What's at risk
   - Consequences of getting it wrong
   - Real-world impact

4. **Cliffhangers** - Does the instructor use suspense before revealing answers?"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_emotional( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>emotional/<name>\n"
        """Assess the emotional dimensions of the teaching:

1. **Enthusiasm Markers** - Find and quote instances of:
   - Excitement language ("amazing," "incredible," "I love this")
   - Explicit passion statements
   - Vocal variety indicators (if mentioned in transcript)

2. **Empathy & Acknowledgment** - Identify when instructor:
   - Acknowledges difficulty ("I know this is hard")
   - Shares personal struggles ("this confused me too")
   - Validates student confusion
   - Shows patience

3. **Wonder & Amazement** - Find expressions of:
   - "Beautifully," "elegantly," "remarkably"
   - Appreciation for the subject matter
   - Moments of genuine awe

4. **Relevance to Students** - Search for phrases:
   - "You'll use this when..."
   - "In your future career..."
   - "This matters because YOU..."
   - Personal benefit statements"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_Coherence( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>Coherence/<name>\n"
        """Evaluate the logical flow and connectedness of the lecture:

1. **Signposting** - Identify all transition phrases:
   - "First," "Next," "Finally"
   - "This leads us to..."
   - "Because of that..."
   - "Now we understand..."
   - Rate clarity of each transition

2. **Callbacks & References** - Find instances where instructor:
   - References earlier points ("Remember when we...")
   - Links to previous lessons
   - Creates continuity across topics

3. **Central Thread** - Identify:
   - What is the ONE main question/theme?
   - How many times does the instructor return to it?
   - Is it maintained throughout or does it drift?

4. **Digressions** - Mark tangents or administrative interruptions
   - Do they break narrative flow?
   - How does instructor return to the main thread?

5. **Progressive Revelation** - Does each section build logically on the previous?
   - Map the information architecture
   - Identify any logical gaps or jumps"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt

tasks_dict = {
        "curiosity":task_curiosity,
        "Coherence": task_Coherence,
        "emotional": task_emotional,
        "narrative": task_narrative,
        "Concrete2Abstract": task_Concrete2Abstract,
        "characters": task_characters

    }
def build_tasks_array(lan="English"):
    unified_tasks = ""
    for task in tasks_dict.values():
        unified_tasks+= task(lan=lan) + "\n"
    return unified_tasks


class TeacherReportStoryTelling(TeacherReport):
    """Storytelling analysis using Anthropic's Claude (default)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None):
        super().__init__(config, api_key)

    def compose_system_prompt(self, lan="English"):      # System prompt - defines the analyzer's role and output format
            system_prompt= ("You are an expert educational content analyzer specializing in storytelling and pedagogical effectiveness. Your role is to analyze lecture transcriptions and assess the instructor's use of narrative techniques to enhance learning."

"You have deep knowledge of:"
"1. **Narrative theory** and story structure (hero's journey, three-act structure, dramatic arcs)"
"2. **Cognitive science** of learning and memory (how stories aid retention)"
"3. **Educational psychology** (engagement, motivation, emotional learning)"
"4. **Rhetoric and communication** (persuasion, clarity, audience connection)"
"5. **Examples from master educators** (Richard Feynman, Carl Sagan, Hans Rosling, etc.)"
"You must analyze across several modules and return valid JSON only (no markdown, no extra text):"
"For each module, return this exact JSON structure:"
                """{
                  "module": "module_name",                 
                  "strengths": ["strength 1", "strength 2"],
                  "weaknesses": ["weakness 1", "weakness 2"],
                  "recommendations": ["recommendation 1", "recommendation 2"],
                  "evidence": ["quote 1", "quote 2"]
                }"""
        "Return a JSON array "

        f"Here is the information about the course:"
        f"<transcript>{self.transcript}</transcript>"
        f"Output specifications"
        f"<output_language>{lan}</output_language>" 
                            f"<course_name> {self.course_name}</course_name>"
                           f"<class_level>{self.class_level}</class_level>"
                    )
            #TODO in the future i will add  difficult_topics ,     quiz_results ,    office_hours_questions

            self.system_prompt = system_prompt
    def compose_user_prompt(self, lan = "English"):
        self.user_prompt = build_tasks_array(lan=lan)


class TeacherReportStoryTellingOR(TeacherReportOR):
    """Storytelling analysis using OpenRouter (secondary option)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(config, api_key, base_url)
        # Set additional properties
        self.course_name = config.get("course_name", "Unknown Course")
        self.class_level = config.get("class_level", "Unknown Level")
    
    # Share the same methods with TeacherReportStoryTelling
    compose_system_prompt = TeacherReportStoryTelling.compose_system_prompt
    compose_user_prompt = TeacherReportStoryTelling.compose_user_prompt



if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    llmproxy = TeacherReportStoryTelling(config)
    llmproxy.course_name="Intro to AI"
    llmproxy.class_level="undergraduate 3rd year"

    llmproxy.prepare_content()
    output = llmproxy.call_api()
    output_file=os.path.join(config["videos_dir"],"story.txt")
    with open(output_file, "w") as file:
         file.write(output)
    print (output)
    #extract_teacher_report_results(config["videos_dir"],output)

    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')