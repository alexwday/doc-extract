"""Extraction schema definitions - user-defined fields to extract."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Type of extraction field."""
    METRIC = "metric"           # Specific value - gets bounding box
    TEXT = "text"               # Short text - gets bounding box
    SUMMARY = "summary"         # Multi-page reasoning - gets page references
    TABLE_CELL = "table_cell"   # Specific cell from a table - gets bounding box


class ExtractionField(BaseModel):
    """User-defined field to extract from documents."""

    name: str = Field(..., description="Field identifier (e.g., 'total_revenue')")
    display_name: str = Field(..., description="Human-readable name")
    field_type: FieldType = Field(..., description="Type of extraction")
    description: str = Field(..., description="Instructions for what to extract")

    # Optional hints to improve extraction
    expected_format: Optional[str] = Field(
        None, description="e.g., 'currency', 'percentage', 'date'"
    )
    table_hint: Optional[str] = Field(
        None, description="Table name if extracting from specific table"
    )

    def to_prompt_line(self) -> str:
        """Format field for inclusion in extraction prompt."""
        line = f"- {self.name}: {self.description}"
        if self.expected_format:
            line += f" (format: {self.expected_format})"
        if self.table_hint:
            line += f" [from table: {self.table_hint}]"
        return line


class EntityGroupField(BaseModel):
    """Field definition within an entity group."""

    name: str = Field(..., description="Field identifier (e.g., 'company_name')")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Instructions for what to extract")
    expected_format: Optional[str] = Field(
        None, description="e.g., 'currency', 'percentage', 'date'"
    )

    def to_prompt_line(self) -> str:
        """Format field for inclusion in extraction prompt."""
        line = f"  - {self.name}: {self.description}"
        if self.expected_format:
            line += f" (format: {self.expected_format})"
        return line


class EntityGroup(BaseModel):
    """Definition of a repeating entity group (e.g., portfolio investments, line items)."""

    name: str = Field(..., description="Group identifier (e.g., 'portfolio_investments')")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Description of what entities to extract")
    fields: list[EntityGroupField] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Format entity group for inclusion in extraction prompt."""
        lines = [f"### {self.name}: {self.description}"]
        lines.append("Fields to extract for each entity:")
        for field in self.fields:
            lines.append(field.to_prompt_line())
        return "\n".join(lines)


class ExtractionSchema(BaseModel):
    """Complete schema for a document type."""

    name: str = Field(..., description="Schema name (e.g., 'Quarterly Report')")
    description: str = Field(..., description="Document type description")
    fields: list[ExtractionField]
    entity_groups: list[EntityGroup] = Field(default_factory=list)

    @property
    def metric_fields(self) -> list[ExtractionField]:
        """Fields that get bounding boxes (metric, text, table_cell)."""
        return [
            f for f in self.fields
            if f.field_type in (FieldType.METRIC, FieldType.TEXT, FieldType.TABLE_CELL)
        ]

    @property
    def summary_fields(self) -> list[ExtractionField]:
        """Fields that get synthesized summaries."""
        return [f for f in self.fields if f.field_type == FieldType.SUMMARY]

    def get_field(self, name: str) -> Optional[ExtractionField]:
        """Get a field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_entity_group(self, name: str) -> Optional[EntityGroup]:
        """Get an entity group by name."""
        for g in self.entity_groups:
            if g.name == name:
                return g
        return None

    def format_metric_fields(self) -> str:
        """Format metric fields for extraction prompt."""
        if not self.metric_fields:
            return "(No metric fields defined)"
        return "\n".join(f.to_prompt_line() for f in self.metric_fields)

    def format_summary_fields(self) -> str:
        """Format summary fields for extraction prompt."""
        if not self.summary_fields:
            return "(No summary fields defined)"
        return "\n".join(f.to_prompt_line() for f in self.summary_fields)

    def format_entity_groups(self) -> str:
        """Format entity groups for extraction prompt."""
        if not self.entity_groups:
            return "(No entity groups defined)"
        return "\n\n".join(g.to_prompt_block() for g in self.entity_groups)
