"""Per-window signal processing for one frontal channel (Fp1).

Window: 4 s of raw counts -> uV -> three bands:

    analysis   3-45 Hz   the PSD band. The MindWave front end is ~3-100 Hz analog, so delta is
                         unusable and nothing is built on it.
    detection  0.5-8 Hz  blinks and movement. A blink is a 200-400 ms deflection, i.e. energy at
                         1-3 Hz, so it MUST NOT be detected in the analysis band: that highpass
                         cuts a 250 uV blink to ~70 uV (400 ms -> ~34 uV) and turns the smooth
                         deflection into a narrow biphasic spike, destroying the 50-500 ms
                         duration signature the detector relies on.
    display    0.5-45 Hz what the monitor plots, so blinks are visible to the eye.

Artifacts are found in the detection band; the resulting mask is interpolated across in the
analysis band before the Welch PSD -> log10 band powers -> indices.

    effort      = log theta - log alpha        frontal theta/alpha workload ratio (primary)
    engagement  = log beta - log(alpha+theta)  Pope/Mikulka engagement index (secondary)

Fp1 sits over the eye, so blinks are 100-300 uV transients. They are detected first (adaptive
threshold on a robust sigma), masked out of the PSD, and reported as their own signal: blink rate
and duration are validated fatigue markers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, sosfiltfilt, welch

from .thinkgear import FS, UV_PER_RAW

BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0), "gamma": (30.0, 45.0)}
BP_LO, BP_HI = 3.0, 45.0            # analysis band (PSD)
BLINK_LO, BLINK_HI = 0.5, 8.0       # detection band (blinks / movement)
DISP_LO, DISP_HI = 0.5, 45.0        # display band (monitor trace)
_SOS = butter(4, [BP_LO, BP_HI], btype="bandpass", fs=FS, output="sos")
_SOS_BLINK = butter(2, [BLINK_LO, BLINK_HI], btype="bandpass", fs=FS, output="sos")
_SOS_DISP = butter(2, [DISP_LO, DISP_HI], btype="bandpass", fs=FS, output="sos")


@dataclass(slots=True)
class Blink:
    start: int              # sample index within the window
    end: int
    amplitude_uv: float     # peak |x|
    duration_ms: float


@dataclass
class WindowFeatures:
    log_theta: float
    log_alpha: float
    log_beta: float
    log_gamma: float
    effort: float
    engagement: float
    blinks: list[Blink]
    artifact_coverage: float            # fraction of the window masked out
    filtered: np.ndarray = field(repr=False)   # display band, 0.5-45 Hz
    mask: np.ndarray = field(repr=False)


def to_uv(raw) -> np.ndarray:
    return np.asarray(raw, dtype=np.float64) * UV_PER_RAW


def bandpass(x_uv: np.ndarray) -> np.ndarray:
    """Analysis band, 3-45 Hz. Do not detect blinks in this band - see the module docstring."""
    return sosfiltfilt(_SOS, x_uv - np.mean(x_uv))


def blink_band(x_uv: np.ndarray) -> np.ndarray:
    """Detection band, 0.5-8 Hz: preserves blink amplitude and duration."""
    return sosfiltfilt(_SOS_BLINK, x_uv - np.mean(x_uv))


def display_band(x_uv: np.ndarray) -> np.ndarray:
    """0.5-45 Hz, for plotting: blinks stay visible next to the EEG."""
    return sosfiltfilt(_SOS_DISP, x_uv - np.mean(x_uv))


def detect_artifacts(x: np.ndarray, fs: int = FS, floor_uv: float = 40.0, k: float = 5.0,
                     min_ms: float = 50.0, max_ms: float = 800.0, merge_ms: float = 50.0,
                     pad_ms: float = 100.0) -> tuple[list[Blink], np.ndarray]:
    """Blinks and longer movement artifacts. Expects the DETECTION band (see blink_band).

    Threshold = max(k * robust sigma, floor_uv). Returns the blinks and a boolean mask covering
    every excursion (blink or not) padded by pad_ms on each side; excursions longer than max_ms
    are movement, masked out of the PSD but not counted as blinks.

    duration_ms is inflated roughly 1.5x by the 0.5 Hz filter edge (a 250 ms blink measures
    ~400 ms). It is a relative fatigue measure - watch whether it rises - not an absolute number.
    """
    med = np.median(x)
    sigma = 1.4826 * np.median(np.abs(x - med)) + 1e-9
    thr = max(k * sigma, floor_uv)
    above = np.abs(x) > thr
    n = len(x)
    mask = np.zeros(n, dtype=bool)
    blinks: list[Blink] = []
    if not above.any():
        return blinks, mask
    d = np.diff(above.astype(np.int8))
    starts = list(np.flatnonzero(d == 1) + 1)
    ends = list(np.flatnonzero(d == -1) + 1)
    if above[0]:
        starts.insert(0, 0)
    if above[-1]:
        ends.append(n)
    merge = int(merge_ms * fs / 1000)
    runs: list[list[int]] = []
    for s, e in zip(starts, ends):
        if runs and s - runs[-1][1] <= merge:
            runs[-1][1] = e
        else:
            runs.append([s, e])
    pad = int(pad_ms * fs / 1000)
    for s, e in runs:
        dur_ms = (e - s) * 1000.0 / fs
        mask[max(0, s - pad):min(n, e + pad)] = True
        if min_ms <= dur_ms <= max_ms:
            blinks.append(Blink(s, e, float(np.max(np.abs(x[s:e]))), dur_ms))
    return blinks, mask


def interpolate(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if not mask.any() or mask.all():
        return x
    idx = np.arange(len(x))
    y = x.copy()
    y[mask] = np.interp(idx[mask], idx[~mask], x[~mask])
    return y


def band_powers(x: np.ndarray, fs: int = FS) -> dict[str, float]:
    f, p = welch(x, fs=fs, nperseg=min(512, len(x)))
    out = {}
    for name, (lo, hi) in BANDS.items():
        sel = (f >= lo) & (f < hi)
        out[name] = float(np.trapezoid(p[sel], f[sel])) if sel.sum() > 1 else 0.0
    return out


def compute_window(raw_window, fs: int = FS, **artifact_kw) -> WindowFeatures:
    x_uv = to_uv(raw_window)
    blinks, mask = detect_artifacts(blink_band(x_uv), fs, **artifact_kw)
    bp = band_powers(interpolate(bandpass(x_uv), mask), fs)
    eps = 1e-6
    lt, la, lb, lg = (float(np.log10(bp[k] + eps)) for k in ("theta", "alpha", "beta", "gamma"))
    engagement = float(np.log10(bp["beta"] + eps) - np.log10(bp["alpha"] + bp["theta"] + eps))
    return WindowFeatures(lt, la, lb, lg, lt - la, engagement, blinks, float(mask.mean()),
                          display_band(x_uv), mask)
