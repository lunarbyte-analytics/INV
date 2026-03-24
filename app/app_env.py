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
    data = _load_settings_file()
    if data:
        raw = data.get("environment", AppEnvironment.PRODUCTION.value)
        if raw in (e.value for e in AppEnvironment):
            _current = AppEnvironment(raw)
        else:
            _current = AppEnvironment.PRODUCTION
    else:
        _current = AppEnvironment.PRODUCTION
    return _current


def get_environment() -> AppEnvironment:
    if _current is None:
        return load_settings()
    return _current


def _load_settings_file() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _save_settings_file(data: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def set_environment(env: AppEnvironment, *, persist: bool = True) -> None:
    global _current
    _current = env
    if persist:
        data = _load_settings_file()
        data["environment"] = env.value
        _save_settings_file(data)


def get_context_organization_id() -> int | None:
    """Wybrana w UI „moja firma” — do rozróżnienia sprzedaży i zakupu na liście faktur."""
    v = _load_settings_file().get("context_organization_id")
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def set_context_organization_id(org_id: int | None, *, persist: bool = True) -> None:
    data = _load_settings_file()
    if org_id is None:
        data.pop("context_organization_id", None)
    else:
        data["context_organization_id"] = int(org_id)
    if "environment" not in data:
        data["environment"] = get_environment().value
    if persist:
        _save_settings_file(data)


def get_database_path() -> Path:
    """Ścieżka pliku SQLite zależnie od wybranego środowiska."""
    env = get_environment()
    if env == AppEnvironment.TEST:
        return Path("sqllite3_inv_test.db")
    return Path("sqllite3_inv.db")


def is_test_environment() -> bool:
    return get_environment() == AppEnvironment.TEST
