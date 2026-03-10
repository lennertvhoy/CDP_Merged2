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
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD=("$PROJECT_ROOT/.venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
    PYTHON_CMD=(uv run python)
else
    PYTHON_CMD=(python)
fi

exec "${PYTHON_CMD[@]}" src/mcp_server.py --transport "$TRANSPORT" --port "$PORT"
