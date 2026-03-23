# INV — aplikacja do faktur i słowników

Lokalna aplikacja desktopowa (Python + **tkinter**) do prowadzenia prostego systemu fakturowania: słowniki (podatki, jednostki, usługi, adresy, organizacje), lista faktur z szybkimi akcjami oraz **eksport faktury do PDF** (ReportLab). Dane przechowywane są w bazie **SQLite** w pliku w katalogu projektu.

## Wymagania

- **Python 3.10+** (w kodzie używana jest m.in. składnia adnotacji typów z `tuple[str, ...]`).
- Biblioteka **reportlab** (generowanie PDF).

```bash
pip install reportlab
```

Opcjonalnie własne środowisko wirtualne w katalogu projektu:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install reportlab
```

## Uruchomienie

Z katalogu głównego projektu (`INV`), aby ścieżki do bazy i folderu `reports/` były poprawne:

```bash
python main.py
```

Punkt wejścia wywołuje `init_db()` (utworzenie tabel i danych startowych, jeśli bazy jeszcze nie ma) oraz otwiera główne okno aplikacji.

## Struktura projektu (skrót)

| Element | Opis |
|--------|------|
| `main.py` | Uruchomienie: `from app.main import main` |
| `app/main.py` | Inicjalizacja bazy, DPI na Windows, start `MainApp` |
| `app/db.py` | Połączenie z SQLite, transakcje `tx()`, ścieżka bazy |
| `app/models/` | Logika SQL: faktury, organizacje, adresy, usługi, podatki, jednostki, dni w kalendarzu |
| `app/ui/` | Okna tkinter: lista faktur, CRUD słowników, kalendarz |
| `app/reports/invoice_pdf.py` | Budowa PDF faktury, podgląd w przeglądarce |
| `app/utils/translate_number.py` | Kwota słownie po polsku (do sekcji „słownie” na PDF) |
| `app/tools/` | Skrypty pomocnicze (migracje / generowanie insertów SQL) |
| `sqllite3_inv.db` | Plik bazy SQLite (tworzony przy pierwszym uruchomieniu) |
| `reports/` | Wygenerowane pliki PDF faktur |
| `backups/` | Kopie zapasowe CSV (jeśli używane w workflow) |

## Główne funkcje

- **Lista faktur** — tabela z ID, numerem, datą, statusem, sprzedawcą i nabywcą.
- **Edycja** — dwuklik lub Enter na wierszu otwiera okno faktury.
- **Akcje w tabeli** — kolumny z ikonami: druk PDF, zmiana statusu (szkic / wystawiona / opłacona).
- **Słowniki** (menu *Słowniki*): faktury, podatki, jednostki miary, usługi, adresy, organizacje.
- **Widok → Kalendarz** — kalendarz z obsługą świąt i dni niestandardowych (model `custom_days`).
- **PDF** — layout A4, dane z nagłówka i pozycji, kwoty z podatkiem; kwota **słownie** po polsku.

## Baza danych

- Plik: **`sqllite3_inv.db`** w bieżącym katalogu roboczym (zgodnie z `app/db.py`: `DB_PATH = Path("sqllite3_inv.db")`).
- Przy starcie tworzone są m.in. tabele: `Tax`, `Unit`, `Service`, `Address`, `Organization`, `PaymentMethod`, `Status`, `InvoiceType`, `Invoice`, `InvoiceDetail` (klucze obce włączone: `PRAGMA foreign_keys = ON`).

## Zmienne środowiskowe

- **`DEBUG_SQL`** — w `app/db.py` domyślnie włączone jest logowanie zapytań SQL do konsoli (`DEBUG_SQL=1`). Aby wyłączyć: ustaw np. `DEBUG_SQL=0` lub pustą wartość zgodnie z logiką w kodzie.

## Uwagi techniczne

- Aplikacja jest **okienkowa (Windows)**; w `app/main.py` ustawiane jest `SetProcessDpiAwareness` dla lepszego skalowania interfejsu.
- Skrypt `drop_db.py` w repozytorium ma **pustą zmienną ścieżki do bazy** — przed użyciem do resetu bazy należy uzupełnić ścieżkę lub ręcznie usunąć plik `sqllite3_inv.db` przy zamkniętej aplikacji.

## Licencja / autor

Projekt lokalny — brak pliku licencji w katalogu; uzupełnij według potrzeb.
