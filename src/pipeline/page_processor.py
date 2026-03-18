"""Two-pass per-page processing."""

import json
import re
from typing import Optional

from ..models import (
    ExtractionSchema,
    CumulativeContext,
    PageImage,
    PageResult,
    PageExtraction,
    SummaryFlag,
    EntityExtraction,
    BoundingBox,
)
from ..vlm import VLMModel, PromptBuilder


class PageProcessor:
    """Processes individual pages with two-pass extraction."""

    def __init__(self, model: VLMModel):
        """
        Initialize the page processor.

        Args:
            model: VLM model instance for inference
        """
        self.model = model

    def process_page(
        self,
        page: PageImage,
        schema: ExtractionSchema,
        context: CumulativeContext,
    ) -> tuple[PageResult, CumulativeContext]:
        """
        Two-pass processing for a single page.

        Pass 1: Pure OCR (no context)
        Pass 2: Extraction with cumulative context

        Args:
            page: Page image to process
            schema: Extraction schema defining fields
            context: Cumulative context from prior pages

        Returns:
            Tuple of (PageResult, updated CumulativeContext)
        """
        print(f"\n--- Processing Page {page.page_number} ---")

        # === PASS 1: PURE OCR ===
        print(f"  Pass 1: OCR...")
        markdown = self.model.ocr_page(page.image_path)
        print(f"  OCR complete ({len(markdown)} chars)")

        # === PASS 2: EXTRACTION + FLAGGING ===
        print(f"  Pass 2: Extraction...")
        extraction_prompt = PromptBuilder.extraction_prompt(schema, context)
        extraction_response = self.model.extract_from_page(
            page.image_path,
            extraction_prompt,
        )

        # Parse the extraction response
        extractions, summary_flags, entity_extractions, notes = self._parse_extraction_response(
            extraction_response, page.page_number
        )
        print(f"  Found {len(extractions)} extractions, {len(summary_flags)} summary flags, {len(entity_extractions)} entities")

        # Update cumulative context
        new_context = self._update_context(
            context, extractions, summary_flags, entity_extractions, notes, page.page_number
        )

        return PageResult(
            page_number=page.page_number,
            markdown=markdown,
            extractions=extractions,
            summary_flags=summary_flags,
            entity_extractions=entity_extractions,
            image_path=page.image_path,
            image_width=page.width,
            image_height=page.height,
        ), new_context

    def _parse_extraction_response(
        self,
        response: str,
        page_number: int,
    ) -> tuple[list[PageExtraction], list[SummaryFlag], list[EntityExtraction], list[str]]:
        """
        Parse the VLM's JSON extraction response.

        Args:
            response: Raw response from VLM
            page_number: Current page number

        Returns:
            Tuple of (extractions, summary_flags, entity_extractions, notes)
        """
        extractions = []
        summary_flags = []
        entity_extractions = []
        notes = []

        # Try to extract JSON from response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            print(f"  Warning: No JSON found in response")
            return extractions, summary_flags, entity_extractions, notes

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            print(f"  Warning: Failed to parse JSON: {e}")
            return extractions, summary_flags, entity_extractions, notes

        # Parse extractions
        for ext in data.get("extractions", []):
            try:
                # Support both bbox_2d (new) and bounding_box (legacy) keys
                bbox_data = ext.get("bbox_2d") or ext.get("bounding_box", [0, 0, 0, 0])
                # Handle both list and dict formats
                if isinstance(bbox_data, dict):
                    bbox = BoundingBox(
                        x1=bbox_data.get("x1", 0),
                        y1=bbox_data.get("y1", 0),
                        x2=bbox_data.get("x2", 0),
                        y2=bbox_data.get("y2", 0),
                    )
                else:
                    # Convert to integers and create bbox
                    # Note: bbox_2d uses pixel coordinates, we'll normalize to 0-1000 later if needed
                    bbox_data = [int(v) for v in bbox_data]
                    bbox = BoundingBox.from_list(bbox_data)

                value = str(ext.get("value", ""))
                confidence = float(ext.get("confidence", 0.5))

                # Skip completely empty values, but keep N/A with low confidence
                # so we track that the model looked but didn't find it
                if value.strip() == "":
                    continue

                # Mark N/A values with very low confidence
                if value.lower() in ("n/a", "na", "none", "not found", "not available"):
                    confidence = min(confidence, 0.1)

                extractions.append(PageExtraction(
                    field_name=ext.get("field", ""),
                    value=value,
                    bounding_box=bbox,
                    confidence=confidence,
                    page_number=page_number,
                ))
            except (ValueError, KeyError) as e:
                print(f"  Warning: Failed to parse extraction: {e}")
                continue

        # Parse summary flags
        for flag in data.get("summary_flags", []):
            try:
                summary_flags.append(SummaryFlag(
                    field_name=flag.get("field", ""),
                    relevant_content=flag.get("relevant_content", ""),
                    context=flag.get("context"),
                    page_number=page_number,
                ))
            except (ValueError, KeyError) as e:
                print(f"  Warning: Failed to parse summary flag: {e}")
                continue

        # Parse entity groups
        entity_groups_data = data.get("entity_groups", {})
        for group_name, entities in entity_groups_data.items():
            if not isinstance(entities, list):
                continue
            for entity in entities:
                try:
                    # Handle both {"values": {...}} and direct field values
                    if "values" in entity:
                        values = entity.get("values", {})
                    else:
                        # Entity might have fields directly (excluding metadata keys)
                        values = {k: v for k, v in entity.items()
                                  if k not in ("confidence", "bboxes", "row_bbox_2d", "bbox")}

                    if not values:
                        continue

                    # Parse bounding boxes for each field (optional)
                    bboxes = {}
                    for field_name, bbox_data in entity.get("bboxes", {}).items():
                        if isinstance(bbox_data, list) and len(bbox_data) == 4:
                            try:
                                bbox_data = [int(v) for v in bbox_data]
                                bboxes[field_name] = BoundingBox.from_list(bbox_data)
                            except (ValueError, TypeError):
                                pass

                    # Parse row bounding box (optional)
                    row_bbox = None
                    row_bbox_data = entity.get("row_bbox_2d") or entity.get("bbox")
                    if row_bbox_data and isinstance(row_bbox_data, list) and len(row_bbox_data) == 4:
                        try:
                            row_bbox_data = [int(v) for v in row_bbox_data]
                            row_bbox = BoundingBox.from_list(row_bbox_data)
                        except (ValueError, TypeError):
                            pass

                    confidence = float(entity.get("confidence", 0.8))

                    entity_extractions.append(EntityExtraction(
                        group_name=group_name,
                        values=values,
                        bounding_boxes=bboxes,
                        row_bounding_box=row_bbox,
                        confidence=confidence,
                        page_number=page_number,
                    ))
                except (ValueError, KeyError, TypeError) as e:
                    print(f"  Warning: Failed to parse entity: {e}")
                    continue

        # Parse notes
        notes = data.get("notes", [])

        return extractions, summary_flags, entity_extractions, notes

    def _update_context(
        self,
        context: CumulativeContext,
        extractions: list[PageExtraction],
        summary_flags: list[SummaryFlag],
        entity_extractions: list[EntityExtraction],
        notes: list[str],
        page_number: int,
    ) -> CumulativeContext:
        """
        Update cumulative context with new extractions and flags.

        Args:
            context: Current cumulative context
            extractions: New extractions from this page
            summary_flags: New summary flags from this page
            entity_extractions: New entity extractions from this page
            notes: Cross-page notes from this page
            page_number: Current page number

        Returns:
            Updated CumulativeContext
        """
        # Create a copy of the context
        new_context = CumulativeContext(
            candidates_by_field={k: list(v) for k, v in context.candidates_by_field.items()},
            summary_flags_by_field={k: list(v) for k, v in context.summary_flags_by_field.items()},
            entity_candidates_by_group={k: list(v) for k, v in context.entity_candidates_by_group.items()},
            all_metric_fields=list(context.all_metric_fields),
            all_entity_groups=list(context.all_entity_groups),
            notes=list(context.notes),
        )

        # Add all extractions as candidates (context tracks confidence levels)
        for ext in extractions:
            new_context.add_candidate(
                ext.field_name,
                ext.value,
                page_number,
                ext.confidence,
                bbox={
                    "x1": ext.bounding_box.x1,
                    "y1": ext.bounding_box.y1,
                    "x2": ext.bounding_box.x2,
                    "y2": ext.bounding_box.y2,
                },
            )

        # Add new summary flags
        for flag in summary_flags:
            new_context.add_summary_flag(
                flag.field_name,
                flag.relevant_content,
                page_number,
                flag.context,
            )

        # Add entity extractions
        for entity in entity_extractions:
            bboxes = {}
            for field_name, bbox in entity.bounding_boxes.items():
                bboxes[field_name] = {
                    "x1": bbox.x1, "y1": bbox.y1, "x2": bbox.x2, "y2": bbox.y2
                }

            row_bbox = None
            if entity.row_bounding_box:
                row_bbox = {
                    "x1": entity.row_bounding_box.x1,
                    "y1": entity.row_bounding_box.y1,
                    "x2": entity.row_bounding_box.x2,
                    "y2": entity.row_bounding_box.y2,
                }

            new_context.add_entity_candidate(
                entity.group_name,
                entity.values,
                page_number,
                entity.confidence,
                bboxes=bboxes,
                row_bbox=row_bbox,
            )

        # Add notes
        for note in notes:
            new_context.add_note(note)

        return new_context
