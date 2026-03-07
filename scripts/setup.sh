#!/usr/bin/env bash
# setup.sh — Full local development setup for CDP_Merged
set -euo pipefail

echo "🚀 CDP_Merged Setup"
echo "===================="

# 1. Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 required"; exit 1; }
command -v docker   >/dev/null 2>&1 || { echo "❌ Docker required"; exit 1; }
command -v poetry   >/dev/null 2>&1 || {
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
}

# 2. Install Python dependencies
echo "📦 Installing Python dependencies..."
poetry install --no-interaction

# 3. Set up local override file
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local from template..."
    cp .env.local.example .env.local
    echo "⚠️  Edit .env.local to set your OPENAI_API_KEY and local Tracardi credentials"
fi

# 4. Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
poetry run pre-commit install

# 5. Start the full local stack
echo "🐳 Starting local PostgreSQL, Tracardi, and chatbot..."
docker compose up -d --build

# 6. Wait for Tracardi to be ready
echo "⏳ Waiting for Tracardi to be ready..."
MAX_TRIES=30
for i in $(seq 1 $MAX_TRIES); do
    if curl -fsS http://localhost:8686/healthcheck >/dev/null 2>&1; then
        echo "✅ Tracardi is ready"
        break
    fi
    echo "   Waiting... ($i/$MAX_TRIES)"
    sleep 5
done

echo "⏳ Waiting for chatbot to be ready..."
for i in $(seq 1 $MAX_TRIES); do
    if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
        echo "✅ Chatbot is ready"
        break
    fi
    echo "   Waiting... ($i/$MAX_TRIES)"
    sleep 5
done

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open chatbot:  http://localhost:8000"
echo "  2. Open Tracardi: http://localhost:8787"
echo "  3. Run local regression: .venv/bin/python scripts/regression_local_chatbot.py"
