import os
import time

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
#import librosa
import tensorflow as tf
import torchaudio
import torchaudio.transforms as transforms
from pydub import AudioSegment
from scipy.io import wavfile
from scipy.signal import find_peaks
from console_progressbar import ProgressBar
from silance_detect import analyze_silence, merge_audio_and_silence
from utils.utils import execution_time
# Constants
FRAME_SIZE = 2048  # Window size for analysis
HOP_SIZE = 512  # Step size for moving window


BASE_SOUND_CLASSES = {
    "Speech": ["Speech", "Lecture", "Narration", "Explaining", "Discussion", "Q&A"],
    "Audience": ["Applause", "Laughter", "Coughing", "Whispering", "Chatter"],
    "Lecture Environment": ["Chalk Writing", "Whiteboard Marker", "Typing", "Page Turning", "Projector Fan"],
    "Objects": ["Pen Click", "Book Drop", "Glass Clink", "Microphone Feedback", "Chair Moving"],
    "Electronics": ["Keyboard Typing", "Mouse Click", "Phone Ringing", "Notification Sound", "Printer"],
    "Ambient": ["Air Conditioning", "Room Noise", "Distant Traffic"],
    "Music": ["Intro Music", "Outro Music", "Elevator Music", "Instrumental Background"],
}

LECTURE_SOUND_CLASSES = {
    "Speech": ["Speech", "Narration", "Conversation", "Lecture", "Discussion", "Q&A", "Explaining"],
    "Audience": ["Applause", "Laughter", "Coughing", "Whispering", "Murmuring", "Booing"],
    "Lecture Environment": ["Chalk Writing", "Whiteboard Marker", "Typing", "Page Turning", "Projector Fan", "Door Opening"],
    "Questions & Answers": ["Student Asking", "Teacher Answering", "Panel Discussion"],
    "Objects": ["Pen Click", "Book Drop", "Glass Clink", "Microphone Feedback", "Chair Moving"],
    "Electronics": ["Keyboard Typing", "Mouse Click", "Phone Ringing", "Notification Sound", "Printer"],
    "Ambient": ["Air Conditioning", "Room Noise", "Distant Traffic"],
    "Background Music": ["Intro Music", "Outro Music", "Elevator Music", "Instrumental Background"],
}

ALL_SOUND_CLASSES = {**BASE_SOUND_CLASSES, **LECTURE_SOUND_CLASSES}
@tf.function
def run_yamnet(model, segment):
    return model(segment)
device = '/CPU:0'
#tf.config.set_visible_devices([], 'GPU')  # Disables GPU usage

