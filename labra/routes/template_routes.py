"""Template routes: create, read (merged view), and mark-field-unused."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from labra.model.errors import ApiErrors, FieldError
from labra.model.template_model import SetUnusedIn, TemplateCreate
from labra.queries import fields_queries, template_queries, mapping_queries
from labra.service import template_service

router = APIRouter()


@router.post("/mapping-templates")
def create_template(body: TemplateCreate, request: Request):
    conn = request.app.state.conn
    try:
        template_id = template_service.create_template(conn, body)
    except ApiErrors as e:
        return JSONResponse(status_code=e.status_code, content=e.body())
    view = template_service.get_template_view(conn, template_id)
    return JSONResponse(status_code=201, content=view.model_dump())


@router.get("/mapping-templates/{template_id}")
def get_template(template_id: str, request: Request):
    conn = request.app.state.conn
    view = template_service.get_template_view(conn, template_id)
    if view is None:
        return JSONResponse(
            status_code=404,
            content={"errors": [FieldError(
                field="template_id", received=template_id,
                message=f"Template {template_id} not found.",
                fix="Create the template first.",
            ).model_dump()]},
        )
    return view.model_dump()


@router.patch("/mapping-templates/{template_id}/fields/{labra_field}")
def set_field_unused(template_id: str, labra_field: str, body: SetUnusedIn, request: Request):
    """Mark an optional field used/unused on a template.

    Marking a required field unused is rejected; the fix says AWS requires it.
    """
    conn = request.app.state.conn

    if template_queries.get_template(conn, template_id) is None:
        return JSONResponse(status_code=404, content={"errors": [FieldError(
            field="template_id", received=template_id,
            message=f"Template {template_id} not found.",
            fix="Create the template first.",
        ).model_dump()]})

    field = fields_queries.get_field(conn, labra_field)
    if field is None:
        return JSONResponse(status_code=404, content={"errors": [FieldError(
            field=labra_field, received=labra_field,
            message=f"{labra_field} is not a Labra field.",
            fix="Use a field from the shared list.",
        ).model_dump()]})

    if body.unused and field["required"]:
        return JSONResponse(status_code=422, content={"errors": [FieldError(
            field=labra_field,
            message=f"{labra_field} is required by AWS and cannot be marked unused.",
            fix="Keep the field in use and map it.",
        ).model_dump()]})

    mapping_queries.set_unused(conn, template_id, labra_field, body.unused)
    view = template_service.get_template_view(conn, template_id)
    return view.model_dump()
