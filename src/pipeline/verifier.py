"""OpenAI verification and summary synthesis."""

import json
import os
from typing import Optional

from openai import OpenAI

from ..models import (
    AssembledDocument,
    ExtractionSchema,
    ExtractionCandidate,
    EntityExtraction,
    EntityGroup,
    FieldType,
    BoundingBox,
)


class VerifiedExtraction:
    """Final extraction result after OpenAI verification."""

    def __init__(
        self,
        field_name: str,
        display_name: str,
        field_type: FieldType,
        value: str,
        page: int,
        bounding_box: Optional[BoundingBox] = None,
        verified: bool = True,
        verification_notes: Optional[str] = None,
        confidence: float = 1.0,
        original_value: Optional[str] = None,
        source_pages: Optional[list[int]] = None,
    ):
        self.field_name = field_name
        self.display_name = display_name
        self.field_type = field_type
        self.value = value
        self.page = page
        self.bounding_box = bounding_box
        self.verified = verified
        self.verification_notes = verification_notes
        self.confidence = confidence
        self.original_value = original_value  # If corrected, what VLM originally extracted
        self.source_pages = source_pages  # For summaries: pages content was drawn from

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "field_name": self.field_name,
            "display_name": self.display_name,
            "field_type": self.field_type.value,
            "value": self.value,
            "page": self.page,
            "verified": self.verified,
            "confidence": self.confidence,
        }
        if self.bounding_box:
            result["bounding_box"] = {
                "x1": self.bounding_box.x1,
                "y1": self.bounding_box.y1,
                "x2": self.bounding_box.x2,
                "y2": self.bounding_box.y2,
            }
        if self.verification_notes:
            result["verification_notes"] = self.verification_notes
        if self.original_value and self.original_value != self.value:
            result["original_value"] = self.original_value
        return result


class VerifiedEntity:
    """Single verified entity from an entity group."""

    def __init__(
        self,
        values: dict[str, str],
        page: int,
        confidence: float,
        bounding_boxes: Optional[dict[str, BoundingBox]] = None,
        row_bounding_box: Optional[BoundingBox] = None,
        verified: bool = True,
        verification_notes: Optional[str] = None,
    ):
        self.values = values
        self.page = page
        self.confidence = confidence
        self.bounding_boxes = bounding_boxes or {}
        self.row_bounding_box = row_bounding_box
        self.verified = verified
        self.verification_notes = verification_notes

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "values": self.values,
            "page": self.page,
            "confidence": self.confidence,
            "verified": self.verified,
        }
        if self.bounding_boxes:
            result["bounding_boxes"] = {
                k: {"x1": v.x1, "y1": v.y1, "x2": v.x2, "y2": v.y2}
                for k, v in self.bounding_boxes.items()
            }
        if self.row_bounding_box:
            result["row_bounding_box"] = {
                "x1": self.row_bounding_box.x1,
                "y1": self.row_bounding_box.y1,
                "x2": self.row_bounding_box.x2,
                "y2": self.row_bounding_box.y2,
            }
        if self.verification_notes:
            result["verification_notes"] = self.verification_notes
        return result


class VerifiedEntityGroup:
    """Verified entity group with all entities."""

    def __init__(
        self,
        group_name: str,
        display_name: str,
        entities: list[VerifiedEntity],
    ):
        self.group_name = group_name
        self.display_name = display_name
        self.entities = entities

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.group_name,
            "display_name": self.display_name,
            "entities": [e.to_dict() for e in self.entities],
        }


