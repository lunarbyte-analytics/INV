"""Logi konsoli do debugu KSeF — włącz: KSEF_DEBUG=1 (true/yes/on)."""
from __future__ import annotations

import os


def ksef_debug_enabled() -> bool:
    v = (os.getenv("KSEF_DEBUG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def ksef_debug(msg: str) -> None:
    if ksef_debug_enabled():
        print(f"[KSeF] {msg}", flush=True)
