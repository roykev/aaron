"""Transcription (language-routed faster-whisper) + speaker diarization (pyannote) -> speaker-attributed transcript.

    python -m audio.transcription.pipeline <media file or dir> [--out DIR] [--max-speakers 10] [--language he]

Writes <out>/transcript_speakers.csv and .json: one row per speaker-homogeneous sentence
(start, end, timestamp, speaker, text), plus metadata (language, models, speakers' talk time).

Speaker assignment is per word: each word takes the diarization speaker it overlaps most (or the nearest
turn within MAX_SNAP_S), and a transcript segment is split wherever the speaker changes inside it.
Speakers are renamed SPK_1, SPK_2, ... by total talk time (SPK_1 = most talk, usually the lecturer).
"""
import os
import json
import time
import logging
import argparse
from dataclasses import asdict
from typing import List, Optional

import numpy as np
import pandas as pd
import torch

from .transcribe import TranscriptionConfig, Transcriber, init_cuda, format_timestamp
from .diarize import DiarizationConfig, diarize

MAX_SNAP_S = 1.0  # a word outside every turn takes the nearest turn if it is this close


def speaker_for_span(start: float, end: float, turns: pd.DataFrame) -> Optional[str]:
    if turns.empty:
        return None
    overlap = (np.minimum(turns["end"].values, end) - np.maximum(turns["start"].values, start)).clip(min=0)
    if overlap.max() > 0:
        per_speaker = pd.Series(overlap).groupby(turns["speaker"].values).sum()
        return per_speaker.idxmax()
    gap = np.maximum(turns["start"].values - end, start - turns["end"].values)
    i = int(gap.argmin())
    return turns["speaker"].iloc[i] if gap[i] <= MAX_SNAP_S else None


def assign_speakers(segments: pd.DataFrame, turns: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    for seg in segments.itertuples():
        words = json.loads(seg.words) if getattr(seg, "words", "") else []
        if not words:  # no word timings: whole segment
            rows.append(dict(start=seg.start, end=seg.end, text=seg.text,
                             speaker=speaker_for_span(seg.start, seg.end, turns)))
            continue
        current = None
        for w in words:
            spk = speaker_for_span(w["s"], w["e"], turns)
            if current is not None and spk == current["speaker"]:
                current["end"] = w["e"]
                current["text"].append(w["w"])
            else:
                if current is not None:
                    rows.append(current)
                current = dict(start=w["s"], end=w["e"], speaker=spk, text=[w["w"]])
        rows.append(current)
    for r in rows:
        if isinstance(r["text"], list):
            r["text"] = " ".join(r["text"])
    return pd.DataFrame(rows, columns=["start", "end", "speaker", "text"])


def rename_by_talk_time(df: pd.DataFrame, turns: pd.DataFrame):
    talk = (turns["end"] - turns["start"]).groupby(turns["speaker"]).sum().sort_values(ascending=False)
    names = {spk: f"SPK_{i + 1}" for i, spk in enumerate(talk.index)}
    df["speaker"] = df["speaker"].map(names).fillna("UNKNOWN")
    return df, {names[s]: round(float(t), 1) for s, t in talk.items()}


def run(media: str, out_dir: Optional[str] = None,
        tconfig: Optional[TranscriptionConfig] = None,
        dconfig: Optional[DiarizationConfig] = None) -> pd.DataFrame:
    tconfig = tconfig or TranscriptionConfig()
    tconfig.word_timestamps = True  # required for word-level speaker assignment
    dconfig = dconfig or DiarizationConfig()
    if tconfig.device == "cuda":
        init_cuda(log_memory=tconfig.log_gpu_memory)

    t0 = time.time()
    with torch.no_grad():
        transcriber = Transcriber(media, tconfig)
        segments = transcriber.run()
    t1 = time.time()
    turns = diarize(transcriber.file_name, dconfig)
    t2 = time.time()

    df = assign_speakers(segments, turns)
    df, talk_time = rename_by_talk_time(df, turns)
    df.insert(2, "timestamp", df["start"].apply(format_timestamp))

    meta = dict(file=transcriber.file_name,
                language=transcriber.detected_language, language_probability=transcriber.language_probability,
                asr_model=transcriber.model_used, diarization_model=dconfig.model,
                speakers_talk_time_s=talk_time, n_turns=len(turns),
                seconds=dict(transcription=round(t1 - t0, 1), diarization=round(t2 - t1, 1)),
                transcription_config=asdict(tconfig), diarization_config=asdict(dconfig))
    out_dir = out_dir or (media if os.path.isdir(media) else os.path.dirname(os.path.abspath(media)))
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "transcript_speakers.csv"), index=False)
    turns.to_csv(os.path.join(out_dir, "diarization_turns.csv"), index=False)
    with open(os.path.join(out_dir, "transcript_speakers.json"), "w", encoding="utf-8") as f:
        json.dump(dict(metadata=meta, segments=df.to_dict(orient="records")), f, ensure_ascii=False, indent=2)
    logging.info(f"Done | {len(df)} rows | {len(talk_time)} speakers | asr {t1 - t0:.0f}s | "
                 f"diarization {t2 - t1:.0f}s | -> {out_dir}")
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media", help="media file, or a directory with raw.mp3 / an .mp4")
    ap.add_argument("--out", default=None)
    ap.add_argument("--language", default=None, help="skip detection, e.g. he / en")
    ap.add_argument("--num-speakers", type=int, default=None)
    ap.add_argument("--min-speakers", type=int, default=None)
    ap.add_argument("--max-speakers", type=int, default=None)
    ap.add_argument("--no-routing", action="store_true", help="always use the base model")
    a = ap.parse_args()
    tconfig = TranscriptionConfig(language=a.language)
    if a.no_routing:
        tconfig.language_models = {}
    dconfig = DiarizationConfig(num_speakers=a.num_speakers, min_speakers=a.min_speakers,
                                max_speakers=a.max_speakers)
    run(a.media, a.out, tconfig, dconfig)


if __name__ == "__main__":
    main()
