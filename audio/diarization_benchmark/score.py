"""Score diarization hypotheses against the benchmark reference.

    python score.py <hyp_rttm_dir> [--ref data/knesset] [--collar 0.5]

Hypothesis dir holds one <clip>.rttm per clip (any model). Prints DER (with breakdown) and JER per clip
and in total, and writes <hyp_rttm_dir>/scores.csv.
"""
import os, argparse
import pandas as pd
from pyannote.database.util import load_rttm, load_uem
from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

HERE = os.path.dirname(os.path.abspath(__file__))


def load_one(path, clip):
    d = load_rttm(path)
    return d.get(clip) or next(iter(d.values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hyp_dir")
    ap.add_argument("--ref", default=os.path.join(HERE, "data", "knesset"))
    ap.add_argument("--collar", type=float, default=0.5)
    a = ap.parse_args()

    der = DiarizationErrorRate(collar=a.collar, skip_overlap=False)
    jer = JaccardErrorRate(collar=a.collar, skip_overlap=False)
    rows = []
    for f in sorted(os.listdir(os.path.join(a.ref, "rttm"))):
        clip = f[:-5]
        hyp_path = os.path.join(a.hyp_dir, f)
        if not os.path.exists(hyp_path):
            print(f"missing hypothesis for {clip}")
            continue
        ref = load_one(os.path.join(a.ref, "rttm", f), clip)
        hyp = load_one(hyp_path, clip)
        uem = load_uem(os.path.join(a.ref, "uem", f"{clip}.uem"))[clip]
        c = der(ref, hyp, uem=uem, detailed=True)
        j = jer(ref, hyp, uem=uem)
        rows.append(dict(clip=clip, DER=c["diarization error rate"], miss=c["missed detection"] / c["total"],
                         false_alarm=c["false alarm"] / c["total"], confusion=c["confusion"] / c["total"],
                         JER=j, ref_spk=len(ref.labels()), hyp_spk=len(hyp.labels())))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.hyp_dir, "scores.csv"), index=False)
    pd.set_option("display.width", 200)
    print(df.round(3).to_string(index=False))
    tot = der[:]  # accumulated components
    print(f"\nTOTAL (collar {a.collar}s, {len(df)} clips): DER {abs(der):.1%}  "
          f"miss {tot['missed detection'] / tot['total']:.1%}  FA {tot['false alarm'] / tot['total']:.1%}  "
          f"confusion {tot['confusion'] / tot['total']:.1%}  JER {abs(jer):.1%}  "
          f"speaker-count exact {(df.ref_spk == df.hyp_spk).mean():.0%}")


if __name__ == "__main__":
    main()
