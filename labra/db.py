"""SQLite connection and schema.

Three tables carry the whole design:

  labra_fields   the shared list Labra+AWS own. ONE row per Labra field.
  templates      one row per customer mapping template.
  mappings       only the customer's own choices (their deltas). One row per
                 (template, labra_field) the customer has mapped or marked unused.

A new Labra field is a single INSERT into labra_fields. No template or mapping
row is touched, yet every template "shows" the field because GET merges
labra_fields with that template's mappings at read time.
"""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS labra_fields (
    labra_field  TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    required     INTEGER NOT NULL DEFAULT 0,   -- 0/1
    sort_order   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
    template_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    crm_type     TEXT NOT NULL                 -- 'salesforce' | 'hubspot'
);

CREATE TABLE IF NOT EXISTS mappings (
    template_id  TEXT NOT NULL,
    labra_field  TEXT NOT NULL,
    crm_object   TEXT,                         -- null when unmapped/unused
    crm_field    TEXT,
    unused       INTEGER NOT NULL DEFAULT 0,   -- 0/1; customer marked optional field unused
    PRIMARY KEY (template_id, labra_field),
    FOREIGN KEY (template_id) REFERENCES templates(template_id) ON DELETE CASCADE,
    FOREIGN KEY (labra_field) REFERENCES labra_fields(labra_field) ON DELETE CASCADE
);
"""


def connect(db_path: str = "labra.db") -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults.

    check_same_thread=False so the single app-held connection works under the
    sync TestClient / threaded server. Row access by column name.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
