"""Field-list business logic: introduce a new field or update an existing one."""
from __future__ import annotations

import sqlite3

from labra.model.errors import ApiErrors, FieldError
from labra.model.field_model import FieldIntroduce
from labra.queries import fields_queries


def introduce_field(conn: sqlite3.Connection, body: FieldIntroduce) -> None:
    """Add a new Labra field, or update an existing field's definition.

    This is a single write to labra_fields. No template or mapping row is
    touched, so every existing template shows the field (unmapped) on its next
    read. Re-calling for the same field updates its label/required; mapped CRM
    fields on existing templates are left as the customer left them.
    """
    errors: list[FieldError] = []
    if not body.labra_field or not body.labra_field.strip():
        errors.append(FieldError(
            field="labra_field", received=body.labra_field,
            message="labra_field is blank.",
            fix="Send a non-empty labra_field key.",
        ))
    if not body.label or not body.label.strip():
        errors.append(FieldError(
            field="label", received=body.label,
            message="label is blank.",
            fix="Send a non-empty label.",
        ))
    if errors:
        raise ApiErrors(errors, status_code=422)

    fields_queries.upsert_field(
        conn, body.labra_field.strip(), body.label.strip(), body.required
    )
