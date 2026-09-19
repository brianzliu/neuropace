"""Live view of the MindWave signal pipeline.

    python monitor.py                       # the headset on COM3
    python monitor.py --fake                # simulated EEG, no headset needed
    python monitor.py --replay sessions/<stamp> [--speed 2]
    python monitor.py --ws                  # also serve the WebSocket feed on :8765

Three panels, top to bottom:

  1. LIVE EEG      the last 4 s. Red = blink or movement the detector masked out of the analysis.
  2. EFFORT/ENGAGE the last 2 minutes. Effort (theta/alpha) is how hard the brain is working;
                   engagement (beta/(alpha+theta)) is how switched-on it is. Before calibration
                   these are raw index units; after it they are z-scores, easy ~ -1, hard ~ +1.
  3. BAND POWER    log10 power in theta / alpha / beta / gamma right now.

Start with --fake to learn the display, then put the headset on. In --fake, keys c/e/h/d/o set
the simulated state and the banner tells you what each one should look like; nothing is recorded.

Go/no-go on your own head: see GO_NO_GO below, or the project README.
"""
from __future__ import annotations

import argparse
import time

import matplotlib.pyplot as plt
import numpy as np

from mindwave import Pipeline
from mindwave.keys import CAL_KEYS, FAKE_KEYS, apply_key
from mindwave.sources import FakeSource
from run_pipeline import add_source_args, build_source, log_dir_for

HIST = 120          # seconds of index history
WIN = 4.0           # seconds of raw trace
DECIM = 4           # plot every Nth sample: 2048 -> 512 points, blinks still obvious
FAST_MS = 60        # trace refresh (blitted, cheap)
GOOD_Q = 50         # poor_signal above this = no usable contact

GO_NO_GO = """go/no-go, headset on your head:
  1  quality reaches 0-30 within ~20 s
  2  five deliberate blinks -> five red marks
  3  press 1, eyes closed 10 s; press 2, easy reading 25 s  -> alpha closed/open >= 1.5x
  4  press 3, count down from 1000 by 7s OUT LOUD 25 s; press 0  -> effort hard > easy"""

FAKE_HINT = {
    "eyes_closed": "alpha bar tall, effort LOW",
    "easy": "the baseline - everything mid",
    "hard": "theta up, alpha down, effort HIGH",
    "drowsy": "blinks frequent, blink rate climbs",
    "off": "INVALID - electrode off the skin",
}
KEYS_LINE = ("calibrate:  1 eyes-closed   2 easy   3 hard   0 done   r reset   a auto (10/25/25 s)"
             "          q quit")
KEYS_FAKE = "simulate:   c closed   e easy   h hard   d drowsy   o off-head   b blink"


def _f(v, fmt="{:+.2f}", dash="  --"):
    return dash if v is None else fmt.format(v)


