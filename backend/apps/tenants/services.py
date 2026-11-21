"""Tenant services."""

from apps.accounting.services import (
    clone_master_sat_catalog as clone_master_sat_catalog_from_accounting,
)


def clone_master_sat_catalog(company):
    """Populate the company chart of accounts from the SAT master catalog.

    Kept as a thin wrapper so the company creation flow (and its tests) can
    import the hook from the tenants app while the implementation lives in
    ``apps.accounting.services``.
    """
    return clone_master_sat_catalog_from_accounting(company)
