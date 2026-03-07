#!/bin/bash
# Setup webhook tunnel for Resend integration

echo "=== CDP Webhook Tunnel Setup ==="
echo ""
echo "This script helps set up a tunnel to receive Resend webhooks."
echo ""
echo "Prerequisites:"
echo "  - ngrok with auth token, OR"
echo "  - cloudflared installed, OR"  
echo "  - localtunnel (npm install -g localtunnel)"
echo ""

# Check for ngrok
if command -v ngrok &> /dev/null; then
    echo "✓ ngrok found"
    echo "Starting ngrok tunnel to 137.117.212.154:8686..."
    ngrok http 137.117.212.154:8686
    exit 0
fi

# Check for cloudflared
if command -v cloudflared &> /dev/null; then
    echo "✓ cloudflared found"
    echo "Starting Cloudflare tunnel to 137.117.212.154:8686..."
    cloudflared tunnel --url http://137.117.212.154:8686
    exit 0
fi

# Fallback to localtunnel
echo "Using localtunnel (may expire periodically)..."
npx localtunnel --port 8686 --local-host 137.117.212.154
