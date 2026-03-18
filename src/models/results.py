"""Result models for document extraction."""

from typing import Optional

from PIL import Image
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized coordinates (0-1000 scale per Qwen3-VL)."""

    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)
    x2: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000)

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        """Convert to pixel coordinates for rendering."""
        return (
            int(self.x1 * width / 1000),
            int(self.y1 * height / 1000),
            int(self.x2 * width / 1000),
            int(self.y2 * height / 1000),
        )

    @classmethod
    def from_list(cls, coords: list[int]) -> "BoundingBox":
        """Create from [x1, y1, x2, y2] list."""
        if len(coords) != 4:
            raise ValueError(f"Expected 4 coordinates, got {len(coords)}")
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])


class PageExtraction(BaseModel):
    """Single extracted value from a page."""

    field_name: str
    value: str
    bounding_box: BoundingBox
    confidence: float = Field(ge=0, le=1)
    page_number: int = 0  # Set during processing


class SummaryFlag(BaseModel):
    """Content flagged as relevant to a summary field."""

    field_name: str
    relevant_content: str
    context: Optional[str] = None
    page_number: int = 0  # Set during processing


class EntityExtraction(BaseModel):
    """Single entity extracted from an entity group."""

    group_name: str
    values: dict[str, str]  # field_name -> value
    bounding_boxes: dict[str, BoundingBox] = Field(default_factory=dict)  # field_name -> bbox
    row_bounding_box: Optional[BoundingBox] = None
    confidence: float = Field(ge=0, le=1)
    page_number: int = 0  # Set during processing


class PageImage(BaseModel):
    """Page image with metadata."""

    page_number: int
    image_path: str
    width: int
    height: int

    class Config:
        arbitrary_types_allowed = True


class PageResult(BaseModel):
    """Complete result from processing one page."""

    page_number: int
    markdown: str
    extractions: list[PageExtraction]
    summary_flags: list[SummaryFlag]
    entity_extractions: list[EntityExtraction] = Field(default_factory=list)
    image_path: str
    image_width: int
    image_height: int


class ExtractionCandidate(BaseModel):
    """A candidate extraction with all metadata."""

    field_name: str
    value: str
    page_number: int
    confidence: float
    bounding_box: Optional[BoundingBox] = None


class AssembledDocument(BaseModel):
    """Assembled results from all pages."""

    full_ocr_markdown: str
    # All candidates grouped by field
    candidates_by_field: dict[str, list[ExtractionCandidate]]
    summary_flags_by_field: dict[str, list[dict]]
    # Entity extractions grouped by entity group name
    entity_candidates_by_group: dict[str, list[EntityExtraction]] = Field(default_factory=dict)
    page_results: list[PageResult]
    page_count: int

    @property
    def best_extractions(self) -> dict[str, ExtractionCandidate]:
        """Get best extraction per field (highest confidence)."""
        result = {}
        for field, candidates in self.candidates_by_field.items():
            if candidates:
                result[field] = max(candidates, key=lambda c: c.confidence)
        return result

    def get_all_candidates(self, field_name: str) -> list[ExtractionCandidate]:
        """Get all candidates for a field, sorted by confidence."""
        candidates = self.candidates_by_field.get(field_name, [])
        return sorted(candidates, key=lambda c: c.confidence, reverse=True)

    def get_entities(self, group_name: str) -> list[EntityExtraction]:
        """Get all entity extractions for a group, sorted by page then confidence."""
        entities = self.entity_candidates_by_group.get(group_name, [])
        return sorted(entities, key=lambda e: (e.page_number, -e.confidence))
