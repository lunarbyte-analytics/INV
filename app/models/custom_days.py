# app/models/custom_days.py
from typing import List, Tuple
from datetime import datetime, date
import sqlite3
from ..db import tx  # identycznie jak w models/invoice.py

ISO_DATE = "%Y-%m-%d"

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _mk_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"

def ensure_table() -> None:
    """
    Tworzy tabelę na własne dni wolne.
    Przechowujemy datę w formacie ISO jako PRIMARY KEY (unikalność 1 dzień = 1 rekord).
    """
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS CustomFreeDay (
                DayDate TEXT PRIMARY KEY,      -- 'YYYY-MM-DD'
                Name    TEXT NOT NULL,         -- np. 'Własny dzień wolny'
                Created TEXT NOT NULL,
                Updated TEXT NOT NULL
            );
        """)
        # Opcjonalnie: indeks po roku-miesiącu przy zapytaniach po zakresie
        cur.execute("CREATE INDEX IF NOT EXISTS idx_CustomFreeDay_month ON CustomFreeDay(substr(DayDate,1,7));")

def add_or_update_day(year: int, month: int, day: int, name: str = "Własny dzień wolny") -> None:
    """
    Dodaje lub aktualizuje wpis dla wskazanego dnia.
    """
    ds = _mk_date(year, month, day)
    now = _now_iso()
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO CustomFreeDay (DayDate, Name, Created, Updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(DayDate) DO UPDATE SET
                Name = excluded.Name,
                Updated = excluded.Updated;
        """, (ds, name, now, now))

def delete_day(year: int, month: int, day: int) -> bool:
    """
    Usuwa wpis dla wskazanego dnia. Zwraca True, jeśli coś usunięto.
    """
    ds = _mk_date(year, month, day)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM CustomFreeDay WHERE DayDate = ?;", (ds,))
        return cur.rowcount > 0

def list_for_month(year: int, month: int):
    """
    Zwraca listę rekordów z bieżącego miesiąca.
    Zwraca wiersze (sqlite3.Row) zawierające co najmniej: DayDate, Name.
    """
    # wyznacz zakres miesiąca
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    d_from = _mk_date(year, month, 1)
    d_to   = _mk_date(year, month, last_day)
    with tx() as conn:
        # jeżeli tx() ustawia row_factory=sqlite3.Row, zwrócimy Row-y;
        # jeśli nie, i tak CalendarWindow poradzi sobie z tuple/dict.
        cur = conn.cursor()
        cur.execute("""
            SELECT DayDate, Name
            FROM CustomFreeDay
            WHERE DayDate BETWEEN ? AND ?
            ORDER BY DayDate;
        """, (d_from, d_to))
        return cur.fetchall()

# (opcjonalnie) pomocnicze API
def list_all() -> list:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DayDate, Name FROM CustomFreeDay ORDER BY DayDate;")
        return cur.fetchall()
