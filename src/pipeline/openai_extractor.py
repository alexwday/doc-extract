"""OpenAI-based extraction from OCR text."""

import json
import os
from typing import Optional

from openai import OpenAI

from ..models import (
    ExtractionSchema,
    FieldType,
    BoundingBox,
)
from .verifier import VerifiedExtraction, VerifiedEntity, VerifiedEntityGroup


class OpenAIExtractor:
    """Extracts structured data from OCR text using OpenAI."""

    def __init__(
        self,
        model: str = "gpt-4.1",
        api_key: Optional[str] = None,
    ):
        """
        Initialize the extractor.

        Args:
            model: OpenAI model to use (default: gpt-4.1)
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
        """
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def extract_all(
        self,
        ocr_by_page: dict[int, str],
        schema: ExtractionSchema,
    ) -> tuple[list[VerifiedExtraction], dict[str, VerifiedEntityGroup]]:
        """
        Extract all fields and entity groups from OCR text.

        Args:
            ocr_by_page: Dict mapping page number to OCR text
            schema: Extraction schema defining what to extract

        Returns:
            Tuple of (list of extractions, dict of entity groups)
        """
        # Combine OCR with page markers
        full_ocr = self._combine_ocr(ocr_by_page)

        results = []
        entity_groups = {}

        # Step 1: Extract metrics and text fields
        print("  Extracting metrics and text fields...")
        metric_extractions = self._extract_metrics(full_ocr, schema)

        for field_name, extraction in metric_extractions.items():
            field = schema.get_field(field_name)
            if not field:
                continue

            results.append(VerifiedExtraction(
                field_name=field_name,
                display_name=field.display_name,
                field_type=field.field_type,
                value=extraction.get("value", ""),
                page=extraction.get("page", 1),
                bounding_box=None,  # No bounding boxes from text extraction
                verified=True,  # OpenAI extracted it directly
                verification_notes=extraction.get("notes"),
                confidence=extraction.get("confidence", 0.9),
            ))

        # Step 2: Synthesize summaries
        print("  Synthesizing summaries...")
        for summary_field in schema.summary_fields:
            synthesis = self._synthesize_summary(summary_field, full_ocr)

            source_pages = synthesis.get("source_pages", [])
            results.append(VerifiedExtraction(
                field_name=summary_field.name,
                display_name=summary_field.display_name,
                field_type=FieldType.SUMMARY,
                value=synthesis.get("summary", ""),
                page=source_pages[0] if source_pages else 1,
                bounding_box=None,
                verified=True,
                verification_notes=f"Synthesized from pages: {source_pages}",
                confidence=synthesis.get("confidence", 0.8),
                source_pages=source_pages,
            ))

        # Step 3: Extract entity groups
        print("  Extracting entity groups...")
        for entity_group in schema.entity_groups:
            verified_group = self._extract_entity_group(entity_group, full_ocr)
            entity_groups[entity_group.name] = verified_group
            print(f"    {entity_group.name}: {len(verified_group.entities)} entities")

        return results, entity_groups

    def _combine_ocr(self, ocr_by_page: dict[int, str]) -> str:
        """Combine OCR text from all pages with page markers."""
        pages = []
        for page_num in sorted(ocr_by_page.keys()):
            text = ocr_by_page[page_num]
            pages.append(f"=== PAGE {page_num} ===\n\n{text}")
        return "\n\n".join(pages)

    def _extract_metrics(
        self,
        full_ocr: str,
        schema: ExtractionSchema,
    ) -> dict[str, dict]:
        """
        Extract metric and text fields from OCR.

        Returns dict of {field_name: {value, page, confidence, notes}}
        """
        # Build field descriptions
        field_descriptions = []
        for field in schema.fields:
            if field.field_type == FieldType.SUMMARY:
                continue
            desc = f"- {field.name}: {field.description}"
            if field.expected_format:
                desc += f" (expected format: {field.expected_format})"
            field_descriptions.append(desc)

        if not field_descriptions:
            return {}

        prompt = f"""You are extracting structured data from document OCR text.

## Document Text (OCR)

{full_ocr}

## Fields to Extract

{chr(10).join(field_descriptions)}

## Instructions

1. Find each field's value in the OCR text
2. Extract the EXACT value as it appears in the document
3. Note which page the value was found on
4. If a value appears multiple times, use the most authoritative/prominent occurrence

Return JSON in this exact format:
{{
    "extractions": {{
        "field_name": {{
            "value": "the extracted value exactly as written",
            "page": 1,
            "confidence": 0.95,
            "notes": "optional notes about the extraction"
        }}
    }}
}}

Rules:
- Extract values EXACTLY as they appear (preserve formatting, symbols, etc.)
- page should be the page number where the value was found
- confidence should reflect how certain you are (0.0 to 1.0)
- Include all fields, even if not found (value: null for missing fields)
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("extractions", {})

        except Exception as e:
            print(f"    Warning: Metric extraction failed: {e}")
            return {}

    def _synthesize_summary(
        self,
        field,
        full_ocr: str,
    ) -> dict:
        """
        Synthesize a summary answer from OCR text.

        Returns {summary, source_pages, confidence}
        """
        prompt = f"""You are synthesizing a summary from document content.

