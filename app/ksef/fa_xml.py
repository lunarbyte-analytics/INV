"""Budowa dokumentu FA (2) (XML) z danych `get_invoice_full`."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.etree import ElementTree as ET

NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"


def Q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _q2(x: float | Decimal) -> str:
    d = Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(d, "f")


def _q8(x: float | Decimal) -> str:
    d = Decimal(str(x)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return format(d, "f")


def _format_ilosci_fa2(x: float | Decimal) -> str:
    """
    Typ TIlosci w FA(2) — wzorzec nie akceptuje np. '10.00000000' (_q8);
    liczby całkowite zapisujemy bez części ułamkowej (por. przykłady MF: <P_8B>1</P_8B>).
    """
    d = Decimal(str(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if d == d.to_integral_value():
        return format(int(d), "d")
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def _nip_digits(s: str | None) -> str:
    if not s:
        return ""
    d = re.sub(r"\D", "", str(s))
    return d


def _date_iso(s: str | None) -> str:
    if not s:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    s = str(s).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _country_code(s: str | None) -> str:
    c = (s or "").strip().upper()
    if not c or c == "POLSKA" or c == "PL":
        return "PL"
    if len(c) == 2:
        return c
    return "PL"


def _addr_lines(street: str | None, no: str | None, zipc: str | None, city: str | None) -> tuple[str, str | None]:
    parts = [(street or "").strip(), (no or "").strip()]
    l1 = " ".join(p for p in parts if p).strip()
    if not l1:
        l1 = "-"
    l2p = " ".join(p for p in ((zipc or "").strip(), (city or "").strip()) if p).strip()
    l2 = l2p if l2p else None
    return l1, l2


def _xml_escape_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def invoice_header_is_kor(header: dict) -> bool:
    """Faktura korygująca FA(2) — RodzajFaktury KOR."""
    return "korekt" in (header.get("TypeName") or "").lower()


def tax_rate_to_stawka(tax: float) -> str:
    t = int(round(float(tax)))
    allowed = (23, 22, 8, 7, 5, 0)
    if t not in allowed:
        raise ValueError(
            f"Nieobsługiwana stawka VAT ({tax}). Dla KSeF (FA2) obsługiwane: {allowed}."
        )
    return str(t)


def compute_fa2_lines(
    header: dict, details: list[dict]
) -> tuple[list[dict], Decimal, dict[str, tuple[Decimal, Decimal]], str, str, bool]:
    """
    Oblicza pozycje i sumy wg reguł FA(2) (te same co w XML).
    Dla faktury korygującej (KOR) kwoty w pozycjach i sumach to różnice (mogą być ujemne).
    Zwraca: lines_calc, suma brutto (P_15), agregacja stawek, NIP sprzedawcy, NIP nabywcy, is_kor.
    """
    if not details:
        raise ValueError("Faktura nie ma pozycji — brak danych do wysyłki KSeF.")

    is_kor = invoice_header_is_kor(header)

    nip_sprzed = _nip_digits(header.get("CoNIP"))
    if len(nip_sprzed) != 10:
        raise ValueError("Sprzedawca musi mieć poprawny NIP (10 cyfr).")

    nip_naby = _nip_digits(header.get("CuNIP"))
    if len(nip_naby) != 10:
        raise ValueError("Nabywca musi mieć poprawny NIP (10 cyfr) do FA(2).")

    gross_sum = Decimal("0")

    agg: dict[str, tuple[Decimal, Decimal]] = {
        "23": (Decimal("0"), Decimal("0")),
        "8": (Decimal("0"), Decimal("0")),
        "5": (Decimal("0"), Decimal("0")),
        "0": (Decimal("0"), Decimal("0")),
    }

    lines_calc: list[dict] = []
    for d in details:
        qty = Decimal(str(d["Quantity"]))
        price = Decimal(str(d["UnitPrice"]))
        tax = float(d["TaxValue"])
        st = tax_rate_to_stawka(tax)
        line_net = (price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_vat = (line_net * Decimal(str(tax)) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        line_gross = line_net + line_vat
        gross_sum += line_gross
        if st in ("23", "22"):
            a, b = agg["23"]
            agg["23"] = (a + line_net, b + line_vat)
        elif st in ("8", "7"):
            a, b = agg["8"]
            agg["8"] = (a + line_net, b + line_vat)
        elif st == "5":
            a, b = agg["5"]
            agg["5"] = (a + line_net, b + line_vat)
        elif st == "0":
            a, b = agg["0"]
            agg["0"] = (a + line_net, b + line_vat)
        lines_calc.append(
            {
                "name": d.get("ServiceName") or "Usługa",
                "unit": d.get("UnitCode") or "szt.",
                "qty": qty,
                "price_net": price,
                "line_net": line_net,
                "stawka": st,
            }
        )

    return lines_calc, gross_sum, agg, nip_sprzed, nip_naby, is_kor


def _emit_agg_p13(
    fa: ET.Element, agg: dict[str, tuple[Decimal, Decimal]], *, is_kor: bool
) -> None:
    """P_13/P_14 dla stawek — dla KOR emituj także wartości ujemne (różnice)."""
    n23, v23 = agg["23"]

    def _pair(tag_net: str, tag_vat: str, n: Decimal, v: Decimal) -> None:
        if is_kor:
            if n == 0 and v == 0:
                return
        else:
            if n <= 0 and v <= 0:
                return
        ET.SubElement(fa, Q(tag_net)).text = _q2(n)
        ET.SubElement(fa, Q(tag_vat)).text = _q2(v)

    _pair("P_13_1", "P_14_1", n23, v23)
    n8, v8 = agg["8"]
    _pair("P_13_2", "P_14_2", n8, v8)
    n5, v5 = agg["5"]
    _pair("P_13_3", "P_14_3", n5, v5)
    n0, _v0 = agg["0"]
    if is_kor:
        if n0 != 0:
            ET.SubElement(fa, Q("P_13_6_1")).text = _q2(n0)
    else:
        if n0 > 0:
            ET.SubElement(fa, Q("P_13_6_1")).text = _q2(n0)


def build_fa2_invoice_xml(header: dict, details: list[dict]) -> str:
    """Zwraca XML jako str (UTF-8, z deklaracją)."""
    lines_calc, gross_sum, agg, nip_sprzed, nip_naby, is_kor = compute_fa2_lines(header, details)

    ET.register_namespace("", NS)

    root = ET.Element(Q("Faktura"))

    nag = ET.SubElement(root, Q("Naglowek"))
    kf = ET.SubElement(
        nag,
        Q("KodFormularza"),
        {"kodSystemowy": "FA (2)", "wersjaSchemy": "1-0E"},
    )
    kf.text = "FA"
    wf = ET.SubElement(nag, Q("WariantFormularza"))
    wf.text = "2"
    dw = ET.SubElement(nag, Q("DataWytworzeniaFa"))
    dw.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    si = ET.SubElement(nag, Q("SystemInfo"))
    si.text = "INV"

    p1 = ET.SubElement(root, Q("Podmiot1"))
    di1 = ET.SubElement(p1, Q("DaneIdentyfikacyjne"))
    ET.SubElement(di1, Q("NIP")).text = nip_sprzed
    naz1 = header.get("CompanyName") or f"Podmiot {header.get('CompanyId')}"
    ET.SubElement(di1, Q("Nazwa")).text = _xml_escape_text(str(naz1)[:512])
    adr1 = ET.SubElement(p1, Q("Adres"))
    co_l1, co_l2 = _addr_lines(
        header.get("CoStreet"),
        header.get("CoStreetNo"),
        header.get("CoZip"),
        header.get("CoCity"),
    )
    ET.SubElement(adr1, Q("KodKraju")).text = _country_code(header.get("CoCountry"))
    ET.SubElement(adr1, Q("AdresL1")).text = _xml_escape_text(co_l1[:512])
    if co_l2:
        ET.SubElement(adr1, Q("AdresL2")).text = _xml_escape_text(co_l2[:512])

    p2 = ET.SubElement(root, Q("Podmiot2"))
    di2 = ET.SubElement(p2, Q("DaneIdentyfikacyjne"))
    ET.SubElement(di2, Q("NIP")).text = nip_naby
    naz2 = header.get("CustomerName") or f"Nabywca {header.get('CustomerId')}"
    ET.SubElement(di2, Q("Nazwa")).text = _xml_escape_text(str(naz2)[:512])
    adr2 = ET.SubElement(p2, Q("Adres"))
    cu_l1, cu_l2 = _addr_lines(
        header.get("CuStreet"),
        header.get("CuStreetNo"),
        header.get("CuZip"),
        header.get("CuCity"),
    )
    ET.SubElement(adr2, Q("KodKraju")).text = _country_code(header.get("CuCountry"))
    ET.SubElement(adr2, Q("AdresL1")).text = _xml_escape_text(cu_l1[:512])
    if cu_l2:
        ET.SubElement(adr2, Q("AdresL2")).text = _xml_escape_text(cu_l2[:512])

    fa = ET.SubElement(root, Q("Fa"))
    ET.SubElement(fa, Q("KodWaluty")).text = "PLN"
    d_issue = _date_iso(header.get("CreateDate"))
    ET.SubElement(fa, Q("P_1")).text = d_issue
    ET.SubElement(fa, Q("P_2")).text = _xml_escape_text(
        (header.get("Name") or str(header.get("InvoiceId")))[:256]
    )
    d_sales = _date_iso(header.get("SalesDate"))
    if d_sales != d_issue:
        ET.SubElement(fa, Q("P_6")).text = d_sales

    _emit_agg_p13(fa, agg, is_kor=is_kor)

    ET.SubElement(fa, Q("P_15")).text = _q2(gross_sum)

    ad = ET.SubElement(fa, Q("Adnotacje"))
    ET.SubElement(ad, Q("P_16")).text = "2"
    ET.SubElement(ad, Q("P_17")).text = "2"
    ET.SubElement(ad, Q("P_18")).text = "2"
    ET.SubElement(ad, Q("P_18A")).text = "2"
    zw = ET.SubElement(ad, Q("Zwolnienie"))
    ET.SubElement(zw, Q("P_19N")).text = "1"
    nst = ET.SubElement(ad, Q("NoweSrodkiTransportu"))
    ET.SubElement(nst, Q("P_22N")).text = "1"
    ET.SubElement(ad, Q("P_23")).text = "2"
    pm = ET.SubElement(ad, Q("PMarzy"))
    ET.SubElement(pm, Q("P_PMarzyN")).text = "1"

    ET.SubElement(fa, Q("RodzajFaktury")).text = "KOR" if is_kor else "VAT"
    if is_kor:
        rsn = (header.get("CorrectionReason") or "").strip()
        if rsn:
            ET.SubElement(fa, Q("PrzyczynaKorekty")).text = _xml_escape_text(rsn[:512])
        n_orig = (header.get("CorrectedOriginalName") or "").strip()
        d_orig = _date_iso(header.get("CorrectedOriginalCreateDate"))
        if not n_orig:
            raise ValueError(
                "Faktura korygująca: w nagłówku brak danych faktury pierwotnej — ustaw „ID faktury korygowanej” i zapisz."
            )
        dk = ET.SubElement(fa, Q("DaneFaKorygowanej"))
        ET.SubElement(dk, Q("DataWystFaKorygowanej")).text = d_orig
        ET.SubElement(dk, Q("NrFaKorygowanej")).text = _xml_escape_text(n_orig[:256])
        kref = (header.get("CorrectedOriginalKsefRef") or "").strip()
        if kref:
            ET.SubElement(dk, Q("NrKSeF")).text = "1"
            ET.SubElement(dk, Q("NrKSeFFaKorygowanej")).text = _xml_escape_text(kref[:512])
        else:
            ET.SubElement(dk, Q("NrKSeFN")).text = "1"

    for i, ln in enumerate(lines_calc, start=1):
        fw = ET.SubElement(fa, Q("FaWiersz"))
        ET.SubElement(fw, Q("NrWierszaFa")).text = str(i)
        ET.SubElement(fw, Q("P_7")).text = _xml_escape_text(str(ln["name"])[:256])
        ET.SubElement(fw, Q("P_8A")).text = _xml_escape_text(str(ln["unit"])[:256])
        ET.SubElement(fw, Q("P_8B")).text = _format_ilosci_fa2(ln["qty"])
        ET.SubElement(fw, Q("P_9A")).text = _q8(ln["price_net"])
        ET.SubElement(fw, Q("P_11")).text = _q2(ln["line_net"])
        ET.SubElement(fw, Q("P_12")).text = ln["stawka"]

    buf = BytesIO()
    tree = ET.ElementTree(root)
    # Nie używać default_namespace= przy write(): wymaga wtedy, by *każdy* węzeł
    # miał tag w notacji {URI}nazwa; część implementacji ET generuje wyjątek.
    # register_namespace('', NS) wystarczy do domyślnego xmlns w serializacji.
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")
