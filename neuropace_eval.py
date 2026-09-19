"""reflow_eval.py - honest-numbers toolkit for Reflow (numpy only).

  gate      : is a probe-labelled feature real?  permutation test on block labels
  detector  : does the state detector agree with thought probes?  confusion + exact binomial
  outcome   : does a SENSOR-TIMED reflow beat a YOKED RANDOM-TIMED one?  paired perm + bootstrap CI
  selftest  : runs all three on simulated data with known ground truth

THE TRAP THIS FILE EXISTS TO AVOID (plan section 9): Szafir & Mutlu 2012 ran the closest published
study to Reflow - NeuroSky at FP1, engagement index, real-time attention cues. Adaptive cues beat
the NO-CUE baseline (p=.022) but did NOT beat RANDOM-TIMED cues (p=.118). So comparing "Reflow on"
against "plain text" proves only that interventions help; it proves nothing about the sensor, which
is the entire claim. Every `outcome` call must therefore be sensor-timed vs a yoked random-timed
control: same interventions, same count, times drawn from another participant's trigger
distribution. Pass those two conditions as `a` and `b`.

Committed BEFORE the data exists, so the analysis is frozen first.

Known and accepted (see the plan, section 8):
  - detector_vs_probes estimates the majority rate from the same data it tests, which is mildly
    anti-conservative, and treats probes as independent. Correct for a PER-WEARER claim; if you
    pool across participants, say so in the caption (within-subject correlation is not modelled).
  - rng is module-level with a fixed seed: reproducible, but repeated calls in one process are
    not independent draws.
"""
import sys, json, math, numpy as np
rng = np.random.default_rng(7)

def cohens_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2: return float("nan")
    sp = math.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) / (len(a)+len(b)-2))
    return (a.mean()-b.mean())/sp if sp > 0 else 0.0

def perm_gate(on_task, lapse, n_perm=5000, alpha=0.10, d_min=0.5):
    """Each element = ONE probe window (mean feature over the 15 s before a probe).
    Windows, not 1 Hz samples, are the unit: samples inside a window are autocorrelated."""
    d = cohens_d(lapse, on_task)
    pool = np.concatenate([on_task, lapse]); k = len(on_task); hits = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        if abs(cohens_d(pool[k:], pool[:k])) >= abs(d): hits += 1
    p = (hits+1)/(n_perm+1)
    return {"d": round(float(d),3), "p_perm": round(p,4), "n_on": len(on_task), "n_lapse": len(lapse),
            "use": bool(abs(d) >= d_min and p <= alpha), "sign": 1 if d > 0 else -1}

def binom_tail(k, n, p):  # P(X >= k)
    return sum(math.comb(n,i)*p**i*(1-p)**(n-i) for i in range(k, n+1))

def detector_vs_probes(pred, truth):
    pred, truth = np.asarray(pred, bool), np.asarray(truth, bool)
    tp=int((pred&truth).sum()); fp=int((pred&~truth).sum()); fn=int((~pred&truth).sum()); tn=int((~pred&~truth).sum())
    n=len(truth); acc=(tp+tn)/n; base=max(truth.mean(), 1-truth.mean())
    return {"tp":tp,"fp":fp,"fn":fn,"tn":tn,"n":n,"accuracy":round(acc,3),"majority_baseline":round(float(base),3),
            "p_vs_baseline":round(binom_tail(tp+tn,n,float(base)),4),
            "recall_of_lapses": round(tp/max(tp+fn,1),3), "precision": round(tp/max(tp+fp,1),3)}

