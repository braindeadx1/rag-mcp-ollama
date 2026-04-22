# Architecture

## Process layout

| Process | Host | Purpose |
|---------|------|---------|
| `qdrant` (container) | RAG host | Vector database, port 6333 (REST + UI), 6334 (gRPC) |
| `rag-api.service` | RAG host | FastAPI on port 8001 (Bearer auth) |
| `rag-watcher.service` | RAG host | Inotify watcher on `/data/rag-inbox/` |
| `rag-backup.timer` | RAG host | rsync `/var/lib/qdrant/` → NAS every 15 min |
| `mcp/server.py` | Anywhere with stdio access to client | FastMCP stdio server, talks HTTP to the REST API |

The MCP server is a **thin adapter**: all logic (chunking, embedding, storage, versioning) lives behind the REST API. This means:

- The same backend can be used by non-MCP clients (curl, n8n, automation).
- The MCP layer can be swapped or extended without touching the pipeline.

## Data flow: indexing

```
content ─▶ chunker ─▶ embedder (Ollama, batched async) ─▶ qdrant_store
                                                              │
                                          ┌───────────────────┼───────────────────┐
                                          ▼                                       ▼
                                 deprecate prior                          upsert new chunks
                              (set is_current=false)                  (is_current=true, version=now)
```

Versioning is **soft-delete by flag**. No data is removed unless `rag_delete(source)` is called explicitly.

## Data flow: search

```
queries[] ─▶ embedder (concurrent) ─▶ qdrant.search(filter: is_current=true) ─▶ ranked hits per query
```

Filters compose: `source` (substring), `content_type` (exact), `include_history` (drops `is_current=true` filter).

## Chunking strategies

| Type | Strategy |
|------|----------|
| Markdown | Split by heading (h1–h6); each section becomes one or more sliding-window chunks of ~512 tokens with 64-token overlap; heading is prepended for context. |
| HTML | Strip script/style/nav/header/footer via BeautifulSoup; extract text; sliding-window chunks. Title attached as metadata. |
| PDF | One pass per page (`pypdf.extract_text`); each page sliding-windowed. Page number stored in chunk meta. |
| Code | Split on top-level boundaries (`def`, `class`, `function`, `interface`, …); each block sliding-windowed. Language stored in chunk meta. |
| Text / config | Plain sliding window. |

Token approximation: `len(text) // 4`. Good enough for chunk sizing; not used for billing.

## Storage layout (Qdrant payload)

```json
{
  "source": "claude-doku/00-INFRASTRUKTUR.md",
  "content": "...",
  "chunk_idx": 17,
  "chunk_meta": {"heading": "## Container auf PVE2"},
  "content_type": "markdown",
  "version": "2026-04-22T15:14:09+00:00",
  "is_current": true,
  "metadata": {"...user-supplied..."},
  "indexed_at": "2026-04-22T15:14:09+00:00"
}
```

Payload indexes are created on `source`, `content_type`, `is_current`, `version` for fast filtered scrolls.

## Embedding choice

`bge-m3` from BAAI (Ollama-packaged):

- 1024-dim
- 8k context window (rare for embed models — handles long chunks)
- Multilingual (German + English + Code in the same space)
- ~1.2 GB on disk via Ollama; runs on CPU (slow) or GPU (fast)

Switching models means changing `OLLAMA_EMBED_MODEL` and `EMBED_DIM`, then re-creating the Qdrant collection (vectors are model-specific). For zero-downtime rotation, use a side-by-side collection name and migrate in two passes.
