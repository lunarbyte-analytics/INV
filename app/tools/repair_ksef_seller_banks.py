"""
Uzupełnia Organization.BankAccountNbr sprzedawców z XML KSeF (Platnosc/RachunekBankowy/NrRB).

Uruchomienie:
  .venv\\Scripts\\python.exe app\\tools\\repair_ksef_seller_banks.py
"""
from __future__ import annotations

import sys
import time

from app.app_env import get_ksef_nip, get_ksef_token, load_settings
from app.db import tx
from app.ksef.auth_flow import obtain_access_token
from app.ksef.client import _effective_base_url
from app.ksef.env_normalize import normalize_ksef_nip, normalize_ksef_token
from app.ksef.fa_import import parse_fa_xml
from app.ksef.purchase_fetch import download_invoice_xml
from app.models.organization import update_organization


def _jobs() -> list[tuple[int, int, str]]:
    """(InvoiceId, CompanyId, KsefNumber) — faktury z numerem KSeF."""
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT i.InvoiceId, i.CompanyId,
                   (
                       SELECT k.ReferenceNumber
                       FROM InvoiceKsefSubmission k
                       WHERE k.InvoiceId = i.InvoiceId
                       ORDER BY k.SentAt DESC, k.InvoiceKsefSubmissionId DESC
                       LIMIT 1
                   ) AS KsefNumber
            FROM Invoice i
            WHERE EXISTS (
                SELECT 1 FROM InvoiceKsefSubmission k2 WHERE k2.InvoiceId = i.InvoiceId
            )
            ORDER BY i.InvoiceId;
            """
        )
        out = []
        for r in cur.fetchall():
            kn = (r["KsefNumber"] or "").strip()
            if kn:
                out.append((int(r["InvoiceId"]), int(r["CompanyId"]), kn))
        return out


def main() -> int:
    load_settings()
    tok = normalize_ksef_token(get_ksef_token())
    nip = normalize_ksef_nip(get_ksef_nip())
    if not tok or not nip:
        print("Brak KSEF_TOKEN / KSEF_NIP", file=sys.stderr)
        return 1

    jobs = _jobs()
    print(f"Faktur z KSeF do sprawdzenia konta: {len(jobs)}")
    if not jobs:
        return 0

    base = _effective_base_url(None)
    access = obtain_access_token(base, ksef_token=tok, nip=nip)

    updated: set[int] = set()
    ok_n = 0
    err_n = 0
    skip_n = 0
    for idx, (iid, company_id, kn) in enumerate(jobs):
        if company_id in updated:
            skip_n += 1
            continue
        if idx > 0:
            time.sleep(4.2)
        try:
            xml = download_invoice_xml(base, access, kn)
            parsed = parse_fa_xml(xml)
        except Exception as e:
            msg = str(e)
            if "429" in msg:
                print(f"InvoiceId={iid}: 429 — czekam 20s…")
                time.sleep(20)
                try:
                    xml = download_invoice_xml(base, access, kn)
                    parsed = parse_fa_xml(xml)
                except Exception as e2:
                    print(f"InvoiceId={iid}: BLAD {e2}")
                    err_n += 1
                    continue
            else:
                print(f"InvoiceId={iid}: BLAD {e}")
                err_n += 1
                continue

        bank = (parsed.seller_bank or "").strip()
        if not bank:
            skip_n += 1
            continue
        update_organization(company_id, BankAccountNbr=bank)
        updated.add(company_id)
        print(f"CompanyId={company_id} (z FV {iid}): {bank}")
        ok_n += 1

    print(f"Zaktualizowano organizacji: {ok_n}, bledy: {err_n}, pominiete: {skip_n}.")
    return 0 if err_n == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
