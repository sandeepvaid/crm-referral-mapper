"""Field-list routes: introduce / update a shared Labra field."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from labra.model.errors import ApiErrors
from labra.model.field_model import FieldIntroduce
from labra.queries import fields_queries
from labra.service import field_service

router = APIRouter()


@router.post("/labra-fields")
def introduce_field(body: FieldIntroduce, request: Request):
    conn = request.app.state.conn
    try:
        field_service.introduce_field(conn, body)
    except ApiErrors as e:
        return JSONResponse(status_code=e.status_code, content=e.body())

    row = fields_queries.get_field(conn, body.labra_field.strip())
    return JSONResponse(status_code=200, content={
        "labra_field": row["labra_field"],
        "label": row["label"],
        "required": bool(row["required"]),
    })
