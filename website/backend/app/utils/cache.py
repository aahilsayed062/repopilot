"""
Semantic Response Cache for RepoPilot AI.

Provides two cache layers:
1. **Routing cache** — Caches agent routing decisions (lightweight, longer TTL).
2. **Response cache** — Caches full /smart endpoint responses (keyed by repo+question+commit).

Both caches are automatically invalidated when a repo is re-indexed (new commit hash)
or when the TTL expires.  Everything is in-memory — no external dependencies.

Thread-safety: Uses asyncio.Lock for safe concurrent access.
"""

import asyncio
import hashlib
import time
from typing import Any, Dict, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Response cache: shorter TTL (results may change if code changes)
RESPONSE_TTL_SECONDS: int = 600  # 10 minutes
RESPONSE_MAX_ENTRIES: int = 200

# Routing cache: longer TTL (routing decision is stable per question shape)
ROUTING_TTL_SECONDS: int = 1800  # 30 minutes
ROUTING_MAX_ENTRIES: int = 500


class _CacheEntry:
    """Single cache entry with timestamp."""
    __slots__ = ("value", "created_at", "hits")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.created_at: float = time.monotonic()
        self.hits: int = 0

    def is_expired(self, ttl_seconds: int) -> bool:
        return (time.monotonic() - self.created_at) > ttl_seconds


class ResponseCache:
    """In-memory LRU-ish cache with per-entry TTL.

    Keyed by ``(repo_id, question, commit_hash)`` so that answers are
    automatically invalidated when the underlying code changes (different
    commit).

    Usage::

        result = cache.get_response(repo_id, question, commit_hash)
        if result is not None:
            return result  # cache hit — skip all LLM work

        # … expensive LLM pipeline …

        cache.put_response(repo_id, question, commit_hash, result)
    """

    def __init__(self) -> None:
        self._response_store: Dict[str, _CacheEntry] = {}
        self._routing_store: Dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    # ── Key helpers ───────────────────────────────────────────────

    @staticmethod
    def _response_key(repo_id: str, question: str, commit_hash: str) -> str:
        """Deterministic cache key for a full response."""
        raw = f"{repo_id}|{question.strip().lower()}|{commit_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _routing_key(question: str) -> str:
        """Cache key for routing decisions (repo-agnostic — routing only depends on query shape)."""
        raw = question.strip().lower()
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── Response cache ────────────────────────────────────────────

    async def get_response(
        self, repo_id: str, question: str, commit_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Return cached response or ``None`` on miss / expiry."""
        key = self._response_key(repo_id, question, commit_hash)
        async with self._lock:
            entry = self._response_store.get(key)
            if entry is None:
                return None
            if entry.is_expired(RESPONSE_TTL_SECONDS):
                del self._response_store[key]
                logger.debug("response_cache_expired", key=key[:12])
                return None
            entry.hits += 1
            logger.info("response_cache_hit", key=key[:12], hits=entry.hits)
            return entry.value

    async def put_response(
        self, repo_id: str, question: str, commit_hash: str, value: Dict[str, Any]
    ) -> None:
        """Store a response in the cache."""
        key = self._response_key(repo_id, question, commit_hash)
        async with self._lock:
            # Evict oldest entries if at capacity
            if len(self._response_store) >= RESPONSE_MAX_ENTRIES:
                self._evict_oldest(self._response_store, RESPONSE_MAX_ENTRIES // 4)
            self._response_store[key] = _CacheEntry(value)
            logger.debug("response_cache_stored", key=key[:12])

    # ── Routing cache ─────────────────────────────────────────────

    async def get_routing(self, question: str) -> Optional[Dict[str, Any]]:
        """Return cached routing decision or ``None``."""
        key = self._routing_key(question)
        async with self._lock:
            entry = self._routing_store.get(key)
            if entry is None:
                return None
            if entry.is_expired(ROUTING_TTL_SECONDS):
                del self._routing_store[key]
                return None
            entry.hits += 1
            logger.info("routing_cache_hit", key=key[:12], hits=entry.hits)
            return entry.value

    async def put_routing(self, question: str, value: Dict[str, Any]) -> None:
        """Store a routing decision."""
        key = self._routing_key(question)
        async with self._lock:
            if len(self._routing_store) >= ROUTING_MAX_ENTRIES:
                self._evict_oldest(self._routing_store, ROUTING_MAX_ENTRIES // 4)
            self._routing_store[key] = _CacheEntry(value)

    # ── Invalidation ──────────────────────────────────────────────

    async def invalidate_repo(self, repo_id: str) -> int:
        """Remove all cached responses for a repo (called after re-index).

        Since the key includes commit_hash, a new commit automatically
        causes misses, but explicit invalidation keeps memory tidy.
        """
        prefix = hashlib.sha256(f"{repo_id}|".encode()).hexdigest()[:8]
        # We can't match by prefix with SHA-256, so do a full scan
        count = 0
        async with self._lock:
            keys_to_remove = []
            for key in self._response_store:
                # entries whose repo_id matches (stored on the entry itself isn't
                # practical with SHA keys, so we store repo_id in the value dict)
                entry = self._response_store[key]
                if isinstance(entry.value, dict) and entry.value.get("_cache_repo_id") == repo_id:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._response_store[key]
                count += 1
        if count:
            logger.info("cache_invalidated_repo", repo_id=repo_id, entries_removed=count)
        return count

    async def clear(self) -> None:
        """Clear all caches."""
        async with self._lock:
            self._response_store.clear()
            self._routing_store.clear()
        logger.info("cache_cleared")

    # ── Stats ─────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "response_entries": len(self._response_store),
            "routing_entries": len(self._routing_store),
            "response_max": RESPONSE_MAX_ENTRIES,
            "routing_max": ROUTING_MAX_ENTRIES,
        }

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _evict_oldest(store: Dict[str, _CacheEntry], count: int) -> None:
        """Remove the `count` oldest entries from the store."""
        if not store:
            return
        sorted_keys = sorted(store, key=lambda k: store[k].created_at)
        for key in sorted_keys[:count]:
            del store[key]


# Global singleton
response_cache = ResponseCache()
