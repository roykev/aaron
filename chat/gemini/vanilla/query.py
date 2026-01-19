from google import genai
from google.genai import types
import sys
from pathlib import Path
import re

# Add project root to path to import utils
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.utils import source_key

def query(client, file_search_store, query, filter, max_output_tokens=None, temperature=None):
    """
    Query the Gemini file search store.

    Args:
        client: Gemini client
        file_search_store: File search store object
        query: Query string
        filter: Metadata filter string
        max_output_tokens: Maximum tokens in response (e.g., 100, 500, 2048)
        temperature: Controls randomness (0.0 to 2.0, default ~1.0)

    Returns:
        Gemini API response
    """
    config_params = {
        'tools': [
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[file_search_store.name],
                    metadata_filter=filter
                )
            ),
        ]
    }

    # Add optional parameters
    if max_output_tokens is not None:
        config_params['max_output_tokens'] = max_output_tokens

    if temperature is not None:
        config_params['temperature'] = temperature

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config=types.GenerateContentConfig(**config_params)
    )
    print(response.text)
    return response

def get_citations(response, top_k=5):
    """
    Extract citations from Gemini response with metadata.

    Returns:
        list: List of dictionaries, each containing:
            - uri: Source URI
            - title: Source title
            - text: Full citation text
            - timestamp_from: Earliest timestamp (HH:MM:SS.mmm)
            - timestamp_to: Latest timestamp (HH:MM:SS.mmm)
            - metadata: Custom metadata dict (if available)
    """
    gm = response.candidates[0].grounding_metadata
    if gm is None:
        print("no grounding metadata")
        return []

    # List all retrieved chunks
    chunks = gm.grounding_chunks  # list of GroundingChunkRetrievedContext
    top_chunks = chunks[:top_k]

    print("### Citations ###########")
    print(f"Retrieved {len(chunks)} chunks (showing top {top_k})")

    citations = []

    for i, chunk in enumerate(top_chunks):
        retrieved_context = chunk.retrieved_context

        # Parse timestamps from the text
        timestamp_from, timestamp_to = parse_vtt_timestamps(retrieved_context.text)

        # Build citation metadata dictionary
        citation_data = {
            'uri': retrieved_context.uri,
            'title': retrieved_context.title,
            'text': retrieved_context.text,
            'timestamp_from': timestamp_from,
            'timestamp_to': timestamp_to,
            'metadata': {}
        }

        # Add custom metadata if available
        if hasattr(retrieved_context, 'metadata'):
            citation_data['metadata'] = retrieved_context.metadata

        # Add file search store if available
        if hasattr(chunk, 'file_search_store'):
            citation_data['file_search_store'] = chunk.file_search_store

        citations.append(citation_data)

  
    return citations

def parse_vtt_timestamps(text):
    """
    Parse VTT timestamps from transcript text.
    Returns tuple of (earliest_start_time, latest_end_time) as strings in HH:MM:SS.mmm format.
    Returns (None, None) if no timestamps found.
    """
    # Pattern to match VTT timestamps: HH:MM:SS.mmm --> HH:MM:SS.mmm
    timestamp_pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})'
    matches = re.findall(timestamp_pattern, text)

    if not matches:
        return None, None

    # Convert timestamps to comparable format (total seconds)
    def time_to_seconds(time_str):
        """Convert HH:MM:SS.mmm to total seconds"""
        h, m, s = time_str.split(':')
        s, ms = s.split('.')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    # Find earliest start and latest end
    start_times = [match[0] for match in matches]
    end_times = [match[1] for match in matches]

    earliest_start = min(start_times, key=time_to_seconds)
    latest_end = max(end_times, key=time_to_seconds)

    return earliest_start, latest_end

if __name__ == '__main__':
    api_key = source_key("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    store_name="fileSearchStores/aaron-250pjghbtrh5"

    inst_name = "ono"
    course_name = "anatomy"
    class_name = "class2"
    year = "2025"
    semester = "A"
    filter = f"institute={inst_name} AND course={course_name} AND class={class_name} AND year={year} AND semester={semester}"

    filter = f"institute={inst_name} AND course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"

    filter = f"course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"

    file_search_store = client.file_search_stores.get(name=store_name)
    #file_search_store = client.file_search_stores.get(name= display_name)

    query_t = "ישורי תנועה ותנועות אנטומיות"
    # response =query(client, file_search_store, query_t, filter)
    # print(f"*****\nResponse: {response}")
    # get_citations(response)


    inst_name = "one"
    course_name = "psy"
    class_name = "class4"
    #year = "2025"
    #semester = "A"

    query_t="what can you tell me about Freud"
    query_t="מי היה פרויד, "
    query_t="what was told about learning during war time?"
    filter = f"institute={inst_name} AND course={course_name} AND class={class_name}"# AND year={year} AND semester={semester}"
    filter = f"course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"

    # response=query(client, file_search_store, query_t, filter)
    # print(f"Response: {response}")
    # get_citations(response)

    query_t="מה ההבדל בין הפרעה למוקדם להפרעה למאוחר"
    filter = f"course=psychology2 AND class=class3"
    course_name = "psychology2"
    class_name = "class2"
    filter = f"course={course_name} AND class={class_name} "
    response=query(client, file_search_store, query_t, filter, 5000, 0.2)

    citations = get_citations(response)

    # Example: Access citation metadata as list/vector
    for i, citation in enumerate(citations):
        print(f"\nCitation {i+1}:")
        print(f"  URI: {citation['uri']}")
        print(f"  Title: {citation['title']}")
        print(f"  Timestamp from: {citation['timestamp_from']}")
        print(f"  Timestamp to: {citation['timestamp_to']}")
        print(f"  Custom metadata: {citation['metadata']}")
        print(f"  Text: {citation['text'][:200]}...")