"""crm-field-values: compute fetches, fetch (one call per object, single retry),
build the referral, validate with Pydantic, translate failures.
"""
from __future__ import annotations

import sqlite3
import time

from pydantic import ValidationError

from labra.crm import CrmRecordNotFound, RateLimited
from labra.model.errors import ApiErrors, FieldError
from labra.model.referral_model import build_referral_model
from labra.service.template_service import get_template_view

CRM_DISPLAY = {"salesforce": "Salesforce", "hubspot": "HubSpot"}

# Per-field (message, fix-action). fix is rendered with the CRM object/field.
_RULE_TEXT = {
    "company_name": ("Company name must be non-empty and at most 255 characters.",
                     "a company name"),
    "website": ("Website must be an http or https URL with a host.",
                "a URL such as https://northwind.example"),
    "country": ("Country must be one of United States, India, Germany, United Kingdom.",
                "United States, India, Germany, or United Kingdom"),
    "expected_monthly_revenue": ("Expected monthly revenue must be a number greater than 0.",
                                 "a number greater than 0"),
    "target_close_date": ("Target close date must be today or later, as YYYY-MM-DD.",
                          "today or a later date as YYYY-MM-DD"),
    "primary_sales_rep_email": ("Primary sales rep email must be a valid email address.",
                                "an email address such as ada@northwind.example"),
    "customer_duns": ("Customer DUNS must be a string of 9 digits.",
                      "a 9-digit DUNS number such as 123456789"),
}


def _fix_set(crm_type: str, crm_object: str | None, crm_field: str | None, action: str) -> str:
    crm = CRM_DISPLAY.get(crm_type, crm_type)
    if crm_object and crm_field:
        return f"Set {crm_object}.{crm_field} in {crm} to {action}."
    return f"Set this field in {crm} to {action}."


def _fetch_with_retry(crm, obj: str, record_id: str, crm_fields: list[str]) -> dict:
    """One fetch, and on RateLimited exactly one retry after the advised wait."""
    try:
        return crm.fetch(obj, record_id, crm_fields)
    except RateLimited as e:
        time.sleep(e.retry_after_ms / 1000.0)
        return crm.fetch(obj, record_id, crm_fields)  # may raise again -> caller handles


def build_referral(conn: sqlite3.Connection, template_id: str, record_id: str, crm) -> dict:
    view = get_template_view(conn, template_id)
    if view is None:
        raise ApiErrors([FieldError(
            field="template_id", received=template_id,
            message=f"Template {template_id} not found.",
            fix="Create the template first.",
        )], status_code=404, include_referral=True)

    crm_type = view.crm_type

    # Context + grouping from the fields the customer currently sees.
    ctx = {f.labra_field: (f.crm_object, f.crm_field) for f in view.fields}
    groups: dict[str, list[tuple[str, str]]] = {}  # crm_object -> [(labra_field, crm_field)]
    for f in view.fields:
        if f.unused or not f.mapped:
            continue  # hidden/unmapped fields are not fetched
        groups.setdefault(f.crm_object, []).append((f.labra_field, f.crm_field))

    fetched: dict[str, object] = {}
    failed_objects: list[str] = []
    not_found_objects: list[str] = []
    any_data = False

    for obj, pairs in groups.items():
        crm_fields = [cf for (_lf, cf) in pairs]
        try:
            row = _fetch_with_retry(crm, obj, record_id, crm_fields)
            any_data = True
            for lf, cf in pairs:
                if cf in row and row[cf] not in (None, ""):
                    fetched[lf] = row[cf]  # empty CRM value -> omit the key
        except RateLimited:
            failed_objects.append(obj)
        except CrmRecordNotFound:
            not_found_objects.append(obj)

    # Unknown record: nothing was found and nothing was rate-limited.
    if not any_data and not_found_objects and not failed_objects:
        raise ApiErrors([FieldError(
            field=None, received=record_id,
            message=f"No CRM record found for record_id '{record_id}'.",
            fix="Use a record_id that exists in the CRM.",
        )], status_code=404, include_referral=True)

    errors: list[FieldError] = []

    # Rate-limit errors: name the object, do not report its fields as blank.
    for obj in failed_objects:
        crm = CRM_DISPLAY.get(crm_type, crm_type)
        errors.append(FieldError(
            field=None, crm_object=obj, crm_field=None, received=None,
            message=f"The {crm} rate limit held for {obj}.",
            fix=f"Retry preparing this referral in a few seconds; the {crm} rate limit for {obj} needs to reset.",
        ))

    # Validate only objects that returned data: exclude failed-object fields.
    model_specs: list[tuple[str, bool]] = []
    for f in view.fields:
        if f.unused:
            continue
        if f.mapped and f.crm_object in failed_objects:
            continue
        model_specs.append((f.labra_field, f.required))

    Referral = build_referral_model(model_specs)
    try:
        referral = Referral(**fetched)
    except ValidationError as ve:
        for err in ve.errors():
            name = err["loc"][0]
            obj, fld = ctx.get(name, (None, None))
            received = err.get("input")
            if err["type"] == "missing":
                errors.append(FieldError(
                    field=name, crm_object=obj, crm_field=fld, received=None,
                    message=f"{name} is required by AWS and has no value.",
                    fix=(f"Map {name} and set a value in {CRM_DISPLAY.get(crm_type, crm_type)}."
                         if not (obj and fld)
                         else _fix_set(crm_type, obj, fld, "a value")),
                ))
            else:
                msg, action = _RULE_TEXT.get(
                    name, (f"{name} is not valid.", "a valid value"))
                errors.append(FieldError(
                    field=name, crm_object=obj, crm_field=fld, received=received,
                    message=msg, fix=_fix_set(crm_type, obj, fld, action),
                ))
        raise ApiErrors(errors, status_code=422, include_referral=True)

    if errors:
        # Rate-limit failures but the returned objects validated cleanly.
        raise ApiErrors(errors, status_code=422, include_referral=True)

    return referral.model_dump(exclude_none=True)
