"""Crowd 'loss map': can N noisy single-electrode learners locate the bad segment of an explanation?
Per learner, per segment: z-scored focus-drop score ~ N(0,1); if the segment truly loses that learner, mean = dprime.
dprime 0.545 <=> single-learner AUC 0.65.  q = fraction of learners the bad segment actually loses.
A good segment still loses a learner with prob base (random mind-wandering)."""

import numpy as np

rng = np.random.default_rng(5)


def sim(N, S=9, q=0.6, base=0.2, dprime=0.545, sims=4000):
    top1 = top2 = 0
    for _ in range(sims):
        lost = rng.random((N, S)) < base
        lost[:, 0] = rng.random(N) < q
        m = (rng.normal(0, 1, (N, S)) + dprime * lost).mean(0)
        r = (m > m[0]).sum()
        top1 += r == 0
        top2 += r <= 1
    return round(float(top1 / sims), 2), round(float(top2 / sims), 2)


if __name__ == "__main__":
    print("P(planted-bad segment ranked #1, top-2) of 9 segments; chance = 0.11, 0.22")
    for dp, label in ((0.545, "AUC .65 sensor"), (1.0, "AUC .76 (EEG + heart pad + quiz miss fused)")):
        print(label)
        for N in (1, 6, 10, 12, 20, 40):
            print(f"  N={N:3d}  q=0.6:{sim(N, dprime=dp)}  q=0.9:{sim(N, q=0.9, dprime=dp)}")
    print("5 segments (chance 0.20, 0.40) - the table in REFLOW.md")
    for dp in (0.545, 1.0):
        for N in (6, 12, 20):
            print(
                f"  dprime={dp} N={N:2d}  q=0.6:{sim(N, S=5, dprime=dp)}  q=0.9:{sim(N, S=5, q=0.9, dprime=dp)}"
            )
