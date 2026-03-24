"""Import faktury FA (XML z KSeF / plik) do lokalnej bazy — scenariusz zakupu (nabywca = „Twoja firma”)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ..models.address import create_address
from ..models.invoice import (
    add_detail,
    create_invoice,
    find_invoice_by_party_and_name,
    record_ksef_submission,
)
from ..models.organization import (
    create_organization,
    find_organization_id_by_nip_digits,
    get_organization_by_id,
)
from ..models.service import create_service
from ..models.tax import find_tax_id_by_value, get_or_create_tax_by_rate
from ..models.unit import create_unit, find_unit_id_by_code


def _local(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for c in parent:
        if _local(c.tag) == name:
            return c
    return None


def _nip_norm(s: str) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _parse_adres_l2(l2: str) -> tuple[str, str]:
    l2 = (l2 or "").strip()
    m = re.match(r"^(\d{2}-\d{3})\s+(.+)$", l2)
    if m:
        return m.group(1), m.group(2)
    return "", l2


def _date_only(s: str) -> str:
    t = (s or "").strip()
    if len(t) >= 10 and t[4] == "-" and t[7] == "-":
        return t[:10]
    return t[:10] if t else ""


@dataclass
class FaParty:
    nip: str
    nazwa: str
    country: str
    adres_l1: str
    zip_code: str
    city: str


@dataclass
class FaLine:
    name: str
    unit: str
    qty: Decimal
    price_net: Decimal
    stawka: str


@dataclass
class FaParsed:
    rodzaj: str
    currency: str
    p1: str
    p2: str
    p6: str | None
    seller: FaParty
    buyer: FaParty
    lines: list[FaLine]


def _parse_party(pod: ET.Element | None) -> FaParty:
    if pod is None:
        raise ValueError("Brak bloku podmiotu w XML.")
    di = _child(pod, "DaneIdentyfikacyjne")
    nip = _nip_norm(_text(_child(di, "NIP")))
    nazwa = _text(_child(di, "Nazwa")) or "—"
    adr = _child(pod, "Adres")
    cc = _text(_child(adr, "KodKraju")) or "PL"
    a1 = _text(_child(adr, "AdresL1")) or "-"
    a2 = _text(_child(adr, "AdresL2"))
    z, c = _parse_adres_l2(a2)
    if not c and a2:
        c = a2
    return FaParty(
        nip=nip,
        nazwa=nazwa[:512],
        country=cc,
        adres_l1=a1[:512],
        zip_code=z,
        city=(c or "")[:256],
    )


def _parse_fa_block(fa_el: ET.Element) -> tuple[str, str, str, str | None, str]:
    """KodWaluty, P_1, P_2, opcjonalnie P_6, RodzajFaktury."""
    cur = _text(_child(fa_el, "KodWaluty")) or "PLN"
    p1 = _date_only(_text(_child(fa_el, "P_1")))
    p2 = _text(_child(fa_el, "P_2")) or ""
    p6_el = _child(fa_el, "P_6")
    p6 = _date_only(_text(p6_el)) if p6_el is not None and _text(p6_el) else None
    rodzaj = _text(_child(fa_el, "RodzajFaktury")) or "VAT"
    return cur, p1, p2, p6, rodzaj


def parse_fa_xml(xml_bytes: bytes) -> FaParsed:
    try:
        root = ET.parse(BytesIO(xml_bytes)).getroot()
    except ET.ParseError as e:
        raise ValueError(f"Niepoprawny XML: {e}") from e

    faktura = root if _local(root.tag) == "Faktura" else None
    if faktura is None:
        for el in root.iter():
            if _local(el.tag) == "Faktura":
                faktura = el
                break
    if faktura is None:
        raise ValueError("Nie znaleziono elementu Faktura.")

    p1 = _child(faktura, "Podmiot1")
    p2 = _child(faktura, "Podmiot2")
    seller = _parse_party(p1)
    buyer = _parse_party(p2)

    fa_el = _child(faktura, "Fa")
    if fa_el is None:
        raise ValueError("Brak sekcji Fa w fakturze.")

    currency, d_issue, inv_no, d_sales, rodzaj = _parse_fa_block(fa_el)
    lines: list[FaLine] = []
    for ch in fa_el:
        if _local(ch.tag) != "FaWiersz":
            continue
        p7 = _text(_child(ch, "P_7")) or "Pozycja"
        p8a = _text(_child(ch, "P_8A")) or "szt."
        p8b = _text(_child(ch, "P_8B")) or "1"
        p9a = _text(_child(ch, "P_9A")) or "0"
        p12 = _text(_child(ch, "P_12")) or "23"
        try:
            qty = Decimal(str(p8b.replace(",", ".")))
        except Exception:
            qty = Decimal("1")
        try:
            price_net = Decimal(str(p9a.replace(",", ".")))
        except Exception:
            price_net = Decimal("0")
        lines.append(
            FaLine(
                name=p7[:512],
                unit=p8a[:64],
                qty=qty,
                price_net=price_net,
                stawka=p12,
            )
        )

    if not lines:
        raise ValueError("Brak pozycji FaWiersz — import odrzucony.")

    return FaParsed(
        rodzaj=rodzaj,
        currency=currency,
        p1=d_issue,
        p2=inv_no[:256],
        p6=d_sales,
        seller=seller,
        buyer=buyer,
        lines=lines,
    )


def _resolve_tax_id(stawka: str) -> int:
    """
    Mapuje pole P_12 z FA na TaxId. Wartość liczbowa jest brana z XML tak jak jest —
    brak sztywnych „aliasów” (np. 7↔8); jeśli nie ma wiersza w Tax, dopisywany jest przez get_or_create_tax_by_rate.
    """
    raw = (stawka or "").strip()
    s = raw.lower().replace("%", "").strip()
    if s in ("np", "oo"):
        return -1
    if s in ("zw", "0") or s == "0.0":
        tid = find_tax_id_by_value(0.0)
        return tid if tid is not None else get_or_create_tax_by_rate(0.0)
    if re.match(r"^\d+$", s) or re.match(r"^\d+[.,]\d+$", s):
        v = float(s.replace(",", "."))
        tid = find_tax_id_by_value(v)
        if tid is not None:
            return tid
        return get_or_create_tax_by_rate(v)
    raise ValueError(f"Nieobsługiwana stawka VAT w pozycji: {stawka!r}")


def _ensure_unit(code: str) -> int:
    c = (code or "").strip() or "szt."
    uid = find_unit_id_by_code(c)
    if uid is not None:
        return uid
    return create_unit(c, c[:64], 0)


def _ensure_organization(party: FaParty) -> int:
    oid = find_organization_id_by_nip_digits(party.nip)
    if oid is not None:
        return oid
    if len(_nip_norm(party.nip)) != 10:
        raise ValueError(
            "Nabywca lub sprzedawca bez polskiego NIP (10 cyfr) — uzupełnij dane ręcznie w słowniku organizacji."
        )
    aid = create_address(
        "Billing",
        party.adres_l1,
        "",
        party.zip_code,
        party.city,
        "Polska" if (party.country or "").upper() in ("PL", "") else party.country,
    )
    return create_organization(
        aid,
        None,
        party.nazwa,
        "",
        "",
        party.nip,
        "",
        "",
        "",
    )


def import_fa_purchase_xml_to_db(
    xml_bytes: bytes,
    *,
    buyer_org_id: int | None = None,
    skip_duplicate: bool = True,
    ksef_number: str | None = None,
) -> tuple[int, list[str]]:
    """
    Zapisuje fakturę zakupową: CompanyId = sprzedawca (Podmiot1), CustomerId = nabywca (Podmiot2).

    buyer_org_id — jeśli podane, NIP nabywcy z XML musi się zgadzać z tą organizacją (Twoja firma).
    """
    notes: list[str] = []
    data = parse_fa_xml(xml_bytes)

    if (data.rodzaj or "").upper() not in ("VAT",):
        raise ValueError(
            f"Obsługiwany jest tylko RodzajFaktury=VAT (tu: {data.rodzaj!r}). Korekty i inne typy — nie."
        )
    if (data.currency or "PLN").upper() != "PLN":
        raise ValueError(f"Tylko waluta PLN (w pliku: {data.currency!r}).")

    bn = _nip_norm(data.buyer.nip)
    sn = _nip_norm(data.seller.nip)
    if len(bn) != 10 or len(sn) != 10:
        raise ValueError("Wymagany polski NIP sprzedawcy i nabywcy (10 cyfr) w XML.")

    if buyer_org_id is not None:
        row = get_organization_by_id(buyer_org_id)
        if row is None:
            raise ValueError(f"Nie znaleziono organizacji o ID={buyer_org_id}.")
        if _nip_norm(row["OrgNbr1"]) != bn:
            raise ValueError(
                "NIP nabywcy w XML nie zgadza się z wybraną organizacją kontekstu (Twoja firma)."
            )
        customer_id = buyer_org_id
    else:
        buyer_existed = find_organization_id_by_nip_digits(data.buyer.nip) is not None
        customer_id = _ensure_organization(data.buyer)
        if not buyer_existed:
            notes.append("Dodano nową organizację nabywcy z faktury.")

    seller_existed = find_organization_id_by_nip_digits(data.seller.nip) is not None
    company_id = _ensure_organization(data.seller)
    if not seller_existed:
        notes.append("Dodano nową organizację sprzedawcy z faktury.")

    inv_name = (data.p2 or "").strip() or f"Import {data.p1}"
    dup = find_invoice_by_party_and_name(company_id, customer_id, inv_name)
    if dup is not None:
        if skip_duplicate:
            return dup, [f"Pominięto duplikat — już jest faktura InvoiceId={dup}."]
        raise ValueError(f"Duplikat: InvoiceId={dup}")

    d_create = data.p1 or ""
    d_sales = data.p6 or data.p1
    if not d_create:
        raise ValueError("Brak daty P_1.")

    invoice_id = create_invoice(
        company_id=company_id,
        customer_id=customer_id,
        payment_method_id=1,
        status_id=2,
        type_id=1,
        is_additional_address=0,
        name=inv_name,
        create_date=d_create,
        sales_date=d_sales,
        payment_date=d_sales,
    )

    for i, ln in enumerate(data.lines, start=1):
        tax_id = _resolve_tax_id(ln.stawka)
        unit_id = _ensure_unit(ln.unit)
        price = float(ln.price_net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        qty_f = float(ln.qty)
        svc_name = (
            f"{ln.name[:120]} (import #{i})" if len(data.lines) > 1 else ln.name[:240]
        )
        sid = create_service(unit_id, tax_id, svc_name, price, version="ksef-import")
        add_detail(invoice_id, sid, qty_f)

    ref = (ksef_number or "").strip()
    if ref:
        try:
            record_ksef_submission(invoice_id, ref)
        except Exception as e:
            notes.append(f"Uwaga: nie zapisano numeru KSeF w tabeli wysyłek: {e}")

    return invoice_id, notes


def import_fa_purchase_xml_file(path: str | Path, **kwargs: Any) -> tuple[int, list[str]]:
    p = Path(path)
    raw = p.read_bytes()
    kn = kwargs.pop("ksef_number", None)
    if kn is None:
        stem = p.stem
        if len(stem) >= 20 and re.match(r"^[\w\-]+$", stem):
            kn = stem
    return import_fa_purchase_xml_to_db(raw, ksef_number=kn, **kwargs)
