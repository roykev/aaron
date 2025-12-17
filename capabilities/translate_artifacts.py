#!/usr/bin/env python3
"""
Artifact Translation - V2
Translates educational artifacts to a target language using a single LLM call with parallel tasks.
All translated files are stored in a language-specific subfolder with original names.
"""

import os
import json
import re
from typing import Dict, Any, List, Tuple
import yaml

from utils.kimi_utils import OpenRouterProxy, AnthropicProxy
from utils.utils import get_logger


# Artifact definitions
ARTIFACTS = {
    "short_summary": {
        "filename": "short_summary.txt",
        "type": "text",
        "instructions": "Translate the entire summary text. Preserve markdown formatting (**, ##, etc.)."
    },
    "long_summary": {
        "filename": "long_summary.txt",
        "type": "text",
        "instructions": "Translate the entire detailed summary text. Preserve markdown formatting."
    },
    "quiz": {
        "filename": "quiz.txt",
        "type": "json",
        "instructions": "Translate only 'question' and 'choice' values. Do NOT translate keys like 'question', 'answers', 'choice', 'correct', or boolean values."
    },
    "quiz_eval": {
        "filename": "quiz_eval.txt",
        "type": "json",
        "instructions": "Translate only 'question' and 'choice' values. Do NOT translate keys like 'question', 'answers', 'choice', 'correct', or boolean values."
    },
    "concepts": {
        "filename": "concepts.txt",
        "type": "json",
        "instructions": "Translate only the 'concept' field values in each JSON object. Keep all keys, structure, and timestamps intact."
    },
    "mind_map": {
        "filename": "mind_map.txt",
        "type": "text",
        "instructions": "Translate only the text inside square brackets (node labels). Keep all markdown mindmap syntax (`mindmap`, `root`, indentation, arrows) untouched."
    },
    "mind_map_svg": {
        "filename": "mind_map.svg",
        "type": "svg",
        "instructions": "Translate the text strings in the array. Return a JSON array with translations in the SAME ORDER as the input array."
    }
}


