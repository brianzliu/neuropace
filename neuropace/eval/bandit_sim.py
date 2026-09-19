"""How fast can NeuroPace tell which explanation works, given a noisy focus signal?
Each 'card' = one explanation variant of one concept. True outcome: learner got it (1) or not (0).
Signals: quiz = true outcome (1 question per card). eeg = noisy flag of 'lost focus', which itself only
partly tracks the outcome. sens/spec 0.62 ~ AUC 0.65 detector.  Thompson sampling, Beta(1,1) priors."""

import numpy as np

rng = np.random.default_rng(3)


def run(p_true, n_cards, signal, sens=0.62, spec=0.62, sims=3000):
    k = len(p_true)
    best = int(np.argmax(p_true))
    hit = 0
    got = 0
    for _ in range(sims):
        a = np.ones(k)
        b = np.ones(k)
        for t in range(n_cards):
            arm = int(np.argmax(rng.beta(a, b)))
            y = rng.random() < p_true[arm]
            got += y
            eeg_ok = (rng.random() < spec) if y else (rng.random() >= sens)  # eeg says "stayed focused"
            if signal == "quiz":
                r = [float(y)]
            elif signal == "eeg":
                r = [float(eeg_ok)]
            else:
                r = [float(y), float(eeg_ok)]
            for x in r:
                a[arm] += x
                b[arm] += 1 - x
        hit += int(np.argmax(a / (a + b)) == best)
    return hit / sims, got / (sims * n_cards)


if __name__ == "__main__":
    p = [0.75, 0.55, 0.55, 0.55]  # one variant clearly better
    print("P(pick best variant) | mean success rate   [uniform random play = 0.25 | 0.60]")
    for n in (12, 24, 60, 150, 400):
        print(f"cards={n:4d}", {s: tuple(round(v, 2) for v in run(p, n, s)) for s in ("quiz", "eeg", "both")})
