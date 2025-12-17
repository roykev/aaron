#!/usr/bin/env python3
"""
Interactive Q&A script for querying Gemini RAG system

Usage:
    python interactive.py
    python interactive.py --concepts concepts.json --summary summary.txt
    python interactive.py --store-name "My_Custom_Store"
"""

import argparse
import sys
import os
import glob
from pathlib import Path

# Add both current directory and project root to path
# IMPORTANT: Current dir must be FIRST so we import the right parsers.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)  # Add project root second
sys.path.insert(0, current_dir)   # Add current dir first (highest priority)

from google import genai

from chat.gemini.config import GeminiConfig
from chat.gemini.parsers import read_file_with_fallback, parse_concepts, parse_summary
from chat.gemini.store_manager import StoreManager
from chat.gemini.store_registry import StoreRegistry
from chat.gemini.query import QueryEngine
from chat.gemini.query_logger import QueryLogger


def run_interactive_session(query_engine: QueryEngine):
    """
    Run interactive Q&A session

    Args:
        query_engine: Initialized QueryEngine instance
    """
    print("\n" + "=" * 70)
    print("🤖 Interactive RAG Query Session Started")
    print("=" * 70)
    print("Type your questions below. Commands:")
    print("  - 'quit' or 'exit' to end session")
    print("  - 'help' for usage tips")
    print("=" * 70 + "\n")

    while True:
        try:
            user_query = input("❓ Your question: ").strip()

            if not user_query:
                continue

            if user_query.lower() in ('quit', 'exit', 'q'):
                print("\n👋 Ending session. Goodbye!")
                break

            if user_query.lower() == 'help':
                print("\n💡 Tips:")
                print("  - Ask specific questions about the lecture content")
                print("  - Reference time periods: 'What was discussed around minute 15?'")
                print("  - Ask about concepts: 'Explain working memory'")
                print("  - Compare topics: 'What's the difference between X and Y?'\n")
                continue

            # Process query
            query_engine.query(user_query, verbose=True)

        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Input stream closed. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error processing query: {e}\n")


