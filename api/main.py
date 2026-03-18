"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import API_PREFIX, CORS_ORIGINS
from .routers import templates_router, documents_router, extraction_router, batch_router, export_router, queue_router

# Create FastAPI app
app = FastAPI(
    title="Document Extraction API",
    description="API for extracting structured data from PDF documents using VLM + LLM",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(templates_router, prefix=API_PREFIX)
app.include_router(documents_router, prefix=API_PREFIX)
app.include_router(extraction_router, prefix=API_PREFIX)
app.include_router(batch_router, prefix=API_PREFIX)
app.include_router(export_router, prefix=API_PREFIX)
app.include_router(queue_router, prefix=API_PREFIX)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Document Extraction API",
        "version": "0.1.0",
    }


@app.get(f"{API_PREFIX}/health")
async def health():
    """API health check."""
    return {"status": "healthy"}
