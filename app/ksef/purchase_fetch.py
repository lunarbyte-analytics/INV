"""Pobieranie metadanych i plików XML faktur zakupowych (nabywca / Subject2) z API KSeF 2.0."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from .http_json import KsefHttpError, request_bytes, request_json


def _metadata_url(
    base_url: str,
    *,
    sort_order: str,
    page_index: int,
    page_size: int,
) -> str:
    base = base_url.rstrip("/")
    q = urlencode(
        {
            "sortOrder": sort_order,
            # pageOffset w API KSeF 2.0 = indeks strony (0, 1, 2…), NIE przesunięcie w rekordach.
            "pageOffset": str(page_index),
            "pageSize": str(page_size),
        }
    )
    return f"{base}/invoices/query/metadata?{q}"


def query_purchase_invoices_metadata(
    base_url: str,
    access_token: str,
    *,
    date_from_iso: str,
    date_to_iso: str | None,
    date_type: str = "PermanentStorage",
    sort_order: str = "Desc",
    page_index: int = 0,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    Faktury, w których zalogowany podmiot (NIP z tokenu) występuje jako nabywca — Subject2.
    Wymaga uprawnienia InvoiceRead.

    Stronicowanie: ``page_index`` to numer strony od 0 (pierwsza strona = 0, następna = 1, …),
    zgodnie z parametrem query ``pageOffset`` w API — nie należy go zwiększać o ``pageSize``.
    """
    if page_size < 10 or page_size > 250:
        raise ValueError("pageSize musi być w zakresie 10–250.")
    body: dict[str, Any] = {
        "subjectType": "Subject2",
        "dateRange": {
            "dateType": date_type,
            "from": date_from_iso,
        },
    }
    if date_to_iso:
        body["dateRange"]["to"] = date_to_iso

    url = _metadata_url(
        base_url,
        sort_order=sort_order,
        page_index=page_index,
        page_size=page_size,
    )
    status, data = request_json("POST", url, json_body=body, bearer_token=access_token)
    if status != 200 or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 200 i obiekt JSON z POST /invoices/query/metadata", status)
    return data


def download_invoice_xml(base_url: str, access_token: str, ksef_number: str) -> bytes:
    """Pobiera pojedynczą fakturę po numerze KSeF (application/xml)."""
    enc = quote(ksef_number.strip(), safe="-")
    url = f"{base_url.rstrip('/')}/invoices/ksef/{enc}"
    status, raw, _ct = request_bytes(
        "GET",
        url,
        bearer_token=access_token,
        accept="application/xml",
    )
    if status != 200:
        raise KsefHttpError(f"Oczekiwano 200 z GET /invoices/ksef/…, otrzymano {status}", status)
    return raw


def format_invoice_row(inv: dict[str, Any]) -> dict[str, Any]:
    """Spłaszcza metadane do wyświetlenia w tabeli."""
    seller = inv.get("seller") or {}
    nip = seller.get("nip") or ""
    name = seller.get("name") or ""
    return {
        "ksefNumber": inv.get("ksefNumber") or "",
        "invoiceNumber": inv.get("invoiceNumber") or "",
        "issueDate": inv.get("issueDate") or "",
        "sellerNip": nip,
        "sellerName": name,
        "grossAmount": inv.get("grossAmount"),
        "currency": inv.get("currency") or "",
        "raw": inv,
    }


def max_range_days_warning(from_dt: datetime, to_dt: datetime) -> str | None:
    """API ogranicza zakres dat (typowo do 3 miesięcy); zwraca komunikat lub None."""
    delta = to_dt - from_dt
    if delta.days > 95:
        return "Zakres dat przekracza ~3 miesiące — API KSeF może odrzucić zapytanie. Zawęż okres."
    return None
