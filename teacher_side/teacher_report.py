import logging
import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import get_tasks, extract_teacher_report_results
from teacher_side.teacher_utils import read_transcript
from utils.kimi_utils import  OpenRouterProxy
from utils.utils import get_logger


class TeacherReport(OpenRouterProxy):
    """Teacher report using Anthropic's Claude (default)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None):
        super().__init__(config, api_key)

    def compose_system_prompt(self, lan="English"):
        system_prompt = (
            f"You are an teaching assistant. Your task is to analyze a university class based on its transcript, and then perform several specific tasks. "
            f"The analysis and output should be in the following language: {lan}"
            f"Here is the information about the video:"
            f"<transcript>{self.transcript}</transcript>\n\n"
            f"Output specifications"
            f" <output_language>{lan}</output_language>\n"
            f"Don't write any system generated content. return only the output in the specified format. no more no less "
            f"include the header of the column (column names) in the output\n"
            f"separate each task with a new line and ### task name ###"
            )
        self.system_prompt= system_prompt

    def compose_user_prompt(self, lan = "English"):
        self.user_prompt = get_tasks(lan)
    
    def prepare_specific_content(self, lan):
        self.transcript = read_transcript(self.config["videos_dir"])


class TeacherReportOR(OpenRouterProxy):
    """Teacher report using OpenRouter (secondary option)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(config, api_key, base_url)
    
    # Share the same methods with TeacherReport
    compose_system_prompt = TeacherReport.compose_system_prompt
    compose_user_prompt = TeacherReport.compose_user_prompt
    prepare_specific_content = TeacherReport.prepare_specific_content

if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Get language from config, default to English if not specified
    language = config.get("language", "English")

    # Process video
    t0 = time.time()
    llmproxy = TeacherReport(config)
    llmproxy.prepare_content(lan=language)
    output = llmproxy.call_api()
    output_file=os.path.join(config["videos_dir"],"output.txt")
    with open(output_file, "w") as file:
         file.write(output)
    print (output)
    #extract_teacher_report_results(config["videos_dir"],output)

    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')