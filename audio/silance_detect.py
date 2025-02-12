import os
from collections import Counter
from datetime import datetime
import pandas as pd
from pydub import AudioSegment,silence
from console_progressbar import ProgressBar

import webrtcvad
import wave
import numpy as np
import pandas as pd



def detect_silence_webrtcvad(audio_file, frame_duration=30, vad_mode=0, rms_threshold=0.01, min_silence_duration=1.0):
    """
    Detects silence and noise segments using WebRTC VAD with improved sensitivity.

    Parameters:
        - audio_file (str): Path to WAV file (16-bit PCM, mono, 16kHz).
        - frame_duration (int): Frame duration (10, 20, or 30 ms).
        - vad_mode (int): Sensitivity (0 = Least aggressive, 3 = Most aggressive).
        - rms_threshold (float): If RMS energy is below this, mark as Silence.
        - min_silence_duration (float): Ignore silence shorter than this (seconds).

    Returns:
        - DataFrame with ["from", "to", "state"]
    """

    assert frame_duration in [10, 20, 30], "❌ frame_duration must be 10, 20, or 30 ms."
    vad = webrtcvad.Vad(vad_mode)

    with wave.open(audio_file, "rb") as wf:
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()

        assert sample_rate in [8000, 16000, 32000, 48000], "❌ Invalid sample rate! Must be 8kHz, 16kHz, 32kHz, or 48kHz."
        assert num_channels == 1, "❌ Audio must be mono (1 channel)."
        assert sample_width == 2, "❌ Audio must be 16-bit PCM WAV."

        frame_size = int(sample_rate * (frame_duration / 1000))  # Samples per frame
        frame_bytes = frame_size * sample_width  # Bytes per frame

        timestamps, states = [], []
        start_time = 0.0

        while True:
            frame = wf.readframes(frame_size)
            if len(frame) < frame_bytes:
                break  # End of file

            # ✅ Compute RMS Energy (for quiet noise detection)
            samples = np.frombuffer(frame, dtype=np.int16)
            rms_energy = np.sqrt(np.mean(samples ** 2)) / 32768.0  # Normalize to [0,1]

            # ✅ If quiet noise, classify as Silence
            try:
                is_speech = vad.is_speech(frame, sample_rate)
                state = "Noise" if is_speech else "Silence"

                if rms_energy < rms_threshold:
                    state = "Silence"  # Override for quiet noise
            except webrtcvad.Error as e:
                print(f"⚠️ WebRTC VAD Error: {e}")
                state = "Error"

            timestamps.append(start_time)
            states.append(state)
            start_time += frame_duration / 1000  # Convert ms to seconds

    # ✅ Convert to DataFrame
    df = pd.DataFrame({"from": timestamps, "to": timestamps[1:] + [timestamps[-1] + frame_duration / 1000], "state": states})

    # ✅ Merge consecutive rows with the same state
    merged_segments = []
    prev_row = None

    for _, row in df.iterrows():
        if prev_row is None:
            prev_row = row
        else:
            if row["state"] == prev_row["state"]:
                prev_row["to"] = row["to"]  # Extend previous row
            else:
                # ✅ Ignore short silence (< min_silence_duration)
                if prev_row["state"] == "Silence" and (prev_row["to"] - prev_row["from"] < min_silence_duration):
                    prev_row["state"] = "Noise"  # Merge with noise
                merged_segments.append(prev_row)
                prev_row = row

    if prev_row is not None:
        merged_segments.append(prev_row)

    final_df = pd.DataFrame(merged_segments)
    return final_df




def convert_mp3_to_wav(mp3_file, wav_file):
    """Convert MP3 to WAV (16-bit PCM, mono) for WebRTC VAD."""
    audio = AudioSegment.from_mp3(mp3_file)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)  # Convert to mono, 16-bit PCM
    audio.export(wav_file, format="wav")
    print(f"✅ Converted {mp3_file} to {wav_file}")

def detect_silence(audio_file, silence_threshold=-50, min_silence_len=1000):
    # Create an AudioSegment instance from an MP3 file
    audio = AudioSegment.from_file(audio_file, "mp3")
