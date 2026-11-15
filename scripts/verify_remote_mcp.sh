#!/usr/bin/env bash
# Phase 3 verification — health + discovery + MCP HTTP surface.
# Usage:
#   ./scripts/verify_remote_mcp.sh https://megmis.onrender.com
#   API_KEY=meg_... ./scripts/verify_remote_mcp.sh https://mcp.example.com

set -euo pipefail

BASE="${1:-}"
if [[ -z "$BASE" ]]; then
  echo "usage: $0 https://your-host" >&2
  exit 2
fi
BASE="${BASE%/}"
KEY="${API_KEY:-${DEV_API_KEY:-}}"

echo "== healthz =="
curl -fsS "$BASE/healthz" | python3 -m json.tool

echo "== well-known mcp.json =="
curl -fsS "$BASE/.well-known/mcp.json" | python3 -m json.tool | head -n 40

echo "== well-known ai-catalog.json =="
curl -fsS "$BASE/.well-known/ai-catalog.json" | python3 -m json.tool | head -n 40

echo "== MCP endpoint (expect HTTP response, not connection error) =="
CODE=$(curl -sS -o /tmp/megmis-mcp-probe.txt -w "%{http_code}" \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  ${KEY:+-H "X-API-Key: $KEY"} \
  "$BASE/mcp/" || true)
echo "HTTP $CODE"
head -c 400 /tmp/megmis-mcp-probe.txt || true
echo

if [[ -n "$KEY" ]]; then
  echo "== REST smoke (weather) =="
  curl -fsS -H "X-API-Key: $KEY" \
    "$BASE/api/v1/weather/current?name=Harare" | python3 -m json.tool | head -n 30
else
  echo "(skip REST smoke — set API_KEY or DEV_API_KEY)"
fi

echo
echo "OK — host responds. Wire clients to: $BASE/mcp/"
echo "Remember: only list production URLs in public directories (not staging)."
