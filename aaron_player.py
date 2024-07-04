import os
import collections
import numpy as np
import streamlit as st
# from pydub import AudioSegment
# from pydub.playback import play
# from pydub.utils import make_chunks
# from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from parse_AI_output import gpt_parser,range2start_end
from streamlit_extras.stylable_container import stylable_container
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

# Function to extract tags from the audio file
def extract_tags():
    # Replace this with your logic to extract tags from the audio file
    # For demonstration purpose, returning dummy tags
    if st.session_state.ai is not None:
        return st.session_state.concepts
    else:
        return {"Concept X": ['00:10-00:30', '01:11-02:30'], "Concept Y": ['02:11-03:00'], "Z": ['01:16-01:30']}
def load_files(cont):

    # Set up tkinter
    root = tk.Tk()
    root.withdraw()

    # Make folder picker dialog appear on top of other windows
    root.wm_attributes('-topmost', 1)

    # Folder picker button
    cont.title('Folder Picker')
    cont.write('Please select a folder:')
    clicked = st.button('Folder Picker')
    if clicked:
        dirname = st.text_input('Selected folder:', filedialog.askdirectory(master=root))

    col1,col2=cont.columns(2)
    st.session_state.audio = col1.file_uploader("Select a class recording (an audio file, format mp3)", type="mp3")
    st.session_state.ai = col2.file_uploader("Select an AI analysis of the class (format txt)", type="txt")



# Function to display audio player
def display_audio_player(cont):
##    audio = AudioSegment.from_mp3(audio_path)
 #   audio = audio.speedup(playback_speed=speed)
   #
   #
   # # cont.audio(audio_path, format='audio/mp3', start_time=jump_time)
   #  audio_id = cont.audio(audio_path, format='audio/mp3', start_time=f"{jump_time}ms", key='audio_player')
   #  col1, col2, col3 = cont.columns([1, 1, 1])
   #  with col2:
   #      play_icon = st.image("https://img.icons8.com/pastel-glyph/64/000000/play--v3.png")
   #      pause_icon = st.image("https://img.icons8.com/pastel-glyph/64/000000/pause--v3.png")
   #      stop_icon = st.image("https://img.icons8.com/pastel-glyph/64/000000/stop--v1.png")
   #      if play_icon.is_clicked:
   #          cont.write(
   #              f'<script>document.getElementById("{audio_id.markdown_key}").currentTime = {jump_time / 1000}; document.getElementById("{audio_id.markdown_key}").play();</script>',
   #              unsafe_allow_html=True)
   #      if pause_icon.is_clicked:
   #          cont.write(f'<script>document.getElementById("{audio_id.markdown_key}").pause();</script>',
   #                   unsafe_allow_html=True)
   #      if stop_icon.is_clicked:
   #          scont.write(
   #              f'<script>document.getElementById("{audio_id.markdown_key}").pause(); document.getElementById("{audio_id.markdown_key}").currentTime = 0;</script>',
   #              unsafe_allow_html=True)
   #  audio_id = "custom_audio_player"
   #
   #  audio_player = f"""
   #  <audio id="{audio_id}" src="{audio_path}" controls>
   #      Your browser does not support the audio element.
   #  </audio>
   #  <script>
   #      var audio = document.getElementById("{audio_id}");
   #      audio.currentTime = {jump_time / 1000};
   #  </script>
   #  """
   #
   #  cont.write(audio_player, unsafe_allow_html=True)

#    cont.subheader("Lesson Recap")
    #audio = cont.file_uploader("Select a class recording (an audio file, format mp3)", type="mp3")
    audio= st.session_state.audio
    if "speed"not in st.session_state:
        st.session_state.spead = 1.0
    if "start_time" not in st.session_state:
        st.session_state.start_time = 0
    if "end_time" not in st.session_state:
        st.session_state.end_time = None

    # Style buttons as links
    with stylable_container(
            key="link_buttons",
            css_styles="""
           button {
               background: none!important;
               border: none;
               padding: 0!important;
               font-family: arial, sans-serif;
               color: #069;
               text-decoration: underline;
               cursor: pointer;
           }
           """,
    ):
        # getting the audio file
        if audio is not None:
            audio_file = audio.read()
            cont.subheader("Player")
            col1,col2 = cont.columns([2,15])
            if col1.button("<<"):
                col1.write('<script>document.getElementById("audio_player").currentTime = 0;</script>',
                           unsafe_allow_html=True)
                st.session_state["start_time"] = 0
                st.session_state["end_time"] = None

                st.experimental_rerun()
            col2.audio(audio_file, format="audio/wav", start_time=st.session_state.start_time,end_time=st.session_state.end_time)
            # with st.expander("Player setting"):
            # # Controls for playback options
            #     speed = cont.slider("Playback Speed", min_value=0.5, max_value=2.0, step=0.1, value=1.0)
            #     st.session_state["speed"]=speed
            #     cont.write(f"Speed: {speed}")
            cont.divider()
            cont.subheader("Key Concepts")
            tags = extract_tags()
            if tags is not None:

                for tag, times in tags.items():

                    l = len(times)
                    columns = cont.columns(l+1)
                    with columns[0]:
                       st.markdown(f"**{tag}**: ")
                # Add custom CSS to align columns to the right
                    alignment_css = "<style> .st-horizonal { justify-content: right; } </style>"
                    st.write(alignment_css, unsafe_allow_html=True)
                    for i, tim in enumerate(times):
                        with columns[i+1]:
                            start_secs,end_secs= range2start_end(tim)
                            if st.button(tim):
                                st.session_state["start_time"] = start_secs
                                st.session_state["end_time"] = end_secs
                                st.experimental_rerun()


