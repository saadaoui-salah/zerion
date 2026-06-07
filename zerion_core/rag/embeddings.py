from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from zerion_core.config import settings
from zerion_core.llm.ollama import OllamaClient


class EmbeddingCache:
    """Disk-based LRU cache for embeddings to avoid re-computation."""

    def __init__(self, max_entries: int = 10000, ttl_seconds: int = 86400) -> None:
        self.cache_path = settings.memory_root / "embedding_cache.json"
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self._cache: dict[str, dict[str, object]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._cache = data
            except (json.JSONDecodeError, OSError):
                self._cache = {}
        self._loaded = True

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Evict oldest entries if over limit
        if len(self._cache) > self.max_entries:
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].get("ts", 0),
            )
            to_remove = sorted_keys[: len(self._cache) - self.max_entries]
            for k in to_remove:
                del self._cache[k]

        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False),
            encoding="utf-8",
        )

    def _key(self, text: str, model: str) -> str:
        raw = f"{model}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, text: str, model: str) -> list[float] | None:
        self._load()
        key = self._key(text, model)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.get("ts", 0) > self.ttl:
            del self._cache[key]
            return None
        return entry["embedding"]

    def put(self, text: str, model: str, embedding: list[float]) -> None:
        self._load()
        key = self._key(text, model)
        self._cache[key] = {"embedding": embedding, "ts": time.time()}
        if len(self._cache) % 50 == 0:
            self._save()

    def save(self) -> None:
        self._save()

    def clear(self) -> None:
        self._cache = {}
        self._save()

    @property
    def size(self) -> int:
        self._load()
        return len(self._cache)


class EmbeddingProvider:
    """Wraps OllamaClient.embed with disk caching."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm
        self.cache = EmbeddingCache()

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or settings.embedding_model
        cached = self.cache.get(text, model)
        if cached is not None:
            return cached
        embedding = await self.llm.embed(text, model=model)
        self.cache.put(text, model, embedding)
        return embedding

    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        results: list[list[float]] = []
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        model = model or settings.embedding_model

        for i, text in enumerate(texts):
            cached = self.cache.get(text, model)
            if cached is not None:
                results.append(cached)
            else:
                results.append([])  # placeholder
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            embeddings = await self.llm.embed_batch(uncached_texts, model=model)
            for idx, emb in zip(uncached_indices, embeddings):
                results[idx] = emb
                self.cache.put(texts[idx], model, emb)

        return results

    def save_cache(self) -> None:
        self.cache.save()
