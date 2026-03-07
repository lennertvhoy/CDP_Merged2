# Archived Scripts

This folder contains older/deprecated scripts that have been replaced by newer implementations.

## Import Scripts (Replaced by `import_kbo_streaming.py`)

| Script | Replaced By | Reason |
|--------|-------------|--------|
| `import_kbo.py` | `import_kbo_streaming.py` | Streaming uses 50x less memory, 10x faster |
| `import_kbo_filtered.py` | `import_kbo_streaming.py` | Filters now in streaming importer |
| `import_kbo_logged.py` | `import_kbo_streaming.py` | Logging integrated |
| `import_kbo_robust.py` | `import_kbo_streaming.py` | Robustness features merged |

## Offline Processing Scripts (Replaced by PostgreSQL Pipeline)

| Script | Replaced By | Reason |
|--------|-------------|--------|
| `enrich_kbo.py` | `src/enrichment/postgresql_pipeline.py` | Enrichment now runs directly on PostgreSQL |
| `cleanup_kbo.py` | PostgreSQL constraints/validation | Cleanup now done during import |
| `validate_kbo.py` | Data quality checks in streaming importer | Validation integrated |

## Legacy Tracardi-Based Runners (Replaced by PostgreSQL)

| Script | Replaced By | Reason |
|--------|-------------|--------|
| `run_phase1.py` | `run_phase2.sh` | PostgreSQL streaming pipeline, Tracardi deferred |
| `run_enrichment_streaming.py` | `run_phase2.sh` | PostgreSQL streaming pipeline, Tracardi deferred |

**Note:** Tracardi deployment is deferred until Phase 2 enrichment completes. When rebuilt, it will use MySQL (not Elasticsearch) for active profiles only (~10K), not all 1.8M companies.

## Deleted Files

| File | Location | Reason |
|------|----------|--------|
| `pipeline.py` | `src/enrichment/` | Legacy ES-based Tracardi pipeline, wrong architecture, has bugs |
| `test_pipeline.py` | `tests/` | Tests for deleted code |
| `cdp-enrichment-tracardi.service` | Root | Obsolete systemd service |

## Schema

| File | Replaced By | Reason |
|------|-------------|--------|
| `schema.sql` | `schema_optimized.sql` | Optimized schema has 10 new indexes, better performance |

---

**Note:** These scripts are kept for reference but are no longer maintained.
Use the newer versions in the main folders.