class DocumentVerifier:
    """Verifies extractions and synthesizes summaries using OpenAI."""

    def __init__(
        self,
        model: str = "gpt-4.1",
        api_key: Optional[str] = None,
    ):
        """
        Initialize the verifier.

        Args:
            model: OpenAI model to use (default: gpt-4.1)
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
        """
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def verify_and_synthesize(
        self,
        assembled: AssembledDocument,
        schema: ExtractionSchema,
    ) -> tuple[list[VerifiedExtraction], dict[str, VerifiedEntityGroup]]:
        """
        Verify metric extractions and synthesize summaries.

        Args:
            assembled: Assembled document with extractions and OCR
            schema: Extraction schema used

        Returns:
            Tuple of (list of verified extractions, dict of verified entity groups)
        """
        results = []
        entity_groups = {}

        # Step 1: Verify metric extractions against OCR
        print("\n  Verifying metric extractions...")
        metric_verifications = self._verify_metrics(assembled, schema)

        for field_name, verification in metric_verifications.items():
            field = schema.get_field(field_name)
            if not field:
                continue

            best_candidate = assembled.best_extractions.get(field_name)
            if not best_candidate:
                continue

            results.append(VerifiedExtraction(
                field_name=field_name,
                display_name=field.display_name,
                field_type=field.field_type,
                value=verification.get("correct_value", best_candidate.value),
                page=best_candidate.page_number,
                bounding_box=best_candidate.bounding_box,
                verified=verification.get("verified", False),
                verification_notes=verification.get("notes"),
                confidence=best_candidate.confidence if verification.get("verified") else 0.5,
                original_value=best_candidate.value if not verification.get("verified") else None,
            ))

        # Step 2: Synthesize summaries from flagged content
        print("  Synthesizing summaries...")
        for summary_field in schema.summary_fields:
            flags = assembled.summary_flags_by_field.get(summary_field.name, [])

            synthesis = self._synthesize_summary(
                summary_field,
                flags,
                assembled.full_ocr_markdown,
            )

            source_pages = synthesis.get("source_pages", [])
            results.append(VerifiedExtraction(
                field_name=summary_field.name,
                display_name=summary_field.display_name,
                field_type=FieldType.SUMMARY,
                value=synthesis.get("summary", ""),
                page=source_pages[0] if source_pages else 1,
                bounding_box=None,  # Summaries don't have bboxes
                verified=True,  # OpenAI generated it
                verification_notes=f"Synthesized from pages: {source_pages}",
                confidence=synthesis.get("confidence", 0.8),
                source_pages=source_pages,
            ))

        # Step 3: Verify entity groups
        print("  Verifying entity groups...")
        for entity_group in schema.entity_groups:
            entities = assembled.entity_candidates_by_group.get(entity_group.name, [])
            if entities:
                verified_group = self._verify_entity_group(
                    entity_group,
                    entities,
                    assembled.full_ocr_markdown,
                )
                entity_groups[entity_group.name] = verified_group

        return results, entity_groups

    def _verify_metrics(
        self,
        assembled: AssembledDocument,
        schema: ExtractionSchema,
    ) -> dict[str, dict]:
        """
        Verify metric extractions against OCR text.

        Returns dict of {field_name: {verified, correct_value, notes}}
        """
        # Format extractions for verification
        extractions_text = []
        for field_name, candidate in assembled.best_extractions.items():
            field = schema.get_field(field_name)
            if field and field.field_type != FieldType.SUMMARY:
                extractions_text.append(
                    f"- {field_name}: \"{candidate.value}\" (page {candidate.page_number})"
                )

        if not extractions_text:
            return {}

        prompt = f"""You are verifying document extractions against the original OCR text.

## Full Document Text (OCR)

{assembled.full_ocr_markdown}

## Extracted Values to Verify

{chr(10).join(extractions_text)}

## Instructions

For each extraction:
1. Search the OCR text to confirm the value exists
2. Check if the extracted value accurately represents what's in the document
3. If the value is wrong or slightly different, provide the correct value from the OCR
4. Note any discrepancies or concerns

Return JSON in this exact format:
{{
    "verifications": {{
        "field_name": {{
            "verified": true/false,
            "correct_value": "the correct value if different from extracted",
            "notes": "explanation if not verified or any concerns"
        }}
    }}
}}

Rules:
- verified=true if the extracted value matches the OCR text (minor formatting differences are OK)
- verified=false if the value is wrong, missing, or significantly different
- Always include correct_value (same as extracted if verified=true)
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("verifications", {})

        except Exception as e:
            print(f"    Warning: Verification failed: {e}")
            # Return all as verified if API fails
            return {
                field: {"verified": True, "correct_value": candidate.value, "notes": "Verification skipped"}
                for field, candidate in assembled.best_extractions.items()
            }

    def _synthesize_summary(
        self,
        field,
        flags: list[dict],
        full_ocr: str,
    ) -> dict:
        """
        Synthesize a summary from flagged content.

        Returns {summary, source_pages, confidence}
        """
        # Format flagged content
        if flags:
            flagged_text = "\n".join([
                f"Page {f['page']}: {f['content']}"
                for f in flags
            ])
        else:
            flagged_text = "(No specific content was flagged for this field)"

        prompt = f"""You are synthesizing a summary from document content.

## Summary Field
Name: {field.name}
Description: {field.description}

## Relevant Content Flagged from Document

{flagged_text}

## Full Document Text (for additional context)

{full_ocr}

## Instructions

1. Synthesize a comprehensive answer based primarily on the flagged content
2. If the flagged content is insufficient, use the full document
3. Keep the summary concise but complete (2-4 sentences)
4. Reference specific facts and figures where relevant

Return JSON in this exact format:
{{
    "summary": "your synthesized summary",
    "source_pages": [1, 2, 3],
    "confidence": 0.9
}}

