"""Run a pyannote pipeline on every benchmark clip and write hypothesis RTTMs.

    python run_pyannote.py [--model pyannote/speaker-diarization-3.1] [--out hyp/pyannote-3.1]
"""
import os, time, argparse
import torch
import pandas as pd
from pyannote.audio import Pipeline

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="pyannote/speaker-diarization-3.1")
    ap.add_argument("--ref", default=os.path.join(HERE, "data", "knesset"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(HERE, "hyp", a.model.split("/")[-1])
    os.makedirs(out, exist_ok=True)

    pipeline = Pipeline.from_pretrained(a.model)
    pipeline.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    timing = []
    wav_dir = os.path.join(a.ref, "wav")
    for f in sorted(os.listdir(wav_dir)):
        clip = f[:-4]
        t = time.time()
        result = pipeline(os.path.join(wav_dir, f))
        annotation = getattr(result, "speaker_diarization", result)  # pyannote 4.x returns DiarizeOutput
        annotation.uri = clip
        with open(os.path.join(out, f"{clip}.rttm"), "w") as fh:
            annotation.write_rttm(fh)
        timing.append(dict(clip=clip, seconds=round(time.time() - t, 2)))
        print(f"{clip}: {len(annotation.labels())} speakers, {timing[-1]['seconds']}s")
    pd.DataFrame(timing).to_csv(os.path.join(out, "timing.csv"), index=False)


if __name__ == "__main__":
    main()
