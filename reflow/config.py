"""Settings: the single source of truth for every tunable (TDD §13)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# The four explanation families the preference model learns over (docs/PRODUCT.md §4).
FORMS: tuple[str, ...] = ("words", "analogy", "visual", "doing")
FORM_LABELS: dict[str, str] = {
    "words": "in words",
    "analogy": "by comparison",
    "visual": "as a picture",
    "doing": "by doing",
}
# keys used before v2 (tally rows, flags, sessions); mapped on read and by the migration
LEGACY_FORMS: dict[str, str] = {
    "plain": "words",
    "keyterm": "words",
    "analogy": "analogy",
    "sketch": "visual",
}


def canonical_form(form: str | None) -> str | None:
    if form is None:
        return None
    return LEGACY_FORMS.get(form, form) if form not in FORMS else form


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def _env_float(name: str, default: float) -> float:
    v = _env(name)
    try:
        return float(v) if v is not None else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path("data"))
    host: str = "127.0.0.1"
    port: int = 8765

    deepgram_api_key: str | None = None
    deepgram_model: str = "nova-3"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    # The product needs OpenAI. The extractive offline generator is for automated tests only.
    allow_offline_llm: bool = False

    headset_port: str | None = None  # None = auto-detect, "sim" = simulate
    tts_model: str = "aura-2-thalia-en"  # the tutor voice (Deepgram Aura)
    totem_port: str | None = None

    # signal engine (TDD §3)
    fs: int = 512
    fft_window_seconds: float = 2.0
    ema_tau_seconds: float = 8.0
    baseline_seconds: float = 180.0
    baseline_min_valid_fraction: float = 0.6
    baseline_min_valid_samples: int = 30
    sigma_floor: float = 0.05
    window_seconds: int = 15
    window_min_valid: int = 8
    drop_enter_z: float = -1.25
    drop_exit_z: float = -0.6
    eeg_flag_max_seconds: float = 30.0
    eeg_refractory_seconds: float = 20.0
    poor_signal_gate: int = 50
    artifact_abs_p2p: float = 400.0
    artifact_median_mult: float = 3.5
    blink_abs_p2p: float = 300.0
    blink_median_mult: float = 3.0

    # spans (TDD §6)
    lead_in_seconds: float = 8.0
    tap_snap_back_max: float = 20.0
    tap_end_extend_max: float = 5.0
    gap_merge_gap_seconds: float = 10.0
    tap_link_eeg_seconds: float = 10.0  # a tap inherits an EEG flag that is open or closed this recently
    tap_link_max_back: float = 60.0  # cap on how far back a linked tap span reaches
    gap_min_seconds: float = 8.0
    gap_max_seconds: float = 90.0

    # recaps and catch-ups
    recap_period_seconds: float = 20.0
    recap_window_seconds: float = 30.0
    recap_min_words: int = 12
    recap_timeout_seconds: float = 15.0
    package_timeout_seconds: float = 45.0
    catchup_ttl_seconds: float = 6.0
    now_words: int = 12

    # tally and review
    tally_prior_pseudocount: float = 2.0
    tally_enough_attempts: int = 12
    review_stop_streak: int = 3

    # loss map
    lossmap_bin_seconds: float = 10.0
    lossmap_window_bins: int = 4

    @property
    def db_path(self) -> Path:
        return self.data_dir / "reflow.db"

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def lectures_dir(self) -> Path:
        return self.data_dir / "lectures"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.sessions_dir, self.lectures_dir):
            p.mkdir(parents=True, exist_ok=True)

    def public(self) -> dict:
        """Values safe to send to the UI."""
        return {
            "baseline_seconds": self.baseline_seconds,
            "lead_in_seconds": self.lead_in_seconds,
            "recap_period_seconds": self.recap_period_seconds,
            "recap_window_seconds": self.recap_window_seconds,
            "catchup_ttl_seconds": self.catchup_ttl_seconds,
            "drop_enter_z": self.drop_enter_z,
            "drop_exit_z": self.drop_exit_z,
            "window_seconds": self.window_seconds,
            "review_stop_streak": self.review_stop_streak,
            "tally_enough_attempts": self.tally_enough_attempts,
            "forms": list(FORMS),
        }


def load_settings(env_file: str | os.PathLike | None = None) -> Settings:
    """Read .env (without overriding real env vars) and build Settings."""
    if env_file is not None:
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)
    s = Settings()
    s.data_dir = Path(_env("REFLOW_DATA_DIR", "data") or "data")
    s.host = _env("REFLOW_HOST", s.host) or s.host
    s.port = _env_int("REFLOW_PORT", s.port)
    s.deepgram_api_key = _env("DEEPGRAM_API_KEY")
    s.deepgram_model = _env("REFLOW_DEEPGRAM_MODEL", s.deepgram_model) or s.deepgram_model
    s.openai_api_key = _env("OPENAI_API_KEY")
    s.openai_model = _env("OPENAI_MODEL", s.openai_model) or s.openai_model
    s.headset_port = _env("REFLOW_HEADSET_PORT")
    s.tts_model = _env("REFLOW_TTS_MODEL", s.tts_model) or s.tts_model
    s.allow_offline_llm = (_env("REFLOW_ALLOW_OFFLINE_LLM", "0") or "0").lower() in ("1", "true", "yes")
    s.totem_port = _env("REFLOW_TOTEM_PORT")
    s.baseline_seconds = _env_float("REFLOW_BASELINE_SECONDS", s.baseline_seconds)
    s.drop_enter_z = _env_float("REFLOW_DROP_ENTER_Z", s.drop_enter_z)
    s.drop_exit_z = _env_float("REFLOW_DROP_EXIT_Z", s.drop_exit_z)
    s.recap_period_seconds = _env_float("REFLOW_RECAP_PERIOD_SECONDS", s.recap_period_seconds)
    s.catchup_ttl_seconds = _env_float("REFLOW_CATCHUP_TTL_SECONDS", s.catchup_ttl_seconds)
    return s
