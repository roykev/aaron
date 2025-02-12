import os
from pydub import AudioSegment
from pyAudioAnalysis import audioSegmentation as aS


class Diarizer:
    def __init__(self,filename,total_duration, num_speakers):
        self.total_duration=total_duration
        self.num_speakers=num_speakers
        self.filename=filename


    def diarize(self):
        # Perform diarization
        file_path=self.filename
        audio = AudioSegment.from_mp3(file_path)
        wav_file=file_path.replace("mp3","wav")
        print(wav_file)
        audio.export(wav_file, format="wav")#save tem
        results  = aS.speaker_diarization(wav_file,self.num_speakers)
        self.results=results[0]
        self.frame_duration =  self.total_duration / len(self.results)
        # for segment in segments:
        #     print(f"Speaker {segment['speaker']}: {segment['start']} to {segment['end']}")
        print("{}, {}".format(len(self.results), max(self.results)))
        os.remove(wav_file)
