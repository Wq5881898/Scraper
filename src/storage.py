from __future__ import annotations

import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .models import ScrapeResult


class StorageBase(ABC):
    """Abstract base class for all storage backends.

    Subclasses must implement write() and close() to handle
    persistence of scraping results.
    """

    @abstractmethod
    def write(self, result: ScrapeResult) -> None:
        """Persist a single scrape result."""

    @abstractmethod
    def close(self) -> None:
        """Flush pending writes and release resources."""


class JsonlStorage(StorageBase):
    """Stores scrape results as JSON Lines (.jsonl) using a background writer thread."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._queue: queue.Queue[Optional[ScrapeResult]] = queue.Queue()
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()

    def write(self, result: ScrapeResult) -> None:
        """Enqueue a scrape result for background writing."""
        self._queue.put(result)

    def close(self) -> None:
        """Signal the writer thread to flush and stop."""
        self._queue.put(None)
        self._thread.join(timeout=5)

    def _writer(self) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            while True:
                item = self._queue.get()
                if item is None:
                    break
                record = {
                    "timestamp": time.time(),
                    "task_id": item.task_id,
                    "source_id": item.source_id,
                    "url": item.url,
                    "parsed_data": item.data,
                    "status": item.success,
                    "latency": item.latency_ms,
                    "error_type": item.error_type,
                    "status_code": item.status_code,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
