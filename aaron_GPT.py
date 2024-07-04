import os

import openai
from openai import OpenAI



params={}
params['level']=5
params['questions']=5
params['grade']=12
model = "gpt-3.5-turbo"
model ="gpt-4o"
params['language']='Hebrew'
params['sum_len']='1000'

message_podcast=   {"role": "system", "content": "you are a podcaster that interviews about the arab world. you invite and interview experts who speark about their research area"
                                          " The content you are provided is a a transcript of a lesson (with timestamps of each section). Here are the tasks"
                                          "Task 1. summarize the content you are provided with for the the listener (summary should contain around {} words)."
                                          "the output format is: "
                                          "#1"
                                          "new line"
                                          "response to task #1"
                                          "new line"
                                          "Task 2. List of the the key names and concepts that are mentioned in the transtrcipt as follow:"
                                          "the output format is: "
                                          "#2"
                                          "new line"
                                          "concept; start-end, start-end. e.g.,"
                                          "AAA; 15-40, 55-100"
                                          "BBB; 35-50"
                                          "and so on"
                                          "when AAA, BBB are examples for concepts and 15-40 are start-end (in seconds from the beginning of the transcript) of when the concept is mentioned."
                                          "note that in this examples AAA is mentioned twice: in 15-40 and in 55-100 seconds from the beginning of the transcript"
                                          "new line"
                                          "Task 3. Compose quiz about what content: {} questions (multiple choice, multiple answers are allowed). write the correct answers of the questions follow the quiz in the following format:"
                                          "the output format is: "
                                          "#3"
                                          "new line "
                                          "question_number; question"
                                          "new line"
                                          "choice A"
                                          "new line"
                                          "choice B"
                                           "and so on"
                                          "new line "
                                          "*** correct answer to the question ****"
                                          "New line"
                                          " question_number; question "
                                          " and so on"
                                          "e.g., "
                                          "1; what is the color of an orange?"
                                          "A; red"
                                          "B; blue"
                                          "C; orange"
                                          "D; green"
                                          "*** C ****"
                                          "Task 4: Suggest 3-5 additional reading for the listener to learn more about this topic "
                                          "the output format is: "
                                          "#4"
                                          "new line "
                                          "Ref 1;"
                                          "new line "
                                          "Ref 2;"
                                          " and so on"
                                         "Task 5: Suggest 3-5 additional media (images, videos etc.) for the listener to learn more about this topic "
                                          "the output format is: "
                                          "#5"
                                          "new line "
                                          "Ref 1;"
                                          "new line "
                                          "Ref 2;"
                                          " and so on"
                                          "Task 6: Suggest 10 additional questions about this topic from external sources"
                                          "the format of questions (multiple choice) and the fromat of the output are identical to task #3"                                          
                                          "Output should be in {} language. output format is strict"                                        
                                          "".format( params['sum_len'],params['questions'], params['language'])}





