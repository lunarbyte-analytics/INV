"""
Klient API Hurtowni Danych CEIDG (Biznes.gov.pl) — API HD v3.
Bazowy URL: …/api/ceidg/v3 (bez /firma, /firmy na końcu).
GET /firma?nip=… — zgodnie z dokumentacją PDF (np. „HD CEIDG - API v3 HD - Dokumentacja dla integratorów”);
OpenAPI w repozytorium opisuje requestData, ale produkcyjne API przyjmuje prosty parametr nip.
Wymaga tokenu JWT z rejestracji na https://dane.biznes.gov.pl/
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from ..app_env import get_ceidg_hd_api_base, get_ceidg_hd_api_token
from ..ksef.http_json import KsefHttpError, request_json

from .debug_log import ceidg_debug


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
    t = get_ceidg_hd_api_token().strip()
    return t or None


def _base_url() -> str:
    return get_ceidg_hd_api_base()


def _normalize_ceidg_base(base: str) -> str:
    """Usuwa przypadkowe końcówki ścieżki (/firma, /firmy), żeby nie powstało …/firmy/firma."""
    b = (base or "").strip().rstrip("/")
    for suffix in ("/firmy", "/firma"):
        if b.endswith(suffix):
            b = b[: -len(suffix)].rstrip("/")
    return b


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
    GET /firma?nip=… — dokumentacja HD v3 (curl w PDF integratora).
    """
    tok = token or get_ceidg_hd_token()
    if not tok:
        raise CeidgHdError(
            "Brak tokenu API. Ustaw token w menu Plik → Ustawienia integracji… "
            "lub zmienną CEIDG_HD_API_TOKEN (token JWT z dane.biznes.gov.pl)."
        )
    nip_digits = normalize_nip_digits(nip_digits)
    q = urlencode({"nip": nip_digits})
    base = _normalize_ceidg_base(_base_url())
    url = f"{base}/firma?{q}"
    ceidg_debug(f"GET {url} (token length={len(tok)})")
    try:
        status, data = request_json("GET", url, bearer_token=tok, timeout=60.0)
    except KsefHttpError as e:
        ceidg_debug(f"HTTP error status={e.status} body[:400]={(e.body or '')[:400]!r}")
        if e.status == 401:
            raise CeidgHdError("Odrzucone uwierzytelnienie (401). Sprawdź token w ustawieniach lub CEIDG_HD_API_TOKEN.") from e
        if e.status == 403:
            raise CeidgHdError("Brak uprawnień do API (403).") from e
        if e.status == 404:
            body = (e.body or "").lower()
            if "context-path" in body or "no context-path" in body:
                raise CeidgHdError(
                    "API zwróciło 404 (brak ścieżki) — bazowy adres Hurtowni CEIDG prawdopodobnie "
                    "nie zgadza się z aktualną dokumentacją (np. zmiana wersji API). "
                    "W panelu dane.biznes.gov.pl / dokumentacji dla integratorów sprawdź "
                    "bieżący URL i ustaw go w Plik → Ustawienia integracji… (pole „Bazowy URL API”) "
                    "lub zmienną CEIDG_HD_API_BASE."
                ) from e
            raise CeidgHdError(
                "Nie znaleziono zasobu (404). Sprawdź NIP oraz bazowy URL API CEIDG."
            ) from e
        if e.status == 429:
            raise CeidgHdError("Przekroczono limit zapytań do API (429). Spróbuj później.") from e
        raise CeidgHdError(str(e)) from e

    if isinstance(data, dict):
        ceidg_debug(f"HTTP {status} response keys={list(data.keys())}")
    else:
        ceidg_debug(f"HTTP {status} response type={type(data).__name__!r}")

    if status == 204 or data is None:
        ceidg_debug("204 lub pusta odpowiedź — brak danych dla NIP")
        raise CeidgNoDataError("Nie znaleziono danych CEIDG dla podanego NIP.")

    firma = _unwrap_firma(data)
    if not firma:
        ceidg_debug("pole 'firma' puste lub nieobecne po parsowaniu")
        raise CeidgNoDataError("Odpowiedź API nie zawiera danych firmy (firma).")

    ceidg_debug(
        "firma: "
        + ", ".join(
            f"{k}={firma.get(k)!r}"
            for k in ("nazwa", "status", "id")
            if k in firma
        )
    )
    return firma


def _country_pl(kraj: str | None) -> str:
    k = (kraj or "").strip().upper()
    if k in ("PL", "POLSKA"):
        return "Polska"
    return kraj.strip() if kraj else "Polska"


def _adres_dzialalnosci(firma: dict[str, Any]) -> dict[str, Any]:
    """v3: adresDzialalnosci; starsze odpowiedzi: adresDzialanosci (literówka w starym API)."""
    raw = firma.get("adresDzialalnosci") or firma.get("adresDzialanosci") or {}
    return raw if isinstance(raw, dict) else {}


def _status_str(firma: dict[str, Any]) -> str | None:
    st = firma.get("status")
    if st is None:
        return None
    if isinstance(st, str):
        return st.strip() or None
    return str(st).strip() or None


def flat_firma_for_org(firma: dict[str, Any]) -> dict[str, Any]:
    """Mapuje odpowiedź /firma na pola używane w Organization + Address."""
    adr = _adres_dzialalnosci(firma)

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
        "status": _status_str(firma),
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
