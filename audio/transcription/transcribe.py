"""faster-whisper transcriber with language routing.

Independent copy of v_indexer/src/silos/transcribe/transcribe.py (commit 5e88b90, 2026-09-01) — does not
import v_indexer. Added: per-language model routing. The base model detects the language once per file;
languages listed in `TranscriptionConfig.language_models` are transcribed with their own model
(Hebrew -> ivrit-ai/whisper-large-v3-turbo-ct2), everything else with the base model.

Why (audio/asr_benchmark/results.csv, 2026-10-22, production decoding settings):
    WER %            stock turbo   ivrit-ai turbo
    ivrit eval-d1        8.7           5.1
    ivrit whatsapp      14.8           7.0
    fleurs he           31.7          20.8
    fleurs en            5.8          49.8   <- ivrit-ai model detects every English clip as Hebrew
"""
import os
import io
import json
import time
import logging
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch

# Configure ffmpeg/ffprobe paths BEFORE importing pydub
# This ensures pydub can find ffmpeg/ffprobe in conda environment
import subprocess

# Try to find ffmpeg/ffprobe and set paths
ffmpeg_full_path = None
ffprobe_full_path = None
try:
    ffmpeg_full_path = subprocess.check_output(['which', 'ffmpeg'], text=True).strip()
    ffprobe_full_path = subprocess.check_output(['which', 'ffprobe'], text=True).strip()
except Exception:
    # Fallback to the running interpreter's env if which fails
    import sys
    conda_bin = os.path.join(sys.prefix, "bin")
    if os.path.exists(os.path.join(conda_bin, "ffmpeg")):
        ffmpeg_full_path = os.path.join(conda_bin, "ffmpeg")
        ffprobe_full_path = os.path.join(conda_bin, "ffprobe")

# Inject ffmpeg dir into PATH so pydub's internal which() can find ffprobe
if ffmpeg_full_path:
    ffmpeg_dir = os.path.dirname(ffmpeg_full_path)
    if ffmpeg_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

from pydub import AudioSegment
import pydub.utils
from pydub.utils import which
from faster_whisper import WhisperModel

# Configure AudioSegment class attributes with absolute paths
if ffmpeg_full_path and ffprobe_full_path:
    AudioSegment.converter = ffmpeg_full_path
    AudioSegment.ffmpeg = ffmpeg_full_path
    AudioSegment.ffprobe = ffprobe_full_path
    # Monkey-patch get_prober_name so mediainfo_json() uses the full path too
    _ffprobe_path = ffprobe_full_path
    pydub.utils.get_prober_name = lambda: _ffprobe_path
else:
    # Last resort - try pydub's which()
    AudioSegment.converter = which("ffmpeg") or "ffmpeg"
    AudioSegment.ffmpeg = which("ffmpeg") or "ffmpeg"
    AudioSegment.ffprobe = which("ffprobe") or "ffprobe"


# =========================================================
# Logging
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)


