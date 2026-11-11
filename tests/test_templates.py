"""Template create + GET, and the create reject rules."""
from __future__ import annotations

from tests.conftest import NORTHWIND_BODY


def _field(view: dict, name: str) -> dict:
    return next(f for f in view["fields"] if f["labra_field"] == name)


def test_create_and_get_northwind(northwind):
    r = northwind.get("/mapping-templates/northwind-default")
    assert r.status_code == 200
    view = r.json()
    assert len(view["fields"]) == 6

    cn = _field(view, "company_name")
    assert cn["crm_object"] == "Account"
    assert cn["crm_field"] == "Name"
    assert cn["mapped"] is True
    assert cn["required"] is True

    rev = _field(view, "expected_monthly_revenue")
    assert (rev["crm_object"], rev["crm_field"]) == ("Opportunity", "Amount")


def test_get_unknown_template_404(client):
    r = client.get("/mapping-templates/does-not-exist")
    assert r.status_code == 404


def _errors_for(client, body):
    r = client.post("/mapping-templates", json=body)
    assert r.status_code == 422, r.text
    return r.json()["errors"]


def test_reject_blank_name(client):
    body = {**NORTHWIND_BODY, "template_id": "t1", "name": "   "}
    errs = _errors_for(client, body)
    assert any(e["field"] == "name" for e in errs)


def test_reject_bad_crm_type(client):
    body = {**NORTHWIND_BODY, "template_id": "t2", "crm_type": "pipedrive"}
    errs = _errors_for(client, body)
    assert any(e["field"] == "crm_type" for e in errs)


def test_reject_unknown_labra_field(client):
    body = {
        **NORTHWIND_BODY, "template_id": "t3",
        "mappings": NORTHWIND_BODY["mappings"] + [
            {"labra_field": "made_up", "crm_object": "Account", "crm_field": "Foo"}
        ],
    }
    errs = _errors_for(client, body)
    assert any("made_up" in (e.get("message") or "") for e in errs)


def test_reject_duplicate_labra_field(client):
    body = {
        **NORTHWIND_BODY, "template_id": "t4",
        "mappings": NORTHWIND_BODY["mappings"] + [
            {"labra_field": "company_name", "crm_object": "Account", "crm_field": "LegalName"}
        ],
    }
    errs = _errors_for(client, body)
    assert any("more than once" in (e.get("message") or "") for e in errs)


def test_reject_duplicate_crm_value(client):
    mappings = [dict(m) for m in NORTHWIND_BODY["mappings"]]
    # Point website at the same CRM value as company_name.
    mappings[1] = {"labra_field": "website", "crm_object": "Account", "crm_field": "Name"}
    body = {**NORTHWIND_BODY, "template_id": "t5", "mappings": mappings}
    errs = _errors_for(client, body)
    assert any("more than one Labra field" in (e.get("message") or "") for e in errs)


def test_reject_blank_crm_on_used_mapping(client):
    mappings = [dict(m) for m in NORTHWIND_BODY["mappings"]]
    mappings[0] = {"labra_field": "company_name", "crm_object": "", "crm_field": ""}
    body = {**NORTHWIND_BODY, "template_id": "t6", "mappings": mappings}
    errs = _errors_for(client, body)
    assert any(e["field"] == "company_name" for e in errs)


def test_reject_required_field_unmapped(client):
    mappings = [m for m in NORTHWIND_BODY["mappings"] if m["labra_field"] != "country"]
    body = {**NORTHWIND_BODY, "template_id": "t7", "mappings": mappings}
    errs = _errors_for(client, body)
    assert any(e["field"] == "country" for e in errs)


def test_nothing_stored_on_reject(client):
    body = {**NORTHWIND_BODY, "template_id": "t8", "name": ""}
    client.post("/mapping-templates", json=body)
    r = client.get("/mapping-templates/t8")
    assert r.status_code == 404
