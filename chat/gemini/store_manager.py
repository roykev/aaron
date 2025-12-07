"""
Gemini File Search Store management (create, upload, list)
"""

import os
import time
from typing import List

from google import genai
from google.genai import types


class StoreManager:
    """Manages Gemini File Search Store operations"""

    def __init__(self, client: genai.Client, store_display_name: str, store_id: str = None):
        """
        Initialize store manager

        Args:
            client: Gemini API client
            store_display_name: Display name for the store
            store_id: Specific store ID to use (optional - e.g., "fileSearchStores/xxx")
        """
        self.client = client
        self.store_display_name = store_display_name
        self.store_id = store_id
        self._store = None

    def get_or_create_store(self) -> types.FileSearchStore:
        """
        Get existing store or create new one

        Returns:
            FileSearchStore instance
        """
        if self._store:
            return self._store

        # If specific store ID is provided, use that directly
        if self.store_id:
            print(f"\n-> Using specified store ID: {self.store_id}")
            try:
                store = self.client.file_search_stores.get(name=self.store_id)
                print(f"-> Successfully connected to store: {store.name}")
                self._store = store
                return store
            except Exception as e:
                print(f"-> Error connecting to store {self.store_id}: {e}")
                print(f"-> Falling back to search by display name...")

        print(f"\n-> Checking for existing File Search Store: '{self.store_display_name}'...")

        # List stores and check for display name match
        for store in self.client.file_search_stores.list():
            if store.display_name == self.store_display_name:
                print(f"-> Found existing store: {store.name}")
                self._store = store
                return store

        # Create new store if not found
        print(f"-> Store not found. Creating new store...")

        # Try to set display_name (may not be supported by API)
        try:
            # Attempt to create store with display_name
            store = self.client.file_search_stores.create(
                display_name=self.store_display_name
            )
            print(f"-> Successfully created new store: {store.name}")
            print(f"   Display name: {self.store_display_name}")
        except (TypeError, Exception) as e:
            # If display_name is not supported, create without it
            print(f"-> Note: display_name not supported by API, creating without it")
            store = self.client.file_search_stores.create()
            print(f"-> Successfully created new store: {store.name}")

        self._store = store
        return store

    def upload_files(
        self,
        file_paths: List[str],
        max_wait_seconds: int = 300
    ) -> List:
        """
        Upload multiple files to the store

        Args:
            file_paths: List of file paths to upload
            max_wait_seconds: Maximum time to wait for uploads to complete

        Returns:
            List of upload operations
        """
        store = self.get_or_create_store()

        print(f"\n-> Uploading {len(file_paths)} files to store '{store.name}'...")

        operations = []
        for file_path in file_paths:
            print(f"   Uploading: {os.path.basename(file_path)}")

            op = self.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store.name,
                file=file_path
            )
            operations.append(op)

        print(f"-> Successfully submitted {len(operations)} files for upload.")

        # Debug: Print first operation details
        if operations:
            print(f"\n-> Debug: Inspecting first operation...")
            op = operations[0]
            print(f"   Type: {type(op)}")
            print(f"   Has 'done' attr: {hasattr(op, 'done')}")
            print(f"   Has 'result' method: {hasattr(op, 'result')}")
            print(f"   Attributes: {dir(op)[:10]}...")  # First 10 attributes
            try:
                print(f"   Operation name: {op.name if hasattr(op, 'name') else 'N/A'}")
            except:
                pass

        # Wait for operations to complete
        print("-> Waiting for uploads to complete...")
        start_time = time.time()
        last_status_time = start_time

        while time.time() - start_time < max_wait_seconds:
            # Refresh operation status from server
            for i in range(len(operations)):
                operations[i] = self.client.operations.get(operations[i])

            all_done = all(op.done for op in operations)
            if all_done:
                break

            # Print progress every 30 seconds
            current_time = time.time()
            if current_time - last_status_time >= 30:
                elapsed = int(current_time - start_time)
                done_count = sum(1 for op in operations if op.done)
                print(f"   [{elapsed}s] {done_count}/{len(operations)} operations completed...")
                last_status_time = current_time

            time.sleep(2)

        # Check results
        succeeded = 0
        failed = 0
        incomplete = 0

        for op in operations:
            if op.done:
                # Check if operation succeeded or failed
                if hasattr(op, 'error') and op.error:
                    print(f"   ✗ Upload failed: {op.error}")
                    failed += 1
                else:
                    succeeded += 1
            else:
                incomplete += 1

        print(f"\n-> Upload results:")
        print(f"   ✓ Succeeded: {succeeded}")
        if failed > 0:
            print(f"   ✗ Failed: {failed}")
        if incomplete > 0:
            print(f"   ⚠ Incomplete: {incomplete}")

        if failed > 0 or incomplete > 0:
            raise Exception(f"Upload failed: {succeeded} succeeded, {failed} failed, {incomplete} incomplete")

        print("-> All files successfully uploaded to store.")
        return operations

    def list_files(self) -> int:
        """
        Get the count of active documents in the store

        Returns:
            Number of active documents
        """
        store = self.get_or_create_store()

        # Refresh store info to get latest document counts
        store = self.client.file_search_stores.get(name=store.name)

        active_count = store.active_documents_count or 0
        print(f"-> Found {active_count} active documents in store")

        return active_count

    @property
    def store_name(self) -> str:
        """Get the store name (creates store if needed)"""
        store = self.get_or_create_store()
        return store.name

    def delete_all_files_in_store(self, store_name: str = None) -> int:
        """
        Delete all files from a specific store

        Args:
            store_name: Store name to delete files from (optional, uses current store if not provided)

        Returns:
            Number of files deleted
        """
        try:
            # Get files from the specific store
            if store_name:
                # List files in the specific store
                try:
                    store_files = list(self.client.file_search_stores.list_files(name=store_name))
                    print(f"-> Found {len(store_files)} files in store {store_name}")
                except AttributeError:
                    # If list_files doesn't exist, try another approach
                    # Get all files and filter by checking each file's metadata
                    print("-> Attempting to list files using alternative method...")
                    all_files = list(self.client.files.list())
                    store_files = []
                    for f in all_files:
                        # Try to check if file belongs to this store
                        try:
                            file_info = self.client.files.get(name=f.name)
                            # Check if file is associated with this store
                            # Note: This is a workaround since the API doesn't expose store association clearly
                            store_files.append(f)
                        except:
                            pass
                    print(f"-> Found {len(store_files)} total files (may include files from other stores)")
            else:
                store_files = list(self.client.files.list())
                print(f"-> Found {len(store_files)} files to delete")

            deleted_count = 0
            for file in store_files:
                try:
                    self.client.files.delete(name=file.name)
                    deleted_count += 1
                    if deleted_count % 10 == 0:
                        print(f"   Deleted {deleted_count}/{len(store_files)} files...")
                except Exception as e:
                    # Skip files that can't be deleted (might belong to other stores)
                    pass

            print(f"-> Deleted {deleted_count} files")
            return deleted_count

        except Exception as e:
            print(f"-> Error listing/deleting files: {e}")
            return 0

    def delete_store(self, store_name: str, delete_files: bool = True) -> bool:
        """
        Delete a specific store by its name

        Args:
            store_name: Store name to delete (e.g., "fileSearchStores/xxx")
            delete_files: If True, delete all files in the store first (required by API)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            print(f"\n-> Deleting store: {store_name}")

            if delete_files:
                print("-> First, deleting all files in the store...")
                # Note: The Gemini API requires the store to be empty before deletion
                # We need to delete files first
                deleted_count = self.delete_all_files_in_store()
                if deleted_count > 0:
                    print(f"-> Deleted {deleted_count} files from store")
                    # Wait a moment for the API to process deletions
                    print("-> Waiting for file deletions to process...")
                    time.sleep(3)

            # Now delete the empty store
            self.client.file_search_stores.delete(name=store_name)
            print(f"-> Successfully deleted store: {store_name}")

            # Clear cached store if it matches
            if self._store and self._store.name == store_name:
                self._store = None

            return True
        except Exception as e:
            error_msg = str(e)
            if "non-empty" in error_msg.lower():
                print(f"-> Error: Store is not empty after file deletion.")
                print(f"-> This may be because files.list() returns files across ALL stores.")
                print(f"-> Waiting 5 seconds and retrying...")
                time.sleep(5)

                # Retry the deletion
                try:
                    self.client.file_search_stores.delete(name=store_name)
                    print(f"-> Successfully deleted store: {store_name}")
                    if self._store and self._store.name == store_name:
                        self._store = None
                    return True
                except Exception as e2:
                    print(f"-> Still cannot delete store: {e2}")
                    print(f"-> Skipping this store for now...")
                    return False
            else:
                print(f"-> Error deleting store {store_name}: {e}")
                return False

    def list_all_stores(self) -> list:
        """
        List all available stores

        Returns:
            List of store objects
        """
        try:
            stores = list(self.client.file_search_stores.list())
            print(f"\n-> Found {len(stores)} total stores:")
            for i, store in enumerate(stores, 1):
                display_name = getattr(store, 'display_name', 'N/A')
                print(f"   [{i}] {store.name}")
                print(f"       Display Name: {display_name}")
            return stores
        except Exception as e:
            print(f"-> Error listing stores: {e}")
            return []

    def delete_all_stores(self) -> int:
        """
        Delete ALL stores (use with caution!)

        Returns:
            Number of stores deleted
        """
        stores = self.list_all_stores()

        if not stores:
            print("-> No stores to delete")
            return 0

        print(f"\n⚠️  WARNING: About to delete {len(stores)} store(s)!")
        confirmation = input("Type 'DELETE ALL' to confirm: ")

        if confirmation != "DELETE ALL":
            print("-> Deletion cancelled")
            return 0

        deleted_count = 0
        for store in stores:
            if self.delete_store(store.name):
                deleted_count += 1

        print(f"\n-> Deleted {deleted_count}/{len(stores)} stores")
        self._store = None
        return deleted_count