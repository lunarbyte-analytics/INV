from typing import Optional
import sqlite3
from ..db import tx
from .record_source import RECORD_SOURCE_USER


def create_address(
    address_type: str,
    street_name: str,
    street_number: str,
    zip_code: str,
    city: str,
    country: str,
    *,
    record_source: str = RECORD_SOURCE_USER,
) -> int:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Address (AddressType, StreetName, StreetNumber, ZipCode, City, Country, RecordSource) VALUES (?, ?, ?, ?, ?, ?, ?);",
            (address_type, street_name, street_number, zip_code, city, country, record_source),
        )
        return cur.lastrowid

def get_address_all():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country, RecordSource FROM Address ORDER BY AddressId;"
        )
        return cur.fetchall()

def get_address_by_id(address_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country, RecordSource FROM Address WHERE AddressId = ?;",
            (address_id,),
        )
        return cur.fetchone()

def update_address(address_id: int, *, address_type: Optional[str] = None, street_name: Optional[str] = None, street_number: Optional[str] = None, zip_code: Optional[str] = None, city: Optional[str] = None, country: Optional[str] = None) -> bool:
    sets, params = [], []
    if address_type is not None:
        sets.append("AddressType = ?"); params.append(address_type)
    if street_name is not None:
        sets.append("StreetName = ?"); params.append(street_name)
    if street_number is not None:
        sets.append("StreetNumber = ?"); params.append(street_number)
    if zip_code is not None:
        sets.append("ZipCode = ?"); params.append(zip_code)
    if city is not None:
        sets.append("City = ?"); params.append(city)
    if country is not None:
        sets.append("Country = ?"); params.append(country)
    if not sets:
        return False
    params.append(address_id)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE Address SET {', '.join(sets)} WHERE AddressId = ?;", params)
        return cur.rowcount > 0

def delete_address(address_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Address WHERE AddressId = ?;", (address_id,))
        return cur.rowcount > 0