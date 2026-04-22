#!/usr/bin/env bash
# Backup Qdrant storage to NAS via rsync.
# Mount the destination beforehand, e.g. via /etc/fstab CIFS or NFS.

set -eu

SRC="${BACKUP_SRC:-/var/lib/qdrant/}"
DST="${BACKUP_DST:-/mnt/nas-backup/rag-qdrant/}"

mkdir -p "$DST"
rsync -a --delete "$SRC" "$DST"
