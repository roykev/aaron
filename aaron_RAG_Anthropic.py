from anthropic import Anthropic
import time
import os
from pathlib import Path
from utils.utils import source_key, split_transcript_into_chunks, remove_before_token
from utils.Anthropic_utils import clean_and_concat_chunks, process_transcript

configs ={}
configs['name'] = "insurance"
configs['course'] = "intro to Insurance"
configs['num']=4
configs['lan'] = "Hebrew"
configs['summary_len'] = 500
configs['num_q']=10
configs['engine']="claude-3-5-sonnet-20240620"
#configs['engine']="claude-3-opus-20240229"
#configs['engine']= "claude-3-sonnet-20240229"


configs['role']='a teaching assistant'
# model="claude-3-opus-20240229",
system_prompt=(f"You are {configs['role']}. Your mission is helping students understand the course and gets ready for the exam."
               f"You will be provided a large transcript of a lecture in {configs['course']}.\n"
               "You will get several tasks based on the transcript. Here's how to proceed:"
               "1. If you receive an example transcript and outputs, use them as a guide for your style and analysis"
               "2. For the new transcript, you'll receive it in parts. Process each part."
               "3. When you receive the final part, combine all chunks into a cohesive final output."
               "4. write just response. Don't write any preceding sentence or the task's name. e.g., Here is the short summary"
               )

# Define tasks
tasks = [
   # {
   #      "name": "long_summary",
   #      "prompt": "Write a detailed, accurate summary of the transcript. Do not leave out any important information. "
   #               f"The summary should be in {configs['lan']}"
   #              "Ensure correct phrasing and proper syntax, without grammatical and spelling errors."
   #              "Summarize the main material learned in the lesson comprehensively, in a clear and organized manner."
   #                "The summary should include several chapters"
   #                "It should include chapter headers with timestamps for when that chapter begins. "
   #                "Each chapter should start with a heading and contain one or more paragraphs to give the summary a clear structure. Add timestamps when each chapter begins in the lecture"
   #              "Use appropriate words from the lesson, while maintaining accuracy of technical terms and original meaning"
   #              "Avoid figurative language, slang, or informal expressions."
   #              "Summarize the material relevant to the lesson topic in a factual and professional manner."
   #      ,
   #      "output_file": "long_summary.txt",
   #  },
    {
        "name": "short_summary",
        "prompt": f"Write a short summary (2-3 paragraph long) of the lecture in {configs['lan']}.",
        "output_file": "short_summary.txt",
    },
    #  {
    #     "name": "main_concepts",
    #     "prompt": f"Extract around {configs['num_q']} key phrases, persons names and concepts from the transcript in {configs['lan']}."
    #     "the output format is: concept; start-end, start-end. e.g.,"
    #     "AAA; 00:15-01:40, 04:55-10:20"
    #     "BBB; 35:15-36:50"
    #     "and so on, when AAA, BBB are examples of concepts and 00:15-01:40 are start-end (from the beginning of the transcript) of when the concept is mentioned."
    #     "note that a concept can be mentioned more than once. In this examples AAA is mentioned twice: in 00:15-01:40 and 04:55-10:20 from the beginning of the transcript",
    #     "output_file": "concepts.txt",
    # },
    # {
    #     "name": "mind_map",
    #     "prompt": f"Generate an SVG code that depicts the mind map of the lecture. Include only the SVG code in your response. The text in the SVG should be in {configs['lan']}.",
    #     "output_file": "mind_map.svg",
    # },
    # {
    #     "name": "additional",
    # "prompt": f" Suggest {configs['num_q']} additional reading, media, and sources about the topics of the lecture in {configs['lan']}. "
    # " the sources should help me getting prepared for the exam"
    # f"Add references authors and pointers where appropriate",
    #  "output_file": "additional.txt",
    # },
    # {
    #     "name": "quiz",
    #     "prompt":
    #         f"Compose a quiz in {configs['lan']} about the of the lecture. {configs['num_q']} questions (multiple choice, multiple answers are allowed). "
    #         f"write '*' before the correct answers of the questions in the following format:"
    #         "question_number; question"
    #         "new line"
    #         "* choice A"
    #         "new line"
    #         "choice B"
    #         "and so on"
    #         "new line "
    #         "e.g., "
    #         "1; what is the color of an orange?"
    #         "A; red"
    #         "B; blue"
    #         "* C; orange"
    #         "D; green",
    #     "output_file": "quiz.txt",
    # },

]
def call_anthropic(system_prompt, task, transcript, long=False):
    # Get the API key
    claude_api_key = source_key("ANTHROPIC_API_KEY")
    if not claude_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set in the environment variables.")
    client = Anthropic(
        api_key=claude_api_key
    )

    prompt = f"{task}. Here is the transcript: <data>{transcript}/<data>"
    if long:
        prompt_chunks = split_transcript_into_chunks(prompt)

        full_response = []

        for i, chunk in enumerate(prompt_chunks):
            if i == 0:
                user_message = f"""
                New transcript to process (part 1): {chunk}
                Please process this part of the transcript.
                """
            elif i == len(prompt_chunks) - 1:
                user_message = f"""
                Final part of the transcript to process: {chunk}
                Please process this final part and ensure the analysis flows smoothly.
                """
            else:
                user_message = f"""
                Next part of the transcript to process: {chunk}
                Please continue processing the transcript.
                """

            chunk_response=process_transcript(client, configs['engine'], system_prompt, user_message)
            full_response.append(chunk_response)
            clean_response = clean_and_concat_chunks(full_response)

    else:
        clean_response = process_transcript(client, configs['engine'], system_prompt, prompt)

        # response = client.messages.create(
        #     model="claude-3-sonnet-20240229",
        #     max_tokens=1000,
        #     system=system_prompt,  # System prompt is now a separate parameter
        #     messages=[
        #         {"role": "user", "content": user_message}
        #     ],
        #     stream=True
        # )
        #
        # chunk_correction = ""
        # for event in response:
        #     if hasattr(event, 'type') and event.type == "content_block_delta":
        #         if hasattr(event.delta, 'text'):
        #             chunk_correction += event.delta.text
        #
        # full_corrected_transcript.append(chunk_correction)
    return (clean_response)

