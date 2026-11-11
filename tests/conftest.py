"""Shared test fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from labra.app import create_app
from labra.crm import FakeCrm


@pytest.fixture
def crm() -> FakeCrm:
    return FakeCrm()


@pytest.fixture
def client(crm, tmp_path) -> TestClient:
    """A TestClient backed by a fresh file-based SQLite db per test."""
    db_path = str(tmp_path / "labra_test.db")
    app = create_app(crm, db_path=db_path)
    return TestClient(app)


NORTHWIND_BODY = {
    "template_id": "northwind-default",
    "name": "Northwind Default",
    "crm_type": "salesforce",
    "mappings": [
        {"labra_field": "company_name", "crm_object": "Account", "crm_field": "Name"},
        {"labra_field": "website", "crm_object": "Account", "crm_field": "Website"},
        {"labra_field": "country", "crm_object": "Account", "crm_field": "BillingCountry"},
        {"labra_field": "expected_monthly_revenue", "crm_object": "Opportunity", "crm_field": "Amount"},
        {"labra_field": "target_close_date", "crm_object": "Opportunity", "crm_field": "CloseDate"},
        {"labra_field": "primary_sales_rep_email", "crm_object": "Contact", "crm_field": "Email"},
    ],
}

CONTOSO_BODY = {
    "template_id": "contoso-default",
    "name": "Contoso Default",
    "crm_type": "hubspot",
    "mappings": [
        {"labra_field": "company_name", "crm_object": "companies", "crm_field": "name"},
        {"labra_field": "website", "crm_object": "companies", "crm_field": "website"},
        {"labra_field": "country", "crm_object": "companies", "crm_field": "country"},
        {"labra_field": "expected_monthly_revenue", "crm_object": "deals", "crm_field": "amount"},
        {"labra_field": "target_close_date", "crm_object": "deals", "crm_field": "closedate"},
        {"labra_field": "primary_sales_rep_email", "crm_object": "contacts", "crm_field": "email"},
    ],
}


@pytest.fixture
def northwind(client) -> TestClient:
    """Create the Northwind template and return the same client."""
    r = client.post("/mapping-templates", json=NORTHWIND_BODY)
    assert r.status_code == 201, r.text
    return client
