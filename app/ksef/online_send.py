"""Sesja interaktywna: otwarcie → wysłanie faktury → zamknięcie."""
from __future__ import annotations

import base64
import hashlib
import re
import time
from typing import Any
from urllib.parse import quote

from .crypto_util import _pick_cert, encrypt_aes256_cbc_pkcs7, encrypt_rsa_oaep_sha256_der, new_aes_key_iv
from .debug_log import ksef_debug
from .http_json import KsefHttpError, request_json

# Kody „w toku” (GET /sessions/.../invoices/...) — należy ponawiać odpytanie.
_PENDING_INVOICE_STATUS_CODES = frozenset({100, 150})

# Wzorzec KsefNumber z OpenAPI KSeF 2.0 (TNumerKSeF) — odróżnia numer KSeF od numeru ref. sesji (…-EE-…).
_KSEF_NUMBER_RE = re.compile(
    r"^([1-9](\d[1-9]|[1-9]\d)\d{7})-(20[2-9][0-9]|2[1-9]\d{2}|[3-9]\d{3})"
    r"(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-([0-9A-F]{6})-?([0-9A-F]{6})-([0-9A-F]{2})$",
    re.IGNORECASE,
)


def extract_ksef_number_from_status(data: dict[str, Any] | None) -> str | None:
    """
    Numer KSeF (TNumerKSeF) jest w odpowiedzi GET statusu faktury w sesji na poziomie głównym
    (SessionInvoiceStatusResponse.ksefNumber), nie wewnątrz statusu.
    """
    if not isinstance(data, dict):
        return None
    for key in ("ksefNumber", "KsefNumber"):
        v = data.get(key)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    for nest in ("invoice", "invoiceStatus"):
        inner = data.get(nest)
        if isinstance(inner, dict):
            for key in ("ksefNumber", "KsefNumber"):
                v = inner.get(key)
                if v is not None:
                    s = str(v).strip()
                    if s:
                        return s
    return None


def is_valid_ksef_number_format(s: str) -> bool:
    """True, jeśli łańcuch wygląda na numer KSeF z API (nie numer ref. faktury w sesji …-EE-…)."""
    t = (s or "").strip()
    if not t:
        return False
    if "-EE-" in t.upper():
        return False
    return bool(_KSEF_NUMBER_RE.match(t))


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def open_online_session_fa3(
    base_url: str,
    access_token: str,
    symmetric_key_cert_der: bytes,
) -> tuple[str, bytes, bytes]:
    aes_key, iv = new_aes_key_iv()
    enc_sym = encrypt_rsa_oaep_sha256_der(symmetric_key_cert_der, aes_key)
    body = {
        # Od 2026-02-01 KSeF 2.0 w praktyce wymaga FA(3).
        "formCode": {"systemCode": "FA (3)", "schemaVersion": "1-0E", "value": "FA"},
        "encryption": {
            "encryptedSymmetricKey": _b64(enc_sym),
            "initializationVector": _b64(iv),
        },
    }
    status, data = request_json(
        "POST",
        f"{base_url}/sessions/online",
        json_body=body,
        bearer_token=access_token,
    )
    if status != 201 or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 201 z POST /sessions/online", status)
    ref = data.get("referenceNumber")
    if not ref:
        raise KsefHttpError("Brak referenceNumber sesji", None)
    ksef_debug(f"open_online_session_fa3: sesja={ref!r}, POST /sessions/online → {status}")
    return str(ref), aes_key, iv


def send_encrypted_invoice(
    base_url: str,
    access_token: str,
    session_ref: str,
    invoice_xml_bytes: bytes,
    aes_key: bytes,
    iv: bytes,
) -> dict[str, Any]:
    enc_body = encrypt_aes256_cbc_pkcs7(aes_key, iv, invoice_xml_bytes)
    h_inv = hashlib.sha256(invoice_xml_bytes).digest()
    h_enc = hashlib.sha256(enc_body).digest()
    payload = {
        "invoiceHash": _b64(h_inv),
        "invoiceSize": len(invoice_xml_bytes),
        "encryptedInvoiceHash": _b64(h_enc),
        "encryptedInvoiceSize": len(enc_body),
        "encryptedInvoiceContent": _b64(enc_body),
        "offlineMode": False,
    }
    status, data = request_json(
        "POST",
        f"{base_url}/sessions/online/{session_ref}/invoices",
        json_body=payload,
        bearer_token=access_token,
    )
    if status not in (200, 202) or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 200/202 z wysłania faktury", status)
    inv_ref = data.get("referenceNumber")
    ksef_debug(
        f"send_encrypted_invoice: HTTP {status}, faktura ref={inv_ref!r}, "
        f"xml_bajtów={len(invoice_xml_bytes)}, szyfrogram_bajtów={len(enc_body)}"
    )
    return data


def _invoice_status_url(base_url: str, session_ref: str, invoice_ref: str) -> str:
    b = base_url.rstrip("/")
    sr = quote(str(session_ref), safe="-_.~")
    ir = quote(str(invoice_ref), safe="-_.~")
    return f"{b}/sessions/{sr}/invoices/{ir}"


