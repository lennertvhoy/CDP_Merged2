# Development Guide — CDP_Merged

## Prerequisites

| Tool | Min Version | Install |
|---|---|---|
| Python | 3.11 | [python.org](https://python.org) |
| Poetry | 1.7+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker & Compose | 24+ | [docker.com](https://docker.com) |
| Git | 2.40+ | OS package manager |

## Quick Start

```bash
# 1. Clone and enter directory
git clone <repo-url>
cd CDP_Merged

# 2. Install dependencies
make install

# 3. Create local overrides with your real OpenAI key
cp .env.local.example .env.local
# Edit .env.local: set OPENAI_API_KEY and your local Tracardi credentials

# 4. Start the full local stack (PostgreSQL, Tracardi, chatbot)
make docker-up

# 5. Open the services
# → Chatbot:  http://localhost:8000
# → Tracardi: http://localhost:8787
```

## Environment Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Local Docker stack forces `openai`; host-only dev can still use `openai`, `azure_openai`, `ollama`, or `mock` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for the provider |
| `OPENAI_API_KEY` | — | Required for OpenAI provider |
| `TRACARDI_API_URL` | `http://localhost:8686` | Tracardi API endpoint |
| `DATABASE_URL` | `postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable` | Local PostgreSQL query plane |
| `FLEXMAIL_ENABLED` | `false` | Enable Flexmail integration |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DEBUG` | `false` | Enable debug mode |

Use `.env.local` for machine-local secrets and local runtime overrides. `.env.example` remains the broad reference file.

## Local Deployment Modes

### Full Docker stack

```bash
make docker-up
docker compose ps
curl http://localhost:8000/healthz
curl http://localhost:8000/readinessz
```

This starts PostgreSQL, Tracardi, and the chatbot locally. Only the OpenAI API stays remote.

### Host-side chatbot for code iteration

```bash
docker compose up -d postgres tracardi-api tracardi-gui elasticsearch redis mysql
./start_chatbot.sh
```

Use this path when you want the app on the host for faster edit/run cycles.

## Using Ollama (Local LLM)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3.1:8b

# Set environment
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Running Tests

```bash
# Unit tests only (fast, no external services)
make test

# Deterministic MVP eval suite with quality gates (non-zero exit on gate failure)
make eval-suite

# Equivalent explicit command with optional threshold overrides
poetry run python -m tests.integration.test_retrieval_grounding_eval_harness \
  --artifact tests/integration/snapshots/eval_suite/eval_summary.json \
  --min-correctness-rate 0.85 \
  --min-groundedness-rate 0.90 \
  --max-failure-rate 0.20 \
  --max-p95-latency-ms 2500

# Unit tests with coverage report
make coverage

# Run a specific test file
poetry run pytest tests/unit/test_validation.py -v

# Run with a specific marker
poetry run pytest -m unit -v

# Local stack regression
.venv/bin/python scripts/regression_local_chatbot.py
```

### Eval suite artifact and gate semantics

- Artifact JSON schema: `eval_summary.v1`
- Default artifact path: `tests/integration/snapshots/eval_suite/eval_summary.json`
- Reported metrics:
  - `correctness_rate`
  - `groundedness_citation_compliance_rate` (for citation-required prompts)
  - `failure_rate`
  - latency summary `latency_ms.p50` and `latency_ms.p95` (+ `mean`)
- Gate source/override order:
  1. CLI flags (highest priority)
  2. Environment variables
     - `EVAL_MIN_CORRECTNESS_RATE`
     - `EVAL_MIN_GROUNDEDNESS_RATE`
     - `EVAL_MAX_FAILURE_RATE`
     - `EVAL_MAX_P95_LATENCY_MS`
  3. Built-in defaults (0.85 / 0.90 / 0.20 / 2500)
- Exit semantics:
  - exit `0` when all gates pass
  - exit `1` when any gate fails

## Linting and Formatting

```bash
# Check linting
make lint

# Auto-fix and format
make format

# Type checking
make type-check
```

## Pre-commit Hooks

```bash
# Install hooks (once)
make pre-commit-install

# Run manually on all files
make pre-commit-run
```

## Project Structure

```
src/
├── app.py              # Chainlit entry point
├── config.py           # Pydantic settings
├── core/               # Shared utilities
│   ├── constants.py    # App-wide constants
│   ├── exceptions.py   # Custom exception types
│   ├── logger.py       # Structlog configuration
│   ├── llm_provider.py # Multi-LLM abstraction
│   ├── metrics.py      # Prometheus metrics
│   └── validation.py   # Query security validation
├── graph/              # LangGraph workflow
│   ├── edges.py        # Edge condition functions
│   ├── nodes.py        # Router + Agent nodes
│   ├── state.py        # AgentState TypedDict
│   └── workflow.py     # Graph assembly
├── ai_interface/       # AI tools & schemas
│   ├── schemas.py      # Pydantic response models
│   └── tools.py        # LangChain tool definitions
├── services/           # External service clients
│   ├── base.py         # BaseService with retry
│   ├── tracardi.py     # Tracardi CDP client
│   └── flexmail.py     # Flexmail API client
└── search_engine/      # Query building
    ├── factory.py      # QueryFactory (strategy)
    ├── interfaces.py   # QueryBuilder ABC
    ├── schema.py       # ProfileSearchParams
    └── builders/
        ├── tql_builder.py  # Tracardi Query Language
        ├── sql_builder.py  # SQL builder
        └── es_builder.py   # Elasticsearch DSL
```

## Adding a New LLM Provider

1. Create a class inheriting from `BaseLLMProvider` in `src/core/llm_provider.py`
2. Implement `generate()` and `generate_structured()`
3. Add the provider name to `LLMMode` enum
4. Register in `get_llm_provider()` factory function
5. Add tests in `tests/unit/test_llm_provider.py`
