import re
from typing import Optional
import sqlite3
from ..db import tx
from .record_source import RECORD_SOURCE_USER


def _nip_norm(s: str | None) -> str:
    return re.sub(r"\D", "", str(s or ""))


def find_organization_id_by_nip_digits(nip_digits: str) -> Optional[int]:
    """Zwraca OrganizationId, jeśli OrgNbr1 ma ten sam NIP (10 cyfr)."""
    nd = _nip_norm(nip_digits)
    if len(nd) != 10:
        return None
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT OrganizationId, OrgNbr1 FROM Organization")
        for r in cur.fetchall():
            if _nip_norm(r["OrgNbr1"]) == nd:
                return int(r["OrganizationId"])
    return None

def create_organization(
    address_id: int,
    additional_address_id: Optional[int],
    name: str,
    phone: str,
    email: str,
    org1: str,
    org2: str,
    org3: str,
    bank: str,
    *,
    record_source: str = RECORD_SOURCE_USER,
) -> int:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO Organization (AddressId, AdditionalAddressId, Name, Phone, Email, OrgNbr1, OrgNbr2, OrgNbr3, BankAccountNbr, RecordSource)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                address_id,
                additional_address_id,
                name,
                phone,
                email,
                org1,
                org2,
                org3,
                bank,
                record_source,
            ),
        )
        return cur.lastrowid

def get_organization_all():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                o.OrganizationId,
                o.Name,
                o.Phone,
                o.Email,
                o.OrgNbr1,
                o.OrgNbr2,
                o.OrgNbr3,
                o.BankAccountNbr,
                o.AddressId,
                o.AdditionalAddressId,
                o.RecordSource,
                a.City   AS AddressCity,
                a.Country AS AddressCountry
            FROM Organization o
            LEFT JOIN Address a ON a.AddressId = o.AddressId
            ORDER BY o.OrganizationId;
            """
        )
        return cur.fetchall()

def get_organization_by_id(org_id: int) -> Optional[sqlite3.Row]:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                o.OrganizationId,
                o.Name,
                o.Phone,
                o.Email,
                o.OrgNbr1,
                o.OrgNbr2,
                o.OrgNbr3,
                o.BankAccountNbr,
                o.AddressId,
                o.AdditionalAddressId,
                o.RecordSource,
                a.City   AS AddressCity,
                a.Country AS AddressCountry
            FROM Organization o
            LEFT JOIN Address a ON a.AddressId = o.AddressId
            WHERE o.OrganizationId = ?;
            """,
            (org_id,),
        )
        return cur.fetchone()

def update_organization(org_id: int, **fields) -> bool:
    sets, params = [], []
    for key, val in fields.items():
        if val is not None:
            sets.append(f"{key} = ?")
            params.append(val)
    if not sets:
        return False
    params.append(org_id)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE Organization SET {', '.join(sets)} WHERE OrganizationId = ?;", params)
        return cur.rowcount > 0

def delete_organization(org_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Organization WHERE OrganizationId = ?;", (org_id,))
        return cur.rowcount > 0
