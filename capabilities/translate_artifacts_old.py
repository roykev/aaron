import logging
import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import get_tasks
from utils.kimi_utils import OpenRouterProxy
from utils.utils import get_logger
def pref_summary(lan):
    pref = (
        f"Task: Translate the ENTIRE content below to {lan}.\n"
        f"Instructions:\n"
        f"- Translate ALL text content completely from beginning to end\n"
        f"- For technical/scientific terms: keep original term, add translation in parentheses (e.g., 'DNA (حمض نووي)')\n"
        f"- Preserve every markdown heading, bold marker (**), time-stamp, number, and HTML tag exactly as written\n"
        f"- Do not stop until you have translated the complete document\n"
        f"\nContent to translate:\n"
    )
    return pref

def pref_quiz(lan):
    pref = (
        f"Task: Translate the ENTIRE quiz content below to {lan}.\n"
        f"Instructions:\n"
        f"- Translate ALL 'question' and 'choice' values completely\n"
        f"- For technical/scientific terms: keep original term, add translation in parentheses (e.g., 'DNA (حمض نووي)')\n"
        f"- Never translate keys ('question', 'answers', 'choice', 'correct') or boolean values\n"
        f"- Process every question in the document without stopping\n"
        f"\nContent to translate:\n"
    )
    return pref

def pref_mindmap(lan):
    pref = (
        f"Task: Translate the ENTIRE mindmap content below to {lan}.\n"
        f"Instructions:\n"
        f"- Translate ALL visible node labels (text inside square brackets)\n"
        f"- For technical/scientific terms: keep original term, add translation in parentheses (e.g., 'DNA (حمض نووي)')\n"
        f"- Keep every markdown symbol (`mindmap`, `root`, indentation, arrows, quotes) untouched\n"
        f"- Process the complete mindmap structure\n"
        f"\nContent to translate:\n"
    )
    return pref

def pref_concepts(lan):
    pref = (
        f"Task: Translate the ENTIRE concepts JSON below to {lan}.\n"
        f"Instructions:\n"
        f"- Translate ALL 'concept' key values in every JSON object\n"
        f"- For technical/scientific terms: keep original term, add translation in parentheses (e.g., 'DNA (حمض نووي)')\n"
        f"- Leave every key name, quote, colon, comma, bracket, and timestamp string exactly as is\n"
        f"- Keep the JSON structure valid\n"
        f"- Process the complete JSON array\n"
        f"\nContent to translate:\n"
    )
    return pref
class ArtifactsTranslator(OpenRouterProxy):
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(config, api_key, base_url)
    def set_lan(self, lan):
        self.lan= lan
    def read_content(self, filename):
        file_path =os.path.join(self.config["videos_dir"],filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

    def compose_system_prompt(self, lan="English"):
        system_prompt = (
           f"You are a literal, file-agnostic translator translating content to {lan}.  "
"Rules – apply to *every* input:"
"\n1. Translate ONLY human-readable string values; never translate keys, tags, markup symbols, timestamps, numbers, booleans, XML/SVG attributes, or JSON brackets."
"\n2. Preserve every byte of structure: indentation, quotes, commas, colons, brackets, mind-map arrows, CSS, empty arrays, etc."
"\n3. For technical terms, scientific terms, and acronyms: keep the ORIGINAL term and add the translation in parentheses immediately after. Examples: 'DNA (حمض نووي)', 'ATP (أدينوسين ثلاثي الفوسفات)', 'working memory (זיכרון עבודה)'. Always keep the original term first, then parentheses with translation."
"\n4. Leave LaTeX, formulas, file-specific syntax, and section numbers untouched."
"\n5. Output only the translated content—no explanations, no thinking, no code fences, no extra whitespace."
"\n6. Keep the original text direction: LTR for English/Russian source, RTL for Hebrew/Arabic source. Do not flip punctuation order."
"\n7. TRANSLATE ALL TEXT - Do not stop partway through. Continue until the entire document is fully translated."
        )
        self.system_prompt= system_prompt
    def compose_user_prompt(self, lan = "English"):
        user_prompt=(
        f"{self.content}")
        self.user_prompt=user_prompt
def bulk_process(llm_agent, config, pref, task, lan):
    # Check if file exists before processing
    file_path = os.path.join(config["videos_dir"], f"{task}.txt")
    if not os.path.exists(file_path):
        print(f"Warning: Artifact file '{task}.txt' not found in {config['videos_dir']}. Skipping.")
        return

    try:
        llm_agent.read_content(f"{task}.txt")
        llm_agent.prepare_content(lan=lan)
        # Fix: Ensure prefix is properly added to the user prompt
        llm_agent.user_prompt = pref + "\n\n" + llm_agent.user_prompt
        output = llm_agent.call_api()
        output_file = os.path.join(config["videos_dir"], f"{lan}_{task}.txt")
        with open(output_file, "w", encoding='utf-8') as file:
            file.write(output)
        print(f"{task} completed: {len(output)} characters translated")
    except Exception as e:
        print(f"Error processing '{task}': {str(e)}. Skipping.")

if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Process video
    t0 = time.time()
    llmproxy = ArtifactsTranslator(config)
    lan = "Arabic"
    #for short and long summary:
    pref = pref_summary(lan)
    bulk_process(llmproxy, config, pref,"short_summary", lan)
    bulk_process(llmproxy, config, pref,"long_summary", lan)
    pref = pref_quiz(lan)
    bulk_process(llmproxy, config, pref,"quiz", lan)
    bulk_process(llmproxy, config, pref,"quiz_eval", lan)
    #
    pref = pref_concepts(lan)
    bulk_process(llmproxy, config, pref,"concepts", lan)
    pref = pref_mindmap(lan)
    bulk_process(llmproxy, config, pref,"mind_map", lan)


    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')