class LectureAudioAnalyzer:

    def __init__(self, audio_path):
        self.audio_path = audio_path
        self.mp3 = os.path.join(audio_path,"raw.mp3")
        self.sample_rate = None
        self.audio_data = None
        self.df = None
        self.yamnet_model = None  # Will load YAMNet for classification

    def load_yamnet_class_names(self):
        """Loads class names from the YAMNet model."""
        try:
            # ✅ Ensure the model has class_map_path()
            if not hasattr(self.yamnet_model, 'class_map_path'):
                print("⚠️ Error: YAMNet model does not have 'class_map_path()'.")
                return []

            class_map_path = self.yamnet_model.class_map_path().numpy().decode("utf-8")
            print(f"🔍 DEBUG: Class Map Path = {class_map_path}")  # ✅ Debugging output

            # ✅ Check if file exists
            if not os.path.exists(class_map_path):
                print(f"⚠️ Error: Class map file not found at {class_map_path}")
                return []

            # ✅ Read file safely
            self.class_names = []
            with open(class_map_path, "r", encoding="utf-8") as f:
                lines = f.readlines()  # Read all lines first
                self.class_names = [line.strip() for line in lines[1:] if line.strip()]  # ✅ Skip first row

            if not self.class_names:
                print(f"⚠️ Error: No class names found in {class_map_path}")
                return []

            print(f"✅ Loaded {len(self.class_names)} YAMNet class names.")
            return self.class_names

        except Exception as e:
            print(f"⚠️ Error loading YAMNet class names: {e}")
            return []  # ✅ Return empty list to prevent crashes



    def load_yamnet_model(self):
        """Loads the YAMNet model and forces it to use GPU if available."""
        print("Loading YAMNet model...")

        # Check if GPU is available and set execution mode
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            try:
                # Enable memory growth to avoid allocation issues
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                tf.config.set_visible_devices(gpus[0], 'GPU')
                print("✅ YAMNet is set to run on GPU.")
            except RuntimeError as e:
                print("⚠️ GPU Runtime Error:", e)

        # Load YAMNet model
        self.yamnet_model = tf.saved_model.load("/home/roy/FS/yamnet_model")
        self.class_names =self.load_yamnet_class_names()
        print("✅ YAMNet model loaded successfully.")

    def load_audio(self):
        """Loads an MP3 file, converts it to WAV, and reads audio data."""
        print("Loading and converting audio file...")
        audio = AudioSegment.from_mp3(self.mp3)
        wav_path = os.path.join(self.audio_path,"processed_audio.wav")
        audio.export(wav_path, format="wav")

        self.sample_rate, self.audio_data = wavfile.read(wav_path)

        # Convert stereo to mono if needed
        if len(self.audio_data.shape) > 1:
            self.audio_data = np.mean(self.audio_data, axis=1)

        # Normalize the audio
        self.audio_data = self.audio_data / np.max(np.abs(self.audio_data))
        print("Audio loaded successfully.")

    def classify_audio_segments(self):
        """Classifies long-duration audio efficiently with chunking, larger hop size, and event merging."""
        print("🔍 Classifying audio using YAMNet...")

        chunk_duration = 1800  # 30 minutes per chunk
        sample_rate = self.sample_rate
        hop_size = int(sample_rate * .25)  # Ensure each row is at least 1 sec

        chunk_size = chunk_duration * sample_rate  # Total samples per chunk
        total_samples = len(self.audio_data)
        num_chunks = int(np.ceil(total_samples / chunk_size))

        print(f"🔄 Splitting audio into {num_chunks} chunks ({chunk_duration // 60} min each).")

        if not hasattr(self, "chunk_files"):
            self.chunk_files = []

        prev_rms_energy = None
        sudden_change_threshold = 0.1

        for chunk_index in range(num_chunks):
            start_sample = chunk_index * chunk_size
            end_sample = min((chunk_index + 1) * chunk_size, total_samples)
            chunk_audio = self.audio_data[start_sample:end_sample]

            print(f"📌 Processing chunk {chunk_index + 1}/{num_chunks} [{start_sample} - {end_sample} samples]")

            output_rows = []
            prev_event_class = None
            prev_sub_class = None
            prev_timestamp = None
            merged_event = None  # Track merged event

            num_segments = int(np.floor(len(chunk_audio) / hop_size))

            for i in range(num_segments):
                try:
                    segment_start = i * hop_size
                    segment_end = segment_start + hop_size

                    if segment_end > len(chunk_audio):
                        break

                    segment = chunk_audio[segment_start:segment_end].astype(np.float32)
                    max_val = np.max(np.abs(segment))

                    if max_val > 0:
                        segment /= max_val
                    else:
                        segment.fill(0)

                    # ✅ Use GPU if available
                    with tf.device(device):
                        scores, embeddings, spectrogram = run_yamnet(self.yamnet_model, segment)

                    class_scores = np.mean(scores.numpy(), axis=0)
                    top_class_index = np.argmax(class_scores)

                    if top_class_index >= len(self.class_names):
                        print(f"⚠️ Warning: Invalid class index {top_class_index}. Skipping.")
                        event_class, sub_class = "Other", "General"
                    else:
                        detected_class = self.class_names[top_class_index].strip().lower()
                        event_class, sub_class = self.map_to_category(detected_class)

                    if event_class not in ALL_SOUND_CLASSES:
                        event_class = "Other"

                except Exception as e:
                    print(f"⚠️ Error processing segment {i}: {e}")
                    event_class, sub_class = "Unknown", "Unknown"

                # ✅ Time calculations
                timestamp = float(start_sample / sample_rate) + (i * hop_size / sample_rate)
                rms_energy = np.sqrt(np.mean(np.square(segment)))

                # ✅ Detect Sudden Change
                sudden_change = abs(rms_energy - (prev_rms_energy if prev_rms_energy is not None else rms_energy))
                sudden_change_flag = 1 if sudden_change > sudden_change_threshold else 0

                # ✅ Merge Consecutive Events of the Same Type
                if (
                        merged_event
                        and event_class == merged_event["event_class"]
                        and sub_class == merged_event["sub_class"]
                ):
                    merged_event["to_time"] = timestamp + (hop_size / sample_rate)
                    merged_event["rms_energy"] = (merged_event["rms_energy"] + rms_energy) / 2  # Average RMS
                    merged_event["sudden_change"] = max(merged_event["sudden_change"], sudden_change_flag)
                else:
                    if merged_event:
                        output_rows.append(merged_event)
                    merged_event = {
                        "from_time": timestamp,
                        "to_time": timestamp + (hop_size / sample_rate),
                        "rms_energy": rms_energy,
                        "sudden_change": sudden_change_flag,
                        "event_class": event_class,
                        "sub_class": sub_class
                    }

                # ✅ Update Previous Values for Next Iteration
                prev_timestamp = timestamp
                prev_event_class = event_class
                prev_sub_class = sub_class
                prev_rms_energy = rms_energy

            # ✅ Add last merged event
            if merged_event:
                output_rows.append(merged_event)

            # ✅ Save chunk results
            chunk_df = pd.DataFrame(output_rows)
            chunk_filename = f"audio_event_analysis_chunk_{chunk_index + 1}.csv"
            chunk_df.to_csv(chunk_filename, index=False, encoding="utf-8-sig")
            self.chunk_files.append(chunk_filename)
            print(f"✅ Chunk {chunk_index + 1} saved: {chunk_filename}")
    def merge_and_clean_files(self,output_csv = "audio_event_analysis_results.csv"):
        """Merges chunk files into a single CSV and deletes temporary files."""
        print("🔄 Merging all chunk files into final CSV...")

        all_data = []
        for file in self.chunk_files:
            chunk_df = pd.read_csv(file)
            all_data.append(chunk_df)
            os.remove(file)  # ✅ Delete temp file after merging

        final_df = pd.concat(all_data, ignore_index=True)
        output_path = os.path.join(self.audio_path, output_csv)
        final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"✅ Final results saved: {output_path}")

    def map_to_category(self, class_index):
        """Maps YAMNet class index to a relevant wedding sound category."""
        try:
            if isinstance(class_index, str):
                    class_name = class_index.split(",")[2].lower().strip()  # Normalize to lowercase
