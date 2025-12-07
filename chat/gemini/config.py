"""
Configuration management for Gemini RAG system
Integrates with project-wide config.yaml
"""

import os
import sys
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add project root to path to import utils
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from utils.utils import source_key


# Find the project root config.yaml
def find_project_config() -> str:
    """Find the project root config.yaml file"""
    current_dir = Path(__file__).resolve().parent

    # Search up the directory tree for config.yaml
    for parent in [current_dir] + list(current_dir.parents):
        config_path = parent / "config.yaml"
        if config_path.exists():
            return str(config_path)

    raise FileNotFoundError("Could not find config.yaml in project directories")


@dataclass
class GeminiConfig:
    """Configuration for Gemini RAG system"""

    # API Configuration
    api_key: str

    # Store Configuration
    store_display_name: str = "Psychology_Lecture_RAG_Store"
    # Note: store_id is looked up from registry using (institute, course_name)

    # Chunking Configuration
    chunk_interval_seconds: int = 30
    output_dir: str = "psychology_chunks"

    # Model Configuration
    model_name: str = "gemini-2.0-flash-exp"

    # Upload Configuration
    max_upload_wait_seconds: int = 300  # 5 minutes
    max_files_per_query: int = 10

    # Logging Configuration
    query_log_path: str = "chat/gemini/query_log.json"
    institute: str = ""

    # Context file paths (from YAML or command line)
    concepts_file: str = "concepts.txt"
    summary_file: str = "short_summary.txt"

    # Videos directory (base path for finding files)
    videos_dir: Optional[str] = None

    # File paths (can be overridden per lecture)
    vtt_path: Optional[str] = None
    concepts_path: Optional[str] = None
    summary_path: Optional[str] = None
    lecture_id: Optional[str] = None

    # Project-level configuration (loaded from YAML)
    language: str = "English"  # Default fallback
    course_name: str = "course"  # Default fallback
    class_level: str = "undergraduate"  # Default fallback

    @classmethod
    def from_project_config(cls, config_path: Optional[str] = None) -> 'GeminiConfig':
        """
        Create configuration from project-wide config.yaml

        Args:
            config_path: Optional path to config.yaml (auto-detected if not provided)

        Returns:
            GeminiConfig instance
        """
        # Find config file
        if config_path is None:
            config_path = find_project_config()

        # Load YAML config
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)

        # Get API key from environment (Gemini uses GEMINI_API_KEY)
        api_key = source_key("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set it with: export GEMINI_API_KEY='your-api-key'"
            )

        # Extract project-level configuration
        language = yaml_config.get('language', 'English')
        course_name = yaml_config.get('course_name', 'course')
        class_level = yaml_config.get('class_level', 'undergraduate')
        videos_dir = yaml_config.get('videos_dir')

        # Extract Gemini-specific configuration (if exists)
        gemini_config = yaml_config.get('gemini_rag', {})

        # Get institute from config
        institute = gemini_config.get('institute', '')

        # Auto-generate store_display_name from institute and course
        if institute:
            store_display_name = f"{institute}_{course_name}_RAG"
        else:
            store_display_name = f"{course_name}_RAG"

        # Allow manual override from YAML if specified
        store_display_name = gemini_config.get('store_name', store_display_name)

        config = cls(
            api_key=api_key,
            language=language,
            course_name=course_name,
            class_level=class_level,
            videos_dir=videos_dir,
            store_display_name=store_display_name,
            chunk_interval_seconds=gemini_config.get('chunk_interval_seconds', 30),
            model_name=gemini_config.get('model', 'gemini-2.0-flash-exp'),
            max_upload_wait_seconds=gemini_config.get('max_upload_wait_seconds', 300),
            max_files_per_query=gemini_config.get('max_files_per_query', 10),
            query_log_path=gemini_config.get('query_log_path', 'chat/gemini/query_log.json'),
            institute=institute,
            concepts_file=gemini_config.get('concepts_file', 'concepts.txt'),
            summary_file=gemini_config.get('summary_file', 'short_summary.txt')
        )

        return config

    def get_concepts_path(self) -> Optional[str]:
        """Get full path to concepts file"""
        if self.videos_dir and self.concepts_file:
            return os.path.join(self.videos_dir, self.concepts_file)
        return self.concepts_file

    def get_summary_path(self) -> Optional[str]:
        """Get full path to summary file"""
        if self.videos_dir and self.summary_file:
            return os.path.join(self.videos_dir, self.summary_file)
        return self.summary_file

    @classmethod
    def from_env(cls, store_name: Optional[str] = None) -> 'GeminiConfig':
        """
        Create configuration from environment variables only
        (Fallback method for simple usage)

        Args:
            store_name: Optional custom store name

        Returns:
            GeminiConfig instance
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set it with: export GEMINI_API_KEY='your-api-key'"
            )

        config = cls(api_key=api_key)

        if store_name:
            config.store_display_name = store_name

        return config

    def update_lecture_paths(self, vtt_path: str, concepts_path: str, summary_path: str, lecture_id: str):
        """
        Update file paths and lecture ID for a specific lecture

        Args:
            vtt_path: Path to VTT transcript file
            concepts_path: Path to concepts JSON file
            summary_path: Path to summary text file
            lecture_id: Unique identifier for the lecture
        """
        self.vtt_path = vtt_path
        self.concepts_path = concepts_path
        self.summary_path = summary_path
        self.lecture_id = lecture_id
        self.output_dir = f"{lecture_id}_chunks"


# Placeholder content for testing/demonstration
PLACEHOLDER_VTT = """WEBVTT

1
00:00:00.000 --> 00:00:02.000
 ‫תודה רבה.

2
00:00:30.000 --> 00:00:33.000
 ‫זה לא שאני מאיימת עליי,

3
00:01:00.000 --> 00:01:05.000
 ‫היום אנחנו מתחילים לעבוד על זיכרון עבודה (Working Memory).
"""

PLACEHOLDER_CONCEPTS = """{
  "concepts": [
    {"concept": "זיכרון לטווח קצר", "times": [{"end": "00:11:00", "start": "00:08:30"}]},
    {"concept": "זיכרון עבודה (Working Memory)", "times": [{"end": "00:30:00", "start": "00:11:00"}]}
  ]
}"""

PLACEHOLDER_SUMMARY = """השיעור עסק בזיכרון, בהמשך לנושא שהחל בשבוע הקודם. נדונו סוגי זיכרון שונים והתהליכים הקשורים בהם."""