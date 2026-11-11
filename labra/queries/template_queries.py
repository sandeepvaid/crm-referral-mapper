"""SQL for mapping templates."""
from __future__ import annotations

import sqlite3


def get_template(conn: sqlite3.Connection, template_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT template_id, name, crm_type FROM templates WHERE template_id = ?",
        (template_id,),
    ).fetchone()


def insert_template(
    conn: sqlite3.Connection, template_id: str, name: str, crm_type: str
) -> None:
    conn.execute(
        "INSERT INTO templates (template_id, name, crm_type) VALUES (?, ?, ?)",
        (template_id, name, crm_type),
    )
    # Commit is handled by the service once mappings are inserted too, so a
    # failed create stores nothing.
