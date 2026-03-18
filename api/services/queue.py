"""Queue service - manages extraction queue with background processing."""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from ..config import DATA_DIR
from .storage import storage
from .extraction import extraction_service


# Queue file path
QUEUE_FILE = DATA_DIR / "queue.json"


class StopProcessingException(Exception):
    """Raised to immediately stop processing the current item."""
    pass


class QueueService:
    """Service for managing the extraction queue."""

    def __init__(self):
        self._lock = threading.Lock()
        self._processing_thread: Optional[threading.Thread] = None
        self._cancel_requested = False
        self._stop_current_item = False
        self._current_item_id: Optional[str] = None
        self._current_pages_processed = 0
        self._load_queue()

    def _load_queue(self):
        """Load queue from disk."""
        if QUEUE_FILE.exists():
            with open(QUEUE_FILE, "r") as f:
                data = json.load(f)
                self._items = data.get("items", [])
        else:
            self._items = []

    def _save_queue(self):
        """Save queue to disk."""
        with open(QUEUE_FILE, "w") as f:
            json.dump({"items": self._items}, f, indent=2, default=str)

    def _get_item_by_id(self, item_id: str) -> Optional[dict]:
        """Get queue item by ID."""
        for item in self._items:
            if item["id"] == item_id:
                return item
        return None

    def add_items(self, items: list[dict]) -> list[dict]:
        """
        Add items to the queue.

        Args:
            items: List of {document_id, template_id, verify} dicts

        Returns:
            List of created queue items
        """
        created = []
        with self._lock:
            for item_data in items:
                document_id = item_data.get("document_id")
                template_id = item_data.get("template_id")
                verify = item_data.get("verify", True)

                # Get document and template info
                document = storage.get_document(document_id)
                template = storage.get_template(template_id)

                if not document:
                    raise ValueError(f"Document not found: {document_id}")
                if not template:
                    raise ValueError(f"Template not found: {template_id}")

                queue_item = {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "document_name": document.get("filename", ""),
                    "template_id": template_id,
                    "template_name": template.get("name", ""),
                    "page_count": document.get("page_count", 0),
                    "verify": verify,
                    "status": "pending",
                    "pages_processed": 0,
                    "result_id": None,
                    "error": None,
                    "processing_time_seconds": None,
                    "added_at": datetime.utcnow().isoformat() + "Z",
                    "started_at": None,
                    "completed_at": None,
                }
                self._items.append(queue_item)
                created.append(queue_item)

            self._save_queue()

        # Start processing if not already running
        self._start_processing()

        return created

    def get_status(self) -> dict:
        """Get current queue status."""
        with self._lock:
            # Calculate totals
            total_pages = 0
            processed_pages = 0

            for item in self._items:
                total_pages += item.get("page_count", 0)
                if item["status"] == "completed":
                    processed_pages += item.get("page_count", 0)
                elif item["status"] == "processing":
                    processed_pages += item.get("pages_processed", 0)

            is_processing = (
                self._processing_thread is not None
                and self._processing_thread.is_alive()
            )

            return {
                "items": self._items.copy(),
                "is_processing": is_processing,
                "total_pages": total_pages,
                "processed_pages": processed_pages,
                "current_item_id": self._current_item_id,
            }

    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the queue. Cannot remove currently processing item."""
        with self._lock:
            item = self._get_item_by_id(item_id)
            if not item:
                return False
            if item["status"] == "processing":
                raise ValueError("Cannot remove item that is currently processing. Stop it first.")
            self._items = [i for i in self._items if i["id"] != item_id]
            self._save_queue()
            return True

    def stop_current(self) -> bool:
        """Stop the currently processing item immediately."""
        with self._lock:
            if not self._current_item_id:
                return False
            self._stop_current_item = True
            return True

    def cancel(self) -> bool:
        """Cancel all queue processing."""
        with self._lock:
            if not self._processing_thread or not self._processing_thread.is_alive():
                return False
            self._cancel_requested = True
            self._stop_current_item = True
            return True

    def clear_completed(self) -> int:
        """Clear completed and failed items from the queue."""
        with self._lock:
            original_count = len(self._items)
            self._items = [
                i for i in self._items
                if i["status"] not in ("completed", "failed")
            ]
            removed = original_count - len(self._items)
            self._save_queue()
            return removed

    def _start_processing(self):
        """Start background processing thread if not already running."""
        with self._lock:
            if self._processing_thread and self._processing_thread.is_alive():
                return  # Already processing

            self._cancel_requested = False
            self._processing_thread = threading.Thread(
                target=self._process_queue,
                daemon=True,
            )
            self._processing_thread.start()

    def _process_queue(self):
        """Process queue items sequentially."""
        while True:
            # Find next pending item
            with self._lock:
                if self._cancel_requested:
                    self._cancel_requested = False
                    self._current_item_id = None
                    break

                pending = [i for i in self._items if i["status"] == "pending"]
                if not pending:
                    self._current_item_id = None
                    break

                item = pending[0]
                item["status"] = "processing"
                item["started_at"] = datetime.utcnow().isoformat() + "Z"
                self._current_item_id = item["id"]
                self._current_pages_processed = 0
                self._save_queue()

            # Process the item (outside lock)
            try:
                start_time = datetime.utcnow()

                def progress_callback(pages_done: int, total_pages: int):
                    # Check if stop was requested
                    if self._stop_current_item:
                        raise StopProcessingException("Processing stopped by user")

                    with self._lock:
                        item_obj = self._get_item_by_id(item["id"])
                        if item_obj:
                            item_obj["pages_processed"] = pages_done
                            self._current_pages_processed = pages_done
                            self._save_queue()

                result = extraction_service.run_extraction(
                    document_id=item["document_id"],
                    template_id=item["template_id"],
                    verify=item["verify"],
                    progress_callback=progress_callback,
                )

                processing_time = (datetime.utcnow() - start_time).total_seconds()

                with self._lock:
                    item_obj = self._get_item_by_id(item["id"])
                    if item_obj:
                        item_obj["status"] = "completed"
                        item_obj["result_id"] = result["id"]
                        item_obj["pages_processed"] = item_obj["page_count"]
                        item_obj["processing_time_seconds"] = processing_time
                        item_obj["completed_at"] = datetime.utcnow().isoformat() + "Z"
                        self._save_queue()

            except StopProcessingException:
                with self._lock:
                    item_obj = self._get_item_by_id(item["id"])
                    if item_obj:
                        item_obj["status"] = "failed"
                        item_obj["error"] = "Stopped by user"
                        item_obj["completed_at"] = datetime.utcnow().isoformat() + "Z"
                        self._save_queue()
                    self._stop_current_item = False

            except Exception as e:
                with self._lock:
                    item_obj = self._get_item_by_id(item["id"])
                    if item_obj:
                        item_obj["status"] = "failed"
                        item_obj["error"] = str(e)
                        item_obj["completed_at"] = datetime.utcnow().isoformat() + "Z"
                        self._save_queue()


# Singleton instance
queue_service = QueueService()