def paired_outcome(a, b, n_perm=10000, n_boot=5000):
    """a,b = one value per participant in two PAIRED conditions, a = sensor-timed, b = yoked random.
    Works for any outcome on a common scale: proportion of checkpoints correct, or (negated)
    seconds-to-return-to-FLOW. Sign-flip permutation + percentile bootstrap CI.
    See the module docstring: `b` must be the yoked random-timing control, not a no-intervention
    baseline, or the result says nothing about the sensor."""
    diff = np.asarray(a,float)-np.asarray(b,float); obs = diff.mean()
    flips = rng.choice([-1,1], size=(n_perm, len(diff)))
    p = (np.sum(np.abs((flips*diff).mean(1)) >= abs(obs))+1)/(n_perm+1)
    boots = rng.choice(diff, size=(n_boot, len(diff)), replace=True).mean(1)
    return {"n":len(diff),"mean_diff":round(float(obs),3),"ci95":[round(float(np.percentile(boots,2.5)),3),round(float(np.percentile(boots,97.5)),3)],"p_perm":round(float(p),4)}

def power(n, gap, n_items=8, base=0.70, sims=1500, between_sd=0.12, n_perm=2000):
    """Study planning: power to detect 'sensor-timed beats yoked random' with `n` participants and
    `n_items` scored checkpoints per condition per person. `gap` is the true advantage in points.
    The dominant error term is binomial noise on a per-person proportion built from few items, so
    the cheapest way to buy power is more checkpoints per person, not only more people."""
    hits = 0
    for _ in range(sims):
        abil = np.clip(rng.normal(base, between_sd, n), .05, .95)
        obs_a = rng.binomial(n_items, np.clip(abil, .02, .98))/n_items
        obs_b = rng.binomial(n_items, np.clip(abil-gap, .02, .98))/n_items
        diff = obs_a - obs_b; obs = diff.mean()
        flips = rng.choice([-1,1], size=(n_perm, n))
        if (np.sum(np.abs((flips*diff).mean(1)) >= abs(obs))+1)/(n_perm+1) <= 0.05: hits += 1
    return round(hits/sims, 3)

def selftest():
    ok = True
    # gate: real effect d~1.2 with 12 v 8 windows should pass; null should fail most of the time
    g = perm_gate(rng.normal(0,1,12), rng.normal(1.4,1,8)); print("gate real :", g); ok &= g["use"]
    fp = np.mean([perm_gate(rng.normal(0,1,12), rng.normal(0,1,8), n_perm=400)["use"] for _ in range(300)])
    print("gate null false-pass rate (12v8 windows, perm p<=.10 AND |d|>=.5): %.3f" % fp); ok &= fp < 0.15
    # naive rule (|d|>=0.5 only) under the null, for comparison
    for k in (4,8,12,20):
        r = np.mean([abs(cohens_d(rng.normal(0,1,k), rng.normal(0,1,k)))>=0.5 for _ in range(4000)])
        print("  naive rule |d|>=0.5 alone, %2d v %2d independent windows, null false-pass: %.2f" % (k,k,r))
    # detector
    truth = rng.random(40) < 0.35; pred = np.where(rng.random(40)<0.75, truth, ~truth)
    print("detector  :", detector_vs_probes(pred, truth))
    # outcome: 8 participants, sensor-timed beats yoked random by 20 points
    a = np.clip(rng.normal(0.72,0.12,8),0,1); b = np.clip(a-0.20+rng.normal(0,0.10,8),0,1)
    o = paired_outcome(a,b); print("outcome   :", o); ok &= o["mean_diff"] > 0
    print("SELFTEST", "PASS" if ok else "FAIL"); return 0 if ok else 1

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv)>1 else "selftest"
    if cmd == "selftest": sys.exit(selftest())
    if cmd == "power":
        print("n    " + "  ".join("gap=%dpt" % (g*100) for g in (.15,.25,.35)))
        for n in (6,8,10,12,14):
            print("%-4d " % n + "  ".join("%6.0f%%" % (power(n,g)*100) for g in (.15,.25,.35)))
        sys.exit(0)
    data = json.load(open(sys.argv[2]))
    fn = {"gate": lambda d: perm_gate(d["on_task"], d["lapse"]),
          "detector": lambda d: detector_vs_probes(d["pred"], d["truth"]),
          "outcome": lambda d: paired_outcome(d["a"], d["b"])}[cmd]
    print(json.dumps(fn(data), indent=2))
