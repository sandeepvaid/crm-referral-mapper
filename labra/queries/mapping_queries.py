"""SQL for per-template mappings (the customer's deltas)."""
from __future__ import annotations

import sqlite3


def get_mappings(conn: sqlite3.Connection, template_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT labra_field, crm_object, crm_field, unused "
        "FROM mappings WHERE template_id = ?",
        (template_id,),
    ).fetchall()


def get_mapping(
    conn: sqlite3.Connection, template_id: str, labra_field: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT labra_field, crm_object, crm_field, unused "
        "FROM mappings WHERE template_id = ? AND labra_field = ?",
        (template_id, labra_field),
    ).fetchone()


def insert_mapping(
    conn: sqlite3.Connection,
    template_id: str,
    labra_field: str,
    crm_object: str | None,
    crm_field: str | None,
    unused: bool = False,
) -> None:
    conn.execute(
        "INSERT INTO mappings (template_id, labra_field, crm_object, crm_field, unused) "
        "VALUES (?, ?, ?, ?, ?)",
        (template_id, labra_field, crm_object, crm_field, 1 if unused else 0),
    )


def set_unused(
    conn: sqlite3.Connection, template_id: str, labra_field: str, unused: bool
) -> None:
    """Mark a field used/unused on a template.

    If no mapping row exists yet (field was never mapped), create one carrying
    just the unused flag with null CRM object/field.
    """
    existing = get_mapping(conn, template_id, labra_field)
    if existing is None:
        conn.execute(
            "INSERT INTO mappings (template_id, labra_field, crm_object, crm_field, unused) "
            "VALUES (?, ?, NULL, NULL, ?)",
            (template_id, labra_field, 1 if unused else 0),
        )
    else:
        conn.execute(
            "UPDATE mappings SET unused = ? WHERE template_id = ? AND labra_field = ?",
            (1 if unused else 0, template_id, labra_field),
        )
    conn.commit()
