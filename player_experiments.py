import streamlit as st
import streamlit.components.v1 as components
import streamlit as st

def main():
    st.title("Audio Player with Dynamic Control Buttons")

    # File uploader
    uploaded_file = st.file_uploader("Choose an audio file", type=['mp3', 'wav'])
    if uploaded_file is not None:
        # Store audio file in session state if newly uploaded
        if 'audio_file' not in st.session_state or uploaded_file.name != st.session_state.audio_file.name:
            st.session_state.audio_file = uploaded_file
            st.session_state.audio_bytes = uploaded_file.getvalue()
            st.session_state.audio_format = uploaded_file.type.split('/')[-1]

    if 'audio_file' in st.session_state:
        # Display audio player
     #   audio_key = st.session_state.get('audio_key', 0)
        st.audio(st.session_state.audio_bytes, format=st.session_state.audio_format, start_time=st.session_state.get('start_time', 0))#, key=audio_key)

        # Manage playback times
        if 'playback_times' not in st.session_state:
            st.session_state.playback_times = []

        new_time = st.number_input("Enter time in seconds", min_value=0, step=1, key='new_time')
        if st.button("Add Time"):
            st.session_state.playback_times.append(new_time)

        # Displaying playback buttons
        for index, time in enumerate(st.session_state.playback_times):
            if st.button(f"Play from {time}s", key=f"time_{index}"):
                # Set the start time and increment the key to force re-render of the audio player
                st.session_state.start_time = time
                st.rerun()
#                st.session_state.audio_key += 1


if __name__ == "__main__":
    main()