## Summary Field
Name: {field.name}
Description: {field.description}

## Full Document Text (OCR)

{full_ocr}

## Instructions

1. Read through the document to find content relevant to "{field.description}"
2. Synthesize a comprehensive answer based on the document content
3. Keep the summary concise but complete (2-4 sentences)
4. Reference specific facts and figures where relevant
5. Note which pages contained the relevant information

Return JSON in this exact format:
{{
    "summary": "your synthesized summary",
    "source_pages": [1, 2],
    "confidence": 0.9
}}

Rules:
- source_pages should list all pages where key information was found
- confidence should reflect how well the document content answers the question
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
            return {
                "summary": "Unable to synthesize summary",
                "source_pages": [],
                "confidence": 0.5,
            }

    def _extract_entity_group(
        self,
        entity_group,
        full_ocr: str,
    ) -> VerifiedEntityGroup:
        """
        Extract all entities for an entity group from OCR text.

        Args:
            entity_group: The entity group definition
            full_ocr: Full OCR text

        Returns:
            VerifiedEntityGroup with extracted entities
        """
        field_descriptions = "\n".join([
            f"  - {f.name}: {f.description}" + (f" (format: {f.expected_format})" if f.expected_format else "")
            for f in entity_group.fields
        ])

        prompt = f"""You are extracting structured entity data from document OCR text.

## Entity Group: {entity_group.name}
Description: {entity_group.description}

Fields to extract for each entity:
{field_descriptions}

## Full Document Text (OCR)

{full_ocr}

## Instructions

1. Find ALL entities (rows/items) that belong to this entity group in the document
2. Extract all required fields for each entity
3. Note which page each entity was found on
4. Preserve exact values as they appear in the document

Return JSON in this exact format:
{{
    "entities": [
        {{
            "values": {{
                "field1": "value1",
                "field2": "value2"
            }},
            "page": 1,
            "confidence": 0.95
        }}
    ]
}}

Rules:
- Extract ALL entities found, even if they span multiple pages
- Each entity must have values for all defined fields
- Use null for fields that are not found for a specific entity
- confidence reflects certainty about the extraction
- Return ONLY valid JSON"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )

            result = json.loads(response.choices[0].message.content)
            entities_data = result.get("entities", [])

            verified_entities = []
            for entity_data in entities_data:
                values = entity_data.get("values", {})

                # Skip entities with all null/empty values
                if not any(v for v in values.values() if v):
                    continue

                verified_entities.append(VerifiedEntity(
                    values=values,
                    page=entity_data.get("page", 1),
                    confidence=entity_data.get("confidence", 0.9),
                    bounding_boxes={},  # No bounding boxes from text extraction
                    row_bounding_box=None,
                    verified=True,
                ))

            return VerifiedEntityGroup(
                group_name=entity_group.name,
                display_name=entity_group.display_name,
                entities=verified_entities,
            )

        except Exception as e:
            print(f"    Warning: Entity extraction failed for {entity_group.name}: {e}")
            return VerifiedEntityGroup(
                group_name=entity_group.name,
                display_name=entity_group.display_name,
                entities=[],
            )
