#!/bin/bash
# Start the MCP server for CDP_Merged
#
# Usage:
#   ./scripts/start_mcp_server.sh              # Stdio mode (for Claude Desktop)
#   ./scripts/start_mcp_server.sh --sse        # SSE mode on port 8001
#   ./scripts/start_mcp_server.sh --sse 8002   # SSE mode on custom port

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)
elif [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Set default database URL if not provided
export DATABASE_URL="${DATABASE_URL:-postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable}"

cd "$PROJECT_ROOT"

# Parse arguments
TRANSPORT="stdio"
PORT="8001"

if [ "$1" == "--sse" ]; then
    TRANSPORT="sse"
    if [ -n "$2" ]; then
        PORT="$2"
    fi
    echo "Starting MCP server in SSE mode on port $PORT..."
    echo "Health check: http://localhost:$PORT/health"
    echo "SSE endpoint: http://localhost:$PORT/sse"
else
    echo "Starting MCP server in stdio mode..."
    echo "Connect via Claude Desktop or other MCP client"
fi

# Run the server
exec poetry run python src/mcp_server.py --transport "$TRANSPORT" --port "$PORT"
