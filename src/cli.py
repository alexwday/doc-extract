#!/usr/bin/env python3
"""
CLI for testing the document extraction pipeline.

Usage:
    python -m src.cli <pdf_path> [--schema <schema_path>] [--verify]
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from .models import ExtractionSchema, ExtractionField, FieldType, CumulativeContext
from .vlm import VLMModel
from .pipeline import (
    PDFProcessor,
    PageProcessor,
    DocumentAssembler,
    DocumentVerifier,
    get_verification_summary,
)


def create_sample_schema() -> ExtractionSchema:
    """Create a sample schema for quarterly reports."""
    return ExtractionSchema(
        name="Quarterly Report",
        description="Extract key metrics from a quarterly financial report",
        fields=[
            ExtractionField(
                name="total_revenue",
                display_name="Total Revenue",
                field_type=FieldType.METRIC,
                description="Total revenue for the quarter",
                expected_format="currency",
            ),
            ExtractionField(
                name="net_income",
                display_name="Net Income",
                field_type=FieldType.METRIC,
                description="Net income for the quarter",
                expected_format="currency",
            ),
            ExtractionField(
                name="gross_margin",
                display_name="Gross Margin",
                field_type=FieldType.METRIC,
                description="Gross margin percentage",
                expected_format="percentage",
            ),
            ExtractionField(
                name="yoy_growth",
                display_name="YoY Growth",
                field_type=FieldType.METRIC,
                description="Year-over-year revenue growth percentage",
                expected_format="percentage",
            ),
            ExtractionField(
                name="customer_count",
                display_name="Customer Count",
                field_type=FieldType.METRIC,
                description="Total number of active customers",
                expected_format="number",
            ),
            ExtractionField(
                name="total_assets",
                display_name="Total Assets",
                field_type=FieldType.TABLE_CELL,
                description="Total assets from balance sheet",
                expected_format="currency",
                table_hint="Balance Sheet",
            ),
            ExtractionField(
                name="cash_equivalents",
                display_name="Cash & Equivalents",
                field_type=FieldType.TABLE_CELL,
                description="Cash and cash equivalents from balance sheet",
                expected_format="currency",
                table_hint="Balance Sheet",
            ),
            ExtractionField(
                name="performance_summary",
                display_name="Performance Summary",
                field_type=FieldType.SUMMARY,
                description="Overall summary of the company's quarterly performance",
            ),
            ExtractionField(
                name="outlook",
                display_name="Forward Outlook",
                field_type=FieldType.SUMMARY,
                description="Forward-looking statements and guidance",
            ),
        ],
    )


def run_extraction(
    pdf_path: str,
    schema: ExtractionSchema,
    verify: bool = False,
) -> dict:
    """
    Run the full extraction pipeline.

    Args:
        pdf_path: Path to PDF file
        schema: Extraction schema to use
        verify: Whether to run OpenAI verification

    Returns:
        Dictionary with extraction results
    """
    print("=" * 60)
    print("Document Extraction Pipeline")
    print("=" * 60)

    start_time = datetime.now()

    # Step 1: Convert PDF to images (150 DPI for memory efficiency on 16GB Macs)
    print(f"\n1. Converting PDF: {pdf_path}")
    pdf_processor = PDFProcessor(dpi=150)
    pages = pdf_processor.process(pdf_path)
    print(f"   Converted {len(pages)} pages")

    # Step 2: Load VLM model
    print("\n2. Loading VLM model...")
    model = VLMModel()
    model.load()

    # Step 3: Process each page
    print("\n3. Processing pages...")
    page_processor = PageProcessor(model)
    context = CumulativeContext.from_schema(schema)
    page_results = []

    for page in pages:
        result, context = page_processor.process_page(page, schema, context)
        page_results.append(result)

    # Step 4: Assemble results
    print("\n4. Assembling results...")
    assembler = DocumentAssembler()
    assembled = assembler.assemble(page_results, schema)

    # Print extraction summary
    print("\n" + assembler.get_extraction_summary(assembled))

    # Step 5: Optional verification
    verified_results = None
    if verify:
        print("\n5. Running OpenAI verification...")
        if not os.getenv("OPENAI_API_KEY"):
            print("   Warning: OPENAI_API_KEY not set, skipping verification")
        else:
            verifier = DocumentVerifier()
            verified_results = verifier.verify_and_synthesize(assembled, schema)
            print("\n" + get_verification_summary(verified_results))

    # Calculate timing
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\nTotal processing time: {elapsed:.1f} seconds")

    # Build output
    best = assembled.best_extractions

    output = {
        "document": str(pdf_path),
        "schema": schema.name,
        "extracted_at": datetime.now().isoformat(),
        "processing_time_seconds": elapsed,
        "page_count": assembled.page_count,
        "verified": verify and verified_results is not None,
    }

    if verified_results:
        # Use verified results
        output["extractions"] = {
            v.field_name: v.to_dict()
            for v in verified_results
        }
    else:
        # Use raw VLM results
        output["extractions"] = {
            field: {
                "value": ext.value,
                "page": ext.page_number,
                "confidence": ext.confidence,
                "bounding_box": {
                    "x1": ext.bounding_box.x1,
                    "y1": ext.bounding_box.y1,
                    "x2": ext.bounding_box.x2,
                    "y2": ext.bounding_box.y2,
                } if ext.bounding_box else None,
            }
            for field, ext in best.items()
        }
        output["summary_flags"] = assembled.summary_flags_by_field

    # Always include all candidates for reference
    output["all_candidates"] = {
        field: [
            {
                "value": c.value,
                "page": c.page_number,
                "confidence": c.confidence,
                "bounding_box": {
                    "x1": c.bounding_box.x1,
                    "y1": c.bounding_box.y1,
                    "x2": c.bounding_box.x2,
                    "y2": c.bounding_box.y2,
                } if c.bounding_box else None,
            }
            for c in candidates
        ]
        for field, candidates in assembled.candidates_by_field.items()
    }

    output["full_ocr_markdown"] = assembled.full_ocr_markdown

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured data from PDF documents"
    )
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument(
        "--schema",
        "-s",
        help="Path to schema JSON file (default: sample quarterly report schema)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Path to output JSON file (default: stdout)",
    )
    parser.add_argument(
        "--verify",
        "-v",
        action="store_true",
        help="Run OpenAI verification and summary synthesis (requires OPENAI_API_KEY)",
    )

    args = parser.parse_args()

    # Check PDF exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Load or create schema
    if args.schema:
        with open(args.schema) as f:
            schema_data = json.load(f)
        schema = ExtractionSchema(**schema_data)
    else:
        print("Using sample quarterly report schema")
        schema = create_sample_schema()

    # Run extraction
    try:
        result = run_extraction(str(pdf_path), schema, verify=args.verify)
    except Exception as e:
        print(f"Error during extraction: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    else:
        print("\n" + "=" * 60)
        print("EXTRACTION RESULTS (JSON)")
        print("=" * 60)
        # Print extractions without full OCR for readability
        print(json.dumps({
            k: v for k, v in result.items()
            if k != "full_ocr_markdown"
        }, indent=2))


if __name__ == "__main__":
    main()
