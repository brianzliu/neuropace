"""Optional Manim rendering for Office Hours' "manim" board kind (docs/PRODUCT.md §5a).

Manim is a genuine dependency, not a stub: it needs LaTeX and ffmpeg on the host and pulls in a heavy
package (`uv sync --group manim`). None of that is required to run NeuroPace at all — `manim_available()`
is checked before the model is even told the kind exists (llm/prompts.py), and every failure here raises
`ManimUnavailable`, the same "no key, no voice, screen stays readable" shape as `tts.py`.

The script is model-written Python executed as a subprocess. `schemas.ManimAnimation` already rejects an
unsafe script (import allowlist, one Scene class) before this module ever sees it; this module adds the
second layer: a stripped environment (no API keys), a fresh temp directory per render, and CPU/memory
limits, so a script that slips past the allowlist still can't do much beyond wasting its own render.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import sys
import tempfile
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path

from .config import Settings

RENDER_TIMEOUT_SECONDS = 45.0
CPU_LIMIT_SECONDS = 40
MEMORY_LIMIT_BYTES = 2_000_000_000


class ManimUnavailable(RuntimeError):
    """Not installed, or the render failed. The caller falls back to the plain animation template."""


@lru_cache(maxsize=1)
def manim_available() -> bool:
    return find_spec("manim") is not None and shutil.which("ffmpeg") is not None


def cache_path(s: Settings, script: str) -> Path:
    key = hashlib.sha256(script.encode()).hexdigest()
    return s.data_dir / "cache" / "manim" / f"{key}.mp4"


def _sandboxed_env() -> dict[str, str]:
    import os

    drop_markers = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    return {k: v for k, v in os.environ.items() if not any(m in k.upper() for m in drop_markers)}


def _limit_resources() -> None:  # pragma: no cover - exercised only on unix, in a child process
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    except Exception:
        pass


async def render(s: Settings, script: str, scene_name: str) -> bytes:
    """MP3-style contract: bytes back, disk-cached by script hash, ManimUnavailable on any failure."""
    path = cache_path(s, script)
    if path.exists():
        return path.read_bytes()
    if not manim_available():
        raise ManimUnavailable("manim is not installed on this server (uv sync --group manim)")

    with tempfile.TemporaryDirectory(prefix="oh_manim_") as tmp:
        tmp_dir = Path(tmp)
        script_path = tmp_dir / "scene.py"
        media_dir = tmp_dir / "media"
        script_path.write_text(script, encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "manim",
            "render",
            "-ql",
            "--disable_caching",
            "-o",
            "out.mp4",
            "--media_dir",
            str(media_dir),
            str(script_path),
            scene_name,
        ]
        kwargs: dict = {
            "cwd": str(tmp_dir),
            "env": _sandboxed_env(),
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if sys.platform != "win32":
            kwargs["preexec_fn"] = _limit_resources
        proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=RENDER_TIMEOUT_SECONDS)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise ManimUnavailable("manim render timed out") from None
        if proc.returncode != 0:
            raise ManimUnavailable(f"manim render failed: {stderr.decode(errors='replace')[-500:]}")
        out = next(media_dir.rglob("out.mp4"), None)
        if out is None:
            raise ManimUnavailable("manim render produced no output file")
        video = out.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(video)
    return video
