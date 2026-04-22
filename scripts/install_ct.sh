#!/usr/bin/env bash
# Idempotent CT-Setup-Script: Docker + Qdrant + Python pipeline + systemd
# Run inside the CT (or via `pct exec <CTID> -- bash install_ct.sh`)

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/rag-mcp-ollama}"
PIPELINE_DIR="/opt/rag-pipeline"
QDRANT_DIR="/opt/rag-qdrant"

if ! command -v docker >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq curl ca-certificates gnupg python3 python3-venv python3-pip git rsync jq
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

mkdir -p "$QDRANT_DIR" /var/lib/qdrant /data/rag-inbox /data/rag-archiv /data/rag-failed
cp "$REPO_DIR/docker-compose.yml" "$QDRANT_DIR/docker-compose.yml"
( cd "$QDRANT_DIR" && docker compose up -d )

if [ ! -d "$PIPELINE_DIR" ]; then
  mkdir -p "$PIPELINE_DIR"
fi
rsync -a --delete "$REPO_DIR/pipeline/" "$PIPELINE_DIR/pipeline/"
cp "$REPO_DIR/pipeline/requirements.txt" "$PIPELINE_DIR/requirements.txt"
[ -f "$PIPELINE_DIR/.env" ] || cp "$REPO_DIR/.env.example" "$PIPELINE_DIR/.env"

if [ ! -d "$PIPELINE_DIR/.venv" ]; then
  python3 -m venv "$PIPELINE_DIR/.venv"
fi
"$PIPELINE_DIR/.venv/bin/pip" install -q --upgrade pip
"$PIPELINE_DIR/.venv/bin/pip" install -q -r "$PIPELINE_DIR/requirements.txt"

cp "$REPO_DIR/systemd/rag-api.service" /etc/systemd/system/rag-api.service
cp "$REPO_DIR/systemd/rag-watcher.service" /etc/systemd/system/rag-watcher.service
cp "$REPO_DIR/systemd/rag-backup.service" /etc/systemd/system/rag-backup.service
cp "$REPO_DIR/systemd/rag-backup.timer" /etc/systemd/system/rag-backup.timer
systemctl daemon-reload
systemctl enable --now rag-api.service rag-watcher.service

echo "install complete. edit $PIPELINE_DIR/.env (RAG_API_KEY!) then: systemctl restart rag-api rag-watcher"
