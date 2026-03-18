"""Cumulative context passed between pages during extraction."""

from pydantic import BaseModel, Field


# Confidence threshold for considering a field "confidently found"
CONFIDENT_THRESHOLD = 0.5


class CumulativeContext(BaseModel):
    """Running context passed to each page's extraction pass."""

    # All candidates found: {"field_name": [{"value": "...", "page": 1, "confidence": 0.95, "bbox": {...}}]}
    # Stores ALL candidates, not just high-confidence ones
    candidates_by_field: dict[str, list[dict]] = Field(default_factory=dict)

    # Summary content collected: {"field_name": [{"content": "...", "page": 2}]}
    summary_flags_by_field: dict[str, list[dict]] = Field(default_factory=dict)

    # Entity candidates by group: {"group_name": [{"values": {...}, "page": 1, "confidence": 0.9, "bboxes": {...}}]}
    entity_candidates_by_group: dict[str, list[dict]] = Field(default_factory=dict)

    # All metric field names from schema
    all_metric_fields: list[str] = Field(default_factory=list)

    # All entity group names from schema
    all_entity_groups: list[str] = Field(default_factory=list)

    # Cross-page context notes
    notes: list[str] = Field(default_factory=list)

    @property
    def confidently_found_fields(self) -> set[str]:
        """Fields with at least one high-confidence extraction."""
        found = set()
        for field, candidates in self.candidates_by_field.items():
            if any(c["confidence"] >= CONFIDENT_THRESHOLD for c in candidates):
                found.add(field)
        return found

    @property
    def missing_fields(self) -> list[str]:
        """Fields not yet confidently found."""
        found = self.confidently_found_fields
        return [f for f in self.all_metric_fields if f not in found]

    @property
    def low_confidence_fields(self) -> list[str]:
        """Fields with only low-confidence candidates."""
        found = self.confidently_found_fields
        has_candidate = set(self.candidates_by_field.keys())
        return [f for f in has_candidate if f not in found]

    def to_prompt_context(self) -> str:
        """Format as text for inclusion in extraction prompt."""
        lines = []

        # Show confidently extracted fields (don't need to re-extract these)
        confident = self.confidently_found_fields
        if confident:
            lines.append("### Already Extracted (DO NOT re-extract):")
            for field in sorted(confident):
                best = self.get_best_candidate(field)
                if best:
                    lines.append(f"- {field}: {best['value']} (page {best['page']})")
            lines.append("")

        # Combine low-confidence and completely missing as "Still Looking For"
        # Both should be attempted on subsequent pages
        low_conf = self.low_confidence_fields
        completely_missing = [f for f in self.all_metric_fields if f not in confident and f not in set(self.candidates_by_field.keys())]

        still_looking = low_conf + completely_missing
        if still_looking:
            lines.append("### STILL LOOKING FOR (please extract if visible on this page):")
            for field in sorted(still_looking):
                best = self.get_best_candidate(field)
                if best and best['confidence'] < CONFIDENT_THRESHOLD:
                    # Show tentative value but indicate we need better
                    lines.append(f"- {field} (tentative: {best['value']} - need better match)")
                else:
                    lines.append(f"- {field}")
            lines.append("")

        if self.notes:
            lines.append("### Notes:")
            for note in self.notes:
                lines.append(f"- {note}")
            lines.append("")

        if not lines:
            return "(First page - no prior context)"

        return "## Extraction Context from Previous Pages\n\n" + "\n".join(lines)

    def add_candidate(
        self,
        field_name: str,
        value: str,
        page: int,
        confidence: float,
        bbox: dict = None,
    ) -> None:
        """Add an extraction candidate."""
        if field_name not in self.candidates_by_field:
            self.candidates_by_field[field_name] = []

        candidate = {
            "value": value,
            "page": page,
            "confidence": confidence,
        }
        if bbox:
            candidate["bbox"] = bbox

        self.candidates_by_field[field_name].append(candidate)

    def get_best_candidate(self, field_name: str) -> dict | None:
        """Get the highest-confidence candidate for a field."""
        candidates = self.candidates_by_field.get(field_name, [])
        if not candidates:
            return None
        return max(candidates, key=lambda c: c["confidence"])

    def add_summary_flag(
        self, field_name: str, content: str, page: int, context: str = None
    ) -> None:
        """Add a summary flag to the context."""
        if field_name not in self.summary_flags_by_field:
            self.summary_flags_by_field[field_name] = []
        entry = {"content": content, "page": page}
        if context:
            entry["context"] = context
        self.summary_flags_by_field[field_name].append(entry)

    def add_note(self, note: str) -> None:
        """Add a cross-page note."""
        self.notes.append(note)

    def add_entity_candidate(
        self,
        group_name: str,
        values: dict[str, str],
        page: int,
        confidence: float,
        bboxes: dict = None,
        row_bbox: dict = None,
    ) -> None:
        """Add an entity candidate for an entity group."""
        if group_name not in self.entity_candidates_by_group:
            self.entity_candidates_by_group[group_name] = []

        candidate = {
            "values": values,
            "page": page,
            "confidence": confidence,
        }
        if bboxes:
            candidate["bboxes"] = bboxes
        if row_bbox:
            candidate["row_bbox"] = row_bbox

        self.entity_candidates_by_group[group_name].append(candidate)

    def get_entity_count(self, group_name: str) -> int:
        """Get the number of entities found for a group."""
        return len(self.entity_candidates_by_group.get(group_name, []))

    @classmethod
    def from_schema(cls, schema) -> "CumulativeContext":
        """Initialize context with all metric fields and entity groups listed."""
        entity_group_names = [g.name for g in getattr(schema, 'entity_groups', [])]
        return cls(
            all_metric_fields=[f.name for f in schema.metric_fields],
            all_entity_groups=entity_group_names,
        )
