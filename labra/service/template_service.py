"""Template business logic: create (with all reject rules) and the merged view."""
from __future__ import annotations

import re
import sqlite3

from labra.model.errors import ApiErrors, FieldError
from labra.model.template_model import (
    FieldView,
    MappingIn,
    TemplateCreate,
    TemplateView,
)
from labra.queries import fields_queries, mapping_queries, template_queries

VALID_CRM_TYPES = {"salesforce", "hubspot"}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "template"


def create_template(conn: sqlite3.Connection, body: TemplateCreate) -> str:
    """Validate and store a template. Returns the template_id.

    Nothing is written unless every rule passes: all validation runs first,
    then a single commit.
    """
    errors: list[FieldError] = []

    if not body.name or not body.name.strip():
        errors.append(FieldError(
            field="name", received=body.name,
            message="Template name is blank.",
            fix="Send a non-empty template name.",
        ))

    if body.crm_type not in VALID_CRM_TYPES:
        errors.append(FieldError(
            field="crm_type", received=body.crm_type,
            message="crm_type must be salesforce or hubspot.",
            fix="Send salesforce or hubspot.",
        ))

    valid_fields = fields_queries.field_names(conn)
    required_fields = {
        row["labra_field"]
        for row in fields_queries.list_fields(conn)
        if row["required"]
    }

    seen_labra: set[str] = set()
    seen_crm: dict[tuple[str, str], str] = {}
    mapped_used: set[str] = set()  # fields with a usable crm_object+crm_field

    for m in body.mappings:
        if m.labra_field not in valid_fields:
            errors.append(FieldError(
                field=m.labra_field, received=m.labra_field,
                message=f"{m.labra_field} is not a Labra field.",
                fix="Remove that mapping or add the field first.",
            ))
            continue

        if m.labra_field in seen_labra:
            errors.append(FieldError(
                field=m.labra_field,
                message=f"{m.labra_field} is mapped more than once.",
                fix="Keep one CRM object and field per Labra field.",
            ))
            continue
        seen_labra.add(m.labra_field)

        if m.unused:
            # Marked unused at create: no CRM value needed. Required fields may
            # not be unused — that is caught by the required-mapping check below.
            continue

        obj_blank = not (m.crm_object and m.crm_object.strip())
        fld_blank = not (m.crm_field and m.crm_field.strip())
        if obj_blank or fld_blank:
            errors.append(FieldError(
                field=m.labra_field,
                crm_object=m.crm_object, crm_field=m.crm_field,
                message="A mapping the customer intends to use is missing its CRM object or field.",
                fix="Fill both crm_object and crm_field, or mark the field unused.",
            ))
            continue

        key = (m.crm_object, m.crm_field)
        if key in seen_crm:
            errors.append(FieldError(
                field=m.labra_field,
                crm_object=m.crm_object, crm_field=m.crm_field,
                message=f"{m.crm_object}.{m.crm_field} is mapped to more than one Labra field.",
                fix="Pick one Labra field for that CRM value.",
            ))
            continue
        seen_crm[key] = m.labra_field
        mapped_used.add(m.labra_field)

    for req in sorted(required_fields):
        if req not in mapped_used:
            errors.append(FieldError(
                field=req,
                message=f"Required Labra field {req} has no mapping.",
                fix="Map that field before saving.",
            ))

    template_id = body.template_id or _slug(body.name)
    if not errors and template_queries.get_template(conn, template_id) is not None:
        errors.append(FieldError(
            field="template_id", received=template_id,
            message=f"Template {template_id} already exists.",
            fix="Use a different template id.",
        ))

    if errors:
        raise ApiErrors(errors, status_code=422)

    template_queries.insert_template(conn, template_id, body.name.strip(), body.crm_type)
    for m in body.mappings:
        mapping_queries.insert_mapping(
            conn, template_id, m.labra_field, m.crm_object, m.crm_field, m.unused
        )
    conn.commit()
    return template_id


def get_template_view(conn: sqlite3.Connection, template_id: str) -> TemplateView | None:
    """Merge the live field list with this template's mappings at read time.

    A field introduced after the template was saved appears here automatically,
    as unmapped, with no row rewrite.
    """
    template = template_queries.get_template(conn, template_id)
    if template is None:
        return None

    mappings = {row["labra_field"]: row for row in mapping_queries.get_mappings(conn, template_id)}

    fields: list[FieldView] = []
    for f in fields_queries.list_fields(conn):
        m = mappings.get(f["labra_field"])
        has_crm = bool(m and m["crm_object"] and m["crm_field"])
        fields.append(FieldView(
            labra_field=f["labra_field"],
            label=f["label"],
            required=bool(f["required"]),
            mapped=has_crm,
            unused=bool(m["unused"]) if m else False,
            crm_object=m["crm_object"] if m else None,
            crm_field=m["crm_field"] if m else None,
        ))

    return TemplateView(
        template_id=template["template_id"],
        name=template["name"],
        crm_type=template["crm_type"],
        fields=fields,
    )
