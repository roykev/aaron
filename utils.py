import base64
import os
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
            if sub_name in f:
                print("File found: ", f)
                return dir+"/"+f
    return None


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