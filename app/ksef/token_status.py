"""Pobranie statusu tokena KSeF: GET /tokens/{referenceNumber} (wymaga access token)."""
from __future__ import annotations

from typing import Any

from .auth_flow import obtain_access_token
from .env_normalize import ensure_ksef_nip_matches_token, normalize_ksef_nip, normalize_ksef_token
from .http_json import KsefHttpError, request_json


def parse_reference_from_ksef_token(ksef_token: str) -> str:
    """Numer referencyjny to część tokena przed pierwszym znakiem |."""
    t = normalize_ksef_token(ksef_token)
    if not t:
        raise ValueError("Pusty token KSeF.")
    part = t.split("|", 1)[0].strip()
    if not part:
        raise ValueError("Token nie zawiera numeru referencyjnego (fragment przed pierwszym |).")
    return part


def fetch_token_status(base_url: str, *, ksef_token: str, nip: str) -> dict[str, Any]:
    """
    Uzyskuje access token (jak przy wysyłce faktury), potem GET /tokens/{ref}.
    Zwraca JSON z polami m.in. status, description, dateCreated.
    """
    base = base_url.strip().rstrip("/")
    tok = normalize_ksef_token(ksef_token)
    nip_d = normalize_ksef_nip(nip)
    if not tok:
        raise ValueError("Brak tokena KSeF.")
    if len(nip_d) != 10:
        raise ValueError("NIP musi mieć dokładnie 10 cyfr.")

    ensure_ksef_nip_matches_token(tok, nip_d)

    ref = parse_reference_from_ksef_token(tok)
    access = obtain_access_token(base, ksef_token=tok, nip=nip_d)
    status, data = request_json(
        "GET",
        f"{base}/tokens/{ref}",
        bearer_token=access,
    )
    if status != 200 or not isinstance(data, dict):
        raise KsefHttpError(f"Oczekiwano 200 z GET /tokens/{{ref}}, otrzymano HTTP {status}", status)
    return data
