"""Extraction service - DeepSeek OCR + OpenAI extraction pipeline."""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
# Add src to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models import ExtractionSchema, ExtractionField, FieldType, EntityGroup, EntityGroupField
from src.vlm import VLMModel
from src.pipeline import OpenAIExtractor

from .storage import storage
from ..config import PDF_DPI, VLM_MODEL


class ExtractionService:
    """Service for running document extractions.

    Pipeline:
    1. DeepSeek-OCR-2: OCR each page to text
    2. OpenAI: Extract all fields and entity groups from combined OCR text
    """

    def __init__(self):
        self._ocr_model: Optional[VLMModel] = None
        self._ocr_model_loaded = False
        self._openai_extractor: Optional[OpenAIExtractor] = None

    def _ensure_ocr_model_loaded(self):
        """Lazy load the OCR model."""
        if not self._ocr_model_loaded:
            print(f"Loading OCR model: {VLM_MODEL}")
            self._ocr_model = VLMModel(VLM_MODEL)
            self._ocr_model.load()
            self._ocr_model_loaded = True
            print("OCR model loaded")

    def _ensure_openai_extractor(self):
        """Lazy load the OpenAI extractor."""
        if self._openai_extractor is None:
            self._openai_extractor = OpenAIExtractor()

    def _template_to_schema(self, template: dict) -> ExtractionSchema:
        """Convert API template to ExtractionSchema."""
        fields = []
        for f in template.get("fields", []):
            field_type_str = f.get("field_type", "metric")
            field_type = FieldType(field_type_str)

            fields.append(ExtractionField(
                name=f["name"],
                display_name=f.get("display_name", f["name"]),
                field_type=field_type,
                description=f.get("description", ""),
                expected_format=f.get("expected_format"),
                table_hint=f.get("table_hint"),
            ))

        # Convert entity groups
        entity_groups = []
        for g in template.get("entity_groups", []):
            group_fields = []
            for gf in g.get("fields", []):
                group_fields.append(EntityGroupField(
                    name=gf["name"],
                    display_name=gf.get("display_name", gf["name"]),
                    description=gf.get("description", ""),
                    expected_format=gf.get("expected_format"),
                ))
            entity_groups.append(EntityGroup(
                name=g["name"],
                display_name=g.get("display_name", g["name"]),
                description=g.get("description", ""),
                fields=group_fields,
            ))

        return ExtractionSchema(
            name=template.get("name", ""),
            description=template.get("description", ""),
            fields=fields,
            entity_groups=entity_groups,
        )

    def run_extraction(
        self,
        document_id: str,
        template_id: str,
        verify: bool = True,  # Kept for API compatibility, but always uses OpenAI now
        progress_callback: callable = None,
    ) -> dict:
        """
        Run extraction on a document using a template.

        Pipeline:
        1. OCR each page with DeepSeek-OCR-2
        2. Extract all fields/entities with OpenAI from combined OCR

        Args:
            document_id: ID of the document to extract from
            template_id: ID of the template to use
            verify: Ignored (always uses OpenAI for extraction now)
            progress_callback: Optional callback for progress updates

        Returns:
            Extraction result dict
        """
        # Load document and template
        document = storage.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        template = storage.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Convert template to schema
        schema = self._template_to_schema(template)

        # Ensure models are loaded
        self._ensure_ocr_model_loaded()
        self._ensure_openai_extractor()

        start_time = datetime.utcnow()

        # Get page images
        from ..config import DOCUMENTS_DIR
        doc_dir = DOCUMENTS_DIR / document_id
        pages_dir = doc_dir / "pages"

        # === PHASE 1: OCR all pages ===
        print(f"Phase 1: OCR ({document['page_count']} pages)...")
        ocr_by_page = {}

        for page_num in range(1, document["page_count"] + 1):
            image_path = pages_dir / f"page_{page_num}.png"
            if image_path.exists():
                print(f"  OCR page {page_num}...")
                ocr_text = self._ocr_model.ocr_page(str(image_path))
                ocr_by_page[page_num] = ocr_text
                print(f"    -> {len(ocr_text)} chars")

                if progress_callback:
                    # Progress: OCR is 50% of total work
                    progress_callback(page_num, document["page_count"] * 2)

        # Combine OCR for full document markdown
        full_ocr_markdown = "\n\n---\n\n".join([
            f"# Page {page_num}\n\n{text}"
            for page_num, text in sorted(ocr_by_page.items())
        ])

        # === PHASE 2: OpenAI extraction ===
        print("Phase 2: OpenAI extraction...")

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable not set")

        extractions_list, entity_groups_dict = self._openai_extractor.extract_all(
            ocr_by_page, schema
        )

        if progress_callback:
            progress_callback(document["page_count"] * 2, document["page_count"] * 2)

        # Calculate timing
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Build result
        result_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        # Format extractions
        extractions = {}
        for v in extractions_list:
            extractions[v.field_name] = {
                "field_name": v.field_name,
                "display_name": v.display_name,
                "field_type": v.field_type.value,
                "value": v.value,
                "page": v.page,
                "confidence": v.confidence,
                "verified": v.verified,
                "verification_notes": v.verification_notes,
                "bounding_box": None,  # No bounding boxes in new pipeline
                "source_pages": getattr(v, 'source_pages', None),
            }

        # Format entity groups
        entity_groups_out = {}
        for group_name, verified_group in entity_groups_dict.items():
            entity_groups_out[group_name] = {
                "name": verified_group.group_name,
                "display_name": verified_group.display_name,
                "entities": [
                    {
                        "values": e.values,
                        "page": e.page,
                        "confidence": e.confidence,
                        "bounding_boxes": None,  # No bounding boxes in new pipeline
                        "row_bounding_box": None,
                    }
                    for e in verified_group.entities
                ],
            }

        result = {
            "id": result_id,
            "document_id": document_id,
            "document_name": document.get("filename", ""),
            "template_id": template_id,
            "template_name": template.get("name", ""),
            "extracted_at": now,
            "processing_time_seconds": processing_time,
            "verified": True,  # Always verified via OpenAI now
            "extractions": extractions,
            "all_candidates": {},  # No candidates in new pipeline
            "entity_groups": entity_groups_out,
            "full_ocr_markdown": full_ocr_markdown,
        }

        # Save result
        storage.save_result(result)

        return result


# Singleton instance
extraction_service = ExtractionService()
