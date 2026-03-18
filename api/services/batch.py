"""Batch processing service - manages batch extraction jobs."""

import uuid
import threading
import traceback
from datetime import datetime
from typing import Optional
from enum import Enum

from .storage import storage
from .extraction import extraction_service


class JobStatus(str, Enum):
    """Status of a batch job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchService:
    """Service for managing batch extraction jobs."""

    def __init__(self):
        self._active_jobs: dict[str, threading.Thread] = {}
        self._cancel_flags: dict[str, bool] = {}

    def create_job(
        self,
        template_id: str,
        document_ids: list[str],
        verify: bool = True,
    ) -> dict:
        """
        Create a new batch job.

        Args:
            template_id: Template to use for extraction
            document_ids: List of document IDs to process
            verify: Whether to run OpenAI verification

        Returns:
            Batch job dict
        """
        # Validate template exists
        template = storage.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Validate all documents exist
        for doc_id in document_ids:
            if not storage.get_document(doc_id):
                raise ValueError(f"Document not found: {doc_id}")

        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        job = {
            "id": job_id,
            "template_id": template_id,
            "template_name": template.get("name", ""),
            "document_ids": document_ids,
            "verify": verify,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "status": JobStatus.PENDING.value,
            "progress": {
                "total": len(document_ids),
                "completed": 0,
                "failed": 0,
                "current_document": None,
                "current_document_name": None,
            },
            "result_ids": [],
            "errors": [],
        }

        storage.save_job(job)
        return job

    def start_job(self, job_id: str) -> dict:
        """
        Start processing a batch job in a background thread.

        Args:
            job_id: ID of the job to start

        Returns:
            Updated job dict
        """
        job = storage.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job["status"] != JobStatus.PENDING.value:
            raise ValueError(f"Job is not pending: {job['status']}")

        # Update status
        job["status"] = JobStatus.PROCESSING.value
        job["started_at"] = datetime.utcnow().isoformat() + "Z"
        storage.save_job(job)

        # Start background thread
        self._cancel_flags[job_id] = False
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id,),
            daemon=True,
        )
        self._active_jobs[job_id] = thread
        thread.start()

        return job

    def _process_job(self, job_id: str):
        """
        Process a batch job (runs in background thread).

        Args:
            job_id: ID of the job to process
        """
        job = storage.get_job(job_id)
        if not job:
            return

        template_id = job["template_id"]
        document_ids = job["document_ids"]
        verify = job.get("verify", True)

        for i, doc_id in enumerate(document_ids):
            # Check for cancellation
            if self._cancel_flags.get(job_id, False):
                job["status"] = JobStatus.CANCELLED.value
                job["completed_at"] = datetime.utcnow().isoformat() + "Z"
                storage.save_job(job)
                return

            # Update progress
            doc = storage.get_document(doc_id)
            job["progress"]["current_document"] = doc_id
            job["progress"]["current_document_name"] = doc.get("filename", "") if doc else ""
            storage.save_job(job)

            try:
                # Run extraction
                print(f"[Batch {job_id[:8]}] Processing document {i+1}/{len(document_ids)}: {doc_id[:8]}")
                result = extraction_service.run_extraction(
                    document_id=doc_id,
                    template_id=template_id,
                    verify=verify,
                )

                # Record success
                job["result_ids"].append(result["id"])
                job["progress"]["completed"] += 1

            except Exception as e:
                # Record failure
                print(f"[Batch {job_id[:8]}] Error processing {doc_id[:8]}: {e}")
                job["progress"]["failed"] += 1
                job["errors"].append({
                    "document_id": doc_id,
                    "document_name": doc.get("filename", "") if doc else "",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })

            storage.save_job(job)

        # Mark completed
        job["status"] = JobStatus.COMPLETED.value
        job["completed_at"] = datetime.utcnow().isoformat() + "Z"
        job["progress"]["current_document"] = None
        job["progress"]["current_document_name"] = None
        storage.save_job(job)

        # Cleanup
        self._active_jobs.pop(job_id, None)
        self._cancel_flags.pop(job_id, None)

        print(f"[Batch {job_id[:8]}] Completed: {job['progress']['completed']} success, {job['progress']['failed']} failed")

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a batch job by ID."""
        return storage.get_job(job_id)

    def list_jobs(self) -> list[dict]:
        """List all batch jobs."""
        return storage.list_jobs()

    def cancel_job(self, job_id: str) -> dict:
        """
        Cancel a running batch job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            Updated job dict
        """
        job = storage.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job["status"] == JobStatus.PROCESSING.value:
            # Signal cancellation
            self._cancel_flags[job_id] = True
        elif job["status"] == JobStatus.PENDING.value:
            # Directly cancel pending job
            job["status"] = JobStatus.CANCELLED.value
            job["completed_at"] = datetime.utcnow().isoformat() + "Z"
            storage.save_job(job)

        return job

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a batch job.

        Args:
            job_id: ID of the job to delete

        Returns:
            True if deleted, False if not found
        """
        job = storage.get_job(job_id)
        if not job:
            return False

        # Cancel if running
        if job["status"] == JobStatus.PROCESSING.value:
            self._cancel_flags[job_id] = True

        return storage.delete_job(job_id)

    def is_job_active(self, job_id: str) -> bool:
        """Check if a job is currently being processed."""
        return job_id in self._active_jobs and self._active_jobs[job_id].is_alive()


# Singleton instance
batch_service = BatchService()
