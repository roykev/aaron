import logging
import random
import time
import os
from io import StringIO

import anthropic
import numpy as np
import pandas as pd
from anthropic import Anthropic

from utils import source_key
class UnifiedPrompt:
    def __init__(self, dir_path, genre="historical drama"):
        self.path = dir_path
        self.genre=genre

    def compose_long_system_prompt(self, lan, trans):
        system_prompt = (f"You are an advanced video analysis system. Your task is to analyze a video based on its transcript and scene partitions, and then perform several specific tasks. "
                         f"The analysis and output should be in the following language:"
                         f"Here is the information about the video:"
                         f"<transcript>{trans}</transcript>"
                         f"Output specifications"
                         f" <output_language>{lan}</output_language>"
                         f"Don't write any system generated content. return only the output in the specified format. no more no less "
                         f"include the header of the column (column names) in the output"
                         f"separate each task with a new line and ### task name ###"
                         )
        return system_prompt

    def task_chapters(self):
        task = (
          f"Task name: <name>chapters/<name>"
          f"Partition the video into chapters:"
          f"- Each chapter should have a distinct theme."
          f"- Ensure a coherent flow between chapters."
          f"- ideal chapter should last between 5-10 minutes. try to aim to this duration when possible"
          f"- try to identify at least 5 chapters"
         
          f" Here's an example of how your output should be structured:"
        f"chapter_number,start_time,end_time,theme"
        f"1, 00:00:00, 00:15:30, 'Introduction and Family Dynamics'"
        f"2, 00:15:30, 00:30:00, 'Revelations and Confrontations'"
        f"3, 00:30:00, 00:41:56, 'Emotional Resolution and Truth'"
        )
        return task
    def task_summary(self, len_ = 300):
        task = (
            f"Task name: <name>summary/<name>"
            f"Summarize the video in {len_} words."
        )
        return task

    def task_title(self):
        task = (
            f"Task name: <name>title/<name>"
            f"give a title to the class."
        )
        return task
    def task_trailer(self, from_2, to_2 ,to_1):
        task = (
       f"Task name: <name>trailer/<name>"
       f"Create suggestions for a trailer of the video:"
       f"- The trailer should be between <trailer_duration_min>{from_2}</trailer_duration_min> and <trailer_duration_max>{to_2}</trailer_duration_max> minutes long."
       f"- Each suggested section should include: start time, end time, and a brief description."
       f"- The trailer should be interesting and dynamic while maintaining the overall story-line."
       f"- Skip non-interesting parts."
       f"- Rules for section selection:"
       f" a. Sections should be the most engaging parts of the video."
       f" b. Each section should not be longer than <max_section_duration>{to_1}</max_section_duration> seconds (unless absolutely necessary)."
       f" c. Never cut mid-sentence or mid-idea. Consider the scene partitions when making cuts."
       f" d. A section should not start when a few seconds before a scene ends and should not end right after a scene starts."
       f" e. Maintain a logical flow from start to end."
       f" f. Ensure sections align with key concepts from the summary."
       f" Here's an example of how your output should be structured:"
        f"section_number,start_time,end_time,description"
        f"1,00:30:20,00:31:00,'Opening tension scene with family confrontation'"
        f"2,00:34:50,00:35:30,'Dramatic revelation about Gabriel Nisan'"
        f"3,00:39:00,00:39:45,'Emotional climax with Sonya'"
        f"4,00:41:20,00:41:50,'Final emotional resolution'"
        )
        return task
    def task_sentiment(self, ):
        task = (
            f"Task name: <name>sentiment/<name>"
            f" a. Sentiment Analysis: Determine the overall sentiment ( (use only these four options: positive, negative, neutral or other) of the text at regular intervals."
            f"b. Emotion Classification: Identify the primary emotion expressed (e.g., happy, sad, angry, surprised) at regular intervals."
            f"c. Keyword Spotting: Identify emotionally significant words (e.g., wow, amazing, love, crying) throughout the transcript."
    
        f"Important Notes:"
    f"- Sentiment is considered a superset of emotion and keywords."
    f"- Your analysis should cover the entire duration of the video."
    f"- Aim for a time resolution of no more than 30 seconds if possible."
     f"-After analyzing in a <= 30 seconds resolution, adjacent sections with the same sentiment and emotions can be combined"
    f"- If there are no significant observations in a time segment, leave the sentiment, emotion, and keywords columns empty for that segment."
            f" Here's an example of how your output should be structured:"
            f"from,to sentiment,emotion,keywords"
    f"00:00,00:23,positive,happy,'wow;amazing'"
    f"00:23,01:00,neutral,,"
    f"01:00,01:30,negative,sad,'crying;disappointed'"

        )
        return task
    tasks_dict = {
        "title":task_title,
     #   "chapters": task_chapters,
        "summary": task_summary,
   #     "trailer": task_trailer,
    #    "sentiment": task_sentiment,
    }
    def process(self, role, lan, title, frmat, out_format, num, trans):
                        #system_prompt, user_prompt, chunk_size, max_retries,
                         #  initial_retry_delay):  # data us euther a dataframe or a file to be opened
        api_key = source_key("ANTHROPIC_API_KEY")
        client = Anthropic(
            api_key=api_key
        )
        user_prompt = self.task_chapters() +'\n' + self.task_sentiment()
        message = client.messages.create(
            #model="claude-3-5-sonnet-20241022",
            model="claude-3-7-sonnet-20250219",
            max_tokens=8192,
            temperature=0.1,
            system=self.compose_long_system_prompt(lan, trans),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]
        )
        return(message.content)
    def extract_results(self,results):
        arr = results[0].text.split("###")
        for i in np.arange(len(arr)):
            task = arr[i].strip()
            if task in self.tasks_dict.keys():
                content = arr[i+1].strip()
                print(content)
                out_file = os.path.join(self.path,f"{task}.csv")
                with open(out_file, "w") as file:
                    file.write(content)



if __name__ == '__main__':

    max_retries = 5
    initial_retry_delay = 2
    # number of rows
    chunk_size = 130
    end_time = time.time()  # Capture end time

    start_time = time.time()  # Capture start time
    dir_name = "/home/roy/FS/OneDriver1/WORK/ideas/aaron/azrieli/intro to computational biology"
    dir_name="/home/roy/FS/OneDriver1/WORK/ideas/Moments/kan11/tzvi/5"
    prompt = UnifiedPrompt(dir_name)
    file_name = os.path.join(dir_name, "vtt.vtt")
    with open(file_name, "r") as vtt_file:
        content_from_file = vtt_file.read().strip()
    ret = prompt.process("teaching assistant", "English", "intro to computational biology", "VTT", "JSON", 5, content_from_file)
    prompt.extract_results(ret)


    elapsed_time_ms = (end_time - start_time)
    print (elapsed_time_ms)