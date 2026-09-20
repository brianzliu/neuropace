"""Settings: the single source of truth for every tunable (TDD §13)."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

FOCUS_METRIC = "theta_alpha_v1"

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


def _compat_env(name: str, legacy_name: str, default: str | None = None) -> str | None:
    """Prefer NeuroPace variables while honoring pre-rename configuration."""
    return _env(name, _env(legacy_name, default))


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
    # Exact hosted UI origins only. A per-process pairing code is required remotely.
    ui_origins: tuple[str, ...] = ("https://neurospace-hackmit.vercel.app",)

    deepgram_api_key: str | None = None
    deepgram_tts_api_key: str | None = field(default=None, repr=False)
    tts_expressivity: int = 2
    deepgram_model: str = "nova-3"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_requests_per_minute: int = 5  # conservative free-tier pacing; raise for a paid project
    llm_provider: str = "openai"
    # The product needs the selected model provider. The extractive fallback is for tests only.
    allow_offline_llm: bool = False

    headset_port: str | None = None  # None = auto-detect, "sim" = simulate
    tts_model: str = "flux-cole-en"  # the tutor voice (Deepgram Aura)
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
    def tts_api_key(self) -> str | None:
        return self.deepgram_tts_api_key or self.deepgram_api_key

    @property
    def llm_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_model")

    @property
    def llm_api_key(self) -> str | None:
        return getattr(self, f"{self.llm_provider}_api_key")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "neuropace.db"

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def lectures_dir(self) -> Path:
        return self.data_dir / "lectures"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.sessions_dir, self.lectures_dir):
            p.mkdir(parents=True, exist_ok=True)
        legacy_db = self.data_dir / "reflow.db"
        if not self.db_path.exists() and legacy_db.exists():
            # SQLite backup includes committed WAL state and leaves the old file recoverable.
            with sqlite3.connect(legacy_db) as source, sqlite3.connect(self.db_path) as target:
                source.backup(target)

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
    load_dotenv(Path(env_file).parent / ".env.tts" if env_file else ".env.tts", override=False)
    s = Settings()
    s.data_dir = Path(_compat_env("NEUROPACE_DATA_DIR", "REFLOW_DATA_DIR", "data") or "data")
    s.host = _compat_env("NEUROPACE_HOST", "REFLOW_HOST", s.host) or s.host
    port = _compat_env("NEUROPACE_PORT", "REFLOW_PORT")
    s.port = int(port) if port and port.isdigit() else s.port
    origins = _compat_env("NEUROPACE_UI_ORIGINS", "REFLOW_UI_ORIGINS")
    if origins is not None:
        s.ui_origins = tuple(o.strip().rstrip("/") for o in origins.split(",") if o.strip())
    s.deepgram_api_key = _env("DEEPGRAM_API_KEY")
    s.deepgram_tts_api_key = _env("DEEPGRAM_TTS_API_KEY")
    s.tts_expressivity = _env_int("NEUROPACE_TTS_EXPRESSIVITY", s.tts_expressivity)
    s.deepgram_model = (
        _compat_env("NEUROPACE_DEEPGRAM_MODEL", "REFLOW_DEEPGRAM_MODEL", s.deepgram_model) or s.deepgram_model
    )
    s.openai_api_key = _env("OPENAI_API_KEY")
    s.openai_model = _env("OPENAI_MODEL", s.openai_model) or s.openai_model
    s.openrouter_api_key = _env("OPENROUTER_API_KEY")
    s.openrouter_model = _env("OPENROUTER_MODEL", s.openrouter_model) or s.openrouter_model
    s.gemini_api_key = _env("GEMINI_API_KEY")
    s.gemini_model = _env("GEMINI_MODEL", s.gemini_model) or s.gemini_model
    s.gemini_requests_per_minute = max(1, _env_int("GEMINI_REQUESTS_PER_MINUTE", 5))
    provider = (
        _compat_env("NEUROPACE_LLM_PROVIDER", "REFLOW_LLM_PROVIDER")
        or (
            "openai"
            if s.openai_api_key
            else "gemini"
            if s.gemini_api_key
            else "openrouter"
            if s.openrouter_api_key
            else "openai"
        )
    ).lower()
    s.llm_provider = provider if provider in ("openai", "openrouter", "gemini") else "openai"
    s.headset_port = _compat_env("NEUROPACE_HEADSET_PORT", "REFLOW_HEADSET_PORT")
    s.tts_model = _compat_env("NEUROPACE_TTS_MODEL", "REFLOW_TTS_MODEL", s.tts_model) or s.tts_model
    s.allow_offline_llm = (
        _compat_env("NEUROPACE_ALLOW_OFFLINE_LLM", "REFLOW_ALLOW_OFFLINE_LLM", "0") or "0"
    ).lower() in ("1", "true", "yes")
    s.totem_port = _compat_env("NEUROPACE_TOTEM_PORT", "REFLOW_TOTEM_PORT")
    for attr, new, old in (
        ("baseline_seconds", "NEUROPACE_BASELINE_SECONDS", "REFLOW_BASELINE_SECONDS"),
        ("drop_enter_z", "NEUROPACE_DROP_ENTER_Z", "REFLOW_DROP_ENTER_Z"),
        ("drop_exit_z", "NEUROPACE_DROP_EXIT_Z", "REFLOW_DROP_EXIT_Z"),
        ("recap_period_seconds", "NEUROPACE_RECAP_PERIOD_SECONDS", "REFLOW_RECAP_PERIOD_SECONDS"),
        ("catchup_ttl_seconds", "NEUROPACE_CATCHUP_TTL_SECONDS", "REFLOW_CATCHUP_TTL_SECONDS"),
    ):
        value = _compat_env(new, old)
        if value is not None:
            try:
                setattr(s, attr, float(value))
            except ValueError:
                pass
    return s
