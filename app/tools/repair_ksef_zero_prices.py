"""
Naprawia UnitPrice=0 na usługach z importu KSeF: ponownie pobiera XML i ustawia cenę
z P_9A / P_11 / P_9B / P_11A (jak w fa_import).

Uruchomienie z katalogu projektu:
  .venv\\Scripts\\python.exe -m app.tools.repair_ksef_zero_prices
"""
from __future__ import annotations

import sys
import time
from decimal import Decimal, ROUND_HALF_UP

from app.app_env import get_ksef_nip, get_ksef_token, load_settings
from app.db import tx
from app.ksef.auth_flow import obtain_access_token
from app.ksef.client import _effective_base_url
from app.ksef.env_normalize import normalize_ksef_nip, normalize_ksef_token
from app.ksef.fa_import import parse_fa_xml
from app.ksef.purchase_fetch import download_invoice_xml
from app.models.record_source import RECORD_SOURCE_KSEF_IMPORT
from app.models.service import update_service


def _jobs() -> list[tuple[int, str, list[tuple[int, int, float]]]]:
    """
    Zwraca listę (InvoiceId, ksefNumber, [(ServiceId, Quantity, UnitPrice), ...]).
    Tylko faktury z zapisem KSeF i co najmniej jedną usługą importu z ceną 0.
    """
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT i.InvoiceId,
                   (
                       SELECT k.ReferenceNumber
                       FROM InvoiceKsefSubmission k
                       WHERE k.InvoiceId = i.InvoiceId
                       ORDER BY k.SentAt DESC, k.InvoiceKsefSubmissionId DESC
                       LIMIT 1
                   ) AS KsefNumber
            FROM Invoice i
            JOIN InvoiceDetail d ON d.InvoiceId = i.InvoiceId
            JOIN Service s ON s.ServiceId = d.ServiceId
            WHERE s.RecordSource = ?
              AND CAST(s.UnitPrice AS REAL) = 0
              AND EXISTS (
                  SELECT 1 FROM InvoiceKsefSubmission k2 WHERE k2.InvoiceId = i.InvoiceId
              )
            ORDER BY i.InvoiceId;
            """,
            (RECORD_SOURCE_KSEF_IMPORT,),
        )
        inv_rows = cur.fetchall()
        out: list[tuple[int, str, list[tuple[int, int, float]]]] = []
        for row in inv_rows:
            iid = int(row["InvoiceId"])
            kn = (row["KsefNumber"] or "").strip()
            if not kn:
                continue
            cur.execute(
                """
                SELECT d.ServiceId, d.Quantity, s.UnitPrice
                FROM InvoiceDetail d
                JOIN Service s ON s.ServiceId = d.ServiceId
                WHERE d.InvoiceId = ?
                ORDER BY d.InvoiceDetailId;
                """,
                (iid,),
            )
            details = [
                (int(r["ServiceId"]), float(r["Quantity"] or 0), float(r["UnitPrice"] or 0))
                for r in cur.fetchall()
            ]
            out.append((iid, kn, details))
        return out


def main() -> int:
    load_settings()
    tok = normalize_ksef_token(get_ksef_token())
    nip = normalize_ksef_nip(get_ksef_nip())
    if not tok or not nip:
        print("Brak KSEF_TOKEN / KSEF_NIP — nie można pobrać XML.", file=sys.stderr)
        return 1

    jobs = _jobs()
    print(f"Do naprawy: {len(jobs)} faktur z cena 0 (import KSeF).")
    if not jobs:
        return 0

    base = _effective_base_url(None)
    access = obtain_access_token(base, ksef_token=tok, nip=nip)

    ok_n = 0
    err_n = 0
    skip_n = 0
    for idx, (iid, kn, details) in enumerate(jobs):
        if idx > 0:
            # Limit GET /invoices/ksef: ok. 16/min — odczekaj między fakturami.
            time.sleep(4.2)
        try:
            xml = download_invoice_xml(base, access, kn)
            parsed = parse_fa_xml(xml)
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                print(f"InvoiceId={iid}: rate limit 429 — czekam 20s i ponawiam…")
                time.sleep(20)
                try:
                    xml = download_invoice_xml(base, access, kn)
                    parsed = parse_fa_xml(xml)
                except Exception as e2:
                    print(f"InvoiceId={iid} kn={kn}: BLAD pobrania/parsowania: {e2}")
                    err_n += 1
                    continue
            else:
                print(f"InvoiceId={iid} kn={kn}: BLAD pobrania/parsowania: {e}")
                err_n += 1
                continue

        if len(parsed.lines) != len(details):
            print(
                f"InvoiceId={iid}: liczba pozycji XML={len(parsed.lines)} "
                f"!= baza={len(details)} - pomijam."
            )
            skip_n += 1
            continue

        for ln, (sid, qty, old_price) in zip(parsed.lines, details):
            if old_price != 0:
                continue
            new_price = float(
                ln.price_net.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            )
            if new_price == 0:
                print(f"InvoiceId={iid} ServiceId={sid}: nadal 0 po parsowaniu - pomijam.")
                skip_n += 1
                continue
            update_service(sid, unit_price=new_price)
            safe_name = ln.name[:40].encode("ascii", "replace").decode("ascii")
            print(
                f"InvoiceId={iid} ServiceId={sid}: {old_price} -> {new_price} "
                f"(qty={qty}, XML qty={ln.qty}, name={safe_name!r})"
            )
            ok_n += 1

    print(f"Zaktualizowano cen: {ok_n}, bledy: {err_n}, pominiete: {skip_n}.")
    return 0 if err_n == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
