# Claude Code PostToolUse hook for WebFetch / WebSearch (Windows / PowerShell).
# Reads JSON event from stdin, posts content to RAG API.
# Required env vars: RAG_API_URL, RAG_API_KEY
# Configure in ~/.claude/settings.json:
#   "hooks": {
#     "PostToolUse": [
#       { "matcher": "WebFetch|WebSearch",
#         "hooks": [{ "type": "command",
#                     "command": "powershell -NoProfile -ExecutionPolicy Bypass -File G:/rag-mcp-ollama/hooks/webfetch_post.ps1" }] }
#     ]
#   }

$ErrorActionPreference = "SilentlyContinue"

if (-not $env:RAG_API_URL -or -not $env:RAG_API_KEY) { exit 0 }

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $event = $raw | ConvertFrom-Json
} catch { exit 0 }

$tool = $event.tool_name
if (-not $tool) { exit 0 }

$urlOrQuery = $event.tool_input.url
if (-not $urlOrQuery) { $urlOrQuery = $event.tool_input.query }
if (-not $urlOrQuery) { exit 0 }

$resp = $event.tool_response
if ($resp -is [System.Collections.IDictionary] -or $resp -is [psobject]) {
    $resp = $resp | ConvertTo-Json -Depth 8 -Compress
}
if (-not $resp -or [string]::IsNullOrWhiteSpace($resp)) { exit 0 }

$bytes = [System.Text.Encoding]::UTF8.GetByteCount($resp)
if ($bytes -lt 500) { exit 0 }

$source = "web/$tool/$urlOrQuery"
$body = @{ url = $source; content = $resp } | ConvertTo-Json -Depth 4 -Compress

try {
    Invoke-RestMethod -Uri "$env:RAG_API_URL/index/web" `
        -Method Post `
        -Headers @{ Authorization = "Bearer $env:RAG_API_KEY" } `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 30 | Out-Null
} catch { }

exit 0
