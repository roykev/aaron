import os
import datetime
import numpy as np
import cv2
import moviepy.video as mpe
import time
from console_progressbar import ProgressBar
from moviepy.editor import *
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image, ImageDraw, ImageFont

#from moviepy.video.compositing.concatenate import concatenate_videoclips
# from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
# from moviepy.video.io.ffmpeg_tools import ffmpeg_merge_video_audio
# from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_audio
from moviepy.video.VideoClip import TextClip
import pandas as pd
def hhmmss_to_seconds(time_str):
    parts = list(map(int, time_str.split(":")))
    if len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = parts
    elif len(parts) == 2:  # MM:SS
        hours = 0
        minutes, seconds = parts
    else:
        raise ValueError(f"Invalid time format: {time_str}")
    return hours * 3600 + minutes * 60 + seconds

# Helper function to convert MM:SS to seconds
def mmss_to_seconds(time_str):
    minutes, seconds = map(int, time_str.split(":"))
    return minutes * 60 + seconds
def mp4_to_mp3(mp4_name,mp3_name):
    video = VideoFileClip(mp4_name)
    video.audio.write_audiofile(mp3_name)
def compress_video(input_path, output_path, target_size):
    # Load the video file
    start = time.time()

    clip = VideoFileClip(input_path)

    # Reduce resolution; you might want to adjust these values
    clip_resized = clip.resize(height=480)  # Example: resize to height of 480p

    # Calculate the target bitrate more aggressively
    target_bitrate = ((target_size * 1024 * 8) / clip_resized.duration) / 1000  # in kilobits per second

    # Write the compressed video
    clip_resized.write_videofile(output_path, bitrate=f"{int(target_bitrate)}k")


    end = time.time()
    print(f'Done compress. ({end - start:.3f}s)')



def create_hebrew_text_image(text, fontsize=50, color="white", size=(1440, 600)):
    """Creates an image with Hebrew text to maintain correct RTL rendering and returns as a NumPy array."""
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Change to a Hebrew-supporting font
    font = ImageFont.truetype(font_path, fontsize)

    img = Image.new("RGBA", size, (0, 0, 0, 0))  # Transparent background
    draw = ImageDraw.Draw(img)

    # Measure text size
    text_size = draw.textbbox((0, 0), text, font=font)
    text_width = text_size[2] - text_size[0]
    text_height = text_size[3] - text_size[1]

    # Center text in image
    text_position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
    draw.text(text_position, text, font=font, fill=color)

    return np.array(img)  # Convert to NumPy array




def add_images(video, before, after, out_video, dur = 3):

    # Load the video file
    video = mpe.VideoFileClip(video)

    # Load the image file
    image1 = mpe.ImageClip(before)
    image2 = mpe.ImageClip(after)

    # Set the duration of the image clip to dur second
    image1 = image1.set_duration(dur)
    # Set the duration of the image clip to dur second
    image2 = image2.set_duration(dur)
    # Combine the image clip and video clip
    final_clip =mpe.CompositeVideoClip([image1, video.set_start(dur)])

    video_duration = final_clip.duration

    final_clip =mpe.CompositeVideoClip([final_clip, image2.set_start(video_duration)])

    # Write the new video file
    final_clip.write_videofile(out_video)

def clip_file(in_file, out_file, t_start,t_end):
    video = VideoFileClip(in_file,verbose=False).subclip(t_start,t_end)
    #result = CompositeVideoClip([video]) #  video
    video.write_videofile(out_file,verbose=False,logger=None,audio_codec="aac",) # Many options...
    return video

def count_frames(video_path):
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total_frames



def tc2sec(tc):

    h, m, s = tc[:-4].split(':')
    sec = (int(datetime.timedelta(hours=int(h), minutes=int(m), seconds=int(s)).total_seconds()))
    return sec

