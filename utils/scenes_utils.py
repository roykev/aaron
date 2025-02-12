import os

import torch

os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

import numpy as np
import webvtt
import cv2
import pandas as pd
from scenedetect import open_video, SceneManager, AdaptiveDetector
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from summarizer import ScenesSummarizer


def find_scenes(video_path,min_scene_len=200):
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(
        AdaptiveDetector(min_scene_len=min_scene_len))


    # Detect all scenes in video from current position to end.
    scene_manager.detect_scenes(video,show_progress=True)
    # `get_scene_list` returns a list of start/end timecode pairs
    # for each scene that was found.
    list = scene_manager.get_scene_list()

    df = pd.DataFrame(columns=["start", "start_tc", "end", "end_tc"])
    for l in iter(list):
        df.loc[len(df)] = [l[0].frame_num, l[0].get_timecode(), l[1].frame_num, l[1].get_timecode()]
    return df

def gen_video_snapshots(videopath,outpath):
    df = find_scenes(videopath)
    #df_file="/media/roy/da11afec-c70f-4d61-b351-a1a7273920ef/OneDriver/WORK/ideas/aaron/Miller/AI for business/2024/2/1/extract/scenes.csv"
    #df = pd.read_csv(df_file)
    # Path to save the snapshot
    if not os.path.exists(outpath):
        os.makedirs(outpath)
    # Open the video file
    cap = cv2.VideoCapture(videopath)

    # Check if the video file is opened successfully
    if not cap.isOpened():
        print("Error: Could not open the video.")
        exit()

    for i, row in enumerate(df.iterrows()):
        row=row[1]
        frame_number = int((row["start"]+row["end"])/2)

        # Set the frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # Read the frame
        ret, frame = cap.read()

        if ret:
            output_snapshot_path=os.path.join(outpath,f'{i}.jpg')
        # Save the frame as an image file
            cv2.imwrite(output_snapshot_path, frame)
            print(f"Snapshot saved as {output_snapshot_path}")
        else:
            print("Error: Could not read the frame.")

    # Release the video capture object
    cap.release()
    return (df)


# Function to convert timecode to seconds
def timecode_to_seconds(timecode):
    h, m, s = map(float, timecode.replace(',', '.').split(':'))
    return h * 3600 + m * 60 + s


# Function to match text to scenes
def match_text(row):
    scene_text = vtt_df[
        (vtt_df["start_sec"] < row["to_sec"]) &
        (vtt_df["end_sec"] > row["from_sec"])
    ]["text"].str.cat(sep=" ")  # Concatenate overlapping texts
    return scene_text

def check():
    model_name = "sshleifer/distilbart-cnn-12-6"


    os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # Forces synchronous CUDA execution
    print("CUDA_LAUNCH_BLOCKING set to:", os.environ["CUDA_LAUNCH_BLOCKING"])

    # 2. Check CUDA availability and GPU information
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("CUDA is available. Using device:", torch.cuda.get_device_name(0))
    else:
        device = torch.device("cpu")
        print("CUDA is not available. Using CPU.")

    # 3. Load Pretrained Model and Tokenizer
    #model_name = "facebook/bart-large-cnn"  # Change to a smaller model if needed, e.g., "sshleifer/distilbart-cnn-12-6"
    print("Loading model and tokenizer...")

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Load model
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)

    # Alternatively, use a pipeline for ease
   # summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=0 if torch.cuda.is_available() else -1)

    # 4. Example text for testing summarization
    test_text = \
    "But what we know in reality, and I think this is like one of the important slides that I want to convey, is that the reality is not that, let's say, happy as what we see in the news or like in the Ynet scientific. The reality is quite, let's say, embarrassing. It's that the vast majority of AI projects fail, and when I'm talking about numbers, you see that the numbers of the failure rate is huge, and it's constant along the time, and stable across industries, stable across geographies, and different companies, small or big, and the numbers are shocking. So, and it's not that I want to frighten anyone, but one thing that I think that is important for each one of us to understand and to address is whether you're a professional or manager or stakeholder in the environment of AI, you should know these numbers because you should know that the odds are against us. We should know what we are getting into it, and if there are not too many success stories in your organization, it's a challenge. It's a challenge that we want to address, and the industry wants to address, and it's a fact, an embarrassing fact, but this is the reality. When you go out of this building, this is what you will find outside. I hope so. This is what I get when, you know, plenty of projects and money, but what we see is the numbers are not falling. There are new technologies. I'll try to explain. Okay, so it's a good question, and there are so much research that was done about, you know, to understand what the root causes, why the"
    # Ensure the input text is within the model's maximum input length
    max_input_length = tokenizer.model_max_length
    test_text = test_text[:max_input_length]

    # Tokenize the input
    inputs = tokenizer(
        test_text,
        return_tensors="pt",
        max_length=max_input_length,
        truncation=True,
        padding=True
    ).to(device)

    print("Tokenized input shape:", inputs["input_ids"].shape)

    # 5. Perform Summarization
    try:
        with torch.no_grad():  # Disable gradients for inference
            summary_ids = model.generate(
                inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_length=60,  # Adjust for desired summary length
                min_length=20,
                length_penalty=2.0,
                num_beams=4,
                no_repeat_ngram_size=2,
                early_stopping=True
            )

            # Decode the generated summary
            summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            print("\nOriginal Text:\n", test_text)
            print("\nGenerated Summary:\n", summary)

    except RuntimeError as e:
        print("\nCUDA Runtime Error:", e)
        print("Consider debugging by setting CUDA_LAUNCH_BLOCKING=1.")

if __name__ == '__main__':
    dirpath = "/home/roy/FS/OneDriver1/WORK/ideas/aaron/azrieli/intro to computational biology"
    video_path=os.path.join(dirpath,"video.mp4")
# 1 fnd scenes
    rerun = False
    df_file = os.path.join(dirpath, "scenes.csv")
    if rerun:
        scenes_df = find_scenes(video_path,200)
        scenes_df.to_csv(df_file,index=False)
    else:
        scenes_df = pd.read_csv(df_file)

    out_file=os.path.join(dirpath, "out.csv")
    num_scenes=len(scenes_df)
    vtt_file = os.path.join(dirpath,"vtt.vtt")

    # Load your VTT file
    vtt_data = []

    # Parse VTT and store the timecodes and text
    for caption in webvtt.read(vtt_file):
        vtt_data.append({
            "start": caption.start,
            "end": caption.end,
            "text": caption.text
        })

    # Convert VTT data to a dataframe
    vtt_df = pd.DataFrame(vtt_data)

    # Convert timecodes in the VTT dataframe to seconds
    vtt_df["start_sec"] = vtt_df["start"].apply(timecode_to_seconds)
    vtt_df["end_sec"] = vtt_df["end"].apply(timecode_to_seconds)

#
#
    # Convert timecodes in scenes_df to seconds
    scenes_df["from_sec"] = scenes_df["start_tc"].apply(timecode_to_seconds)
    scenes_df["to_sec"] = scenes_df["end_tc"].apply(timecode_to_seconds)
    # Add text column to scenes dataframe
    scenes_df["text"] = scenes_df.apply(match_text, axis=1)
    summarizer =ScenesSummarizer(model_name='g')
    # 6. Apply Summarization or Copy to Each Row
    scenes_df["summary"] = scenes_df["text"].apply(summarizer.summarize_or_copy)
    # 7. Display the Results
    print(scenes_df.summary)
    scenes_df.to_csv(out_file,index=False)
