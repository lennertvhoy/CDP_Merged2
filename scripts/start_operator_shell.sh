#!/usr/bin/env bash
# Start the operator shell (Next.js app) on port 3000 (or 3001 if 3000 is occupied by ghost process)
# This must be run on the host (not in a sandbox)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SHELL_DIR="$REPO_ROOT/apps/operator-shell"
LOG_FILE="/tmp/operator-shell.log"

# Use linuxbrew node if available
export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"

# Verify node is available
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found in PATH"
    echo "Please ensure Node.js is installed (e.g., via linuxbrew)"
    exit 1
fi

echo "Using Node.js: $(node -v)"

# Change to shell directory
cd "$SHELL_DIR"

# Check if .env.local exists, create if not
if [[ ! -f .env.local ]]; then
    echo "Creating .env.local with default settings..."
    cat > .env.local << 'EOF'
OPERATOR_API_ORIGIN=http://127.0.0.1:8170
CHAT_RUNTIME_ORIGIN=http://127.0.0.1:8000
EOF
fi

# Source environment
set -a
source .env.local
set +a

# Determine which port to use
# Try 3000 first, but if ghost process exists, use 3001
SHELL_PORT=3000
if curl -s --max-time 1 http://127.0.0.1:3000/ > /dev/null 2>&1; then
    # Port 3000 is responding but might be a ghost process
    # Check if it's serving static files correctly
    if ! curl -s --max-time 2 http://127.0.0.1:3000/_next/static/chunks/main-app-26fb858ab1a9f565.js > /dev/null 2>&1; then
        echo "WARNING: Port 3000 has a ghost process (not serving static files)"
        echo "Switching to port 3001..."
        SHELL_PORT=3001
        LOG_FILE="/tmp/operator-shell-3001.log"
    fi
fi

# Kill any existing processes
pkill -9 -f "node.*server.js" 2>/dev/null || true
sleep 2

# Check if standalone build exists
if [[ ! -f .next/standalone/server.js ]]; then
    echo "ERROR: Standalone build not found. Building now..."
    npm run build
fi

# Ensure static files are copied to standalone directory
if [[ -d .next/static ]] && [[ -d .next/standalone/.next ]]; then
    echo "Copying static files to standalone directory..."
    cp -r .next/static/* .next/standalone/.next/static/ 2>/dev/null || true
fi

# Start the standalone server with explicit localhost binding
export HOSTNAME=127.0.0.1
export PORT=$SHELL_PORT
cd .next/standalone
nohup node server.js > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

echo "Started operator shell (PID: $SERVER_PID) on port $SHELL_PORT"
echo "Log file: $LOG_FILE"
echo ""
echo "Waiting for server to be ready..."

# Wait for server to be ready
for i in {1..30}; do
    if curl -s --max-time 1 "http://127.0.0.1:$SHELL_PORT/" > /dev/null 2>&1; then
        # Also verify static files work
        if curl -s --max-time 2 "http://127.0.0.1:$SHELL_PORT/_next/static/chunks/main-app-26fb858ab1a9f565.js" > /dev/null 2>&1; then
            echo ""
            echo "✓ Operator shell is running!"
            echo "  Local: http://localhost:$SHELL_PORT"
            
            # Get ngrok URL if available
            NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'] if d.get('tunnels') else '')" 2>/dev/null || true)
            if [[ -n "$NGROK_URL" ]]; then
                echo "  Public: $NGROK_URL"
            fi
            
            echo ""
            echo "To view logs: tail -f $LOG_FILE"
            echo "To stop: pkill -f 'node.*server.js'"
            exit 0
        fi
    fi
    sleep 1
done

echo ""
echo "ERROR: Server failed to start within 30 seconds"
echo "Check logs: $LOG_FILE"
exit 1
