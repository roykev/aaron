# audio/transcription — who said what

Speaker-attributed transcription: faster-whisper with **language routing** + **pyannote diarization**,
merged per word. Independent copy of v_indexer's transcriber (does not import v_indexer / production).

## Run

```bash
# best setup: pyannote 4 env -> community-1 diarization
env -u LD_LIBRARY_PATH /home/roy/FS/miniconda3/envs/pyannote4/bin/python \
    -m audio.transcription.pipeline <media file or dir> --max-speakers 10 [--out DIR] [--language he]

# aaron env -> pyannote 3.1 diarization (same CLI)
env -u LD_LIBRARY_PATH python -m audio.transcription.pipeline <media> --max-speakers 10
```

Output in `--out` (default: next to the media): `transcript_speakers.csv` / `.json`
(start, end, timestamp, speaker, text; SPK_1 = most talk time), `diarization_turns.csv`, `trans.csv`.

`env -u LD_LIBRARY_PATH`: `~/.bashrc` puts `/usr/local/cuda-12.1/lib64` first, which breaks torch's CUDA libs.

## What it does

| Step | Detail |
|---|---|
| Loudness normalization | ffmpeg `dynaudnorm` before VAD — Silero VAD drops quiet speech after loud speech (student after lecturer) |
| Language detection | stock `large-v3-turbo`, 8 × 30 s windows spread over the file |
| Routing | `he` → `ivrit-ai/whisper-large-v3-turbo-ct2`; anything else → stock `large-v3-turbo` |
| Decoding | fallback temperatures 0.0–1.0 + `condition_on_previous_text=False` — temperature 0 alone let repetition loops run for minutes on a 4.9 h Zoom lecture (85 loop segments → 22). Benchmarks below predate this change |
| Diarization | pyannote 4 → `speaker-diarization-community-1` (exclusive output); pyannote 3 → `3.1` |
| Merge | each word → speaker with most overlap; segments split where the speaker changes |

The ivrit-ai model must not see English: it detects every English clip as Hebrew (FLEURS-en WER 49.8% vs 5.8%).

## Benchmarks (2026-10-22)

ASR, `audio/asr_benchmark/` — WER %, production decoding settings:

| set | stock turbo | ivrit-ai turbo |
|---|---|---|
| ivrit eval-d1 | 8.7 | 5.1 |
| ivrit WhatsApp | 14.8 | 7.0 |
| FLEURS he | 31.7 | 20.8 |
| FLEURS en | 5.8 | 49.8 |

Speaker-attributed, `audio/diarization_benchmark/` — 20 Hebrew Knesset committee clips (8 min, 4–13 speakers),
reference = protocol text + speaker labels (non-verbatim, so absolute WER is inflated; compare systems):

| system | WER | cpWER | WDER | DER |
|---|---|---|---|---|
| stock ASR + pyannote 3.1 (production-like) | 49.8 | 61.9 | 13.8 | 28.7 |
| routed ASR + 3.1 | 44.3 | 58.8 | 13.2 | 28.7 |
| routed + normalization + 3.1 | 44.6 | 59.0 | 13.0 | 28.7 |
| **routed + normalization + community-1** | 44.9 | **56.4** | **11.7** | **20.6** |

Diarization only (`run_pyannote.py` + `score.py`, standard non-exclusive output): 3.1 DER 28.7, community-1 28.0.
The community-1 gain in the table above comes from its exclusive (one speaker at a time) output.

Runtime is about the same for all four systems: ~35 s per 8-min clip end to end (~14× real time, rough
timestamps from one run each).

### How good is this vs published results

- **Diarization**: community-1's published DER (no collar) is ~11% VoxConverse, ~17% AMI, ~20% DIHARD 3 / AliMeeting.
  20.6% here (collar 0.5) on 4–13-speaker committee audio is in that range. 18.9 points are "false alarm",
  mostly gaps in the reference, so the real error is lower.
- **Transcription**: absolute WER 45% is inflated by the non-verbatim protocol reference. The same ivrit-ai model is
  5–7% WER on verbatim Hebrew (eval-d1, WhatsApp), which is close to the best published Hebrew results.
- **Speaker attribution**: cpWER − WER ≈ 11.5 points ≈ WDER 11.7%, so about 1 word in 9 goes to the wrong speaker. In
  CHiME / NOTSOFAR meeting challenges the gap is typically 5–15 points.
- For true absolute numbers, hand-correct 2–3 clips into verbatim references.

## Files

| path | what |
|---|---|
| `asr_benchmark/compare_whisper.py` | stock vs ivrit-ai WER → `results.csv`, `results_normalized.csv` (`--normalize`) |
| `diarization_benchmark/build_knesset_benchmark.py` | builds the 20 clips from `ivrit-ai/knesset-committees` → `data/knesset/` |
| `diarization_benchmark/run_pyannote.py`, `score.py` | diarization only → `hyp/<model>/*.rttm`, DER/JER |
| `diarization_benchmark/run_pipeline_bench.py` | full pipeline per clip → `hyp/<system>/<clip>/` |
| `diarization_benchmark/score_sa_asr.py` | WER / cpWER / WDER / DER; per-clip → `hyp/<system>/sa_asr_scores.csv` |

`data/` and `hyp/` are gitignored (~1.3 GB audio); rebuild them with the scripts above (gated HF datasets: accept the terms as `roykev`).

Re-run: `diarization_benchmark/run_pipeline_bench.py <name> [flags]` then `score_sa_asr.py hyp/<name> ...`.

## Production (v_indexer)

Not changed. The port plan and findings are in `v_indexer/docs/TRANSCRIPTION_FUTURE_IMPROVEMENTS.md` (+ an entry in
`v_indexer/TODO.md`, Future Work).
