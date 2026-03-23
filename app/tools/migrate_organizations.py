# tools/migrate_organizations.py
import sqlite3
from pathlib import Path
import csv
import argparse
from datetime import datetime

DB_PATH = Path("sqllite3_inv.db")
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

# OrganizationId, AddressId, AdditionalAddressId, Name, Phone, Email, OrgNbr1, OrgNbr2, OrgNbr3, BankAccountNbr
RAW_DATA = [
    (1, 1,   2,   "ACARD Paweł Sawukajtys",               "609644933",           "pawel.sawukajtys@gmail.com", "1181598443", None,        None,        None),
    (2, 3,   None,"Lingaro Sp. z o.o.",                    None,                  None,                          "5272549518", None,        None,        None),
    (3, 4,   None,"Affecto Poland Sp. z o.o.",             None,                  None,                          "5272549518", None,        None,        None),
    (4, 5,   None,"KMD POLAND sp. z o.o.",                 None,                  "vendors@kmdpoland.pl",        "5252591003", "147336430", None,        None),
    (5, 6,   None,"Kulesza Piotr",                         None,                  None,                          None,        None,        None,        None),
    (9, 7,   None,"Relyon IT Services Sp. z o.o. Sp.k",    None,                  None,                          "5213635475", "0000538538", None,       None),
    (10,7,   None,"RITS Professional Services sp. z o.o.", None,                  None,                          "5213635475", "0000538538", None,       None),
    (11,8,   None,"Randstad Services APO Sp. z o.o. Sp. k.", None,                "atos@randstad.pl",            "5272557469", "141161604", None,        None),
    (12,9,   None,"Hays Poland Sp. z o. o.",               None,                  "atosITC@hays.pl",             "5252269193", None,        None,        None),
    (13,11,None,"Novocure Poland Spółka z Ograniczoną Odpowiedzialnością", None, "ap.pl@novocure.com",         "6772483881", None,        None,        None),
]

SQL_UPSERT = """
INSERT INTO Organization
(OrganizationId, AddressId, AdditionalAddressId, Name, Phone, Email, OrgNbr1, OrgNbr2, OrgNbr3, BankAccountNbr)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(OrganizationId) DO UPDATE SET
    AddressId           = excluded.AddressId,
    AdditionalAddressId = excluded.AdditionalAddressId,
    Name                = excluded.Name,
    Phone               = excluded.Phone,
    Email               = excluded.Email,
    OrgNbr1             = excluded.OrgNbr1,
    OrgNbr2             = excluded.OrgNbr2,
    OrgNbr3             = excluded.OrgNbr3,
    BankAccountNbr      = excluded.BankAccountNbr;
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

def get_existing_ids(cur: sqlite3.Cursor, table: str, key: str) -> set[int]:
    cur.execute(f"SELECT {key} FROM {table};")
    return {row[0] for row in cur.fetchall()}

def get_invoice_org_ids(cur: sqlite3.Cursor) -> set[int]:
    used = set()
    # Jeśli tabeli Invoice nie ma – po prostu zostaw zbiór pusty
    try:
        cur.execute("SELECT CompanyId FROM Invoice")
        used |= {r[0] for r in cur.fetchall() if r[0] is not None}
        cur.execute("SELECT CustomerId FROM Invoice")
        used |= {r[0] for r in cur.fetchall() if r[0] is not None}
    except sqlite3.OperationalError:
        pass
    return used

def ensure_addresses_exist(cur: sqlite3.Cursor, data: list[tuple]):
    need = set()
    for (_oid, addr, add_addr, *_rest) in data:
        if addr is not None:
            need.add(int(addr))
        if add_addr is not None:
            need.add(int(add_addr))
    existing = get_existing_ids(cur, "Address", "AddressId")
    missing = sorted(need - existing)
    if missing:
        raise RuntimeError(
            "Brakuje rekordów w Address dla ID: "
            + ", ".join(map(str, missing))
            + ". Najpierw zmigruj Address (albo dodaj brakujące wpisy)."
        )

def normalize(data: list[tuple]) -> list[tuple]:
    """Zamienia 'NULL' i puste stringi na None, pilnuje typów liczbowych."""
    out = []
    for row in data:
        row = list(row)
        # OrganizationId, AddressId, AdditionalAddressId jako int/None
        row[0] = int(row[0])
        row[1] = int(row[1]) if row[1] not in (None, "NULL", "",) else None
        row[2] = int(row[2]) if row[2] not in (None, "NULL", "",) else None
        # Reszta: puste/NULL -> None, zostaw tekst
        for i in range(3, len(row)):
            if row[i] in ("", "NULL"):
                row[i] = None
        out.append(tuple(row))
    return out

def main():
    parser = argparse.ArgumentParser(description="Migracja danych do tabeli Organization (UPSERT, bez kasowania).")
    parser.add_argument("--prune", action="store_true",
                        help="Usuń z Organization rekordy nieobecne w danych i NIE używane przez żadną fakturę.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"❌ Nie znaleziono bazy: {DB_PATH.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        # Backup
        backup_table(cur, "Organization", BACKUP_DIR / f"organization_{ts}.csv")
        try:
            backup_table(cur, "Invoice", BACKUP_DIR / f"invoice_{ts}.csv")
        except sqlite3.OperationalError:
            pass
        print(f"💾 Backup zapisany w {BACKUP_DIR}/")

        # Normalizacja danych
        data = normalize(RAW_DATA)

        # Walidacja FK do Address
        ensure_addresses_exist(cur, data)

        conn.execute("BEGIN;")

        # UPSERT
        cur.executemany(SQL_UPSERT, data)
        print(f"✅ Wstawiono/zaktualizowano {len(data)} rekordów Organization.")

        # Opcjonalny prune (usuń tylko nieużywane i nieobecne w danych)
        if args.prune:
            new_ids = {r[0] for r in data}
            existing_ids = get_existing_ids(cur, "Organization", "OrganizationId")
            invoice_ids = get_invoice_org_ids(cur)
            candidates = sorted(existing_ids - new_ids)
            to_delete = [oid for oid in candidates if oid not in invoice_ids]
            if to_delete:
                print(f"⚠️ Do usunięcia {len(to_delete)} organizacji nieobecnych w danych i nieużywanych: {to_delete[:10]}{'...' if len(to_delete)>10 else ''}")
                confirm = input("Potwierdź usunięcie (TAK/NIE): ").strip().upper()
                if confirm == "TAK":
                    cur.executemany("DELETE FROM Organization WHERE OrganizationId = ?;", [(oid,) for oid in to_delete])
                    print(f"🧹 Usunięto {len(to_delete)} rekordów Organization.")
                else:
                    print("⏭️ Pominięto usuwanie.")
            else:
                print("ℹ️ Brak kandydatów do usunięcia (lub wszystkie są używane przez faktury).")

        conn.commit()
        print("🎉 Migracja Organization zakończona powodzeniem.")
    except Exception as e:
        conn.rollback()
        print("❌ Błąd migracji:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
