"""Configuration for the API."""

from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Storage paths
TEMPLATES_DIR = DATA_DIR / "templates"
DOCUMENTS_DIR = DATA_DIR / "documents"
RESULTS_DIR = DATA_DIR / "results"
JOBS_DIR = DATA_DIR / "jobs"
EXPORTS_DIR = DATA_DIR / "exports"

# Ensure directories exist
for dir_path in [TEMPLATES_DIR, DOCUMENTS_DIR, RESULTS_DIR, JOBS_DIR, EXPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# PDF processing settings
PDF_DPI = 150  # Balance quality vs memory

# Model settings
VLM_MODEL = "mlx-community/DeepSeek-OCR-2-bf16"
OPENAI_MODEL = "gpt-4.1"

# API settings
API_PREFIX = "/api"
CORS_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # Alternative React port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
