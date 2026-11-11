"""Router registration. Each phase adds its router here."""
from __future__ import annotations

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    from labra.routes import template_routes, field_routes, referral_routes

    app.include_router(template_routes.router)
    app.include_router(field_routes.router)
    app.include_router(referral_routes.router)