# # from pydub import AudioSegment
# # import io
# import threading
#
# import streamlit as st
# import time
#
# import streamlit as st
# from streamlit_webrtc import webrtc_streamer, WebRtcMode
# import av
# import numpy as np
# from pydub import AudioSegment
# import io
# import time
# import os
#
# class AudioPlayer1:
#     def __init__(self):
#         self.audio = None
#         self.play_time = 0
#         self.playing = False
#         self.sample_rate = 44100
#
#     def load_audio(self, audio_file):
#         if isinstance(audio_file, str):  # If it's a file path
#             if os.path.exists(audio_file):
#                 self.audio = AudioSegment.from_file(audio_file)
#             else:
#                 raise FileNotFoundError(f"The file {audio_file} does not exist.")
#         else:  # If it's a file object (e.g., from st.file_uploader)
#             audio_bytes = audio_file.read()
#             file_extension = os.path.splitext(audio_file.name)[1][1:].lower()
#             self.audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=file_extension)
#
#         self.audio = self.audio.set_frame_rate(self.sample_rate).set_channels(1)
#     def get_audio_frame(self):
#         if self.playing:
#             start_sample = int(self.play_time * self.sample_rate)
#             end_sample = start_sample + self.sample_rate // 30  # 30 fps
#             samples = self.audio[start_sample:end_sample].get_array_of_samples()
#             self.play_time += 1 / 30
#             if self.play_time >= len(self.audio) / 1000:
#                 self.play_time = 0
#             return np.array(samples, dtype=np.int16)
#         else:
#             return np.zeros(self.sample_rate // 30, dtype=np.int16)
#
#
# class AudioPlayer:
#     def __init__(self):
#         self.audio = None
#         self.play_time = 0
#         self.playing = False
#         self.duration = 0
#
#     def load_audio(self, audio_file):
#         audio_bytes = audio_file.read()
#         self.audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=audio_file.name.split('.')[-1])
#         self.duration = len(self.audio) / 1000  # Duration in seconds
#
# def audio_frame_callback(frame):
#     new_frame = av.AudioFrame.from_ndarray(
#         audio_player.get_audio_frame(), format='s16', layout='mono')
#     new_frame.sample_rate = audio_player.sample_rate
#     return new_frame
#
#
# def main():
#     st.title("Custom Audio Player")
#
#     audio_player = AudioPlayer()
#
#     audio_file = st.file_uploader("Choose an audio file", type=["mp3", "wav"])
#
#     if audio_file is not None:
#         try:
#             audio_player.load_audio(audio_file)
#
#             # Display the built-in audio player
#             st.audio(audio_file)
#
#             # Control buttons
#             col1, col2, col3, col4 = st.columns(4)
#
#             with col1:
#                 if st.button("Play/Pause"):
#                     audio_player.playing = not audio_player.playing
#
#             with col2:
#                 if st.button("Jump to Start"):
#                     audio_player.play_time = 0
#
#             with col3:
#                 if st.button("Jump to 1 Minute"):
#                     audio_player.play_time = min(60, audio_player.duration)
#
#             with col4:
#                 if st.button("Jump to 5 Minutes"):
#                     audio_player.play_time = min(300, audio_player.duration)
#
#             # Progress bar and time display
#             progress = st.progress(0)
#             time_display = st.empty()
#
#             def update_progress():
#                 while True:
#                     if audio_player.playing:
#                         audio_player.play_time += 0.1
#                         if audio_player.play_time >= audio_player.duration:
#                             audio_player.play_time = 0
#                             audio_player.playing = False
#                         progress.progress(audio_player.play_time / audio_player.duration)
#                         mins, secs = divmod(int(audio_player.play_time), 60)
#                         time_display.text(f"Current Position: {mins:02d}:{secs:02d}")
#                     time.sleep(0.1)
#
#             # Start the progress update in a separate thread
#         #    threading.Thread(target=update_progress, daemon=True).start()
#
#             # Keep the app running
#             st.write("Audio player is ready. Use the controls above to play/pause and navigate.")
#           #  st.write("Note: The built-in player and custom controls are not synchronized.")
#            # st.write("Close the browser tab to stop the application.")
#
#         except Exception as e:
#             st.error(f"Error loading audio file: {str(e)}")
# def main1():
#     st.title("Synchronized Audio Player")
#
#     #audio_file = st.file_uploader("Choose an audio file", type=["mp3", "wav"])
#     #audio_file = "media/audio.mp3"
#
#
#     audio_file = st.file_uploader("Choose an audio file", type=["mp3", "wav"])
#
#     if audio_file is not None:
#         try:
#             audio_player.load_audio(audio_file)
#
#             webrtc_ctx = webrtc_streamer(
#                 key="audio-player",
#                 mode=WebRtcMode.SENDONLY,
#                 audio_frame_callback=audio_frame_callback,
#                 rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
#             )
#
#             audio_duration = len(audio_player.audio) / 1000  # Duration in seconds
#
#             # Control buttons
#             col1, col2, col3, col4 = st.columns(4)
#
#             with col1:
#                 if st.button("Play/Pause"):
#                     audio_player.playing = not audio_player.playing
#
#             with col2:
#                 if st.button("Jump to Start"):
#                     audio_player.play_time = 0
#
#             with col3:
#                 if st.button("Jump to 1 Minute"):
#                     audio_player.play_time = min(60, audio_duration)
#
#             with col4:
#                 if st.button("Jump to 5 Minutes"):
#                     audio_player.play_time = min(300, audio_duration)
#
#             # Progress bar and time display
#             progress = st.progress(0)
#             time_display = st.empty()
#
#             def update_progress():
#                 while True:
#                     if webrtc_ctx.state.playing:
#                         progress.progress(audio_player.play_time / audio_duration)
#                         mins, secs = divmod(int(audio_player.play_time), 60)
#                         time_display.text(f"Current Position: {mins:02d}:{secs:02d}")
#                     time.sleep(0.1)
#
#             # Start the progress update in a separate thread
#             threading.Thread(target=update_progress, daemon=True).start()
#
#             # Keep the app running
#             st.write("Audio player is ready. Use the controls above to play/pause and navigate.")
#             st.write("Close the browser tab to stop the application.")
#
#         except Exception as e:
#             st.error(f"Error loading audio file: {str(e)}")
#
# if __name__ == "__main__":
#     audio_player = AudioPlayer()
#     main()
#
#
# #
# # def main():
# #     st.title("Audio Player App")
# #
# #     # Upload audio file
# # #    audio_file = st.file_uploader("Choose an audio file", type=["mp3", "wav"])
# #     audio_file = "media/audio.mp3"
# #
# #     if audio_file is not None:
# #         # Display audio player
# #         st.audio(audio_file)
# #
# #         # Get audio duration (this is a placeholder, as we can't get the actual duration without additional libraries)
# #         # For demonstration purposes, let's assume the audio is 10 minutes long
# #         audio_duration = 600  # 10 minutes in seconds
# #
# #         # Create a progress bar to show current position
# #         progress = st.progress(0)
# #
# #         # Create a placeholder for the current time display
# #         time_display = st.empty()
# #
# #         # Initialize session state for tracking playback position
# #         if 'position' not in st.session_state:
# #             st.session_state.position = 0
# #
# #         # Control buttons
# #         col1, col2, col3 = st.columns(3)
# #
# #         with col1:
# #             if st.button("Jump to Start"):
# #                 st.session_state.position = 0
# #
# #         with col2:
# #             if st.button("Jump to 1 Minute"):
# #                 st.session_state.position = min(60, audio_duration)
# #
# #         with col3:
# #             if st.button("Jump to 5 Minutes"):
# #                 st.session_state.position = min(300, audio_duration)
# #
# #         # Update progress bar and time display
# #         while st.session_state.position < audio_duration:
# #             progress.progress(st.session_state.position / audio_duration)
# #             mins, secs = divmod(st.session_state.position, 60)
# #             time_display.text(f"Current Position: {mins:02d}:{secs:02d}")
# #             time.sleep(1)
# #             st.session_state.position += 1
# #
# #         # Reset position when audio ends
# #         if st.session_state.position >= audio_duration:
# #             st.session_state.position = 0
# # #
# # if __name__ == "__main__":
# #     main()
# # #
# # # Load your audio file
# #
# # audio = AudioSegment.from_file(audio_file_path)
# #
# # # Get user input for start and end times
# # start_time = st.number_input('Start time (seconds)', min_value=0, value=0, step=1)
# # end_time = st.number_input('End time (seconds)', min_value=0, value=30, step=1)
# #
# # # Convert seconds to milliseconds
# # start_time_ms = start_time * 1000
# # end_time_ms = end_time * 1000
# #
# # # Extract the desired part of the audio
# # extracted_part = audio[start_time_ms:end_time_ms]
# #
# # # Save to buffer
# # buffer = io.BytesIO()
# # extracted_part.export(buffer, format="mp3")
# # buffer.seek(0)
# #
# # # Play the audio
# # if st.button('Play Segment'):
# #     st.audio(buffer, format='audio/mp3')
# #
# #
# #
# # # import streamlit as st
# # # import base64
# # # import os
# # #
# # # def get_audio_file_content(file_path):
# # #     # Check if the file exists
# # #     if not os.path.isfile(file_path):
# # #         return None
# # #     # Open the file in binary mode and read the content
# # #     with open(file_path, "rb") as audio_file:
# # #         audio_bytes = audio_file.read()
# # #     base64_bytes = base64.b64encode(audio_bytes)
# # #     base64_string = base64_bytes.decode('utf-8')
# # #     # Assuming the file is an mp3; adjust the mime type if different
# # #     return base64_string
# # #
# # # # File path - adjust this to point to your actual file location
# # # audio_file_path = "/home/roy/Downloads/audio.mp3"  # Update this path to the correct location
# # # audio_file_path = "media/audio.mp3"
# # # full_path = os.path.abspath(audio_file_path)
# # # # # Placeholder for audio data URL
# # # audio_data_url = get_audio_file_content(audio_file_path)
# # # # # audio_data = base64.b64decode(audio_data_url)
# # # # #
# # # # # with open("/home/roy/Downloads/economics/audio1.mp3", "wb") as file:
# # # # #     file.write(audio_data)
# # # #
# # # if audio_data_url is None:
# # #      st.error("Failed to load audio file. Please check the file path.")
# # # else:
# # #      st.text("OK")
# # #
# # #      # Define your HTML with JavaScript for the audio player
# # #      audio_html = f"""
# # #      <div>
# # #          <audio id="audioPlayer" controls>
# # #              <source src="data:audio/mp3;base64,{audio_data_url}" type="audio/mp3">
# # #              Your browser does not support the audio element.
# # #          </audio>
# # #          <script>
# # #              function setStartTime(startTime) {{
# # #                  const audioPlayer = document.getElementById('audioPlayer');
# # #                  if (audioPlayer) {{
# # #                      audioPlayer.currentTime = startTime;
# # #                      audioPlayer.play();
# # #                  }} else {{
# # #                      console.error('Audio player not found');
# # #                  }}
# # #              }}
# # #          </script>
# # #      </div>
# # #      """
# # #
# # #      # Render the HTML in the Streamlit app
# # #      st.markdown(audio_html, unsafe_allow_html=True)
# # #
# # #      # Button in Streamlit to change the start time
# # #      if st.button('Set Start Time to 30s'):
# # #          # Using Streamlit's command to run JavaScript in the client's browser
# # #          st.markdown(
# # #              "<script>setStartTime(30);</script>",
# # #              unsafe_allow_html=True
# # #          )
# # # #
# # # #     # Directly use a known good data URL or a small audio file
# # # # audio_html = f"""
# # # #  <audio controls>
# # # #     <source src="{audio_file_path}" type="audio/mp3">
# # # # </audio>
# # # # # """
# # # # st.text(audio_html)
# # # # st.markdown(audio_html, unsafe_allow_html=True)
# # #
# # # # audio_html = f"""
# # # #  <audio controls>
# # # #     <source src=data:audio/mp3;base64,{audio_data_url} type="audio/mp3">
# # # #     Your browser does not support the audio element.
# # # # </audio>
# # # #
# # # # """
# # # # st.text(f"{len(audio_html)}")
# # # # st.markdown(audio_html, unsafe_allow_html=True)
# # #
# # # # Embed audio player with JavaScript to control start and end times
# # # # audio_html = f"""
# # # # <div>
# # # #     <audio id="audioPlayer" controls>
# # # #         <source src="data:audio/mp3;base64,{audio_data_url}" type="audio/mp3">
# # # #         Your browser does not support the audio element.
# # # #     </audio>
# # # #     <br>
# # # #     <button onclick="jumpToStart()">Jump to Start</button>
# # # #     <button onclick="playUntilOneMinute()">Play Until 01:00</button>
# # # #     <script>
# # # #     document.addEventListener('DOMContentLoaded', function() {{
# # # #              var audioPlayer = document.getElementById('audioPlayer');
# # # #
# # # #             window.jumpToStart = function() {{
# # # #                 audioPlayer.currentTime = 0;
# # # #                 audioPlayer.play();
# # # #             }};
# # # #
# # # #             window.playUntilOneMinute = function() {{
# # # #                 audioPlayer.play();
# # # #                 setTimeout(function() {{
# # # #                     if (audioPlayer.currentTime >= 60) {{
# # # #                         audioPlayer.pause();
# # # #                         audioPlayer.currentTime = 0;
# # # #                     }}
# # # #                 }}, (60 - audioPlayer.currentTime) * 1000);
# # # #             }};
# # # #        }});
# # # #     </script>
# # # # </div>
# # # #     """
# # # #
# # # #
# # # # #         const audioPlayer = document.getElementById('audioPlayer');
# # # # #
# # # # #         function jumpToStart() {{
# # # # #             audioPlayer.currentTime = 0;
# # # # #             audioPlayer.play();
# # # # #         }}
# # # # #
# # # # #         function playUntilOneMinute() {{
# # # # #             if (audioPlayer.currentTime >= 60) {{
# # # # #                 audioPlayer.pause();
# # # # #                 audioPlayer.currentTime = 0;
# # # # #             }} else {{
# # # # #                 audioPlayer.play();
# # # # #                 setTimeout(() => {{
# # # # #                     audioPlayer.pause();
# # # # #                     audioPlayer.currentTime = 0;
# # # # #                 }}, (60 - audioPlayer.currentTime) * 1000);
# # # # #             }}
# # # # #         }}
# # # # #     </script>
# # # # # </div>
# # # # # """
# # # # st.markdown(audio_html, unsafe_allow_html=True)
