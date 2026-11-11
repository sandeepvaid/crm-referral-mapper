"""Request/response shapes for the shared field list."""
from __future__ import annotations

from pydantic import BaseModel


class FieldIntroduce(BaseModel):
    labra_field: str
    label: str
    required: bool = False  # new fields default to optional
