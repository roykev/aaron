import logging
import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import get_tasks, extract_teacher_report_results
from utils.kimi_utils import OpenRouterProxy
from utils.utils import get_logger


class TeacherReport(OpenRouterProxy):
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(config, api_key, base_url)
    def read_transcript(self, suffix='.txt'):
        def find_transcript_file(videos_dir: str, suffix='.txt') -> str:
            """
            Find the transcript file (.txt, .vtt, or .srt) in the videos directory.

            Args:
                videos_dir: Path to the videos directory
                suffix: File extension to search for (default: '.txt')

            Returns:
                Path to the transcript file
            """
            # List of supported transcript formats
            supported_formats = ['.txt', '.vtt', '.srt']

            # If a specific suffix is provided, prioritize it
            search_order = [suffix] + [fmt for fmt in supported_formats if fmt != suffix]

            for fmt in search_order:
                for file in os.listdir(videos_dir):
                    if file.endswith(fmt):
                        return os.path.join(videos_dir, file)

            raise FileNotFoundError(f"No transcript file (.txt, .vtt, or .srt) found in {videos_dir}")

        def parse_transcript_txt(transcript_path: str) -> str:
            """
            Read and extract the full transcript text from the file.

            Args:
                transcript_path: Path to the transcript file

            Returns:
                Full transcript text
            """
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
            logging.debug("Done reading transcript")
        else:
            logging.error(f"{trans_path}, suffix not supported!")

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
        self.read_transcript()

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