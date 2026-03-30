"""Środowisko aplikacji (produkcja / test) — osobna baza SQLite, persystencja w pliku JSON."""
from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path("inv_app_settings.json")

# Domyślne adresy API KSeF v2 — gdy w ustawieniach i KSEF_TEST_BASE_URL jest pusto
DEFAULT_KSEF_TEST_BASE_URL = "https://api-test.ksef.mf.gov.pl/v2"
DEFAULT_KSEF_PRODUCTION_BASE_URL = "https://api.ksef.mf.gov.pl/v2"
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
# Osobne zestawy dla production / test (klucze w integration.{production|test}).


def _integration_env_key() -> str:
    return "test" if get_environment() == AppEnvironment.TEST else "production"


def _migrate_legacy_integration(data: dict[str, Any]) -> bool:
    """
    Stary format: integration: { ksef_token, ... }.
    Nowy: integration: { production: {...}, test: {...} }.
    Zwraca True, jeśli wykonano migrację i zapisano plik.
    """
    raw = data.get("integration")
    if not isinstance(raw, dict):
        return False
    if "production" in raw or "test" in raw:
        return False
    if not any(
        k in raw
        for k in (
            "ksef_token",
            "ksef_nip",
            "ksef_test_base_url",
            "ksef_debug",
            "ceidg_hd_api_token",
            "ceidg_hd_api_base",
            "ceidg_debug",
        )
    ):
        return False
    data["integration"] = {
        "production": dict(raw),
        "test": {},
    }
    if "environment" not in data:
        data["environment"] = get_environment().value
    _save_settings_file(data)
    return True


def _integration_block_for_key(data: dict[str, Any], key: str) -> dict[str, Any]:
    raw = data.get("integration")
    if not isinstance(raw, dict):
        return {}
    if "production" not in raw and "test" not in raw:
        return {}
    block = raw.get(key)
    if not isinstance(block, dict):
        return {}
    return block


def _integration_raw() -> dict[str, Any]:
    data = _load_settings_file()
    if _migrate_legacy_integration(data):
        data = _load_settings_file()
    return _integration_block_for_key(data, _integration_env_key())


def _normalize_integration_block(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "ksef_token": str(r.get("ksef_token") or ""),
        "ksef_nip": str(r.get("ksef_nip") or ""),
        "ksef_test_base_url": str(r.get("ksef_test_base_url") or ""),
        "ksef_debug": bool(r.get("ksef_debug")) if "ksef_debug" in r else False,
        "ceidg_hd_api_token": str(r.get("ceidg_hd_api_token") or ""),
        "ceidg_hd_api_base": str(r.get("ceidg_hd_api_base") or ""),
        "ceidg_debug": bool(r.get("ceidg_debug")) if "ceidg_debug" in r else False,
    }


def get_integration_dict() -> dict[str, Any]:
    """Wartości z pliku dla bieżącego środowiska (Plik → Środowisko)."""
    return _normalize_integration_block(_integration_raw())


def get_integration_dict_for_env(env: AppEnvironment) -> dict[str, Any]:
    """Wartości z pliku dla wskazanego środowiska (bez wpływu Plik → Środowisko)."""
    data = _load_settings_file()
    if _migrate_legacy_integration(data):
        data = _load_settings_file()
    key = "test" if env == AppEnvironment.TEST else "production"
    return _normalize_integration_block(_integration_block_for_key(data, key))


def _clean_integration_dict(integration: dict[str, Any]) -> dict[str, Any]:
    return {
        "ksef_token": str(integration.get("ksef_token") or ""),
        "ksef_nip": str(integration.get("ksef_nip") or ""),
        "ksef_test_base_url": str(integration.get("ksef_test_base_url") or ""),
        "ksef_debug": bool(integration.get("ksef_debug")),
        "ceidg_hd_api_token": str(integration.get("ceidg_hd_api_token") or ""),
        "ceidg_hd_api_base": str(integration.get("ceidg_hd_api_base") or ""),
        "ceidg_debug": bool(integration.get("ceidg_debug")),
    }


def save_integration_dict(integration: dict[str, Any], *, persist: bool = True) -> None:
    """Zapisuje zestaw integracji dla bieżącego środowiska (drugi zestaw pozostaje bez zmian)."""
    data = _load_settings_file()
    _migrate_legacy_integration(data)
    data = _load_settings_file()
    key = _integration_env_key()
    clean = _clean_integration_dict(integration)
    if not isinstance(data.get("integration"), dict):
        data["integration"] = {}
    integ = data["integration"]
    if not isinstance(integ.get("production"), dict):
        integ["production"] = {}
    if not isinstance(integ.get("test"), dict):
        integ["test"] = {}
    integ[key] = clean
    if "environment" not in data:
        data["environment"] = get_environment().value
    if persist:
        _save_settings_file(data)


def save_integration_both(
    production: dict[str, Any],
    test: dict[str, Any],
    *,
    persist: bool = True,
) -> None:
    """Zapisuje oba zestawy integracji (production i test) w jednym zapisie pliku."""
    data = _load_settings_file()
    _migrate_legacy_integration(data)
    data = _load_settings_file()
    if not isinstance(data.get("integration"), dict):
        data["integration"] = {}
    integ = data["integration"]
    integ["production"] = _clean_integration_dict(production)
    integ["test"] = _clean_integration_dict(test)
    if "environment" not in data:
        data["environment"] = get_environment().value
    if persist:
        _save_settings_file(data)


def get_ksef_token() -> str:
    """Najpierw niepusty token z pliku (profil wg Plik → Środowisko), potem KSEF_TOKEN."""
    f = (get_integration_dict().get("ksef_token") or "").strip()
    if f:
        return f
    return (os.getenv("KSEF_TOKEN") or "").strip()


def get_ksef_nip() -> str:
    """Najpierw niepusty NIP z pliku, potem KSEF_NIP."""
    f = (get_integration_dict().get("ksef_nip") or "").strip()
    if f:
        return f
    return (os.getenv("KSEF_NIP") or "").strip()


def get_ksef_test_base_url() -> str:
    """
    Adres API v2 (bez domyślnego hosta): najpierw niepusta wartość z pliku,
    potem zmienne środowiskowe dopasowane do środowiska aplikacji.

    Uwaga: globalna zmienna KSEF_TEST_BASE_URL nie jest używana w trybie produkcyjnym
    aplikacji (żeby nie wymuszać api-test przy zapisanym api.ksef w pliku).
    Gdy pole w pliku jest puste: w trybie testowym — KSEF_TEST_BASE_URL;
    w trybie produkcyjnym — KSEF_BASE_URL lub KSEF_PRODUCTION_BASE_URL.
    """
    f = (get_integration_dict().get("ksef_test_base_url") or "").strip()
    if f:
        return f
    if get_environment() == AppEnvironment.TEST:
        return (os.getenv("KSEF_TEST_BASE_URL") or "").strip()
    return (os.getenv("KSEF_BASE_URL") or os.getenv("KSEF_PRODUCTION_BASE_URL") or "").strip()


def get_default_ksef_api_base_url() -> str:
    """Host API v2 używany przy pustym polu URL: test → api-test, produkcja aplikacji → api.ksef."""
    u = (
        DEFAULT_KSEF_TEST_BASE_URL
        if get_environment() == AppEnvironment.TEST
        else DEFAULT_KSEF_PRODUCTION_BASE_URL
    )
    return u.rstrip("/")


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
