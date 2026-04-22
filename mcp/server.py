from __future__ import annotations
import os
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP


RAG_API_URL = os.environ.get("RAG_API_URL", "http://192.167.200.15:8001").rstrip("/")
RAG_API_KEY = os.environ.get("RAG_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {RAG_API_KEY}"}
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


mcp = FastMCP("rag-mcp-ollama")


def _client() -> httpx.Client:
    return httpx.Client(base_url=RAG_API_URL, headers=HEADERS, timeout=TIMEOUT)


@mcp.tool()
def rag_index(source: str, content: str, content_type: str = "text", metadata: dict | None = None) -> dict:
    """Index text content under a source label. content_type: text|markdown|html|code|pdf.
    Reindexing the same source deprecates older versions (versioning enabled)."""
    with _client() as c:
        r = c.post("/index/text", json={"source": source, "content": content, "content_type": content_type, "metadata": metadata})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def rag_search(queries: list[str], limit: int = 5, source: str | None = None, content_type: str | None = None, include_history: bool = False) -> list[dict]:
    """Semantic search over the RAG index. Pass MULTIPLE queries in one call for batched embedding.
    Filters: source (substring match), content_type (text|markdown|html|code|pdf).
    include_history=True searches across all versions, otherwise only current."""
    with _client() as c:
        r = c.post("/search", json={"queries": queries, "limit": limit, "source": source, "content_type": content_type, "include_history": include_history})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def rag_stats() -> dict:
    """Return index statistics (collection name, point count)."""
    with _client() as c:
        r = c.get("/stats")
        r.raise_for_status()
        return r.json()


@mcp.tool()
def rag_list_sources() -> list[dict]:
    """List all indexed sources with version counts and current/total chunk counts."""
    with _client() as c:
        r = c.get("/sources")
        r.raise_for_status()
        return r.json()


@mcp.tool()
def rag_delete(source: str) -> dict:
    """Delete ALL versions of a source from the index. Irreversible."""
    with _client() as c:
        r = c.delete("/source", params={"source": source})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def rag_index_web(url: str, content: str, title: str | None = None) -> dict:
    """Index web content (HTML or extracted text) under a URL as source."""
    with _client() as c:
        r = c.post("/index/web", json={"url": url, "content": content, "title": title})
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run()
