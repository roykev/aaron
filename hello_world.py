import os
from openai import OpenAI

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

key = source_key()
print(key)
client = OpenAI(api_key=key)
level = 5
grade = 12
language = "Hebrew"
file_path= "/home/roy/Downloads/trans2.txt"
file_content=read_file(file_path)
completion = client.chat.completions.create(
  model="gpt-3.5-turbo",
  # messages=[
  #   {"role": "system", "content": "you are a teacher of a {} grade student who learns history in Israel. Study level of the student is {} [on a scale of 0 (basic) to 5 (advanced)".format(grade, level)},
  #   {"role": "user", "content": "I am a stutent in level {}. Compose a 3 question (multiple choice) quiz about the Hagana movement. Level of the comoplexity of the quiz should reflect my study level. Answers of the questions should follow the quiz in the following format (question number)-(right answer). e.g., 1-A, 2-C, 3-D".format(level)},
  # ]

messages=[
    {"role": "system", "content": "you are a teacher of a {} grade student who learns history in Israel. Study level of the student is {} [on a scale of 0 (basic) to 5 (advanced)."
                                  " The content you  are provided is a a transcript of a lesson (with timestamps of each section), here are the tasks" 
                                  "1. summarize the content you are provided with for the student (summary should be contain 100-200 words)."
                                  "2. List of the the key names and concepts that are mentioned in the transtrcipt (with the timestamps of where they are mentioned. several timestamps allowed if a concept is mentioned more than once)"
                                  "3. Compose a 3 question (multiple choice) quiz about what content) (Answers of the questions should follow the quiz in the following format (question number)-(right answer). e.g., 1-A, 2-C, 3-D)"
                                  "Output should be in {}"
                                  "Task #1: "
                                  "(new line)"
                                  "answer"
                                  "(new line)"
                                  "Task #2"
                                  "(new line)"
                                  "answer"
                                  "and so on"
                                  "".format(grade, level,language)},
    {"role": "user", "content": "{}".format(file_content)}
  ]

)


res = completion.choices[0].message.content
print (res)


