import logging
import random
import time
import os
from io import StringIO

import anthropic
import pandas as pd
from anthropic import Anthropic

from utils import source_key

def header_beta():
    headers = {
        "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"  # This line enables the 8192 token limit
    }
    return headers
def compose_long_system_prompt(role, lan, title):
    system_prompt = (f"You are a {role}. I provide a {lan} transcript of a class in {title}"
                     "The objective is to extract learning material for the students"
                     "Provide only the output csv as instructed. no more no less"
                     "The input transcript is in a csv file format with columns: from, to, text, speaker. Where 'from' and 'to' are the seconds from the beginning where the 'text' starts and ends, respectively \n"
                     "(speaker is an optional column)"
                     "The CSV data is provided in chunks. You will receive portions of a CSV file and perform severasl tasks on each chunk. Process the data you receive and return the results in CSV format, including the new columns. "
                     "Don't write any system generated content. just the csv. from the beginning of the transcript to its end"
                     )
    return system_prompt

def process_chunk(client, chunk, system_prompt,user_prompt,max_retries,initial_retry_delay):

    logging.basicConfig(level=logging.INFO)
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                   model="claude-3-5-sonnet-20241022",

                max_tokens=8192,
                system=system_prompt,  # System prompt is now a separate parameter
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt + "\n\nCSV Chunk:\n" + chunk
                            }
                        ]
                    }
                ],
                stream=True
            )
            chunk_response=""

            for event in response:
                if event.type == "content_block_delta":
                    chunk_response += event.delta.text

            return chunk_response
        except anthropic.APIStatusError as e:
            if e.status_code == 429 or "overloaded" in str(e).lower():
                if attempt < max_retries - 1:
                    retry_delay = initial_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(f"API overloaded. Retrying in {retry_delay:.2f} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Failed to process chunk after {max_retries} attempts.")
                    raise
            else:
                logging.error(f"Unexpected API error: {e}")
                raise

        raise Exception("Max retries reached without successful API call")

def compose_user_prompt(lan,rules):
    user_prompt = (
        f"for each task generate a different output:"
        "1. split each section (original line) to subsections (more lines) to have a better time resolution.this is important: when possible each subsection should be no longer than 30 seconds"
        "2. classify each subsection to the stages of the wedding (preparation, ceremony, party or other) and to the sections"
        f"3. Give a score for each subsection, according to the importance of it in the ceremony and if should it be included in the clip.importance score from 0 to 10 (0 - 'must be skipped', 4- 'could be included in a long movie', 6 - 'should be included in a long clip', 9 - 'should be included in a short clip', 10 - 'must be included').A suggested importance rule is: <data> {rules} /<data>. Whenever the Groom or the Bride speak the score should be highest"
        "4. Provide a short description of the section and a longer description of the subsection."
        "5. When possible suggest who the speaker is: the role, name or relation to the couple. if not is not detected, then leave empty"
        "Output in a CSV format: From, To, from_ts, to_ts, stage, section, score, section description, subsection description, speaker( as detected in task 5). "
        "from_ts, to_ts are like From, To but in timestamp "
        "Pay attention to task 1: each line should be no longer than 30 seconds when possible"
        )

    return user_prompt

def process_in_chuncks(data, system_prompt, user_prompt, chunk_size, max_retries,
                           initial_retry_delay):  # data us euther a dataframe or a file to be opened
        api_key = source_key("ANTHROPIC_API_KEY")
        client = Anthropic(
            api_key=api_key
        )
        # Check if 'data' is a DataFrame
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, str) and os.path.isfile(data):
            # Check if 'data' is a file path and if the file exists
            df = pd.read_csv(data)  # Adjust the reading method if needed (e.g., pd.read_excel)
        else:
            raise ValueError("Invalid input: must be a DataFrame or a valid file path.")

        processed_chunks = []

        # Process the dataframe in chunks
        for i in range(0, len(df), chunk_size):
            print(i)
            chunk = df.iloc[i:i + chunk_size].to_csv(index=False)
            processed_chunk = process_chunk(client, chunk, system_prompt, user_prompt, max_retries,
                                            initial_retry_delay)
            processed_chunks.append(pd.read_csv(StringIO(processed_chunk)))

        # Concatenate all processed chunks
        final_df = pd.concat(processed_chunks, ignore_index=True)
        return final_df


def process_chuncks(role, lan, title, frmat, out_format, num, trans):
                    #system_prompt, user_prompt, chunk_size, max_retries,
                     #  initial_retry_delay):  # data us euther a dataframe or a file to be opened
    api_key = source_key("ANTHROPIC_API_KEY")
    client = Anthropic(
        api_key=api_key
    )
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        temperature=0,
        system=f"You are a {role}. I provide a {lan} transcript of a class in {title}"
               f"The objective is to extract learning material for the students"
               f"Provide only the outputs  as instructed. no more no less"
               f"The input transcript is in a {frmat} "
               f"The input may be provided in chunks. You will receive portions of a file and perform several tasks on each chunk. "
               f"Process the data you receive and return the results in {out_format} format. each task will get its own output"
               f"Don't write any system generated content. just the {out_format}. from the beginning of the transcript to its end"
               f"the output should be in {lan}"
               f"here is the transcript: " + trans,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"task 1: title: give a title to the class "
                                f"task 2: open_questions: write {num} open questions about the content to learn as a homework"
                    }
                ]
            }
        ]
    )
    print(message.content)
max_retries = 5
initial_retry_delay = 2
# number of rows
chunk_size = 130
end_time = time.time()  # Capture end time

start_time = time.time()  # Capture start time
dir_name = "/home/roy/FS/OneDriver1/WORK/ideas/aaron/azrieli/intro to computational biology"
file_name = os.path.join(dir_name, "vtt.vtt")
with open(file_name, "r") as vtt_file:
    content_from_file = vtt_file.read().strip()
process_chuncks("teaching assistant", "Hebrew", "intro to computational biology", "VTT", "JSON", 5, content_from_file)



#result = process_file(file_name)
# system_prompt = compose_long_system_prompt("teaching assistant", "hebrew", "intro to computational biology")
#
# result = process_in_chuncks(file_name,system_prompt,user_prompt,chunk_size,max_retries,initial_retry_delay)
#
# result = process_in_chuncks(file_name,system_prompt,user_prompt)

# out_file_name = os.path.join(dir_name,"trans_score.csv")
# result.to_csv(out_file_name,index=False)
# file_path = "project/trans_scores.txt"
#key_frames_file = open(file_path, 'w')
#key_frames_file.write(result)
#key_frames_file.close()

# Calculate the elapsed time in milliseconds and store it
elapsed_time_ms = (end_time - start_time)
print (elapsed_time_ms)