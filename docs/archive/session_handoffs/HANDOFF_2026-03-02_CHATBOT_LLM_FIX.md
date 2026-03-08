# Handoff: Chatbot LLM Configuration Fix Required

**Date:** 2026-03-02  
**Canonical Repo:** `/home/ff/.openclaw/workspace/repos/CDP_Merged`  
**Task:** Research Analysis → Chatbot LLM Fix  
**Status:** HALT

---

## Read First

1. `AGENTS.md` - Operating rules
2. `STATUS.md` - Current state snapshot
3. `PROJECT_STATE.yaml` - Structured live state
4. `NEXT_ACTIONS.md` - Active queue (shows LLM fix as new priority)
5. This handover

---

## Non-Negotiable Rules

- Work only in `/home/ff/.openclaw/workspace/repos/CDP_Merged`
- Do not work in `/home/ff/.openclaw/workspace/CDP_Merged`
- Treat `PROJECT_STATE.yaml` as required
- Do not restate live status in multiple docs unless updating a summary from `PROJECT_STATE.yaml`
- Do not use `git add -A` by default
- Do not commit or push unless the change set is reviewed, scoped, and intentional
- After each meaningful task, update `PROJECT_STATE.yaml` and `WORKLOG.md`

---

## Verification Labels

Use one of these labels for every operational claim:
- `observed` - verified directly in the current session
- `reported` - supported by logs or prior documentation, but not re-verified now
- `blocked` - verification attempted, but environment/tooling prevented it
- `assumed` - temporary working assumption; avoid when possible

---

## Current Objectives

### 1. Fix Chatbot LLM Provider Configuration
**Status:** `reported` until verified directly.

**Problem:**
Chatbot returns 401 error when processing queries:
```
Error code: 401 - {'error': {'message': 'Incorrect API key provided: mock-key', ...}}
```

**Root Cause:**
- Chatbot starts successfully (`observed`)
- Tracardi authentication works (`observed`)
- LLM provider configured with `mock-key` instead of actual credentials
- Likely `LLM_PROVIDER=openai` with no valid `OPENAI_API_KEY` set

**Code Location:**
- Config: `src/config.py:283` - defaults to `"mock-key"`
- Provider selection: `src/graph/nodes.py:223-287`
- Environment: `.env` file

**Goal:**
Configure valid LLM credentials so chatbot responds to NL queries without 401 errors.

**Fix Options (choose one):**

**Option A: Azure OpenAI (recommended)**
```bash
# Edit .env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your_actual_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
```

**Option B: OpenAI**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-actual-key
```

**Option C: Ollama (local)**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=llama3.2:latest
```

**Verification Method:**
1. Edit `.env` with chosen configuration
2. Restart chatbot:
   ```bash
   source .venv/bin/activate
   PYTHONPATH=/home/ff/.openclaw/workspace/repos/CDP_Merged \
     CHAINLIT_AUTH_SECRET=test-secret-123 \
     chainlit run src/app.py --host 0.0.0.0 --port 8000
   ```
3. Open browser to http://localhost:8000
4. Test query: `"How many IT companies in Oost-Vlaanderen?"`
5. Expected: Count response with segment suggestion (no 401 error)

**Record in `PROJECT_STATE.yaml`:**
- Configuration method used (Azure/OpenAI/Ollama)
- Test query executed
- Result (success/failure)
- Error text if any
- Label: `observed` or `blocked`

---

### 2. Review Git State Safely
**Status:** `reported` until rechecked in this session.

**Goal:**
Determine whether there is a clean, task-scoped commit to make.

**Current State (from previous session):**
- Branch: `push-clean`
- Ahead of main: 7 commits
- Last commit: `a2cd322` (handoff and halt)

**Minimum review:**
```bash
cd /home/ff/.openclaw/workspace/repos/CDP_Merged
git status --short
git log --oneline --decorate -n 5
```

**If a commit is appropriate:**
- Stage only files related to the LLM fix
- Write a scoped commit message (e.g., `fix(config): Update LLM provider credentials`)
- Do not include unrelated edits

**If a push is appropriate:**
- Only push after confirming the branch, commit scope, and intent
- If push is blocked, record the blocker in `WORKLOG.md`

---

## Completion Requirements

- Update `PROJECT_STATE.yaml` with verification evidence
- Append the session result to `WORKLOG.md`
- Update `NEXT_ACTIONS.md` only if task status or priority changed
- Update `STATUS.md` only if the human-readable summary materially changed

---

## Handoff Output Format (for next agent)

Use this structure when you finish:

```markdown
## Handoff
**Task:** Chatbot LLM Configuration Fix
**Status:** COMPLETE / PARTIAL / BLOCKED

### What changed
- [.env] Updated LLM_PROVIDER to [azure_openai/openai/ollama]
- [Added Azure OpenAI credentials / OpenAI key / Ollama config]

### Verification
- [Test query: "How many IT companies in Oost-Vlaanderen?"]
- [Result: Received count response / 401 error / other error]

### Follow-up
1. [Next action if needed]
2. [Next action if needed]
```

---

## Context from Previous Session

### Research Analysis Completed
- `docs/RESEARCH_ANALYSIS_REPORT.md` (19KB) - Executive summary
- `docs/AI_RESEARCH_AGENT_BRIEF.md` (25KB) - Technical deep-dive
- 11 research questions answered
- Prioritized roadmap: P0 CVEs, P1 client consolidation, P2 FastAPI eval

### Current System State
- **Chatbot:** Running on http://localhost:8000 (`observed`)
- **Tracardi:** Connected with 2,500 profiles (`observed`)
- **LLM:** FAILING with 401 error (`observed`)
- **Python:** 3.12.12 working (`observed`)
- **Virtualenv:** `.venv/` active (`observed`)

### CI/CD Status
- Last CD run: `22597100805` - SUCCESS (`observed`)
- Deployment: Staging successful
- Container Security Scan: Passed with warnings (non-blocking)

---

## Notes

1. **Do NOT commit actual API keys to git** - use `.env` file only
2. **Azure OpenAI is preferred** (matches infrastructure ADR-007)
3. **Test with actual KBO data** - 2,500 profiles in Tracardi
4. **Check .env file permissions** - should not be world-readable

---

*End of Handoff*