#audio = AudioSegment.from_mp3("input.mp3")
    df =pd.DataFrame(columns=["from","to"])

    # Detect silence (silence_threshold in dBFS, min_silence_len in milliseconds)
    silent_ranges = silence.detect_silence(audio, silence_thresh= silence_threshold, min_silence_len=min_silence_len)
    pb = ProgressBar(total=len(silent_ranges), prefix='', suffix='', decimals=2, length=50, fill='|', zfill='-')
    for range in silent_ranges:
        row = [range[0]/1000, range[1]/1000]
        df.loc[len(df)]= row
        pb.print_progress_bar(len(df))
        #print("{}--{}".format(datetime.fromtimestamp(range[0]/1000.0),datetime.fromtimestamp(range[1]/1000.0)))
    return df


import pandas as pd


def clean_silence_detection(df):
    """
    Cleans and merges a silence detection DataFrame.

    ✅ Merges consecutive rows with the same state.
    ✅ Ensures that "from" of each row matches "to" of the previous row.

    Parameters:
        df (pd.DataFrame): DataFrame with columns ["from", "to", "state"]

    Returns:
        pd.DataFrame: Cleaned DataFrame
    """

    # ✅ Sort values just in case
    df = df.sort_values(by=["from"]).reset_index(drop=True)

    # ✅ Initialize the merged output
    merged_segments = []
    prev_from, prev_to, prev_state = df.iloc[0]["from"], df.iloc[0]["to"], df.iloc[0]["state"]

    for i in range(1, len(df)):
        curr_from, curr_to, curr_state = df.iloc[i]["from"], df.iloc[i]["to"], df.iloc[i]["state"]

        # ✅ If there's a gap, ensure continuity
        if curr_from > prev_to:
            prev_to = curr_from  # Fix the gap

        # ✅ If the same state, merge
        if curr_state == prev_state:
            prev_to = curr_to  # Expand range
        else:
            merged_segments.append({"from": prev_from, "to": prev_to, "state": prev_state})
            prev_from, prev_to, prev_state = curr_from, curr_to, curr_state

    # ✅ Add the last segment
    merged_segments.append({"from": prev_from, "to": prev_to, "state": prev_state})

    # ✅ Convert to DataFrame & Apply .3f Precision
    final_df = pd.DataFrame(merged_segments)
    final_df["from"] = final_df["from"].apply(lambda x: f"{x:.3f}")
    final_df["to"] = final_df["to"].apply(lambda x: f"{x:.3f}")

    return final_df




