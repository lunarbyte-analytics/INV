"""
Klient API Hurtowni Danych CEIDG (Biznes.gov.pl) — dokumentacja integratorów v1.
Wymaga tokenu JWT z rejestracji na https://dane.biznes.gov.pl/
Zmienna środowiskowa: CEIDG_HD_API_TOKEN (alternatywnie BIZNES_GOV_HD_TOKEN).
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlencode

from ..ksef.http_json import KsefHttpError, request_json

DEFAULT_CEIDG_HD_BASE = "https://dane.biznes.gov.pl/api/ceidg/v1"


class CeidgHdError(Exception):
    """Błąd wywołania API CEIDG HD."""


class CeidgNoDataError(CeidgHdError):
    """Brak rekordu dla zapytania (HTTP 204 lub pusta lista)."""


def normalize_nip_digits(s: str | None) -> str:
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) != 10:
        raise ValueError("NIP musi składać się z 10 cyfr.")
    return d


def get_ceidg_hd_token() -> str | None:
    return (
        os.environ.get("CEIDG_HD_API_TOKEN")
        or os.environ.get("BIZNES_GOV_HD_TOKEN")
        or os.environ.get("HD_CEIDG_API_TOKEN")
    )


def _base_url() -> str:
    return (os.environ.get("CEIDG_HD_API_BASE") or DEFAULT_CEIDG_HD_BASE).rstrip("/")


def _unwrap_firma(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    f = payload.get("firma")
    if f is None:
        return None
    if isinstance(f, list):
        return f[0] if f else None
    if isinstance(f, dict):
        return f
    return None


def fetch_firma_by_nip(nip_digits: str, *, token: str | None = None) -> dict[str, Any]:
    """
    GET /firma?nip= — szczegółowe dane (nazwa, adres, telefon, e-mail wg dokumentacji).
    """
    tok = token or get_ceidg_hd_token()
    if not tok:
        raise CeidgHdError(
            "Brak tokenu API. Ustaw zmienną środowiskową CEIDG_HD_API_TOKEN "
            "(token JWT z Hurtowni danych na dane.biznes.gov.pl)."
        )
    nip_digits = normalize_nip_digits(nip_digits)
    q = urlencode({"nip": nip_digits})
    url = f"{_base_url()}/firma?{q}"
    try:
        status, data = request_json("GET", url, bearer_token=tok, timeout=60.0)
    except KsefHttpError as e:
        if e.status == 401:
            raise CeidgHdError("Odrzucone uwierzytelnienie (401). Sprawdź token CEIDG_HD_API_TOKEN.") from e
        if e.status == 403:
            raise CeidgHdError("Brak uprawnień do API (403).") from e
        if e.status == 429:
            raise CeidgHdError("Przekroczono limit zapytań do API (429). Spróbuj później.") from e
        raise CeidgHdError(str(e)) from e

    if status == 204 or data is None:
        raise CeidgNoDataError("Nie znaleziono danych CEIDG dla podanego NIP.")

    firma = _unwrap_firma(data)
    if not firma:
        raise CeidgNoDataError("Odpowiedź API nie zawiera danych firmy (firma).")

    return firma


def _country_pl(kraj: str | None) -> str:
    k = (kraj or "").strip().upper()
    if k in ("PL", "POLSKA"):
        return "Polska"
    return kraj.strip() if kraj else "Polska"


def flat_firma_for_org(firma: dict[str, Any]) -> dict[str, Any]:
    """Mapuje odpowiedź /firma na pola używane w Organization + Address."""
    adr = firma.get("adresDzialanosci") or {}
    if not isinstance(adr, dict):
        adr = {}

    bud = str(adr.get("budynek") or "").strip()
    lok = str(adr.get("lokal") or "").strip()
    street_no = bud
    if lok and bud:
        street_no = f"{bud}/{lok}"
    elif lok and not bud:
        street_no = lok

    wl = firma.get("wlasciciel") or {}
    if not isinstance(wl, dict):
        wl = {}

    nip = str(wl.get("nip") or "").replace(" ", "")
    regon = str(wl.get("regon") or "").replace(" ", "")

    tel = firma.get("telefon")
    if isinstance(tel, list):
        tel = tel[0] if tel else None
    if tel is not None:
        tel = str(tel).strip() or None

    email = firma.get("email")
    if email is not None:
        email = str(email).strip() or None

    nazwa = firma.get("nazwa")
    if nazwa is not None:
        nazwa = str(nazwa).strip() or None

    return {
        "name": nazwa,
        "phone": tel,
        "email": email,
        "org_nip": nip or None,
        "org_regon": regon or None,
        "street_name": (str(adr.get("ulica") or "").strip() or None),
        "street_number": street_no or None,
        "zip_code": (str(adr.get("kod") or "").strip() or None),
        "city": (str(adr.get("miasto") or "").strip() or None),
        "country": _country_pl(str(adr.get("kraj") or "").strip() or None),
        "status": str(firma.get("status") or "").strip() or None,
    }


def merge_pref(current: str | None, incoming: str | None) -> str | None:
    """Zwraca wartość do zapisu: uzupełnij tylko gdy bieżące jest puste."""
    cur = (current or "").strip()
    inc = (incoming or "").strip() if incoming is not None else ""
    if cur:
        return None
    if not inc:
        return None
    return inc
