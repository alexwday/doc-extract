"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class FieldType(str, Enum):
    """Type of extraction field."""
    METRIC = "metric"
    TEXT = "text"
    SUMMARY = "summary"
    TABLE_CELL = "table_cell"


class JobStatus(str, Enum):
    """Status of a batch job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueueItemStatus(str, Enum):
    """Status of a queue item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Template Schemas
# =============================================================================

class FieldDefinition(BaseModel):
    """Definition of a single extraction field."""
    name: str = Field(..., description="Field identifier (snake_case)")
    display_name: str = Field(..., description="Human-readable name")
    field_type: FieldType = Field(..., description="Type of extraction")
    description: str = Field(..., description="Instructions for extraction")
    expected_format: Optional[str] = Field(None, description="e.g., 'currency', 'percentage'")
    table_hint: Optional[str] = Field(None, description="Table name if extracting from table")


class EntityGroupFieldDefinition(BaseModel):
    """Definition of a field within an entity group."""
    name: str = Field(..., description="Field identifier (snake_case)")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Instructions for extraction")
    expected_format: Optional[str] = Field(None, description="e.g., 'currency', 'percentage'")


class EntityGroupDefinition(BaseModel):
    """Definition of a repeating entity group (e.g., portfolio investments, line items)."""
    name: str = Field(..., description="Group identifier (snake_case)")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Description of what entities to extract")
    fields: list[EntityGroupFieldDefinition] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    """Request to create a new template."""
    name: str = Field(..., description="Template name")
    description: str = Field("", description="Template description")
    fields: list[FieldDefinition] = Field(default_factory=list)
    entity_groups: list[EntityGroupDefinition] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    """Request to update a template."""
    name: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[list[FieldDefinition]] = None
    entity_groups: Optional[list[EntityGroupDefinition]] = None


class TemplateResponse(BaseModel):
    """Template response."""
    id: str
    name: str
    description: str
    fields: list[FieldDefinition]
    entity_groups: list[EntityGroupDefinition] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(BaseModel):
    """List of templates."""
    templates: list[TemplateResponse]
    total: int


# =============================================================================
# Document Schemas
# =============================================================================

class DocumentMetadata(BaseModel):
    """Document metadata."""
    id: str
    filename: str
    uploaded_at: datetime
    page_count: int
    file_size_bytes: int
    status: str = "ready"


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: list[DocumentMetadata]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response after uploading document(s)."""
    documents: list[DocumentMetadata]
    total_uploaded: int


# =============================================================================
# Extraction Schemas
# =============================================================================

class BoundingBoxSchema(BaseModel):
    """Bounding box coordinates (0-1000 normalized scale)."""
    x1: int
    y1: int
    x2: int
    y2: int


class ExtractionValue(BaseModel):
    """Single extracted value."""
    field_name: str
    display_name: str
    field_type: FieldType
    value: str
    page: int
    confidence: float
    verified: bool = False
    verification_notes: Optional[str] = None
    bounding_box: Optional[BoundingBoxSchema] = None
    source_pages: Optional[list[int]] = None  # For summaries


class EntityInstance(BaseModel):
    """Single entity instance within an entity group."""
    values: dict[str, str] = Field(..., description="Field name to value mapping")
    page: int = Field(..., description="Page where entity was found")
    confidence: float = Field(..., description="Average confidence across fields")
    bounding_boxes: Optional[dict[str, BoundingBoxSchema]] = None
    row_bounding_box: Optional[BoundingBoxSchema] = None


class EntityGroupResult(BaseModel):
    """Result for a single entity group."""
    name: str
    display_name: str
    entities: list[EntityInstance] = Field(default_factory=list)


class ExtractionResultResponse(BaseModel):
    """Complete extraction result."""
    id: str
    document_id: str
    document_name: str
    template_id: str
    template_name: str
    extracted_at: datetime
    processing_time_seconds: float
    verified: bool
    extractions: dict[str, ExtractionValue]
    all_candidates: Optional[dict[str, list[dict]]] = None
    entity_groups: dict[str, EntityGroupResult] = Field(default_factory=dict)


class ExtractRequest(BaseModel):
    """Request to run extraction."""
    document_id: str
    template_id: str
    verify: bool = True  # Run OpenAI verification


# =============================================================================
# Batch Schemas
# =============================================================================

class BatchProgress(BaseModel):
    """Progress of a batch job."""
    total: int
    completed: int
    failed: int
    current_document: Optional[str] = None
    current_document_name: Optional[str] = None


class BatchCreateRequest(BaseModel):
    """Request to create a batch job."""
    template_id: str
    document_ids: list[str]
    verify: bool = True


class BatchJobResponse(BaseModel):
    """Batch job status and results."""
    id: str
    template_id: str
    template_name: str
    document_ids: list[str]
    created_at: datetime
    status: JobStatus
    progress: BatchProgress
    result_ids: list[str] = []
    errors: list[dict] = []


# =============================================================================
# Export Schemas
# =============================================================================

class ExportRequest(BaseModel):
    """Request to generate Excel export."""
    result_ids: list[str] = Field(..., description="Result IDs to include in export")
    filename: Optional[str] = Field(None, description="Custom filename (without .xlsx)")


class ExportResponse(BaseModel):
    """Response with export file info."""
    id: str
    filename: str
    created_at: datetime
    result_count: int
    download_url: str


# =============================================================================
# Queue Schemas
# =============================================================================

class QueueItem(BaseModel):
    """Single item in the extraction queue."""
    id: str
    document_id: str
    document_name: str
    template_id: str
    template_name: str
    page_count: int
    verify: bool
    status: QueueItemStatus
    pages_processed: int = 0
    result_id: Optional[str] = None
    error: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    added_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class QueueStatus(BaseModel):
    """Overall queue status with all items."""
    items: list[QueueItem]
    is_processing: bool
    total_pages: int
    processed_pages: int
    current_item_id: Optional[str] = None


class QueueAddRequest(BaseModel):
    """Request to add items to the queue."""
    items: list[dict] = Field(..., description="List of {document_id, template_id, verify} objects")
