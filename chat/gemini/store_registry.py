"""
Store Registry - Maps (institute, course) pairs to Gemini File Search Store names and course directories
"""

import json
import os
from typing import Optional, Dict, Tuple, Any
from datetime import datetime


class StoreRegistry:
    """Manages mapping between (institute, course) and Gemini store names"""

    def __init__(self, registry_file: str = "store_registry.json"):
        """
        Initialize store registry

        Args:
            registry_file: Path to JSON file storing the registry
        """
        self.registry_file = registry_file
        self.registry: Dict[str, str] = self._load_registry()

    def _load_registry(self) -> Dict[str, str]:
        """Load registry from disk"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {self.registry_file}. Starting with empty registry.")
                return {}
        else:
            # Create the file if it doesn't exist
            print(f"-> Creating new registry file: {self.registry_file}")
            self._create_empty_registry()
        return {}

    def _create_empty_registry(self):
        """Create an empty registry file"""
        try:
            # Create directory if it doesn't exist
            registry_dir = os.path.dirname(self.registry_file)
            if registry_dir and not os.path.exists(registry_dir):
                os.makedirs(registry_dir, exist_ok=True)

            # Create empty registry
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            print(f"-> Created empty registry file: {self.registry_file}")
        except Exception as e:
            print(f"-> Warning: Could not create registry file: {e}")

    def _save_registry(self):
        """Save registry to disk"""
        try:
            # Create directory if it doesn't exist
            registry_dir = os.path.dirname(self.registry_file)
            if registry_dir and not os.path.exists(registry_dir):
                os.makedirs(registry_dir, exist_ok=True)

            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)
            print(f"-> Registry saved to {self.registry_file}")
        except Exception as e:
            print(f"-> Warning: Could not save registry: {e}")

    @staticmethod
    def _make_key(institute: str, course: str) -> str:
        """Create registry key from institute and course"""
        return f"{institute.lower().strip()}:{course.lower().strip()}"

    def register_store(
        self,
        institute: str,
        course: str,
        store_name: str,
        course_root: Optional[str] = None,
        class_level: Optional[str] = None
    ):
        """
        Register a store for an institute/course pair

        Args:
            institute: Institute name (e.g., "Hebrew University")
            course: Course name (e.g., "Psychology 101")
            store_name: Gemini store name (e.g., "fileSearchStores/7askqtkrfkr4-yntw8sntgxmn")
            course_root: Root directory for course data (e.g., "/path/to/courses/psychology")
            class_level: Class level (e.g., "undergraduate 1st year")
        """
        key = self._make_key(institute, course)

        # Check if this is an existing entry to preserve created_at
        existing_entry = self.registry.get(key)
        created_at = None
        if existing_entry and isinstance(existing_entry, dict):
            created_at = existing_entry.get('metadata', {}).get('created_at')

        # Create new format entry
        entry = {
            "store_id": store_name,
            "metadata": {
                "course_name": course,
                "institute": institute,
                "created_at": created_at or datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        }

        if course_root:
            entry["course_root"] = course_root
        if class_level:
            entry["metadata"]["class_level"] = class_level

        self.registry[key] = entry
        self._save_registry()
        print(f"-> Registered store '{store_name}' for {institute} - {course}")
        if course_root:
            print(f"   Course root: {course_root}")

    def get_store(self, institute: str, course: str) -> Optional[str]:
        """
        Get store ID for an institute/course pair (backward compatible)

        Args:
            institute: Institute name
            course: Course name

        Returns:
            Store ID if found, None otherwise
        """
        key = self._make_key(institute, course.lower())
        entry = self.registry.get(key)

        if entry is None:
            return None

        # Handle both old format (string) and new format (dict)
        if isinstance(entry, str):
            return entry  # Old format: just the store_id
        elif isinstance(entry, dict):
            return entry.get("store_id")  # New format: extract store_id from dict
        return None

    def get_course_root(self, institute: str, course: str) -> Optional[str]:
        """
        Get course root directory for an institute/course pair

        Args:
            institute: Institute name
            course: Course name

        Returns:
            Course root path if found, None otherwise
        """
        key = self._make_key(institute, course)
        entry = self.registry.get(key)

        if entry and isinstance(entry, dict):
            return entry.get("course_root")
        return None

    def get_entry(self, institute: str, course: str) -> Optional[Dict[str, Any]]:
        """
        Get full registry entry for an institute/course pair

        Args:
            institute: Institute name
            course: Course name

        Returns:
            Full entry dict if found, None otherwise
        """
        key = self._make_key(institute, course)
        entry = self.registry.get(key)

        if entry is None:
            return None

        # Convert old format to new format on the fly
        if isinstance(entry, str):
            return {
                "store_id": entry,
                "metadata": {
                    "course_name": course,
                    "institute": institute
                }
            }
        return entry

    def remove_store(self, institute: str, course: str) -> bool:
        """
        Remove store mapping for an institute/course pair

        Args:
            institute: Institute name
            course: Course name

        Returns:
            True if removed, False if not found
        """
        key = self._make_key(institute, course)
        if key in self.registry:
            del self.registry[key]
            self._save_registry()
            print(f"-> Removed store mapping for {institute} - {course}")
            return True
        return False

    def list_all(self) -> Dict[Tuple[str, str], str]:
        """
        List all registered stores

        Returns:
            Dict mapping (institute, course) tuples to store names
        """
        result = {}
        for key, store_name in self.registry.items():
            institute, course = key.split(':', 1)
            result[(institute, course)] = store_name
        return result

    def print_registry(self):
        """Print all registered stores in a formatted way"""
        if not self.registry:
            print("-> Registry is empty")
            return

        print("\n=== Store Registry ===")
        for key, store_name in sorted(self.registry.items()):
            institute, course = key.split(':', 1)
            print(f"  {institute.title()} - {course.title()}")
            print(f"    → {store_name}")
        print("=" * 50)

    def remove_by_store_name(self, store_name: str) -> bool:
        """
        Remove registry entries that match a specific store name

        Args:
            store_name: Store name to remove (e.g., "fileSearchStores/xxx")

        Returns:
            True if any entries were removed, False otherwise
        """
        entries_to_remove = [key for key, value in self.registry.items() if value == store_name]

        if not entries_to_remove:
            print(f"-> No registry entries found for store: {store_name}")
            return False

        for key in entries_to_remove:
            institute, course = key.split(':', 1)
            print(f"-> Removing registry entry: {institute} - {course}")
            del self.registry[key]

        self._save_registry()
        print(f"-> Removed {len(entries_to_remove)} registry entry/entries")
        return True

    def clear_all(self) -> bool:
        """
        Clear entire registry (use with caution!)

        Returns:
            True if registry was cleared
        """
        if not self.registry:
            print("-> Registry is already empty")
            return False

        print(f"\n⚠️  WARNING: About to clear {len(self.registry)} registry entry/entries!")
        confirmation = input("Type 'CLEAR' to confirm: ")

        if confirmation != "CLEAR":
            print("-> Clear cancelled")
            return False

        self.registry = {}
        self._save_registry()
        print("-> Registry cleared")
        return True


# Convenience function for quick access
def get_store_for_course(institute: str, course: str, registry_file: str = "store_registry.json") -> Optional[str]:
    """
    Quick helper to get store name for a course

    Args:
        institute: Institute name
        course: Course name
        registry_file: Path to registry file

    Returns:
        Store name if found, None otherwise
    """
    registry = StoreRegistry(registry_file)
    return registry.get_store(institute, course)