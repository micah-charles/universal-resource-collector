from __future__ import annotations

import hashlib
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(slots=True)
class DownloadResult:
    final_url: str
    status: int
    content_type: str
    sha256: str
    bytes: int
    path: Path


class DownloadError(RuntimeError):
    pass


class DownloadManager:
    def __init__(self, output_root: str | Path, delay_seconds: float = .35, max_retries: int = 3, user_agent: str = "universal-resource-collector/0.1"):
        self.output_root = Path(output_root); self.output_root.mkdir(parents=True, exist_ok=True)
        self.delay_seconds = delay_seconds; self.max_retries = max_retries; self.user_agent = user_agent

    def fetch(self, url: str, subdir: str = "originals", progress: Callable[[int, int | None], None] | None = None, stop: Callable[[], bool] | None = None) -> DownloadResult:
        last: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            if stop and stop(): raise DownloadError("cancelled")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=90) as response:
                    final_url = response.geturl(); status = response.status; content_type = response.headers.get_content_type(); total = response.headers.get("Content-Length")
                    total_int = int(total) if total and total.isdigit() else None
                    temp_dir = self.output_root / subdir; temp_dir.mkdir(parents=True, exist_ok=True); temp = temp_dir / ".download.part"
                    hasher = hashlib.sha256(); size = 0
                    with temp.open("wb") as handle:
                        while True:
                            if stop and stop(): raise DownloadError("cancelled")
                            chunk = response.read(1024 * 1024)
                            if not chunk: break
                            handle.write(chunk); hasher.update(chunk); size += len(chunk)
                            if progress: progress(size, total_int)
                    if size == 0: raise DownloadError("empty response")
                    data_hash = hasher.hexdigest(); destination = temp_dir / f"{data_hash}.bin"; temp.replace(destination)
                    time.sleep(self.delay_seconds)
                    return DownloadResult(final_url, status, content_type, data_hash, size, destination)
            except (urllib.error.URLError, TimeoutError, OSError, DownloadError) as exc:
                last = exc
                if isinstance(exc, DownloadError) and str(exc) == "cancelled": raise
                if attempt < self.max_retries: time.sleep(min(30.0, 2 ** (attempt - 1) + random.random()))
        raise DownloadError(f"failed after {self.max_retries} attempts: {last}")
