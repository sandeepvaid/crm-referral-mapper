"""SQL for the shared Labra field list."""
from __future__ import annotations

import sqlite3


def list_fields(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every current Labra field, in display order."""
    return conn.execute(
        "SELECT labra_field, label, required, sort_order "
        "FROM labra_fields ORDER BY sort_order"
    ).fetchall()


def get_field(conn: sqlite3.Connection, labra_field: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT labra_field, label, required, sort_order "
        "FROM labra_fields WHERE labra_field = ?",
        (labra_field,),
    ).fetchone()


def field_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT labra_field FROM labra_fields").fetchall()
    return {row["labra_field"] for row in rows}


def upsert_field(
    conn: sqlite3.Connection, labra_field: str, label: str, required: bool
) -> None:
    """Introduce a new field, or update an existing field's definition.

    On update, mappings on existing templates are left completely alone.
    sort_order for a brand-new field goes to the end of the list.
    """
    existing = get_field(conn, labra_field)
    if existing is None:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM labra_fields"
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO labra_fields (labra_field, label, required, sort_order) "
            "VALUES (?, ?, ?, ?)",
            (labra_field, label, 1 if required else 0, next_order),
        )
    else:
        conn.execute(
            "UPDATE labra_fields SET label = ?, required = ? WHERE labra_field = ?",
            (label, 1 if required else 0, labra_field),
        )
    conn.commit()
