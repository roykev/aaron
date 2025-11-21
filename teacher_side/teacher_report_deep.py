import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import extract_teacher_report_results
from teacher_side.teacher_report import TeacherReport
from utils.utils import get_logger


def task_communication( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>communication/<name>\n"
        f"Evaluate the instructor's communication effectiveness."
        "**Sub-dimensions:**"
        "**Language Clarity**: Assess sentence structure, jargon usage, and explanation clarity"
        "- **Vocabulary Appropriateness**: Evaluate vocabulary level for the target audience"
        "- **Speech Patterns**: Analyze pacing, filler words, pauses, and verbal fluency"
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_engagement( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>engagement/<name>\n"
        "Evaluate how well the instructor maintains student engagement."
        "**Sub-dimensions:**"
       "- **Interaction Quality**: Questions asked, student participation encouraged, responsiveness"
       "- **Energy and Enthusiasm**: Instructor's energy level and passion for material"
       "- **Attention Management**: Use of examples, stories, and engagement techniques"
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
def task_pedagogical( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>pedagogical/<name>\n"
        "Evaluate the instructional approach and pedagogical effectiveness."
        "**Sub-dimensions:**"
      """- **Scaffolding**: Building from simple to complex concepts
- **Example Quality**: Relevance, clarity, and diversity of examples
- **Assessment Integration**: Checking for understanding, formative feedback
- **Learning Theory Application**: Use of active learning, constructivism, etc."""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt

def task_content( lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>content/<name>\n"
        "Evaluate the effectiveness of content delivery."
        "**Sub-dimensions:**"
      """- **Difficult Topics Handling**: How well challenging material was explained (cross-reference with difficult_topics input if provided)
- **Conceptual Gaps**: Missing explanations or logical jumps
- **Depth vs Breadth**: Appropriate coverage for class level
- **Accuracy**: Correctness of information presented"""
        "include the following: strengths, weaknesses, recommendations, evidence"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"
    )
    return prompt
tasks_dict = {
        "communication":task_communication,
        "content": task_content,
        "pedagogical": task_pedagogical,
        "engagement": task_engagement
    }
def build_tasks_array(lan="English"):
    unified_tasks = ""
    for task in tasks_dict.values():
        unified_tasks+= task(lan=lan) + "\n"
    return unified_tasks


class TeacherReportDeep(TeacherReport):
    """Deep analysis using Anthropic's Claude (default)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None, logger=None):
        super().__init__(config, api_key, logger)

    def compose_system_prompt(self, lan="English"):      # System prompt - defines the analyzer's role and output format
            system_prompt= ("You are an educational content analyzer. Analyze the provided lecture transcription across multiple dimensions and provide structured feedback for improvement."
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


class TeacherReportDeepOR(TeacherReport):
    """Deep analysis using OpenRouter (secondary option)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1", logger=None):
        # Import the OR version
        from teacher_side.teacher_report import TeacherReportOR
        # Initialize with OpenRouter parent
        TeacherReportOR.__init__(self, config, api_key, base_url, logger)
    
    # Share the same methods with TeacherReportDeep
    compose_system_prompt = TeacherReportDeep.compose_system_prompt
    compose_user_prompt = TeacherReportDeep.compose_user_prompt



if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    llmproxy = TeacherReportDeep(config)
    llmproxy.course_name = "Intro to AI"
    llmproxy.class_level = "undergraduate 3rd year"

    llmproxy.prepare_content()
    output = llmproxy.call_api()
    output_file=os.path.join(config["videos_dir"],"deep.txt")
    with open(output_file, "w") as file:
         file.write(output)
    print (output)
    #extract_teacher_report_results(config["videos_dir"],output)

    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')