"""Document management endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from typing import List

from ..schemas import (
    DocumentMetadata,
    DocumentListResponse,
    DocumentUploadResponse,
)
from ..services.storage import storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents():
    """List all uploaded documents."""
    documents = storage.list_documents()
    return DocumentListResponse(
        documents=[DocumentMetadata(**d) for d in documents],
        total=len(documents),
    )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload one or more PDF documents."""
    uploaded = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} is not a PDF"
            )

        content = await file.read()
        metadata = storage.save_document(file.filename, content)
        uploaded.append(DocumentMetadata(**metadata))

    return DocumentUploadResponse(
        documents=uploaded,
        total_uploaded=len(uploaded),
    )


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str):
    """Get document metadata."""
    document = storage.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentMetadata(**document)


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its files."""
    if not storage.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "id": document_id}


@router.get("/{document_id}/pages/{page}")
async def get_page_image(document_id: str, page: int):
    """Get a page image."""
    image_path = storage.get_page_image_path(document_id, page)
    if not image_path:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"page_{page}.png",
    )


@router.get("/{document_id}/pdf")
async def get_pdf(document_id: str):
    """Get the original PDF file."""
    pdf_path = storage.get_pdf_path(document_id)
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Document not found")

    document = storage.get_document(document_id)
    filename = document.get("filename", "document.pdf") if document else "document.pdf"

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
