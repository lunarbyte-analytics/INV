"""Środowisko aplikacji (produkcja / test) — osobna baza SQLite, persystencja w pliku JSON."""
from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path("inv_app_settings.json")

# Domyślny adres API KSeF v2 (środowisko testowe) — jak w app/ksef/client.py
DEFAULT_KSEF_TEST_BASE_URL = "https://api-test.ksef.mf.gov.pl/v2"
# Hurtownia danych CEIDG — OpenAPI „API HD v3” (servers.url w API HD v3.json)
DEFAULT_CEIDG_HD_API_BASE = "https://dane.biznes.gov.pl/api/ceidg/v3"


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


# --- Integracja KSeF / CEIDG (plik JSON + nadpisanie zmiennymi środowiskowymi) ---


def _integration_raw() -> dict[str, Any]:
    data = _load_settings_file().get("integration")
    return data if isinstance(data, dict) else {}


def get_integration_dict() -> dict[str, Any]:
    """Wartości z pliku ustawień (do edycji w oknie Ustawienia)."""
    r = _integration_raw()
    return {
        "ksef_token": str(r.get("ksef_token") or ""),
        "ksef_nip": str(r.get("ksef_nip") or ""),
        "ksef_test_base_url": str(r.get("ksef_test_base_url") or ""),
        "ksef_debug": bool(r.get("ksef_debug")) if "ksef_debug" in r else False,
        "ceidg_hd_api_token": str(r.get("ceidg_hd_api_token") or ""),
        "ceidg_hd_api_base": str(r.get("ceidg_hd_api_base") or ""),
        "ceidg_debug": bool(r.get("ceidg_debug")) if "ceidg_debug" in r else False,
    }


def save_integration_dict(integration: dict[str, Any], *, persist: bool = True) -> None:
    """Zapisuje sekcję integration (pozostałe klucze pliku bez zmian)."""
    data = _load_settings_file()
    clean = {
        "ksef_token": str(integration.get("ksef_token") or ""),
        "ksef_nip": str(integration.get("ksef_nip") or ""),
        "ksef_test_base_url": str(integration.get("ksef_test_base_url") or ""),
        "ksef_debug": bool(integration.get("ksef_debug")),
        "ceidg_hd_api_token": str(integration.get("ceidg_hd_api_token") or ""),
        "ceidg_hd_api_base": str(integration.get("ceidg_hd_api_base") or ""),
        "ceidg_debug": bool(integration.get("ceidg_debug")),
    }
    data["integration"] = clean
    if "environment" not in data:
        data["environment"] = get_environment().value
    if persist:
        _save_settings_file(data)


def get_ksef_token() -> str:
    v = (os.getenv("KSEF_TOKEN") or "").strip()
    if v:
        return v
    return (get_integration_dict().get("ksef_token") or "").strip()


def get_ksef_nip() -> str:
    v = (os.getenv("KSEF_NIP") or "").strip()
    if v:
        return v
    return (get_integration_dict().get("ksef_nip") or "").strip()


def get_ksef_test_base_url() -> str:
    v = (os.getenv("KSEF_TEST_BASE_URL") or "").strip()
    if v:
        return v
    return (get_integration_dict().get("ksef_test_base_url") or "").strip()


def get_ksef_debug() -> bool:
    raw = os.getenv("KSEF_DEBUG")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return bool(get_integration_dict().get("ksef_debug"))


def get_ceidg_hd_api_token() -> str:
    for key in ("CEIDG_HD_API_TOKEN", "BIZNES_GOV_HD_TOKEN", "HD_CEIDG_API_TOKEN"):
        v = (os.getenv(key) or "").strip()
        if v:
            return v
    return (get_integration_dict().get("ceidg_hd_api_token") or "").strip()


def get_ceidg_hd_api_base() -> str:
    v = (os.getenv("CEIDG_HD_API_BASE") or "").strip()
    if v:
        return v.rstrip("/")
    f = (get_integration_dict().get("ceidg_hd_api_base") or "").strip()
    if f:
        return f.rstrip("/")
    return DEFAULT_CEIDG_HD_API_BASE.rstrip("/")


def get_ceidg_debug() -> bool:
    """Logi [CEIDG] na konsoli — CEIDG_DEBUG=1 lub ustawienia (checkbox)."""
    raw = os.getenv("CEIDG_DEBUG")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return bool(get_integration_dict().get("ceidg_debug"))