class ArtifactTranslatorBase:
    """Base class for artifact translation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.videos_dir = config.get("videos_dir")
        self.target_language = config.get("translation", {}).get("target_language", "Arabic")
        self.output_folder = config.get("translation", {}).get("output_folder_name", "arabic")
        self.artifacts_content = {}

    def read_artifacts(self):
        """Read all available artifact files."""
        self.artifacts_content = {}

        for artifact_id, artifact_info in ARTIFACTS.items():
            file_path = os.path.join(self.videos_dir, artifact_info["filename"])

            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()

                        # For SVG files, extract only text content
                        if artifact_info["type"] == "svg":
                            svg_texts = extract_svg_text_content(content)
                            # Store as JSON array for translation
                            self.artifacts_content[artifact_id] = json.dumps(svg_texts, ensure_ascii=False)
                            print(f"✓ Loaded: {artifact_info['filename']} ({len(svg_texts)} text strings)")
                        else:
                            self.artifacts_content[artifact_id] = content
                            print(f"✓ Loaded: {artifact_info['filename']}")
                except Exception as e:
                    print(f"⚠ Warning: Could not read {artifact_info['filename']}: {e}")
            else:
                print(f"⚠ Warning: {artifact_info['filename']} not found, skipping")

    def compose_system_prompt(self):
        """Compose system prompt for translation."""
        system_prompt = (
            f"You are a professional translator specializing in educational content translation to {self.target_language}.\n\n"

            "TRANSLATION RULES:\n"
            "1. Translate ONLY human-readable text content to the target language\n"
            "2. For technical/scientific terms: keep the ORIGINAL term and add translation in parentheses\n"
            "   Examples: 'DNA (حمض نووي)', 'working memory (זיכרון עבודה)'\n"
            "3. Preserve ALL structure:\n"
            "   - JSON keys, brackets, commas, colons, quotes\n"
            "   - Markdown syntax (##, **, -, etc.)\n"
            "   - Mindmap syntax (indentation, arrows, backticks)\n"
            "   - Timestamps and numbers\n"
            "4. Do NOT translate:\n"
            "   - JSON keys\n"
            "   - Boolean values (true/false)\n"
            "   - Numbers, timestamps\n"
            "   - Markup/syntax symbols\n"
            "5. Keep text direction appropriate (RTL for Hebrew/Arabic, LTR for English/Russian)\n"
            "6. Output ONLY valid JSON - NO markdown code fences (```json), NO extra text\n\n"

            "OUTPUT FORMAT:\n"
            "Return a single JSON object with translated content:\n"
            "{\n"
        )

        # Add structure for each available artifact
        artifact_fields = []
        for artifact_id in self.artifacts_content.keys():
            artifact_fields.append(f'  "{artifact_id}": "translated content here"')

        system_prompt += ",\n".join(artifact_fields)
        system_prompt += (
            "\n}\n\n"
            f"All translated text must be in {self.target_language}.\n"
            "Return ONLY the JSON object, no markdown fences or explanations."
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self):
        """Compose user prompt with all artifacts to translate."""
        prompt_parts = [
            f"Translate the following educational artifacts to {self.target_language}.\n"
            f"Follow the specific instructions for each artifact type.\n\n"
        ]

        for artifact_id, content in self.artifacts_content.items():
            artifact_info = ARTIFACTS[artifact_id]
            prompt_parts.append(
                f"## ARTIFACT: {artifact_id}\n"
                f"Filename: {artifact_info['filename']}\n"
                f"Type: {artifact_info['type']}\n"
                f"Instructions: {artifact_info['instructions']}\n\n"
                f"Content:\n"
                f"<{artifact_id}>\n"
                f"{content}\n"
                f"</{artifact_id}>\n\n"
                f"---\n\n"
            )

        prompt_parts.append(
            f"FINAL INSTRUCTIONS:\n"
            f"- Translate all artifacts to {self.target_language}\n"
            f"- Return a single JSON object with all translations\n"
            f"- Use artifact IDs as JSON keys: {', '.join(self.artifacts_content.keys())}\n"
            f"- NO markdown code fences\n"
            f"- Ensure valid JSON structure\n"
        )

        self.user_prompt = "\n".join(prompt_parts)

    def prepare_content(self):
        """Prepare content for translation."""
        self.read_artifacts()
        if not self.artifacts_content:
            raise ValueError("No artifacts found to translate!")
        self.compose_system_prompt()
        self.compose_user_prompt()


class ArtifactTranslator(ArtifactTranslatorBase, AnthropicProxy):
    """Artifact translator using Anthropic Claude."""

    def __init__(self, config: Dict[str, Any], api_key: str = None, logger=None):
        AnthropicProxy.__init__(self, config, api_key, logger)
        ArtifactTranslatorBase.__init__(self, config)


class ArtifactTranslatorOR(ArtifactTranslatorBase, OpenRouterProxy):
    """Artifact translator using OpenRouter."""

    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1", logger=None):
        OpenRouterProxy.__init__(self, config, api_key, base_url, logger)
        ArtifactTranslatorBase.__init__(self, config)


def clean_llm_output(output: str) -> str:
    """
    Remove markdown code fences and other artifacts from LLM output.

    Args:
        output: Raw LLM output string

    Returns:
        Cleaned JSON string
    """
    output = output.strip()

    # Remove opening markdown fence (```json or ```)
    if output.startswith('```'):
        # Find the first newline after the opening fence
        first_newline = output.find('\n')
        if first_newline != -1:
            output = output[first_newline + 1:]
        else:
            # No newline found, just remove the fence
            output = output[3:]

    # Remove closing markdown fence (```)
    # Look for the last occurrence of ``` on a line by itself
    lines = output.split('\n')

    # Remove trailing lines that are just ```
    while lines and lines[-1].strip() == '```':
        lines = lines[:-1]

    output = '\n'.join(lines)

    # Remove any leading/trailing whitespace again
    output = output.strip()

    return output


def extract_svg_text_content(svg_content: str) -> List[str]:
    """
    Extract actual text content from SVG <text> elements (removing HTML tags).

    Args:
        svg_content: SVG file content as string

    Returns:
        List of unique text strings
    """
    # Find all <text>...</text> elements and their content
    text_pattern = r'<text[^>]*>(.*?)</text>'
    matches = re.findall(text_pattern, svg_content, re.DOTALL)

    # Extract actual text from each match by removing all HTML tags
    texts = []
    for match in matches:
        # Remove all tags from the match (like <tspan>, </tspan>, etc.)
        cleaned = re.sub(r'<[^>]+>', '', match)
        cleaned = cleaned.strip()
        if cleaned:
            texts.append(cleaned)

    # Create unique list of text content (remove duplicates)
    unique_texts = list(set(texts))

    return unique_texts


def translate_svg_texts(texts: List[str], target_language: str, translator) -> Dict[str, str]:
    """
    Translate a list of text strings using the LLM.

    Args:
        texts: List of text strings to translate
        target_language: Target language name
        translator: Translator instance (ArtifactTranslator or ArtifactTranslatorOR)

    Returns:
        Dictionary mapping original text to translated text
    """
    if not texts:
        return {}

    # Create a simple prompt for translation
    texts_json = json.dumps(texts, ensure_ascii=False, indent=2)

    translator.system_prompt = (
        f"You are a professional translator specializing in educational content translation to {target_language}.\n"
        "Translate each text string in the provided JSON array.\n"
        "For technical/scientific terms: keep the ORIGINAL term and add translation in parentheses.\n"
        f"Return a JSON object mapping each original text to its {target_language} translation.\n"
        "Output ONLY valid JSON - NO markdown code fences, NO extra text."
    )

    translator.user_prompt = (
        f"Translate the following text strings to {target_language}:\n\n"
        f"{texts_json}\n\n"
        f"Return a JSON object with this structure:\n"
        '{\n'
        '  "original text 1": "translated text 1",\n'
        '  "original text 2": "translated text 2"\n'
        '}\n'
    )

    output = translator.call_api()
    cleaned = clean_llm_output(output)

    # Parse the translation mapping
    from json import JSONDecoder
    decoder = JSONDecoder()
    try:
        translation_map, idx = decoder.raw_decode(cleaned)
    except json.JSONDecodeError:
        translation_map = json.loads(cleaned)

    return translation_map


def replace_svg_text_content(svg_content: str, translation_map: Dict[str, str]) -> str:
    """
    Replace text content in SVG with translated versions while preserving structure.

    Args:
        svg_content: Original SVG content
        translation_map: Dictionary mapping original text to translated text

    Returns:
        SVG content with translated text
    """
    def replace_text(match):
        # Extract the full match including <text> tags and attributes
        text_attrs = match.group(1)  # Attributes of <text> tag
        text_content = match.group(2)  # Full content including <tspan> tags

        # Extract actual text by removing all HTML tags
        original_text = re.sub(r'<[^>]+>', '', text_content).strip()

        # Get translated text
        translated_text = translation_map.get(original_text, original_text)

        # Strategy: Find the first innermost <tspan> tag and replace its content
        # Remove all other text nodes to avoid duplication

        # Find the deepest level of tspan nesting
        # Pattern: <tspan...>TEXT</tspan> where TEXT doesn't contain < or >
        innermost_tspan_pattern = r'(<tspan[^>]*>)([^<]*)(</tspan>)'

        # Track if we've inserted the translation yet
        translation_inserted = False

        def replace_innermost(m):
            nonlocal translation_inserted
            opening = m.group(1)
            text_node = m.group(2)
            closing = m.group(3)

            # If this has actual text content and we haven't inserted translation yet
            if text_node.strip() and not translation_inserted:
                translation_inserted = True
                return opening + translated_text + closing
            else:
                # Remove the text content but keep the tags
                return opening + closing

        # Replace text in innermost tspan elements
        new_content = re.sub(innermost_tspan_pattern, replace_innermost, text_content)

        return f'<text{text_attrs}>{new_content}</text>'

    text_pattern = r'<text([^>]*)>(.*?)</text>'
    result = re.sub(text_pattern, replace_text, svg_content, flags=re.DOTALL)

    return result


def save_translated_artifacts(translations: Dict[str, str], config: Dict[str, Any], logger):
    """
    Save translated artifacts to language-specific subfolder.

    Args:
        translations: Dictionary mapping artifact_id to translated content
        config: Configuration dictionary
        logger: Logger instance
    """
    videos_dir = config.get("videos_dir")
    output_folder = config.get("translation", {}).get("output_folder_name", "arabic")

    # Create output directory
    output_dir = os.path.join(videos_dir, output_folder)
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Created output directory: {output_dir}")

    # Save each translated artifact with original filename
    for artifact_id, translated_content in translations.items():
        if artifact_id not in ARTIFACTS:
            logger.warning(f"Unknown artifact ID '{artifact_id}', skipping")
            continue

        artifact_info = ARTIFACTS[artifact_id]
        output_file = os.path.join(output_dir, artifact_info["filename"])

        try:
            # Special handling for SVG files
            if artifact_info["type"] == "svg":
                # Read the original SVG file
                svg_file = os.path.join(videos_dir, artifact_info["filename"])
                with open(svg_file, 'r', encoding='utf-8') as f:
                    svg_content = f.read()

                # Extract original text list from SVG
                original_texts = extract_svg_text_content(svg_content)

                # Parse the translation array
                if isinstance(translated_content, str):
                    translated_array = json.loads(clean_llm_output(translated_content))
                else:
                    translated_array = translated_content

                # Create translation map from original->translated pairs
                translation_map = {}
                for i, original in enumerate(original_texts):
                    if i < len(translated_array):
                        translation_map[original] = translated_array[i]
                    else:
                        logger.warning(f"  ⚠ Missing translation for: {original}")
                        translation_map[original] = original

                # Replace text in SVG
                translated_svg = replace_svg_text_content(svg_content, translation_map)

                # Save translated SVG
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(translated_svg)

                logger.info(f"  ✅ Saved: {output_file}")

            else:
                # Clean the content (remove any remaining markdown artifacts)
                cleaned_content = clean_llm_output(translated_content) if isinstance(translated_content, str) else translated_content

                with open(output_file, 'w', encoding='utf-8') as f:
                    if artifact_info["type"] == "json":
                        # For JSON files, ensure proper formatting
                        if isinstance(cleaned_content, str):
                            # Try to parse and re-serialize for clean formatting
                            try:
                                parsed = json.loads(cleaned_content)
                                f.write(json.dumps(parsed, ensure_ascii=False, indent=2))
                            except json.JSONDecodeError:
                                # If parsing fails, write as-is
                                f.write(cleaned_content)
                        else:
                            f.write(json.dumps(cleaned_content, ensure_ascii=False, indent=2))
                    else:
                        # For text files, write as-is
                        f.write(cleaned_content if isinstance(cleaned_content, str) else str(cleaned_content))

            logger.info(f"  ✅ Saved: {output_file}")

        except Exception as e:
            logger.error(f"  ❌ Failed to save {artifact_info['filename']}: {e}")


def main():
    """Main function for artifact translation."""
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    target_language = config.get("translation", {}).get("target_language", "Arabic")
    output_folder = config.get("translation", {}).get("output_folder_name", "arabic")

    logger.info(f"Starting artifact translation to {target_language}")
    logger.info(f"Output folder: {output_folder}/")

    # Determine which LLM backend to use
    use_openrouter = config.get("llm", {}).get("use_openrouter", False)

    if use_openrouter:
        logger.info("Using OpenRouter backend")
        translator = ArtifactTranslatorOR(config, logger=logger)
    else:
        logger.info("Using Anthropic Claude backend")
        translator = ArtifactTranslator(config, logger=logger)

    # Prepare content
    logger.info("Loading artifacts...")
    translator.prepare_content()

    if not translator.artifacts_content:
        logger.error("No artifacts found to translate!")
        return

    logger.info(f"Found {len(translator.artifacts_content)} artifacts to translate")

    # Call LLM
    logger.info("Calling LLM for translation...")
    output = translator.call_api()

    # Save raw output for debugging
    raw_file = os.path.join(config["videos_dir"], "translation_raw_output.txt")
    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(output)
    logger.info(f"Raw output saved to: {raw_file}")

    # Clean and parse output
    try:
        cleaned_output = clean_llm_output(output)

        # Try to parse JSON - use JSONDecoder to handle extra data after valid JSON
        from json import JSONDecoder
        decoder = JSONDecoder()
        try:
            translations, idx = decoder.raw_decode(cleaned_output)
            if idx < len(cleaned_output):
                remaining = cleaned_output[idx:].strip()
                if remaining:
                    logger.warning(f"Extra data after JSON (ignored): {repr(remaining[:100])}")
        except json.JSONDecodeError:
            # Fall back to regular json.loads if raw_decode fails
            translations = json.loads(cleaned_output)

        # Save translated artifacts
        logger.info("Saving translated artifacts...")
        save_translated_artifacts(translations, config, logger)

        logger.info(f"✅ Translation completed successfully!")
        logger.info(f"Translated files saved to: {os.path.join(config['videos_dir'], output_folder)}/")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse LLM output as JSON: {e}")
        logger.error(f"First 500 chars of cleaned output: {cleaned_output[:500]}")
        logger.error(f"Last 500 chars of cleaned output: {cleaned_output[-500:]}")


if __name__ == '__main__':
    main()