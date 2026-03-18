"""Annotation service - renders bounding boxes on page images."""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
import colorsys

from .storage import storage
from ..config import DOCUMENTS_DIR


# Pre-defined distinct colors for fields (more visually distinct than HSV generation)
FIELD_COLORS = [
    (220, 38, 38),   # Red
    (37, 99, 235),   # Blue
    (22, 163, 74),   # Green
    (217, 119, 6),   # Amber
    (147, 51, 234),  # Purple
    (236, 72, 153),  # Pink
    (6, 182, 212),   # Cyan
    (249, 115, 22),  # Orange
]


class AnnotationService:
    """Service for rendering bounding box annotations on page images."""

    def render_annotated_page(
        self,
        document_id: str,
        page_number: int,
        result_id: str,
        highlight_field: Optional[str] = None,
    ) -> Optional[Image.Image]:
        """
        Render a page image with bounding box annotations.

        Args:
            document_id: Document ID
            page_number: Page number (1-indexed)
            result_id: Extraction result ID to get bboxes from
            highlight_field: Optional field name to highlight (others will be dimmed)

        Returns:
            PIL Image with annotations, or None if not found
        """
        # Get page image
        image_path = storage.get_page_image_path(document_id, page_number)
        if not image_path:
            return None

        # Get extraction result
        result = storage.get_result(result_id)
        if not result:
            return None

        # Load image
        img = Image.open(image_path).convert("RGBA")
        img_width, img_height = img.size

        # Get all field names for consistent color assignment
        extractions = result.get("extractions", {})
        field_names = sorted(extractions.keys())
        field_colors = {name: FIELD_COLORS[i % len(FIELD_COLORS)] for i, name in enumerate(field_names)}

        # Create overlay for annotations
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Load font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
            small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
        except:
            font = ImageFont.load_default()
            small_font = font

        # Draw bounding boxes for this page
        for field_name, extraction in extractions.items():
            if extraction.get("page") != page_number:
                continue

            bbox = extraction.get("bounding_box")
            if not bbox:
                continue

            # Convert from 0-1000 normalized to pixel coordinates
            x1 = int(bbox["x1"] * img_width / 1000)
            y1 = int(bbox["y1"] * img_height / 1000)
            x2 = int(bbox["x2"] * img_width / 1000)
            y2 = int(bbox["y2"] * img_height / 1000)

            # Get color for this field
            color = field_colors.get(field_name, (255, 0, 0))

            # Determine if this field is highlighted or dimmed
            is_highlighted = highlight_field == field_name
            is_dimmed = highlight_field is not None and not is_highlighted

            if is_dimmed:
                # Very faint for non-highlighted fields
                fill_alpha = 10
                outline_alpha = 60
                line_width = 1
            elif is_highlighted:
                # Bold for highlighted field
                fill_alpha = 50
                outline_alpha = 255
                line_width = 3
            else:
                # Normal when nothing is highlighted
                fill_alpha = 30
                outline_alpha = 200
                line_width = 2

            # Draw filled rectangle
            draw.rectangle(
                [x1, y1, x2, y2],
                fill=(*color, fill_alpha),
                outline=(*color, outline_alpha),
                width=line_width
            )

            # Draw label (skip if dimmed)
            if not is_dimmed:
                label = extraction.get("display_name", field_name)
                value = extraction.get("value", "")
                if len(value) > 20:
                    label_text = f"{label}: {value[:20]}..."
                else:
                    label_text = f"{label}: {value}"

                # Position label above the box, or below if too close to top
                label_y = y1 - 20 if y1 > 25 else y2 + 4

                text_bbox = draw.textbbox((x1, label_y), label_text, font=small_font)

                # Draw label background
                padding = 3
                draw.rectangle(
                    [text_bbox[0] - padding, text_bbox[1] - padding,
                     text_bbox[2] + padding, text_bbox[3] + padding],
                    fill=(255, 255, 255, 230),
                    outline=(*color, outline_alpha),
                    width=1
                )
                draw.text((x1, label_y), label_text, fill=(*color, 255), font=small_font)

        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)
        return img.convert('RGB')

    def get_extractions_for_page(
        self,
        result_id: str,
        page_number: int,
    ) -> list[dict]:
        """
        Get all extractions for a specific page.

        Args:
            result_id: Extraction result ID
            page_number: Page number (1-indexed)

        Returns:
            List of extractions on this page
        """
        result = storage.get_result(result_id)
        if not result:
            return []

        extractions = []
        for field_name, extraction in result.get("extractions", {}).items():
            if extraction.get("page") == page_number:
                extractions.append(extraction)

        return extractions


# Singleton instance
annotation_service = AnnotationService()
