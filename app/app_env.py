"""Środowisko aplikacji (produkcja / test) — osobna baza SQLite, persystencja w pliku JSON."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

SETTINGS_FILE = Path("inv_app_settings.json")


class AppEnvironment(str, Enum):
    PRODUCTION = "production"
    TEST = "test"


_current: AppEnvironment | None = None


def load_settings() -> AppEnvironment:
    """Wczytuje ustawienie z dysku (wywołaj przed pierwszym użyciem bazy)."""
    global _current
    if _current is not None:
        return _current
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            raw = data.get("environment", AppEnvironment.PRODUCTION.value)
            if raw in (e.value for e in AppEnvironment):
                _current = AppEnvironment(raw)
            else:
                _current = AppEnvironment.PRODUCTION
        except (OSError, json.JSONDecodeError, TypeError):
            _current = AppEnvironment.PRODUCTION
    else:
        _current = AppEnvironment.PRODUCTION
    return _current


def get_environment() -> AppEnvironment:
    if _current is None:
        return load_settings()
    return _current


def set_environment(env: AppEnvironment, *, persist: bool = True) -> None:
    global _current
    _current = env
    if persist:
        SETTINGS_FILE.write_text(
            json.dumps({"environment": env.value}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def get_database_path() -> Path:
    """Ścieżka pliku SQLite zależnie od wybranego środowiska."""
    env = get_environment()
    if env == AppEnvironment.TEST:
        return Path("sqllite3_inv_test.db")
    return Path("sqllite3_inv.db")


def is_test_environment() -> bool:
    return get_environment() == AppEnvironment.TEST
