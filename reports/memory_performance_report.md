# Memory Backend Performance Comparison Report

**Date:** 2026-02-25  
**Test Environment:** ff-en-i3-oc (Linux 6.18.9, AMD 12-core/24-thread)  
**Network:** Residential fiber connection

---

## Executive Summary

Benchmark comparing Cloud Mem0 (hosted at app.mem0.ai) against local file-based storage for the CDP_Merged KBO agent project. **File-based operations are ~10,000-26,000x faster** than cloud API calls.

---

## Test Results

### Raw Latency Measurements

| Backend | Operation | Mean Latency | Min | Max | Std Dev |
|---------|-----------|--------------|-----|-----|---------|
| **Cloud Mem0** | Store | 1,194.9 ms | 997.7 ms | 1,774.1 ms | 296.9 ms |
| **Cloud Mem0** | Search | 1,035.9 ms | 950.2 ms | 1,211.3 ms | 91.5 ms |
| **File-based** | Read | 0.04 ms | 0.03 ms | 0.07 ms | ~0 |
| **File-based** | Write | 0.12 ms | 0.03 ms | 0.28 ms | ~0 |

### Performance Multipliers

| Comparison | Multiplier |
|------------|------------|
| Cloud Store vs File Write | **10,270x slower** |
| Cloud Search vs File Read | **25,771x slower** |
| Cloud Store vs File Read | **29,873x slower** |

---

## Detailed Analysis

### Cloud Mem0 Characteristics

**Observed Behavior:**
- Store operations: ~1.2s average (variable, 1.0-1.8s range)
- Search operations: ~1.0s average (more consistent, 0.95-1.2s range)
- Network latency dominates (likely 150-250ms RTT to US-based servers)
- Additional processing time for embedding generation and vector search

**Implications for 516K Profile Dataset:**
- **Sequential store of all profiles:** ~172 hours (7+ days) if done one-by-one
- **Bulk/batch operations:** Essential for any large-scale ingestion
- **Search during operation:** Each search adds ~1s delay to user queries

### File-Based Characteristics

**Observed Behavior:**
- Read latency: ~0.04ms (effectively instant)
- Write latency: ~0.12ms (still extremely fast)
- Performance limited by local SSD I/O, not network

**Implications:**
- **Sequential store of all profiles:** ~62 seconds for 516K records
- **Search capability:** Requires grep/ripgrep or in-memory indexing
- **No network dependency:** Works offline, no API rate limits

---

## Use Case Recommendations

### When to Use Cloud Mem0

✅ **Good for:**
- Cross-device memory persistence
- Multi-agent shared memory
- Production systems requiring managed infrastructure
- Semantic search with natural language queries
- Cases where ~1s latency is acceptable

❌ **Avoid for:**
- High-frequency write operations (>1 write/sec)
- Real-time interactive applications
- Large batch ingestions without bulk API
- Latency-sensitive workflows

### When to Use File-Based Storage

✅ **Good for:**
- Local-first development workflows
- Fast iteration and testing
- Offline-capable systems
- High-frequency read/write operations
- Simple key-value or append-only storage

❌ **Avoid for:**
- Semantic/natural language search
- Multi-device synchronization needs
- Complex querying requirements
- Shared memory across agents

### Hybrid Approach (Recommended for CDP_Merged)

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Session                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐     ┌──────────────┐     ┌────────────┐  │
│  │  Local Cache │────▶│  File Store  │────▶│  Snapshot  │  │
│  │  (In-Memory) │◀────│  (MEMORY.md) │◀────│   Export   │  │
│  └──────────────┘     └──────────────┘     └────────────┘  │
│         │                      │                            │
│         ▼                      ▼                            │
│  ┌─────────────────────────────────────────┐                │
│  │         Periodic Cloud Sync             │                │
│  │  (Nightly or manual triggered backup)   │                │
│  └─────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Strategy:**
1. **Primary storage:** Local files for KBO profiles (fast access)
2. **Search:** Local ripgrep for exact matches, optional local vector DB for semantic
3. **Backup:** Nightly batch sync to cloud Mem0 for cross-device access
4. **Memory management:** Compaction strategy for MEMORY.md to prevent bloat

---

## Cost Considerations

### Cloud Mem0 Pricing
- API calls are metered
- 516K profile stores = 516K API calls minimum
- Search operations add additional costs
- Consider batch APIs if available

### File-Based Costs
- Storage: Negligible (~50MB for 516K text records)
- I/O: Limited only by hardware
- No external dependencies or quotas

---

## Action Items

1. **Immediate:** Proceed with file-based storage for CDP_Merged KBO agent
2. **Short-term:** Implement local vector DB (Chroma, Qdrant) for semantic search
3. **Medium-term:** Design nightly cloud backup strategy
4. **Long-term:** Evaluate local Mem0 setup for hybrid benefits

---

## Local Mem0 Setup (Optional Future Work)

If cross-device sync becomes critical, consider local Mem0 deployment:

```bash
# Prerequisites
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text
docker run -d -p 6333:6333 qdrant/qdrant

# Expected performance: ~50ms store, ~20ms search
# Trade-off: Setup complexity vs cloud latency
```

---

## Conclusion

**For the CDP_Merged project with 516K KBO profiles, file-based storage is the clear winner** for local development and operation. The ~10,000x performance advantage is decisive for batch operations and interactive use.

Cloud Mem0 remains valuable as a backup/sync target but should not be the primary storage for latency-sensitive agent operations.

---

*Report generated by benchmark script: `scripts/benchmark_memory.py`*  
*Results saved to: `reports/memory_benchmark.json`*