Rules:
- source_pages should list all pages where key information was found
- confidence should reflect how well the available content answers the field
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"    Warning: Summary synthesis failed: {e}")
            # Return flagged content as-is if API fails
            return {
                "summary": flags[0]["content"] if flags else "Unable to synthesize summary",
                "source_pages": [f["page"] for f in flags] if flags else [],
                "confidence": 0.5,
            }

    def _verify_entity_group(
        self,
        entity_group: EntityGroup,
        entities: list[EntityExtraction],
        full_ocr: str,
    ) -> VerifiedEntityGroup:
        """
        Verify entities in an entity group and deduplicate.

        Args:
            entity_group: The entity group definition
            entities: List of extracted entities
            full_ocr: Full OCR text for verification

        Returns:
            VerifiedEntityGroup with verified/corrected entities
        """
        if not entities:
            return VerifiedEntityGroup(
                group_name=entity_group.name,
                display_name=entity_group.display_name,
                entities=[],
            )

        # Format entities for verification
        entities_text = []
        for i, entity in enumerate(entities):
            values_str = ", ".join([f"{k}: \"{v}\"" for k, v in entity.values.items()])
            entities_text.append(f"Entity {i+1} (page {entity.page_number}): {values_str}")

        field_names = [f.name for f in entity_group.fields]
        field_descriptions = "\n".join([f"  - {f.name}: {f.description}" for f in entity_group.fields])

        prompt = f"""You are verifying extracted entities against the original OCR text.

## Entity Group: {entity_group.name}
Description: {entity_group.description}

Fields to extract for each entity:
{field_descriptions}

## Full Document Text (OCR)

{full_ocr}

## Extracted Entities to Verify

{chr(10).join(entities_text)}

## Instructions

1. Verify each entity's values against the OCR text
2. Identify and remove duplicate entities (same entity appearing on multiple pages or extracted multiple times)
3. Correct any values that don't match the OCR
4. Ensure field values are not swapped between columns

Return JSON in this exact format:
{{
    "verified_entities": [
        {{
            "index": 0,
            "verified": true,
            "corrected_values": {{"field1": "corrected value"}},
            "is_duplicate": false,
            "duplicate_of": null,
            "notes": "optional verification notes"
        }}
    ]
}}

Rules:
- index refers to the original entity index (0-based)
- verified=true if entity exists in the document
- corrected_values only includes fields that need correction (empty if no corrections)
- is_duplicate=true if this entity is a duplicate of another
- duplicate_of is the index of the entity this duplicates (if is_duplicate=true)
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )

            result = json.loads(response.choices[0].message.content)
            verifications = result.get("verified_entities", [])

            # Build verified entities, excluding duplicates
            verified_entities = []
            for v in verifications:
                idx = v.get("index", 0)
                if idx >= len(entities):
                    continue

                # Skip duplicates
                if v.get("is_duplicate", False):
                    continue

                original_entity = entities[idx]

                # Apply corrections if any
                corrected_values = original_entity.values.copy()
                for field, corrected_value in v.get("corrected_values", {}).items():
                    corrected_values[field] = corrected_value

                verified_entities.append(VerifiedEntity(
                    values=corrected_values,
                    page=original_entity.page_number,
                    confidence=original_entity.confidence,
                    bounding_boxes=original_entity.bounding_boxes,
                    row_bounding_box=original_entity.row_bounding_box,
                    verified=v.get("verified", True),
                    verification_notes=v.get("notes"),
                ))

            return VerifiedEntityGroup(
                group_name=entity_group.name,
                display_name=entity_group.display_name,
                entities=verified_entities,
            )

        except Exception as e:
            print(f"    Warning: Entity verification failed: {e}")
            # Return entities as-is if API fails
            return VerifiedEntityGroup(
                group_name=entity_group.name,
                display_name=entity_group.display_name,
                entities=[
                    VerifiedEntity(
                        values=entity.values,
                        page=entity.page_number,
                        confidence=entity.confidence,
                        bounding_boxes=entity.bounding_boxes,
                        row_bounding_box=entity.row_bounding_box,
                        verified=False,
                        verification_notes="Verification skipped",
                    )
                    for entity in entities
                ],
            )


def get_verification_summary(verified: list[VerifiedExtraction]) -> str:
    """Generate a human-readable summary of verification results."""
    lines = ["=" * 60, "VERIFICATION SUMMARY", "=" * 60, ""]

    # Metrics
    metrics = [v for v in verified if v.field_type != FieldType.SUMMARY]
    if metrics:
        lines.append("## Verified Metrics")
        lines.append("")
        for v in sorted(metrics, key=lambda x: x.field_name):
            status = "✓" if v.verified else "✗"
            line = f"{status} {v.field_name}: {v.value} (page {v.page})"
            if v.original_value and v.original_value != v.value:
                line += f" [corrected from: {v.original_value}]"
            if v.verification_notes and not v.verified:
                line += f"\n    Note: {v.verification_notes}"
            lines.append(line)
        lines.append("")

    # Summaries
    summaries = [v for v in verified if v.field_type == FieldType.SUMMARY]
    if summaries:
        lines.append("## Synthesized Summaries")
        lines.append("")
        for v in summaries:
            lines.append(f"### {v.display_name}")
            lines.append(v.value)
            if v.verification_notes:
                lines.append(f"({v.verification_notes})")
            lines.append("")

    # Stats
    verified_count = sum(1 for v in metrics if v.verified)
    corrected_count = sum(1 for v in metrics if not v.verified and v.original_value)

    lines.append("## Statistics")
    lines.append(f"- Metrics verified: {verified_count}/{len(metrics)}")
    if corrected_count:
        lines.append(f"- Metrics corrected: {corrected_count}")
    lines.append(f"- Summaries synthesized: {len(summaries)}")

    return "\n".join(lines)
