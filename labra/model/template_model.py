"""Request/response shapes for mapping templates."""
from __future__ import annotations

from pydantic import BaseModel


class MappingIn(BaseModel):
    labra_field: str
    crm_object: str | None = None
    crm_field: str | None = None
    unused: bool = False


class TemplateCreate(BaseModel):
    # template_id is optional; when omitted the service slugs it from name.
    template_id: str | None = None
    name: str
    crm_type: str
    mappings: list[MappingIn] = []


class FieldView(BaseModel):
    """One row in a GET /mapping-templates/{id} response."""
    labra_field: str
    label: str
    required: bool
    mapped: bool
    unused: bool
    crm_object: str | None
    crm_field: str | None


class TemplateView(BaseModel):
    template_id: str
    name: str
    crm_type: str
    fields: list[FieldView]


class SetUnusedIn(BaseModel):
    unused: bool
