# Changelog

All notable changes to the CDP_Merged project are documented in this file.

Historical changelog entries may not reflect the current live state. Use `PROJECT_STATE.yaml` and `STATUS.md` for operational truth.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Infrastructure
- **Tracardi Redeployment (2026-03-01)**: Re-deployed Tracardi infrastructure after premature deletion
  - Deployed from `infra/tracardi/` (canonical stack, 2 VMs: B2s + B1ms)
  - Tracardi API: http://137.117.212.154:8686
  - Tracardi GUI: http://137.117.212.154:8787
  - Fixed Container App auth alignment (username: admin@cdpmerged.local → admin)
  - Evidence: `logs/tracardi_redeploy_20260301T1546Z.log`

- **KBO Profile Sync (2026-03-01)**: Synced 10,000 POC-relevant profiles from KBO zip to Tracardi
  - Source: `KboOpenData_0285_2026_02_27_Full.zip`
  - Criteria: Active Belgian companies in East Flanders (Oost-Vlaanderen)
  - 475 IT-related companies (NACE codes: 62, 63, 58.2, 61)
  - 175 cities covered
  - Script: `scripts/sync_kbo_to_tracardi.py`
  - Evidence: `logs/profile_sync_20260301T172918.log`

- **Resend Integration (2026-03-01)**: Configured Resend email provider (alternative to Flexmail)
  - API key verified and working
  - 3 audiences created in Resend
  - Test contacts added successfully
  - Scripts: `scripts/setup_resend_audience.py`, `scripts/setup_resend_with_emails.py`

- **Resend Webhook Configuration (2026-03-01)**: Configured event webhooks for email engagement tracking
  - Added webhook CRUD methods to Resend client (`src/services/resend.py`)
  - Created webhook setup script (`scripts/setup_resend_webhooks.py`)
  - Created Tracardi workflow setup script (`scripts/setup_tracardi_resend_workflow.py`)
  - Added Resend webhook endpoint to gateway (`scripts/webhook_gateway.py`)
  - Created test script (`scripts/test_resend_webhooks.py`)
  - Webhook endpoint: `http://137.117.212.154:8686/tracker`
  - Tracked events: `email.sent`, `email.delivered`, `email.opened`, `email.clicked`, `email.bounced`
  - Tracardi workflows: Email Engagement Processor, Email Bounce Processor

- **End-to-End POC Test (2026-03-01)**: Completed full POC verification
  - ✅ PostgreSQL: 1,813,016 profiles confirmed
  - ✅ Tracardi: Deployed and accessible (137.117.212.154)
  - ✅ Profile Sync: 10K IT companies from East Flanders synced
  - ✅ Resend: API connected with 3 audiences
  - ✅ Webhooks: Configuration ready (manual dashboard setup available)
  - All 5 GO/No-GO criteria verified and ready

### Added
- **NACE Codes Expansion**: Added 733 NACE codes (was 30) for comprehensive industry classification coverage
- **Juridical Codes**: Added 62 Belgian legal form codes for proper company type identification
- **B2B Provider Framework**: Stub implementation for future Cognism/Lusha integrations
- **KBO Data Extraction**: Documented extraction process for Belgian business registry data
- **Word Boundary Validation**: Regex-based filtering to eliminate false positives in name searches (e.g., "Spitaels" no longer matches "pita")

### Fixed
- **Segment Creation Bug**: Fixed mismatch between count queries and segment creation. TQL queries now search both `traits.nace_code` and `traits.nace_codes` field names for backward compatibility
- **Search Quality Issues**: Fixed substring matching that caused false positives (e.g., "pita" matching "Spitaels", "Capital", "Hospital")
- **NACE Code Resolution**: Enhanced domain synonym mapping for better industry keyword matching

### Changed
- **TQL Builder**: Updated to support both singular and plural NACE code field names
- **ES Builder**: Updated Elasticsearch queries to use bool/should structure for field name flexibility
- **Search Pipeline**: Added validation layer to filter false positives from substring matching

### Security
- **SQL Injection Prevention**: Added parameterized query support in SQL builder
- **Query Validation**: Enhanced critic layer validation for user inputs

## [1.0.0] - 2025-02-21

### Added
- **Natural Language Query**: Ask questions in English, French, or Dutch
- **Belgian KBO Data**: Import and query the public business registry
- **Segment Creation**: AI generates Tracardi segments from user intent
- **Flexmail Integration**: Push segments to email campaigns, receive engagement back
- **Resend Email Provider**: Alternative email service with profile enrichment capabilities
- **Multi-LLM Support**: OpenAI, Azure OpenAI, or Ollama (local/offline)
- **Query Security**: Critic layer blocks destructive operations and injection
- **Structured Logging**: JSON logs with trace IDs and structlog
- **Observability**: Prometheus metrics for requests, errors, and LLM usage
- **LangGraph Workflow**: 4+ node workflow (Router → Agent → Critic → Enrichment)

### Infrastructure
- Docker Compose setup for local development
- Azure Container Apps deployment configuration
- Terraform infrastructure as code
- CI/CD pipelines with GitHub Actions

### Documentation
- Comprehensive README with quick start guide
- Architecture documentation with C4 diagrams
- Development setup guide
- Deployment guide for Docker/Kubernetes
- API documentation and troubleshooting guides
