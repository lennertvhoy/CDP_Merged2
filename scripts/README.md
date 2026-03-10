# Scripts

This directory contains operational helpers, sync jobs, enrichment runners, demo utilities, and local verification tooling for the repo.

## Dependency And Runtime Model

Use the repo root as the working directory and use Poetry for Python dependencies:

```bash
poetry install
```

Run Python entry points through Poetry so they use the same environment as the application:

```bash
poetry run python scripts/<script_name>.py ...
```

Run shell helpers from the repo root:

```bash
bash scripts/<script_name>.sh
```

There is no separate maintained `scripts/requirements.txt` workflow. The canonical dependency source is the root `pyproject.toml`.

## Common Workflows

### Local stack setup

```bash
./scripts/setup.sh
docker compose up -d --build
```

### Sync source data into PostgreSQL

```bash
poetry run python scripts/sync_teamleader_to_postgres.py --full
poetry run python scripts/sync_exact_to_postgres.py --full
poetry run python scripts/sync_autotask_to_postgres.py --full
```

### Run enrichment

```bash
poetry run python scripts/enrich_companies_batch.py --enrichers website --limit 25 --batch-size 25
bash scripts/run_enrichment_persistent.sh
bash scripts/monitor_enrichment.sh
```

### Verify chatbot or auth behavior

```bash
poetry run python scripts/regression_local_chatbot.py
poetry run python scripts/setup_azure_ad_auth.py
python3 scripts/doc_lint.py
```

## Directory Notes

- `scripts/migrations/` holds SQL migrations used by local and demo workflows.
- `scripts/archive/` holds legacy offline KBO cleanup/enrichment scripts and historical notes. Do not treat that folder as the current operator workflow.
- `scripts/data_cleanup/` contains older Tracardi cleanup material that still needs explicit historical review before reuse.

## Legacy Note

Older docs may still mention `cleanup_kbo.py`, `enrich_kbo.py`, `validate_kbo.py`, or `pip install -r requirements.txt`. Those references describe an older offline workflow and should be treated as historical unless they explicitly point to `scripts/archive/`.
