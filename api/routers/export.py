"""Export endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

from ..schemas import ExportRequest, ExportResponse
from ..services.excel import excel_service

router = APIRouter(prefix="/export", tags=["export"])


@router.post("", response_model=ExportResponse)
async def create_export(request: ExportRequest):
    """
    Generate an Excel export from extraction results.

    Returns export metadata including download URL.
    """
    try:
        export = excel_service.generate_export(
            result_ids=request.result_ids,
            filename=request.filename,
        )

        return ExportResponse(
            id=export["id"],
            filename=export["filename"],
            created_at=export["created_at"],
            result_count=export["result_count"],
            download_url=f"/api/export/{export['id']}",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/{export_id}")
async def download_export(export_id: str):
    """Download an Excel export file."""
    result = excel_service.get_export(export_id)
    if not result:
        raise HTTPException(status_code=404, detail="Export not found")

    content, filename = result

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