def merge_audio_and_silence(silence_file, events_file):
    """
    Merges silence detection data with event classification data.

    ✅ Keeps silence rows as "Silence" in event_class.
    ✅ Breaks noise rows into correct event_class based on event time intervals.
    ✅ Merges consecutive segments with the same event_class.
    ✅ Ensures correct time continuity.

    Parameters:
        silence_df (pd.DataFrame): Silence detection DataFrame with columns ["from", "to", "state"]
        events_df (pd.DataFrame): Audio event classification DataFrame with columns
                                  ["from_time", "to_time", "rms_energy", "sudden_change", "event_class", "sub_class"]

    Returns:
        pd.DataFrame: Merged DataFrame with improved segmentation
    """
    silence_df = pd.read_csv(silence_file)
    events_df = pd.read_csv(events_file)
    merged_data = []

    for _, row in silence_df.iterrows():
        s_from, s_to, state = row["from"], row["to"], row["state"]

        if state == "Silence":
            # ✅ Keep silence as a separate row
            merged_data.append({
                "from_time": s_from,
                "to_time": s_to,
                "rms_energy": np.nan,
                "sudden_change": 0,
                "event_class": "Silence",
                "sub_class": "Silent"
            })
            continue

        # If state is Noise, find matching event rows
        matched_events = events_df[
            (events_df["from_time"] < s_to) & (events_df["to_time"] > s_from)
            ]

        if not matched_events.empty:
            for _, event in matched_events.iterrows():
                e_from, e_to = max(s_from, event["from_time"]), min(s_to, event["to_time"])

                if e_from < e_to:  # Ensure valid range
                    merged_data.append({
                        "from_time": e_from,
                        "to_time": e_to,
                        "rms_energy": event["rms_energy"],
                        "sudden_change": event["sudden_change"],
                        "event_class": event["event_class"],
                        "sub_class": event["sub_class"]
                    })

        else:
            # If no matching event, keep it as unknown noise
            merged_data.append({
                "from_time": s_from,
                "to_time": s_to,
                "rms_energy": np.nan,
                "sudden_change": 0,
                "event_class": "Unknown",
                "sub_class": "Noise"
            })

    # Convert merged list to DataFrame
    merged_df = pd.DataFrame(merged_data)

    # 🔄 **Merge consecutive rows with the same event_class**
    final_data = []
    prev_row = None

    for _, row in merged_df.iterrows():
        if prev_row is not None and row["event_class"] == prev_row["event_class"]:
            # ✅ Merge same event_class rows
            prev_row["to_time"] = row["to_time"]
            prev_row["rms_energy"] = np.nanmean([prev_row["rms_energy"], row["rms_energy"]])
            prev_row["sudden_change"] = max(prev_row["sudden_change"], row["sudden_change"])
            prev_row["sub_class"] = Counter([prev_row["sub_class"], row["sub_class"]]).most_common(1)[0][0]
        else:
            # ✅ Save the previous row before starting a new group
            if prev_row is not None:
                final_data.append(prev_row)
            prev_row = row.to_dict()  # Convert current row to dict
    # Append last row
    if prev_row is not None:
        final_data.append(prev_row)

    # Convert to DataFrame
    final_df = pd.DataFrame(final_data)

    # **Format output**
    final_df["from_time"] = final_df["from_time"].apply(lambda x: f"{x:.3f}")
    final_df["to_time"] = final_df["to_time"].apply(lambda x: f"{x:.3f}")
    final_df["rms_energy"] = final_df["rms_energy"].apply(lambda x: f"{x:.3f}" if not pd.isna(x) else "")

    return final_df

def analyze_silence(audio_path,a_file ="raw.mp3"):
    audio_file = os.path.join(audio_path, a_file)
    silence_file = os.path.join(audio_path, "silence.csv")
    audio_wav = os.path.join(audio_path, "audio.wav")
    convert_mp3_to_wav(audio_file, audio_wav)
    silence_df = detect_silence_webrtcvad(audio_wav, frame_duration=30, vad_mode=0, rms_threshold=0.02,
                                              min_silence_duration=1.0)

    # ✅ Load Data & Run Cleaning
    cleaned_df = clean_silence_detection(silence_df)
    os.remove(audio_wav)
    # Save to CSV
    cleaned_df.to_csv(silence_file, index=False, encoding="utf-8-sig")

#
if __name__ == '__main__':

# Apply a fade-in effect (2 seconds)
#faded_audio = audio.fade_in(2000)
    audio_path = "/home/roy/FS/OneDrive/WORK/ideas/Moments/shani_dolev"
    audio_file=os.path.join(audio_path,"raw.mp3")
    silence_file = os.path.join(audio_path,"silence.csv")
    if False:
        audio_wav=os.path.join(audio_path,"audio.wav")
        convert_mp3_to_wav(audio_file, audio_wav)
        silence_df = detect_silence_webrtcvad(audio_wav,frame_duration=30, vad_mode=0, rms_threshold=0.02,
                                              min_silence_duration=1.0)

        # ✅ Load Data & Run Cleaning
        cleaned_df = clean_silence_detection(silence_df)
        os.remove(audio_wav)
        # Save to CSV
        cleaned_df.to_csv(silence_file, index=False, encoding="utf-8-sig")
        # df = detect_silence(audio_file,silence_threshold=-16,min_silence_len=1000)
        # df.to_csv(silence_file,index=False)

    if False:
        event_analysis_file = os.path.join(audio_path,"audio_event_analysis_results.csv")
        optimized_audio_analysis_file= os.path.join(audio_path,"optimized_audio_analysis.csv")
    # Usage Example
        merged_df =merge_audio_and_silence(silence_file,event_analysis_file)

        merged_df.to_csv(optimized_audio_analysis_file, index=False, encoding="utf-8-sig")




