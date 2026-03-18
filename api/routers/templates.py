"""Template management endpoints."""

from fastapi import APIRouter, HTTPException

from ..schemas import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
)
from ..services.storage import storage

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates():
    """List all templates."""
    templates = storage.list_templates()
    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in templates],
        total=len(templates),
    )


@router.post("", response_model=TemplateResponse)
async def create_template(data: TemplateCreate):
    """Create a new template."""
    # Convert fields to dicts
    template_data = {
        "name": data.name,
        "description": data.description,
        "fields": [f.model_dump() for f in data.fields],
    }
    template = storage.create_template(template_data)
    return TemplateResponse(**template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get a template by ID."""
    template = storage.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(**template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: str, data: TemplateUpdate):
    """Update a template."""
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.fields is not None:
        update_data["fields"] = [f.model_dump() for f in data.fields]

    template = storage.update_template(template_id, update_data)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(**template)


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """Delete a template."""
    if not storage.delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted", "id": template_id}
