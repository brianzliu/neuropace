"""Environment check (FR-O1): keys, Deepgram, OpenAI model, ports, frontend build."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx

from mindwave.ports import list_serial_ports

from .config import Settings
from .signal.headset import autodetect_headset_port
from .totem.bridge import autodetect_totem_port

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


async def check_deepgram(key: str | None) -> dict:
    if not key:
        return {"ok": False, "reason": "no DEEPGRAM_API_KEY"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {key}"})
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:200]}


async def check_openai(key: str | None, model: str) -> dict:
    if not key:
        return {"ok": False, "reason": "no OPENAI_API_KEY", "model": model}
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key)
        try:
            await asyncio.wait_for(client.models.retrieve(model), timeout=10.0)
            return {"ok": True, "model": model}
        except Exception as e:  # noqa: BLE001
            names: list[str] = []
            try:
                page = await asyncio.wait_for(client.models.list(), timeout=10.0)
                names = sorted(
                    m.id for m in page.data if any(k in m.id for k in ("gpt-5", "gpt-4.1", "o4", "gpt-4o"))
                )
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False, "model": model, "reason": str(e)[:200], "alternatives": names[:20]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "model": model, "reason": str(e)[:200]}


_devices_cache: dict = {"t": 0.0, "value": None}
_devices_lock = asyncio.Lock()


async def detect_devices(s: Settings, max_age_s: float = 4.0) -> dict:
    """Which headset and pad a session would get right now. Cached briefly: the Listen screen polls it and
    Windows probes Bluetooth COM ports by opening them (a second or two each)."""
    async with _devices_lock:
        now = time.monotonic()
        if _devices_cache["value"] is not None and now - _devices_cache["t"] < max_age_s:
            return _devices_cache["value"]
        hp = (
            "sim"
            if s.headset_port == "sim"
            else (s.headset_port or await asyncio.to_thread(autodetect_headset_port))
        )
        tp = (
            "keyboard"
            if s.totem_port in ("sim", "keyboard")
            else (s.totem_port or await asyncio.to_thread(autodetect_totem_port, hp))
        )
        value = {
            "headset": {
                "port": hp,
                "kind": "simulated" if not hp or hp == "sim" else "real",
                "setting": s.headset_port,
                "bridge": "mindwave pipeline" if hp and hp != "sim" else None,
            },
            "totem": {
                "port": tp,
                "kind": "keyboard" if not tp or tp in ("sim", "keyboard") else "real",
                "setting": s.totem_port,
            },
            "checked_at": time.time(),
        }
        _devices_cache.update(t=now, value=value)
        return value


async def run_doctor(s: Settings) -> dict:
    dg, oa, dev = await asyncio.gather(
        check_deepgram(s.deepgram_api_key),
        check_openai(s.openai_api_key, s.openai_model),
        detect_devices(s, max_age_s=0.0),
    )
    return {
        "keys": {"deepgram": bool(s.deepgram_api_key), "openai": bool(s.openai_api_key)},
        "deepgram": dg,
        "tts": {"ok": bool(s.deepgram_api_key) and dg.get("ok", False), "model": s.tts_model},
        "openai": {**oa, "required": not s.allow_offline_llm},
        "headset": dev["headset"],
        "totem": dev["totem"],
        "platform": sys.platform,
        "serial_ports": [
            {"device": p.device, "description": p.description, "hwid": p.hwid, "vid": p.vid}
            for p in list_serial_ports()
        ],
        "frontend_built": (FRONTEND_DIST / "index.html").exists(),
        "data_dir": str(s.data_dir.resolve()),
        "baseline_seconds": s.baseline_seconds,
    }
