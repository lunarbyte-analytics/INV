from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
import sqlite3
from ..app_env import get_context_organization_id
from ..db import tx

ISO_DATE = "%Y-%m-%d"

def _exec(cur, sql: str, params=None):
    print("[SQL]", " ".join(sql.split()))
    if params is not None and len(params) > 0:
        print("[BIND]", params)
        cur.execute(sql, params)
    else:
        cur.execute(sql)

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _date_str(d: Optional[date] = None) -> str:
    return (d or date.today()).strftime(ISO_DATE)

# --- Lookups (do comboboxów w GUI) ---
def get_payment_methods():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT PaymentMethodId, Name FROM PaymentMethod ORDER BY PaymentMethodId;")
        return cur.fetchall()

def get_statuses():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT StatusId, Name FROM Status ORDER BY StatusId;")
        return cur.fetchall()

def get_invoice_types():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT TypeId, Name FROM InvoiceType ORDER BY TypeId;")
        return cur.fetchall()

def get_organizations():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT OrganizationId, Name FROM Organization ORDER BY OrganizationId;")
        return cur.fetchall()

def get_services():
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.ServiceId, s.Name, s.UnitPrice, u.Code AS UnitCode, t.Value AS TaxValue
            FROM Service s
            JOIN Unit u ON u.UnitId = s.UnitId
            JOIN Tax  t ON t.TaxId  = s.TaxId
            ORDER BY s.ServiceId;
        """)
        return cur.fetchall()

# --- Invoice header ---
def create_invoice(*, company_id: int, customer_id: int, payment_method_id: int,
                   status_id: int, type_id: int, is_additional_address: int,
                   name: Optional[str], create_date: Optional[str] = None,
                   sales_date: Optional[str] = None, payment_date: Optional[str] = None) -> int:
    now = _now_iso()
    cd = create_date or _date_str()
    sd = sales_date or cd
    pd = payment_date or cd
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Invoice (CompanyId, CustomerId, PaymentMethodId, StatusId, TypeId, IsAdditionalAddress,
                                 Name, CreateDate, SalesDate, PaymentDate, Created, Updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (company_id, customer_id, payment_method_id, status_id, type_id, int(is_additional_address),
              name, cd, sd, pd, now, now))
        return cur.lastrowid

def update_invoice(invoice_id: int, **fields) -> bool:
    if not fields:
        return False
    sets, params = [], []
    for k, v in fields.items():
        sets.append(f"{k} = ?"); params.append(v)
    sets.append("Updated = ?"); params.append(_now_iso())
    params.append(invoice_id)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE Invoice SET {', '.join(sets)} WHERE InvoiceId = ?;", params)
        return cur.rowcount > 0

def find_invoice_by_party_and_name(company_id: int, customer_id: int, name: str) -> Optional[int]:
    """Unikalność wg sprzedawca + nabywca + numer faktury (pole Name)."""
    n = (name or "").strip()
    if not n:
        return None
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT InvoiceId FROM Invoice
            WHERE CompanyId = ? AND CustomerId = ? AND Name = ?
            LIMIT 1;
            """,
            (company_id, customer_id, n),
        )
        row = cur.fetchone()
        return int(row["InvoiceId"]) if row else None


def delete_invoice(invoice_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM Invoice WHERE InvoiceId = ?;", (invoice_id,))
        return cur.rowcount > 0


def invoice_has_ksef_submission(invoice_id: int) -> bool:
    """Czy w bazie jest zapis wysyłki do KSeF (nasza aplikacja zapisała numer referencyjny)."""
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM InvoiceKsefSubmission WHERE InvoiceId = ? LIMIT 1;",
            (invoice_id,),
        )
        return cur.fetchone() is not None


def invoice_can_be_deleted(
    invoice_id: int,
    company_id: int,
    customer_id: int,
) -> Tuple[bool, str]:
    """
    Reguły usuwania: faktura zakupowa — zawsze; sprzedażowa — tylko gdy nie było wysyłki do KSeF
    (brak wiersza w InvoiceKsefSubmission). Typ (sprzedaż/zakup) wg kontekstu „Moja firma”.
    """
    ctx = get_context_organization_id()
    role = invoice_flow_role(company_id, customer_id, ctx)
    has_ksef = invoice_has_ksef_submission(invoice_id)

    if role == "Zakup":
        return True, ""

    if role == "Sprzedaż":
        if not has_ksef:
            return True, ""
        return (
            False,
            "Nie można usunąć: faktura sprzedażowa została wysłana do KSeF.",
        )

    if role == "Sprzedaż i zakup":
        if not has_ksef:
            return True, ""
        return (
            False,
            "Nie można usunąć: faktura ma zapis wysyłki do KSeF (sprzedaż).",
        )

    # Brak kontekstu („—”) lub „Poza kontekstem” — nie rozróżniamy sprzedaży i zakupu.
    if not has_ksef:
        return True, ""
    return (
        False,
        "Nie można usunąć: faktura ma zapis wysyłki do KSeF. "
        "Ustaw „Moją firmę” w kontekście na liście faktur, aby stosować reguły sprzedaż/zakup.",
    )


