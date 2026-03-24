from typing import Optional
import sqlite3
from ..db import tx


def create_tax(name: str, value: float, default_flag: int = 0) -> int:
    if default_flag not in (0, 1):
        raise ValueError("default_flag musi być 0 lub 1")
    with tx() as conn:
        cur = conn.cursor()
        if default_flag == 1:
            cur.execute("UPDATE Tax SET DefaultFlag = 0;")
        cur.execute(
            "INSERT INTO Tax (Name, Value, DefaultFlag) VALUES (?, ?, ?);",
            (name, float(value), default_flag),
        )
        return cur.lastrowid


def get_tax_all():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT TaxId, Name, Value, DefaultFlag FROM Tax ORDER BY TaxId;")
        return cur.fetchall()


def find_tax_id_by_value(rate: float) -> Optional[int]:
    """Pierwszy TaxId o danej stawce (np. 23.0)."""
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT TaxId FROM Tax WHERE ABS(Value - ?) < 0.001 ORDER BY TaxId LIMIT 1;",
            (float(rate),),
        )
        row = cur.fetchone()
        return int(row["TaxId"]) if row else None


def get_or_create_tax_by_rate(rate: float) -> int:
    """Gwarantuje istnienie stawki w słowniku Tax (np. import FA z nietypową stawką)."""
    tid = find_tax_id_by_value(rate)
    if tid is not None:
        return tid
    label = f"VAT {float(rate):g}%"
    return create_tax(label, float(rate), 0)


def get_tax_by_id(tax_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT TaxId, Name, Value, DefaultFlag FROM Tax WHERE TaxId = ?;", (tax_id,))
        return cur.fetchone()


def update_tax(tax_id: int, name: Optional[str] = None, value: Optional[float] = None, default_flag: Optional[int] = None) -> bool:
    sets, params = [], []
    if name is not None:
        sets.append("Name = ?"); params.append(name)
    if value is not None:
        sets.append("Value = ?"); params.append(float(value))
    if default_flag is not None:
        if default_flag not in (0, 1):
            raise ValueError("default_flag musi być 0 lub 1")
    if not sets and default_flag is None:
        return False

    with tx() as conn:
        cur = conn.cursor()
        if default_flag is not None:
            if default_flag == 1:
                cur.execute("UPDATE Tax SET DefaultFlag = 0 WHERE TaxId <> ?;", (tax_id,))
            sets.append("DefaultFlag = ?"); params.append(default_flag)
        params.append(tax_id)
        cur.execute(f"UPDATE Tax SET {', '.join(sets)} WHERE TaxId = ?;", params)
        return cur.rowcount > 0


def delete_tax(tax_id: int) -> bool:
    if tax_id == -1:
        raise ValueError("Nie można usunąć wiersza specjalnego TaxId = -1.")
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Tax WHERE TaxId = ?;", (tax_id,))
        return cur.rowcount > 0


def set_default_tax(tax_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM Tax WHERE TaxId = ?;", (tax_id,))
        if not cur.fetchone():
            return False
        cur.execute("UPDATE Tax SET DefaultFlag = 0;")
        cur.execute("UPDATE Tax SET DefaultFlag = 1 WHERE TaxId = ?;", (tax_id,))
        return True