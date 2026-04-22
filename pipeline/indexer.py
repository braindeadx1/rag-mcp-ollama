from __future__ import annotations
import asyncio
from pathlib import Path
from .chunker import chunk_payload, chunk_file, detect_content_type
from .embedder import Embedder
from .qdrant_store import QdrantStore


class Indexer:
    def __init__(self, store: QdrantStore | None = None, embedder: Embedder | None = None):
        self.store = store or QdrantStore()
        self.embedder = embedder or Embedder()

    async def index_text(self, source: str, content: str | bytes, content_type: str, metadata: dict | None = None) -> dict:
        chunks = chunk_payload(content, content_type)
        if not chunks:
            return {"source": source, "chunks": 0, "version": None, "deprecated": 0}
        deprecated = self.store.deprecate_source(source)
        vectors = await self.embedder.embed_many([c["content"] for c in chunks])
        version = self.store.upsert_chunks(source, chunks, vectors, content_type, metadata)
        return {"source": source, "chunks": len(chunks), "version": version, "deprecated": deprecated, "content_type": content_type}

    async def index_file(self, path: Path, source: str | None = None, metadata: dict | None = None) -> dict:
        chunks, ct = chunk_file(path)
        if not chunks:
            return {"source": source or str(path), "chunks": 0, "version": None, "deprecated": 0}
        src = source or str(path)
        deprecated = self.store.deprecate_source(src)
        vectors = await self.embedder.embed_many([c["content"] for c in chunks])
        version = self.store.upsert_chunks(src, chunks, vectors, ct, metadata)
        return {"source": src, "chunks": len(chunks), "version": version, "deprecated": deprecated, "content_type": ct}

    async def search(self, queries: list[str], limit: int = 5, source: str | None = None, content_type: str | None = None, include_history: bool = False) -> list[dict]:
        vectors = await self.embedder.embed_many(queries)
        results = []
        for q, vec in zip(queries, vectors):
            hits = self.store.search(vec, limit=limit, source=source, content_type=content_type, include_history=include_history)
            results.append({"query": q, "hits": hits})
        return results

    async def close(self):
        await self.embedder.close()
