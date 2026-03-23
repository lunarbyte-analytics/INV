from pathlib import Path
from datetime import datetime
import webbrowser
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from ..models.invoice import get_invoice_full
import os
from decimal import Decimal, ROUND_HALF_UP
try:
    # dostosuj ścieżkę importu do Twojego projektu
    from ..utils.translate_number import TranslateNumber
except Exception:
    # awaryjnie: zakładamy, że TranslateNumber jest w tym samym folderze
    from translate_number import TranslateNumber


REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

def _pl_form(n: int, forms: tuple[str, str, str]) -> str:
    """
    Zwraca poprawną formę rzeczownika dla liczby n.
    forms = (liczba pojedyncza, liczba mnoga 2-4, liczba mnoga 5+)
    """
    n = abs(int(n))
    if n == 1:
        return forms[0]
    # 12–14 to forma 5+ (złotych/groszy)
    if 10 < (n % 100) < 15:
        return forms[2]
    last = n % 10
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def _amount_words_pl(amount: Decimal | float) -> str:
    """
    Zwraca tekst 'xxx xxx zł yy gr' słownie, np.
    'sto dwadzieścia trzy złote czterdzieści pięć groszy'.
    Używa dostarczonego TranslateNumber (do 99 999).
    """
    tn = TranslateNumber()

    # Bezpieczne zaokrąglenie do 2 miejsc
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    zl = int(d)
    gr = int((d - Decimal(zl)) * 100)

    # słowa (TranslateNumber przyjmuje string)
    def _to_words(num: int) -> str:
        s = str(num)
        # TranslateNumber obsługuje do 5 cyfr (<= 99 999)
        if len(s) <= 5:
            w = tn.get_translation(s).strip()
            # jeżeli z jakiegoś powodu zwróci pusty string – awaryjnie cyfry
            return w if w else s
        # bardzo duże kwoty – awaryjnie sformatuj cyframi
        return s

    zl_s = _to_words(zl)
    gr_s = _to_words(gr)

    zl_word = _pl_form(zl, ("złoty", "złote", "złotych"))
    gr_word = _pl_form(gr, ("grosz", "grosze", "groszy"))

    return f"{zl_s} {zl_word} {gr_s} {gr_word}"

def _wrap_every_n_words(text: str, n: int = 3) -> str:
    if not text:
        return ""
    words = str(text).split()
    lines = []
    for i in range(0, len(words), n):
        lines.append(" ".join(words[i:i+n]))
    # Paragraph rozumie <br/> jako nową linię
    return "<br/>".join(lines)

def _addr_html(street: str, no: str, zipc: str, city: str, country: str, nip: str = "") -> str:
    """
    Składa adres do formatu HTML z <br/> i obsługuje dodatkowy parametr NIP.
    Linia NIP pojawia się tylko, jeśli nip jest niepusty.
    """
    parts = []

    # Ulica + numer
    if street or no:
        parts.append(" ".join([p for p in (street, no) if p]))

    # Kod pocztowy + miasto
    if zipc or city:
        parts.append(" ".join([p for p in (zipc, city) if p]))

    # Kraj
    if country:
        parts.append(country)

    # NIP (nowa linia)
    if nip:
        parts.append(f"NIP: {nip}")

    # Jeśli kompletnie puste
    if not parts:
        return "-"

    # Rozbijanie po przecinku na segmenty
    full = ", ".join(parts)
    segments = [seg.strip() for seg in full.split(",") if seg.strip()]

    return "<br/>".join(segments)


# -------------------- FONTS (Unicode) --------------------
def _first_existing(paths):
    for p in paths:
        if p and Path(p).exists():
            return p
    return None

def _register_pl_font():
    """
    Rejestruje fonty TTF/OTF z polskimi znakami i zwraca tuple: (FONT_REGULAR, FONT_BOLD).
    Kolejność preferencji: DejaVu Sans, Noto Sans, Arial (Windows).
    """
    candidates_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "C:/Windows/Fonts/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/NotoSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]

    reg_path = _first_existing(candidates_regular)
    bold_path = _first_existing(candidates_bold)

    # jeśli nic nie znaleziono, podpowiedź (ale spróbujemy i tak działać na Helvetica)
    if not reg_path or not bold_path:
        print("Uwaga: nie znaleziono czcionek z polskimi znakami. "
              "Zainstaluj DejaVu Sans / Noto Sans / Arial i ustaw ścieżkę.")

    # Nazwy fontów w ReportLab
    font_reg = "DejaVuSans" if reg_path and "DejaVu" in os.path.basename(reg_path) else \
               "NotoSans" if reg_path and "NotoSans" in os.path.basename(reg_path) else \
               "Arial" if reg_path and "arial" in os.path.basename(reg_path).lower() else \
               "UnicodeRegular"

    font_bold = "DejaVuSans-Bold" if bold_path and "DejaVu" in os.path.basename(bold_path) else \
                "NotoSans-Bold" if bold_path and "NotoSans" in os.path.basename(bold_path) else \
                "Arial-Bold" if bold_path and "arial" in os.path.basename(bold_path).lower() else \
                "UnicodeBold"

    try:
        if reg_path:
            pdfmetrics.registerFont(TTFont(font_reg, reg_path))
        if bold_path:
            pdfmetrics.registerFont(TTFont(font_bold, bold_path))
    except Exception as e:
        print("Błąd rejestracji fontów:", e)

    return font_reg or "Helvetica", font_bold or "Helvetica-Bold"


def _fmt_money(x: float) -> str:
    return f"{x:.2f}"


