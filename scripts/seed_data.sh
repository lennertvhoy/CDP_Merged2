#!/usr/bin/env bash
# seed_data.sh — Load KBO CSV data into Tracardi
set -euo pipefail

KBO_CSV="${1:-}"

if [ -z "$KBO_CSV" ]; then
    echo "Usage: ./scripts/seed_data.sh /path/to/kbo_data.csv"
    echo ""
    echo "Expected CSV columns: enterprise_number, name, city, zip_code,"
    echo "  status, nace_code, start_date, juridical_form, email, phone"
    exit 1
fi

if [ ! -f "$KBO_CSV" ]; then
    echo "❌ File not found: $KBO_CSV"
    exit 1
fi

echo "📦 Loading KBO data from: $KBO_CSV"
echo "🚀 Starting ingestion..."

uv run python -c "
import asyncio
import sys
from src.ingestion.tracardi_loader import TracardiBatchLoader

async def main():
    loader = TracardiBatchLoader()
    result = await loader.load_from_csv('$KBO_CSV')
    print(f'✅ Loaded {result.get(\"loaded\", 0)} profiles')
    print(f'❌ Failed: {result.get(\"failed\", 0)} profiles')
    print(f'⏱️  Duration: {result.get(\"duration_s\", 0):.1f}s')

asyncio.run(main())
"

echo "Done! Check Tracardi at http://localhost:8787"
