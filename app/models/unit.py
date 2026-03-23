from typing import Optional
import sqlite3
from ..db import tx


def create_unit(code: str, name: str, default_flag: int = 0) -> int:
    if default_flag not in (0, 1):
        raise ValueError("default_flag musi być 0 lub 1")
    with tx() as conn:
        cur = conn.cursor()
        if default_flag == 1:
            cur.execute("UPDATE Unit SET DefaultFlag = 0;")
        cur.execute(
            "INSERT INTO Unit (Code, Name, DefaultFlag) VALUES (?, ?, ?);",
            (code, name, default_flag),
        )
        return cur.lastrowid


def get_unit_all():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT UnitId, Code, Name, DefaultFlag FROM Unit ORDER BY UnitId;")
        return cur.fetchall()


def get_unit_by_id(unit_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT UnitId, Code, Name, DefaultFlag FROM Unit WHERE UnitId = ?;", (unit_id,))
        return cur.fetchone()


def update_unit(unit_id: int, code: Optional[str] = None, name: Optional[str] = None, default_flag: Optional[int] = None) -> bool:
    sets, params = [], []
    if code is not None:
        sets.append("Code = ?"); params.append(code)
    if name is not None:
        sets.append("Name = ?"); params.append(name)
    if default_flag is not None:
        if default_flag not in (0, 1):
            raise ValueError("default_flag musi być 0 lub 1")
    if not sets and default_flag is None:
        return False

    with tx() as conn:
        cur = conn.cursor()
        if default_flag is not None:
            if default_flag == 1:
                cur.execute("UPDATE Unit SET DefaultFlag = 0 WHERE UnitId <> ?;", (unit_id,))
            sets.append("DefaultFlag = ?"); params.append(default_flag)
        params.append(unit_id)
        cur.execute(f"UPDATE Unit SET {', '.join(sets)} WHERE UnitId = ?;", params)
        return cur.rowcount > 0


def delete_unit(unit_id: int) -> bool:
    if unit_id == -1:
        raise ValueError("Nie można usunąć wiersza specjalnego UnitId = -1.")
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Unit WHERE UnitId = ?;", (unit_id,))
        return cur.rowcount > 0


def set_default_unit(unit_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM Unit WHERE UnitId = ?;", (unit_id,))
        if not cur.fetchone():
            return False
        cur.execute("UPDATE Unit SET DefaultFlag = 0;")
        cur.execute("UPDATE Unit SET DefaultFlag = 1 WHERE UnitId = ?;", (unit_id,))
        return True