message_teacher=   {"role": "system", "content": "you are a teacher of a {} grade student who learns history in Israel. Study level of the student is {} [on a scale of 0 (basic) to 5 (advanced)."
                                          " The content you are provided is a a transcript of a lesson (with timestamps of each section). Here are the tasks"
                                          "Task 1. summarize the content you are provided with for the student (summary should contain around {} words)."
                                          "the output format is: "
                                          "#1"
                                          "new line"
                                          "response to task #1"
                                          "new line"
                                          "Task 2. List of the the key names and concepts that are mentioned in the transtrcipt as follow:"
                                          "the output format is: "
                                          "#2"
                                          "new line"
                                          "concept; start-end, start-end. e.g.,"
                                          "AAA; 15-40, 55-100"
                                          "BBB; 35-50"
                                          "and so on"
                                          "when AAA, BBB are examples for concepts and 15-40 are start-end (in seconds from the beginning of the transcript) of when the concept is mentioned."
                                          "note that in this examples AAA is mentioned twice: in 15-40 and in 55-100 seconds from the beginning of the transcript"
                                          "new line"
                                          "Task 3. Compose quiz about what content: {} questions (multiple choice, multiple answers are allowed). write the correct answers of the questions follow the quiz in the following format:"
                                          "the output format is: "
                                          "#3"
                                          "new line "
                                          "question_number; question"
                                          "new line"
                                          "choice A"
                                          "new line"
                                          "choice B"
                                           "and so on"
                                          "new line "
                                          "*** correct answer to the question ****"
                                          "New line"
                                          " question_number; question "
                                          " and so on"
                                          "e.g., "
                                          "1; what is the color of an orange?"
                                          "A; red"
                                          "B; blue"
                                          "C; orange"
                                          "D; green"
                                          "*** C ****"
                                          "Task 4: Suggest 3-5 additional reading for the student to learn more about this topic "
                                          "the output format is: "
                                          "#4"
                                          "new line "
                                          "Ref 1;"
                                          "new line "
                                          "Ref 2;"
                                          " and so on"
                                         "Task 5: Suggest 3-5 additional media (images, videos etc.) for the student to learn more about this topic "
                                          "the output format is: "
                                          "#5"
                                          "new line "
                                          "Ref 1;"
                                          "new line "
                                          "Ref 2;"
                                          " and so on"
                                          "Task 6: Suggest 10 additional questions about this topic from external sources"
                                          "the format of questions (multiple choice) and the fromat of the output are identical to task #3"                                          
                                          "Output should be in {} language. output format is strict"                                        
                                          "".format(params['grade'], params['level'], params['sum_len'],params['questions'], params['language'])}
params['message']=message_podcast
def calc_cost(in_tokens, out_tokens,model):
    # Assuming the cost is based on the length of the response
    # You can adjust this calculation based on other factors

    # You may also want to consider the pricing model of the OpenAI API
    # and any additional factors such as complexity or time

    # Here, we simply calculate the cost based on the length of the response text
    if model=="gpt-4o":
        cost_per_in = 5 / 1000000  # Adjust this based on OpenAI pricing or your own criteria
        cost_per_out = 15 / 1000000  #
    else:
        cost_per_in = 1.5/1000000  # Adjust this based on OpenAI pricing or your own criteria
        cost_per_out = 2.5/1000000  #
    cost = in_tokens* cost_per_in + out_tokens*cost_per_out

    return cost



def source_key():
    # Load the contents of ~/.bashrc into environment variables
    bashrc_path = os.path.expanduser("~/.bashrc")
    with open(bashrc_path, "r") as f:
        bashrc_contents = f.read()

    # Split the contents into lines and process each line
    for line in bashrc_contents.split("\n"):
        # Skip empty lines and comments
        if not line.strip() or line.strip().startswith("#"):
            continue

        # Parse lines in the format: export VARIABLE=value
        if line.startswith("export "):
            parts = line.split(" ", 1)[1].split("=", 1)
            if len(parts) == 2:
                variable, value = parts
                os.environ[variable] = value.strip('"')

    # Now you can access the environment variables as if they were set in the shell
    print(os.environ["OPENAI_API_KEY"])
    return  (os.environ["OPENAI_API_KEY"])
def read_file(file_path):

    with open(file_path, 'r') as file:
        file_content = file.read()
    return file_content
def write_file(loc, text):
    f = open(loc, "w")
    f.write(text)
    f.close()
def compose_prompt(text_chunk, task):
    prompt = f"Task: {task}\nText:\n{text_chunk}\n"
    return prompt

def call_gpt_chunk(client, model,chunk_size=12000):
    hunk_size = 10000  # Adjust based on API limits and text characteristics
    tasks = ["keyword extraction"]

    chunks = [file_content[i:i + chunk_size] for i in range(0, len(file_content), chunk_size)]

    for chunk in chunks:
        for task in tasks:
            prompt = compose_prompt(chunk, task)
            # Make API call with prompt and process response
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": ""}
                    ]
                )
                print("Task:", task)
                print("Generated Response:", response.choices[0].message.content)
            except openai.OpenAIError as e:
                print("OpenAI API Error:", e)

            # Process response according to task
            return(response.choices[0].message.content)
