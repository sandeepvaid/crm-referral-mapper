"""The single error object used across the API.

Template failures, field-list failures, and CRM-data validation failures all
return this same shape. crm_object / crm_field may be null; fix always says
what to change.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FieldError(BaseModel):
    field: str | None = None
    crm_object: str | None = None
    crm_field: str | None = None
    received: Any | None = None
    message: str
    fix: str


class ApiErrors(Exception):
    """Carries a batch of FieldError plus the HTTP status to return.

    `include_referral` controls the response envelope: the crm-field-values
    endpoint returns {"referral": null, "errors": [...]}, while create/field
    endpoints return {"errors": [...]}.
    """

    def __init__(
        self,
        errors: list[FieldError],
        status_code: int = 422,
        include_referral: bool = False,
    ):
        self.errors = errors
        self.status_code = status_code
        self.include_referral = include_referral
        super().__init__(f"{len(errors)} error(s)")

    def body(self) -> dict:
        payload: dict = {"errors": [e.model_dump() for e in self.errors]}
        if self.include_referral:
            payload = {"referral": None, **payload}
        return payload
