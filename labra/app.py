"""Application factory.

create_app(crm) is the test seam. Tests build a FakeCrm, seed it, and call
create_app(crm) to get an app whose routes use that exact CRM. The handlers
never build their own CRM client.
"""
from __future__ import annotations

from fastapi import FastAPI

from labra.db import connect, init_db
from labra.seed import seed_fields


def create_app(crm, db_path: str = "labra.db") -> FastAPI:
    app = FastAPI(title="Labra referral mapping service")

    conn = connect(db_path)
    init_db(conn)
    seed_fields(conn)

    # Shared handles for route modules (accessed via request.app.state).
    app.state.conn = conn
    app.state.crm = crm

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Routers are registered here as each phase lands them.
    from labra.routes import register_routes

    register_routes(app)

    return app
