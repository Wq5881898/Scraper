from __future__ import annotations

import json
import queue
import threading
import time
from typing import Any, Dict, Optional

from .models import ScrapeResult


class StorageBase:
    def write(self, result: ScrapeResult) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class JsonlStorage(StorageBase):
    def __init__(self, path: str) -> None:
        self._path = path
        self._queue: queue.Queue[Optional[ScrapeResult]] = queue.Queue()
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()

    def write(self, result: ScrapeResult) -> None:
        self._queue.put(result)

    def close(self) -> None:
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
