"""
RAG query functionality for Gemini File Search
"""

import time
import re
import os
import glob
from google import genai
from google.genai import types
from typing import List, Optional, Dict
from query_logger import QueryLogger
from chunk_matcher import ChunkMatcher


class QueryEngine:
    """Handles RAG queries against the file search store"""

    def __init__(
        self,
        client: genai.Client,
        store_name: str,
        topics: str,
        summary: str,
        model_name: str = "gemini-2.0-flash-exp",
        max_files: int = 10,
        logger: Optional[QueryLogger] = None,
        class_level: Optional[str] = None,
        query_scope: str = "course",
        lecture_id: Optional[str] = None,
        top_chunks_to_show: int = 3,
        course_name: Optional[str] = None,
        institute: Optional[str] = None
    ):
        """
        Initialize query engine

        Args:
            client: Gemini API client
            store_name: Name of the file search store
            topics: Course topics string
            summary: Lecture summary
            model_name: Gemini model to use
            max_files: Maximum number of files to use as context
            logger: QueryLogger instance for logging queries (optional)
            class_level: Class level for filtering (used when scope is 'class')
            query_scope: Scope of queries - 'class' (single class) or 'course' (entire course)
            lecture_id: Specific lecture ID for class-level filtering (e.g., 'psychology_20251206_234701')
            top_chunks_to_show: Number of top chunks to display with content (default: 3)
        """
        self.client = client
        self.store_name = store_name
        self.topics = topics
        self.summary = summary
        self.model_name = model_name
        self.max_files = max_files
        self.logger = logger
        self.class_level = class_level
        self.query_scope = query_scope
        self.lecture_id = lecture_id
        self.top_chunks_to_show = top_chunks_to_show
        self.course_name = course_name
        self.institute = institute

    def _filter_files_by_scope(self, files: List) -> List:
        """
        Filter files based on query scope (class vs course)

        Args:
            files: List of all files

        Returns:
            Filtered list of files based on scope
        """
        if self.query_scope == "course":
            # Course scope: use all files in the store
            return files
        elif self.query_scope == "class" and self.class_level:
            # Class scope: filter by class_level in filename
            # Assuming filenames contain class level info like: business_grad1_Lec1_chunk_...
            # For now, we'll use a simple approach - if class_level is specified,
            # filter files that contain the class identifier in their name
            class_identifier = self.class_level.replace(" ", "_").lower()
            filtered = [f for f in files if class_identifier in f.name.lower()]
            if filtered:
                return filtered
            # If no files match, fall back to all files
            return files
        else:
            # Default: use all files
            return files

    def _extract_chunk_references(self, files_used: List) -> List[Dict]:
        """
        Extract time chunk references from file names and read their content

        Args:
            files_used: List of file objects used in the query

        Returns:
            List of chunk references with lecture_id, time range, and content
        """
        chunks = []
        for file in files_used:
            # File names are expected to be in format: LectureID_START-END.txt
            # Example: PsychLec4_00-00-00_to_00-00-30.txt
            match = re.match(r'(.+?)_(\d{2}-\d{2}-\d{2})_to_(\d{2}-\d{2}-\d{2})\.txt', file.name)
            if match:
                lecture_id = match.group(1)
                start_time = match.group(2).replace('-', ':')
                end_time = match.group(3).replace('-', ':')

                # Try to read the chunk content from the file
                try:
                    # Download file content
                    file_content = self.client.files.get(name=file.name)
                    content = file_content.get('content', 'Content not available')
                except Exception as e:
                    content = f"Error reading file: {e}"

                chunks.append({
                    "lecture_id": lecture_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "chunk_file": file.name,
                    "content": content
                })
        return chunks

    def query(self, user_query: str, verbose: bool = True) -> dict:
        """
        Perform RAG query with timing, logging, and chunk references

        Args:
            user_query: User's question
            verbose: Whether to print detailed output

        Returns:
            Dictionary with answer, metadata, timing, and chunk references
        """
        # Start timing
        start_time = time.time()

        if verbose:
            print(f"\n-> Running query with store reference: {self.store_name}")

        # Create system instruction with context
        system_instruction = (
            "You are an expert teaching assistant for an Advanced Psychology course, specifically the 'Memory' unit. "
            "Your responses MUST be grounded ONLY in the provided source material. "
            f"Course Topics: {self.topics}\n"
            f"Lecture Summary: {self.summary}\n"
        )

        # Check store document count
        store = self.client.file_search_stores.get(name=self.store_name)
        active_docs = store.active_documents_count or 0

        if verbose:
            print(f"Store has {active_docs} active documents")

        if active_docs == 0:
            if verbose:
                print("⚠️  Warning: Store has no documents. Upload files using batch.py first.")
            # Return empty result
            return {
                'query': user_query,
                'answer': "No documents found in store. Please upload lecture content first.",
                'model': self.model_name,
                'store': self.store_name,
                'response_time_seconds': 0,
                'chunks_used': []
            }

        # Configure File Search tool with store
        # Build metadata filter for class-level filtering if needed
        metadata_filter = None
        if self.query_scope == "class" and self.lecture_id:
            # Filter to specific lecture ID for class-level queries
            metadata_filter = types.MetadataFilter(
                key="lecture_id",
                value=self.lecture_id,
                match_type="EXACT"
            )
            if verbose:
                print(f"-> Using class scope filter: lecture_id={self.lecture_id}")

        # Configure File Search tool
        # Build tool config based on whether we have metadata filter
        if metadata_filter:
            file_search_config = types.FileSearch(
                file_search_store_names=[self.store_name],
                metadata_filter=metadata_filter
            )
        else:
            file_search_config = types.FileSearch(
                file_search_store_names=[self.store_name]
            )

        # Create tool configuration - pass fileSearch (camelCase) as the tool type
        tools = [types.Tool(fileSearch=file_search_config)]

        # Generate response with File Search Store
        # Try-catch to handle potential API changes
        try:
            # Use tool_config parameter which specifies how tools should be used
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="AUTO"
                )
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_query,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    tool_config=tool_config
                )
            )
        except Exception as e:
            # If tools with tool_config fail, try without tool_config
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_query,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=tools
                    )
                )
            except Exception as e2:
                # If tools fail completely, try without them (final fallback)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_query,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction
                    )
                )

        # Calculate response time
        response_time = time.time() - start_time

        # Try to extract grounding metadata first (preferred method)
        chunks_used = []
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding = candidate.grounding_metadata

                if verbose:
                    print(f"\n-> Grounding metadata available")
                    if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
                        print(f"   Found {len(grounding.grounding_chunks)} grounding chunks")

                # Extract chunk information from grounding metadata
                if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
                    for i, chunk in enumerate(grounding.grounding_chunks):
                        chunk_info = {
                            'chunk_index': i,
                            'content': 'Grounding chunk from File Search Store'
                        }

                        # Try to extract chunk details if available
                        if hasattr(chunk, 'retrieved_context'):
                            ctx = chunk.retrieved_context
                            if hasattr(ctx, 'uri'):
                                chunk_info['uri'] = ctx.uri
                            if hasattr(ctx, 'title'):
                                chunk_info['title'] = ctx.title
                            if hasattr(ctx, 'text'):
                                chunk_info['content'] = ctx.text

                        chunks_used.append(chunk_info)

        # Fallback: Use answer-to-chunk similarity matching if no grounding metadata
        if not chunks_used:
            # Find chunks directory based on scope
            # Search in project root (parent of chat/gemini directory)
            from pathlib import Path
            script_dir = Path(__file__).resolve().parent
            project_root = script_dir.parent.parent  # Go up two levels from chat/gemini to project root

            chunks_dirs = glob.glob(os.path.join(str(project_root), "*_chunks"))

            if self.query_scope == "class" and self.lecture_id:
                # Class scope: use specific lecture's chunks directory
                lecture_chunks_dir = f"{self.lecture_id}_chunks"
                if os.path.exists(lecture_chunks_dir):
                    chunks_dirs_to_search = [lecture_chunks_dir]
                elif chunks_dirs:
                    # Fallback: find chunks dir matching lecture_id
                    matching_dirs = [d for d in chunks_dirs if self.lecture_id in d]
                    chunks_dirs_to_search = matching_dirs if matching_dirs else [max(chunks_dirs, key=os.path.getmtime)]
                else:
                    chunks_dirs_to_search = []
            elif chunks_dirs:
                # Course scope: search across ALL chunks directories
                chunks_dirs_to_search = chunks_dirs
            else:
                chunks_dirs_to_search = []

            if chunks_dirs_to_search:
                try:
                    # Collect matches from all relevant chunks directories
                    all_matches = []

                    for chunks_dir in chunks_dirs_to_search:
                        # Create chunk matcher for this directory
                        matcher = ChunkMatcher(chunks_dir)

                        # Find matches in this directory
                        dir_matches = matcher.find_matching_chunks(response.text, top_k=self.top_chunks_to_show * 5)
                        all_matches.extend(dir_matches)

                    # Sort all matches by similarity score
                    all_matches.sort(key=lambda x: x.get('similarity', 0), reverse=True)

                    # For class scope, filter matches to specific lecture_id
                    if self.query_scope == "class" and self.lecture_id:
                        matches = [m for m in all_matches if m['lecture_id'] == self.lecture_id][:self.top_chunks_to_show]
                    else:
                        matches = all_matches[:self.top_chunks_to_show]

                    # Convert to chunks_used format
                    chunks_used = [
                        {
                            'lecture_id': m['lecture_id'],
                            'start_time': m['start_time'],
                            'end_time': m['end_time'],
                            'filename': m['filename'],
                            'content': m['content'],
                            'similarity': m['similarity']
                        }
                        for m in matches
                    ]
                except Exception as e:
                    if verbose:
                        print(f"Error during chunk matching: {e}")

        # Prepare result
        result = {
            'query': user_query,
            'answer': response.text,
            'model': self.model_name,
            'store': self.store_name,
            'response_time_seconds': round(response_time, 2),
            'chunks_used': chunks_used
        }

        # Log the query if logger is available
        if self.logger:
            self.logger.log_query(
                query=user_query,
                answer=response.text,
                model=self.model_name,
                store=self.store_name,
                response_time_seconds=response_time,
                chunks_used=chunks_used
            )

        if verbose:
            print("-" * 70)
            print("🤖 Model Response:")
            print("-" * 70)
            print(response.text)
            print("-" * 70)
            print(f"⏱️  Response time: {response_time:.2f} seconds")

            if chunks_used:
                print(f"\n📚 Source Chunks ({len(chunks_used)} total):")
                print("=" * 70)
                for i, chunk in enumerate(chunks_used[:self.top_chunks_to_show], 1):
                    # Check if this is a similarity-matched chunk or grounding metadata chunk
                    if 'lecture_id' in chunk and 'start_time' in chunk:
                        # Similarity-matched chunk with timestamps
                        # Build header line with course info
                        header_parts = []
                        if self.course_name:
                            header_parts.append(self.course_name.title())
                        if self.class_level:
                            header_parts.append(f"({self.class_level})")

                        if header_parts:
                            print(f"\n[{i}] {' '.join(header_parts)}")
                            print(f"    📅 Lecture: {chunk['lecture_id']}")
                        else:
                            print(f"\n[{i}] {chunk['lecture_id']}")

                        if self.institute:
                            print(f"    🏫 Institute: {self.institute}")
                        print(f"    ⏰ Time: {chunk['start_time']} - {chunk['end_time']}")
                        if 'filename' in chunk:
                            print(f"    📄 File: {chunk['filename']}")
                        if 'similarity' in chunk:
                            print(f"    🎯 Similarity: {chunk['similarity']:.3f}")
                    else:
                        # Grounding metadata chunk
                        print(f"\n[{i}] Chunk {chunk.get('chunk_index', i)}")
                        if 'title' in chunk:
                            print(f"    📄 Title: {chunk['title']}")
                        if 'uri' in chunk:
                            print(f"    🔗 URI: {chunk['uri']}")

                    # Display chunk content preview
                    content = chunk.get('content', 'Content not available')
                    if content and content != 'Content not available':
                        # Truncate if too long
                        max_content_length = 200
                        if len(content) > max_content_length:
                            content_preview = content[:max_content_length] + "..."
                        else:
                            content_preview = content
                        print(f"    📝 Content:\n       {content_preview.replace(chr(10), chr(10) + '       ')}")
                    else:
                        print(f"    📝 Content: {content}")
                    print()

                if len(chunks_used) > self.top_chunks_to_show:
                    print(f"   ... and {len(chunks_used) - self.top_chunks_to_show} more chunks used")
            print("-" * 70)

        return result

    def search_and_answer(self, query: str) -> dict:
        """
        Perform search and return structured answer

        Args:
            query: User's search query

        Returns:
            Dictionary with 'answer' and metadata
        """
        # Query method now returns a dict with all metadata
        return self.query(query, verbose=False)

    def batch_query(self, queries: List[str]) -> List[dict]:
        """
        Process multiple queries in batch

        Args:
            queries: List of user queries

        Returns:
            List of answer dictionaries
        """
        results = []
        for i, query in enumerate(queries, 1):
            print(f"\n[Query {i}/{len(queries)}]: {query}")
            result = self.search_and_answer(query)
            results.append(result)
            print(f"Answer: {result['answer'][:200]}...")  # Print first 200 chars

        return results