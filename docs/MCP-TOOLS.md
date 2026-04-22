# MCP Tools

All tools are exposed by `mcp/server.py` (FastMCP, stdio transport).

## `rag_index`

Index text under a source label. Re-indexing the same source deprecates older versions (they remain searchable via `include_history=True`).

```python
rag_index(
    source="docs/foo.md",
    content="...",
    content_type="markdown",   # text|markdown|html|code|pdf
    metadata={"author": "me"}, # optional, free-form
)
# → {"source": ..., "chunks": 12, "version": "2026-04-22T...", "deprecated": 8}
```

## `rag_index_web`

Index a fetched web page. Equivalent to `rag_index` with `content_type="html"` and the URL as `source`.

```python
rag_index_web(url="https://example.com/page", content="<html>...", title="Page title")
```

## `rag_search`

Batched semantic search. Always pass **multiple queries** in one call when possible — embeddings run concurrently.

```python
rag_search(
    queries=["how to provision an LXC", "qdrant disk usage"],
    limit=5,
    source="docs",          # substring filter
    content_type="markdown",
    include_history=False,
)
# → [{"query": "...", "hits": [{"score": ..., "source": ..., "content": ..., ...}, ...]}, ...]
```

## `rag_stats`

```python
rag_stats()
# → {"collection": "rag", "points_total": 12345, ...}
```

## `rag_list_sources`

```python
rag_list_sources()
# → [{"source": ..., "versions": [...], "current_chunks": ..., "total_chunks": ..., "content_type": ...}, ...]
```

## `rag_delete`

Removes **all** chunks of a source (current and historical). Irreversible.

```python
rag_delete(source="docs/old.md")
```