def process_all_tasks(system_prompt, transcript, tasks, out_dir):
    # Create output directory if it doesn't exist
    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each task
    results = {}
    try:
        for task in tasks:
            t0 = time.time()
            name = task['name']
            prompt = task['prompt']
            output_file = task['output_file']
            print(f"Processing task: {name}")
            results[name] = call_anthropic(system_prompt, prompt,transcript)
            if name =="mind_map":
                results[name]=remove_before_token(results[name],"<svg")
            print(f"Completed task: {name}")
            out_path = os.path.join(out_dir, output_file)
            # Save the output to a file
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(results[name])
            t1 = time.time()
            print(f'Done {name}. ({t1 - t0:.3f}s). Sleeping')
            time.sleep(10)  # Add a delay between tasks to avoid rate limiting

    except Exception as e:
        print(f"Error processing task {name}: {str(e)}")

# Execute tasks
t0 = time.time()
# Load the text file

file_path = f"/home/roy/OneDrive/WORK/ideas/aaron/{configs['name']}/{configs['num']}/lesson{configs['num']}.txt"
with open(file_path, "r") as transcript_raw_file:
    transcript = transcript_raw_file.read().strip()
out_dir = f"/home/roy/OneDrive/WORK/ideas/aaron/{configs['name']}/{configs['num']}/Anthropic"
process_all_tasks(system_prompt,transcript,tasks,out_dir)

#print (res)
results = {}

t1 = time.time()
print(f'Done Anthropic tasks. ({ t1- t0:.3f}s).')