def call_gpt(client, model, params):
    completion = client.chat.completions.create(
      #  model="gpt-3.5-turbo",
        model=model,



        messages=[params["message"],
            # {"role": "system", "content": "you are a teacher of a {} grade student who learns history in Israel. Study level of the student is {} [on a scale of 0 (basic) to 5 (advanced)."
            #                               " The content you are provided is a a transcript of a lesson (with timestamps of each section). Here are the tasks"
            #                               "Task 1. summarize the content you are provided with for the student (summary should contain around {} words)."
            #                               "the output format is: "
            #                               "#1"
            #                               "new line"
            #                               "response to task #1"
            #                               "new line"
            #                               "Task 2. List of the the key names and concepts that are mentioned in the transtrcipt as follow:"
            #                               "the output format is: "
            #                               "#2"
            #                               "new line"
            #                               "concept; start-end, start-end. e.g.,"
            #                               "AAA; 15-40, 55-100"
            #                               "BBB; 35-50"
            #                               "and so on"
            #                               "when AAA, BBB are examples for concepts and 15-40 are start-end (in seconds from the beginning of the transcript) of when the concept is mentioned."
            #                               "note that in this examples AAA is mentioned twice: in 15-40 and in 55-100 seconds from the beginning of the transcript"
            #                               "new line"
            #                               "Task 3. Compose quiz about what content: {} questions (multiple choice, multiple answers are allowed). write the correct answers of the questions follow the quiz in the following format:"
            #                               "the output format is: "
            #                               "#3"
            #                               "new line "
            #                               "question_number; question"
            #                               "new line"
            #                               "choice A"
            #                               "new line"
            #                               "choice B"
            #                                "and so on"
            #                               "new line "
            #                               "*** correct answer to the question ****"
            #                               "New line"
            #                               " question_number; question "
            #                               " and so on"
            #                               "e.g., "
            #                               "1; what is the color of an orange?"
            #                               "A; red"
            #                               "B; blue"
            #                               "C; orange"
            #                               "D; green"
            #                               "*** C ****"
            #                               "Task 4: Suggest 3-5 additional reading for the student to learn more about this topic "
            #                               "the output format is: "
            #                               "#4"
            #                               "new line "
            #                               "Ref 1;"
            #                               "new line "
            #                               "Ref 2;"
            #                               " and so on"
            #                              "Task 5: Suggest 3-5 additional media (images, videos etc.) for the student to learn more about this topic "
            #                               "the output format is: "
            #                               "#5"
            #                               "new line "
            #                               "Ref 1;"
            #                               "new line "
            #                               "Ref 2;"
            #                               " and so on"
            #                               "Task 6: Suggest 10 additional questions about this topic from external sources"
            #                               "the format of questions (multiple choice) and the fromat of the output are identical to task #3"
            #                               "Output should be in {} language. output format is strict"
            #                               "".format(params['grade'], params['level'], params['sum_len'],params['questions'], params['language'])}
            #


            {"role": "user", "content": "{}".format(file_content)}
        ]

    )



    res = completion.choices[0].message.content
    in_tokens = completion.usage.prompt_tokens
    out_tokens= completion.usage.completion_tokens
    return (res,in_tokens,out_tokens)
if __name__ == '__main__':

    key = source_key()
    print(key)
    client = OpenAI(api_key=key)
    file_path= "/home/roy/Downloads/boris.txt"
    file_content=read_file(file_path)
    model = "gpt-3.5-turbo"
    #gpt_res,in_tokens,out_tokens=call_gpt(client,model,params)
    gpt_res= call_gpt_chunk(client,model)
    file_path= "/home/roy/Downloads/boris_gpt.txt"
    #write_file(file_path,gpt_res)
    #print(1000*calc_cost(in_tokens,out_tokens,model))





level = 5
grade = 12
language = "Hebrew"