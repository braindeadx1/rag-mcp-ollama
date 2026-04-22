import uuid
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from .config import settings


class QdrantStore:
    def __init__(self, url: str | None = None, collection: str | None = None):
        self.collection = collection or settings.qdrant_collection
        self.client = QdrantClient(url=url or settings.qdrant_url, prefer_grpc=False)
        self._ensure_collection()
        self._ensure_indexes()

    def _ensure_collection(self):
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=settings.embed_dim, distance=qm.Distance.COSINE),
            )

    def _ensure_indexes(self):
        for field, schema in [
            ("source", qm.PayloadSchemaType.KEYWORD),
            ("content_type", qm.PayloadSchemaType.KEYWORD),
            ("is_current", qm.PayloadSchemaType.BOOL),
            ("version", qm.PayloadSchemaType.KEYWORD),
        ]:
            try:
                self.client.create_payload_index(self.collection, field, field_schema=schema)
            except Exception:
                pass

    def deprecate_source(self, source: str) -> int:
        scroll, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(
                must=[
                    qm.FieldCondition(key="source", match=qm.MatchValue(value=source)),
                    qm.FieldCondition(key="is_current", match=qm.MatchValue(value=True)),
                ]
            ),
            limit=10000,
            with_payload=False,
            with_vectors=False,
        )
        ids = [p.id for p in scroll]
        if ids:
            self.client.set_payload(
                collection_name=self.collection,
                payload={"is_current": False},
                points=ids,
            )
        return len(ids)

    def upsert_chunks(self, source: str, chunks: list[dict], vectors: list[list[float]], content_type: str, metadata: dict | None = None) -> str:
        version = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta = metadata or {}
        points = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            payload = {
                "source": source,
                "content": chunk["content"],
                "chunk_idx": idx,
                "chunk_meta": chunk.get("meta", {}),
                "content_type": content_type,
                "version": version,
                "is_current": True,
                "metadata": meta,
                "indexed_at": version,
            }
            points.append(qm.PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
        self.client.upsert(collection_name=self.collection, points=points)
        return version

    def search(self, query_vec: list[float], limit: int = 5, source: str | None = None, content_type: str | None = None, include_history: bool = False) -> list[dict]:
        must = []
        if not include_history:
            must.append(qm.FieldCondition(key="is_current", match=qm.MatchValue(value=True)))
        if source:
            must.append(qm.FieldCondition(key="source", match=qm.MatchText(text=source)))
        if content_type:
            must.append(qm.FieldCondition(key="content_type", match=qm.MatchValue(value=content_type)))
        qfilter = qm.Filter(must=must) if must else None
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=query_vec,
            query_filter=qfilter,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "score": h.score,
                "source": h.payload.get("source"),
                "content": h.payload.get("content"),
                "content_type": h.payload.get("content_type"),
                "version": h.payload.get("version"),
                "is_current": h.payload.get("is_current"),
                "chunk_idx": h.payload.get("chunk_idx"),
                "metadata": h.payload.get("metadata", {}),
            }
            for h in hits
        ]

    def stats(self) -> dict:
        info = self.client.get_collection(self.collection)
        scroll_current, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(must=[qm.FieldCondition(key="is_current", match=qm.MatchValue(value=True))]),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        return {
            "collection": self.collection,
            "points_total": info.points_count,
            "vectors_count": info.vectors_count,
            "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def list_sources(self, limit: int = 1000) -> list[dict]:
        seen: dict[str, dict] = {}
        offset = None
        while True:
            scroll, offset = self.client.scroll(
                collection_name=self.collection,
                limit=512,
                offset=offset,
                with_payload=["source", "version", "is_current", "content_type"],
                with_vectors=False,
            )
            for p in scroll:
                src = p.payload.get("source")
                if not src:
                    continue
                entry = seen.setdefault(src, {"source": src, "versions": set(), "current_chunks": 0, "total_chunks": 0, "content_type": p.payload.get("content_type")})
                entry["versions"].add(p.payload.get("version"))
                entry["total_chunks"] += 1
                if p.payload.get("is_current"):
                    entry["current_chunks"] += 1
            if offset is None:
                break
            if len(seen) >= limit:
                break
        return [
            {**v, "versions": sorted(v["versions"], reverse=True)} for v in seen.values()
        ]

    def delete_source(self, source: str) -> int:
        result = self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source))])
            ),
        )
        return result.operation_id if hasattr(result, "operation_id") else 0
