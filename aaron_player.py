import base64
import os
import io
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
#from streamlit_extras.stylable_container import stylable_container
from utils import find_audio, find_txt, get_audio_file_content, get_binary_file_downloader_html

sections=["Short_Summary", "Quiz", "Long_Summary","Concepts","Additional"]


# Function to extract tags from the audio file
def extract_tags():
    # Replace this with your logic to extract tags from the audio file
    # For demonstration purpose, returning dummy tags
    data = {}
    if st.session_state.concepts is not None:
        arr = st.session_state.concepts.split('\n')
        for row in arr:
            concept_vec = row.split(';')
            if len(concept_vec)==2:
                term = concept_vec[0].strip()
                times_arr = concept_vec[1].strip().split(",")
                data[term]=times_arr
    else:
        #audio = st.session_state.audio
        # audio_player_html = \
        #     f"""<audio id="audio_player" controls>
        #               <source src="{audio} type="audio/mpeg">
        #                Your browser does not support the audio element.</audio>"""
        #
        # st.markdown(audio_player_html, unsafe_allow_html=True)

        # Data setup
        data = { "AAA": ["00:10-00:30", '01:11-02:30'],
                 "BBB" :['02:11-03:00'],
                 "Z": ['01:16-01:30']}

        # # Display table with JavaScript buttons
        # for item in data:
        #     col1, col2 = st.columns([1, 2])
        #     col1.write(item["text"])
        #
        #     for name, script in item["scripts"]:
        #         button_html = f"<button onclick='{script}'>{name}</button>"
        #         col2.markdown(button_html, unsafe_allow_html=True)
    return data


        #return {"Concept X": ['00:10-00:30', '01:11-02:30'], "Concept Y": ['02:11-03:00'], "Z": ['01:16-01:30']}
def load_files(cont):

    # Set up tkinter
    root = tk.Tk()
    root.withdraw()
    # Make folder picker dialog appear on top of other windows
    root.wm_attributes('-topmost', 1)

    # Folder picker button
    #cont.title('Folder Picker')
    col1, col2 = cont.columns(2)
    col1.write('Please select a folder:')
    clicked = col2.button('Folder Picker')
    if clicked:
        dir =  filedialog.askdirectory(master=root, initialdir="./")
        st.session_state.dir=dir
      #  audio = find_audio(dir)
       # st.session_state.audio=audio

# Function to render the HTML audio player with start and end times
def audio_player(file_path, start_time, end_time):
    # HTML template for the audio player with JavaScript to set and monitor times
    file_path="media/audio.mp3"
    audio_data_url = get_audio_file_content(file_path)

    #start_time=start_time
    #end_time=end_time
    audio_html = f"""
    <audio id="audioPlayer" controls>
       <source src="data:audio/mp3;base64,{audio_data_url}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {{
            const audioPlayer = document.getElementById('audioPlayer');
            // Set the start time in seconds
            audioPlayer.currentTime = {start_time};
            // Play the audio
            audioPlayer.play();
            // Function to stop audio at the end time
            function checkTime() {{
                if (audioPlayer.currentTime >= {end_time}) {{
                    audioPlayer.pause();
                    audioPlayer.currentTime = {end_time};  // Optionally set to end time
                    audioPlayer.removeEventListener('timeupdate', checkTime);
                }}
            }}
            // Event listener to check the current time against end time
            audioPlayer.addEventListener('timeupdate', checkTime);
        }});
    </script>
    """
    return audio_html
def jump_player():
    st.session_state.audio_player = st.session_state["audio_cont"].audio(st.session_state.audio, format="audio/wav",
                                                                         start_time=st.session_state.start_time,
                                                                         end_time=st.session_state.end_time)