#                    class_name = self.class_names[class_index].lower().strip()  # Normalize to lowercase
                    class_index = int(class_index.split(",")[0])  # ✅ Extract first part and convert to int
            # ✅ Ensure class index is within bounds
            if class_index < 0 or class_index >= len(self.class_names):
                print(f"⚠️ Error: class_index {class_index} is out of range (0-{len(self.class_names) - 1})")
                return "Other", "General"

                   # ✅ Check if the class belongs to BASE_SOUND_CLASSES
            for category, keywords in ALL_SOUND_CLASSES.items():
                if class_name in (name.lower() for name in keywords):
                    return category, class_name# ✅ Found match in BASE_SOUND_CLASSES
            return "Other", class_name  # ✅ Default to "Other" if no match is found

        except Exception as e:
            print(f"⚠️ Error mapping class_index {class_index}: {e}")
            return "Other", "General"  # Fallback



    def save_results(self, output_csv="audio_event_analysis_results.csv"):
        """Saves the results to a CSV file."""
        self.merge_and_clean_files()  # ✅ Call function to merge and delete temp files
        # print(f"Saving results to {output_csv}...")
        # output_path = os.path.join(self.audio_path, output_csv)
        # self.df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print("Results saved successfully.")

    def plot_results(self):
        """Generates a plot showing loudness levels and detected events."""
        print("Generating visualization...")
        plt.figure(figsize=(12, 6))

        # Plot RMS energy with peaks
        plt.plot(self.df["rms_energy"], label="RMS Energy (Loudness)")
        plt.scatter(self.df.index[self.df["sudden_change"] == 1],
                    self.df["rms_energy"][self.df["sudden_change"] == 1],
                    color='red', label="Detected Peaks")

        plt.xlabel("Time Frames")
        plt.ylabel("Loudness Level")
        plt.title("Music Peaks, Speech, and Crowd Events")
        plt.legend()
        plt.show()
        print("Visualization complete.")

    def finalize (self):
        wav_path = os.path.join(self.audio_path,"processed_audio.wav")
        os.remove(wav_path)

def analyze_energy_events(audio_path):
    """Main function to run the audio event analysis."""
    start_time = time.time()  # Capture start time
    analyzer = LectureAudioAnalyzer(audio_path)
    analyzer.load_audio()
    load_audio_time = time.time()
    print(f"load_audio: {execution_time(load_audio_time, start_time)}")
    analyzer.load_yamnet_model()
    load_yamnet_model_time = time.time()
    print(f"load_yamnet_model: {execution_time(load_audio_time, load_yamnet_model_time )}")
    analyzer.classify_audio_segments()
    print(f"classify_audio_segments: { execution_time(load_yamnet_model_time, time.time() )}")
    analyzer.save_results()
    print(f"total time: {execution_time(start_time, time.time())}")
    analyzer.finalize()
def main(audio_path):
    #analyze_energy_events(audio_path)
    analyze_silence(audio_path)
    event_analysis_file = os.path.join(audio_path, "audio_event_analysis_results.csv")
    optimized_audio_analysis_file = os.path.join(audio_path, "optimized_audio_analysis.csv")
    silence_file = os.path.join(audio_path, "silence.csv")

# Usage Example
    merged_df = merge_audio_and_silence(silence_file, event_analysis_file)

    merged_df.to_csv(optimized_audio_analysis_file, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    audio_path = "/home/roy/FS/OneDrive/WORK/ideas/aaron/philosophy_of_education"
    audio_path="/home/roy/FS/OneDriver1/WORK/ideas/aaron/azrieli/intro to computational biology"
    audio_path =                 "/home/roy/FS/OneDriver1/WORK/ideas/aaron/Miller/AI for business/2024/6/2"

    main(audio_path)
