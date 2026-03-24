"""Logi konsoli dla operacji CEIDG — włącz: CEIDG_DEBUG=1 lub Plik → Ustawienia integracji (checkbox)."""
from __future__ import annotations

from ..app_env import get_ceidg_debug


def ceidg_debug_enabled() -> bool:
    return get_ceidg_debug()


def ceidg_debug(msg: str) -> None:
    if ceidg_debug_enabled():
        print(f"[CEIDG] {msg}", flush=True)