# Function to display audio player
def display_audio_player(cont):
    # File uploader
    uploaded_file = cont.file_uploader("Choose an audio file", type=['mp3', 'wav'])
    if uploaded_file is not None:
        st.session_state.audio_file = uploaded_file
        st.session_state.audio_bytes = uploaded_file.getvalue()
        st.session_state.audio_format = uploaded_file.type.split('/')[-1]
    audio= st.session_state.audio

    if 'audio_file' in st.session_state:
        cont.markdown("**Player**")
        # Display audio player
        #   audio_key = st.session_state.get('audio_key', 0)
        col1, col2 = cont.columns([2, 15])

        with col2:
            st.audio(st.session_state.audio_bytes, format=st.session_state.audio_format,
                 start_time=st.session_state.get('start_time', 0))  # , key=audio_key)

        # Manage playback times
        if 'playback_times' not in st.session_state:
            st.session_state.playback_times = {}
        with col1:
            st.session_state.playback_times["0"]=0
            if st.button("⏪", key="0"):
                # Set the start time and increment the key to force re-render of the audio player
                st.session_state.start_time = 0
                st.rerun()


    # Style buttons as links
    if "speed"not in st.session_state:
        st.session_state.spead = 1.0
    if "start_time" not in st.session_state:
        st.session_state.start_time = 0
    if "end_time" not in st.session_state:
        st.session_state.end_time = None

    #
    # # Style buttons as links
    # with stylable_container(
    #         key="link_buttons",
    #         css_styles="""
    #         button {
    #             background: none!important;
    #             border: none;
    #             padding: 0!important;
    #             font-family: arial, sans-serif;
    #             color: #069;
    #             text-decoration: underline;
    #             cursor: pointer;
    #         }
    #         """,
    # ):
    #     # getting the audio file
    #     if audio is not None:
    #         audio_file = audio
    #         cont.subheader("Player")
    #         col1,col2 = cont.columns([2,15])
    #         st.session_state["audio_cont"]=col2
    #         st.session_state.audio_player=st.session_state["audio_cont"].markdown(audio_player(audio_file, st.session_state["start_time"], st.session_state["end_time"]), unsafe_allow_html=True)
    #         #st.session_state.audio_player=st.session_state["audio_cont"].audio(audio_file, format="audio/wav", start_time=st.session_state.start_time,end_time=st.session_state.end_time)
    #
    #         # Button in Streamlit to change the start time
    #         if col2.button('<<'):
    #             # Using Streamlit's command to run JavaScript in the client's browser
    #             st.markdown(
    #                 "<script>setStartTime(0);</script>",
    #                 unsafe_allow_html=True
    #             )

            # if col1.button("<<"):
            #     # col1.write('<script>document.getElementById("audio_player").currentTime = 0;</script>',
            #     #            unsafe_allow_html=True)
            #     st.session_state["start_time"] = 0
            #     st.session_state["end_time"] = None
            #     st.session_state.audio_player = st.session_state["audio_cont"].markdown(
            #         audio_player(audio_file, st.session_state["start_time"], st.session_state["end_time"]),
            #         unsafe_allow_html=True)

            #     st.rerun()

    cont.divider()
            # if "concepts_expd" not in st.session_state or st.session_state["concepts_expd"]==None:
            #     st.session_state["concepts_expd"]=cont.expander("Key Concepts", expanded=True, icon="🚨")
            # tags = extract_tags()
            # if tags is not None:
            #     show_concepts( st.session_state["concepts_expd"],tags)



