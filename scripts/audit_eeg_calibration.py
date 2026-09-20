from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.signal import welch

from mindwave import features as front
from mindwave.thinkgear import FS, UV_PER_RAW
from neuropace.config import Settings
from neuropace.signal.features import FocusEngine

ROOT = Path(__file__).resolve().parents[1]


def audit(directory: Path, plots: bool = False) -> dict:
    calibration = json.loads((directory / "calibration.json").read_text())
    events = [json.loads(line) for line in (directory / "trial.jsonl").read_text().splitlines()]
    focus = [row for row in events if row.get("type") == "focus"]
    offset = float(np.median([row["wall"] - row["t"] for row in focus]))
    recording = ROOT / calibration["headset"]["mw"]["session_dir"]
    meta = json.loads((recording / "session.json").read_text())
    raw = np.fromfile(recording / "raw.int16", dtype="<i2")
    frames = [json.loads(line) for line in (recording / "features.jsonl").read_text().splitlines()]
    assert meta["fs"] == FS == 512 and meta["source"]["kind"] == "mindwave"
    errors, windows = [], []
    for frame in frames:
        n = frame["n"]
        segment = raw[n - 4 * FS : n]
        assert len(segment) == 4 * FS
        calculated = front.compute_window(segment)
        for field in (
            "log_theta",
            "log_alpha",
            "log_beta",
            "log_gamma",
            "effort",
            "engagement",
            "artifact_coverage",
        ):
            errors.append(abs(getattr(calculated, field) - frame[field]))
        uv = front.to_uv(segment)
        cleaned = front.interpolate(front.bandpass(uv), calculated.mask)
        frequency, power = welch(cleaned, fs=FS, nperseg=FS)
        windows.append(
            {"t": frame["t"] - offset, "frame": frame, "power": power, "uv": uv, "feature": calculated}
        )
    phases, spectra = [], {}
    for phase in calibration["measurements"]:
        selected = [
            window
            for window in windows
            if phase["t_start"] + 5 <= window["t"] < phase["t_end"] and window["frame"]["valid"]
        ]
        if not selected:
            phases.append({"phase": phase["phase"], "valid_windows": 0})
            continue
        spectrum = np.median(np.stack([window["power"] for window in selected]), axis=0)
        spectra[phase["phase"]] = spectrum
        alpha_bins = (frequency >= 8) & (frequency < 13)
        phases.append(
            {
                "phase": phase["phase"],
                "valid_windows": len(selected),
                "median_artifact_fraction": float(
                    np.median([window["frame"]["artifact_coverage"] for window in selected])
                ),
                "median_raw_rms_uv": float(np.median([np.std(window["uv"]) for window in selected])),
                "alpha_peak_hz": float(frequency[alpha_bins][np.argmax(spectrum[alpha_bins])]),
                "mean_log_gamma": float(np.mean([window["frame"]["log_gamma"] for window in selected])),
                "mean_log_engagement": float(np.mean([window["frame"]["engagement"] for window in selected])),
                "sd_log_engagement": float(
                    np.std([window["frame"]["engagement"] for window in selected], ddof=1)
                ),
            }
        )
    tones = {}
    for hz, expected in ((6, "theta"), (10, "alpha"), (20, "beta")):
        signal = 20 * np.sin(2 * np.pi * hz * np.arange(4 * FS) / FS) / UV_PER_RAW
        feature = front.compute_window(signal)
        powers = {name: 10 ** getattr(feature, "log_" + name) for name in front.BANDS}
        tones[str(hz)] = {"dominant_band": max(powers, key=powers.get), "expected_band": expected}
        assert max(powers, key=powers.get) == expected
    replay_settings = Settings(baseline_seconds=30)
    replay = FocusEngine(replay_settings)
    training = next(phase for phase in calibration["measurements"] if phase["phase"] == "concentrate")
    replay_samples, replay_events = [], []
    selected = [point for point in focus if point["t"] >= training["t_start"] + 5]
    for point in selected:
        feature = point.get("mw") or {}
        value = feature.get("engagement")
        valid = (
            point["quality"] == "good"
            and not point["artifact"]
            and value is not None
            and math.isfinite(value)
        )
        replay.feed_frame(value, point["poor_signal"], valid)
        sample, detected = replay.tick(point["t"])
        replay_samples.append(sample.to_dict())
        replay_events.extend({"kind": event.kind, "t": event.t} for event in detected)
    held_out = []
    for phase in calibration["measurements"]:
        if phase["phase"] not in ("daydream", "concentrate_again"):
            continue
        points = [point for point in replay_samples if phase["t_start"] <= point["t"] < phase["t_end"]]
        valid = [
            point
            for point in points
            if point["quality"] == "good" and not point["artifact"] and point["w15"] is not None
        ]
        held_out.append(
            {
                "phase": phase["phase"],
                "minimum_w15": min((point["w15"] for point in valid), default=None),
                "maximum_w15": max((point["w15"] for point in valid), default=None),
                "drop_seconds": sum(point["state"] == "drop" for point in points),
                "entries": [
                    event["t"]
                    for event in replay_events
                    if event["kind"] == "enter" and phase["t_start"] <= event["t"] < phase["t_end"]
                ],
            }
        )
    report = {
        "recording": str(recording),
        "raw_samples": int(raw.size),
        "nominal_sample_rate_hz": FS,
        "raw_extrema_counts": [int(raw.min()), int(raw.max())],
        "int16_rail_samples": int(np.sum((raw == -32768) | (raw == 32767))),
        "feature_frames": len(frames),
        "valid_feature_frames": sum(frame["valid"] for frame in frames),
        "raw_to_logged_feature_max_absolute_error": max(errors),
        "recomputed_feature_check": "PASS" if max(errors) <= 0.000051 else "FAIL",
        "known_tone_band_checks": tones,
        "phase_spectral_audit": phases,
        "focused_only_replay": {
            "description": "Exploratory replay using the unchanged detector and existing 30-second rehearsal baseline; fit only on the first counting block, then run forward through later untouched data. Not a new live validation or a population accuracy estimate.",
            "mu": replay.baseline.mu,
            "sigma": replay.baseline.sigma,
            "training_samples_used": len(replay.baseline._xs),
            "enter_z": replay_settings.drop_enter_z,
            "exit_z": replay_settings.drop_exit_z,
            "events": replay_events,
            "held_out": held_out,
        },
        "limitations": [
            "One eyes-closed block and one daydream block cannot establish sensitivity, specificity or a reliable personal optimum.",
            "Adjacent four-second EEG windows overlap; the frame count is not an independent sample size.",
            "Counting tests workload; it does not establish attention to a particular lesson.",
            "Fp1 beta and gamma can contain muscle activity; single-channel EEG cannot cleanly separate every artifact.",
        ],
    }
    if plots:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figure, axes = plt.subplots(3, 1, figsize=(13, 11), constrained_layout=True)
        colors = {
            "eyes_open_1": "#70816d",
            "eyes_closed": "#9467bd",
            "concentrate": "#2878ad",
            "daydream": "#d18d21",
            "concentrate_again": "#2f966a",
        }
        for phase in calibration["measurements"]:
            name = phase["phase"]
            for axis in axes[1:]:
                axis.axvspan(phase["t_start"], phase["t_end"], color=colors[name], alpha=0.12)
            if name in spectra:
                visible = (frequency >= 3) & (frequency <= 45)
                axes[0].semilogy(frequency[visible], spectra[name][visible], label=name, color=colors[name])
        axes[0].set(
            xlim=(3, 45),
            xlabel="Frequency (Hz)",
            ylabel="Median cleaned PSD (uV squared / Hz)",
            title="Recomputed from the original 512 Hz recording",
        )
        axes[0].legend(ncol=3)
        axes[1].plot(
            [point["t"] for point in focus],
            [(point.get("mw") or {}).get("engagement", np.nan) for point in focus],
            label="Raw log engagement",
            alpha=0.6,
        )
        axes[1].plot(
            [point["t"] for point in focus],
            [point.get("x", np.nan) for point in focus],
            label="Production EMA",
        )
        axes[1].set(
            xlabel="Session seconds",
            ylabel="log10 beta / (alpha + theta)",
            title="Task-dependent changes, not a calibrated probability of attention",
        )
        axes[1].legend()
        axes[2].plot(
            [point["t"] for point in focus],
            [point.get("w15", np.nan) for point in focus],
            label="Live mixed-baseline w15",
        )
        axes[2].plot(
            [point["t"] for point in replay_samples],
            [point.get("w15", np.nan) for point in replay_samples],
            label="Exploratory focused-only replay",
        )
        axes[2].axhline(-1.25, color="red", linestyle="--", label="Unchanged entry threshold")
        axes[2].set(
            xlabel="Session seconds",
            ylabel="15-second mean z",
            title="Changing the reference distribution is not the same as changing the algorithm",
        )
        axes[2].legend()
        figure.savefig(directory / "manual-audit.png", dpi=150)
        plt.close(figure)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--plots", action="store_true")
    args = parser.parse_args()
    report = audit(args.directory, args.plots)
    (args.directory / "manual-audit.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps(report, indent=2, allow_nan=False))
