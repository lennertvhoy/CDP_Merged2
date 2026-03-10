# Test Plan for CDP_Merged

## Overview

This document outlines how to verify that the merged project works correctly.

## Prerequisites

1. Docker and Docker Compose installed
2. Python 3.12+ with uv
3. OpenAI API key (or Ollama installed)

## Test Categories

### 1. Infrastructure Tests

#### Test 1.1: Docker Compose Starts Successfully
```bash
cd /home/ff/Documents/CDP_Merged
docker-compose up -d
```
**Expected:** All services start without errors
**Verify:**
```bash
docker-compose ps
# Should show: elasticsearch, redis, mysql, tracardi-api, tracardi-gui, wiremock
```

#### Test 1.2: Tracardi Health Check
```bash
curl http://localhost:8686/health
```
**Expected:** HTTP 200 with health status

#### Test 1.3: Elasticsearch Health
```bash
curl http://localhost:9200/_cluster/health
```
**Expected:** `status` is `yellow` or `green`

---

### 2. Configuration Tests

#### Test 2.1: Environment Variables Load
```bash
cp .env.example .env
# Edit with test values
uv run python -c "from src.config import settings; print(settings.TRACARDI_API_URL)"
```
**Expected:** Prints the configured URL

#### Test 2.2: Multi-LLM Provider Selection
```bash
# Test OpenAI
LLM_PROVIDER=openai uv run python -c "
from src.core.llm_provider import get_llm_provider
p = get_llm_provider()
print(type(p).__name__)
"
```
**Expected:** `OpenAIProvider`

```bash
# Test Mock (no API key needed)
LLM_PROVIDER=mock uv run python -c "
from src.core.llm_provider import get_llm_provider
p = get_llm_provider()
print(type(p).__name__)
"
```
**Expected:** `MockProvider`

---

### 3. Service Tests

#### Test 3.1: Tracardi Client Authentication
```bash
uv run python -c "
import asyncio
from src.services.tracardi import TracardiClient

async def test():
    client = TracardiClient()
    await client._ensure_token()
    print('Token acquired:', bool(client.token))

asyncio.run(test())
"
```
**Expected:** `Token acquired: True`

#### Test 3.2: Profile Search (Empty)
```bash
uv run python -c "
import asyncio
from src.services.tracardi import TracardiClient

async def test():
    client = TracardiClient()
    result = await client.search_profiles('traits.name=\"NonExistent\", limit=1')
    print('Total:', result.get('total'))

asyncio.run(test())
"
```
**Expected:** `Total: 0` (or small number if data exists)

---

### 4. Query Builder Tests

#### Test 4.1: TQL Builder
```bash
uv run python -c "
from src.search_engine.schema import ProfileSearchParams
from src.search_engine.builders.tql_builder import TQLBuilder

params = ProfileSearchParams(city='Gent', status='AC')
builder = TQLBuilder()
query = builder.build(params)
print('TQL:', query)
"
```
**Expected:** Valid TQL query string with city and status conditions

#### Test 4.2: NACE Code Lookup
```bash
uv run python -c "
from src.ai_interface.tools import _get_nace_codes_from_keyword
codes = _get_nace_codes_from_keyword('IT')
print('IT codes:', codes)
"
```
**Expected:** List including 62010, 62020, etc.

---

### 5. Integration Tests

#### Test 5.1: KBO Data Ingestion (if data available)
```bash
# Place KBO CSVs in data/kbo/
uv run python src/ingestion/tracardi_loader.py
```
**Expected:** Successfully imports profiles to Tracardi

#### Test 5.2: End-to-End NLQ Flow
```bash
# Start the app
uv run chainlit run src/app.py &

# In browser, test:
# 1. Open http://localhost:8000
# 2. Type: "How many companies in Gent?"
# 3. Expect: Count response with sample profiles
```

---

### 6. Validation Tests

#### Test 6.1: Query Validation (Critic)
```bash
uv run python -c "
from src.core.validation import validate_query

# Safe query
result = validate_query('SELECT * FROM profiles WHERE city = \"Gent\"')
print('Safe query valid:', result['valid'])

# Dangerous query
result = validate_query('DROP TABLE profiles')
print('Dangerous query valid:', result['valid'])
print('Error:', result.get('error'))
"
```
**Expected:** Safe=valid, Dangerous=invalid with error

---

## Automated Test Suite

Run all tests:
```bash
uv run pytest tests/ -v
```

## Manual Acceptance Criteria

| # | Test | Expected Result |
|---|------|-----------------|
| 1 | Ask "How many IT companies in Gent?" | Returns count > 0 |
| 2 | Ask "Create segment X of companies in Brussels" | Segment created |
| 3 | Push segment to Flexmail | Contacts added |
| 4 | End-to-end time | < 60 seconds |
| 5 | Query validation | Destructive queries blocked |

## Debugging

### Check Service Logs
```bash
docker-compose logs -f tracardi-api
docker-compose logs -f agent
```

### Verify Network
```bash
docker network ls
docker network inspect cdp_merged_default
```

### Reset Everything
```bash
docker-compose down -v
docker-compose up -d
```
