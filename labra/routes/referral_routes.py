"""crm-field-values route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from labra.model.errors import ApiErrors
from labra.service import referral_service

router = APIRouter()


class CrmFieldValuesIn(BaseModel):
    record_id: str


@router.post("/mapping-templates/{template_id}/crm-field-values")
def crm_field_values(template_id: str, body: CrmFieldValuesIn, request: Request):
    conn = request.app.state.conn
    crm = request.app.state.crm
    try:
        referral = referral_service.build_referral(conn, template_id, body.record_id, crm)
    except ApiErrors as e:
        return JSONResponse(status_code=e.status_code, content=e.body())
    return {"referral": referral, "errors": []}