#
# def find_audio (dir):
#     for i in os.listdir(dir):
#         # List files with .mp4
#         if i.endswith(".mp3"):
#             print("Files with extension .mp3 are:", i)
#             return dir+"/"+i
# def select_folder():
#    root = tk.Tk()
#    root.withdraw()
#    folder_path = filedialog.askdirectory(initialdir="/home/roy/Downloads/aaron")
#    root.destroy()
#    return folder_path
def show_quiz(cont):
    quiz = st.session_state["quiz"]
    if quiz is not None:
        score = 0
    # Iterate through each question
        for i, block in quiz.items():
            question = block[0]
            cont.markdown(f"***{question}***")
            choices=block[1]
            # Allow multiple answers using multiselect
            selected_answers = cont.multiselect("Select all that apply", choices)
            correct =block[2]

            # Display selected answers
            if len(selected_answers):
                letters=[]
                for answer in selected_answers:
                    letter=answer.split(';')[0]
                    letters.append(letter)

                res = collections.Counter(correct) == collections.Counter(letters)
                if res:
                    pref = ':green[**Correct!**]'
                    score+=1
                    
                else:
                    pref= ':red[**Oops. Try again**]'

                st.markdown(f"**Question {i}**. {pref}: You selected: {letters}")
        st.markdown(f"**Total score:** {score}/{len(quiz)} ")



def load_AI(cont):
    ai = st.session_state.ai
    if ai is not None:
        cont.subheader("Class Summary")
        content =  ai.getvalue().decode("utf-8")
        parser = gpt_parser()
        parser.parse(content)

        cont.markdown(parser.summary)
        st.session_state["summary"]=parser.summary
        st.session_state["concepts"]= parser.concepts
        st.session_state["quiz"]= parser.quiz
        cont.divider()
        cont.subheader("Quiz")
        show_quiz(cont)

#
# # Function to display tags
# def display_tags(cont,tags):
#     if tags is not None:
#         for tag, timepoints in tags.items():
#             for timepoint in timepoints:
#                 cont.markdown(f"<font color='green'>{tag}</font>: {timepoint // 60:02d}:{timepoint % 60:02d}", unsafe_allow_html=True)

# Streamlit app
def main():
    st.session_state["dir"]=""
    st.session_state["jump"]=0
    st.session_state["ai"]=None
    st.session_state["summary"]=""
    st.session_state["concepts"]=None
    st.session_state["quiz"]=None

    sb, m_container, _ = st.columns([5,95, 5])

    # Sidebar for configuration
    m_container.title("Audio Player with Tags")
  #  sb.header("Config")

  #  col1,col2=m_container.columns(2)
    player_placeholder= m_container.empty()
    cont = player_placeholder.container()
    cont.subheader("Lesson Recap")
    load_files(cont)

    load_AI(m_container)

    display_audio_player(cont)


 #   folder_select_button = col1.button("Select Folder")
  #  if folder_select_button:
   #     selected_folder_path = select_folder()
    #    _dir = selected_folder_path
     #   st.session_state["_dir"]=_dir

    #audio_directory = st.session_state["_dir"]
    #speed = sb.slider("Select Speed", min_value=0.5, max_value=2.0, step=0.1, value=1.0)
    # jump_t, jump_b=m_container.columns([10,2])
    # jump_time_str = jump_t.text_input("Jump to Time", "00:00")
    # if jump_b.button("Jump"):
    #     # Convert jump_time_str to seconds
    #     jump_time_minutes, jump_time_seconds = map(int, jump_time_str.split(':'))
    #     jump_time = jump_time_minutes * 60 + jump_time_seconds
    #     st.session_state["jump"]=jump_time


    # Middle frame
#     if audio_directory:
#         m_container.write(f"Selected Directory: {audio_directory}")
#  #       audio_path = find_audio(os.path.join(audio_directory))
# #        tags = extract_tags(audio_path)
#
#         m_container.subheader("Tags")
#         display_tags(m_container, tags)
#
#         m_container.subheader("Text Box")
#         m_container.text_area("Enter Text", "")

if __name__ == "__main__":
    main()
