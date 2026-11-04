import os
import numpy as np
import pandas as pd
import torch
from pyannote.audio import Pipeline

PIPELINE_NAME = "pyannote/speaker-diarization-3.1"
FRAME_MS = 100  # resolution of the frame-label array kept for merge_diarization_transcript


def _hf_token():
    token = os.environ.get("HF_TOKEN")
    if not token:
        try:
            from utils.utils import source_key
            source_key("HF_TOKEN")
            token = os.environ.get("HF_TOKEN")
        except Exception:
            pass
    return token


class Diarizer:
    """Speaker diarization with pyannote.audio 3.4 (speaker-diarization-3.1 pipeline).

    Legacy API kept for transcribe_faster_w.py. New code: audio/transcription (routed ASR + community-1 diarization).

    num_speakers: exact count if known; otherwise leave None and optionally bound with min/max_speakers.
    total_duration is in milliseconds (as returned by pydub / Transcriber).
    """

    def __init__(self, filename, total_duration, num_speakers=None, min_speakers=None, max_speakers=None):
        self.total_duration = total_duration
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.filename = filename
        self.pipeline = None

    def init_model(self):
        self.pipeline = Pipeline.from_pretrained(PIPELINE_NAME, use_auth_token=_hf_token())
        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

    def diarize(self):
        if self.pipeline is None:
            self.init_model()
        kwargs = {k: v for k, v in (("num_speakers", self.num_speakers),
                                    ("min_speakers", self.min_speakers),
                                    ("max_speakers", self.max_speakers)) if v is not None}
        diarization, self.speaker_embeddings = self.pipeline(self.filename, return_embeddings=True, **kwargs)

        rows = [(turn.start, turn.end, speaker)
                for turn, _, speaker in diarization.itertracks(yield_label=True)]
        self.segments = pd.DataFrame(rows, columns=["from", "to", "speaker"])

        # frame-level int labels (-1 = no speech), kept for merge_diarization_transcript
        self.speaker_labels = sorted(self.segments["speaker"].unique())
        label_id = {s: i for i, s in enumerate(self.speaker_labels)}
        results = np.full(max(1, int(np.ceil(self.total_duration / FRAME_MS))), -1, dtype=int)
        for start, end, speaker in rows:
            results[int(start * 1000 / FRAME_MS):int(np.ceil(end * 1000 / FRAME_MS))] = label_id[speaker]
        self.results = results
        self.frame_duration = FRAME_MS
        print("{} segments, {} speakers".format(len(rows), len(self.speaker_labels)))
        return self.segments

    def assign_speakers(self, df_transcript):
        """Return a copy of df_transcript ('from','to' in seconds) with a 'speaker' column, by max overlap."""
        seg = self.segments
        speakers = []
        for start, end in zip(df_transcript["from"], df_transcript["to"]):
            overlap = (np.minimum(seg["to"], end) - np.maximum(seg["from"], start)).clip(lower=0)
            per_speaker = overlap.groupby(seg["speaker"]).sum()
            speakers.append(per_speaker.idxmax() if per_speaker.max() > 0 else None)
        out = df_transcript.copy()
        out["speaker"] = speakers
        return out
