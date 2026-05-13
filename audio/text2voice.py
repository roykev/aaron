"""
Hebrew TTS: text file -> MP3
Uses Facebook MMS-TTS (facebook/mms-tts-heb) for local synthesis.

Requirements:
    pip install transformers torch scipy pydub numpy
    # System dependency: ffmpeg must be installed
    #   macOS:  brew install ffmpeg
    #   Ubuntu: sudo apt install ffmpeg

Usage:
    python tts_he.py input.txt output.mp3
    python tts_he.py input.txt output.mp3 --bitrate 192k
"""

import argparse
import io
import os.path
import re
import sys
from pathlib import Path

import numpy as np
import scipy.io.wavfile
import torch
from pydub import AudioSegment
from transformers import AutoTokenizer, VitsModel


MODEL_ID = "facebook/mms-tts-heb"
SILENCE_THRESHOLD = 0.01  # amplitude threshold for trimming trailing silence


def normalize_text(text: str) -> str:
    """Basic preprocessing. Extend this for better output quality."""
    text = re.sub(r"\s+", " ", text).strip()
    # --- Tweak hooks (add later for quality wins) ---
    # 1. Niqqud injection via Nakdimon / Dicta nakdan API
    # 2. Number expansion: "90%" -> "תשעים אחוז", "2026" -> "אלפיים עשרים ושש"
    # 3. Acronym/abbreviation expansion: "ד״ר" -> "דוקטור", "וכו׳" -> "וכולי"
    # 4. English term handling (route to English TTS or transliterate)
    return text


def trim_trailing_silence(waveform: np.ndarray, sample_rate: int,
                          threshold: float = SILENCE_THRESHOLD) -> np.ndarray:
    """Trim trailing silence, keeping a small natural tail (~50ms)."""
    mask = np.abs(waveform) > threshold
    if not mask.any():
        return waveform
    last_non_silent = int(np.where(mask)[0][-1])
    tail_samples = int(0.05 * sample_rate)
    end = min(last_non_silent + tail_samples, len(waveform))
    return waveform[:end]


def synthesize(text: str, model: VitsModel, tokenizer) -> tuple[np.ndarray, int]:
    """Run MMS-TTS on text. Returns (waveform, sample_rate)."""
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        output = model(**inputs).waveform
    waveform = output.squeeze().cpu().numpy().astype(np.float32)
    return waveform, model.config.sampling_rate


def waveform_to_mp3(waveform: np.ndarray, sample_rate: int,
                    output_path: Path, bitrate: str = "128k") -> None:
    """Convert float waveform [-1, 1] to MP3 via pydub + ffmpeg."""
    pcm16 = np.clip(waveform * 32767, -32768, 32767).astype(np.int16)

    wav_buffer = io.BytesIO()
    scipy.io.wavfile.write(wav_buffer, sample_rate, pcm16)
    wav_buffer.seek(0)

    audio = AudioSegment.from_wav(wav_buffer)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(output_path, format="mp3", bitrate=bitrate)


def tts_to_mp3(input_txt: Path, output_mp3: Path, bitrate: str = "128k") -> None:
    print(f"Loading model: {MODEL_ID}")
    model = VitsModel.from_pretrained(MODEL_ID)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model.eval()

    print(f"Reading: {input_txt}")
    text = input_txt.read_text(encoding="utf-8")
    text = normalize_text(text)
    if not text:
        raise ValueError("Input text is empty after normalization.")

    print(f"Synthesizing {len(text)} chars...")
    waveform, sr = synthesize(text, model, tokenizer)
    waveform = trim_trailing_silence(waveform, sr)

    print(f"Writing MP3: {output_mp3}")
    waveform_to_mp3(waveform, sr, output_mp3, bitrate=bitrate)
    print(f"Done. Duration: {len(waveform) / sr:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hebrew TTS: txt -> mp3 (MMS-TTS)")
    parser.add_argument("input", type=Path, help="Input text file (UTF-8)")
    parser.add_argument("output", type=Path, help="Output MP3 file")
    parser.add_argument("--bitrate", default="128k",
                        help="MP3 bitrate (default: 128k; try 192k for higher quality)")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"Error: {args.input} not found")

    tts_to_mp3(args.input, args.output, bitrate=args.bitrate)


if __name__ == "__main__":
#    main()
    dir = "/home/roy/Downloads/"
    in_file = "בינה מלאכותית ויישומיה - lecture 4 - short_summary.txt"
    out_file = "a.mp3"
    in_ = os.path.join(dir, in_file)
    out_ = os.path.join(dir, out_file)

    tts_to_mp3(Path(in_),Path(out_), bitrate=" 192k")