def show_quiz(cont):
    quiz = st.session_state["quiz"]
    if quiz is not None:
        score = 0
        quiz_arr = quiz.split("\n\n")
        valid = 0
    # Iterate through each question
        for block in quiz_arr:
            q_a= block.split('\n')
            if len(q_a)<2:
                continue
            if(len(q_a[0])==0):
                q_a = q_a[1:]
            question = q_a[0]
            question_body = question.split(';')[1].strip()
            cont.markdown(f"***{valid+1}: {question_body}***")
            choices=q_a[1:]
            choices_arr=[]
            correct_arr=[]
            for answer in choices:
                choice_arr=answer.split(";")
                choices_arr.append(choice_arr[1].strip())
                if choice_arr[0].find("*")>= 0:
                    correct_arr.append(choice_arr[1].strip())

            # Allow multiple answers using multiselect
            selected_answers = cont.multiselect("Select all that apply", choices_arr)
            valid += 1

            # # Display selected answers
            if len(selected_answers):
            #     letters=[]
            #     for answer in selected_answers:
            #         letter=answer.split(';')[0]
            #         letters.append(letter)

                res = collections.Counter(correct_arr) == collections.Counter(selected_answers)
                if res:
                    pref = ':green[**Correct!**]'
                    score+=1
                    
                else:
                    pref= ':red[**Oops. Try again**]'

                cont.markdown(f"**Question {valid+1}**. {pref}: You selected: {selected_answers}")
        cont.markdown(f"<h2 style='font-size:26px;'>Total score: {score}/{valid}</h2>", unsafe_allow_html=True)


def show_concepts(cont, tags):
    if cont is not None:
      #  Define the initial CSS to style the 'table'
      #   cont.markdown("""
      #   <style>
      #   div.stButton > button:first-child {
      #       width: 100%;
      #       margin: 2px 0;  # Adds space between buttons
      #   }
      #   .css-1k0ckh2 {
      #       padding: 0.25rem !important;  # Reduces space in the layout to mimic table rows
      #   }
      #   .css-18e3th9 {
      #       padding: 0 !important;  # Adjust padding for the container
      #   }
      #   </style>
      #   """, unsafe_allow_html=True)
        for tag, times in tags.items():
            l = len(times)
            columns = cont.columns(l + 1)
            with columns[0]:
                cont.markdown(f"**{tag}**: ")
            # Add custom CSS to align columns to the right
         #   alignment_css = "<style> .st-horizonal { justify-content: right; } </style>"
          #  st.write(alignment_css, unsafe_allow_html=True)
            for i, tim in enumerate(times):
                with columns[i + 1]:
                    start_secs, end_secs = range2start_end(tim.strip())
                    key = f'{tag}_{tim}'
                    st.session_state.playback_times[key] = start_secs

                    #    if key not in st.session_state:
                    if st.button(tim, key=key):
                        st.session_state["start_time"] = start_secs
                        st.rerun()
            cont.divider()


def get_body(str):
    # Find the index of the substring
    substring_to_find="Result:"
    index = str.find(substring_to_find)

    if index != -1:
        # Calculate the starting index of the substring after the found substring
        start_index = index + len(substring_to_find)
        # Extract the substring from start_index to the end
        result_string = str[start_index:]
    else:
        result_string = ""

    return(result_string)
def find_body_of(task):
    body = None
    if 'dir' in st.session_state or st.session_state['dir']!='':
        file_name = find_txt(st.session_state["dir"], task)
        if file_name is not None:
            f = io.open(file_name, mode="r", encoding="utf-8")
            content = f.read()
            body=get_body(content)
            f.close()
        return body

    
