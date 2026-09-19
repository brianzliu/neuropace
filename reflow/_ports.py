from __future__ import annotations


def list_serial_ports() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except Exception:  # pragma: no cover
        return []
    return [(p.device, p.description or "") for p in list_ports.comports()]
