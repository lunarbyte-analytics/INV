"""Integracja z Hurtownią danych CEIDG (Biznes.gov.pl)."""

from .hd_client import (
    CeidgHdError,
    CeidgNoDataError,
    fetch_firma_by_nip,
    flat_firma_for_org,
    get_ceidg_hd_token,
    normalize_nip_digits,
)

__all__ = [
    "CeidgHdError",
    "CeidgNoDataError",
    "fetch_firma_by_nip",
    "flat_firma_for_org",
    "get_ceidg_hd_token",
    "normalize_nip_digits",
]
