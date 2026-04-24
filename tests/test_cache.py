"""Tests for the disk-based extraction cache."""

from __future__ import annotations

from app.services.cache import ExtractionCache


def test_cache_roundtrip(tmp_path):
    cache = ExtractionCache(tmp_path, enabled=True)
    key = ExtractionCache.key_for(b"hello world")
    assert cache.get(key) is None

    payload = {"status": "success", "confidence": 0.9}
    cache.set(key, payload)
    assert cache.get(key) == payload


def test_cache_disabled_is_noop(tmp_path):
    cache = ExtractionCache(tmp_path, enabled=False)
    key = ExtractionCache.key_for(b"hello")
    cache.set(key, {"x": 1})
    assert cache.get(key) is None


def test_cache_key_is_sha256_stable():
    key1 = ExtractionCache.key_for(b"payload")
    key2 = ExtractionCache.key_for(b"payload")
    assert key1 == key2
    assert len(key1) == 64
