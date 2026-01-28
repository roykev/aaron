
from google import genai
from google.genai import types
import re
from datetime import datetime, timedelta

from utils.utils import source_key


def query(client, file_search_store, query, filter, max_output_tokens=1500, temperature=0.0, max_sentances=3,
          system_instruction=None, grounded_only=True):
    """
    Query the Gemini file search store with grounded answers.

    Args:
        client: Gemini client
        file_search_store: File search store object
        query: Query string
        filter: Metadata filter string
        max_output_tokens: Maximum tokens in response (default: 300, range: 1-8192)
        temperature: Controls randomness (0.0 to 2.0, default 0.0 for grounded answers)
        system_instruction: Custom system instruction (default: enforces document-only answers)
        grounded_only: If True, only answer from documents (default: True)

    Returns:
        Gemini API response with grounding_metadata if available
    """
    # Default system instruction to enforce document-only answers
    if system_instruction is None and grounded_only:
        system_instruction = (
            "You are a helpful assistant that ONLY answers questions based on the provided documents. "
            f"Provide BRIEF and CONCISE answers - {max_sentances} sentences maximum. "
            "If the answer is not found in the documents, respond EXACTLY with: "
            "'לא נמצא מידע זה במסמכים' or 'I cannot find this information in the provided documents.' "
            "Never use external knowledge or make assumptions beyond what is explicitly stated in the documents."
        )

    config_params = {
        'tools': [
            types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[file_search_store.name],
                    metadata_filter=filter
                )
            ),
        ],
        'temperature': temperature,  # Low temperature (0.0) for document-grounded answers
        'max_output_tokens': max_output_tokens,
    }

    if system_instruction:
        config_params['system_instruction'] = system_instruction

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config=types.GenerateContentConfig(**config_params)
    )

    print(response.text)
    return response


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


def has_grounded_answer(response):
    """
    Check if the response has grounded information from documents.

    Args:
        response: Gemini API response

    Returns:
        bool: True if response is grounded with citations, False otherwise
    """
    # Check for "not found" phrases in Hebrew or English
    not_found_phrases = [
        "לא נמצא מידע",
        "cannot find this information",
        "not found in",
        "no information",
        "אין מידע"
    ]

    response_text = response.text.lower()
    for phrase in not_found_phrases:
        if phrase.lower() in response_text:
            return False

    # Check if there's grounding metadata
    try:
        gm = response.candidates[0].grounding_metadata
        if gm is None or not hasattr(gm, 'grounding_chunks'):
            return False

        # Check if there are actual chunks
        chunks = gm.grounding_chunks
        return len(chunks) > 0
    except (AttributeError, IndexError):
        return False


