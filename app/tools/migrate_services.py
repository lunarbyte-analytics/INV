import sqlite3
from pathlib import Path

DB_PATH = Path("sqllite3_inv.db")

DATA = [
    (-1, -1, -1, "Brak", 0.00, "1"),
    (1, 1, 1, "Usługa doradztwa przy projektach w obszarze rozwoju hurtowni danych", 75.00, "1"),
    (2, 1, 1, "Rozliczenie delegacji slużbowej", 669.44, "1"),
    (3, 1, 1, "Usługi informatyczne zgodnie z umową z dnia 10.12.2014 r.", 9500.00, "1"),
    (4, 1, 1, "Usługi informatyczne zgodne z umową z dnia 10.12.2014 r.", 720.00, "2"),
    (5, 1, 1, "Usługi informatyczne zgodne z umową z dnia 10.12.2014 r.", 90.00, "3"),
    (6, 1, 1, "Rozliczenie wyjazdu służbowego", 2758.93, "1"),
    (7, 1, 1, "Rozliczenie delegacji slużbowej", 1119.84, "1"),
    (8, 1, 1, "Rozliczenie delegacji służbowej 26/06", 1753.28, "1"),
    (9, 1, 1, "Rozliczenie delegacji służbowej 06/08", 1280.55, "1"),
    (10, 1, 1, "Usługi zgodne z umową z dnia 06.11.2017", 115.00, "1"),
    (11, 1, 1, "Rozliczenie delegacji służbowej 03/11", 477.50, "1"),
    (12, 1, 1, "Usługi zgodne z umową z dnia 06.11.2017", 117.31, "aneks1"),
    (13, 1, 1, "Rozliczenie delegacji służbowej 24/05", 270.00, "1"),
    (14, 1, 1, "Rozliczenie delegacji służbowej 10/09", 504.43, "1"),
    (15, 1, 1, "Usługi zgodne z umową z dnia 06.11.2017", 120.00, "aneks2"),
    (16, 1, 1, "Koszty dodatkowe zgodne z umową", 485.19, "1"),
    (17, 1, 1, "Usługi zgodne z umową z dnia 06.11.2017", 122.20, "aneks3"),
    (18, 1, 1, "Koszty dodatkowe zgodne z umową", 429.00, "1"),
    (19, 1, 1, "Polecenie dostawcy", 3000.00, "1"),
    (20, 1, 1, "Usługi zgodne z umową 18/2021", 1080.00, "1"),
    (21, 1, 1, "Usługi zgodne z umową 18/2021", 1120.00, "2"),
    (22, 2, 1, "Randstad umowa z 24.03.2022", 147.00, "1"),
    (23, 1, 1, "Rozliczenie kosztów dodatkowych", 4052.72, "1"),
    (24, 2, 1, "Usługa informatyczna/ realizacja projektu/ prace programistyczne związane z rozwojem aplikacji bazodanowych zgodnie z umową z dnia 30.11.2022 r.", 160.00, "1"),
    (25, 1, 1, "Zamówienie Nr 3700209325", 3100.00, "1"),
    (26, 1, 1, "Zamówienie Nr 3700209325", 415.47, "1"),
    (27, 1, 1, "Zamówienie Nr 3700242722", 4010.39, "1"),
    (28, 1, 1, "Zamówienie Nr 3700287707", 4730.00, "1"),
    (29, 2, 1, "Usługi zgodne z umową z dnia 07.10.2024 PO 4500182248", 180.00, "1"),
    (30, 1, 1, "Wydatki związane z delegacją", 4535.00, "1"),
]

SQL_INSERT = """
INSERT INTO Service (ServiceId, UnitId, TaxId, Name, UnitPrice, Version)
VALUES (?, ?, ?, ?, ?, ?);
"""

def main():
    if not DB_PATH.exists():
        raise SystemExit(f"❌ Nie znaleziono bazy: {DB_PATH.resolve()}")

    print("⚠️ UWAGA: ta operacja USUNIE WSZYSTKIE rekordy z tabeli Service.")
    confirm = input("Czy na pewno chcesz kontynuować? (TAK/NIE): ").strip().upper()
    if confirm != "TAK":
        print("❌ Anulowano migrację.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    try:
        # Czyszczenie tabeli
        cur.execute("DELETE FROM Service;")
        print("🧹 Wyczyściłem tabelę Service.")

        # Wstawienie danych
        cur.executemany(SQL_INSERT, DATA)
        conn.commit()
        print(f"✅ Zakończono migrację — wstawiono {len(DATA)} rekordów.")
    except Exception as e:
        conn.rollback()
        print("❌ Błąd migracji:", e)
    finally:
        conn.close()


if __name__ == "__main__":
    main()