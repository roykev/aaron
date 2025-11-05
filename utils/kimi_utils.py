import logging
import os
import json
import time

import yaml
import pandas as pd
from typing import Dict, Any
from openai import OpenAI

from teacher_side.teacher_prompts import get_tasks, compose_long_system_prompt, extract_teacher_report_results
from utils.utils import source_key, get_logger


class OpenRouterProxy:
    """
    A class for extracting AI artifacts from class transcripts.
    """
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        """
        Initialize the VideoSummarizer.

        Args:
            config: Configuration dictionary from pipe.yaml
            api_key: OpenAI API key (defaults to OPEN_ROUTER_API_KEY env var)
            base_url: Base URL for the API (defaults to OpenRouter)
        """
        self.config = config
        self.api_key = source_key("OPEN_ROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key is required. Set OPEN_ROUTER_API_KEY environment variable or pass api_key parameter.")
        self.client = OpenAI(
            base_url=base_url,
            api_key=self.api_key,
        )

        # Use model from config if available, otherwise default
        self.model = self.config.get('llm', {}).get('model', "moonshotai/kimi-k2:free")

    def call_api(self):
        try:
            # Make API call
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/your-repo",
                    "X-Title": "Class Analyzer",
                },
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": self.user_prompt
                    },

                ],
                max_tokens=12000,
                temperature=0.1,
                top_p=0.8,
            )

            # Extract and return the description
            description = completion.choices[0].message.content.strip()


            import re
            description = re.sub(r'◁think▷.*?◁/think▷', '', description, flags=re.S).strip()
            description = re.sub(r'<think>.*?</think>', '', description, flags=re.S).strip()

            return description

        except Exception as e:
            raise RuntimeError(f"Failed to generate analysis: {str(e)}")
    def compose_system_prompt(self, lan="English"):
        self.system_prompt= "system prompt"
    def compose_user_prompt(self, lan = "English"):
        self.user_prompt= "user prompt"
    def prepare_prompts(self,lan="English"):
        self.compose_user_prompt(lan)
        self.compose_system_prompt(lan)
    def prepare_specific_content(self, lan):
        pass
    def prepare_content(self, lan="English"):
        self.prepare_specific_content(lan)
        self.prepare_prompts(lan)



if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    llmproxy = OpenRouterProxy(config)
    llmproxy.prepare_content()
    output = llmproxy.call_api()
    output_file=os.path.join(config["videos_dir"],"output.txt")
    with open(output_file, "w") as file:
        file.write(output)
    print (output)
    extract_teacher_report_results(config["videos_dir"],output)

    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')

