from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from scripts.guided_eeg_trial import valid_focus


def analyze(directory: Path) -> dict:
    result = json.loads((directory / "calibration.json").read_text())
    rows = [json.loads(line) for line in (directory / "trial.jsonl").read_text().splitlines()]
    focus = [row for row in rows if row.get("type") == "focus"]
    flags = [
        row["flag"]
        for row in rows
        if row.get("type") == "flag_open"
        and row["flag"].get("source") == "eeg"
        and row["flag"].get("simulated") is False
    ]
    hello = next(row for row in rows if row.get("type") == "hello")
    phases = []
    for phase in result["measurements"]:
        points = [point for point in focus if phase["t_start"] + 5 <= point["t"] < phase["t_end"]]
        clean = [point for point in points if valid_focus(point)]
        windows = [
            point["w15"] for point in clean if point.get("w15") is not None and point.get("baseline_ready")
        ]
        indices = [(point.get("mw") or {}).get("engagement") for point in clean]
        indices = [index for index in indices if index is not None]
        phases.append(
            {
                "phase": phase["phase"],
                "ticks": len(points),
                "valid_ticks": len(clean),
                "quality_zero_ticks": sum(point.get("poor_signal") == 0 for point in points),
                "mean_log_engagement": statistics.mean(indices) if indices else None,
                "geometric_mean_beta_over_alpha_theta": 10 ** statistics.mean(indices) if indices else None,
                "minimum_live_w15": min(windows) if windows else None,
                "maximum_live_w15": max(windows) if windows else None,
                "natural_flags": sum(
                    phase["t_start"] <= flag["t_trigger"] < phase["t_end"] for flag in flags
                ),
            }
        )
    return {
        "session_id": result["measurements"][0]["session_id"],
        "alpha_closed_open_ratio": result["alpha_closed_open_ratio"],
        "total_focus_ticks": len(focus),
        "valid_focus_ticks": sum(valid_focus(point) for point in focus),
        "quality_zero_ticks": sum(point.get("poor_signal") == 0 for point in focus),
        "raw_display_samples": sum(len(row["uv"]) for row in rows if row.get("type") == "raw"),
        "automatic_eeg_flags": len(flags),
        "effective_config": hello["config"],
        "phases": phases,
        "limits": [
            "Phase labels are instructed tasks, pending participant confirmation.",
            "The production focus baseline in this signal diagnostic includes eyes-closed and relaxed periods; it is not a focused-lecture baseline.",
            "The pipeline's three-anchor calibration succeeded, but it is separate from the production engagement-drop detector.",
            "No classifier accuracy or useful catch-up claim follows from this calibration-only run.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = analyze(args.directory)
    (args.directory / "analysis.json").write_text(json.dumps(output, indent=2, allow_nan=False))
    print(json.dumps(output, indent=2, allow_nan=False))
