"""Runnable server for manual exploration (uvicorn labra.main:app).

There is no real CRM in this exercise, so this wires a FakeCrm pre-seeded with
Northwind's opp-100 record. That lets the README's curl walkthrough reach
crm-field-values end to end. Tests do NOT use this module; they build and seed
their own FakeCrm via create_app(crm).
"""
from __future__ import annotations

from labra.app import create_app
from labra.crm import FakeCrm


def _demo_crm() -> FakeCrm:
    crm = FakeCrm()
    crm.seed("Account", "opp-100", {
        "Name": "Northwind Traders",
        "Website": "https://northwind.example",
        "BillingCountry": "United States",
        "InternalNotes": "do not copy me",
    })
    crm.seed("Opportunity", "opp-100", {"Amount": 5000, "CloseDate": "2027-12-01"})
    crm.seed("Contact", "opp-100", {"Email": "ada@northwind.example"})
    return crm


app = create_app(_demo_crm(), db_path="labra.db")
