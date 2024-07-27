def clean_and_concat_chunks(chunks):
    cleaned_chunks = []
    for chunk in chunks:
        # Remove any system messages or prefixes
        if "Here's the corrected part of the transcript:" in chunk:
            chunk = chunk.split("Here's the corrected part of the transcript:", 1)[1]
        elif "Here is the corrected transcript:" in chunk:
            chunk = chunk.split("HHere is the corrected transcript:", 1)[1]
        elif "Here is the corrected transcript for that section:" in chunk:
            chunk = chunk.split("Here is the corrected transcript for that section:", 1)[1]
        elif "Here is my attempt at correcting the transcript:" in chunk:
            chunk = chunk.split("Here is my attempt at correcting the transcript:", 1)[1]
        elif "Here is the corrected version of the transcript" in chunk:
            chunk = chunk.split("Here is the corrected version of the transcript:", 1)[1]
        elif "Here is my attempt to correct the transcript:" in chunk:
            chunk = chunk.split("Here is my attempt to correct the transcript:", 1)[1]
        elif "Here is the corrected final part of the transcript with smooth flow:" in chunk:
            chunk = chunk.split("Here is the corrected final part of the transcript with smooth flow:", 1)[1]
            # Remove any other potential prefixes or suffixes
        chunk = chunk.strip()
        cleaned_chunks.append(chunk)

    # Join the chunks, ensuring proper spacing and formatting
    full_transcript = " ".join(cleaned_chunks)

    # Additional cleaning if needed (e.g., remove double spaces, normalize line breaks)
    full_transcript = " ".join(full_transcript.split())

    return full_transcript

def process_transcript(client, model, system_prompt, user_message):
    # messages = [
    #     {"role": "user", "content": f"{task_instruction}\n\nHere's the full transcript:\n\n{transcript}"}
    # ]

    response = client.messages.create(
        model=model,
        system=system_prompt,  # System prompt is now a separate parameter
        max_tokens=2000,
        messages=[
            {"role": "user", "content": user_message}
        ],
    stream=True
    )

    chunk_correction = ""
    for event in response:
        if hasattr(event, 'type') and event.type == "content_block_delta":
            if hasattr(event.delta, 'text'):
                chunk_correction += event.delta.text

    return(chunk_correction)


