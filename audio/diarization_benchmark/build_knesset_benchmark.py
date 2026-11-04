"""Build a Hebrew speaker-diarization benchmark from ivrit-ai/knesset-committees.

Ground truth = protocol speaker labels + ivrit.ai forced-alignment timestamps (silver, not hand-labelled).
One window (< 10 min) per session, kept only if every segment is single-speaker and well aligned.

Output (in OUT_DIR):
    wav/<clip>.wav     16 kHz mono
    rttm/<clip>.rttm   reference, times relative to clip start
    uem/<clip>.uem     scored region (whole clip)
    clips.csv          one row per clip: session, offsets, speakers, quality, title
"""
import os, sys, json, random, subprocess
import numpy as np
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

REPO = "ivrit-ai/knesset-committees"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knesset")
N_CLIPS = 20
MAX_SESSIONS_TRIED = 80
WINDOW_S = 480            # target window length (8 min)
LOW_Q = 0.5               # turn quality = median word alignment probability
MAX_LOW_Q_SHARE = 0.10    # window: at most this share of speech time in turns below LOW_Q
MIN_MEAN_Q = 0.85         # window: speech-time-weighted mean turn quality
MIN_SPEAKERS = 3          # speakers with >= MIN_SPEAKER_S of speech
MIN_SPEAKER_S = 15
MAX_GAP_S = 20            # longer silences may hide unlabelled speech
PAD_S = 0.5
SEED = 0


def session_files(sid, cache):
    paths = {}
    for f in ["metadata.json", "speakers.txt", "speakers.segments.txt",
              "transcript.refined.json", "transcript.refined.map.json"]:
        paths[f] = hf_hub_download(REPO, f"{sid}/{f}", repo_type="dataset", local_dir=cache)
    return paths


def load_words(paths):
    """One row per aligned protocol word: word, start, end, speaker (protocol speaker id), prob, seg.
    The speaker is the one whose protocol char range contains the word."""
    segs = json.load(open(paths["transcript.refined.json"]))["segments"]
    smap = json.load(open(paths["transcript.refined.map.json"]))
    assert len(segs) == len(smap)
    ranges = np.loadtxt(paths["speakers.segments.txt"], dtype=np.int64, ndmin=2)  # speaker, start_char, end_char
    ranges = ranges[np.argsort(ranges[:, 1])]

    def speaker_at(char):
        k = np.searchsorted(ranges[:, 1], char, side="right") - 1
        return int(ranges[k, 0]) if k >= 0 and char < ranges[k, 2] else None

    rows = []
    for i, (s, m) in enumerate(zip(segs, smap)):
        text, pos = s["text"], 0
        for w in s.get("words") or []:
            found = text.find(w["word"].strip(), pos)
            if found >= 0:
                pos = found + len(w["word"].strip())
            rows.append(dict(word=w["word"].strip(), start=w["start"], end=w["end"], prob=w["probability"], seg=i,
                             speaker=speaker_at(m["start_char"] + (found if found >= 0 else pos))))
    return pd.DataFrame(rows)


def load_segments(paths):
    """Speaker turns: consecutive words of one speaker within a segment form one turn."""
    words = load_words(paths)
    key = (words["seg"] != words["seg"].shift()) | (words["speaker"] != words["speaker"].shift())
    words["turn"] = key.cumsum()
    df = words.groupby("turn").agg(start=("start", "first"), end=("end", "last"), speaker=("speaker", "first"),
                                   q=("prob", "median")).reset_index(drop=True)
    df["n_spk"] = df["speaker"].notna().astype(int)  # 0 = word outside every speaker range
    return df.sort_values("start").reset_index(drop=True)


def write_reference_words(paths, clip, t0, t1):
    """Word-level reference (text + speaker + time, relative to clip start) for speaker-attributed WER."""
    w = load_words(paths)
    w = w[(w["start"] >= t0) & (w["end"] <= t1)].copy()
    w["start"] -= t0
    w["end"] -= t0
    w["speaker"] = "spk" + w["speaker"].astype(str)
    os.makedirs(os.path.join(OUT_DIR, "ref_words"), exist_ok=True)
    w[["word", "start", "end", "speaker"]].to_csv(os.path.join(OUT_DIR, "ref_words", f"{clip}.csv"), index=False)


