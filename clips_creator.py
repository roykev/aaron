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
    def make_system_prompt(self, from_1=35, to_1=45, from_2=3, to_2=5, genre="lecture"):
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


        system_prompt = {f"You are an AI assistant tasked with analyzing and creating a trailer for a {genre} based on provided information."
        f"Your goal is to select the most informative sections of the video while conveying the main concepts."
        f"Here's the information you have:"
        f"Genre: <video_genre>{genre}</video_genre>"
        f"<transcript> {self.transcription}\n</transcript>"
        f"user will provide several tasks based on the information"
        f"The input may be provided in chunks. You will receive portions of a file and perform several tasks on each chunk. "
        f"Process the data you receive and return the results in {out_format} format. each task will get its own output"
        f"Don't write any system generated content. just the {out_format}. from the beginning of the transcript to its end"
        }
        return system_prompt
    def make_user_prompt_highlights(self, from_1=35, to_1=45, from_2=3, to_2=5,genre="lecture", lan= "English"):
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

    def make_user_prompt_chapters(self, from_1=35, to_1=45, from_2=3, to_2=5,genre="lecture", lan= "English"):
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

def make_user_prompt_emotions(self, from_1=35, to_1=45, from_2=3, to_2=5, genre="lecture", lan="English"):

            user_prompt = {
               f"Your tasks are as follows:"
            f"1. Sentiment Analysis: Determine the overall sentiment (positive, negative, or neutral) of the text at regular intervals."
            f"2. Emotion Classification: Identify the primary emotion expressed (e.g., happy, sad, angry, surprised) at regular intervals."
            f"3. Keyword Spotting: Identify emotionally significant words (e.g., 'wow,' 'amazing,' 'love,' 'crying') throughout the transcript."

            f"Important Notes:"
            f"- Sentiment is considered a superset of emotion and keywords."
            f"- Your analysis should cover the entire duration of the video."
            f"- Aim for a time resolution of no more than 30 seconds if possible."
            f" -After analyzing in a <= 30 seconds resolution, adjacent sections with the same sentiment and emotions can be combined"
            f"- If there are no significant observations in a time segment, leave the sentiment, emotion, and keywords columns empty for that segment."

        f"Output Format:"
        f"You will present your analysis in a CSV format with the following columns:"
        f"from (time),to (time),sentiment,emotion,keywords"
        f"Here's an example of how your output should be structured:"

        f"from,to sentiment,emotion,keywords"
        f"00:00,00:23,positive,happy,'wow,amazing'"
        f"00:23,01:00,neutral,,"
        f"01:00,01:30,negative,sad,'crying,disappointed'"
        f"provide only the csv. no more no less"
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
    dirpath="/home/roy/FS/OneDriver1/WORK/ideas/Moments/kan11/tzvi/5"

    movie_file = "video.mp4"
    lesson_name= "HaTZvi-5"

    extract_dir = os.path.join(dirpath, "clips")
    detect_silence = False
    rerun_prompt = False
    if detect_silence:
        analyze_silence(dirpath,a_file="raw.mp3")

    if rerun_prompt:
        clip_creator=ClipCreator(dirpath)
        clip_creator.load_artifacts()
        system_prompt=clip_creator.make_system_prompt()
        user_prompt =clip_creator.make_user_prompt_highlights()
        api_key = source_key(param="ANTHROPIC_API_KEY")
        client = Anthropic(
            api_key=api_key
        )

        res = process_prompt(client, system_prompt, user_prompt)
        print(res)
        df = pd.read_csv(io.StringIO(res))
        df.to_csv(os.path.join(dirpath,"clips.csv"),index=False)
    else:
        df= pd.read_csv(os.path.join(dirpath,"extract/trailer.csv"))


    if not os.path.exists(extract_dir):
         os.makedirs(extract_dir)
    if True:
        create_clips(df,movie_file,dirpath,from_field="start_tc",to_field="end_tc")
        make_trailer(df,extract_dir, lesson_name=lesson_name)