def fetch_session_invoice_status(
    base_url: str,
    access_token: str,
    session_ref: str,
    invoice_ref: str,
) -> dict[str, Any]:
    """GET /sessions/{session}/invoices/{invoice} — pełny status faktury w sesji."""
    url = _invoice_status_url(base_url, session_ref, invoice_ref)
    status, data = request_json("GET", url, bearer_token=access_token)
    if status != 200 or not isinstance(data, dict):
        raise KsefHttpError(f"Oczekiwano 200 z GET statusu faktury, otrzano {status}", status)
    return data


def wait_for_session_invoice_result(
    base_url: str,
    access_token: str,
    session_ref: str,
    invoice_ref: str,
    *,
    max_wait_s: float = 120.0,
    interval_s: float = 0.45,
) -> dict[str, Any]:
    """
    Oczekuje na status końcowy przetwarzania faktury (asynchroniczna weryfikacja XSD/semantyki).
    Zwraca ostatnią odpowiedź GET (SessionInvoiceStatusResponse).
    """
    deadline = time.monotonic() + max_wait_s
    last_err: BaseException | None = None
    poll_n = 0
    last_logged_code: int | None = None
    logged_200_awaiting_knr = False
    while time.monotonic() < deadline:
        try:
            poll_n += 1
            data = fetch_session_invoice_status(base_url, access_token, session_ref, invoice_ref)
            st = data.get("status") or {}
            code = st.get("code")
            if code is None:
                ksef_debug(
                    f"wait_session_invoice: poll #{poll_n} brak status.code, czekam…"
                )
                time.sleep(interval_s)
                continue
            if code in _PENDING_INVOICE_STATUS_CODES:
                if code != last_logged_code:
                    ksef_debug(
                        f"wait_session_invoice: poll #{poll_n} status.code={code} (w toku), czekam…"
                    )
                    last_logged_code = code
                time.sleep(interval_s)
                continue
            # Sukces (200) może przyjść zanim pole ksefNumber zostanie uzupełnione — dalej polujemy.
            if code == 200 and not extract_ksef_number_from_status(data):
                if not logged_200_awaiting_knr:
                    ksef_debug(
                        "wait_session_invoice: status.code=200, brak ksefNumber (jeszcze), czekam…"
                    )
                    logged_200_awaiting_knr = True
                time.sleep(interval_s)
                continue
            ksef_debug(
                f"wait_session_invoice: poll #{poll_n} status końcowy code={code} "
                f"opis={(st.get('description') or '')[:80]!r}"
            )
            return data
        except KsefHttpError as e:
            last_err = e
            if e.status in (404, 425):
                ksef_debug(
                    f"wait_session_invoice: poll #{poll_n} HTTP {e.status} (faktura jeszcze niedostępna?), "
                    f"ponawiam…"
                )
                time.sleep(interval_s)
                continue
            raise
    msg = "Przekroczono czas oczekiwania na status przetworzenia faktury w KSeF."
    if last_err is not None:
        msg += f"\n(Ostatni błąd HTTP: {last_err})"
    ksef_debug(f"wait_session_invoice: TIMEOUT po {poll_n} próbach, sesja={session_ref!r}")
    raise TimeoutError(msg)


def close_online_session(base_url: str, access_token: str, session_ref: str) -> None:
    status, _data = request_json(
        "POST",
        f"{base_url}/sessions/online/{session_ref}/close",
        bearer_token=access_token,
    )
    if status not in (200, 204):
        raise KsefHttpError(f"Zamknięcie sesji: nieoczekiwany kod {status}", status)
    ksef_debug(f"close_online_session: sesja={session_ref!r}, HTTP {status}")


def send_invoice_xml(
    base_url: str,
    access_token: str,
    invoice_xml_bytes: bytes,
    certs: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Wysyła XML, czeka na status końcowy (w tym 450 — błąd semantyki), potem zamyka sesję.
    Zwraca m.in.:
      - referenceNumber — numer referencyjny faktury w KSeF
      - sessionReferenceNumber — numer sesji
      - invoiceStatusPayload — pełna odpowiedź GET statusu (pole status.code: 200 = OK)
    """
    sym_cert = _pick_cert(certs, "SymmetricKeyEncryption")
    ksef_debug(
        f"send_invoice_xml: start, XML bytes={len(invoice_xml_bytes)}, "
        f"base_url={base_url!r}"
    )
    session_ref, aes_key, iv = open_online_session_fa3(base_url, access_token, sym_cert)
    try:
        send_resp = send_encrypted_invoice(
            base_url, access_token, session_ref, invoice_xml_bytes, aes_key, iv
        )
        invoice_ref = send_resp.get("referenceNumber")
        if not invoice_ref:
            raise KsefHttpError("Brak referenceNumber faktury w odpowiedzi wysyłki", None)
        invoice_ref = str(invoice_ref)
        status_payload = wait_for_session_invoice_result(
            base_url, access_token, session_ref, invoice_ref
        )
        ksef_debug(
            f"send_invoice_xml: zakończono przed zamknięciem sesji, "
            f"invoice_ref={invoice_ref!r}"
        )
        return {
            "referenceNumber": invoice_ref,
            "sessionReferenceNumber": session_ref,
            "sendResponse": send_resp,
            "invoiceStatusPayload": status_payload,
        }
    finally:
        try:
            close_online_session(base_url, access_token, session_ref)
        except Exception as ex:
            ksef_debug(f"send_invoice_xml: zamknięcie sesji: wyjątek (ignorowany): {ex!r}")
