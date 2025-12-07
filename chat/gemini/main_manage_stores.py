#!/usr/bin/env python3
"""
Comprehensive Gemini Store Management Tool
Handles all store operations: list, view files, delete, registry management
"""

import sys
import os
import time
from pathlib import Path

# Add both current directory and project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from google import genai
from chat.gemini.config import GeminiConfig
from chat.gemini.store_manager import StoreManager
from chat.gemini.store_registry import StoreRegistry


def list_all_stores(client):
    """List all Gemini file search stores"""
    print("\n" + "=" * 70)
    print("📚 All File Search Stores")
    print("=" * 70)

    stores = list(client.file_search_stores.list())

    if not stores:
        print("\nNo stores found.")
        return []

    print(f"\nFound {len(stores)} store(s):\n")
    for i, store in enumerate(stores, 1):
        display_name = getattr(store, 'display_name', 'N/A')
        print(f"[{i}] {store.name}")
        if display_name != 'N/A':
            print(f"    Display Name: {display_name}")

    print("=" * 70)
    return stores


def list_all_files(client, store_id=None):
    """List all documents across File Search Stores"""
    print("\n" + "=" * 70)
    print("📁 File Search Store Documents")
    print("=" * 70)
    print()

    # Get all stores and their document counts
    stores = list(client.file_search_stores.list())

    if not stores:
        print("No File Search Stores found.")
        print("=" * 70)
        return []

    total_active = 0
    total_pending = 0
    total_failed = 0

    for i, store in enumerate(stores, 1):
        active = store.active_documents_count or 0
        pending = store.pending_documents_count or 0
        failed = store.failed_documents_count or 0

        total_active += active
        total_pending += pending
        total_failed += failed

        print(f"[{i}] {store.name}")
        if store.display_name:
            print(f"    Display Name: {store.display_name}")
        print(f"    Active Documents: {active}")
        if pending > 0:
            print(f"    Pending Documents: {pending}")
        if failed > 0:
            print(f"    Failed Documents: {failed}")
        if store.size_bytes:
            print(f"    Total Size: {store.size_bytes:,} bytes")
        print()

    print("-" * 70)
    print(f"Total Documents:")
    print(f"  Active: {total_active}")
    if total_pending > 0:
        print(f"  Pending: {total_pending}")
    if total_failed > 0:
        print(f"  Failed: {total_failed}")

    print("\nNote: File Search Store documents are indexed and persist indefinitely.")
    print("They are NOT shown in client.files.list() (which shows temporary uploads).")
    print("=" * 70)
    return stores


def delete_specific_store(client, store_manager, registry):
    """Delete a specific store"""
    stores = list_all_stores(client)
    if not stores:
        return

    store_num = input("\nEnter store number to delete (or 'c' to cancel): ").strip()
    if store_num.lower() == 'c':
        print("-> Cancelled")
        return

    try:
        store_idx = int(store_num) - 1
        if 0 <= store_idx < len(stores):
            store_to_delete = stores[store_idx]
            print(f"\n⚠️  About to delete: {store_to_delete.name}")
            confirm = input("Type 'DELETE' to confirm: ")

            if confirm == "DELETE":
                if store_manager.delete_store(store_to_delete.name):
                    registry.remove_by_store_name(store_to_delete.name)
                    print("✓ Store deleted and removed from registry")
            else:
                print("-> Deletion cancelled")
        else:
            print("-> Invalid store number")
    except ValueError:
        print("-> Invalid input")


def delete_all_stores(client, store_manager, registry):
    """Delete all stores with confirmation"""
    stores = list(client.file_search_stores.list())

    if not stores:
        print("\n-> No stores to delete")
        return

    print(f"\n⚠️  WARNING: About to DELETE ALL {len(stores)} store(s)!")
    print("\nStores to be deleted:")
    for i, store in enumerate(stores, 1):
        print(f"  [{i}] {store.name}")

    confirm = input("\nType 'DELETE ALL' to confirm: ")

    if confirm != "DELETE ALL":
        print("-> Deletion cancelled")
        return

    deleted = 0
    failed = 0

    for i, store in enumerate(stores, 1):
        print(f"\n[{i}/{len(stores)}] Deleting: {store.name}")
        try:
            # Try to delete files first
            print("-> Attempting to delete files...")
            files = list(client.files.list())
            if files:
                for file in files:
                    try:
                        client.files.delete(name=file.name)
                    except:
                        pass
                print(f"-> Deleted {len(files)} file(s)")
                time.sleep(3)

            # Try to delete store
            client.file_search_stores.delete(name=store.name)
            print(f"✓ Deleted: {store.name}")
            deleted += 1

        except Exception as e:
            error_msg = str(e)
            if "non-empty" in error_msg.lower():
                print(f"✗ Cannot delete (store not empty): {store.name}")
                print("   This is a Gemini API limitation - stores may appear empty but still contain files")
            else:
                print(f"✗ Error: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"Summary: ✓ Deleted {deleted} | ✗ Failed {failed}")
    print("=" * 70)

    if deleted > 0:
        print("\n-> Clearing registry...")
        registry.clear_all()


def view_registry(registry):
    """View current registry"""
    registry.print_registry()


def register_store(registry):
    """Manually register a store"""
    print("\n" + "=" * 70)
    print("📝 Register Store in Registry")
    print("=" * 70)

    institute = input("\nInstitute name: ").strip()
    course = input("Course name: ").strip()
    store_id = input("Store ID (e.g., fileSearchStores/xxx): ").strip()

    if not institute or not course or not store_id:
        print("-> All fields required. Cancelled.")
        return

    registry.register_store(institute, course, store_id)
    print(f"\n✓ Registered: {institute}:{course} → {store_id}")


def main():
    print("=" * 70)
    print("🗄️  Gemini Store Management Tool")
    print("=" * 70)

    # Initialize
    try:
        config = GeminiConfig.from_project_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    client = genai.Client(api_key=config.api_key)
    store_manager = StoreManager(client, "management_tool")

    # Use absolute path to registry in chat/gemini directory
    registry_path = os.path.join(current_dir, "store_registry.json")
    registry = StoreRegistry(registry_path)

    while True:
        print("\n" + "=" * 70)
        print("Options:")
        print("  1. List all stores")
        print("  2. List all files")
        print("  3. Delete specific store")
        print("  4. Delete ALL stores (⚠️  CAUTION)")
        print("  5. View registry")
        print("  6. Register a store manually")
        print("  7. Clear registry")
        print("  8. Exit")
        print("=" * 70)

        choice = input("\nEnter choice (1-8): ").strip()

        if choice == "1":
            list_all_stores(client)

        elif choice == "2":
            list_all_files(client)

        elif choice == "3":
            delete_specific_store(client, store_manager, registry)

        elif choice == "4":
            delete_all_stores(client, store_manager, registry)

        elif choice == "5":
            view_registry(registry)

        elif choice == "6":
            register_store(registry)

        elif choice == "7":
            print("\n⚠️  Clear all registry entries?")
            confirm = input("Type 'CLEAR' to confirm: ")
            if confirm == "CLEAR":
                registry.clear_all()
            else:
                print("-> Cancelled")

        elif choice == "8":
            print("\n👋 Goodbye!")
            break

        else:
            print("-> Invalid choice")


if __name__ == "__main__":
    main()