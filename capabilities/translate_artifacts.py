import logging
import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import get_tasks
from utils.kimi_utils import OpenRouterProxy
from utils.utils import get_logger
def pref_summary(lan):
    pref = (f"[{lan}]\n"  
    f"Translate all text inside the <summary> block. to {lan} while leaving every structure intact"
"Preserve every markdown heading, bold marker (**), time-stamp, number, and HTML tag exactly as written."
            )
    return pref
def pref_quiz(lan):
    pref =(f"[{lan}]\n"  
f"Translate only the values of 'question' and 'choice' keys. to {lan}, while leaving every structure intact"  
f"Never translate keys ('question', 'answers', 'choice', 'correct') or boolean values."
           )
    return pref
def pref_mindmap(lan):
    pref = (f"[{lan}]\n"  
f"Translate only the visible node labels (text inside square brackets). to {lan} while leaving every structure intact"  
"Keep every markdown symbol (`mindmap`, `root`, indentation, arrows, quotes) untouched.")
    return pref
def pref_concepts(lan):
    pref = (f"[{lan}]\n"  
    f"Translate only the values of the 'concept' keys in the JSON below to {lan}.while leaving every structure intact"
            "Leave every key name, quote, colon, comma, bracket, and timestamp string exactly as is."
            "Keep the JSON structure valid "
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
           "You are a literal, file-agnostic translator.  "
"Rules – apply to *every* input:"  
"1. Translate ONLY human-readable string values; never translate keys, tags, markup symbols, timestamps, numbers, booleans, XML/SVG attributes, or JSON brackets."  
"Preserve every byte of structure: indentation, quotes, commas, colons, brackets, mind-map arrows, CSS, empty arrays, etc."
"3. First occurrence of any technical term or acronym: keep the original term and add its translation in parentheses immediately after, e.g. 'ATP (ATP)'."  
"4. Leave LaTeX, formulas, file-specific syntax, and section numbers untouched.  "
"5. Output only the translated content—no explanations, no thinking, no code fences, no extra whitespace."
"6. Keep the original text direction: LTR for English/Russian source, RTL for Hebrew/Arabic source. Do not flip punctuation order."

        )
        self.system_prompt= system_prompt
    def compose_user_prompt(self, lan = "English"):
        user_prompt=(
        f"{self.content}")
        self.user_prompt=user_prompt
def bulk_process(llm_agent, config, pref, task, lan):
    llm_agent.read_content(f"{task}.txt")
    llm_agent.prepare_content(lan=lan)
    llm_agent.user_prompt = pref + llmproxy.user_prompt
    output = llm_agent.call_api()
    output_file = os.path.join(config["videos_dir"], f"{lan}_{task}.txt")
    with open(output_file, "w") as file:
        file.write(output)
    print(f"{task}: \n, {output}")

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