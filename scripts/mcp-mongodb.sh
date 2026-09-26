#!/usr/bin/env bash
# Launches the MongoDB MCP server with credentials from the repo's gitignored .env.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi
: "${MDB_MCP_CONNECTION_STRING:?Set MDB_MCP_CONNECTION_STRING in .env}"
case "$MDB_MCP_CONNECTION_STRING" in *'<db_password>'*) echo "Replace <db_password> in .env" >&2; exit 1;; esac
export MDB_MCP_READ_ONLY="${MDB_MCP_READ_ONLY:-true}"
exec npx -y "mongodb-mcp-server@<3"
