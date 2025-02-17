import logging
import io
import os
import time
import random
import pandas
import pandas as pd
import tiktoken
from anthropic import Anthropic,APIStatusError

from utils.clips_utils import create_clips, make_trailer
from utils.utils import source_key
from audio.silance_detect import analyze_silence

class ClipCreator:
    def __init__(self, dir_path, genre="educational"):
        self.path = dir_path
        self.genre=genre
    def load_artifacts(self):
        summary_f = os.path.join(self.path, "short_summary.txt")
        f = open(summary_f, "r")
        self.summary =f.read()

        try:
            concepts_f = os.path.join(self.path, "concepts.txt")
            f = open(concepts_f, "r")
            self.concepts = f.read()
        except:
            pass
        trans_f = os.path.join(self.path, "transcript.json")
        f = open(trans_f, "r")
        self.transcription = f.read()
        scenes_f = os.path.join(self.path, "scenes.csv")
        self.scenes = pd.read_csv(scenes_f)
        silence_f = os.path.join(self.path, "silence.csv")
        self.silence = pd.read_csv(silence_f)
    def make_system_prompt(self, from_1=35, to_1=45, from_2=3, to_2=5, genre="lecture", lan= "English"):
        # system_prompt = {f"You are a professional video editor specializing in creating concise {self.genre} content. "
        #                  "Your task is to analyze lecture content and identify the most important sections that maintain the core message while fitting within time constraints."
        #                  "You will output your selections in CSV format."
        #                  "Rules for section selection:"
        #                  f"- Each section should be {from_1}-{to_1} seconds (unless absolutely necessary to be longer)"
        #                  f"- Total video should be {from_2}-{to_2} minutes"
        #                  f"- Never cut mid-sentence or mid-idea. Avoid long silence periods"
        #                  f"- A section should not start a few seconds before a scene ends or during a long silence (in that case it would start after)"
        #                  f"- A section should not end right after a scene start, in a middle of a sentance, or during a long silence (in that case it would end before)"
        #                  f"- Maintain logical flow from introduction through conclusion"
        #                  f"- Ensure sections align with key concepts (optional) from summary"
        #                  "The data may be provided in chunks. so process them all before providing the results"}


        system_prompt = {f"You are an AI assistant tasked with creating a trailer for a lecture based on provided information."
        f"Your goal is to select the most infromative sections of the video while conveying the main concepts."
        f"Here's the information you have:"
        f"Genre: <video_genre>{genre}</video_genre>"
        f"<language>{lan}</language>"
        f"<transcript> {self.transcription}\n</transcript>"
        }
        return system_prompt
    def make_user_prompt(self, from_1=35, to_1=45, from_2=3, to_2=5,genre="lecture", lan= "English"):
        # user_prompt = {
        #     "Create a video edit selection from this lecture. "
        #     "Output should be in CSV format with columns: from,to,duration,description"
        #     "The sections should:"
        #     "1. Cover the main ideas from the summary"
        #     "2. Maintain logical flow"
        #     "3. Include key demonstrations if relevant"
        #     f"4. Total around {from_2}-{to_2} minutes"
        #     f"5. Each section {from_1}-{to_1} seconds unless necessary"
        #     f"6. each section should contain complete idea(s)"
        #
        #     f"Here are the source materials:"
        #     f"<summary>"
        #     f"{self.summary}"
        #     f"</summary>"
        #     f"<concepts>"
        #     f"{self.concepts}"
        #     f"</concepts>"
        #     f"<transcript>"
        #     f"{self.transcription}"
        #     f"</transcript>"
        #     f"<scenes>"
        #     f"{self.scenes}"
        #     f"</scenes>"
        #     f"<silence>"
        #     f"{self.silence}"
        #     f"</silence>"
        #     f"Output the selections in this format:"
        #     f"from,to,duration,description"
        #     f"00:00:00,00:00:45,45,'Introduction and context'"
        #     f"[continue with additional rows...]"
        #     f"Provide only the output csv as instructed. no more no less"
        #
        # }
        user_prompt = {
            f"Your task is to create a trailer for this {genre} "
f"Please follow these rules when selecting sections:"
f"1. Choose the most informative,sections."
f"2. Each section should be between <min_section_duration>{from_1}</min_section_duration> and <max_section_duration>{to_1}</max_section_duration> seconds long, unless absolutely necessary to be longer."
f"3. Never cut mid-sentence or mid-idea. Consider the scenes and audio events, such as silences."
f"4. Maintain a logical flow from start to end."
f"5. Ensure selected sections align with key concepts" 
f"6. Skip non-interesting, irrelevant parts."

f"output structure:"
f"from,to,duration, short description,long description"
f"00:00:09, 00:00:45,36, 'Intro', 'Opening scene introducing main character'"
f"00:02:15,00:02:52,37, 'Action, 'Exciting action sequence'"
f"Please provide your analysis and trailer section suggestions in {lan}." 
            f"output should be the csv. no more, no less "
                       }
        return user_prompt

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
                                "text": user_prompt + "\n\nChunk:\n" + chunk
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
        except APIStatusError as e:
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
def split_task_into_chunks(prompt, max_tokens=7200):
    """
    Split a long transcript into chunks that fit within the specified token limit.

    :param transcript: The full transcript text
    :param max_tokens: Maximum number of tokens per chunk
    :return: List of transcript chunks
    """
    # Initialize the tokenizer
    enc = tiktoken.get_encoding("cl100k_base")

    # Tokenize the entire transcript
    tokens = enc.encode(prompt)

    chunks = []
    current_chunk = []
    current_chunk_tokens = 0

    for token in tokens:
        if current_chunk_tokens + 1 > max_tokens:
            # If adding this token would exceed the limit, save the current chunk
            chunks.append(enc.decode(current_chunk))
            current_chunk = []
            current_chunk_tokens = 0

        current_chunk.append(token)
        current_chunk_tokens += 1

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(enc.decode(current_chunk))
    return chunks
def process_prompt(client, system_prompt,user_prompt):
    # Create the message
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        system=system_prompt.pop(),  # System prompt is now a separate parameter
        messages=[{
            "role": "user",
            "content": user_prompt.pop()
        }]
    )

    # Return the summary
    return message.content[0].text


if __name__ == '__main__':
    dirpath = "/home/roy/FS/OneDriver1/WORK/ideas/aaron/Miller/AI for business/2024/6/2"
    movie_file = "6.2.mp4"
    lesson_name= "Intro to AI"

    extract_dir = os.path.join(dirpath, "clips")
    detect_silence = False
    rerun_prompt = True
    if detect_silence:
        analyze_silence(dirpath,a_file="raw.mp3")

    if rerun_prompt:
        clip_creator=ClipCreator(dirpath)
        clip_creator.load_artifacts()
        system_prompt=clip_creator.make_system_prompt()
        user_prompt =clip_creator.make_user_prompt()
        api_key = source_key(param="ANTHROPIC_API_KEY")
        client = Anthropic(
            api_key=api_key
        )

        res = process_prompt(client, system_prompt, user_prompt)
        print(res)
        df = pd.read_csv(io.StringIO(res))
        df.to_csv(os.path.join(dirpath,"clips.csv"),index=False)
    else:
        df= pd.read_csv(os.path.join(dirpath,"clips.csv"))


    if not os.path.exists(extract_dir):
         os.makedirs(extract_dir)
    if False:
        create_clips(df,movie_file,dirpath)
        make_trailer(df,extract_dir, lesson_name=lesson_name)



