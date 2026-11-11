"""Seed the six required Labra fields into an empty database.

These are the shared field list the assessment starts with. Every one is
required. sort_order fixes the display order in GET responses.
"""
from __future__ import annotations

import sqlite3

SEED_FIELDS = [
    # (labra_field, label, required, sort_order)
    ("company_name", "Company name", 1, 1),
    ("website", "Website", 1, 2),
    ("country", "Country", 1, 3),
    ("expected_monthly_revenue", "Expected monthly revenue", 1, 4),
    ("target_close_date", "Target close date", 1, 5),
    ("primary_sales_rep_email", "Primary sales rep email", 1, 6),
]


def seed_fields(conn: sqlite3.Connection) -> None:
    """Insert the six base fields if they are not already present."""
    conn.executemany(
        """
        INSERT OR IGNORE INTO labra_fields (labra_field, label, required, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        SEED_FIELDS,
    )
    conn.commit()