class Monitor:
    """Fast path blits the EEG trace only. Everything else redraws once per FeatureFrame (1 Hz),
    which is also the only place y-limits change - limits must stay put between blits."""

    def __init__(self, pipe: Pipeline, source) -> None:
        self.pipe, self.source = pipe, source
        self.fake = isinstance(source, FakeSource)
        self._bg = None
        self._last_n = -1
        self._ylim = 100.0
        self._closing = False
        self._build()

    # ---- layout ----------------------------------------------------------------------------

    def _build(self) -> None:
        self.fig = fig = plt.figure(figsize=(12.6, 8.6))
        fig.canvas.manager.set_window_title("MindWave monitor")
        try:    # free c/h/o/a/e from matplotlib's default key bindings
            fig.canvas.mpl_disconnect(fig.canvas.manager.key_press_handler_id)
        except Exception:
            pass
        gs = fig.add_gridspec(3, 2, width_ratios=[3.05, 1], height_ratios=[2, 2, 1.15],
                              left=0.065, right=0.985, top=0.855, bottom=0.115,
                              hspace=0.62, wspace=0.03)
        self.ax_raw = fig.add_subplot(gs[0, 0])
        self.ax_idx = fig.add_subplot(gs[1, 0])
        self.ax_band = fig.add_subplot(gs[2, 0])
        self.ax_txt = fig.add_subplot(gs[:, 1]); self.ax_txt.axis("off")

        self.banner = fig.text(0.065, 0.945, "starting...", fontsize=15, weight="bold",
                               family="monospace", va="center",
                               bbox=dict(boxstyle="round,pad=0.45", fc="#e8e8e8", ec="none"))
        self.subbanner = fig.text(0.065, 0.893, "", fontsize=9.5, family="monospace",
                                  va="center", color="#444")
        fig.text(0.065, 0.055, KEYS_LINE, fontsize=8.6, family="monospace", color="#333")
        if self.fake:
            fig.text(0.065, 0.025, KEYS_FAKE, fontsize=8.6, family="monospace", color="#333")

        # 1. raw trace
        n = int(WIN * self.pipe.fs) // DECIM
        t = np.linspace(-WIN, 0, n)
        self.l_raw, = self.ax_raw.plot(t, np.zeros(n), lw=0.7, color="#1f77b4", animated=True)
        self.l_art, = self.ax_raw.plot(t, np.full(n, np.nan), lw=1.6, color="#d62728", animated=True)
        self.ax_raw.set_xlim(-WIN, 0)
        self.ax_raw.set_ylim(-self._ylim, self._ylim)
        self.ax_raw.set_ylabel("µV")
        self.ax_raw.set_title("1 · LIVE EEG   —   last 4 seconds.   red = blink / movement, "
                              "excluded from the analysis", loc="left", fontsize=10.5, pad=6)
        self.ax_raw.tick_params(labelsize=8)

        # 2. index history
        ht = np.arange(-HIST + 1, 1, dtype=float)
        nan = np.full(HIST, np.nan)
        self.l_eff, = self.ax_idx.plot(ht, nan.copy(), color="#ff7f0e", lw=0.9, alpha=0.4)
        self.l_eff_e, = self.ax_idx.plot(ht, nan.copy(), color="#ff7f0e", lw=2.4,
                                         label="effort  θ/α  (how hard the brain is working)")
        self.l_eng_e, = self.ax_idx.plot(ht, nan.copy(), color="#2ca02c", lw=2.4,
                                         label="engagement  β/(α+θ)")
        self.l_bad, = self.ax_idx.plot(ht, nan.copy(), ls="none", marker="|", ms=7,
                                       color="#999", label="no contact / artifact")
        self.ax_idx.axhline(0, color="#ccc", lw=0.8)
        self.ax_idx.set_xlim(-HIST, 0)
        self.ax_idx.set_ylim(-1, 1)
        self.ax_idx.set_xlabel("seconds ago", fontsize=8.5)
        self.ax_idx.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.85)
        self.ax_idx.tick_params(labelsize=8)

        # 3. band powers
        self.bars = self.ax_band.bar(["theta\n4-8", "alpha\n8-13", "beta\n13-30", "gamma\n30-45"],
                                     [0] * 4, color=["#ff7f0e", "#1f77b4", "#2ca02c", "#9467bd"])
        self.ax_band.set_ylabel("log10 power")
        self.ax_band.set_title("3 · BAND POWER now   (alpha jumps when you close your eyes)",
                               loc="left", fontsize=10.5, pad=6)
        self.ax_band.tick_params(labelsize=8)

        self.readout = self.ax_txt.text(0.0, 1.0, "", va="top", ha="left", fontsize=9.2,
                                        family="monospace", transform=self.ax_txt.transAxes)
        fig.canvas.mpl_connect("key_press_event", self._on_key)
        fig.canvas.mpl_connect("close_event", self._on_close)
        fig.canvas.mpl_connect("draw_event", self._on_draw)

    # ---- events ----------------------------------------------------------------------------

    def _on_key(self, event) -> None:
        if event.key in ("q", "escape"):
            plt.close(self.fig)
            return
        msg = apply_key(event.key, self.pipe, self.source)
        if msg:
            print(f"[key] {msg}", flush=True)
            self._slow()

    def _on_close(self, _event) -> None:
        self._closing = True

    def _on_draw(self, _event) -> None:
        self._bg = self.fig.canvas.copy_from_bbox(self.ax_raw.bbox)

    # ---- rendering -------------------------------------------------------------------------

    def _title2(self, calibrated: bool) -> str:
        unit = "z-score: easy ≈ -1, hard ≈ +1" if calibrated else "raw index units, not yet calibrated"
        return f"2 · EFFORT & ENGAGEMENT   —   last 2 minutes.   {unit}"

    def _series(self, hist, get):
        a = np.full(HIST, np.nan)
        v = [get(h) for h in hist]
        a[HIST - len(v):] = [np.nan if x is None else x for x in v]
        return a

    def _slow(self) -> None:
        """Once per FeatureFrame: banner, index history, bars, readout. Full redraw."""
        pipe = self.pipe
        f, st = pipe.latest, pipe.status()
        q = st["quality"]

        if not st["connected"]:
            head, colour = "NO HEADSET", "#d62728"
            sub = st["error"] or "waiting for the stream - is the headset switched on and in range?"
        elif q > GOOD_Q:
            head, colour = f"NO CONTACT   q={q}", "#d62728"
            sub = ("electrode not on skin: pad flat on bare forehead (no hair under it), "
                   "ear clip on the earlobe, both contacts touching")
        else:
            head = f"CONTACT {'GOOD' if q <= 30 else 'OK  '}   q={q}"
            colour = "#2ca02c" if q <= 30 else "#e8a33d"
            sub = "calibrate when you are ready: press 1, then 2, then 3, then 0   (or a)"
        if self.fake:
            head = f"[SIMULATED: {self.source.state}]  " + head
            sub = f"expect: {FAKE_HINT[self.source.state]}"
        if st["cal_phase"]:
            sub = f"CALIBRATING '{st['cal_phase']}' - keep going, then press the next key"
        for m in st["messages"]:
            sub = "! " + m
        self.banner.set_text(head)
        self.banner.get_bbox_patch().set_facecolor(colour)
        self.banner.set_color("white")
        self.subbanner.set_text(sub)

        hist = list(pipe.history)[-HIST:]
        if hist:
            cal = hist[-1].calibrated
            if cal:
                e = self._series(hist, lambda h: h.z_effort)
                ee = self._series(hist, lambda h: h.z_effort_ema)
                ge = self._series(hist, lambda h: h.z_engagement_ema)
            else:
                e = self._series(hist, lambda h: h.effort if h.valid else None)
                ee = self._series(hist, lambda h: h.effort_ema)
                ge = self._series(hist, lambda h: h.engagement_ema)
            self.l_eff.set_ydata(e)
            self.l_eff_e.set_ydata(ee)
            self.l_eng_e.set_ydata(ge)
            finite = np.concatenate([v[np.isfinite(v)] for v in (e, ee, ge)]) if hist else np.array([])
            if finite.size:
                lo, hi = float(finite.min()), float(finite.max())
                pad = max(0.25, (hi - lo) * 0.2)
                self.ax_idx.set_ylim(lo - pad, hi + pad)
            lo, hi = self.ax_idx.get_ylim()
            self.l_bad.set_ydata(self._series(hist, lambda h: None if h.valid else 1.0)
                                 * (lo + 0.045 * (hi - lo)))
            self.ax_idx.set_title(self._title2(cal), loc="left", fontsize=10.5, pad=6)

        if f is not None:
            vals = [f.log_theta, f.log_alpha, f.log_beta, f.log_gamma]
            for b, v in zip(self.bars, vals):
                b.set_height(v)
            self.ax_band.set_ylim(min(vals) - 0.4, max(vals) + 0.4)
            ratio = st["alpha_closed_open_ratio"]
            self.readout.set_text("\n".join([
                "CONTACT",
                f"  quality     {q:>7d}   0 best, >{GOOD_Q} unusable",
                f"  artifacts   {f.artifact_coverage:>6.0%}",
                f"  usable      {'yes' if f.valid else 'NO':>7s}",
                "",
                "SIGNAL  (raw indices)",
                f"  effort θ/α  {_f(f.effort):>7s}",
                f"  engagement  {_f(f.engagement):>7s}",
                f"  alpha now   {_f(f.alpha_ratio, '{:.2f}x'):>7s}   vs easy phase",
                "",
                "CALIBRATED  (z-scores:",
                "easy ≈ -1, hard ≈ +1)",
                f"  z effort    {_f(f.z_effort_ema):>7s}",
                f"  z engage    {_f(f.z_engagement_ema):>7s}",
                "",
                "CALIBRATION",
                f"  state       {('done' if f.calibrated else 'not yet'):>7s}"
                + ("  weak" if f.calibration_weak else ""),
                f"  phase       {(f.cal_phase or '-'):>7s}",
                f"  closed/open {_f(ratio, '{:.2f}x'):>7s}   want >= 1.5x",
                "",
                "BLINKS  (fatigue axis)",
                f"  rate        {f.blink_rate:>7.1f}   per minute",
                f"  duration    {_f(f.blink_dur_ms, '{:.0f}ms'):>7s}",
                "",
                "NEUROSKY  (their numbers,",
                "for comparison only)",
                f"  attention   {(f.attention if f.attention is not None else '-'):>7}",
                f"  meditation  {(f.meditation if f.meditation is not None else '-'):>7}",
                "",
                f"recording: {'off' if not st['session_dir'] else 'on'}",
            ]))
            x, _, _ = pipe.raw_window(WIN)
            if np.any(x):
                want = max(60.0, float(np.percentile(np.abs(x), 99.5)) * 1.35)
                if not (0.6 * self._ylim <= want <= 1.15 * self._ylim):
                    self._ylim = want
                    self.ax_raw.set_ylim(-want, want)
        self.fig.canvas.draw_idle()

    def _fast(self) -> None:
        """Every FAST_MS: blit the EEG trace. No limit or text changes here."""
        if self._closing:
            return
        pipe = self.pipe
        if pipe.latest is not None and pipe.latest.n != self._last_n:
            self._last_n = pipe.latest.n
            self._slow()
            return
        if self._bg is None:
            self.fig.canvas.draw()
            return
        x, mask, _ = pipe.raw_window(WIN)
        xd, md = x[::DECIM], mask[::DECIM]
        self.l_raw.set_ydata(xd)
        self.l_art.set_ydata(np.where(md, xd, np.nan))
        canvas = self.fig.canvas
        canvas.restore_region(self._bg)
        self.ax_raw.draw_artist(self.l_raw)
        self.ax_raw.draw_artist(self.l_art)
        canvas.blit(self.ax_raw.bbox)
        canvas.flush_events()

    def run(self) -> None:
        timer = self.fig.canvas.new_timer(interval=FAST_MS)
        timer.add_callback(self._fast)
        timer.start()
        self._slow()
        plt.show()
        timer.stop()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(ap)
    ap.add_argument("--ws", action="store_true", help="also serve the WebSocket feed on :8765")
    args = ap.parse_args()

    source = build_source(args)
    pipe = Pipeline(source, log_dir=log_dir_for(args))
    if args.ws:
        pipe.serve()
    pipe.start()
    print(f"source: {source.describe()}   recording: {pipe.session_dir or 'off'}")
    print(GO_NO_GO)
    try:
        Monitor(pipe, source).run()
    finally:
        pipe.stop()
        if pipe.session_dir:
            print(f"session saved: {pipe.session_dir}")


if __name__ == "__main__":
    main()
