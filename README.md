# INV — aplikacja do faktur

Lokalna aplikacja desktopowa (Python + **tkinter**) do **fakturowania**: lista i edycja faktur (w tym korekty), **eksport do PDF** (ReportLab), integracja z **KSeF** (wysyłka FA(2), pobieranie faktur zakupowych z API, import XML). Dane pomocnicze — kontrahenci, usługi, podatki, jednostki, adresy — w menu **Encje**. Wszystko w bazie **SQLite** w pliku w katalogu projektu.

## Wymagania

- **Python 3.10+**
- Zależności z pliku **`requirements.txt`** (m.in. ReportLab, `cryptography`, `tzdata`, `tkcalendar`).

```bash
pip install -r requirements.txt
```

Opcjonalnie środowisko wirtualne:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uruchomienie

Z katalogu głównego projektu (`INV`), aby ścieżki do bazy i folderu `reports/` były poprawne:

```bash
python main.py
```

Przy starcie wywoływane są `init_db()` (tabele i dane startowe) oraz główne okno aplikacji (domyślnie **zmaksymalizowane** na Windows).

### Windows — dla osób nietechnicznych (bez znajomości Pythona)

1. **Zainstaluj Pythona** (jednorazowo): [python.org — pobieranie dla Windows](https://www.python.org/downloads/windows/), wersja **3.10+**. Przy instalacji zaznacz **„Add python.exe to PATH”** (lub „Add Python to environment variables”).
2. **Skopiuj cały folder projektu** `INV` na komputer (np. z pendrive’a lub ZIP).
3. **Uruchom:** dwukrotnie kliknij **`UruchomINV.bat`**. Skrypt ustawi katalog roboczy, uruchomi `pip install -r requirements.txt` (cicho) i startuje aplikację.

Baza (`sqllite3_inv.db`) i PDF (`reports/`) tworzą się **w tym samym folderze** co `UruchomINV.bat` — nie przenoś samego `.bat` bez reszty katalogu.

**Dystrybucja bez Pythona u odbiorcy** — osobna budowa np. **`.exe`** (PyInstaller / Nuitka); to krok dla osoby technicznej.

## Menu (skrót)

| Menu | Zawartość |
|------|-----------|
| **Plik** (pierwsze na pasku) | Środowisko aplikacji (baza test / prod), **Ustawienia integracji…** (KSeF, CEIDG itd.), Zakończ |
| **Encje** | Podatki, jednostki, usługi, adresy, organizacje |
| **Widok** | Nowa faktura, Kalendarz (dni wolne / święta) |
| **KSeF** | Test połączenia, faktury zakupowe (zapytanie do API) |

Ustawienia integracji można też trzymać w pliku JSON (np. `inv_app_settings.json`) — szczegóły w kodzie `app/app_env.py` (priorytet pól w pliku vs zmiennych środowiskowych).

## Główne funkcje

- **Lista faktur** — filtr „Moja firma (kontekst)” i widok sprzedaż/zakup; kolumna **Typ** (względem kontekstu); dla faktury korygującej dopisek **„korekta”** (np. „Sprzedaż korekta”). Przyciski pod listą: PDF, statusy, **Wyślij do KSeF**, pobieranie zakupowych z KSeF, nowa korekta, odświeżenie. Krótki opis kolumny Typ — pod przyciskiem **?**.
- **Okno faktury** — nagłówek, pozycje, historia wysyłek KSeF; daty (**wystawienia, sprzedaży, płatności**) w polach z **kalendarzem** (`tkcalendar`).
- **PDF** — A4, kwoty z podatkiem, kwota **słownie** po polsku.
- **KSeF — faktury zakupowe** — zakres dat (też z kalendarzem), rozmiar strony; lista wyników z **stronicowaniem** (`<` / `>`). Parametr API `pageOffset` to **numer strony** (0, 1, 2…), nie przesunięcie rekordów.

## Struktura projektu (skrót)

| Element | Opis |
|--------|------|
| `main.py` | Uruchomienie: `from app.main import main` |
| `UruchomINV.bat` | Start na Windows bez ręcznego `pip` / `python` |
| `requirements.txt` | Zależności Python |
| `app/main.py` | Inicjalizacja bazy, DPI na Windows, start `MainApp` |
| `app/db.py` | SQLite, `tx()`, ścieżka bazy |
| `app/models/` | Logika SQL: faktury, organizacje, encje, KSeF |
| `app/ksef/` | Klient HTTP, FA(2), wysyłka, import, zakupy |
| `app/ui/` | Okna tkinter: lista faktur, CRUD faktury i encji, KSeF, ustawienia |
| `app/reports/invoice_pdf.py` | PDF faktury, podgląd |
| `app/utils/translate_number.py` | Kwota słownie (PL) |
| `sqllite3_inv.db` | Baza SQLite (tworzona przy pierwszym uruchomieniu) |
| `reports/` | Wygenerowane PDF |
| `backups/` | Kopie CSV (jeśli używane) |

## Baza danych

- Plik: **`sqllite3_inv.db`** w bieżącym katalogu roboczym (`app/db.py`).
- Tabele m.in.: `Tax`, `Unit`, `Service`, `Address`, `Organization`, `PaymentMethod`, `Status`, `InvoiceType`, `Invoice`, `InvoiceDetail`, `InvoiceKsefSubmission` (klucze obce: `PRAGMA foreign_keys = ON`).

## Zmienne środowiskowe

- **`DEBUG_SQL`** — w `app/db.py` logowanie SQL do konsoli; wyłączenie: np. `DEBUG_SQL=0` (zgodnie z logiką w kodzie).
- KSeF (token, NIP, URL) — opis w **Plik → Ustawienia integracji…** i w `app/app_env.py`.

## Uwagi techniczne

- Aplikacja jest **okienkowa**; w `app/main.py` ustawiane jest `SetProcessDpiAwareness` (Windows).
- Skrypt `drop_db.py` (jeśli jest w repozytorium) — przed użyciem sprawdź ścieżkę do bazy lub usuń `sqllite3_inv.db` przy zamkniętej aplikacji.

## Licencja / autor

Projekt lokalny — brak pliku licencji w katalogu; uzupełnij według potrzeb.