# Function to break long text into multiple lines
def wrap_text(text, max_width=30):
    """Wrap text into multiple lines of a specified width."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 > max_width:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
        else:
            current_line.append(word)
            current_length += len(word) + 1

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)

def create_clips(df,movie_file, path,from_field="from", to_field="to", concat=False):
    extract_dir= os.path.join(path,"clips")
    movie_path = os.path.join(path,movie_file)
    clips = []
    for i,row in enumerate(df.iterrows()):
        clipfile = os.path.join(extract_dir,f"{i+1}.mp4")
        clip =clip_file(movie_path, clipfile, row[1][from_field], row[1][to_field])
        clips.append(clip)

    if concat:
        final = concatenate_videoclips(clips)
        final.write_videofile(os.path.join(extract_dir,"trailer.mp4"))
def make_trailer(df,clips_path,lesson_name):
    # Configuration
    logo = "media/Picture1.jpg"
   # lesson_name = "Intro to AI"  # Lesson name to display below the logo
    output = os.path.join(clips_path, "trailer.mp4")
    duration_slide = 4  # Duration for slides in seconds
    font ="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
   # font=None
  # Font for text slides
    font_size = 30  # Font size for text
    text_color = "black"
    background_color = "white"
    video_resolution = (800, 600)  # Default resolution of the video
    # Initialize fps and codec variables
    fps = None
    codec = "libmp3lame"
    descriptions = df["description"]


    # Create starting logo slide with lesson name
    logo_clip = ImageClip(logo, duration=duration_slide).resize(height=400).set_position("center")  # Resize and center logo
    lesson_name_text = TextClip(
        wrap_text(lesson_name),
        fontsize=30,
        color="white",
        size=(1440, None),
    ).set_position(("center", 800)).set_duration(duration_slide*1.5)  # Adjust position to below the logo
    start_slide = CompositeVideoClip([logo_clip, lesson_name_text], size=video_resolution).set_duration(duration_slide*1.5)

    intro = os.path.join(clips_path, "intro.mp4")
    start_slide.write_videofile(os.path.join(clips_path, "intro.mp4"),
                         fps=24,
                         codec="libx264",
                         audio_codec="aac",
                         audio_bitrate="192k")
    # Load the new audio
    mp3 = "media/intro.mp3"
    new_audio= AudioFileClip(mp3)

    # If the audio is longer/shorter than the video, you might want to set the duration
    new_audio = new_audio.set_duration(start_slide.duration)

    # Combine video with new audio
    start_with_music = start_slide.set_audio(new_audio)


    clips = [start_with_music]  # Start with the logo slide

    for i in range(1, len(descriptions) +1):
        description = wrap_text(descriptions[i-1])

        # Create opening slide with text
        opening_text = TextClip(
            f"Part {i}\n{description}",
            fontsize=font_size,
            color="white",
            #bg_color=background_color,
            size=(1920, 1080),
            font=font,
        ).set_duration(duration_slide)
        # Create the text image
        lesson_name_img = create_hebrew_text_image( f"{i}\n{description}")
        # Convert to ImageClip
        lesson_name_text = ImageClip(lesson_name_img).set_position(("center", 800)).set_duration(duration_slide )

        try:
            # Load the main video clip
            main_clip = VideoFileClip(os.path.join(clips_path,f"{i}.mp4"))
            # Set fps for consistency if not already set
            if fps is None:
                fps = main_clip.fps
            if main_clip.duration is None:
                print(f"Warning: Clip {i}.mp4 has no duration. Skipping this clip.")
                continue

            # Concatenate opening slide and clip
            part = concatenate_videoclips([lesson_name_text, main_clip], method="compose")
            clips.append(part)
            # Debug: Write intermediate part to verify
            part.write_videofile(os.path.join(clips_path,f"part_{i}.mp4"),
                                 fps=fps,
                                 codec="libx264",
                                 audio_codec="aac",
                                 audio_bitrate="192k"  )

        except Exception as e:
            print(f"Error loading clip {i}.mp4: {e}")
            continue

    # Create closing slide (same as starting slide without lesson name)
    closing_slide = ImageClip(logo, duration=duration_slide)
    clips.append(closing_slide)

    # Check for empty clips
    if len(clips) < 2:
        print("Error: No valid video clips to concatenate.")
        exit(1)

    # Concatenate all parts into the final video
    final_video = concatenate_videoclips(clips, method="compose")

    # Write the final video to a file
    final_video.write_videofile(output, fps=fps,
                                 codec="libx264",
                                 audio_codec="aac",
                                 audio_bitrate="192k"  )

    print(f"Final video created: {output}")
def override_audio(mp4, mp3,newmp4):
    # Load the video
    video = VideoFileClip(mp4)

    # Load the new audio
    new_audio = AudioFileClip(mp3)

    # If the audio is longer/shorter than the video, you might want to set the duration
    new_audio = new_audio.set_duration(video.duration)

    # Combine video with new audio
    final_video = video.set_audio(new_audio)

    # Write the result
    final_video.write_videofile(newmp4)

    # Close the files
    video.close()
    new_audio.close()
if __name__ == '__main__':
    dirpath = "/home/roy/FS/OneDriver1/WORK/ideas/aaron/DORON/democracy"
    dirpath = "/home/roy/FS/OneDriver1/WORK/ideas/Moments/kan11/tkuma/2/"

    df = pd.read_csv(os.path.join(dirpath,"extract/trailer4.csv"))
    movie_file = "video.mp4"
    extract_dir= os.path.join(dirpath,"clips1")
    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir)
    #create_clips(df,movie_file,dirpath)
    make_trailer(df,extract_dir)
    mp4 = os.path.join(dirpath,"clips/intro.mp4")
    mp3="media/intro.mp3"
    mp4new = os.path.join(dirpath,"clips/intro_.mp4")
    override_audio(mp4, mp3, mp4new)



