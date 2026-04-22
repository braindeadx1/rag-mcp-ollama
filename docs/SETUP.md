# Setup

End-to-end setup for a Linux host (LXC container, VM, or bare-metal). Assumes Debian 12 / Ubuntu 22.04+.

## Prerequisites

- Docker (installed by `install_ct.sh` if missing)
- Python 3.11+
- A reachable Ollama server (any host; can be the same machine or a dedicated GPU node)
- Optional: a NAS mount for backups

## 1. Get the code

```bash
sudo mkdir -p /opt/rag-mcp-ollama
sudo git clone https://github.com/braindeadx1/rag-mcp-ollama.git /opt/rag-mcp-ollama
```

## 2. Pull the embedding model

```bash
OLLAMA_HOST=<ollama-host>:11434 /opt/rag-mcp-ollama/scripts/pull_ollama_model.sh bge-m3
```

## 3. Run the install script

```bash
sudo REPO_DIR=/opt/rag-mcp-ollama bash /opt/rag-mcp-ollama/scripts/install_ct.sh
```

This will:

1. Install Docker if absent.
2. Start the Qdrant container (compose).
3. Create `/opt/rag-pipeline/` with a venv and the pipeline code.
4. Drop `.env.example` to `.env` (edit before restart!).
5. Install and enable `rag-api.service` and `rag-watcher.service`.

## 4. Configure secrets

```bash
sudoedit /opt/rag-pipeline/.env
```

Set at minimum:

```dotenv
OLLAMA_URL=http://<ollama-host>:11434
RAG_API_KEY=<long random string>
```

Restart:

```bash
sudo systemctl restart rag-api rag-watcher
```

## 5. Smoke tests

```bash
curl http://localhost:8001/health
# {"status":"ok","collection":"rag","points_total":0,...}

curl -X POST http://localhost:8001/index/text \
  -H "Authorization: Bearer $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"source":"test/hello","content":"Hello world from rag-mcp-ollama","content_type":"text"}'

curl -X POST http://localhost:8001/search \
  -H "Authorization: Bearer $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"queries":["greeting"], "limit":3}'
```

## 6. MCP client wiring

See README "Configure the MCP server".

## 7. Backups (optional)

Mount your NAS at `/mnt/nas-backup/`, then enable the timer:

```bash
sudo systemctl enable --now rag-backup.timer
```

Confirm:

```bash
systemctl list-timers rag-backup.timer
```

## 8. Bulk import existing docs

```bash
sudo -u root /opt/rag-pipeline/.venv/bin/python -m pipeline.bulk_import \
  /path/to/docs --prefix docs --ext .md --ext .pdf
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `503` from `/health` after restart | Ollama unreachable | Check `OLLAMA_URL` and that the embed model is pulled |
| `400` on first index call | Collection vector dim mismatch | `EMBED_DIM` in `.env` must match the model output |
| Watcher loops on the same file | Watcher writes back into inbox | Ensure `ARCHIVE_DIR` is **outside** `INBOX_DIR` |
| OOM on PDF import | Large PDFs split poorly | Lower `CHUNK_SIZE` or pre-split the PDF |
