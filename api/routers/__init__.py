"""API routers."""

from .templates import router as templates_router
from .documents import router as documents_router
from .extraction import router as extraction_router
from .batch import router as batch_router
from .export import router as export_router
from .queue import router as queue_router

__all__ = ["templates_router", "documents_router", "extraction_router", "batch_router", "export_router", "queue_router"]