def run_search_mode(query_engine: QueryEngine):
    """
    Run single search query mode

    Args:
        query_engine: Initialized QueryEngine instance
    """
    print("\n🔍 Search Mode")
    print("Enter your query:")

    try:
        query = input("> ").strip()

        if query:
            result = query_engine.search_and_answer(query)

            print("\n" + "=" * 70)
            print("📝 Query:", result['query'])
            print("=" * 70)
            print(result['answer'])
            print("=" * 70)
            print(f"Model: {result['model']} | Store: {result['store']}")
            print("=" * 70)
        else:
            print("No query provided.")

    except KeyboardInterrupt:
        print("\n\nSearch cancelled.")
    except Exception as e:
        print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Q&A for Gemini RAG system"
    )

    parser.add_argument(
        '--mode',
        choices=['interactive', 'search'],
        default='interactive',
        help='Run mode: interactive (chat) or search (single query)'
    )
    parser.add_argument(
        '--concepts',
        help='Path to concepts JSON file (optional)'
    )
    parser.add_argument(
        '--summary',
        help='Path to summary text file (optional)'
    )
    parser.add_argument(
        '--store-name',
        help='Custom store name (optional)'
    )
    parser.add_argument(
        '--api-key',
        help='Gemini API key (alternatively set GEMINI_API_KEY env var)'
    )
    parser.add_argument(
        '--model',
        default='gemini-2.0-flash-exp',
        help='Gemini model to use (default: gemini-2.0-flash-exp)'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        default=10,
        help='Maximum number of files to use as context (default: 10)'
    )
    parser.add_argument(
        '--scope',
        choices=['class', 'course'],
        default='course',
        help='Query scope: class (single class level) or course (entire course) (default: course)'
    )
    parser.add_argument(
        '--lecture-id',
        help='Lecture ID for class-level queries (e.g., psychology_20251206_234701). Required when --scope=class'
    )

    args = parser.parse_args()

    # Validate: if scope is 'class', lecture-id is required
    if args.scope == 'class' and not args.lecture_id:
        print("Error: --lecture-id is required when using --scope=class")
        print("\nAvailable lectures:")
        # List available chunk directories to help user
        chunks_dirs = glob.glob(os.path.join(os.getcwd(), "*_chunks"))
        if chunks_dirs:
            for chunks_dir in sorted(chunks_dirs):
                lecture_id = os.path.basename(chunks_dir).replace("_chunks", "")
                print(f"  - {lecture_id}")
        sys.exit(1)

    # Initialize configuration
    try:
        if args.api_key:
            # Use direct API key if provided
            config = GeminiConfig(api_key=args.api_key)
        else:
            # Load from project-wide config.yaml
            config = GeminiConfig.from_project_config()

        # Override with command-line arguments
        if args.store_name:
            config.store_display_name = args.store_name
        if args.model:
            config.model_name = args.model
        if args.max_files:
            config.max_files_per_query = args.max_files

    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Config file error: {e}")
        print("Falling back to environment variables only...")
        try:
            config = GeminiConfig.from_env(store_name=args.store_name)
            if args.model:
                config.model_name = args.model
            if args.max_files:
                config.max_files_per_query = args.max_files
        except ValueError as e2:
            print(f"Configuration error: {e2}")
            sys.exit(1)

    print("=" * 70)
    print("📚 Gemini RAG Interactive Query System")
    print("=" * 70)

    # Load context files if provided
    print("\n[Step 1/4] Loading context...")

    # Use command-line args if provided, otherwise use config from YAML (videos_dir + filenames)
    concepts_path = args.concepts if args.concepts else config.get_concepts_path()
    summary_path = args.summary if args.summary else config.get_summary_path()

    concepts_content = read_file_with_fallback(concepts_path, "concepts") if concepts_path else ""
    summary_content = read_file_with_fallback(summary_path, "summary") if summary_path else ""

    course_topics = parse_concepts(concepts_content) if concepts_content else "N/A"
    lecture_summary = parse_summary(summary_content) if summary_content else "N/A"

    print(f"✓ Topics: {course_topics[:100]}...")
    print(f"✓ Summary: {lecture_summary[:100]}...")

    # Initialize Gemini client and store
    print("\n[Step 2/4] Connecting to Gemini...")

    try:
        client = genai.Client(api_key=config.api_key)

        # Look up store_id from registry using (institute, course)
        # Use absolute path based on current script directory
        registry_path = os.path.join(current_dir, "store_registry.json")
        registry = StoreRegistry(registry_path)

        institute = config.institute if config.institute else "default_institute"
        course = config.course_name if config.course_name else "default_course"

        # Try to get existing store from registry
        store_id = registry.get_store(institute, course)

        if store_id:
            print(f"-> Found store in registry for {institute}:{course}")
            print(f"-> Store ID: {store_id}")
        else:
            print(f"-> No store found in registry for {institute}:{course}")
            print(f"-> Please upload lectures using batch.py first")
            sys.exit(1)

        # Initialize store manager with store_id from registry
        store_manager = StoreManager(
            client,
            config.store_display_name,
            store_id=store_id
        )
        store_name = store_manager.store_name
        print(f"✓ Connected to store: {store_name}")

        # List available files
        files = store_manager.list_files()
        if not files:
            print("\n⚠️  Warning: No files found in store. Please upload lectures using batch.py first.")
            response = input("\nContinue anyway? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)

    except Exception as e:
        print(f"Error connecting to Gemini: {e}")
        sys.exit(1)

    # Initialize query logger
    print("\n[Step 3/4] Initializing query logger...")

    logger = QueryLogger(
        log_path=config.query_log_path,
        institute=config.institute,
        course_name=config.course_name,
        class_level=config.class_level
    )
    print(f"✓ Query logger initialized (Log: {config.query_log_path})")

    # Initialize query engine
    print("\n[Step 4/4] Initializing query engine...")

    query_engine = QueryEngine(
        client=client,
        store_name=store_name,
        topics=course_topics,
        summary=lecture_summary,
        model_name=config.model_name,
        max_files=config.max_files_per_query,
        logger=logger,
        class_level=config.class_level,
        query_scope=args.scope,
        lecture_id=args.lecture_id,
        course_name=config.course_name,
        institute=config.institute
    )

    scope_info = f"{args.scope}"
    if args.scope == 'class' and args.lecture_id:
        scope_info += f" (lecture: {args.lecture_id})"
    print(f"✓ Query engine ready (Model: {config.model_name}, Scope: {scope_info})")

    # Run the selected mode
    if args.mode == 'interactive':
        run_interactive_session(query_engine)
    else:
        run_search_mode(query_engine)


if __name__ == "__main__":
    main()