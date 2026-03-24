"""Logi konsoli do debugu KSeF — włącz: KSEF_DEBUG lub ustawienia w pliku (Plik → Ustawienia integracji)."""
from __future__ import annotations

from ..app_env import get_ksef_debug


def ksef_debug_enabled() -> bool:
    return get_ksef_debug()


def ksef_debug(msg: str) -> None:
    if ksef_debug_enabled():
        print(f"[KSeF] {msg}", flush=True)
