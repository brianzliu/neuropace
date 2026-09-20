from __future__ import annotations

import secrets


def new_id(prefix: str) -> str:
    """Short, greppable ids: prefix + 8 hex chars (e.g. sess_1a2b3c4d)."""
    return f"{prefix}_{secrets.token_hex(4)}"
