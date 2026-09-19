"""Hour-0 check without hardware (spec §3): run the focus-index feature on the public Wang et al. (2013) EEG confusion
dataset (Kaggle "EEG brainwave dataset: confusion", file EEG_data.csv), split by subject and video.

Per (subject, video): mean ln E with E = (Beta1+Beta2)/(Alpha1+Alpha2+Theta); z-scored within subject; the score for
"confused" is -z. Reports AUC against the user-defined label and the predefined label. Distrust anything above ~0.75.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict


def auc(scores: list[float], labels: list[int]) -> float:
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    for p in pos:
        for q in neg:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(pos) * len(neg))


def run(path: str) -> dict:
    rows = list(csv.DictReader(open(path, newline="")))
    if not rows:
        raise SystemExit("empty csv")
    cols = {c.lower().replace(" ", ""): c for c in rows[0].keys()}

    def col(*names: str) -> str:
        for n in names:
            if n in cols:
                return cols[n]
        raise SystemExit(f"missing column among {names}; have {list(cols)}")

    c_sub, c_vid = col("subjectid", "subject"), col("videoid", "video")
    c_th, c_a1, c_a2, c_b1, c_b2 = col("theta"), col("alpha1"), col("alpha2"), col("beta1"), col("beta2")
    c_user = col("user-definedlabeln", "user-definedlabel", "userdefinedlabeln", "userdefinedlabel")
    c_pre = col("predefinedlabel")
    acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    lab_u: dict[tuple[str, str], int] = {}
    lab_p: dict[tuple[str, str], int] = {}
    for r in rows:
        try:
            th, a1, a2, b1, b2 = (float(r[c]) for c in (c_th, c_a1, c_a2, c_b1, c_b2))
        except ValueError:
            continue
        denom = a1 + a2 + th
        if denom <= 0 or (b1 + b2) <= 0:
            continue
        k = (r[c_sub], r[c_vid])
        acc[k].append(math.log((b1 + b2) / denom))
        lab_u[k] = int(float(r[c_user]))
        lab_p[k] = int(float(r[c_pre]))
    per_sub: dict[str, list[tuple[tuple[str, str], float]]] = defaultdict(list)
    for k, xs in acc.items():
        per_sub[k[0]].append((k, sum(xs) / len(xs)))
    scores, yu, yp = [], [], []
    for _sub, items in per_sub.items():
        m = sum(v for _, v in items) / len(items)
        sd = math.sqrt(sum((v - m) ** 2 for _, v in items) / max(1, len(items) - 1)) or 1.0
        for k, v in items:
            scores.append(-(v - m) / sd)
            yu.append(lab_u[k])
            yp.append(lab_p[k])
    return {
        "subject_videos": len(scores),
        "subjects": len(per_sub),
        "auc_user_label": round(auc(scores, yu), 3),
        "auc_predefined_label": round(auc(scores, yp), 3),
        "note": "chance = 0.5; published band-power detectors reach about 0.65; distrust > 0.75",
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: reflow kaggle-check PATH/EEG_data.csv")
        return 2
    res = run(argv[0])
    for k, v in res.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
