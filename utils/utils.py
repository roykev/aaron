import base64
import os
import tiktoken

def find_video (dir):
    for i in os.listdir(dir):
        # List files with .mp4
        if i.endswith(".mp4"):
            print("Files with extension .mp4 are:", i)
            return dir+"/"+i
def find_audio (dir):
    for i in os.listdir(dir):
        # List files with .mp4
        if i.endswith(".mp3"):
            print("Files with extension .mp3 are:", i)
            return dir+"/"+i

def find_txt (dir,sub_name):

    for f in os.listdir(dir):
        # List files with .mp4
        if f.endswith(".txt"):
            if sub_name.lower() in f.lower():
                print("File found: ", f)
                return dir+"/"+f
    return None

def source_key(param="OPENAI_API_KEY"):
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
    print(os.environ[param])
    return  (os.environ[param])



def split_transcript_into_chunks(transcript, max_tokens=3500):
    """
    Split a long transcript into chunks that fit within the specified token limit.

    :param transcript: The full transcript text
    :param max_tokens: Maximum number of tokens per chunk
    :return: List of transcript chunks
    """
    # Initialize the tokenizer
    enc = tiktoken.get_encoding("cl100k_base")

    # Tokenize the entire transcript
    tokens = enc.encode(transcript)

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


def remove_before_token(string, token):
    # Find the position of the token in the string
    token_pos = string.find(token)

    # If token is not found, return the original string
    if token_pos == -1:
        return string

    # Return the substring from the token to the end of the string
    return string[token_pos:]


def get_binary_file_downloader_html(bin_file, file_label='mp3'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}">Download {file_label}</a>'
    return href
def secs2str(secs):
    h=int(secs/3600)
    m=int((secs-h*3600)/60)
    s = secs - h*3600 - m*60
    h_s =f"{h:02d}"
    m_s = f"{m:02d}"
    s_s = f"{s:02d}"
    if h>0:
        return f"{h_s}:{m_s}:{s_s}"
    else:
        return f"{m_s}:{s_s}"

def get_audio_file_content(file_path):
    # Check if the file exists
    if not os.path.isfile(file_path):
        return None
    # Open the file in binary mode and read the content
    with open(file_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
    base64_bytes = base64.b64encode(audio_bytes)
    base64_string = base64_bytes.decode('utf-8')
    # Assuming the file is an mp3; adjust the mime type if different
    return base64_string