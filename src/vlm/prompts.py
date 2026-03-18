"""Prompt templates for VLM extraction."""

from ..models import ExtractionSchema, CumulativeContext


class PromptBuilder:
    """Builder for VLM prompts."""

    @staticmethod
    def ocr_prompt() -> str:
        """
        Build the pure OCR prompt (Pass 1).

        No extraction context - just converts page to markdown.
        """
        return """Convert this document page to clean markdown.

Rules:
- Preserve all text exactly as written
- Preserve numbers exactly as written; do not normalize or reformat them
- Use markdown headings (#, ##, ###) for section titles
- Use markdown tables for tabular data
- Use bullet points for lists
- Do not add interpretation or commentary
- Do not summarize - include ALL text"""

    @staticmethod
    def extraction_prompt(
        schema: ExtractionSchema,
        context: CumulativeContext,
    ) -> str:
        """
        Build the extraction prompt (Pass 2).

        Includes schema fields and cumulative context from prior pages.
        """
        # Build entity groups section if any are defined
        entity_groups_section = ""
        if schema.entity_groups:
            entity_groups_section = f"""
## Entity Groups (extract ALL rows from tables)

{schema.format_entity_groups()}

IMPORTANT for entity groups:
- Extract EVERY row/entity visible in the table on this page
- Each entity needs values for ALL fields listed above
- Do NOT skip any rows - extract the complete table
"""

        # Build entity groups response format if any are defined
        entity_groups_response = ""
        if schema.entity_groups:
            # Use actual group names for clarity
            group_examples = []
            for g in schema.entity_groups:
                field_examples = ", ".join([f'"{f.name}": "..."' for f in g.fields[:3]])
                if len(g.fields) > 3:
                    field_examples += ", ..."
                group_examples.append(f'"{g.name}": [{{"values": {{{field_examples}}}, "confidence": 0.9}}]')

            entity_groups_response = ',\n    "entity_groups": {' + ", ".join(group_examples) + '}'

        prompt = f"""You are extracting structured data from a document page.

## Fields to Extract (with precise bounding boxes)

{schema.format_metric_fields()}

## Fields to Flag Content For (summaries - no bbox needed)

{schema.format_summary_fields()}
{entity_groups_section}
{context.to_prompt_context()}

## Instructions

1. For METRIC/TEXT/TABLE_CELL fields:
   - Find the value on this page if present
   - The value must be the EXACT text span as it appears on the page; do not reformat, round, or change units
   - Copy the text verbatim from the document
   - Return a TIGHT bounding box around ONLY the value text itself
   - The bbox must surround just the extracted value (e.g., "$147.3 million"), NOT the entire sentence or line
   - When the value is inside a sentence or paragraph, box ONLY the exact words/numbers/units for that value with minimal padding (~1-3 units on the 0-1000 scale)
   - Do NOT include neighboring words, bullets, or the full text line; aim for word/phrase-level precision
   - Use normalized coordinates from 0-1000 (0,0 is top-left, 1000,1000 is bottom-right) for bbox_2d
   - Ensure x1 < x2 and y1 < y2
   - If already extracted on a previous page, only extract again if this page has a MORE RELEVANT value

2. For SUMMARY fields:
   - Do NOT try to answer the summary
   - Instead, FLAG any content on this page that is RELEVANT to answering it
   - Include a brief snippet of the relevant content

3. For ENTITY GROUPS:
   - Extract ALL rows from the table for each entity group
   - Each row needs values for all defined fields
   - Return as an array of objects with "values" and "confidence"

4. If a table continues from a previous page, note this

## Response Format

Return ONLY the raw JSON object (no markdown code fences, no ```json wrapper) in this exact format:
{{
    "extractions": [
        {{
            "field": "field_name",
            "value": "extracted value",
            "bbox_2d": [x1, y1, x2, y2],
            "confidence": 0.95
        }}
    ],
    "summary_flags": [
        {{
            "field": "summary_field_name",
            "relevant_content": "snippet of relevant text...",
            "context": "optional context about why this is relevant"
        }}
    ],
    "notes": ["any cross-page observations, e.g., 'table continues from page 1'"]{entity_groups_response}
}}

IMPORTANT for bounding boxes:
- bbox_2d coordinates are [x_min, y_min, x_max, y_max] normalized on a 0-1000 scale (0,0 top-left; 1000,1000 bottom-right)
- Ensure x1 < x2 and y1 < y2
- The box must TIGHTLY surround ONLY the value text, not the surrounding sentence
- Anchor top-left at the first character and bottom-right at the last character; keep padding minimal (~1-3 units on the 0-1000 scale)
- For "$147.3 million", box only those characters, not "total revenue reaching $147.3 million"
- Paragraph example (GOOD): Sentence "Total revenue reached $147.3 million in 2024." -> bbox_2d hugs only "$147.3 million" with tight width/height (e.g., [120, 410, 240, 442])
- Paragraph example (BAD): One wide box covering the entire sentence or row
- Table example (GOOD): Cell "Net income | 52.1" -> bbox_2d encloses just "52.1" (e.g., [620, 530, 680, 552]), not the whole row
- confidence must be a float between 0.0 and 1.0 (not a percentage)

If no extractions or flags found on this page, return empty arrays.
Return ONLY the JSON, no other text."""

        return prompt

    @staticmethod
    def simple_extraction_prompt(
        fields: list[str],
        context: CumulativeContext = None,
    ) -> str:
        """
        Build a simplified extraction prompt for testing.

        Args:
            fields: List of field descriptions (e.g., ["Total Revenue", "Net Income"])
            context: Optional cumulative context
        """
        field_list = "\n".join(f"- {f}" for f in fields)
        context_text = context.to_prompt_context() if context else ""

        return f"""Extract these values from the document:

{field_list}

{context_text}

For each value found, provide:
1. The field name
2. The extracted value
   - The value must be the EXACT text span as it appears on the page; do not reformat, round, or change units
   - Copy the text verbatim from the document
3. bbox_2d = [x_min, y_min, x_max, y_max] normalized on a 0-1000 scale (0,0 top-left; 1000,1000 bottom-right), TIGHT around ONLY the value text
   - Anchor top-left at the first character and bottom-right at the last character; add only minimal padding (~1-3 units on the 0-1000 scale)
   - If inside a paragraph, box only the exact words/numbers/units for the value
   - Do not include neighboring words, bullets, or the full sentence width
   - Ensure x1 < x2 and y1 < y2
   - Paragraph example (GOOD): Sentence "Total revenue reached $147.3 million in 2024." -> bbox_2d hugs only "$147.3 million" (e.g., [120, 410, 240, 442])
   - Paragraph example (BAD): One wide box covering the entire sentence

Return ONLY the raw JSON object (no markdown code fences, no ```json wrapper):
{{
    "extractions": [
        {{"field": "...", "value": "...", "bbox_2d": [x1, y1, x2, y2], "confidence": 0.95}}
    ]
}}

IMPORTANT:
- bbox_2d must tightly surround ONLY the value itself, not the entire sentence
- confidence must be a float between 0.0 and 1.0 (not a percentage)"""
