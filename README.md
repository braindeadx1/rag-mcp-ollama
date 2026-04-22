# rag-mcp-ollama

Persistent RAG (Retrieval-Augmented Generation) backend exposed as a Model Context Protocol (MCP) server. Built on Qdrant for vector storage and Ollama for embeddings — runs entirely on your own infrastructure.

Designed to live alongside ephemeral context tools (like `context-mode`) and provide **cross-session memory** of large research, documentation, or codebases that you want Claude (or any MCP client) to reach for instead of re-reading files every time.

## Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Vector DB | Qdrant | Production-grade, fast filtering, dashboard UI, simple Docker deploy |
| Embeddings | Ollama + `bge-m3` (1024-dim, multilingual, 8k ctx) | Local, multilingual, GPU-accelerated when available |
| Pipeline | Python 3.11 + FastAPI + watchdog + qdrant-client | Async, simple |
| MCP server | FastMCP (`mcp[cli]`) | stdio transport, works with Claude Code / Cursor / any MCP host |

## Architecture

```
┌──────────────┐  stdio   ┌──────────────────┐ HTTP+Bearer ┌──────────────┐
│  MCP Client  │─────────▶│   mcp/server.py  │────────────▶│   REST API   │
│ (Claude etc.)│          │   (FastMCP)      │             │  (FastAPI)   │
└──────────────┘          └──────────────────┘             └──────┬───────┘
                                                                   │
                                                  ┌────────────────┼─────────────────┐
                                                  ▼                ▼                  ▼
                                          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                                          │   Qdrant     │  │   Ollama     │  │   Inbox      │
                                          │ (port 6333)  │  │ (any host)   │  │ /data/rag-…  │
                                          └──────────────┘  └──────────────┘  └──────────────┘
```

## Features

- **Versioned indexing**: re-indexing the same source marks old chunks as `is_current=false` instead of deleting them. Searches default to current only; pass `include_history=true` to reach back.
- **Multi-format chunking**: Markdown (heading-aware), HTML (boilerplate stripped via BeautifulSoup), PDF (page-aware via `pypdf`), code (boundary-aware), plain text (sliding window).
- **Four ways to ingest**:
  1. MCP tool call (`rag_index`) — manual, deliberate
  2. REST API (`POST /index/text|file|web`) — for hooks and scripts
  3. Inbox watcher — drop a file in `/data/rag-inbox/`, it gets indexed and archived
  4. Bulk importer — recurse a directory tree (`python -m pipeline.bulk_import /some/dir`)
- **Filterable search**: scope by `source` (substring), `content_type` (`markdown|html|pdf|code|text`), or include historical versions.
- **Bearer-token auth**: REST API gated by `RAG_API_KEY`.
- **Backup hook**: ships a 15-minute rsync timer for shipping `/var/lib/qdrant` to a NAS mount.

## Quick start

### 1. Run Qdrant

```bash
docker compose up -d
```

Qdrant dashboard: <http://localhost:6333/dashboard>

### 2. Pull the embedding model into Ollama

```bash
OLLAMA_HOST=localhost:11434 ./scripts/pull_ollama_model.sh bge-m3
```

### 3. Install the pipeline (idempotent)

```bash
sudo REPO_DIR="$(pwd)" ./scripts/install_ct.sh
```

This sets up `/opt/rag-pipeline` (venv + code), copies `.env.example` to `.env`, and installs/enables the systemd units. Edit `/opt/rag-pipeline/.env` to set `RAG_API_KEY` and the right `OLLAMA_URL`.

### 4. Configure the MCP server (any client)

```bash
cd mcp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Add to your Claude Code `~/.claude.json` (or equivalent MCP host config):

```json
{
  "mcpServers": {
    "rag": {
      "command": "/path/to/mcp/.venv/bin/python",
      "args": ["/path/to/mcp/server.py"],
      "env": {
        "RAG_API_URL": "http://<ct-ip>:8001",
        "RAG_API_KEY": "<same key as the API>"
      }
    }
  }
}
```

## MCP tools

| Tool | Description |
|------|-------------|
| `rag_index(source, content, content_type?, metadata?)` | Index text. Re-indexing a source deprecates older versions. |
| `rag_index_web(url, content, title?)` | Index a web page (HTML). |
| `rag_search(queries[], limit?, source?, content_type?, include_history?)` | Batched semantic search. |
| `rag_stats()` | Collection size and metadata. |
| `rag_list_sources()` | All indexed sources with version counts. |
| `rag_delete(source)` | Remove a source (irreversible). |

## REST endpoints

`Authorization: Bearer <RAG_API_KEY>` is required on all routes except `/health`.

```
GET    /health
POST   /index/text   {source, content, content_type, metadata?}
POST   /index/file   multipart: file, source, content_type
POST   /index/web    {url, content, title?, metadata?}
POST   /search       {queries[], limit?, source?, content_type?, include_history?}
GET    /stats
GET    /sources
DELETE /source?source=<name>
```

## WebFetch hook (Claude Code)

Auto-index everything Claude fetches from the web by adding to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "WebFetch|WebSearch",
        "hooks": [
          { "type": "command",
            "command": "RAG_API_URL=http://<ct-ip>:8001 RAG_API_KEY=<key> bash /path/to/hooks/webfetch_post.sh" }
        ]
      }
    ]
  }
}
```

The hook script skips responses smaller than 500 bytes (no spam from short answers).

## Bulk import

```bash
/opt/rag-pipeline/.venv/bin/python -m pipeline.bulk_import /path/to/docs \
  --prefix docs \
  --ext .md --ext .pdf
```

`--dry-run` lists matched files without indexing.

## Backup

The shipped systemd timer copies `/var/lib/qdrant/` to `/mnt/nas-backup/rag-qdrant/` every 15 minutes via rsync. Override paths with the `BACKUP_SRC` and `BACKUP_DST` env vars in the service file.

## Versioning model

Each indexing operation writes a UTC timestamp `version` and `is_current=true` to every new chunk; existing chunks for that source are flipped to `is_current=false` (kept on disk, not deleted). To inspect history:

```python
rag_search(queries=["my query"], include_history=True)
```

To purge a source completely (irreversible):

```python
rag_delete(source="some/source")
```

## Project layout

```
rag-mcp-ollama/
├── docker-compose.yml          # Qdrant
├── pipeline/
│   ├── api.py                  # FastAPI REST surface
│   ├── chunker.py              # Multi-format chunking
│   ├── config.py               # Pydantic settings (.env)
│   ├── embedder.py             # Async Ollama client
│   ├── indexer.py              # Orchestrator
│   ├── qdrant_store.py         # Qdrant wrapper + versioning
│   ├── watcher.py              # /data/rag-inbox/ → index → archive
│   ├── bulk_import.py          # CLI: recursive import
│   └── requirements.txt
├── mcp/
│   ├── server.py               # FastMCP server (stdio)
│   └── requirements.txt
├── systemd/                    # rag-api / rag-watcher / rag-backup units
├── hooks/webfetch_post.sh      # PostToolUse hook example
├── scripts/                    # install_ct.sh, backup.sh, pull_ollama_model.sh
└── docs/                       # ARCHITECTURE.md, SETUP.md, MCP-TOOLS.md
```

## License

MIT
