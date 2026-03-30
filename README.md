# INV — aplikacja do faktur / invoicing application

## Polski

Lokalna aplikacja desktopowa (Python + **tkinter**) do **fakturowania**: lista i edycja faktur (w tym korekty), **eksport do PDF** (ReportLab), integracja z **KSeF** (wysyłka FA(2), pobieranie faktur zakupowych z API, import XML). Dane pomocnicze — kontrahenci, usługi, podatki, jednostki, adresy — w menu **Encje**. Wszystko w bazie **SQLite** w pliku w katalogu projektu.

### Wymagania

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

### Uruchomienie

Z katalogu głównego projektu (`INV`), aby ścieżki do bazy i folderu `reports/` były poprawne:

```bash
python main.py
```

Przy starcie wywoływane są `init_db()` (tabele i dane startowe) oraz główne okno aplikacji (domyślnie **zmaksymalizowane** na Windows).

#### Windows — dla osób nietechnicznych (bez znajomości Pythona)

1. **Zainstaluj Pythona** (jednorazowo): [python.org — pobieranie dla Windows](https://www.python.org/downloads/windows/), wersja **3.10+**. Przy instalacji zaznacz **„Add python.exe to PATH”** (lub „Add Python to environment variables”).
2. **Skopiuj cały folder projektu** `INV` na komputer (np. z pendrive’a lub ZIP).
3. **Uruchom:** dwukrotnie kliknij **`UruchomINV.bat`**. Skrypt ustawi katalog roboczy, uruchomi `pip install -r requirements.txt` (cicho) i startuje aplikację.

Baza (`sqllite3_inv.db`) i PDF (`reports/`) tworzą się **w tym samym folderze** co `UruchomINV.bat` — nie przenoś samego `.bat` bez reszty katalogu.

**Dystrybucja bez Pythona u odbiorcy** — osobna budowa np. **`.exe`** (PyInstaller / Nuitka); to krok dla osoby technicznej.

### Menu (skrót)

| Menu | Zawartość |
|------|-----------|
| **Plik** (pierwsze na pasku) | Środowisko aplikacji (baza test / prod), **Ustawienia integracji…** (KSeF, CEIDG itd.), Zakończ |
| **Encje** | Podatki, jednostki, usługi, adresy, organizacje |
| **Widok** | Nowa faktura, Kalendarz (dni wolne / święta) |
| **KSeF** | Test połączenia, faktury zakupowe (zapytanie do API) |

Ustawienia integracji można też trzymać w pliku JSON (np. `inv_app_settings.json`) — szczegóły w kodzie `app/app_env.py` (priorytet pól w pliku vs zmiennych środowiskowych).

### Główne funkcje

- **Lista faktur** — filtr „Moja firma (kontekst)” i widok sprzedaż/zakup; kolumna **Typ** (względem kontekstu); dla faktury korygującej dopisek **„korekta”** (np. „Sprzedaż korekta”). Przyciski pod listą: PDF, statusy, **Wyślij do KSeF**, pobieranie zakupowych z KSeF, nowa korekta, odświeżenie. Krótki opis kolumny Typ — pod przyciskiem **?**.
- **Okno faktury** — nagłówek, pozycje, historia wysyłek KSeF; daty (**wystawienia, sprzedaży, płatności**) w polach z **kalendarzem** (`tkcalendar`).
- **PDF** — A4, kwoty z podatkiem, kwota **słownie** po polsku.
- **KSeF — faktury zakupowe** — zakres dat (też z kalendarzem), rozmiar strony; lista wyników z **stronicowaniem** (`<` / `>`). Parametr API `pageOffset` to **numer strony** (0, 1, 2…), nie przesunięcie rekordów.

### Struktura projektu (skrót)

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

### Baza danych

- Plik: **`sqllite3_inv.db`** w bieżącym katalogu roboczym (`app/db.py`).
- Tabele m.in.: `Tax`, `Unit`, `Service`, `Address`, `Organization`, `PaymentMethod`, `Status`, `InvoiceType`, `Invoice`, `InvoiceDetail`, `InvoiceKsefSubmission` (klucze obce: `PRAGMA foreign_keys = ON`).

### Zmienne środowiskowe

- **`DEBUG_SQL`** — w `app/db.py` logowanie SQL do konsoli; wyłączenie: np. `DEBUG_SQL=0` (zgodnie z logiką w kodzie).
- KSeF (token, NIP, URL) — opis w **Plik → Ustawienia integracji…** i w `app/app_env.py`.

### Uwagi techniczne

- Aplikacja jest **okienkowa**; w `app/main.py` ustawiane jest `SetProcessDpiAwareness` (Windows).
- Skrypt `drop_db.py` (jeśli jest w repozytorium) — przed użyciem sprawdź ścieżkę do bazy lub usuń `sqllite3_inv.db` przy zamkniętej aplikacji.

### Licencja / autor

Projekt lokalny — brak pliku licencji w katalogu; uzupełnij według potrzeb.

---

## English

A local desktop app (Python + **tkinter**) for **invoicing**: invoice list and editing (including corrections), **PDF export** (ReportLab), and **KSeF** integration (FA(2) submission, purchase invoices from the API, XML import). Master data — contractors, services, taxes, units, addresses — lives under the **Encje** menu. Everything is stored in an **SQLite** database file in the project directory.

### Requirements

- **Python 3.10+**
- Dependencies listed in **`requirements.txt`** (including ReportLab, `cryptography`, `tzdata`, `tkcalendar`).

```bash
pip install -r requirements.txt
```

Optional virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Running the app

From the project root (`INV`), so paths to the database and `reports/` resolve correctly:

```bash
python main.py
```

On startup, `init_db()` runs (tables and seed data) and the main window opens (**maximized** by default on Windows).

#### Windows — non-technical users (no Python experience)

1. **Install Python** (once): [python.org — Windows downloads](https://www.python.org/downloads/windows/), version **3.10+**. During setup, enable **“Add python.exe to PATH”** (or “Add Python to environment variables”).
2. **Copy the whole project folder** `INV` to the machine (e.g. USB drive or ZIP).
3. **Run:** double-click **`UruchomINV.bat`**. The script sets the working directory, runs `pip install -r requirements.txt` (quietly), and starts the app.

The database (`sqllite3_inv.db`) and PDFs (`reports/`) are created **in the same folder** as `UruchomINV.bat` — do not move only the `.bat` file without the rest of the directory.

**Shipping without Python on the target machine** requires building an **`.exe`** (e.g. PyInstaller / Nuitka); that is a separate step for a technical person.

### Menu (overview)

| Menu | Contents |
|------|----------|
| **Plik** (first on the bar) | App environment (test / prod database), **Integration settings…** (KSeF, CEIDG, etc.), Exit |
| **Encje** | Taxes, units, services, addresses, organizations |
| **Widok** | New invoice, Calendar (public holidays / custom days off) |
| **KSeF** | Connection test, purchase invoices (API query) |

Integration settings can also be stored in a JSON file (e.g. `inv_app_settings.json`) — see `app/app_env.py` (priority of file fields vs environment variables).

### Main features

- **Invoice list** — “My company (context)” filter and sales/purchase view; **Type** column (relative to context); correcting invoices show a **“korekta”** suffix (e.g. “Sprzedaż korekta”). Buttons under the list: PDF, statuses, **Send to KSeF**, KSeF purchase fetch, new correction, refresh. Short help for the Type column — **?** button.
- **Invoice window** — header, line items, KSeF submission history; **issue, sale, payment** dates use **calendar** pickers (`tkcalendar`).
- **PDF** — A4 layout, amounts with VAT, amount **in words** in Polish.
- **KSeF — purchase invoices** — date range (also with calendar), page size; result list with **pagination** (`<` / `>`). The API parameter `pageOffset` is the **page number** (0, 1, 2…), not a row skip.

### Project layout (short)

| Item | Description |
|------|-------------|
| `main.py` | Entry: `from app.main import main` |
| `UruchomINV.bat` | Windows launcher without manual `pip` / `python` |
| `requirements.txt` | Python dependencies |
| `app/main.py` | DB init, Windows DPI, `MainApp` |
| `app/db.py` | SQLite, `tx()`, DB path |
| `app/models/` | SQL logic: invoices, organizations, entities, KSeF |
| `app/ksef/` | HTTP client, FA(2), submit, import, purchases |
| `app/ui/` | tkinter UI: invoice list, invoice/entity CRUD, KSeF, settings |
| `app/reports/invoice_pdf.py` | Invoice PDF, preview |
| `app/utils/translate_number.py` | Amount in words (PL) |
| `sqllite3_inv.db` | SQLite database (created on first run) |
| `reports/` | Generated PDFs |
| `backups/` | CSV backups (if used) |

### Database

- File: **`sqllite3_inv.db`** in the current working directory (`app/db.py`).
- Tables include: `Tax`, `Unit`, `Service`, `Address`, `Organization`, `PaymentMethod`, `Status`, `InvoiceType`, `Invoice`, `InvoiceDetail`, `InvoiceKsefSubmission` (foreign keys: `PRAGMA foreign_keys = ON`).

### Environment variables

- **`DEBUG_SQL`** — in `app/db.py`, logs SQL to the console; disable e.g. with `DEBUG_SQL=0` (see code).
- KSeF (token, NIP, URL) — see **Plik → Ustawienia integracji…** and `app/app_env.py`.

### Technical notes

- The app is **desktop GUI**; `app/main.py` sets `SetProcessDpiAwareness` on Windows.
- Script `drop_db.py` (if present in the repo) — verify DB path before use, or delete `sqllite3_inv.db` while the app is closed.

### License / author

Local project — no license file in the repo; add as needed.
