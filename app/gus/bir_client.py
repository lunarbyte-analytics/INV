"""
Klient API GUS BIR 1.1 (REGON) — SOAP 1.2.
Zaloguj → DaneSzukajPodmioty (NIP) → Wyloguj.
Dokumentacja: https://api.stat.gov.pl/Home/RegonApi
"""
from __future__ import annotations

import html
import re
import ssl
import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from ..app_env import get_gus_bir_api_base, get_gus_bir_api_key
from ..ceidg.hd_client import normalize_nip_digits

from .debug_log import gus_debug

BIR_NS = "http://CIS/BIR/PUBL/2014/07"
DATA_NS = "http://CIS/BIR/PUBL/2014/07/DataContract"
ACTION_LOGIN = f"{BIR_NS}/IUslugaBIRzewnPubl/Zaloguj"
ACTION_LOGOUT = f"{BIR_NS}/IUslugaBIRzewnPubl/Wyloguj"
ACTION_SEARCH = f"{BIR_NS}/IUslugaBIRzewnPubl/DaneSzukajPodmioty"


class GusBirError(Exception):
    """Błąd wywołania API GUS BIR."""


class GusNoDataError(GusBirError):
    """Brak podmiotu dla podanego NIP."""


def get_gus_bir_key() -> str | None:
    k = get_gus_bir_api_key().strip()
    return k or None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_first_text(root: ET.Element, name: str) -> str | None:
    for el in root.iter():
        if _local(el.tag) == name and el.text is not None:
            t = el.text.strip()
            if t:
                return t
    return None


def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def _extract_soap_xml(raw: str) -> str:
    """WCF czasem zwraca MTOM/XOP (multipart) — wyciągnij envelope SOAP."""
    text = (raw or "").lstrip("\ufeff")
    m = re.search(r"<[^:>\s]*:?Envelope\b", text)
    if not m:
        return text
    i = m.start()
    end = -1
    for em in ("</s:Envelope>", "</soap:Envelope>", "</Envelope>"):
        j = text.rfind(em)
        if j >= 0:
            end = max(end, j + len(em))
    if end > i:
        return text[i:end]
    # fallback: namespace-qualified closing tag
    m2 = re.search(r"</[^:>\s]*:?Envelope\s*>", text[i:])
    if m2:
        return text[i : i + m2.end()]
    return text