# =========================================================
# Config
# =========================================================
@dataclass
class TranscriptionConfig:
    # ---------- Model ----------
    # Examples:
    # "large-v2"
    # "large-v3"
    # "large-v3-turbo"
    # "distil-large-v3.5"
    model_size: str = "large-v3-turbo"
    compute_type: str = "float16"   # "float16", "int8_float16", "int8"
    device: str = "cuda"

    # ---------- Language ----------
    # None => auto detect
    # "he", "en", "ar"
    language: Optional[str] = None

    # ---------- Language routing ----------
    # language -> model used to transcribe it; other languages use model_size.
    # Empty dict => no routing (plain v_indexer behaviour).
    language_models: Dict[str, str] = field(
        default_factory=lambda: {"he": "ivrit-ai/whisper-large-v3-turbo-ct2"})
    # Language detection: this many 30 s windows spread evenly over the file (base model, VAD on);
    # the language with the highest summed probability wins. Spread, not the file's head: a lecture's
    # first minutes (setup, noise) came out pt 0.45 / en 0.58 where the rest is he 0.99.
    language_detect_windows: int = 8

    # ---------- Decoding ----------
    beam_size: int = 5
    best_of: int = 5
    # Fallback temperatures + no conditioning on previous text: with temperature 0 only, faster-whisper
    # cannot retry a segment that fails its compression-ratio check, and conditioning lets one loop
    # ("רגע, רגע, רגע...") feed the next segment. On a 4.9 h Zoom lecture: 84 looping segments at
    # temperature 0; on a 20 min window of it, 12 loop segments -> 1 and +17% words recovered.
    temperature: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    condition_on_previous_text: bool = False
    word_timestamps: bool = False

    # ---------- Loudness ----------
    # Silero VAD drops quiet speech that follows loud speech (e.g. a student's question after the
    # lecturer, on a room mic). Normalizing loudness first recovers it: on a mix of loud and 40 dB quieter
    # clips, VAD kept 36 of 70 s of speech raw and 70 of 70 s after dynaudnorm.
    normalize_loudness: bool = True
    loudness_filter: str = "dynaudnorm=f=250:g=15:m=30"

    # ---------- VAD ----------
    vad_filter: bool = True
    vad_min_silence_duration_ms: int = 500

    # ---------- Input ----------
    preferred_audio_name: str = "raw.mp3"

    # ---------- Chunking ----------
    use_chunking: bool = False                 # manual override
    auto_chunking: bool = True                # if True, decide by duration
    auto_chunk_threshold_minutes: float = 20.0
    chunk_duration_minutes: float = 8.0
    chunk_overlap_seconds: float = 1.5
    chunk_export_format: str = "wav"

    # ---------- Output ----------
    output_csv_name: str = "trans.csv"
    output_json_name: str = "trans.json"

    # ---------- Runtime / fallback ----------
    log_gpu_memory: bool = True
    fallback_to_safe_precision: bool = True
    safe_fallback_compute_type: str = "int8"

    # ---------- Post-processing ----------
    enable_merge_segments: bool = True
    merge_max_gap_seconds: float = 0.4
    merge_max_chars: int = 220
    merge_max_words: int = 40

    # Near-duplicate suppression for chunk overlap
    enable_near_duplicate_suppression: bool = True
    near_dup_max_start_diff: float = 0.75
    near_dup_max_end_diff: float = 0.75


# =========================================================
# Utilities
# =========================================================
def init_cuda(log_memory: bool = True) -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        if log_memory:
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
            free_est = total - reserved
            logging.info(
                f"GPU detected | total={total:.2f}GB | "
                f"allocated={allocated:.2f}GB | reserved={reserved:.2f}GB | "
                f"approx_free={free_est:.2f}GB"
            )
    else:
        logging.warning("CUDA not available. Using CPU.")


def get_media_file(dir_name: str, preferred_audio_name: str = "raw.mp3") -> str:
    if os.path.isfile(dir_name):  # a media file was passed directly
        return dir_name
    mp3_path = os.path.join(dir_name, preferred_audio_name)
    if os.path.exists(mp3_path):
        logging.debug(f"Using audio file: {mp3_path}")
        return mp3_path

    mp4_files = sorted([f for f in os.listdir(dir_name) if f.lower().endswith(".mp4")])
    if mp4_files:
        file_name = os.path.join(dir_name, mp4_files[0])
        logging.debug(f"{preferred_audio_name} not found, using video file: {file_name}")
        return file_name

    raise FileNotFoundError(
        f"No media file found in {dir_name}. "
        f"Expected '{preferred_audio_name}' or at least one .mp4 file."
    )


def load_audio_segment(file_path: str) -> AudioSegment:
    """Load audio file using pydub with explicit ffmpeg path."""
    lower = file_path.lower()

    # Get absolute paths to ffmpeg/ffprobe
    ffmpeg_path = which("ffmpeg") or "ffmpeg"
    ffprobe_path = which("ffprobe") or "ffprobe"

    # Use explicit parameters to avoid pydub's path detection issues
    if lower.endswith(".mp3"):
        return AudioSegment.from_file(file_path, format="mp3",
                                     parameters=["-f", "mp3"])
    if lower.endswith(".wav"):
        return AudioSegment.from_file(file_path, format="wav",
                                     parameters=["-f", "wav"])

    # For mp4 and other formats, let ffmpeg auto-detect
    return AudioSegment.from_file(file_path)


