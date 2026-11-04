"""Compare faster-whisper models on Hebrew and English test sets (WER + language detection + speed).

Decoding settings mirror v_indexer production (src/main/config.yaml -> transcription).
Language is auto-detected (language=None) as in production, so detection errors count against WER.

    python compare_whisper.py [--n 150]
"""
import os, re, time, argparse, unicodedata, subprocess, tempfile, shutil
import numpy as np
import pandas as pd
import jiwer
from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

MODELS = {
    "stock-large-v3-turbo": "large-v3-turbo",
    "ivrit-large-v3-turbo": "ivrit-ai/whisper-large-v3-turbo-ct2",
}
# set name -> expected language; audio + reference text listed in data/manifest.csv
SETS = {"fleurs-he": "he", "fleurs-en": "en", "ivrit-eval-d1": "he", "ivrit-eval-whatsapp": "he"}
PROD = dict(compute_type="float16", device="cuda", beam_size=5, best_of=5, temperature=0.0, vad_filter=True)
NIQQUD = re.compile("[֑-ׇ]")


def normalize(text):
    text = NIQQUD.sub("", unicodedata.normalize("NFKC", text)).lower()
    text = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text)
    return " ".join(text.split())


def load_set(manifest, name, n, seed=0):
    m = manifest[manifest["set"] == name]
    m = m.sample(n=min(n, len(m)), random_state=seed)
    return [(os.path.join(HERE, p), t) for p, t in zip(m["path"], m["text"])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--normalize", default=None, help='ffmpeg loudness filter applied first, e.g. "dynaudnorm=f=250:g=15:m=30"')
    ap.add_argument("--out", default="results.csv")
    a = ap.parse_args()
    manifest = pd.read_csv(os.path.join(DATA, "manifest.csv"))
    data = {k: load_set(manifest, k, a.n) for k in SETS if k in set(manifest["set"])}
    print({k: len(v) for k, v in data.items()})

    tmpdir = tempfile.mkdtemp(prefix="asr_norm_")
    rows = []
    for mname, mpath in MODELS.items():
        model = WhisperModel(mpath, device=PROD["device"], compute_type=PROD["compute_type"])
        for sname, items in data.items():
            refs, hyps, langs, audio_s, t0 = [], [], [], 0.0, time.time()
            for audio, ref in items:
                if a.normalize:
                    tmp = os.path.join(tmpdir, "norm.wav")
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", audio, "-af", a.normalize,
                                    "-ac", "1", "-ar", "16000", tmp], check=True)
                    audio = tmp
                segs, info = model.transcribe(audio, language=None, beam_size=PROD["beam_size"],
                                              best_of=PROD["best_of"], temperature=PROD["temperature"],
                                              vad_filter=PROD["vad_filter"])
                hyps.append(normalize(" ".join(s.text for s in segs)))
                refs.append(normalize(ref))
                langs.append(info.language)
                audio_s += info.duration
            elapsed = time.time() - t0
            keep = [i for i, r in enumerate(refs) if r]
            wer = jiwer.wer([refs[i] for i in keep], [hyps[i] or "<empty>" for i in keep])
            exp = SETS[sname]
            rows.append(dict(model=mname, set=sname, n=len(items), WER=round(100 * wer, 1),
                             lang_correct=round(100 * np.mean([l == exp for l in langs]), 1),
                             detected=dict(pd.Series(langs).value_counts().head(3)),
                             xRT=round(audio_s / elapsed, 1)))
            print(rows[-1])
        del model
    shutil.rmtree(tmpdir, ignore_errors=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, a.out), index=False)
    pd.set_option("display.width", 200)
    print("\n", df.pivot(index="set", columns="model", values="WER").to_string())
    print("\nlanguage detected correctly (%):\n", df.pivot(index="set", columns="model", values="lang_correct").to_string())


if __name__ == "__main__":
    main()
