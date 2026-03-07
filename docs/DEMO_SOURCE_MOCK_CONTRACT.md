# Demo Source Mock Contract

**Purpose:** Define one hyperrealistic mock standard for demo-only source integrations.  
**Status:** Active for the demo-first track as of 2026-03-04.  
**Scope:** Exact Online, Teamleader, and Autotask.

This document exists because the current repo only has hard-coded demo scripts in:

- `scripts/demo_exact_integration.py`
- `scripts/demo_teamleader_integration.py`
- `scripts/demo_autotask_integration.py`

Those scripts are useful for narration, but they are not yet a reusable mock system. They do not currently preserve vendor-specific auth, pagination, webhook behavior, or failure modes in a consistent way.

## Current Provenance Baseline

As of 2026-03-04, the Teamleader demo runs as a live Teamleader slice when local credentials are available, with mock fallback only if no company-linked events are visible on the fetched page. Exact and Autotask remain `mock` until current-state docs record verified live access.

| Source | Current provenance | Near-term target | Why it exists in the demo |
|--------|--------------------|------------------|---------------------------|
| Teamleader | `real` | Harden pagination/rate-limit handling while preserving mock fallback scenarios | CRM contacts, deals, and activity history |
| Exact Online | `mock` | Upgrade to `real` if trial/demo access is sufficient | Financial health, invoices, payment behavior |
| Autotask | `mock` | Keep `mock` until vendor/demo access exists | Service tickets, contracts, assets, SLA context |

## Contract Rules For Every Mock Source

### 1. Provenance Must Be Explicit

Every mock flow must expose:

- `source_name`
- `provenance`: `real`, `mock`, or `hybrid`
- `mock_scenario_id` when the source is not fully real
- `contract_version`
- `captured_at` or `generated_at`
- `source_record_url` or a clear placeholder when a live vendor URL does not exist

The UI may present a source as connected for the demo, but logs and current docs must stay honest about provenance.

### 2. Auth Must Look Vendor-Realistic

Do not jump straight to data. Each mock must model the source-specific auth ceremony and its likely failure cases.

Minimum auth scenarios:

- success
- expired credential
- revoked or invalid credential
- insufficient scope or permission

The response shape should look like the vendor family being modeled, not a generic `{"ok": true}` placeholder.

### 3. IDs, Timestamps, And Payload Shapes Must Stay Stable

Mocks must use:

- stable external IDs per source
- realistic foreign-key relationships between company, contact, deal, invoice, contract, ticket, and asset records
- ISO 8601 timestamps in UTC unless the vendor behavior requires a different format
- realistic sparse or partial data, not only perfect records

At least one scenario per source must include missing optional fields.

### 4. Pagination And Filtering Must Behave Like The Source

At least one fixture set per source must require multiple pages and carry the same paging fields the real source would expose.

Required cases:

- first page
- middle page
- last page
- empty result
- filtered result with checkpoint or cursor semantics

### 5. Eventing Must Be Demo-Realistic

If the real source uses webhooks, the mock must provide webhook-shaped callbacks. If the real source is more naturally polled, the mock must still provide delta snapshots or change events that look operationally real.

Required cases:

- initial sync
- incremental update
- deletion, closure, or cancellation event
- retry after transient failure

### 6. Failures Must Be Visible

Each source needs at least these non-happy-path scenarios:

- auth failure
- rate limit or quota pressure
- upstream `5xx` or timeout
- partial data validation failure

The goal is not to be exhaustive. The goal is to stop the demo from teaching the wrong behavior.

### 7. Mapping To CDP Must Preserve Source Context

Every mock payload that becomes a CDP trait, metric, or event must preserve:

- source system name
- external record ID
- sync timestamp
- provenance label
- scenario ID when mocked

This prevents demo-only data from looking like verified production data.

## Source Profiles

### Exact Online

**Reference basis:** `docs/research/RESEARCH_ANALYSIS_2026-02-28.md`

Mocks for Exact must preserve these behaviors:

- OAuth-style authentication
- regional endpoint choice such as `start.exactonline.be`
- mandatory division context
- OData-style list/query behavior
- 60-record maximum page behavior
- ID-based checkpointing or modified-since sync behavior

Required demo scenarios:

- paid invoice history
- open invoice and outstanding balance
- slow or failed sync caused by bad division or auth
- paginated invoice retrieval over more than one page

### Teamleader

**Reference basis:** `docs/research/RESEARCH_ANALYSIS_2026-02-28.md`, `docs/PROMPT_HYBRID_ARCHITECTURE.md`

Mocks for Teamleader must preserve these behaviors:

- OAuth 2.0 with PKCE-style flow
- one-hour access token behavior with refresh semantics
- `page[number]` and `page[size]` pagination
- `companies.search` or `people.search` style retrieval
- `include`-style sideloading expectations
- `X-RateLimit-*` response headers
- signed webhook callbacks using `X-Teamleader-Signature`

Required demo scenarios:

- company + contacts + deals happy path
- multi-page contact or activity retrieval
- rate-limit warning or retry behavior
- signed webhook for a company or contact update

### Autotask

**Reference basis:** `docs/research/RESEARCH_ANALYSIS_2026-02-28.md`

Mocks for Autotask must preserve these behaviors:

- zone-aware authentication and endpoint selection
- API key style credential handling
- 500-record maximum query behavior
- `id > last_id` style pagination or checkpointing
- tenant-wide quota pressure as a first-class behavior

Required demo scenarios:

- open and in-progress ticket set
- active contract and asset inventory
- quota-pressure or throttling scenario
- incremental sync using last-seen ID semantics

Autotask is mock-first for now, so its failure and rate-limit behavior matters more than polish. The demo should teach that this connector is operationally sensitive, not trivial.

## Fixture And Scenario Structure

When these mocks are implemented beyond the current hard-coded scripts, keep one structure across all three sources:

```text
<future fixture home>/
  <source>/
    scenario_manifest.json
    auth/
    pages/
    events/
    failures/
```

Each scenario manifest should declare:

- `scenario_id`
- `source`
- `provenance`
- `records_included`
- `paging_mode`
- `failure_mode`
- `expected_cdp_traits`

## Minimum Compliance Checklist

A demo source is contract-compliant only when all of the following are true:

- auth is source-shaped, not generic
- at least one paginated scenario exists
- at least one failure scenario exists
- event or delta behavior exists
- provenance is visible in docs or runtime output
- CDP-mapped outputs preserve source IDs and provenance

## Current Repo Gap

As of 2026-03-04, the existing demo scripts are still below this contract:

- they are single-scenario happy-path demos
- they do not expose a shared provenance surface
- they do not model pagination in a reusable way
- they do not model realistic failure or retry behavior
- they are not yet backed by reusable fixture sets

That gap is acceptable for today only if the current docs keep calling them `mock` and do not present them as completed production integrations.
