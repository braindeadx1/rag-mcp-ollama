#!/usr/bin/env bash
# Claude Code PostToolUse hook for WebFetch / WebSearch.
# Reads JSON event from stdin, posts content to RAG API.
# Required env vars: RAG_API_URL, RAG_API_KEY
# Configure in ~/.claude/settings.json:
#   "hooks": {
#     "PostToolUse": [
#       { "matcher": "WebFetch|WebSearch",
#         "hooks": [{ "type": "command", "command": "bash /path/to/webfetch_post.sh" }] }
#     ]
#   }

set -eu

: "${RAG_API_URL:?RAG_API_URL not set}"
: "${RAG_API_KEY:?RAG_API_KEY not set}"

payload=$(cat)
tool=$(printf '%s' "$payload" | jq -r '.tool_name // empty')
url=$(printf '%s' "$payload" | jq -r '.tool_input.url // .tool_input.query // empty')
content=$(printf '%s' "$payload" | jq -r '.tool_response // .tool_response.content // empty')

if [ -z "$content" ] || [ -z "$url" ]; then
  exit 0
fi

bytes=${#content}
if [ "$bytes" -lt 500 ]; then
  exit 0
fi

source="web/${tool}/${url}"

curl -sS -m 30 -X POST "$RAG_API_URL/index/web" \
  -H "Authorization: Bearer $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  --data "$(jq -nc --arg u "$source" --arg c "$content" '{url:$u, content:$c}')" \
  >/dev/null 2>&1 || true

exit 0
