"""Phase 0 smoke test: the app boots, the db seeds, health responds."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_six_fields_seeded(client):
    conn = client.app.state.conn
    rows = conn.execute("SELECT labra_field FROM labra_fields ORDER BY sort_order").fetchall()
    fields = [row["labra_field"] for row in rows]
    assert fields == [
        "company_name",
        "website",
        "country",
        "expected_monthly_revenue",
        "target_close_date",
        "primary_sales_rep_email",
    ]