def invoice_flow_role(company_id: int, customer_id: int, context_org_id: Optional[int]) -> str:
    """
    Względem wybranej „mojej firmy”: sprzedaż = wystawiamy, zakup = jesteśmy nabywcą.
    """
    if context_org_id is None:
        return "—"
    if company_id == context_org_id and customer_id == context_org_id:
        return "Sprzedaż i zakup"
    if company_id == context_org_id:
        return "Sprzedaż"
    if customer_id == context_org_id:
        return "Zakup"
    return "Poza kontekstem"


def get_invoice_list(
    *,
    context_org_id: Optional[int] = None,
    flow_filter: Optional[str] = None,
):
    """
    flow_filter: None / 'all' — wszystkie; 'sales' — tylko sprzedaż (CompanyId = kontekst);
    'purchase' — tylko zakup (CustomerId = kontekst). Wymaga ustawionego context_org_id.
    """
    where_extra: list[str] = []
    params: list[Any] = []
    if flow_filter == "sales" and context_org_id is not None:
        where_extra.append("i.CompanyId = ?")
        params.append(context_org_id)
    elif flow_filter == "purchase" and context_org_id is not None:
        where_extra.append("i.CustomerId = ?")
        params.append(context_org_id)

    where_sql = ""
    if where_extra:
        where_sql = " AND " + " AND ".join(where_extra)

    with tx() as conn:
        cur = conn.cursor()
        sql = f"""
            SELECT
                i.InvoiceId,
                i.Name,
                i.CreateDate,
                s.Name AS StatusName,
                c.OrganizationId  AS CustomerId,
                co.OrganizationId AS CompanyId,
                COALESCE(NULLIF(TRIM(c.Name), ''),  'Org ' || c.OrganizationId)  AS CustomerName,
                COALESCE(NULLIF(TRIM(co.Name), ''), 'Org ' || co.OrganizationId) AS CompanyName,
                (
                    SELECT k.ReferenceNumber
                    FROM InvoiceKsefSubmission k
                    WHERE k.InvoiceId = i.InvoiceId
                    ORDER BY k.SentAt DESC, k.InvoiceKsefSubmissionId DESC
                    LIMIT 1
                ) AS KsefReferenceNumber,
                (
                    SELECT k.SentAt
                    FROM InvoiceKsefSubmission k
                    WHERE k.InvoiceId = i.InvoiceId
                    ORDER BY k.SentAt DESC, k.InvoiceKsefSubmissionId DESC
                    LIMIT 1
                ) AS KsefSentAt
            FROM Invoice i
            LEFT JOIN Status s        ON s.StatusId        = i.StatusId
            LEFT JOIN Organization c  ON c.OrganizationId  = i.CustomerId
            LEFT JOIN Organization co ON co.OrganizationId = i.CompanyId
            WHERE 1=1
            {where_sql}
            ORDER BY i.InvoiceId DESC;
        """
        print("[DEBUG] get_invoice_list()")
        cur.execute(sql, params)
        rows = cur.fetchall()
    out: list[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["FlowRole"] = invoice_flow_role(
            int(d["CompanyId"]), int(d["CustomerId"]), context_org_id
        )
        out.append(d)
    return out


def get_invoice_full(invoice_id: int):
    with tx() as conn:
        cur = conn.cursor()

        sql_header = """
            SELECT i.*,
                   pm.Name AS PaymentName,
                   st.Name  AS StatusName,
                   it.Name  AS TypeName,

                   -- nazwy org
                   co.Name AS CompanyName,
                   cu.Name AS CustomerName,

                   -- adres SPRZEDAWCY (Organization.AddressId)
                   co_addr.StreetName   AS CoStreet,
                   co_addr.StreetNumber AS CoStreetNo,
                   co_addr.ZipCode      AS CoZip,
                   co_addr.City         AS CoCity,
                   co_addr.Country      AS CoCountry,
                   co.OrgNbr1           AS CoNIP,

                   -- adres NABYWCY (AddressId lub AdditionalAddressId wg IsAdditionalAddress)
                   cu_addr.StreetName   AS CuStreet,
                   cu_addr.StreetNumber AS CuStreetNo,
                   cu_addr.ZipCode      AS CuZip,
                   cu_addr.City         AS CuCity,
                   cu_addr.Country      AS CuCountry,
                   cu.OrgNbr1           AS CuNIP

            FROM Invoice i
            JOIN PaymentMethod pm ON pm.PaymentMethodId = i.PaymentMethodId
            JOIN Status        st ON st.StatusId        = i.StatusId
            JOIN InvoiceType   it ON it.TypeId          = i.TypeId

            JOIN Organization co  ON co.OrganizationId  = i.CompanyId
            LEFT JOIN Address  co_addr ON co_addr.AddressId = co.AddressId

            JOIN Organization cu  ON cu.OrganizationId  = i.CustomerId
            LEFT JOIN Address  cu_addr
                   ON cu_addr.AddressId = CASE
                        WHEN i.IsAdditionalAddress = 1 AND cu.AdditionalAddressId IS NOT NULL
                             THEN cu.AdditionalAddressId
                        ELSE cu.AddressId
                   END

            WHERE i.InvoiceId = ?;
        """
        _exec(cur, sql_header, (invoice_id,))
        header_row = cur.fetchone()
        if header_row is None:
            return None, []

        # (opcjonalnie) konwersja na dict, jeśli używasz .get() później:
        header = dict(header_row)

        sql_details = """
            SELECT d.InvoiceDetailId, d.Quantity,
                   s.ServiceId, s.Name AS ServiceName,
                   s.UnitPrice, u.Code AS UnitCode, t.Value AS TaxValue
            FROM InvoiceDetail d
            JOIN Service s ON s.ServiceId = d.ServiceId
            JOIN Unit    u ON u.UnitId    = s.UnitId
            JOIN Tax     t ON t.TaxId     = s.TaxId
            WHERE d.InvoiceId = ?
            ORDER BY d.InvoiceDetailId;
        """
        _exec(cur, sql_details, (invoice_id,))
        details = [dict(r) for r in cur.fetchall()]

        return header, details

# --- Invoice details ---
def add_detail(invoice_id: int, service_id: int, quantity: float) -> int:
    now = _now_iso()
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO InvoiceDetail (InvoiceId, ServiceId, Quantity, Created, Updated)
            VALUES (?, ?, ?, ?, ?);
        """, (invoice_id, service_id, float(quantity), now, now))
        return cur.lastrowid

def update_detail(detail_id: int, *, service_id: Optional[int] = None, quantity: Optional[float] = None) -> bool:
    sets, params = [], []
    if service_id is not None:
        sets.append("ServiceId = ?"); params.append(service_id)
    if quantity is not None:
        sets.append("Quantity = ?"); params.append(float(quantity))
    if not sets:
        return False
    sets.append("Updated = ?"); params.append(_now_iso())
    params.append(detail_id)
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE InvoiceDetail SET {', '.join(sets)} WHERE InvoiceDetailId = ?;", params)
        return cur.rowcount > 0

def delete_detail(detail_id: int) -> bool:
    with tx() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM InvoiceDetail WHERE InvoiceDetailId = ?;", (detail_id,))
        return cur.rowcount > 0


# --- KSeF (zapis wysyłek) ---

def record_ksef_submission(
    invoice_id: int,
    reference_number: str,
    *,
    sent_at_iso: str | None = None,
) -> int:
    """Zapis udanej wysyłki do KSeF (numer referencyjny dokumentu z API)."""
    ref = (reference_number or "").strip()
    if not ref:
        raise ValueError("reference_number nie może być pusty.")
    when = sent_at_iso or _now_iso()
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO InvoiceKsefSubmission (InvoiceId, ReferenceNumber, SentAt)
            VALUES (?, ?, ?);
            """,
            (invoice_id, ref, when),
        )
        return int(cur.lastrowid)


def get_ksef_submissions_for_invoice(invoice_id: int) -> List[Dict[str, Any]]:
    """Wszystkie zapisane wysyłki KSeF dla faktury (od najnowszej)."""
    with tx() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT InvoiceKsefSubmissionId, InvoiceId, ReferenceNumber, SentAt
            FROM InvoiceKsefSubmission
            WHERE InvoiceId = ?
            ORDER BY SentAt DESC, InvoiceKsefSubmissionId DESC;
            """,
            (invoice_id,),
        )
        return [dict(r) for r in cur.fetchall()]
