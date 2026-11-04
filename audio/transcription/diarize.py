"""Speaker diarization with pyannote (3.x or 4.x, whichever is installed).

pyannote 4.x -> pyannote/speaker-diarization-community-1, using its *exclusive* output (one speaker at a
time), which is the one meant for aligning with transcripts. pyannote 3.x -> speaker-diarization-3.1.
Benchmark on Hebrew Knesset committee clips: audio/diarization_benchmark/.
"""
import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd
import torch
import pyannote.audio
from pyannote.audio import Pipeline

PYANNOTE_MAJOR = int(pyannote.audio.__version__.split(".")[0])
DEFAULT_MODEL = ("pyannote/speaker-diarization-community-1" if PYANNOTE_MAJOR >= 4
                 else "pyannote/speaker-diarization-3.1")
SR = 16000


@dataclass
class DiarizationConfig:
    model: str = DEFAULT_MODEL
    device: str = "cuda"
    num_speakers: Optional[int] = None   # exact count, if known
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None   # lectures: a bound like 10 helps more than a guess


_PIPELINES: Dict[str, Pipeline] = {}


def load_pipeline(model: str, device: str) -> Pipeline:
    key = f"{model}|{device}"
    if key not in _PIPELINES:
        logging.info(f"Loading diarization pipeline | model={model} | pyannote={pyannote.audio.__version__}")
        pipeline = Pipeline.from_pretrained(model)  # token: HF_TOKEN env or `huggingface-cli login` cache
        if pipeline is None:
            raise RuntimeError(f"Could not load {model}: accept its terms on huggingface.co and log in")
        if device == "cuda" and torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        _PIPELINES[key] = pipeline
    return _PIPELINES[key]


def load_waveform(file_path: str) -> dict:
    """Whole file as a 16 kHz mono tensor via ffmpeg (any container: mp3, mp4, m4a, wav...)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", file_path, "-vn", "-ac", "1",
                          "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    return {"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": SR}


def diarize(file_path: str, config: Optional[DiarizationConfig] = None) -> pd.DataFrame:
    """Speaker turns: DataFrame[start, end, speaker] in seconds, sorted by start."""
    config = config or DiarizationConfig()
    pipeline = load_pipeline(config.model, config.device)
    kwargs = {k: v for k, v in (("num_speakers", config.num_speakers), ("min_speakers", config.min_speakers),
                                ("max_speakers", config.max_speakers)) if v is not None}
    audio = load_waveform(file_path)
    with torch.no_grad():
        output = pipeline(audio, **kwargs)
    if hasattr(output, "exclusive_speaker_diarization"):   # pyannote 4.x DiarizeOutput
        annotation = output.exclusive_speaker_diarization
    elif hasattr(output, "speaker_diarization"):
        annotation = output.speaker_diarization
    else:                                                   # pyannote 3.x Annotation
        annotation = output
    turns = pd.DataFrame([(t.start, t.end, spk) for t, _, spk in annotation.itertracks(yield_label=True)],
                         columns=["start", "end", "speaker"])
    turns = turns.sort_values("start").reset_index(drop=True)
    logging.info(f"Diarization | {len(turns)} turns | {turns['speaker'].nunique()} speakers")
    return turns
