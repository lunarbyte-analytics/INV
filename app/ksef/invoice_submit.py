"""Wysyłka pojedynczej faktury z bazy do KSeF (FA(3), sesja interaktywna)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..app_env import get_ksef_nip, get_ksef_token
from ..models.invoice import get_invoice_full, record_ksef_submission
from .auth_flow import fetch_public_certs, obtain_access_token
from .client import _effective_base_url
from .env_normalize import ensure_ksef_nip_matches_token, normalize_ksef_nip, normalize_ksef_token
from .debug_log import ksef_debug
from .fa_validate import validate_invoice_for_ksef, validate_xml_size_fits_ksef
from .fa_xml import build_fa3_invoice_xml
from .http_json import KsefHttpError
from .online_send import extract_ksef_number_from_status, is_valid_ksef_number_format, send_invoice_xml


@dataclass
class KsefSubmitResult:
    ok: bool
    message: str
    invoice_reference: str | None = None
    detail: dict[str, Any] | None = None


def send_invoice_to_ksef(invoice_id: int) -> KsefSubmitResult:
    ksef_debug(f"send_invoice_to_ksef: start, InvoiceId={invoice_id}")
    token = normalize_ksef_token(get_ksef_token())
    nip = normalize_ksef_nip(get_ksef_nip())
    if not token or not nip:
        raise ValueError(
            "Brak konfiguracji KSeF. Ustaw w menu Plik → Ustawienia integracji… "
            "lub zmienne środowiskowe:\n"
            "  KSEF_TOKEN — token KSeF do uwierzytelnienia\n"
            "  KSEF_NIP — NIP kontekstu (podmiotu), zgodny z tokenem\n"
            "Opcjonalnie: pole URL w ustawieniach lub zmienne środowiskowe (gdy pole w pliku puste); "
            "gdy wszędzie pusto: api-test / api.ksef wg Plik → Środowisko."
        )

    ensure_ksef_nip_matches_token(token, nip)

    base_url = _effective_base_url(None)
    ksef_debug(f"send_invoice_to_ksef: base_url={base_url!r}, NIP(len)={len(nip)}")
    header, details = get_invoice_full(invoice_id)
    if header is None:
        raise ValueError(f"Nie znaleziono faktury o ID={invoice_id}.")

    validate_invoice_for_ksef(header, details, env_nip=nip)
    xml_str = build_fa3_invoice_xml(header, details)
    xml_bytes = xml_str.encode("utf-8")
    validate_xml_size_fits_ksef(xml_bytes)
    ksef_debug(
        f"send_invoice_to_ksef: XML utworzony, bajtów={len(xml_bytes)}, pozycji={len(details)}"
    )

    access = obtain_access_token(base_url, ksef_token=token, nip=nip)
    ksef_debug("send_invoice_to_ksef: access token uzyskany (długość ukryta)")
    certs = fetch_public_certs(base_url)
    ksef_debug(f"send_invoice_to_ksef: certyfikaty MF: {len(certs)} wpisów")
    resp = send_invoice_xml(base_url, access, xml_bytes, certs)
    ksef_debug(f"send_invoice_to_ksef: send_invoice_xml zakończone, klucze odpowiedzi: {list(resp.keys())}")
    ref = resp.get("referenceNumber")
    status_payload = resp.get("invoiceStatusPayload") or {}
    st = status_payload.get("status") or {}
    code = st.get("code")
    if code is None:
        ksef_debug("send_invoice_to_ksef: BRAK status.code w invoiceStatusPayload")
        return KsefSubmitResult(
            ok=False,
            message="Nie udało się odczytać statusu przetworzenia faktury w KSeF (brak pola status.code).",
            invoice_reference=str(ref) if ref else None,
            detail=resp,
        )
    desc = (st.get("description") or "").strip()
    details_list = st.get("details")
    detail_txt = ""
    if isinstance(details_list, list) and details_list:
        detail_txt = "\n".join(str(x) for x in details_list)

    ksef_debug(
        f"send_invoice_to_ksef: status.code={code} ref={ref!r} desc={desc[:120]!r}"
    )

    if code == 200:
        ksef_nr = extract_ksef_number_from_status(status_payload)
        lines = [
            "Faktura została przyjęta i przetworzona przez KSeF.",
            f"Numer referencyjny dokumentu: {ref or '—'}",
        ]
        if ksef_nr:
            lines.append(f"Numer KSeF: {ksef_nr}")
        msg = "\n".join(lines)
        if ksef_nr:
            try:
                # NrKSeFFaKorygowanej wymaga TNumerKSeF — nie zapisujemy referenceNumber sesji (…-EE-…).
                num_to_save = str(ksef_nr).strip()
                if num_to_save and is_valid_ksef_number_format(num_to_save):
                    record_ksef_submission(invoice_id, num_to_save)
                else:
                    msg += (
                        "\n\nUwaga: pole ksefNumber z API nie pasuje do oczekiwanego formatu numeru KSeF — "
                        "nie zapisano go w bazie (uniknięcie błędnego NrKSeFFaKorygowanej przy korekcie)."
                    )
            except Exception as db_exc:
                msg += (
                    "\n\nUwaga: nie udało się zapisać numeru w bazie lokalnej:\n"
                    f"{db_exc}"
                )
        else:
            msg += (
                "\n\nUwaga: brak pola ksefNumber w odpowiedzi statusu — numer KSeF nie został zapisany w bazie. "
                "Sprawdź w KSeF numer dokumentu i ewentualnie dopisz go ręcznie przy korekcie."
            )
        ksef_debug(f"send_invoice_to_ksef: SUKCES (200), numer KSeF={ksef_nr!r}")
        return KsefSubmitResult(
            ok=True,
            message=msg,
            invoice_reference=str(ref) if ref else None,
            detail=resp,
        )

    # Błędy m.in. 430 (plik), 450 (semantyka), 440 (duplikat) — patrz OpenAPI InvoiceStatusInfo
    ksef_debug(f"send_invoice_to_ksef: odrzucone przez KSeF, szczegóły: {detail_txt[:500]!r}")
    parts = [
        f"KSeF odrzucił dokument po weryfikacji (kod statusu: {code}).",
    ]
    if desc:
        parts.append(desc)
    if detail_txt:
        parts.append(detail_txt)
    msg = "\n".join(parts)
    return KsefSubmitResult(
        ok=False,
        message=msg,
        invoice_reference=str(ref) if ref else None,
        detail=resp,
    )


def format_ksef_error(exc: BaseException) -> str:
    if isinstance(exc, KsefHttpError):
        return str(exc)
    if isinstance(exc, TimeoutError):
        return str(exc)
    return str(exc)
