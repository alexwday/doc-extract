"""Extraction endpoints."""

import io
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from ..schemas import (
    ExtractRequest,
    ExtractionResultResponse,
    ExtractionValue,
    BoundingBoxSchema,
)
from ..services.storage import storage
from ..services.extraction import extraction_service
from ..services.annotation import annotation_service

router = APIRouter(tags=["extraction"])


@router.post("/extract", response_model=ExtractionResultResponse)
async def run_extraction(request: ExtractRequest):
    """
    Run extraction on a document using a template.

    This may take several minutes depending on document size.
    """
    try:
        result = extraction_service.run_extraction(
            document_id=request.document_id,
            template_id=request.template_id,
            verify=request.verify,
        )

        # Convert to response model
        extractions = {}
        for field_name, ext in result.get("extractions", {}).items():
            bbox = ext.get("bounding_box")
            extractions[field_name] = ExtractionValue(
                field_name=ext["field_name"],
                display_name=ext.get("display_name", field_name),
                field_type=ext.get("field_type", "metric"),
                value=ext.get("value", ""),
                page=ext.get("page", 1),
                confidence=ext.get("confidence", 0),
                verified=ext.get("verified", False),
                verification_notes=ext.get("verification_notes"),
                bounding_box=BoundingBoxSchema(**bbox) if bbox else None,
                source_pages=ext.get("source_pages"),
            )

        return ExtractionResultResponse(
            id=result["id"],
            document_id=result["document_id"],
            document_name=result.get("document_name", ""),
            template_id=result["template_id"],
            template_name=result.get("template_name", ""),
            extracted_at=result["extracted_at"],
            processing_time_seconds=result.get("processing_time_seconds", 0),
            verified=result.get("verified", False),
            extractions=extractions,
            all_candidates=result.get("all_candidates"),
            entity_groups=result.get("entity_groups", {}),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/results")
async def list_results():
    """List all extraction results."""
    results = storage.list_results()
    return {"results": results, "total": len(results)}


@router.get("/results/{result_id}")
async def get_result(result_id: str):
    """Get a specific extraction result."""
    result = storage.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Don't return full OCR markdown in list view (too large)
    return {
        k: v for k, v in result.items()
        if k != "full_ocr_markdown"
    }


@router.get("/results/{result_id}/ocr")
async def get_result_ocr(result_id: str):
    """Get the full OCR markdown for a result."""
    result = storage.get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return {
        "result_id": result_id,
        "full_ocr_markdown": result.get("full_ocr_markdown", ""),
    }


@router.delete("/results/{result_id}")
async def delete_result(result_id: str):
    """Delete an extraction result."""
    if not storage.delete_result(result_id):
        raise HTTPException(status_code=404, detail="Result not found")
    return {"status": "deleted", "id": result_id}


@router.get("/documents/{document_id}/pages/{page}/annotated")
async def get_annotated_page(
    document_id: str,
    page: int,
    result_id: str,
    highlight: Optional[str] = None,
):
    """
    Get a page image with bounding box annotations.

    Args:
        document_id: Document ID
        page: Page number (1-indexed)
        result_id: Result ID to get bounding boxes from
        highlight: Optional field name to highlight
    """
    img = annotation_service.render_annotated_page(
        document_id=document_id,
        page_number=page,
        result_id=result_id,
        highlight_field=highlight,
    )

    if not img:
        raise HTTPException(status_code=404, detail="Page or result not found")

    # Convert to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=page_{page}_annotated.png"},
    )


@router.get("/results/{result_id}/pages/{page}/extractions")
async def get_page_extractions(result_id: str, page: int):
    """Get all extractions for a specific page."""
    extractions = annotation_service.get_extractions_for_page(result_id, page)
    return {"page": page, "extractions": extractions}
