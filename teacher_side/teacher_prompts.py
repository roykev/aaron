import os
import time

# import numpy as np
# from anthropic import Anthropic

from utils.utils import source_key

#from utils.utils import source_key

max_retries = 5
initial_retry_delay = 2
# number of rows
chunk_size = 130

def task_title(format='JSON', lan="English"):  # Task 1: title
    prompt = (
        "Task name: <name>title/<name>\n"
        "Provide a concise and descriptive title for the lecture.\n"
        f"The format of the output should be {format}. and in {lan}"
    )
    return prompt


def task_open_questions(k=3, lan="English",format='JSON'):  # Task 2: open questions
    prompt = (
        "Task name: <name>open_questions/<name>\n"
        f"Write {k} simple open questions.\n"
        f"Write {k} difficult open questions.\n"
        f"The format of the output should be {format}."
        f" <output_language>{lan}</output_language>"

    )
    return prompt


# task 3: chapters
def task_sections(format='csv', lan="English"):  # Task 3: chapters
    prompt = (
        "Task name: <name>sections/<name>\n"
        "Partition the lecture into chapters/sections. The principles of chapters:\n"
        "1. Each section/chapter should have a distinct theme.\n"
        "2. Ensure a coherent flow between chapters.\n\n"
        "For a 60-minute lesson, try to aim for 3-7 chapters.(chapters don't have to be in an equal length)\n"
        "The output should be as follows:\n"
        "chapter_num, from, to, chapter_title, duration\n"
        "Example:\n"
        "1, 0:03:09, 0:20:02, \"Course Introduction and Syllabus Overview\", 0:16:53\n"
        "2, 0:20:02, 0:43:10, \"Early History of AI: From Aristotle to the Perceptron\", 0:23:08\n"
        "3, 0:43:10, 1:07:54, \"Symbolic vs. Connectionist Approaches to AI\", 0:24:44\n"
        "4, 1:07:54, 1:27:22, \"AI Winter and Notable Projects: ELIZA, SHRDLU, and Cyc\", 0:19:28\n"
        "5, 1:27:22, 1:28:07, \"Conclusion and Preview of Next Lecture\", 0:00:45\n\n"
        f"The format of the output should be {format} and in {lan}."
    )
    return prompt


# # Task 4: real world examples
def task_examples(lan='English',format='csv'):
    prompt = (
        "Task name: <name>examples/<name>\n"
        "Provide the relevant realistic examples from the last year about the topics there were discussed in class . \n"
        "Also provide up to three examples there were not mentioned in the class, so the teacher can use next time"       
        "Provide any reference when available. Don't invent anything"
        "If the example was mentioned in class the reference should be: class, otherwise write the reference"
        f"Output should be in {lan} and in {format}. The format is:\n\n"
        "Topic, Example, reference" )
    return prompt

# Task 5: interaction summary
def task_interaction(lan='English', format='csv'):
    prompt = (
        "Task name: <name>interaction/<name>\n"
        "Summarize the interactions between the teacher and the class: questions they asked, discussions, etc.\n"
        f"Output should be in {lan} and in {format}. The format is:\n\n"
        "Time of the interaction:\n"
        "Type: student question/teacher question/discussion/other\n"
        "Time, Type, Description"
    )
    return prompt

# Task 6: difficult topics
def task_difficult_topics(lan='English', format='csv'):
    prompt = (
        "Task name: <name>difficult_topics/<name>\n"
        "Summarize the topics that students find harder or less understood.\n"
        "Your inference should be based on the questions they asked, the discussions, and any indication that a topic wasn't conveyed clearly.\n"
        "Suggest in one sentence how to improve it (e.g., add visualization, explain simpler, give examples, give homework).\n"
        f"Output should be in {lan} and in {format}. The format is:\n\n"
        "Topic, Reason for difficulty, Recommendation for improvement."
    )
    return prompt
def compose_long_system_prompt(trans,lan="English" ):
    system_prompt = (f"You are an teaching assistant. Your task is to analyze a university class based on its transcript, and then perform several specific tasks. "
                     f"The analysis and output should be in the following language: {lan}"
                     f"Here is the information about the video:"
                     f"<transcript>{trans}</transcript>"
                     f"Output specifications"
                     f" <output_language>{lan}</output_language>"
                     f"Don't write any system generated content. return only the output in the specified format. no more no less "
                     f"include the header of the column (column names) in the output"
                     f"separate each task with a new line and ### task name ###"
                     )
    return system_prompt


tasks_dict = {
        "title":task_title,
        "sections": task_sections,
        "examples": task_examples,
       "open_questions": task_open_questions,
        "interaction": task_interaction,
        "difficult_topics": task_difficult_topics
    }

def get_tasks(lan="English"):
    unified_tasks = ""
    for task in tasks_dict.values():
        unified_tasks+= task(lan=lan) + "\n"
    return unified_tasks

def process_llm_teacher_report(trans,lan="English"):
    api_key = source_key("ANTHROPIC_API_KEY")
    client = Anthropic(
        api_key=api_key
    )
    user_prompt = get_tasks()
    message = client.messages.create(
        # model="claude-3-5-sonnet-20241022",
        model="claude-3-7-sonnet-20250219",
        max_tokens=8192,
        temperature=0.1,
        system=compose_long_system_prompt(trans,lan),
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
    return (message.content)
def extract_teacher_report_results(d_path,results):
    if isinstance(results, str):
        arr = [part.strip() for part in results.split("###") if part.strip()]
    else:
        arr = results[0].text.split("###")
    for i in np.arange(len(arr)):
        task = arr[i].strip()
        if task in tasks_dict.keys():
            content = arr[i+1].strip()
            #print(content)
            suf="csv"
            if task=="open_questions":
                suf="json"
            out_file = os.path.join(d_path,f"{task}.{suf}")
            with open(out_file, "w") as file:
                file.write(content)
if __name__ == '__main__':

    if False:
        start_time = time.time()  # Capture start time
        dir_name="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/maoz/demo/"
        dir_name="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/keren"
        dir_name="/home/roy/FS/Dropbox/WORK/Ideas/aaron/maoz"
        dir_name="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/Tal"

        file_name = os.path.join(dir_name, "transcript.vtt")
        with open(file_name, "r") as vtt_file:
            content_from_file = vtt_file.read().strip()
        ret = process_llm_teacher_report(content_from_file)
        extract_teacher_report_results(dir_name,ret)

        end_time = time.time()  # Capture end time

        elapsed_time_ms = (end_time - start_time)
        print (elapsed_time_ms)