def load_AI(cont):
    if 'dir' in st.session_state and st.session_state['dir'] != None:

        # short = find_short_summary()
        short= find_body_of("Short_Summary")
        if short is not None:
            expd = cont.expander("Short Summary", expanded=True, icon="💥")
            expd.subheader("Short Summary")
            expd.markdown(f'<div style="text-align: right;">{short}</div>', unsafe_allow_html=True)
            st.session_state["short_summary"]=short
            expd.markdown(get_binary_file_downloader_html('media/short.mp3', 'Audio'), unsafe_allow_html=True)


        concepts = find_body_of("Concepts")
        if concepts is not None:
            st.session_state["concepts"]=concepts
           # if "concepts_expd" not in st.session_state or st.session_state["concepts_expd"] == None:
            st.session_state["concepts_expd"] = cont.expander("Key Concepts", expanded=True, icon="🏹")
            tags = extract_tags()
            if tags is not None:
                show_concepts(st.session_state["concepts_expd"], tags)

        long = find_body_of("Long_Summary")
        if long is not None:
            expd = cont.expander("Long Summary", expanded=True, icon="🏫")
            expd.subheader("Long Summary")
            expd.markdown(f'<div style="text-align: right;">{long}</div>', unsafe_allow_html=True)
           # expd.markdown(long)
            st.session_state["long_summary"] = long

        quiz = find_body_of("Quiz")
        if quiz is not None:
            expd = cont.expander("Quiz", expanded=True, icon="❓")
            expd.subheader("Self Evaluation Quiz")
            st.session_state["quiz"] = quiz
            show_quiz(expd)
           # expd.markdown(f'<div style="text-align: right;">{quiz}</div>', unsafe_allow_html=True)
            # expd.markdown(long)

        additional = find_body_of("Additional")
        if additional is not None:
            expd = cont.expander("Additional Reading", expanded=True, icon="📚")
            expd.subheader("Additional Reading")
            expd.markdown(f'<div style="text-align: right;">{additional}</div>', unsafe_allow_html=True)
           # expd.markdown(long)
            st.session_state["Additional"] = additional

        st.session_state["ai"] = True



        # tags = extract_tags()
        # if tags is not None:
        #     show_concepts( st.session_state["concepts_expd"], tags)
      #  expd = cont.expander("Long Summary", expanded=True, icon="🏫")
       # expd.subheader("Long Summary")
        #expd.markdown(f'<div style="text-align: right;">{long}</div>', unsafe_allow_html=True)
       # expd.markdown(long)
        #st.session_state["long_summary"] = long
    # ai = st.session_state.ai
    # if ai is not None:
    #     cont.subheader("Class Summary")
    #     content =  ai.getvalue().decode("utf-8")
    #     parser = gpt_parser()
    #     parser.parse(content)
    #
    #
    #     cont.markdown(parser.summary)
    #     st.session_state["summary"]=parser.summary
    #     st.session_state["concepts"]= parser.concepts
    #     st.session_state["quiz"]= parser.quiz
    #     cont.divider()
    #     cont.subheader("Quiz")
    #     show_quiz(cont)

#
# # Function to display tags
# def display_tags(cont,tags):
#     if tags is not None:
#         for tag, timepoints in tags.items():
#             for timepoint in timepoints:
#                 cont.markdown(f"<font color='green'>{tag}</font>: {timepoint // 60:02d}:{timepoint % 60:02d}", unsafe_allow_html=True)
def init():
    if 'dir' not in st.session_state:
        st.session_state["dir"] = None
    if 'jump' not in st.session_state:
        st.session_state["jump"] = 0
    if 'ai' not in st.session_state:
        st.session_state["ai"] = False
    if 'short_summary' not in st.session_state:
        st.session_state["short_summary"] = ""
    if 'long_summary' not in st.session_state:
        st.session_state["long_summary"] = ""
    if 'concepts' not in st.session_state:
        st.session_state["concepts"] = None
    if 'quiz' not in st.session_state:
        st.session_state["quiz"] = None
    if 'audio' not in st.session_state:
        st.session_state["audio"] = None
    if 'audio_player' not in st.session_state:
        st.session_state["audio_player"] = None
    if 'concepts_expd' not in st.session_state:
        st.session_state["concepts_expd"] = None
    if 'audio_cont' not in st.session_state:
            st.session_state["audio_cont"] = None

# Streamlit app
def main():
    if 'ai' not in st.session_state or st.session_state["ai"] == False:
        init()

    sb, m_container = st.columns([1,100])

    m_container.title("Aaron")
    m_container.subheader("Lecture Recap")

    player_placeholder= m_container.empty()
    cont = player_placeholder.container()
    #if 'dir' not in st.session_state or st.session_state["dir"] == "":
    load_files(cont)

    #if  'dir' in st.session_state and st.session_state["dir"] != "":
    display_audio_player(cont)
    #if 'ai' not in st.session_state or st.session_state["ai"] == False:
    load_AI(m_container)



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