def _soap_post(url: str, body: str, *, sid: str | None = None, timeout: float = 60.0) -> str:
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "Accept": "application/soap+xml, application/xml, text/xml, */*",
    }
    if sid:
        headers["sid"] = sid
    req = Request(url, method="POST", data=body.encode("utf-8"), headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return _extract_soap_xml(raw)
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise GusBirError(f"HTTP {e.code} GUS BIR: {raw[:800]}") from e
    except URLError as e:
        raise GusBirError(f"Brak połączenia z GUS BIR ({url}): {e.reason!s}") from e


def _envelope(action: str, to_url: str, body_inner: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        f'xmlns:ns="{BIR_NS}" xmlns:dat="{DATA_NS}" '
        'xmlns:wsa="http://www.w3.org/2005/08/addressing">'
        "<soap:Header>"
        f"<wsa:To>{escape(to_url)}</wsa:To>"
        f"<wsa:Action>{escape(action)}</wsa:Action>"
        "</soap:Header>"
        f"<soap:Body>{body_inner}</soap:Body>"
        "</soap:Envelope>"
    )


def _login(url: str, api_key: str) -> str:
    body = _envelope(
        ACTION_LOGIN,
        url,
        f"<ns:Zaloguj><ns:pKluczUzytkownika>{escape(api_key)}</ns:pKluczUzytkownika></ns:Zaloguj>",
    )
    raw = _soap_post(url, body)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise GusBirError(f"Niepoprawna odpowiedź SOAP (Zaloguj): {raw[:400]}") from e
    sid = _find_first_text(root, "ZalogujResult")
    if not sid:
        raise GusBirError(
            "Logowanie do GUS BIR nie powiodło się (pusty sid). "
            "Sprawdź klucz API (GUS_BIR_API_KEY) — klucz testowy działa tylko na adresie testowym."
        )
    gus_debug(f"Zaloguj OK (sid length={len(sid)})")
    return sid


def _logout(url: str, sid: str) -> None:
    body = _envelope(
        ACTION_LOGOUT,
        url,
        f"<ns:Wyloguj><ns:pIdentyfikatorSesji>{escape(sid)}</ns:pIdentyfikatorSesji></ns:Wyloguj>",
    )
    try:
        _soap_post(url, body, sid=sid)
        gus_debug("Wyloguj OK")
    except GusBirError as e:
        gus_debug(f"Wyloguj: {e}")


def _parse_search_result_xml(result_text: str) -> list[ET.Element]:
    """DaneSzukajPodmiotyResult to często XML (czasem HTML-escaped) z <root><dane>…."""
    text = (result_text or "").strip()
    if not text:
        return []
    # Wynik bywa podwójnie escaped (&amp;lt; …)
    for _ in range(2):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # czasem otoczony białymi znakami / BOM
        m = re.search(r"<root[\s>].*</root>", text, flags=re.DOTALL | re.IGNORECASE)
        if not m:
            raise GusBirError(f"Nie udało się sparsować wyniku wyszukiwania GUS: {text[:300]}")
        root = ET.fromstring(m.group(0))

    dane_list: list[ET.Element] = []
    if _local(root.tag) == "dane":
        dane_list.append(root)
    else:
        for el in root.iter():
            if _local(el.tag) == "dane":
                dane_list.append(el)
    return dane_list


def _dane_to_dict(dane: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for el in dane:
        name = _local(el.tag)
        val = (el.text or "").strip()
        out[name] = val
    return out


def _search_by_nip(url: str, sid: str, nip: str) -> dict[str, str]:
    body = _envelope(
        ACTION_SEARCH,
        url,
        "<ns:DaneSzukajPodmioty>"
        "<ns:pParametryWyszukiwania>"
        f"<dat:Nip>{escape(nip)}</dat:Nip>"
        "</ns:pParametryWyszukiwania>"
        "</ns:DaneSzukajPodmioty>",
    )
    raw = _soap_post(url, body, sid=sid)
    try:
        soap_root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise GusBirError(f"Niepoprawna odpowiedź SOAP (DaneSzukajPodmioty): {raw[:400]}") from e

    result_text = _find_first_text(soap_root, "DaneSzukajPodmiotyResult")
    if not result_text:
        raise GusNoDataError("Nie znaleziono danych GUS (REGON) dla podanego NIP.")

    dane_nodes = _parse_search_result_xml(result_text)
    if not dane_nodes:
        raise GusNoDataError("Nie znaleziono danych GUS (REGON) dla podanego NIP.")

    first = _dane_to_dict(dane_nodes[0])
    err = first.get("ErrorCode") or first.get("errorCode")
    if err:
        msg = first.get("ErrorMessagePl") or first.get("ErrorMessageEn") or f"kod {err}"
        if str(err) in ("4", "5"):  # brak wyników / nie znaleziono
            raise GusNoDataError(f"Nie znaleziono danych GUS (REGON) dla podanego NIP ({msg}).")
        raise GusBirError(f"GUS BIR: {msg}")

    gus_debug(
        "podmiot: "
        + ", ".join(
            f"{k}={first.get(k)!r}"
            for k in ("Nazwa", "Nip", "Regon", "Miejscowosc", "Typ")
            if first.get(k)
        )
    )
    return first


def fetch_podmiot_by_nip(nip_digits: str, *, api_key: str | None = None) -> dict[str, str]:
    """Wyszukuje podmiot w REGON po NIP (DaneSzukajPodmioty)."""
    key = api_key or get_gus_bir_key()
    if not key:
        raise GusBirError(
            "Brak klucza API GUS BIR. Ustaw klucz w menu Plik → Ustawienia integracji… "
            "lub zmienną GUS_BIR_API_KEY (wniosek: https://api.stat.gov.pl/Home/RegonApi)."
        )
    nip = normalize_nip_digits(nip_digits)
    url = get_gus_bir_api_base().rstrip("/")
    gus_debug(f"DaneSzukajPodmioty nip={nip} url={url}")

    sid = _login(url, key)
    try:
        return _search_by_nip(url, sid, nip)
    finally:
        _logout(url, sid)


def _country_pl(kraj: str | None) -> str:
    k = (kraj or "").strip().upper()
    if not k or k in ("PL", "POLSKA"):
        return "Polska"
    return kraj.strip() if kraj else "Polska"


def flat_podmiot_for_org(dane: dict[str, str]) -> dict[str, Any]:
    """Mapuje wynik DaneSzukajPodmioty na pola Organization + Address (jak flat_firma_for_org)."""
    bud = (dane.get("NrNieruchomosci") or "").strip()
    lok = (dane.get("NrLokalu") or "").strip()
    street_no = bud
    if lok and bud:
        street_no = f"{bud}/{lok}"
    elif lok and not bud:
        street_no = lok

    nip = re.sub(r"\D", "", dane.get("Nip") or "")
    regon = re.sub(r"\D", "", dane.get("Regon") or "")
    nazwa = (dane.get("Nazwa") or "").strip() or None
    ulica = (dane.get("Ulica") or "").strip() or None
    # GUS czasem zwraca „ul. …” albo samą nazwę ulicy
    if ulica and ulica.lower().startswith("ul."):
        ulica = ulica[3:].strip() or None

    return {
        "name": nazwa,
        "phone": None,
        "email": None,
        "org_nip": nip or None,
        "org_regon": regon or None,
        "street_name": ulica,
        "street_number": street_no or None,
        "zip_code": (dane.get("KodPocztowy") or "").strip() or None,
        "city": (dane.get("Miejscowosc") or "").strip() or None,
        "country": _country_pl(dane.get("Kraj") or "PL"),
        "status": (dane.get("StatusNip") or "").strip() or None,
    }