def get_citations(response, top_k=3, skip_if_no_answer=True):
    """
    Extract citations from Gemini response with metadata and confidence scores.

    Args:
        response: Gemini API response
        top_k: Number of top citations to return
        skip_if_no_answer: If True, return empty list when answer not found in documents

    Returns:
        list: List of dictionaries, each containing:
            - uri: Source URI
            - title: Source title
            - text: Full citation text
            - timestamp_from: Earliest timestamp (HH:MM:SS.mmm)
            - timestamp_to: Latest timestamp (HH:MM:SS.mmm)
            - metadata: Custom metadata dict (if available)
            - confidence_score: Grounding support score (if available, 0.0-1.0)
    """
    # Check if we should skip citations when no answer is found
    if skip_if_no_answer and not has_grounded_answer(response):
        print("No grounded answer found in documents - skipping citations")
        return []

    try:
        gm = response.candidates[0].grounding_metadata
    except (AttributeError, IndexError):
        print("No grounding metadata available")
        return []

    if gm is None:
        print("No grounding metadata")
        return []

    # List all retrieved chunks
    chunks = gm.grounding_chunks  # list of GroundingChunkRetrievedContext
    if not chunks:
        print("No grounding chunks found")
        return []

    top_chunks = chunks[:top_k]

    print("### Citations ###########")
    print(f"Retrieved {len(chunks)} chunks (showing top {top_k})")

    # Debug: Print all available attributes in grounding_metadata
    # print(f"DEBUG - Grounding metadata attributes: {dir(gm)}")

    # Try to find confidence/score in various possible locations
    confidence_score = None

    # Check common confidence score attribute names
    for attr_name in ['grounding_support', 'confidence', 'score', 'grounding_score', 'relevance_score']:
        if hasattr(gm, attr_name):
            confidence_score = getattr(gm, attr_name)
            print(f"Found confidence score ({attr_name}): {confidence_score}")
            break

    # Check for search_entry_point which might contain scoring info
    if hasattr(gm, 'search_entry_point') and confidence_score is None:
        sep = gm.search_entry_point
        if hasattr(sep, 'confidence') or hasattr(sep, 'score'):
            confidence_score = getattr(sep, 'confidence', getattr(sep, 'score', None))
            if confidence_score:
                print(f"Found confidence in search_entry_point: {confidence_score}")

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
            'metadata': {},
            'confidence_score': confidence_score  # Overall confidence for the response
        }

        # Check for chunk-level score/confidence if available
        chunk_score = None
        for attr_name in ['score', 'relevance_score', 'confidence', 'similarity_score']:
            if hasattr(chunk, attr_name):
                chunk_score = getattr(chunk, attr_name)
                citation_data['chunk_score'] = chunk_score
                break

        # Also check in retrieved_context
        if chunk_score is None:
            for attr_name in ['score', 'relevance_score', 'confidence']:
                if hasattr(retrieved_context, attr_name):
                    chunk_score = getattr(retrieved_context, attr_name)
                    citation_data['chunk_score'] = chunk_score
                    break

        # Add custom metadata if available
        if hasattr(retrieved_context, 'metadata'):
            citation_data['metadata'] = retrieved_context.metadata

        # Add file search store if available
        if hasattr(chunk, 'file_search_store'):
            citation_data['file_search_store'] = chunk.file_search_store

        citations.append(citation_data)

    return citations


if __name__ == '__main__':
    api_key = source_key("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    display_name="TARASA"
    store_name="fileSearchStores/TARASA-qto443d7uryu" #what was retutred once
    display_name = "aaron"
    # name = init_store(client, display_name)#fileSearchStores/sites-qto443d7uryu

    store_name = "fileSearchStores/aaron-250pjghbtrh5"

    inst_name = "ono"
    course_name = "anatomy"
    class_name = "class2"
    year = "2025"
    semester = "A"



    filter = f"institute={inst_name} AND course={course_name} AND class={class_name} AND year={year} AND semester={semester}"

    filter = f"institute={inst_name} AND course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"

    filter = f"course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"
    filter = f"institute={inst_name} AND course={course_name} "


    file_search_store = client.file_search_stores.get(name=store_name)
    #file_search_store = client.file_search_stores.get(name= display_name)
    filter = f"course={course_name} AND class={class_name} "#AND year={year} AND semester={semester}"

    query_t="what can you tell me about Khirbet Samara "
    query_t="מי היה פרויד, "
#    query_t="what can you tell me about meditation"

    response =query(client, file_search_store, query_t, filter="")
    citations = get_citations(response)

    # Example: Access citation metadata
    for citation in citations:
        print(f"\nAccessing citation data for: {citation['title']}")
        print(f"  Time range: {citation['timestamp_from']} to {citation['timestamp_to']}")

    print("_______________")
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

    response=query(client, file_search_store, query_t, filter)
    citations = get_citations(response)

    # Example: Access citation metadata as list/vector
    for i, citation in enumerate(citations):
        print(f"\nCitation {i+1} metadata:")
        print(f"  URI: {citation['uri']}")
        print(f"  Title: {citation['title']}")
        print(f"  Timestamp from: {citation['timestamp_from']}")
        print(f"  Timestamp to: {citation['timestamp_to']}")
        if 'chunk_score' in citation:
            print(f"  Chunk score: {citation['chunk_score']}")
        print(f"  Custom metadata: {citation['metadata']}")

