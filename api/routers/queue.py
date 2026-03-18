"""Queue router - endpoints for queue management."""

from fastapi import APIRouter, HTTPException

from ..schemas.api import QueueStatus, QueueAddRequest
from ..services.queue import queue_service


router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("", response_model=QueueStatus)
async def add_to_queue(request: QueueAddRequest):
    """Add items to the extraction queue."""
    try:
        queue_service.add_items(request.items)
        return queue_service.get_status()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=QueueStatus)
async def get_queue_status():
    """Get current queue status with all items and progress."""
    return queue_service.get_status()


@router.delete("/{item_id}")
async def remove_queue_item(item_id: str):
    """Remove a pending item from the queue."""
    try:
        removed = queue_service.remove_item(item_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop")
async def stop_current():
    """Stop the currently processing item immediately."""
    stopped = queue_service.stop_current()
    return {"success": stopped}


@router.post("/cancel")
async def cancel_queue():
    """Cancel all queue processing."""
    cancelled = queue_service.cancel()
    return {"success": cancelled}


@router.delete("/completed")
async def clear_completed():
    """Clear completed and failed items from the queue."""
    removed = queue_service.clear_completed()
    return {"removed": removed}
