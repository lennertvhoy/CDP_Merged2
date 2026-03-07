## Handoff - URGENT REDIRECTION

**Task:** CRITICAL - Fix Deployed Chatbot UI/UX - Non-Functional in Production  
**Status:** P0 CRITICAL - IMMEDIATE ACTION REQUIRED  
**Previous Task:** UI/UX Enhancement Planning (DEPRIORITIZED)  
**Discovered:** 2026-03-03 21:50  
**Severity:** CRITICAL - Production chatbot is non-functional

---

## PROBLEM STATEMENT

**User Report:** "The UI/UX is just awful, no contract at all, I cant see anything, it doesnt work at all either"

**Verification Results:**
- URL loads (HTTP 200) but **UI is non-functional**
- HTML contains broken JavaScript config: `<script>undefined\nundefined</script>`
- Chainlit configuration is not being injected into the HTML template
- The UI appears to load but likely fails to initialize due to missing config

**Root Cause (Suspected):** Chainlit config injection failure - the `window.chainlitConfig` or similar is `undefined`

---

## VERIFICATION EVIDENCE

```bash
# Root path returns HTML but with broken config
curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/

# Response contains:
# <script>
# undefined
# undefined
# </script>
```

**Current Deployment:**
- Revision: `ca-cdpmerged-fast--stg-2dbba58`
- Status: Running, Healthy
- Traffic: 100%
- **BUT:** UI non-functional for users

---

## IMMEDIATE ACTIONS REQUIRED

### 1. DIAGNOSE (30 minutes)

**Check 1: Local reproduction**
```bash
# Run locally and verify UI works
poetry run chainlit run src/app.py --headless
# Check if config injects properly locally
```

**Check 2: Docker build verification**
```bash
# Build and test Docker image locally
docker build -t cdp-test .
docker run -p 8080:8080 cdp-test
# Check if / returns proper config injection
```

**Check 3: Missing files in container**
```bash
# Check if chainlit.md, .chainlit/config.toml are in the Docker image
# These are needed for Chainlit to generate the config
```

### 2. LIKELY CAUSES & FIXES

**Cause A: Missing config files in Docker image**
- `chainlit.md` - Required for Chainlit page generation
- `.chainlit/config.toml` - Required for UI configuration
- `public/cdp-custom.css` - Referenced but may be missing

**Fix:** Update `.dockerignore` and `Dockerfile` to include these files

**Cause B: Environment variable issue**
- Chainlit may need specific env vars to generate config
- Check `CHAINLIT_AUTH_SECRET`, `CHAINLIT_HOST`, etc.

**Cause C: Build process issue**
- The `undefined` suggests template variable not being set
- May be a Chainlit version incompatibility

### 3. TESTING CHECKLIST

After any fix:
- [ ] `curl /` returns HTML with valid config (not `undefined`)
- [ ] WebSocket connects properly
- [ ] Chat interface loads in browser
- [ ] Can send a message and get response
- [ ] UI shows "CDP AI Assistant" branding
- [ ] Chat profiles appear (Marketing Manager, Sales Rep, etc.)

---

## FILES TO INVESTIGATE

| File | Purpose | Check |
|------|---------|-------|
| `Dockerfile` | Container build | Missing COPY for config files? |
| `.dockerignore` | Exclusions | Blocking chainlit files? |
| `src/app.py` | Chainlit app | Healthz routes conflicting? |
| `.chainlit/config.toml` | UI config | In container? |
| `chainlit.md` | Welcome content | In container? |
| `public/cdp-custom.css` | Custom styles | In container? Accessible? |

---

## ROLLBACK OPTION

If fix takes >2 hours:
1. Identify last known working revision
2. Update Azure Container App to route 100% traffic to that revision
3. Document broken revision for post-mortem

---

## CONTEXT SWITCH

**Abandoned:** UI/UX enhancement planning (was: cleanup + Chainlit polish)
**New Priority:** Fix production deployment - chatbot is non-functional
**Enrichment Pipeline:** Still running autonomously (87 chunks, ~4.5%, ~30h remaining)

---

## NEXT AGENT INSTRUCTIONS

1. **STOP** - Do not continue with UI/UX enhancements
2. **VERIFY** - Run `curl https://ca-cdpmerged-fast.wonderfulisland-74a59b9d.westeurope.azurecontainerapps.io/` and confirm `undefined` in HTML
3. **DIAGNOSE** - Check Dockerfile and .dockerignore for missing Chainlit files
4. **FIX** - Add missing config files to Docker image
5. **TEST** - Deploy and verify UI works in browser
6. **DOCUMENT** - Update STATUS.md and PROJECT_STATE.yaml with fix details

---

**Critical Success Criteria:** User can access the chatbot URL and successfully interact with the AI assistant.
