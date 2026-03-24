# ------------------------------ app/models/__init__.py ------------------------------

from .record_source import (
    RECORD_SOURCE_KSEF_IMPORT,
    RECORD_SOURCE_USER,
    record_source_label_pl,
)

# --- TAX ---
from .tax import (
    create_tax,
    get_tax_all,
    get_tax_by_id,
    get_or_create_tax_by_rate,
    update_tax,
    delete_tax,
    set_default_tax,
)

# --- UNIT ---
from .unit import (
    create_unit,
    get_unit_all,
    get_unit_by_id,
    update_unit,
    delete_unit,
    set_default_unit,
)

# --- SERVICE ---
from .service import (
    create_service,
    get_service_all,
    get_service_by_id,
    update_service,
    delete_service,
)

# --- ADDRESS ---
from .address import (
    create_address,
    get_address_all,
    get_address_by_id,
    update_address,
    delete_address,
)

# --- ORGANIZATION ---
from .organization import (
    create_organization,
    get_organization_all,
    get_organization_by_id,
    update_organization,
    delete_organization,
)

# --- INVOICE (header + details) ---
from .invoice import (
    create_invoice,
    update_invoice,
    delete_invoice,
    get_invoice_list,
    get_invoice_full,
    record_ksef_submission,
    get_ksef_submissions_for_invoice,
    add_detail,
    update_detail,
    delete_detail,
    # lookups
    get_payment_methods,
    get_statuses,
    get_invoice_types,
    get_organizations,
    get_services,
)

__all__ = [
    "RECORD_SOURCE_USER",
    "RECORD_SOURCE_KSEF_IMPORT",
    "record_source_label_pl",
    # TAX
    "create_tax",
    "get_tax_all",
    "get_tax_by_id",
    "get_or_create_tax_by_rate",
    "update_tax",
    "delete_tax",
    "set_default_tax",

    # UNIT
    "create_unit",
    "get_unit_all",
    "get_unit_by_id",
    "update_unit",
    "delete_unit",
    "set_default_unit",

    # SERVICE
    "create_service",
    "get_service_all",
    "get_service_by_id",
    "update_service",
    "delete_service",

    # ADDRESS
    "create_address",
    "get_address_all",
    "get_address_by_id",
    "update_address",
    "delete_address",

    # ORGANIZATION
    "create_organization",
    "get_organization_all",
    "get_organization_by_id",
    "update_organization",
    "delete_organization",

    # INVOICE (header + details)
    "create_invoice",
    "update_invoice",
    "delete_invoice",
    "get_invoice_list",
    "get_invoice_full",
    "record_ksef_submission",
    "get_ksef_submissions_for_invoice",
    "add_detail",
    "update_detail",
    "delete_detail",
    "get_payment_methods",
    "get_statuses",
    "get_invoice_types",
    "get_organizations",
    "get_services",
]
