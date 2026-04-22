#!/usr/bin/env bash
# Pull the embedding model into a remote Ollama instance.
# Usage: OLLAMA_HOST=192.167.200.5:11434 ./pull_ollama_model.sh [model]
# Defaults to bge-m3 (1024-dim, multilingual).

set -eu

MODEL="${1:-bge-m3}"
HOST="${OLLAMA_HOST:-localhost:11434}"

curl -sS -X POST "http://${HOST}/api/pull" \
  -H "Content-Type: application/json" \
  --data "{\"model\":\"${MODEL}\",\"stream\":false}"
echo
