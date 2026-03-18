"""Batch processing endpoints."""

from fastapi import APIRouter, HTTPException

from ..schemas import (
    BatchCreateRequest,
    BatchJobResponse,
    BatchProgress,
    JobStatus,
)
from ..services.batch import batch_service
from ..services.storage import storage

router = APIRouter(prefix="/batch", tags=["batch"])


def _job_to_response(job: dict) -> BatchJobResponse:
    """Convert job dict to response model."""
    return BatchJobResponse(
        id=job["id"],
        template_id=job["template_id"],
        template_name=job.get("template_name", ""),
        document_ids=job["document_ids"],
        created_at=job["created_at"],
        status=JobStatus(job["status"]),
        progress=BatchProgress(
            total=job["progress"]["total"],
            completed=job["progress"]["completed"],
            failed=job["progress"]["failed"],
            current_document=job["progress"].get("current_document"),
            current_document_name=job["progress"].get("current_document_name"),
        ),
        result_ids=job.get("result_ids", []),
        errors=job.get("errors", []),
    )


@router.post("", response_model=BatchJobResponse)
async def create_batch_job(request: BatchCreateRequest):
    """
    Create and start a new batch extraction job.

    The job will process documents in the background.
    Poll GET /api/batch/{id} to check progress.
    """
    try:
        # Create job
        job = batch_service.create_job(
            template_id=request.template_id,
            document_ids=request.document_ids,
            verify=request.verify,
        )

        # Start processing
        job = batch_service.start_job(job["id"])

        return _job_to_response(job)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch job: {str(e)}")


@router.get("")
async def list_batch_jobs():
    """List all batch jobs."""
    jobs = batch_service.list_jobs()
    return {
        "jobs": [_job_to_response(j) for j in jobs],
        "total": len(jobs),
    }


@router.get("/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(job_id: str):
    """Get batch job status and progress."""
    job = batch_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.post("/{job_id}/cancel", response_model=BatchJobResponse)
async def cancel_batch_job(job_id: str):
    """Cancel a running or pending batch job."""
    try:
        job = batch_service.cancel_job(job_id)
        return _job_to_response(job)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{job_id}")
async def delete_batch_job(job_id: str):
    """Delete a batch job (cancels if running)."""
    if not batch_service.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "deleted", "id": job_id}


@router.get("/{job_id}/results")
async def get_batch_results(job_id: str):
    """Get all extraction results from a batch job."""
    job = batch_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = []
    for result_id in job.get("result_ids", []):
        result = storage.get_result(result_id)
        if result:
            # Return summary without full OCR
            results.append({
                "id": result["id"],
                "document_id": result["document_id"],
                "document_name": result.get("document_name", ""),
                "extracted_at": result["extracted_at"],
                "processing_time_seconds": result.get("processing_time_seconds", 0),
                "verified": result.get("verified", False),
                "extraction_count": len(result.get("extractions", {})),
            })

    return {
        "job_id": job_id,
        "status": job["status"],
        "results": results,
        "total": len(results),
        "errors": job.get("errors", []),
    }
