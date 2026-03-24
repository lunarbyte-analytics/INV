from typing import Optional
import sqlite3
from ..db import tx
from .record_source import RECORD_SOURCE_USER


def create_service(
    unit_id: int,
    tax_id: int,
    name: str,
    unit_price: float,
    version: Optional[str] = None,
    *,
    record_source: str = RECORD_SOURCE_USER,
) -> int:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Service (UnitId, TaxId, Name, UnitPrice, Version, RecordSource) VALUES (?, ?, ?, ?, ?, ?);",
            (unit_id, tax_id, name, float(unit_price), version, record_source),
        )
        return cur.lastrowid


def get_service_all():
    with tx() as conn:
        cur = conn.cursor()
        # join for readable names
        cur.execute(
            """
            SELECT s.ServiceId, s.Name, s.UnitPrice, s.Version, s.RecordSource,
                   u.UnitId, u.Code as UnitCode, u.Name as UnitName,
                   t.TaxId, t.Name as TaxName, t.Value as TaxValue
            FROM Service s
            JOIN Unit u ON u.UnitId = s.UnitId
            JOIN Tax  t ON t.TaxId  = s.TaxId
            ORDER BY s.ServiceId;
            """
        )
        return cur.fetchall()


def get_service_by_id(service_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.ServiceId, s.Name, s.UnitPrice, s.Version, s.RecordSource,
                   u.UnitId, u.Code as UnitCode, u.Name as UnitName,
                   t.TaxId, t.Name as TaxName, t.Value as TaxValue
            FROM Service s
            JOIN Unit u ON u.UnitId = s.UnitId
            JOIN Tax  t ON t.TaxId  = s.TaxId
            WHERE s.ServiceId = ?;
            """,
            (service_id,),
        )
        return cur.fetchone()


def update_service(service_id: int, *, unit_id: Optional[int] = None, tax_id: Optional[int] = None, name: Optional[str] = None, unit_price: Optional[float] = None, version: Optional[str] = None) -> bool:
    sets, params = [], []
    if unit_id is not None:
        sets.append("UnitId = ?"); params.append(unit_id)
    if tax_id is not None:
        sets.append("TaxId = ?"); params.append(tax_id)
    if name is not None:
        sets.append("Name = ?"); params.append(name)
    if unit_price is not None:
        sets.append("UnitPrice = ?"); params.append(float(unit_price))
    if version is not None:
        sets.append("Version = ?"); params.append(version)
    if not sets:
        return False
    params.append(service_id)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE Service SET {', '.join(sets)} WHERE ServiceId = ?;", params)
        return cur.rowcount > 0


def delete_service(service_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Service WHERE ServiceId = ?;", (service_id,))
        return cur.rowcount > 0