# CDP_Merged Status

**Updated At:** 2026-03-14 19:15 CET  
**Execution Mode:** Local-only permanent  
**Azure Deployment:** Disabled for cost control  
**Public URL:** https://kbocdpagent.ngrok.app

---

## Runtime Status

| Component | Port | Status |
|-----------|------|--------|
| Operator Shell (Next.js) | 3000 | ✅ Live |
| Operator API (FastAPI) | 8170 | ✅ Live |
| PostgreSQL | 5432 | ✅ Full dataset (1.94M) |
| Tracardi | 8686/8787 | ⚠️ Optional (profiles: 83) |

---

## Headlines (7 max)

1. **Tracardi optionalization complete** — Core stack verified working without Tracardi (2026-03-14)
2. **Admin panel live** — /admin with basic authorization, non-admin denial verified (2026-03-14)
3. **Typed intents implemented** — 38 tests passing, 10 intent types covering common queries (2026-03-14)
4. **Chainlit deprecated** — Operator Shell (port 3000) is the only supported UI (2026-03-14)
5. **Microsoft Entra ID ready** — Implementation complete, activation blocked until Azure quota reset (2026-03-14)
6. **Model benchmark complete** — Switched from GPT-5 (incompatible) to GPT-4o (2-3x faster) (2026-03-15)
7. **Stable ngrok infrastructure** — Hobbyist plan with fixed domain, systemd-managed (2026-03-14)

---

## Immediate Priority

1. Keep enrichment progressing (background monitoring)
2. Verify Entra auth end-to-end after March 14 quota reset
3. Complete Illustrated Guide v3.3 credibility pass

---

## Active Blockers

None. Azure deployment path intentionally disabled, not blocked.

---

## Canonical Counts (as_of: 2026-03-09)

See `PROJECT_STATE.yaml` section `enrichment.canonical_counts` for authoritative numbers.

Quick reference:
- `total`: 1,940,603 (full KBO dataset)
- `cbe_enriched`: 1,252,019
- `website_url`: 70,922
- `geo_latitude`: 63,979
- `ai_description`: 31,033

---

## References

- **Detailed history:** WORKLOG.md
- **Structured state:** PROJECT_STATE.yaml
- **Active queue:** NEXT_ACTIONS.md
- **Roadmap:** BACKLOG.md
- **Operating rules:** AGENTS.md
