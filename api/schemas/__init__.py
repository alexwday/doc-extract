"""API schemas (Pydantic models)."""

from .api import (
    # Enums
    FieldType,
    JobStatus,
    # Templates
    FieldDefinition,
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    # Documents
    DocumentMetadata,
    DocumentListResponse,
    DocumentUploadResponse,
    # Extraction
    BoundingBoxSchema,
    ExtractionValue,
    ExtractionResultResponse,
    ExtractRequest,
    # Batch
    BatchCreateRequest,
    BatchJobResponse,
    BatchProgress,
    # Export
    ExportRequest,
    ExportResponse,
)

__all__ = [
    "FieldType",
    "JobStatus",
    "FieldDefinition",
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "TemplateListResponse",
    "DocumentMetadata",
    "DocumentListResponse",
    "DocumentUploadResponse",
    "BoundingBoxSchema",
    "ExtractionValue",
    "ExtractionResultResponse",
    "ExtractRequest",
    "BatchCreateRequest",
    "BatchJobResponse",
    "BatchProgress",
    "ExportRequest",
    "ExportResponse",
]
