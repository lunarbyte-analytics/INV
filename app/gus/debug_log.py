"""Logi konsoli dla operacji GUS BIR — włącz: GUS_DEBUG=1 lub Plik → Ustawienia integracji (checkbox)."""
from __future__ import annotations

from ..app_env import get_gus_debug


def gus_debug_enabled() -> bool:
    return get_gus_debug()


def gus_debug(msg: str) -> None:
    if gus_debug_enabled():
        print(f"[GUS] {msg}", flush=True)
