"""Run audio.transcription.pipeline on every benchmark clip under a named configuration.

    python run_pipeline_bench.py <system_name> [--no-routing] [--no-normalize] [--max-speakers N]

Writes hyp/<system_name>/<clip>/{transcript_speakers.csv, diarization_turns.csv, ...}; score with
score_sa_asr.py hyp/<system_name>.
"""
import os
import sys
import time
import argparse
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # repo root, for `audio.transcription`

from audio.transcription.pipeline import run  # noqa: E402
from audio.transcription.transcribe import TranscriptionConfig  # noqa: E402
from audio.transcription.diarize import DiarizationConfig  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system")
    ap.add_argument("--ref", default=os.path.join(HERE, "data", "knesset"))
    ap.add_argument("--no-routing", action="store_true")
    ap.add_argument("--no-normalize", action="store_true")
    ap.add_argument("--max-speakers", type=int, default=None)
    a = ap.parse_args()
    logging.getLogger().setLevel(logging.WARNING)

    out_root = os.path.join(HERE, "hyp", a.system)
    wav_dir = os.path.join(a.ref, "wav")
    for f in sorted(os.listdir(wav_dir)):
        clip = f[:-4]
        tcfg = TranscriptionConfig(normalize_loudness=not a.no_normalize)
        if a.no_routing:
            tcfg.language_models = {}
        t = time.time()
        df = run(os.path.join(wav_dir, f), os.path.join(out_root, clip), tcfg,
                 DiarizationConfig(max_speakers=a.max_speakers))
        print(f"{clip}: {len(df)} rows, {df['speaker'].nunique()} speakers, {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
