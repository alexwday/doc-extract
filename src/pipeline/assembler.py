"""Document assembly from page results."""

from ..models import (
    PageResult,
    PageExtraction,
    AssembledDocument,
    ExtractionCandidate,
    EntityExtraction,
    ExtractionSchema,
    BoundingBox,
)


class DocumentAssembler:
    """Assembles page results into a complete document extraction."""

    def assemble(
        self,
        page_results: list[PageResult],
        schema: ExtractionSchema,
    ) -> AssembledDocument:
        """
        Combine all page results into document-level data.

        Args:
            page_results: List of results from all pages
            schema: Extraction schema used

        Returns:
            AssembledDocument with combined data
        """
        # Concatenate all markdown with page separators
        full_ocr = "\n\n---\n\n".join([
            f"# Page {r.page_number}\n\n{r.markdown}"
            for r in page_results
        ])

        # Collect all extractions as candidates grouped by field
        candidates_by_field: dict[str, list[ExtractionCandidate]] = {}
        for result in page_results:
            for ext in result.extractions:
                if ext.field_name not in candidates_by_field:
                    candidates_by_field[ext.field_name] = []
                candidates_by_field[ext.field_name].append(
                    ExtractionCandidate(
                        field_name=ext.field_name,
                        value=ext.value,
                        page_number=ext.page_number,
                        confidence=ext.confidence,
                        bounding_box=ext.bounding_box,
                    )
                )

        # Collect all summary flags by field
        summary_flags_by_field: dict[str, list[dict]] = {}
        for result in page_results:
            for flag in result.summary_flags:
                if flag.field_name not in summary_flags_by_field:
                    summary_flags_by_field[flag.field_name] = []
                summary_flags_by_field[flag.field_name].append({
                    "content": flag.relevant_content,
                    "page": result.page_number,
                    "context": flag.context,
                })

        # Collect all entity extractions by group
        entity_candidates_by_group: dict[str, list[EntityExtraction]] = {}
        for result in page_results:
            for entity in result.entity_extractions:
                if entity.group_name not in entity_candidates_by_group:
                    entity_candidates_by_group[entity.group_name] = []
                entity_candidates_by_group[entity.group_name].append(entity)

        return AssembledDocument(
            full_ocr_markdown=full_ocr,
            candidates_by_field=candidates_by_field,
            summary_flags_by_field=summary_flags_by_field,
            entity_candidates_by_group=entity_candidates_by_group,
            page_results=page_results,
            page_count=len(page_results),
        )

    def get_extraction_summary(self, assembled: AssembledDocument) -> str:
        """
        Generate a human-readable summary of extractions.

        Args:
            assembled: Assembled document

        Returns:
            Formatted summary string
        """
        lines = ["=" * 60, "EXTRACTION SUMMARY", "=" * 60, ""]

        # Best extractions (highest confidence per field)
        best = assembled.best_extractions
        if best:
            lines.append("## Best Extractions (highest confidence per field)")
            lines.append("")
            for field_name, ext in sorted(best.items()):
                confidence_str = f"{ext.confidence:.0%}"
                status = "✓" if ext.confidence >= 0.5 else "?"
                lines.append(
                    f"{status} {field_name}: {ext.value} "
                    f"(page {ext.page_number}, {confidence_str})"
                )
            lines.append("")

        # Show all candidates for fields with multiple options
        multi_candidate_fields = [
            f for f, c in assembled.candidates_by_field.items() if len(c) > 1
        ]
        if multi_candidate_fields:
            lines.append("## Fields with Multiple Candidates")
            lines.append("")
            for field_name in sorted(multi_candidate_fields):
                lines.append(f"### {field_name}")
                for candidate in assembled.get_all_candidates(field_name):
                    lines.append(
                        f"  - {candidate.value} (page {candidate.page_number}, "
                        f"{candidate.confidence:.0%})"
                    )
            lines.append("")

        # Summary flags collected
        if assembled.summary_flags_by_field:
            lines.append("## Summary Content Flagged")
            lines.append("")
            for field_name, flags in assembled.summary_flags_by_field.items():
                lines.append(f"### {field_name}")
                for flag in flags:
                    content = flag["content"][:100]
                    lines.append(f"  - Page {flag['page']}: {content}...")
            lines.append("")

        # Statistics
        total_candidates = sum(len(c) for c in assembled.candidates_by_field.values())
        high_conf = sum(
            1 for ext in best.values() if ext.confidence >= 0.5
        )
        low_conf = len(best) - high_conf

        lines.append("## Statistics")
        lines.append(f"- Pages processed: {assembled.page_count}")
        lines.append(f"- Total candidates: {total_candidates}")
        lines.append(f"- Fields extracted: {len(best)}")
        lines.append(f"  - High confidence (≥50%): {high_conf}")
        lines.append(f"  - Low confidence (<50%): {low_conf}")
        lines.append(f"- Summary fields flagged: {len(assembled.summary_flags_by_field)}")

        return "\n".join(lines)
