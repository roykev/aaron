"""Score speaker-attributed transcription: transcription and diarization together.

    python score_sa_asr.py <system_dir> [<system_dir> ...] [--ref data/knesset] [--collar 0.5]

<system_dir>/<clip>/transcript_speakers.csv  (start, end, speaker, text)  -- audio.transcription.pipeline output
<system_dir>/<clip>/diarization_turns.csv    (start, end, speaker)        -- for DER

Metrics (all in %, lower is better):
  WER    transcription only: all words in time order, speakers ignored
  cpWER  transcription + speakers: each speaker's words concatenated, best speaker mapping
         (Hungarian), errors / reference words  [CHiME-6 / NOTSOFAR metric]
  WDER   of the words recognized (correct or substituted), share attributed to the wrong speaker
         under the cpWER mapping
  DER    diarization only, time-based (pyannote.metrics), collar --collar

Caveat: the reference is the Knesset protocol, edited into formal Hebrew rather than verbatim, so absolute
WER/cpWER are inflated for every system; compare systems with each other.
"""
import os
import re
import argparse
import unicodedata
import numpy as np
import pandas as pd
import jiwer
from scipy.optimize import linear_sum_assignment
from pyannote.core import Annotation, Segment, Timeline
from pyannote.database.util import load_rttm, load_uem
from pyannote.metrics.diarization import DiarizationErrorRate

HERE = os.path.dirname(os.path.abspath(__file__))
NIQQUD = re.compile("[֑-ׇ]")


def norm_words(text):
    text = NIQQUD.sub("", unicodedata.normalize("NFKC", str(text))).lower()
    text = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text)
    return text.split()


def word_table(df, text_col):
    """One row per normalized word: speaker, time (for ordering)."""
    rows = []
    for r in df.itertuples():
        for w in norm_words(getattr(r, text_col)):
            rows.append((r.start, r.speaker, w))
    return pd.DataFrame(rows, columns=["start", "speaker", "word"]).sort_values("start", kind="stable")


def errors(ref_words, hyp_words):
    if not ref_words:
        return len(hyp_words)
    if not hyp_words:
        return len(ref_words)
    o = jiwer.process_words(" ".join(ref_words), " ".join(hyp_words))
    return o.substitutions + o.deletions + o.insertions


def cp_wer(ref, hyp):
    """Returns (errors, n_ref_words, mapping hyp_speaker -> ref_speaker)."""
    rs, hs = list(ref["speaker"].unique()), list(hyp["speaker"].unique())
    rw = {s: ref.loc[ref.speaker == s, "word"].tolist() for s in rs}
    hw = {s: hyp.loc[hyp.speaker == s, "word"].tolist() for s in hs}
    R, H, BIG = len(rs), len(hs), 10 ** 9
    # square (R+H) matrix: [ref x hyp errors | ref unmatched] / [hyp unmatched | 0]
    cost = np.full((R + H, H + R), BIG, dtype=np.int64)
    for i, r in enumerate(rs):
        for j, h in enumerate(hs):
            cost[i, j] = errors(rw[r], hw[h])
        cost[i, H + i] = len(rw[r])                   # ref speaker matched to nobody: all deleted
    for j, h in enumerate(hs):
        cost[R + j, j] = len(hw[h])                   # hyp speaker matched to nobody: all inserted
    cost[R:, H:] = 0
    row, col = linear_sum_assignment(cost)
    mapping = {hs[c]: rs[r] for r, c in zip(row, col) if r < R and c < H}
    return int(cost[row, col].sum()), len(ref), mapping


def wder(ref, hyp, mapping):
    out = jiwer.process_words(" ".join(ref["word"]), " ".join(hyp["word"]))
    rspk, hspk = ref["speaker"].tolist(), hyp["speaker"].tolist()
    pairs = wrong = 0
    for chunk in out.alignments[0]:
        if chunk.type in ("equal", "substitute"):
            for k in range(chunk.ref_end_idx - chunk.ref_start_idx):
                pairs += 1
                wrong += mapping.get(hspk[chunk.hyp_start_idx + k]) != rspk[chunk.ref_start_idx + k]
    return wrong, pairs


def turns_annotation(df, uri):
    ann = Annotation(uri=uri)
    for r in df.itertuples():
        if r.end > r.start:
            ann[Segment(r.start, r.end)] = r.speaker
    return ann


def score_system(sys_dir, ref_dir, collar):
    der = DiarizationErrorRate(collar=collar, skip_overlap=False)
    tot = dict(wer_err=0, cp_err=0, n=0, wd_wrong=0, wd_pairs=0)
    rows = []
    for f in sorted(os.listdir(os.path.join(ref_dir, "ref_words"))):
        clip = f[:-4]
        hyp_csv = os.path.join(sys_dir, clip, "transcript_speakers.csv")
        if not os.path.exists(hyp_csv):
            continue
        ref = word_table(pd.read_csv(os.path.join(ref_dir, "ref_words", f)), "word")
        hyp = word_table(pd.read_csv(hyp_csv).fillna({"speaker": "UNKNOWN", "text": ""}), "text")
        w_err = errors(ref["word"].tolist(), hyp["word"].tolist())
        c_err, n, mapping = cp_wer(ref, hyp)
        wrong, pairs = wder(ref, hyp, mapping)
        ref_ann = list(load_rttm(os.path.join(ref_dir, "rttm", f"{clip}.rttm")).values())[0]
        uem = load_uem(os.path.join(ref_dir, "uem", f"{clip}.uem"))[clip]
        hyp_ann = turns_annotation(pd.read_csv(os.path.join(sys_dir, clip, "diarization_turns.csv")), clip)
        d = der(ref_ann, hyp_ann, uem=uem)
        rows.append(dict(clip=clip, WER=100 * w_err / n, cpWER=100 * c_err / n, WDER=100 * wrong / max(pairs, 1),
                         DER=100 * d, ref_spk=ref["speaker"].nunique(), hyp_spk=hyp["speaker"].nunique()))
        for k, v in dict(wer_err=w_err, cp_err=c_err, n=n, wd_wrong=wrong, wd_pairs=pairs).items():
            tot[k] += v
    per_clip = pd.DataFrame(rows)
    summary = dict(system=os.path.basename(os.path.normpath(sys_dir)), clips=len(rows),
                   WER=100 * tot["wer_err"] / tot["n"], cpWER=100 * tot["cp_err"] / tot["n"],
                   WDER=100 * tot["wd_wrong"] / max(tot["wd_pairs"], 1), DER=100 * abs(der),
                   spk_count_exact=100 * (per_clip.ref_spk == per_clip.hyp_spk).mean())
    return summary, per_clip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+")
    ap.add_argument("--ref", default=os.path.join(HERE, "data", "knesset"))
    ap.add_argument("--collar", type=float, default=0.5)
    a = ap.parse_args()
    summaries = []
    for s in a.systems:
        summary, per_clip = score_system(s, a.ref, a.collar)
        per_clip.round(2).to_csv(os.path.join(s, "sa_asr_scores.csv"), index=False)
        summaries.append(summary)
    df = pd.DataFrame(summaries).set_index("system").round(1)
    pd.set_option("display.width", 200)
    print(df.to_string())
    print(f"\n% , lower is better (spk_count_exact: higher). Reference = non-verbatim protocol; compare systems.")


if __name__ == "__main__":
    main()