def generate_invoice_pdf(invoice_id: int) -> Path:
    header, details = get_invoice_full(invoice_id)
    pdf_path = REPORTS_DIR / f"faktura_{invoice_id}.pdf"

    # Rejestracja czcionek PL
    FONT_REG, FONT_BOLD = _register_pl_font()

    # Dokument
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    # Style – podmień fonty na Unicode
    styles = getSampleStyleSheet()
    # Normal
    styles["Normal"].fontName = FONT_REG
    styles["Normal"].fontSize = 10
    # Title / Headings
    styles["Title"].fontName = FONT_BOLD
    styles["Title"].fontSize = 18
    if "Heading1" in styles:
        styles["Heading1"].fontName = FONT_BOLD
    if "Heading2" in styles:
        styles["Heading2"].fontName = FONT_BOLD

    story = []

    # Nagłówek – używamy numeru z bazy (Invoice.Name)
    invoice_name = header.get("Name") or f"nr {invoice_id}"
    title = f"Faktura {invoice_name}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))

    # Sprzedawca / Nabywca
    company = header["CompanyName"] or f"Org {header['CompanyId']}"
    customer = header["CustomerName"] or f"Org {header['CustomerId']}"
    pm_name = header["PaymentName"]
    st_name = header["StatusName"]
    tp_name = header["TypeName"]

    # nazwy łamane co 3 słowa + adres pod spodem (mniejsza czcionka)
    company_block = Paragraph(
        _wrap_every_n_words(company, 3) + "<br/><font size=9>" +
        _addr_html(header.get("CoStreet"), header.get("CoStreetNo"),
                header.get("CoZip"), header.get("CoCity"), header.get("CoCountry"), header.get("CoNIP")) +
        "</font>",
        styles["Normal"]
    )

    customer_block = Paragraph(
        _wrap_every_n_words(customer, 3) + "<br/><font size=9>" +
        _addr_html(header.get("CuStreet"), header.get("CuStreetNo"),
                header.get("CuZip"), header.get("CuCity"), header.get("CuCountry"), header.get("CuNIP")) +
        "</font>",
        styles["Normal"]
    )

    meta_table = Table(
        [
            ["Sprzedawca:", company_block, "Nabywca:", customer_block],
            ["Typ:", tp_name],
            ["Płatność:", pm_name, "Wystawienie:", header["CreateDate"]],
            ["Sprzedaż:", header["SalesDate"], "Termin płatności:", header["PaymentDate"]],
        ],
        colWidths=[28*mm, 70*mm, 28*mm, 70*mm]
    )
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_REG),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),   # etykiety lewe
        ("FONTNAME", (2, 0), (2, -1), FONT_BOLD),   # etykiety prawe
        # pozwól Paragraphom się zawijać
        ("WORDWRAP", (1, 0), (1, -1), "CJK"),
        ("WORDWRAP", (3, 0), (3, -1), "CJK"),
    ]))

    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Tabela pozycji
    p_service = ParagraphStyle(
        "ServiceCell",
        parent=styles["Normal"],
        fontName=FONT_REG,
        fontSize=9,
        leading=11,
        alignment=0,     # LEFT
        wordWrap="LTR",  # zawijanie wg. spacji/znaków interpunkcyjnych
    )

    # Szerokości MUSZĄ się sumować do 180 mm (A4: 210 - 2*15)
    col_widths = [72*mm, 10*mm, 14*mm, 18*mm, 12*mm, 18*mm, 18*mm, 18*mm]  # = 180 mm

    data = [["Usługa", "Jm", "Ilość", "Cena", "VAT %", "Netto", "VAT", "Brutto"]]
    net_sum = vat_sum = gross_sum = 0.0
    for d in details:
        qty = float(d["Quantity"])
        price = float(d["UnitPrice"])
        tax = float(d["TaxValue"])
        line_net = price * qty
        line_vat = round(line_net * tax / 100.0, 2)
        line_gross = line_net + line_vat
        net_sum += line_net
        vat_sum += line_vat
        gross_sum += line_gross

        # <<< NAZWA USŁUGI JAKO Paragraph – będzie się zawijać w kolumnie 72 mm
        name_para = Paragraph(d["ServiceName"], p_service)

        data.append([
            name_para, d["UnitCode"], f"{qty:.2f}",
            _fmt_money(price), f"{tax:.2f}",
            _fmt_money(line_net), _fmt_money(line_vat), _fmt_money(line_gross)
        ])

    tbl = Table(
        data,
        colWidths=col_widths,
        repeatRows=1  # powtarzaj nagłówek na kolejnych stronach
    )
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 9),

        ("FONTNAME", (0, 1), (-1, -1), FONT_REG),
        ("FONTSIZE", (0, 1), (-1, -1), 9),

        ("ALIGN", (0, 1), (0, -1), "LEFT"),   # kolumna „Usługa”
        ("ALIGN", (1, 1), (1, -1), "CENTER"), # „Jm”
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"), # reszta liczbowa

        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # Podsumowanie
    sum_table = Table(
        [
            ["Suma netto:", _fmt_money(net_sum)],
            ["Suma VAT:", _fmt_money(vat_sum)],
            ["Suma brutto:", _fmt_money(gross_sum)],
        ],
        colWidths=[35*mm, 35*mm],
        hAlign="RIGHT"
    )
    sum_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_REG),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(sum_table)

    # Kwota słownie
    try:
        gross_dec = Decimal(str(gross_sum)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        kwota_slownie = _amount_words_pl(gross_dec)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<b>Kwota słownie:</b> {kwota_slownie}",
            styles["Normal"]
        ))
    except Exception as e:
        # nie blokuj wydruku, gdyby coś poszło nie tak
        print("[WARN] Kwota słownie – błąd:", e)
        
    # Stopka
    #story.append(Spacer(1, 10))
    #story.append(Paragraph(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))

    doc.build(story)
    return pdf_path


def open_preview(pdf_path: Path) -> None:
    webbrowser.open(pdf_path.resolve().as_uri())
