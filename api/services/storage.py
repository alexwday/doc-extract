"""Filesystem storage service for templates, documents, and results."""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from ..config import (
    TEMPLATES_DIR,
    DOCUMENTS_DIR,
    RESULTS_DIR,
    JOBS_DIR,
    EXPORTS_DIR,
    PDF_DPI,
)


class StorageService:
    """Service for managing local filesystem storage."""

    # =========================================================================
    # Templates
    # =========================================================================

    def list_templates(self) -> list[dict]:
        """List all templates."""
        templates = []
        for path in TEMPLATES_DIR.glob("*.json"):
            with open(path) as f:
                templates.append(json.load(f))
        return sorted(templates, key=lambda t: t.get("updated_at", ""), reverse=True)

    def get_template(self, template_id: str) -> Optional[dict]:
        """Get a template by ID."""
        path = TEMPLATES_DIR / f"{template_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def create_template(self, data: dict) -> dict:
        """Create a new template."""
        template_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        template = {
            "id": template_id,
            "name": data["name"],
            "description": data.get("description", ""),
            "fields": data.get("fields", []),
            "created_at": now,
            "updated_at": now,
        }

        path = TEMPLATES_DIR / f"{template_id}.json"
        with open(path, "w") as f:
            json.dump(template, f, indent=2)

        return template

    def update_template(self, template_id: str, data: dict) -> Optional[dict]:
        """Update an existing template."""
        template = self.get_template(template_id)
        if not template:
            return None

        if "name" in data and data["name"] is not None:
            template["name"] = data["name"]
        if "description" in data and data["description"] is not None:
            template["description"] = data["description"]
        if "fields" in data and data["fields"] is not None:
            template["fields"] = data["fields"]

        template["updated_at"] = datetime.utcnow().isoformat() + "Z"

        path = TEMPLATES_DIR / f"{template_id}.json"
        with open(path, "w") as f:
            json.dump(template, f, indent=2)

        return template

    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        path = TEMPLATES_DIR / f"{template_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    # =========================================================================
    # Documents
    # =========================================================================

    def list_documents(self) -> list[dict]:
        """List all documents."""
        documents = []
        for doc_dir in DOCUMENTS_DIR.iterdir():
            if doc_dir.is_dir():
                metadata_path = doc_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path) as f:
                        documents.append(json.load(f))
        return sorted(documents, key=lambda d: d.get("uploaded_at", ""), reverse=True)

    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document metadata by ID."""
        metadata_path = DOCUMENTS_DIR / document_id / "metadata.json"
        if not metadata_path.exists():
            return None
        with open(metadata_path) as f:
            return json.load(f)

    def save_document(self, filename: str, content: bytes) -> dict:
        """Save an uploaded PDF and generate page images."""
        document_id = str(uuid.uuid4())
        doc_dir = DOCUMENTS_DIR / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Save original PDF
        pdf_path = doc_dir / "original.pdf"
        with open(pdf_path, "wb") as f:
            f.write(content)

        # Generate page images
        pages_dir = doc_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        doc = fitz.open(str(pdf_path))
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            image_path = pages_dir / f"page_{page_num + 1}.png"
            img.save(image_path)

        doc.close()

        # Save metadata
        now = datetime.utcnow().isoformat() + "Z"
        metadata = {
            "id": document_id,
            "filename": filename,
            "uploaded_at": now,
            "page_count": page_count,
            "file_size_bytes": len(content),
            "status": "ready",
        }

        with open(doc_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its files."""
        doc_dir = DOCUMENTS_DIR / document_id
        if not doc_dir.exists():
            return False
        shutil.rmtree(doc_dir)
        return True

    def get_page_image_path(self, document_id: str, page: int) -> Optional[Path]:
        """Get the path to a page image."""
        image_path = DOCUMENTS_DIR / document_id / "pages" / f"page_{page}.png"
        if not image_path.exists():
            return None
        return image_path

    def get_pdf_path(self, document_id: str) -> Optional[Path]:
        """Get the path to the original PDF."""
        pdf_path = DOCUMENTS_DIR / document_id / "original.pdf"
        if not pdf_path.exists():
            return None
        return pdf_path

    # =========================================================================
    # Results
    # =========================================================================

    def list_results(self) -> list[dict]:
        """List all extraction results."""
        results = []
        for path in RESULTS_DIR.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                # Return summary without full OCR
                results.append({
                    "id": data["id"],
                    "document_id": data["document_id"],
                    "document_name": data.get("document_name", ""),
                    "template_id": data["template_id"],
                    "template_name": data.get("template_name", ""),
                    "extracted_at": data["extracted_at"],
                    "processing_time_seconds": data.get("processing_time_seconds", 0),
                    "verified": data.get("verified", False),
                })
        return sorted(results, key=lambda r: r.get("extracted_at", ""), reverse=True)

    def get_result(self, result_id: str) -> Optional[dict]:
        """Get an extraction result by ID."""
        path = RESULTS_DIR / f"{result_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def save_result(self, result: dict) -> dict:
        """Save an extraction result."""
        result_id = result.get("id") or str(uuid.uuid4())
        result["id"] = result_id

        path = RESULTS_DIR / f"{result_id}.json"
        with open(path, "w") as f:
            json.dump(result, f, indent=2)

        return result

    def delete_result(self, result_id: str) -> bool:
        """Delete an extraction result."""
        path = RESULTS_DIR / f"{result_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    # =========================================================================
    # Jobs
    # =========================================================================

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a batch job by ID."""
        path = JOBS_DIR / f"{job_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def save_job(self, job: dict) -> dict:
        """Save a batch job."""
        job_id = job.get("id") or str(uuid.uuid4())
        job["id"] = job_id

        path = JOBS_DIR / f"{job_id}.json"
        with open(path, "w") as f:
            json.dump(job, f, indent=2)

        return job

    def list_jobs(self) -> list[dict]:
        """List all batch jobs."""
        jobs = []
        for path in JOBS_DIR.glob("*.json"):
            with open(path) as f:
                jobs.append(json.load(f))
        return sorted(jobs, key=lambda j: j.get("created_at", ""), reverse=True)

    def delete_job(self, job_id: str) -> bool:
        """Delete a batch job."""
        path = JOBS_DIR / f"{job_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    # =========================================================================
    # Exports
    # =========================================================================

    def get_export_path(self, export_id: str) -> Optional[Path]:
        """Get the path to an export file."""
        # Check both with and without .xlsx extension
        path = EXPORTS_DIR / f"{export_id}.xlsx"
        if path.exists():
            return path
        path = EXPORTS_DIR / export_id
        if path.exists():
            return path
        return None

    def save_export(self, export_id: str, content: bytes, filename: str) -> dict:
        """Save an export file."""
        path = EXPORTS_DIR / f"{export_id}.xlsx"
        with open(path, "wb") as f:
            f.write(content)

        return {
            "id": export_id,
            "filename": filename,
            "path": str(path),
        }


# Singleton instance
storage = StorageService()
