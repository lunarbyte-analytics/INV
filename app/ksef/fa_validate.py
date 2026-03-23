"""
Walidacja danych faktury przed wysyłką do KSeF (FA(2)).

Opiera się na:
- dokumentacji KSeF (m.in. weryfikacja faktury, limity rozmiaru),
- regułach unikalności dokumentu (NIP sprzedawcy + RodzajFaktury + P_2),
- poprawności NIP (suma kontrolna — dla PL),
- polach wymaganych przez generator XML (zgodnie ze schematem logicznym FA(2)).

Szczegółowe wymagania XSD: schemat FA(2) publikowany przez MF / repozytorium ksef-docs.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .fa_xml import compute_fa2_lines

# Limit rozmiaru faktury bez załączników (KSeF — dokumentacja integracyjna).
MAX_INVOICE_BYTES = 1_000_000

_NIP_PL_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
_PL_ZIP = re.compile(r"^\d{2}-\d{3}$")


def is_valid_nip_pl(nip: str) -> bool:
    """Walidacja polskiego NIP (10 cyfr, suma kontrolna)."""
    if len(nip) != 10 or not nip.isdigit():
        return False
    s = sum(int(nip[i]) * _NIP_PL_WEIGHTS[i] for i in range(9))
    r = s % 11
    if r == 10:
        return False
    return int(nip[9]) == r


def _parse_date_ymd(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    t = str(s).strip()[:10]
    if len(t) != 10 or t[4] != "-" or t[7] != "-":
        return None
    try:
        return date(int(t[:4]), int(t[5:7]), int(t[8:10]))
    except ValueError:
        return None


def _nonempty_str(x: Any, label: str, errors: list[str], *, max_len: int | None = None) -> str | None:
    v = (x if x is not None else "")
    s = str(v).strip()
    if not s:
        errors.append(f"Brak lub pusty: {label}.")
        return None
    if max_len is not None and len(s) > max_len:
        errors.append(f"{label}: przekroczono limit {max_len} znaków (FA(2)).")
        return None
    return s


def validate_invoice_for_ksef(
    header: dict,
    details: list[dict],
    *,
    env_nip: str | None = None,
) -> None:
    """
    Sprawdza dane przed złożeniem FA(2) do KSeF.
    Przy błędach rzuca ValueError z listą punktów (po polsku).
    """
    errors: list[str] = []

    type_name = (header.get("TypeName") or "").lower()
    if "korekt" in type_name:
        errors.append(
            "Typ „faktura korygująca” nie jest obsługiwany przez ten eksport (wymagany pełny XML KOR)."
        )

    if not details:
        errors.append("Faktura musi mieć co najmniej jedną pozycję.")

    _nonempty_str(
        header.get("Name"),
        "Numer faktury (pole „Nazwa” w aplikacji — mapuje się na P_2 w FA; KSeF wymaga unikalności z NIP i rodzajem dokumentu)",
        errors,
        max_len=256,
    )
    _nonempty_str(header.get("CompanyName"), "Nazwa sprzedawcy", errors, max_len=512)
    _nonempty_str(header.get("CustomerName"), "Nazwa nabywcy", errors, max_len=512)

    co_nip = re.sub(r"\D", "", str(header.get("CoNIP") or ""))
    cu_nip = re.sub(r"\D", "", str(header.get("CuNIP") or ""))
    if len(co_nip) != 10 or not co_nip.isdigit():
        errors.append("NIP sprzedawcy: wymagane dokładnie 10 cyfr.")
    elif not is_valid_nip_pl(co_nip):
        errors.append("NIP sprzedawcy: niepoprawna suma kontrolna (sprawdź numer).")

    if len(cu_nip) != 10 or not cu_nip.isdigit():
        errors.append("NIP nabywcy: wymagane dokładnie 10 cyfr.")
    elif not is_valid_nip_pl(cu_nip):
        errors.append("NIP nabywcy: niepoprawna suma kontrolna (sprawdź numer).")

    if env_nip and co_nip:
        env_d = re.sub(r"\D", "", env_nip)
        if len(env_d) == 10 and env_d != co_nip:
            errors.append(
                "KSEF_NIP ze środowiska musi być zgodny z NIP sprzedawcy na fakturze "
                f"(token jest dla podmiotu {env_d}, na fakturze: {co_nip})."
            )

    d_issue = _parse_date_ymd(header.get("CreateDate"))
    if d_issue is None:
        errors.append("Data wystawienia (CreateDate) — wymagany format RRRR-MM-DD.")
    else:
        today = date.today()
        if d_issue > today:
            errors.append(
                "Data wystawienia faktury (P_1) nie może być późniejsza niż dziś "
                "(KSeF odrzuca dokument z przyszłą datą względem przyjęcia)."
            )

    raw_sales = str(header.get("SalesDate") or "").strip()
    d_sales = _parse_date_ymd(header.get("SalesDate")) if raw_sales else None
    if raw_sales and d_sales is None:
        errors.append("Data sprzedaży (SalesDate) — niepoprawny format (oczekiwane RRRR-MM-DD).")
    if d_issue is not None and d_sales is not None and d_sales > d_issue:
        errors.append("Data sprzedaży nie może być późniejsza niż data wystawienia faktury.")

    def _check_addr(prefix: str, street: Any, zipc: Any, city: Any, country: Any) -> None:
        cc = _country_code_for_validate(country)
        z = (str(zipc or "").strip())
        c = (str(city or "").strip())
        st = (str(street or "").strip())
        if cc == "PL" and z and not _PL_ZIP.match(z):
            errors.append(
                f"{prefix}: dla kraju PL kod pocztowy powinien mieć format XX-XXX (jest: {z!r})."
            )
        if not st and not (c or z):
            errors.append(
                f"{prefix}: uzupełnij co najmniej ulicę lub kombinację miejscowość + kod — "
                "w FA wymagany jest adres (AdresL1 / AdresL2)."
            )

    _check_addr("Adres sprzedawcy", header.get("CoStreet"), header.get("CoZip"), header.get("CoCity"), header.get("CoCountry"))
    _check_addr("Adres nabywcy", header.get("CuStreet"), header.get("CuZip"), header.get("CuCity"), header.get("CuCountry"))

    for i, row in enumerate(details, start=1):
        try:
            q = Decimal(str(row.get("Quantity")))
        except Exception:
            errors.append(f"Pozycja {i}: niepoprawna ilość (Quantity).")
            continue
        if q <= 0:
            errors.append(f"Pozycja {i}: ilość musi być większa od zera (FA: P_8B).")
        try:
            p = Decimal(str(row.get("UnitPrice")))
        except Exception:
            errors.append(f"Pozycja {i}: niepoprawna cena jednostkowa (UnitPrice).")
            continue
        if p < 0:
            errors.append(f"Pozycja {i}: cena jednostkowa nie może być ujemna.")
        svc = (str(row.get("ServiceName") or "")).strip()
        if not svc:
            errors.append(f"Pozycja {i}: brak nazwy towaru/usługi (P_7).")
        try:
            float(row.get("TaxValue"))
        except (TypeError, ValueError):
            errors.append(f"Pozycja {i}: niepoprawna stawka VAT (TaxValue).")

    if errors:
        raise ValueError("Nie można wysłać faktury do KSeF — popraw dane:\n" + "\n".join(f"• {e}" for e in errors))

    try:
        compute_fa2_lines(header, details)
    except ValueError as e:
        raise ValueError("Nie można zbudować FA(2):\n" + str(e)) from e


def _country_code_for_validate(s: str | None) -> str:
    c = (s or "").strip().upper()
    if not c or c == "POLSKA" or c == "PL":
        return "PL"
    if len(c) == 2:
        return c
    return "PL"


def validate_xml_size_fits_ksef(xml_bytes: bytes) -> None:
    """Po zbudowaniu XML — limit 1 MB (KSeF)."""
    n = len(xml_bytes)
    if n > MAX_INVOICE_BYTES:
        raise ValueError(
            f"Wygenerowany XML ma {n} bajtów — limit KSeF dla faktury bez załączników to {MAX_INVOICE_BYTES} bajtów (1 MB)."
        )
