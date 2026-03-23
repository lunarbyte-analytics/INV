"""Normalizacja KSEF_TOKEN / KSEF_NIP ze zmiennych środowiskowych (Windows, cudzysłowy, BOM)."""
from __future__ import annotations

import re


def normalize_ksef_token(raw: str | None) -> str:
    if not raw:
        return ""
    s = raw.strip()
    # BOM / znaki niewidoczne
    s = s.strip("\ufeff\u200b\u200c\u200d")
    # Cudzysłowy z edytora zmiennych Windows
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    s = s.replace("\r", "").replace("\n", " ").strip()
    return s


def normalize_ksef_nip(raw: str | None) -> str:
    return re.sub(r"\D", "", (raw or ""))


def nip_from_ksef_token_middle_segment(ksef_token: str) -> str | None:
    """
    Z drugiego segmentu tokena (po pierwszym |) typu nip-XXXXXXXXXX zwraca 10 cyfr NIP.
    Inne formaty (np. internalId-...) — None (nie weryfikujemy automatycznie).
    """
    t = normalize_ksef_token(ksef_token)
    parts = t.split("|")
    if len(parts) < 2:
        return None
    mid = parts[1].strip().lower()
    if mid.startswith("nip-"):
        return re.sub(r"\D", "", mid[4:])
    return None


def ensure_ksef_nip_matches_token(ksef_token: str, nip_10: str) -> None:
    """Jeśli token zawiera segment nip-..., musi być zgodny z KSEF_NIP — inaczej 450 w API."""
    emb = nip_from_ksef_token_middle_segment(ksef_token)
    if emb is None:
        return
    if len(nip_10) != 10:
        return
    if emb != nip_10:
        raise ValueError(
            "NIP w zmiennej KSEF_NIP musi być taki sam jak w tokenie (środkowa część między |).\n"
            f"  W tokenie (nip-...): {emb}\n"
            f"  KSEF_NIP:            {nip_10}\n"
            "Popraw KSEF_NIP lub wygeneruj token dla właściwego podmiotu."
        )
