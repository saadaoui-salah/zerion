from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from zerion_core.config import settings


class CodeVectorStore:
    """ChromaDB-backed vector store for code chunks, separate from memory store."""

    COLLECTION = "zerion_code_rag"

    def __init__(self) -> None:
        rag_db_path = settings.chroma_path.parent / "rag_chroma"
        rag_db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(rag_db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, str] | None = None,
        where_document: dict[str, str] | None = None,
    ) -> dict[str, list]:
        kwargs: dict[str, object] = {
            "query_embeddings": [embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document
        return self._collection.query(**kwargs)

    async def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    async def delete_by_file(self, file_path: str) -> None:
        """Delete all chunks belonging to a specific file."""
        self._collection.delete(where={"file_path": file_path})

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self.COLLECTION)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
