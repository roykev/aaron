import math
import io
import os
import time
import numpy as np
import pandas as pd
from faster_whisper import WhisperModel
import torch
from pydub import AudioSegment
#from diarization import Diarizer
from console_progressbar import ProgressBar
m_size = "medium"
#m_size = "tiny"
m_size = "large"



def init_cuda():
     torch.cuda.empty_cache()
    # print(f"Available GPU memory: {torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)}")

def split_audio(
    audio_path: str,
    chunk_duration_minutes: float = 0.5,
) :
    """Splits an audio file into chunks of the specified duration, returning each chunk with its length.

    Args:
        audio_path (str): Path to the input MP3 file.
        chunk_duration_minutes (float): Target duration for each audio chunk in minutes.

    Returns:
        List[Tuple[io.BytesIO, float]]: List of tuples, each containing an audio chunk as an io.BytesIO object and its length in seconds.
    """
    print(f"Splitting audio into {chunk_duration_minutes}-minute chunks...")
    audio = AudioSegment.from_mp3(audio_path)
    chunk_duration_milliseconds = int(chunk_duration_minutes * 60 * 1000)

    chunks = []
    parts = range(0, len(audio), chunk_duration_milliseconds)
    for i in parts:
        chunk = audio[i : i + chunk_duration_milliseconds]
        chunks.append(
            (io.BytesIO(chunk.export(format="mp3").read()), len(chunk) / 1000.0)
        )

    return chunks
class Transcriber:
    def __init__(self, file_name,m_size):
        self.file_name=file_name
        self.transcribe_df = pd.DataFrame(columns=["from", "to", "text"])
        self.m_size =m_size

    def init_model(self,chunk_dur =30):
        self.compute_chunk_len( chunk_dur)
        # model = WhisperModel("sivan22/faster-whisper-ivrit-ai-whisper-large-v2-tuned",compute_type="int8")#"int8")#, device='cpu')
        self.model = WhisperModel(self.m_size, device="cuda", compute_type="int8")

    def compute_chunk_len(self, sec):
        # Load the MP3 file
        self.audio = AudioSegment.from_mp3(self.file_name)
        # Get the total duration of the audio in milliseconds
        self.total_duration = len(self.audio)
        # Calculate the number of chunks
        self.chunk_size = sec * 1000  # convert seconds to milliseconds
        self.num_chunks = math.ceil(self.total_duration / self.chunk_size)


    def transcribe(self):
        chunk_size=self.chunk_size
        pb = ProgressBar(total=self.num_chunks, prefix='', suffix='', decimals=2, length=50, fill='|', zfill='-')
        for i in np.arange(self.num_chunks):
            # Define start and end time for each chunk
            init_cuda()
            start_time = i * chunk_size
            end_time = min(start_time + chunk_size, self.total_duration)
            # Extract the chunk
            chunk = self.audio[start_time:end_time]
            # Export the chunk as a new MP3 file
            chunk.export(tmp_name, format="mp3")
            segments, info = self.model.transcribe(tmp_name, beam_size=5, language="he")

            for segment in segments:
                row = [int((start_time / 1000) + segment.start), int((start_time / 1000) + segment.end),  segment.text]
                self.transcribe_df.loc[len(self.transcribe_df)]=row
            pb.print_progress_bar(i)
        os.remove(tmp_name)



def merge_diarization_transcript(df_transcript, diarizer):

    # Create an empty DataFrame
    df_columns = ["from", "to", "text", "speaker"]
    synchronized_df = pd.DataFrame(columns=df_columns)
    labels = diarizer.results
    # Calculate frame duration
    audio_duration = diarizer.total_duration
    num_frames = len(labels)
    frame_duration = diarizer.frame_duration/1000

    # Synchronize speaker labels with transcription segments
    for row in df_transcript.iterrows():
        segment = row[1]

        start_frame = int(segment["from"] / frame_duration)
        end_frame = int(segment["to"] / frame_duration)
        # Ensure end_frame is within the bounds
        if end_frame > num_frames:
            end_frame = num_frames

        # Extract speaker labels for the segment
        segment_labels = labels[start_frame:end_frame]

        # Get the most frequent speaker label in this segment
        if len(segment_labels) > 0:
            most_common_label = np.bincount(segment_labels).argmax()
        else:
            most_common_label = -1  # Default value if no labels
        row = [segment["from"], segment["to"],segment['text'],most_common_label]
        # Append results to the DataFrame
        synchronized_df.loc[len(synchronized_df)]=row


    return synchronized_df



if __name__ == '__main__':
    t0 = time.time()
    dir_name ="/home/roy/Downloads/"
    dir_name = "/home/roy/OneDrive/WORK/ideas/aaron/philosophy_of_education"
    dir_name ="/home/roy/FS/OneDrive/WORK/ideas/aaron/hadasa/maoz/demo/"
    file_name = os.path.join(dir_name,"raw.mp3")
    #file_name = os.path.join(dir_name,"lesson1-0.mp3")
    tmp_name= os.path.join(dir_name,"tmp_output.mp3")
    outfile = os.path.join(dir_name,f"{m_size}_out.txt")


    with torch.no_grad():

        transcriber=Transcriber(file_name,m_size)
        transcriber.init_model()
        total_duration=transcriber.total_duration
       # diarizer = Diarizer(file_name,total_duration,10)
     #   diarizer.diarize()
        t1 = time.time()
        print(f'Diarization of {total_duration / 1000}. Done in ({t1 - t0:.3f}s)')
        transcriber.transcribe()
        df = transcriber.transcribe_df
        trans_name = os.path.join(dir_name, f"{m_size}_transcript.csv")

        df.to_csv(trans_name, index=False)
       # print(df)
        t2 = time.time()
        print(f'Transcribe of {total_duration / 1000} with {m_size}. Done in ({t2 - t1:.3f}s)')
        # Optionally, save the DataFrame to a CSV file
      #  synchronized_df= merge_diarization_transcript(df, diarizer)
      #  mrg_name = os.path.join(dir_name, f"{m_size}_synchronized_results.csv")
       # synchronized_df.to_csv(mrg_name, index=False)
        if False:
            with open(outfile, "w") as txt_file:
                for i in range(num_chunks):
                    # Define start and end time for each chunk
                    init_cuda()
                    start_time = i * chunk_size
                    end_time = min(start_time + chunk_size, total_duration)
                    # Extract the chunk
                    chunk = audio[start_time:end_time]
                    # Export the chunk as a new MP3 file
                    chunk.export(tmp_name, format="mp3")
                    print(tmp_name)
                    segments, info = model.transcribe(tmp_name ,beam_size=5,language="he")

                    for segment in segments:
                        txt_file.write("[{:.1f},{:.1f}] {}\n".format((start_time/1000)+segment.start, (start_time/1000)+segment.end, segment.text))
                    ##    print("[%.2fs -> %.2fs] %s" % ((start_time/1000)+segment.start, (start_time/1000)+segment.end, segment.text))

    t3 = time.time()
    print(f'Total work of {total_duration/1000} with {m_size}. Done in ({t3 - t0:.3f}s)')

