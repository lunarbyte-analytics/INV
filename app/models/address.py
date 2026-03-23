from typing import Optional
import sqlite3
from ..db import tx

def create_address(address_type: str, street_name: str, street_number: str, zip_code: str, city: str, country: str) -> int:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Address (AddressType, StreetName, StreetNumber, ZipCode, City, Country) VALUES (?, ?, ?, ?, ?, ?);",
            (address_type, street_name, street_number, zip_code, city, country),
        )
        return cur.lastrowid

def get_address_all():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country FROM Address ORDER BY AddressId;")
        return cur.fetchall()

def get_address_by_id(address_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT AddressId, AddressType, StreetName, StreetNumber, ZipCode, City, Country FROM Address WHERE AddressId = ?;", (address_id,))
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