def best_window(df):
    """Contiguous run of segments ~WINDOW_S long passing all filters; prefer most speaker changes."""
    best, best_score = None, -1
    starts, ends = df["start"].values, df["end"].values
    for i in range(len(df)):
        j = np.searchsorted(ends, starts[i] + WINDOW_S, side="right") - 1
        if j <= i or ends[j] - starts[i] < WINDOW_S * 0.9:
            continue
        w = df.iloc[i:j + 1]
        dur = w["end"] - w["start"]
        if (w["n_spk"] != 1).any() or dur[w["q"] < LOW_Q].sum() > MAX_LOW_Q_SHARE * dur.sum() \
                or (w["q"] * dur).sum() < MIN_MEAN_Q * dur.sum():
            continue
        if (w["start"].values[1:] - w["end"].values[:-1]).max(initial=0) > MAX_GAP_S:
            continue
        talk = (w["end"] - w["start"]).groupby(w["speaker"]).sum()
        if (talk >= MIN_SPEAKER_S).sum() < MIN_SPEAKERS:
            continue
        score = (w["speaker"].values[1:] != w["speaker"].values[:-1]).sum()
        if score > best_score:
            best, best_score = (i, j), score
    return best


def cut_audio(sid, cache, t0, t1, out_wav):
    m4a = hf_hub_download(REPO, f"{sid}/audio.m4a", repo_type="dataset", local_dir=cache)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", m4a,
                    "-ac", "1", "-ar", "16000", out_wav], check=True)
    os.remove(m4a)  # sessions are ~100 MB each; keep only the clip


def rebuild_references():
    """Regenerate ref_words/ for the clips already in clips.csv (from the cached session files)."""
    cache = os.path.join(OUT_DIR, "_cache")
    for r in pd.read_csv(os.path.join(OUT_DIR, "clips.csv")).itertuples():
        paths = session_files(str(r.session), cache)
        write_reference_words(paths, r.clip, r.offset_s, r.offset_s + r.duration_s)
        print(r.clip)


def main():
    if "--refs-only" in sys.argv:
        return rebuild_references()
    for sub in ["wav", "rttm", "uem"]:
        os.makedirs(os.path.join(OUT_DIR, sub), exist_ok=True)
    cache = os.path.join(OUT_DIR, "_cache")
    sessions = sorted(e.path for e in HfApi().list_repo_tree(REPO, repo_type="dataset") if "." not in e.path)
    random.Random(SEED).shuffle(sessions)
    print(f"{len(sessions)} sessions in repo")

    clips = []
    for sid in sessions[:MAX_SESSIONS_TRIED]:
        if len(clips) >= N_CLIPS:
            break
        try:
            paths = session_files(sid, cache)
        except Exception as e:
            print(f"{sid}: skip ({type(e).__name__})")
            continue
        df = load_segments(paths)
        win = best_window(df)
        if win is None:
            print(f"{sid}: no valid window")
            continue
        w = df.iloc[win[0]:win[1] + 1]
        t0, t1 = max(0.0, w["start"].iloc[0] - PAD_S), w["end"].iloc[-1] + PAD_S
        clip = f"knesset_{sid}_{int(t0)}"
        cut_audio(sid, cache, t0, t1, os.path.join(OUT_DIR, "wav", f"{clip}.wav"))
        with open(os.path.join(OUT_DIR, "rttm", f"{clip}.rttm"), "w") as f:
            for r in w.itertuples():
                f.write(f"SPEAKER {clip} 1 {r.start - t0:.3f} {r.end - r.start:.3f} <NA> <NA> spk{r.speaker} <NA> <NA>\n")
        with open(os.path.join(OUT_DIR, "uem", f"{clip}.uem"), "w") as f:
            f.write(f"{clip} 1 0.000 {t1 - t0:.3f}\n")
        write_reference_words(paths, clip, t0, t1)
        meta = json.load(open(paths["metadata.json"]))
        talk = (w["end"] - w["start"]).groupby(w["speaker"]).sum()
        clips.append(dict(clip=clip, session=sid, offset_s=round(t0, 2), duration_s=round(t1 - t0, 2),
                          n_speakers=len(talk), n_speakers_15s=int((talk >= MIN_SPEAKER_S).sum()),
                          speaker_changes=int((w["speaker"].values[1:] != w["speaker"].values[:-1]).sum()),
                          mean_q=round((w["q"] * (w["end"] - w["start"])).sum() / (w["end"] - w["start"]).sum(), 3), committee=meta.get("committee_name"),
                          date=meta.get("session_date"), title=meta.get("title")))
        print(f"{sid}: {clip} {len(talk)} speakers, {clips[-1]['speaker_changes']} changes")

    pd.DataFrame(clips).to_csv(os.path.join(OUT_DIR, "clips.csv"), index=False)
    print(f"{len(clips)} clips -> {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