def has_audio_track(file_path: str) -> bool:
    """Return True if the file has at least one audio stream."""
    global ffprobe_full_path
    try:
        probe_path = ffprobe_full_path or which("ffprobe") or "ffprobe"
        result = subprocess.run(
            [probe_path, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return True  # assume audio present if ffprobe fails


def load_audio_window(file_path: str, start: float, seconds: float, sr: int = 16000) -> np.ndarray:
    """`seconds` of audio from `start` as 16 kHz mono float32 (ffmpeg seek, without decoding the whole file)."""
    out = subprocess.run(
        [ffmpeg_full_path or "ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}",
         "-i", file_path,
         "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0


def make_normalized_wav(file_path: str, loudness_filter: str, out_path: str) -> str:
    """16 kHz mono wav with loudness normalization; ASR source when config.normalize_loudness."""
    subprocess.run([ffmpeg_full_path or "ffmpeg", "-v", "error", "-nostdin", "-y", "-i", file_path, "-vn",
                    "-af", loudness_filter, "-ac", "1", "-ar", "16000", out_path], check=True)
    return out_path


_MODEL_CACHE: Dict[Tuple[str, str, str], WhisperModel] = {}


def load_whisper(model_name: str, device: str, compute_type: str) -> WhisperModel:
    """Load once per process; routing models stay resident across files."""
    key = (model_name, device, compute_type)
    if key not in _MODEL_CACHE:
        logging.info(f"Loading model | model={model_name} | device={device} | compute_type={compute_type}")
        _MODEL_CACHE[key] = WhisperModel(model_name, device=device, compute_type=compute_type)
    return _MODEL_CACHE[key]


def get_audio_duration_minutes(file_path: str) -> float:
    """Get audio/video duration using ffprobe directly (faster and more reliable than pydub)."""
    global ffprobe_full_path

    try:
        # Use the global ffprobe path we found at module import time
        probe_path = ffprobe_full_path or which("ffprobe") or "ffprobe"

        result = subprocess.run(
            [probe_path, "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             file_path],
            capture_output=True,
            text=True,
            check=True
        )
        duration_seconds = float(result.stdout.strip())
        return duration_seconds / 60.0
    except Exception as e:
        logging.warning(f"ffprobe failed, falling back to pydub: {e}")
        # Fallback to pydub if ffprobe fails
        audio = load_audio_segment(file_path)
        return len(audio) / (1000.0 * 60.0)


def split_audio_to_memory_chunks(
    file_path: str,
    chunk_duration_minutes: float,
    overlap_seconds: float = 0.0,
    export_format: str = "wav",
) -> List[Tuple[io.BytesIO, float, float]]:
    """
    Returns a list of tuples:
    (buffer, chunk_start_sec, chunk_end_sec)
    """
    logging.info(
        f"Splitting audio | chunk_duration={chunk_duration_minutes:.2f} min | "
        f"overlap={overlap_seconds:.2f} sec | format={export_format}"
    )

    audio = load_audio_segment(file_path)

    chunk_ms = int(chunk_duration_minutes * 60 * 1000)
    overlap_ms = int(overlap_seconds * 1000)

    if chunk_ms <= 0:
        raise ValueError("chunk_duration_minutes must be > 0")

    chunks = []
    total_ms = len(audio)
    start_ms = 0

    while start_ms < total_ms:
        end_ms = min(start_ms + chunk_ms, total_ms)
        chunk = audio[start_ms:end_ms]

        buf = io.BytesIO()
        chunk.export(buf, format=export_format)
        buf.seek(0)

        chunks.append((buf, start_ms / 1000.0, end_ms / 1000.0))

        if end_ms >= total_ms:
            break

        start_ms = max(0, end_ms - overlap_ms)

    logging.debug(f"Created {len(chunks)} chunks")
    return chunks


def format_timestamp(seconds: float) -> str:
    if seconds is None:
        return ""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


BIDI_CONTROLS = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"))


def normalize_text(text: str) -> str:
    # ivrit-ai models emit RTL embedding marks (U+202B) after commas; they break search and CSV display
    return " ".join((text or "").translate(BIDI_CONTROLS).split()).strip()


def safe_float(x) -> float:
    return float(x)


def can_merge_segments(
    current_seg: dict,
    next_seg: dict,
    max_gap_seconds: float,
    max_chars: int,
    max_words: int,
) -> bool:
    gap = safe_float(next_seg["start"]) - safe_float(current_seg["end"])
    gap = max(0.0, gap)

    if gap > max_gap_seconds:
        return False

    merged_text = normalize_text(
        f'{current_seg.get("text", "")} {next_seg.get("text", "")}'
    )

    if len(merged_text) > max_chars:
        return False

    if len(merged_text.split()) > max_words:
        return False

    return True


def merge_close_segments(
    segments: List[dict],
    max_gap_seconds: float = 0.4,
    max_chars: int = 220,
    max_words: int = 40,
) -> List[dict]:
    if not segments:
        return []

    segments = sorted(segments, key=lambda x: (x["start"], x["end"]))
    merged = [segments[0].copy()]

    for seg in segments[1:]:
        last = merged[-1]

        if can_merge_segments(
            last,
            seg,
            max_gap_seconds=max_gap_seconds,
            max_chars=max_chars,
            max_words=max_words,
        ):
            last["end"] = seg["end"]
            last["text"] = normalize_text(f'{last["text"]} {seg["text"]}')
            if last.get("words") or seg.get("words"):
                last["words"] = json.dumps(json.loads(last.get("words") or "[]") +
                                           json.loads(seg.get("words") or "[]"), ensure_ascii=False)
        else:
            merged.append(seg.copy())

    return merged


def suppress_near_duplicates(
    segments: List[dict],
    max_start_diff: float = 0.75,
    max_end_diff: float = 0.75,
) -> List[dict]:
    """
    Useful mainly for chunk-overlap artifacts.
    If two nearby segments overlap strongly in time and one text contains the other,
    keep the longer / more informative text.
    """
    if not segments:
        return []

    cleaned = [segments[0].copy()]

    for seg in segments[1:]:
        prev = cleaned[-1]

        start_close = abs(seg["start"] - prev["start"]) <= max_start_diff
        end_close = abs(seg["end"] - prev["end"]) <= max_end_diff

        prev_text = normalize_text(prev["text"])
        curr_text = normalize_text(seg["text"])

        text_overlap = (prev_text in curr_text) or (curr_text in prev_text)

        if start_close and end_close and text_overlap:
            if len(curr_text) > len(prev_text):
                cleaned[-1] = seg.copy()
        else:
            cleaned.append(seg.copy())

    return cleaned


def build_output_dataframe(segments_list: List[dict]) -> pd.DataFrame:
    if not segments_list:
        return pd.DataFrame(columns=["start", "end", "seconds", "timestamp", "text"])

    df = pd.DataFrame(segments_list)
    df = df.sort_values(["start", "end"]).reset_index(drop=True)

    df["start"] = df["start"].astype(float)
    df["end"] = df["end"].astype(float)

    # requested normalized fields
    df["seconds"] = df["start"]
    df["timestamp"] = df["start"].apply(format_timestamp)

    cols = ["start", "end", "seconds", "timestamp", "text"]
    if "words" in df.columns and df["words"].astype(bool).any():
        cols.append("words")  # JSON list of {w, s, e}; needed for word-level speaker assignment
    return df[cols]


def save_outputs(
    df: pd.DataFrame,
    out_dir: str,
    csv_name: str,
    json_name: str,
    metadata: Optional[dict] = None,
) -> None:
    csv_path = os.path.join(out_dir, csv_name)
    json_path = os.path.join(out_dir, json_name)

    df.to_csv(csv_path, index=False)

    payload = {
        "metadata": metadata or {},
        "segments": df.to_dict(orient="records"),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logging.info(f"Saved CSV:  {csv_path}")
    logging.info(f"Saved JSON: {json_path}")


# =========================================================
# Main Transcriber
# =========================================================
class Transcriber:
    def __init__(self, dir_name: str, config: TranscriptionConfig):
        self.dir_name = dir_name
        self.config = config
        self.file_name = get_media_file(dir_name, config.preferred_audio_name)
        self.source_file = self.file_name  # audio actually decoded (normalized copy when enabled)

        self.model: Optional[WhisperModel] = None          # base model (language detection + default)
        self.active_model: Optional[WhisperModel] = None   # model chosen for this file
        self.model_used: Optional[str] = None
        self.language: Optional[str] = config.language  # decoding language, set by route()
        self.transcribe_df = pd.DataFrame(columns=["start", "end", "seconds", "timestamp", "text"])
        self.detected_language: Optional[str] = config.language
        self.language_probability: Optional[float] = None
        self.audio_duration_minutes: Optional[float] = None
        self.used_chunking: Optional[bool] = None

    def _device(self) -> str:
        if self.config.device == "cuda" and not torch.cuda.is_available():
            logging.warning("CUDA requested but not available. Using CPU.")
            return "cpu"
        return self.config.device

    def _load(self, model_name: str) -> WhisperModel:
        device = self._device()
        try:
            return load_whisper(model_name, device, self.config.compute_type)
        except Exception as e:
            logging.exception("Model load failed with requested precision.")
            if self.config.fallback_to_safe_precision and device == "cuda":
                logging.warning(f"Retrying with safer precision: {self.config.safe_fallback_compute_type}")
                self.config.compute_type = self.config.safe_fallback_compute_type
                return load_whisper(model_name, device, self.config.compute_type)
            raise e

    def init_model(self) -> None:
        self.model = self._load(self.config.model_size)

    def detect_language(self) -> Tuple[str, float]:
        """Language of the file, using the base model.

        Whisper's detection on `language_detect_windows` 30 s windows spread over the file; the language
        with the highest summed probability wins (one window of setup chatter or music can't flip it).
        """
        duration = get_audio_duration_minutes(self.source_file) * 60
        n = max(1, self.config.language_detect_windows)
        starts = np.linspace(0, max(0.0, duration - 30), n) if duration > 30 else [0.0]
        totals: Dict[str, float] = {}
        used = 0
        for start in sorted(set(round(float(x), 1) for x in starts)):
            window = load_audio_window(self.source_file, start, 30)
            if len(window) < 16000:
                continue
            try:
                _, _, probs = self.model.detect_language(window, vad_filter=True)
            except Exception:
                continue  # window without speech after VAD
            for lang, p in probs:
                totals[lang] = totals.get(lang, 0.0) + p
            used += 1
        if not totals:
            logging.warning("Language detection found no speech; falling back to base model auto-detect")
            return None, None
        lang = max(totals, key=totals.get)
        return lang, totals[lang] / used

    def route(self) -> None:
        """Pick the model for this file and fix the decoding language."""
        if self.model is None:
            self.init_model()
        lang = self.config.language
        if lang is None and self.config.language_models:
            lang, prob = self.detect_language()
            self.detected_language, self.language_probability = lang, prob
        target = self.config.language_models.get(lang) if lang else None
        self.active_model = self._load(target) if target else self.model
        self.model_used = target or self.config.model_size
        self.language = lang  # None only when routing is off and language is auto
        logging.info(f"Routing | language={lang} (p={self.language_probability}) | model={self.model_used}")

    def should_use_chunking(self) -> bool:
        # explicit manual request wins
        if self.config.use_chunking:
            logging.debug("Chunking ENABLED by explicit config.use_chunking=True")
            return True

        self.audio_duration_minutes = get_audio_duration_minutes(self.file_name)
        logging.debug(f"Audio duration: {self.audio_duration_minutes:.2f} minutes")

        if self.config.auto_chunking and self.audio_duration_minutes >= self.config.auto_chunk_threshold_minutes:
            logging.info(
                f"Chunking ENABLED automatically "
                f"(duration >= {self.config.auto_chunk_threshold_minutes:.2f} min)"
            )
            return True

        logging.debug("Chunking NOT needed")
        return False

    def _transcribe_source(self, source, time_offset: float = 0.0) -> List[dict]:
        if self.active_model is None:
            raise RuntimeError("Model is not initialized")

        start_t = time.time()

        segments, info = self.active_model.transcribe(
            source,
            beam_size=self.config.beam_size,
            best_of=self.config.best_of,
            language=self.language,
            temperature=list(self.config.temperature) if isinstance(self.config.temperature, (tuple, list))
            else self.config.temperature,
            condition_on_previous_text=self.config.condition_on_previous_text,
            vad_filter=self.config.vad_filter,
            vad_parameters=(
                {"min_silence_duration_ms": self.config.vad_min_silence_duration_ms}
                if self.config.vad_filter else None
            ),
            word_timestamps=self.config.word_timestamps,
        )

        result = []
        for segment in segments:
            text = normalize_text(segment.text)
            if not text:
                continue

            # Word timings, when asked for. They cost ~1% of transcription time
            # (measured: 2.25s -> 2.27s on a 96s clip) because the alignment
            # reuses the decoder's cross-attention rather than re-decoding — the
            # words come back identical, only segment grouping shifts. Until now
            # they were computed and thrown away here.
            #
            # They are what turns a `cues:` phrase in must_moments.yaml into a
            # +/-0.2s anchor on the event timeline, which is the most precise
            # anchor available anywhere in this pipeline.
            words = ''
            if getattr(segment, 'words', None):
                words = json.dumps(
                    [{'w': normalize_text(w.word),
                      's': round(safe_float(w.start) + time_offset, 3),
                      'e': round(safe_float(w.end) + time_offset, 3)}
                     for w in segment.words if normalize_text(w.word)],
                    ensure_ascii=False)

            result.append({
                "start": safe_float(segment.start) + time_offset,
                "end": safe_float(segment.end) + time_offset,
                "text": text,
                "words": words,
            })

        elapsed = time.time() - start_t

        if self.language is None:  # only when auto-detecting inside transcribe (routing off)
            self.detected_language = getattr(info, "language", self.detected_language)
            self.language_probability = getattr(info, "language_probability", None)

        logging.info(
            f"Chunk/file transcribed in {elapsed:.2f}s | "
            f"detected_language={self.detected_language} | "
            f"language_prob={self.language_probability}"
        )

        return result

    def _postprocess_segments(self, rows: List[dict]) -> List[dict]:
        rows = sorted(rows, key=lambda x: (x["start"], x["end"]))

        # Step 1: remove exact duplicates
        deduped = []
        seen = set()
        for r in rows:
            key = (round(r["start"], 3), round(r["end"], 3), r["text"])
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # Step 2: suppress near duplicates from chunk overlap
        if self.config.enable_near_duplicate_suppression:
            before = len(deduped)
            deduped = suppress_near_duplicates(
                deduped,
                max_start_diff=self.config.near_dup_max_start_diff,
                max_end_diff=self.config.near_dup_max_end_diff,
            )
            after = len(deduped)
            logging.debug(f"Near-duplicate suppression | before={before} | after={after}")

        # Step 3: merge close consecutive segments
        if self.config.enable_merge_segments:
            before = len(deduped)
            deduped = merge_close_segments(
                deduped,
                max_gap_seconds=self.config.merge_max_gap_seconds,
                max_chars=self.config.merge_max_chars,
                max_words=self.config.merge_max_words,
            )
            after = len(deduped)
            logging.debug(f"Post-process merge | before={before} | after={after}")

        return deduped

    def transcribe_full_file(self) -> pd.DataFrame:
        logging.debug("Running transcription on full file")
        rows = self._transcribe_source(self.source_file, time_offset=0.0)
        rows = self._postprocess_segments(rows)
        self.transcribe_df = build_output_dataframe(rows)
        return self.transcribe_df

    def transcribe_in_chunks(self) -> pd.DataFrame:
        logging.debug("Running chunked transcription")

        chunks = split_audio_to_memory_chunks(
            self.source_file,
            chunk_duration_minutes=self.config.chunk_duration_minutes,
            overlap_seconds=self.config.chunk_overlap_seconds,
            export_format=self.config.chunk_export_format,
        )

        all_rows = []
        total_chunks = len(chunks)

        for i, (buf, chunk_start, chunk_end) in enumerate(chunks, start=1):
            logging.info(
                f"Transcribing chunk {i}/{total_chunks} | "
                f"range={chunk_start:.2f}-{chunk_end:.2f}s"
            )

            rows = self._transcribe_source(buf, time_offset=chunk_start)
            all_rows.extend(rows)

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        all_rows = self._postprocess_segments(all_rows)
        self.transcribe_df = build_output_dataframe(all_rows)
        return self.transcribe_df

    def run(self) -> pd.DataFrame:
        if not has_audio_track(self.file_name):
            logging.info(f"No audio track found in {self.file_name} — skipping transcription")
            return self.transcribe_df
        import tempfile
        with tempfile.TemporaryDirectory(prefix="transcribe_") as tmp:
            if self.config.normalize_loudness:
                self.source_file = make_normalized_wav(self.file_name, self.config.loudness_filter,
                                                       os.path.join(tmp, "normalized.wav"))
            try:
                self.route()
                self.used_chunking = self.should_use_chunking()
                if self.used_chunking:
                    return self.transcribe_in_chunks()
                return self.transcribe_full_file()
            finally:
                self.source_file = self.file_name

    def get_metadata(self) -> dict:
        return {
            "file_name": self.file_name,
            "audio_duration_minutes": self.audio_duration_minutes,
            "used_chunking": self.used_chunking,
            "config": asdict(self.config),
            "language_detected": self.detected_language,
            "language_probability": self.language_probability,
            "model_used": self.model_used,
            "rows": len(self.transcribe_df),
        }


# =========================================================
# Public runner
# =========================================================
def run_transcribe(dir_name: str, config: TranscriptionConfig) -> Tuple[str, pd.DataFrame]:
    if config.device == "cuda":
        init_cuda(log_memory=config.log_gpu_memory)

    t1 = time.time()

    with torch.no_grad():
        transcriber = Transcriber(dir_name=dir_name, config=config)
        df = transcriber.run()

        save_outputs(
            df=df,
            out_dir=dir_name if os.path.isdir(dir_name) else os.path.dirname(os.path.abspath(dir_name)),
            csv_name=config.output_csv_name,
            json_name=config.output_json_name,
            metadata=transcriber.get_metadata(),
        )

    t2 = time.time()
    logging.info(f"Transcription finished in {t2 - t1:.2f}s")

    return transcriber.detected_language or "unknown", df


# =========================================================
# Convenience presets
# =========================================================
def make_config(
    model_size: str = "large-v3-turbo",
    compute_type: str = "float16",
    language: Optional[str] = None,
) -> TranscriptionConfig:
    return TranscriptionConfig(
        model_size=model_size,
        compute_type=compute_type,
        language=language,
    )


# =========================================================
# CLI (transcription only; for transcription + speakers use pipeline.py)
# =========================================================
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("media", help="media file, or a directory with raw.mp3 / an .mp4")
    ap.add_argument("--language", default=None)
    ap.add_argument("--no-routing", action="store_true")
    a = ap.parse_args()
    cfg = make_config(language=a.language)
    if a.no_routing:
        cfg.language_models = {}
    lang, df = run_transcribe(a.media, cfg)
    logging.info(f"Detected language: {lang} | rows: {len(df)}")
