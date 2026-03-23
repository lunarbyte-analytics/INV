# tools/migrate_addresses.py
import sqlite3
from pathlib import Path
import csv
import argparse
from datetime import datetime

DB_PATH = Path("sqllite3_inv.db")
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

# AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country
DATA = [
    (1,  "1", "Ossowska", "90", "05-220", "Zielonka", "Polska"),
    (2,  "2", "Conrada", "12", "01-922", "Warszawa", "Polska"),
    (3,  "1", "Puławska", "99a", "02-595", "Warszawa", "Polska"),
    (4,  "1", "Pl. Marszałka Józefa Piłsudskiego", "1", "00-078", "Warszawa", "Polska"),
    (5,  "1", "Inflancka", "4A", "00-189", "Warszawa", "Polska"),
    (6,  "1", "Udrzynek", "33", "07-308", "Poręba", "Polska"),
    (7,  "1", "Wołoska", "9", "02-583", "Warszawa", "Polska"),
    (8,  "1", "Al. Jerozolimskie", "134", "02-305", "Warszawa", "Polska"),
    (9,  "1", "Marszałkowska", "126/134", "00-008", "Warszawa", "Polska"),
    (10, "1", "Aleja Pokoju", "18", "31-564", "Kraków", "Polska"),
    (11, "1", "Fabryczna Office Park B4, Aleja Pokoju", "18C", "31-564", "Kraków", "Polska"),
]

SQL_UPSERT = """
INSERT INTO Address (AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(AddressId) DO UPDATE SET
    AddressType = excluded.AddressType,
    StreetName  = excluded.StreetName,
    StreetNumber= excluded.StreetNumber,
    ZipCode     = excluded.ZipCode,
    City        = excluded.City,
    Country     = excluded.Country;
"""

def backup_table(cur: sqlite3.Cursor, table: str, path: Path):
    cur.execute(f"SELECT * FROM {table};")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])

def get_referenced_address_ids(cur: sqlite3.Cursor) -> set[int]:
    """Zbierz wszystkie AddressId użyte w Organization (AddressId + AdditionalAddressId)."""
    cur.execute("SELECT AddressId FROM Organization WHERE AddressId IS NOT NULL")
    ids = {row[0] for row in cur.fetchall()}
    cur.execute("SELECT AdditionalAddressId FROM Organization WHERE AdditionalAddressId IS NOT NULL")
    ids |= {row[0] for row in cur.fetchall()}
    return ids

def get_existing_address_ids(cur: sqlite3.Cursor) -> set[int]:
    cur.execute("SELECT AddressId FROM Address")
    return {row[0] for row in cur.fetchall()}

def main():
    parser = argparse.ArgumentParser(description="Migracja danych do tabeli Address (UPSERT).")
    parser.add_argument("--prune", action="store_true",
                        help="Usuń z Address rekordy nieobecne na liście DATA (tylko te, które nie są referencjonowane).")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"❌ Nie znaleziono bazy: {DB_PATH.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        # Backup tabel powiązanych
        backup_table(cur, "Address",      BACKUP_DIR / f"address_{ts}.csv")
        backup_table(cur, "Organization", BACKUP_DIR / f"organization_{ts}.csv")
        print(f"💾 Backup zapisany w {BACKUP_DIR}/")

        conn.execute("BEGIN;")

        # UPSERT wszystkich adresów z listy
        cur.executemany(SQL_UPSERT, DATA)
        print(f"✅ Wstawiono/zaktualizowano {len(DATA)} rekordów Address.")

        # Opcjonalne porządkowanie – usuń adresy nieobecne w DATA i nieużywane
        if args.prune:
            new_ids = {a[0] for a in DATA}
            existing_ids = get_existing_address_ids(cur)
            referenced_ids = get_referenced_address_ids(cur)
            candidates = sorted(existing_ids - new_ids)

            # zostaw te, które są referencjonowane
            to_delete = [aid for aid in candidates if aid not in referenced_ids]

            if to_delete:
                print(f"⚠️ Do usunięcia {len(to_delete)} rekordów nieobecnych w DATA i nieużywanych: {to_delete[:10]}{'...' if len(to_delete)>10 else ''}")
                confirm = input("Potwierdź usunięcie (TAK/NIE): ").strip().upper()
                if confirm == "TAK":
                    cur.executemany("DELETE FROM Address WHERE AddressId = ?;", [(aid,) for aid in to_delete])
                    print(f"🧹 Usunięto {len(to_delete)} rekordów Address.")
                else:
                    print("⏭️ Pominięto usuwanie.")
            else:
                print("ℹ️ Brak kandydatów do usunięcia (albo wszystkie są referencjonowane).")

        conn.commit()
        print("🎉 Migracja Address zakończona powodzeniem.")
    except Exception as e:
        conn.rollback()
        print("❌ Błąd migracji:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
