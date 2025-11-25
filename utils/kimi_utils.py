import logging
import os
import json
import time

import yaml
import pandas as pd
from typing import Dict, Any
from openai import OpenAI
from anthropic import Anthropic

from dotenv import load_dotenv

from teacher_side.teacher_prompts import get_tasks, compose_long_system_prompt, extract_teacher_report_results
from utils.utils import source_key, get_logger

load_dotenv(".env")
env = os.environ

class OpenRouterProxy:
    """
    A class for extracting AI artifacts from class transcripts.
    """
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1", logger=None):
        """
        Initialize the VideoSummarizer.

        Args:
            config: Configuration dictionary from pipe.yaml
            api_key: OpenAI API key (defaults to OPEN_ROUTER_API_KEY env var)
            base_url: Base URL for the API (defaults to OpenRouter)
            logger: Optional logger instance for debugging
        """
        self.config = config
        self.logger = logger
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

        # Get max_tokens from config, default to 12000
        self.max_tokens = self.config.get('llm', {}).get('max_tokens', 12000)

    def call_api(self):
        try:
            # Make API call
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://aarontheowl.com",
                    "X-Title": "Aaron The Owl",
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
                max_tokens=self.max_tokens,
                temperature=0.1,
                top_p=0.8,
            )

            # Extract and return the description
            description = completion.choices[0].message.content.strip()

            # Debug: Log the raw response length
            if hasattr(self, 'logger') and self.logger is not None:
                self.logger.info(f"Raw API response length: {len(description)} characters")
                if len(description) == 0:
                    self.logger.error("API returned empty response!")

            import re
            # Save pre-regex description for debugging
            pre_regex = description
            description = re.sub(r'◁think▷.*?◁/think▷', '', description, flags=re.S).strip()
            description = re.sub(r'<think>.*?</think>', '', description, flags=re.S).strip()

            # Debug: Check if regex removed everything
            if hasattr(self, 'logger') and self.logger is not None and len(pre_regex) > 0 and len(description) == 0:
                self.logger.error("Thinking tag removal regex deleted all content!")
                self.logger.info(f"Pre-regex length: {len(pre_regex)}")
                # Save the pre-regex content for inspection
                debug_file = os.path.join(self.config.get("videos_dir", "."), "debug_pre_regex.txt")
                with open(debug_file, 'w') as f:
                    f.write(pre_regex)
                self.logger.info(f"Saved pre-regex content to {debug_file}")
                # Return the pre-regex version since regex is clearly broken
                return pre_regex

            return description

        except Exception as e:
            if hasattr(self, 'logger') and self.logger is not None:
                self.logger.error(f"API call exception: {type(e).__name__}: {str(e)}")
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


class AnthropicProxy:
    """
    A class for extracting AI artifacts from class transcripts using Anthropic's Claude.
    """
    def __init__(self, config: Dict[str, Any], api_key: str = None, logger=None):
        """
        Initialize the AnthropicProxy.

        Args:
            config: Configuration dictionary from config.yaml
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            logger: Optional logger instance for debugging
        """

        self.config = config
        self.logger = logger
        self.api_key = api_key or source_key("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key is required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")

        self.client = Anthropic(api_key=self.api_key)

        # Use model from config if available, otherwise default to Claude Sonnet
        llm_config = self.config.get('llm', {})
        configured_model = llm_config.get('model', "claude-sonnet-4")

        # If the model is specified as an OpenRouter path (e.g., "anthropic/claude-sonnet-4.5"),
        # extract just the model name
        if "/" in configured_model and configured_model.startswith("anthropic/"):
            self.model = configured_model.split("/", 1)[1]
        else:
            self.model = configured_model

        # Get max_tokens from config, default to 12000
        self.max_tokens = llm_config.get('max_tokens', 12000)

    def call_api(self):
        try:
            # Make API call to Anthropic
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.1,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": self.user_prompt
                    }
                ]
            )

            # Extract and return the description
            description = response.content[0].text.strip()

            # Debug: Log the raw response length
            if hasattr(self, 'logger') and self.logger is not None:
                self.logger.info(f"Raw API response length: {len(description)} characters")
                if len(description) == 0:
                    self.logger.error("API returned empty response!")
                    # Save response object for debugging
                    import json
                    debug_file = os.path.join(self.config.get("videos_dir", "."), "debug_api_response.json")
                    with open(debug_file, 'w') as f:
                        json.dump({
                            "model": response.model,
                            "stop_reason": response.stop_reason,
                            "usage": response.usage.model_dump() if hasattr(response.usage, 'model_dump') else str(response.usage),
                            "content_blocks": len(response.content),
                            "first_block_type": type(response.content[0]).__name__ if response.content else None
                        }, f, indent=2)
                    self.logger.info(f"Saved debug info to {debug_file}")

            # Remove thinking tags if present (similar to OpenRouter version)
            import re
            # Save pre-regex description for debugging
            pre_regex = description
            description = re.sub(r'◁think▷.*?◁/think▷', '', description, flags=re.S).strip()
            description = re.sub(r'<think>.*?</think>', '', description, flags=re.S).strip()

            # Debug: Check if regex removed everything
            if hasattr(self, 'logger') and self.logger is not None and len(pre_regex) > 0 and len(description) == 0:
                self.logger.error("Thinking tag removal regex deleted all content!")
                self.logger.info(f"Pre-regex length: {len(pre_regex)}")
                # Save the pre-regex content for inspection
                debug_file = os.path.join(self.config.get("videos_dir", "."), "debug_pre_regex.txt")
                with open(debug_file, 'w') as f:
                    f.write(pre_regex)
                self.logger.info(f"Saved pre-regex content to {debug_file}")
                # Return the pre-regex version since regex is clearly broken
                return pre_regex

            return description

        except Exception as e:
            if hasattr(self, 'logger') and self.logger is not None:
                self.logger.error(f"API call exception: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Failed to generate analysis: {str(e)}")
    
    def compose_system_prompt(self, lan="English"):
        self.system_prompt = "system prompt"
    
    def compose_user_prompt(self, lan="English"):
        self.user_prompt = "user prompt"
    
    def prepare_prompts(self, lan="English"):
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

