"""Tiny disk-based cache for extraction results.

Keyed by ``sha256(file_bytes)``. Entries are JSON files under
``settings.cache_dir``. The cache is intentionally dumb: no TTL, no
eviction, zero dependencies. It's a *90% cost cut* when the same invoice
hits the endpoint twice (retries, pipeline re-runs, upload de-duping on
the Laravel side, …).

Callers opt-out with ``X-Extraction-Strategy: force_llm`` or by
disabling it in config.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionCache:
    """Content-addressable cache of successful ``ExtractionResponse`` payloads."""

    def __init__(self, base_dir: str | Path, enabled: bool = True) -> None:
        self._base = Path(base_dir)
        self._enabled = enabled
        if self._enabled:
            self._base.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key_for(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            logger.info("cache_hit", key=key[:12])
            return payload
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        if not self._enabled:
            return
        try:
            tmp = self._path_for(key).with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            tmp.replace(self._path_for(key))
            logger.info("cache_write", key=key[:12])
        except OSError as exc:
            logger.warning("cache_write_failed", key=key[:12], error=str(exc))

    def _path_for(self, key: str) -> Path:
        shard = key[:2]
        directory = self._base / shard
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.json"
