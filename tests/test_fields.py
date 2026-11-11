"""Introducing a later field, and the unused-field behavior."""
from __future__ import annotations


def _field(view: dict, name: str):
    return next((f for f in view["fields"] if f["labra_field"] == name), None)


def test_new_field_appears_on_old_template(northwind):
    # Snapshot the raw mapping rows before introducing the field.
    conn = northwind.app.state.conn
    before = conn.execute(
        "SELECT * FROM mappings WHERE template_id = 'northwind-default'"
    ).fetchall()

    r = northwind.post("/labra-fields", json={
        "labra_field": "customer_duns", "label": "Customer DUNS", "required": False,
    })
    assert r.status_code == 200

    view = northwind.get("/mapping-templates/northwind-default").json()

    duns = _field(view, "customer_duns")
    assert duns is not None
    assert duns["mapped"] is False
    assert duns["crm_object"] is None and duns["crm_field"] is None

    cn = _field(view, "company_name")
    assert (cn["crm_object"], cn["crm_field"]) == ("Account", "Name")

    # No second write of Northwind's mappings: rows are byte-for-byte the same.
    after = conn.execute(
        "SELECT * FROM mappings WHERE template_id = 'northwind-default'"
    ).fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]


def test_reintroduce_updates_label_keeps_mappings(northwind):
    northwind.post("/labra-fields", json={
        "labra_field": "customer_duns", "label": "Customer DUNS", "required": False,
    })
    northwind.post("/labra-fields", json={
        "labra_field": "customer_duns", "label": "DUNS Number", "required": False,
    })
    view = northwind.get("/mapping-templates/northwind-default").json()
    assert _field(view, "customer_duns")["label"] == "DUNS Number"
    assert _field(view, "company_name")["crm_object"] == "Account"


def test_mark_unused_persists_through_label_change(northwind):
    northwind.post("/labra-fields", json={
        "labra_field": "customer_duns", "label": "Customer DUNS", "required": False,
    })
    r = northwind.patch(
        "/mapping-templates/northwind-default/fields/customer_duns",
        json={"unused": True},
    )
    assert r.status_code == 200
    assert _field(r.json(), "customer_duns")["unused"] is True

    # Change the label; the unused choice stays.
    northwind.post("/labra-fields", json={
        "labra_field": "customer_duns", "label": "DUNS Number", "required": False,
    })
    view = northwind.get("/mapping-templates/northwind-default").json()
    duns = _field(view, "customer_duns")
    assert duns["unused"] is True
    assert duns["label"] == "DUNS Number"


def test_cannot_mark_required_field_unused(northwind):
    r = northwind.patch(
        "/mapping-templates/northwind-default/fields/company_name",
        json={"unused": True},
    )
    assert r.status_code == 422
    assert any(e["field"] == "company_name" for e in r.json()["errors"])
