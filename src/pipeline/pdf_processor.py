"""PDF to images conversion."""

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from ..models import PageImage


class PDFProcessor:
    """Converts PDF documents to page images."""

    def __init__(self, dpi: int = 150, temp_dir: Optional[Path] = None):
        """
        Initialize the PDF processor.

        Args:
            dpi: Resolution for rendering (150 balances quality vs memory for 16GB Macs)
            temp_dir: Directory for temporary images (default: .temp_images in PDF dir)
        """
        self.dpi = dpi
        self.temp_dir = temp_dir

    def process(self, pdf_path: str | Path) -> list[PageImage]:
        """
        Convert PDF to page images.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of PageImage objects with paths and metadata
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Set up temp directory
        temp_dir = self.temp_dir or (pdf_path.parent / ".temp_images")
        temp_dir.mkdir(exist_ok=True)

        doc = fitz.open(str(pdf_path))
        pages = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Save to temp file (MLX-VLM works better with file paths)
                image_path = temp_dir / f"page_{page_num + 1}.png"
                img.save(image_path)

                pages.append(PageImage(
                    page_number=page_num + 1,
                    image_path=str(image_path),
                    width=pix.width,
                    height=pix.height,
                ))

                print(f"  Converted page {page_num + 1}/{len(doc)}")

        finally:
            doc.close()

        return pages

    def cleanup(self, pages: list[PageImage]) -> None:
        """
        Remove temporary image files.

        Args:
            pages: List of PageImage objects to clean up
        """
        for page in pages:
            path = Path(page.image_path)
            if path.exists():
                path.unlink()

        # Try to remove temp directory if empty
        if pages:
            temp_dir = Path(pages[0].image_path).parent
            try:
                temp_dir.rmdir()
            except OSError:
                pass  # Directory not empty or other issue
