import sqlite3
from contextlib import contextmanager
from pathlib import Path
import os

DB_PATH = Path("sqllite3_inv.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # enforce foreign keys per connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_conn() -> sqlite3.Connection:
    return _connect()


@contextmanager
def tx():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 👇 WŁĄCZ/ WYŁĄCZ trace przez zmienną środowiskową DEBUG_SQL=1
    if os.getenv("DEBUG_SQL", "1") == "1":
        conn.set_trace_callback(lambda s: print(f"[SQL] {s}"))
    try:
        # (opcjonalnie) pilnuj FK
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with tx() as conn:
        cur = conn.cursor()
        # --- Tax table ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Tax';")
        if not cur.fetchone():
            cur.execute(
                """
                CREATE TABLE Tax (
                    TaxId INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL,
                    Value DECIMAL(18, 2) NOT NULL,
                    DefaultFlag INTEGER NOT NULL CHECK(DefaultFlag IN (0,1))
                );
                """
            )
            cur.executemany(
                "INSERT INTO Tax (TaxId, Name, Value, DefaultFlag) VALUES (?, ?, ?, ?);",
                [(-1, "Brak", 0.00, 0), (1, "VAT23", 23.00, 0), (2, "VAT19", 19.00, 0)],
            )
        # --- Unit table ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Unit';")
        if not cur.fetchone():
            cur.execute(
                """
                CREATE TABLE Unit (
                    UnitId INTEGER PRIMARY KEY AUTOINCREMENT,
                    Code TEXT,
                    Name TEXT,
                    DefaultFlag INTEGER NOT NULL CHECK(DefaultFlag IN (0,1))
                );
                """
            )
            cur.executemany(
                "INSERT INTO Unit (UnitId, Code, Name, DefaultFlag) VALUES (?, ?, ?, ?);",
                [(-1, "", "Brak", 0), (1, "szt", "Sztuka", 0), (2, "kg", "Kilogram", 0)],
            )
        # --- Service table ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Service';")
        if not cur.fetchone():
            cur.execute(
                """
                CREATE TABLE Service (
                    ServiceId INTEGER PRIMARY KEY AUTOINCREMENT,
                    UnitId INTEGER NOT NULL,
                    TaxId INTEGER NOT NULL,
                    Name TEXT,
                    UnitPrice DECIMAL(18,2) NOT NULL,
                    Version TEXT,
                    FOREIGN KEY(UnitId) REFERENCES Unit(UnitId) ON DELETE CASCADE,
                    FOREIGN KEY(TaxId)  REFERENCES Tax(TaxId)   ON DELETE CASCADE
                );
                """
            )
            # optional seed
            cur.executemany(
                "INSERT INTO Service (UnitId, TaxId, Name, UnitPrice, Version) VALUES (?,?,?,?,?);",
                [
                    (1, 1, "Usługa przykładowa A", 100.00, "v1"),
                    (2, 2, "Usługa przykładowa B", 12.50,  "v1"),
                ],
            )
        # --- Address table ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Address';")
        if not cur.fetchone():
            cur.execute(
                """
                CREATE TABLE Address (
                    AddressId INTEGER PRIMARY KEY AUTOINCREMENT,
                    AddressType TEXT,
                    StreetName TEXT,
                    StreetNumber TEXT,
                    ZipCode TEXT,
                    City TEXT,
                    Country TEXT
                );
                """
            )
            # optional seed (możesz usunąć lub zmienić)
            cur.executemany(
                "INSERT INTO Address (AddressType, StreetName, StreetNumber, ZipCode, City, Country) VALUES (?,?,?,?,?,?);",
                [
                    ("Billing", "Długa", "15A", "00-123", "Warszawa", "Polska"),
                    ("Shipping", "Krótka", "7", "30-555", "Kraków", "Polska"),
                ],
            )
        # --- Organization table ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Organization';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE Organization (
                    OrganizationId INTEGER PRIMARY KEY AUTOINCREMENT,
                    AddressId INTEGER NOT NULL,
                    AdditionalAddressId INTEGER NULL,
                    Name TEXT,
                    Phone TEXT,
                    Email TEXT,
                    OrgNbr1 TEXT,
                    OrgNbr2 TEXT,
                    OrgNbr3 TEXT,
                    BankAccountNbr TEXT,
                    FOREIGN KEY(AddressId) REFERENCES Address(AddressId) ON DELETE CASCADE,
                    FOREIGN KEY(AdditionalAddressId) REFERENCES Address(AddressId) ON DELETE SET NULL
                );
            """)
        # --- PaymentMethod lookup ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='PaymentMethod';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE PaymentMethod (
                    PaymentMethodId INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL
                );
            """)
            cur.executemany(
                "INSERT INTO PaymentMethod (PaymentMethodId, Name) VALUES (?, ?);",
                [(1, "Przelew 14 dni"), (2, "Gotówka"), (3, "Karta")]
            )

        # --- Status lookup ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Status';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE Status (
                    StatusId INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL
                );
            """)
            cur.executemany(
                "INSERT INTO Status (StatusId, Name) VALUES (?, ?);",
                [(1, "Szkic"), (2, "Wystawiona"), (3, "Opłacona"), (4, "Storno")]
            )

        # --- InvoiceType lookup ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='InvoiceType';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE InvoiceType (
                    TypeId INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL
                );
            """)
            cur.executemany(
                "INSERT INTO InvoiceType (TypeId, Name) VALUES (?, ?);",
                [(1, "Faktura VAT"), (2, "Faktura pro forma"), (3, "Korekta")]
            )

        # --- Organization table (jeśli jeszcze nie dodałeś) ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Organization';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE Organization (
                    OrganizationId INTEGER PRIMARY KEY AUTOINCREMENT,
                    AddressId INTEGER NOT NULL,
                    AdditionalAddressId INTEGER NULL,
                    Name TEXT,
                    Phone TEXT,
                    Email TEXT,
                    OrgNbr1 TEXT,
                    OrgNbr2 TEXT,
                    OrgNbr3 TEXT,
                    BankAccountNbr TEXT,
                    FOREIGN KEY(AddressId) REFERENCES Address(AddressId) ON DELETE CASCADE,
                    FOREIGN KEY(AdditionalAddressId) REFERENCES Address(AddressId) ON DELETE SET NULL
                );
            """)

        # --- Invoice header ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Invoice';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE Invoice (
                    InvoiceId INTEGER PRIMARY KEY AUTOINCREMENT,
                    CompanyId INTEGER NOT NULL,
                    CustomerId INTEGER NOT NULL,
                    PaymentMethodId INTEGER NOT NULL,
                    StatusId INTEGER NOT NULL,
                    TypeId INTEGER NOT NULL,
                    IsAdditionalAddress INTEGER NOT NULL CHECK(IsAdditionalAddress IN (0,1)),
                    Name TEXT,
                    CreateDate TEXT NOT NULL,  -- YYYY-MM-DD
                    SalesDate  TEXT NOT NULL,  -- YYYY-MM-DD
                    PaymentDate TEXT NOT NULL, -- YYYY-MM-DD
                    Created TEXT NOT NULL,     -- ISO datetime
                    Updated TEXT NOT NULL,     -- ISO datetime
                    FOREIGN KEY(CompanyId) REFERENCES Organization(OrganizationId),
                    FOREIGN KEY(CustomerId) REFERENCES Organization(OrganizationId),
                    FOREIGN KEY(PaymentMethodId) REFERENCES PaymentMethod(PaymentMethodId),
                    FOREIGN KEY(StatusId) REFERENCES Status(StatusId),
                    FOREIGN KEY(TypeId) REFERENCES InvoiceType(TypeId)
                );
            """)

        # --- Invoice details ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='InvoiceDetail';")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE InvoiceDetail (
                    InvoiceDetailId INTEGER PRIMARY KEY AUTOINCREMENT,
                    InvoiceId INTEGER NOT NULL,
                    ServiceId INTEGER NOT NULL,
                    Quantity DECIMAL(18,2) NOT NULL,
                    Created TEXT NOT NULL,
                    Updated TEXT NOT NULL,
                    FOREIGN KEY(InvoiceId) REFERENCES Invoice(InvoiceId) ON DELETE CASCADE,
                    FOREIGN KEY(ServiceId) REFERENCES Service(ServiceId)
                );
            """)
