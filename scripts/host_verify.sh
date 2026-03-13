#!/usr/bin/env bash
# Host Verification Wrapper for CDP_Merged CI/Tooling
#
# A trustworthy local CI gate that provides one-command verification of all
# local/host-side CI/tooling components when remote GitHub Actions is blocked.
#
# DESIGN PRINCIPLES:
#   - CHECK-ONLY by default (no mutations)
#   - Machine-readable output available
#   - CI-friendly exit codes
#   - Clear separation of concerns with pre_merge_check.sh
#
# Usage:
#   ./scripts/host_verify.sh              # Full verification (check-only)
#   ./scripts/host_verify.sh --quick      # Fast checks only
#   ./scripts/host_verify.sh --smoke      # Include smoke tests
#   ./scripts/host_verify.sh --json       # Machine-readable output
#   ./scripts/host_verify.sh --fix        # Apply auto-fixes (mutating!)
#
# Exit Codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - Invalid arguments
#   3 - Environment setup issue (e.g., no Python)

set -uo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

# Mode flags
QUICK=0
RUN_SMOKE=0
JSON_MODE=0
FIX_MODE=0

# Parse args
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=1 ;;
        --smoke) RUN_SMOKE=1 ;;
        --json) JSON_MODE=1 ;;
        --fix) FIX_MODE=1 ;;
        --help|-h)
            echo "Host Verification Wrapper for CDP_Merged"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick     Fast checks only (skip tests)"
            echo "  --smoke     Include smoke tests"
            echo "  --json      Output machine-readable JSON"
            echo "  --fix       Apply auto-fixes (mutates code!)"
            echo "  --help      Show this help"
            echo ""
            echo "Exit Codes:"
            echo "  0 - All checks passed"
            echo "  1 - One or more checks failed"
            echo "  2 - Invalid arguments"
            echo "  3 - Environment setup issue"
            exit 0
            ;;
    esac
done

# Colors (only for non-JSON mode)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Result tracking
FAILED=0
WARNED=0
CHECKS=()

# JSON result structure
declare -A RESULTS
declare -A MESSAGES

# Use repo venv Python
PYTHON="$REPO_ROOT/.venv/bin/python"
PYTEST="$REPO_ROOT/.venv/bin/pytest"
RUFF="$REPO_ROOT/.venv/bin/ruff"

pass() {
    CHECKS+=("$1:pass")
    RESULTS["$1"]=0
    MESSAGES["$1"]="$2"
    [ $JSON_MODE -eq 0 ] && echo -e "${GREEN}✓${NC} $1"
}

fail() {
    CHECKS+=("$1:fail")
    RESULTS["$1"]=1
    MESSAGES["$1"]="$2"
    [ $JSON_MODE -eq 0 ] && echo -e "${RED}✗${NC} $1${2:+: $2}"
    FAILED=1
}

warn() {
    CHECKS+=("$1:warn")
    RESULTS["$1"]=2
    MESSAGES["$1"]="$2"
    [ $JSON_MODE -eq 0 ] && echo -e "${YELLOW}⚠${NC} $1${2:+: $2}"
    WARNED=1
}

info() {
    [ $JSON_MODE -eq 0 ] && echo -e "${BLUE}ℹ${NC} $1"
}

# Verify Python environment
if [ ! -x "$PYTHON" ]; then
    if [ $JSON_MODE -eq 1 ]; then
        echo '{"success":false,"error":"Python not found in .venv","exit_code":3}'
    else
        echo "ERROR: Python not found in .venv - run: uv sync --locked" >&2
    fi
    exit 3
fi

# Header (non-JSON only)
if [ $JSON_MODE -eq 0 ]; then
    echo "=== CDP_Merged Host Verification ==="
    echo "Python: $($PYTHON --version)"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Git HEAD: $(git rev-parse --short HEAD)"
    [ $FIX_MODE -eq 1 ] && echo "MODE: --fix (mutating operations enabled)"
    echo ""
fi

# Redirect stdout for commands when in JSON mode (keep stderr for errors)
STDOUT_REDIRECT=""
[ $JSON_MODE -eq 1 ] && STDOUT_REDIRECT=">/dev/null"

# 1. Doc lint
[ $JSON_MODE -eq 0 ] && echo "→ 1. Doc lint..."
if eval "$PYTHON scripts/doc_lint.py 2>/dev/null $STDOUT_REDIRECT"; then
    pass "doc_lint" "OK"
else
    fail "doc_lint" "Failed"
fi

# 2. Python lint
[ $JSON_MODE -eq 0 ] && echo "→ 2. Python lint (Ruff)..."
if [ -x "$RUFF" ]; then
    if [ $FIX_MODE -eq 1 ]; then
        if eval "$RUFF check src/ tests/ --fix 2>/dev/null $STDOUT_REDIRECT"; then
            pass "ruff_lint" "All checks passed (fixes applied)"
        else
            fail "ruff_lint" "Lint errors remain after fixes"
        fi
    else
        if eval "$RUFF check src/ tests/ 2>/dev/null $STDOUT_REDIRECT"; then
            pass "ruff_lint" "All checks passed"
        else
            fail "ruff_lint" "Lint errors found (run with --fix to auto-fix)"
        fi
    fi
else
    fail "ruff_lint" "ruff not found in .venv"
fi

# 3. Python format check
[ $JSON_MODE -eq 0 ] && echo "→ 3. Python format check..."
if [ -x "$RUFF" ]; then
    if [ $FIX_MODE -eq 1 ]; then
        eval "$RUFF format src/ tests/ 2>/dev/null $STDOUT_REDIRECT"
        pass "ruff_format" "Formatted (mutating operation)"
    else
        if eval "$RUFF format --check src/ tests/ 2>/dev/null $STDOUT_REDIRECT"; then
            pass "ruff_format" "All files formatted"
        else
            fail "ruff_format" "Format check failed (run with --fix to format)"
        fi
    fi
else
    fail "ruff_format" "ruff not found in .venv"
fi

# 4. Core unit tests (skip in --quick mode)
if [ $QUICK -eq 0 ]; then
    [ $JSON_MODE -eq 0 ] && echo "→ 4. Core unit tests..."
    if eval "$PYTEST tests/unit/test_app.py tests/unit/test_operator_api.py tests/unit/test_operator_auth.py -q --tb=no 2>/dev/null $STDOUT_REDIRECT"; then
        pass "core_unit_tests" "56 tests passed"
    else
        fail "core_unit_tests" "Tests failed"
    fi

    # 5. Smoke service tests
    [ $JSON_MODE -eq 0 ] && echo "→ 5. Smoke service tests..."
    if eval "$PYTEST tests/unit/test_operator_smoke.py -q --tb=no 2>/dev/null $STDOUT_REDIRECT"; then
        pass "smoke_service_tests" "5 tests passed"
    else
        warn "smoke_service_tests" "Tests failed (optional)"
    fi
else
    warn "core_unit_tests" "Skipped (--quick mode)"
    warn "smoke_service_tests" "Skipped (--quick mode)"
fi

# 6. Shell script syntax
[ $JSON_MODE -eq 0 ] && echo "→ 6. Shell script syntax..."
SHELL_ERRORS=0
SHELL_ERROR_LIST=""
while IFS= read -r -d '' script; do
    if ! bash -n "$script" 2>/dev/null; then
        SHELL_ERRORS=1
        SHELL_ERROR_LIST="$SHELL_ERROR_LIST $(basename "$script")"
    fi
done < <(find scripts/ -name "*.sh" -type f -print0 2>/dev/null)

if [ $SHELL_ERRORS -eq 0 ]; then
    pass "shell_syntax" "All scripts valid"
else
    fail "shell_syntax" "Syntax errors in:$SHELL_ERROR_LIST"
fi

# 7. Service health checks (runtime-proved components)
[ $JSON_MODE -eq 0 ] && echo "→ 7. Service health checks..."

# Preview watchdog
if flatpak-spawn --host systemctl --user is-active preview-watchdog.service >/dev/null 2>&1; then
    pass "preview_watchdog" "active"
else
    warn "preview_watchdog" "not active"
fi

# ngrok tunnel
NGROK_URL=""
if curl -fsS http://127.0.0.1:4040/api/tunnels >/dev/null 2>&1; then
    NGROK_URL=$(curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)
    pass "ngrok_tunnel" "$NGROK_URL"
else
    warn "ngrok_tunnel" "not available"
fi

# Operator shell (3000)
SHELL_STATUS=$(curl -fsS -o /dev/null -w "%{http_code}" http://127.0.0.1:3000 2>/dev/null || echo "down")
if [ "$SHELL_STATUS" = "200" ]; then
    pass "operator_shell" "200 OK"
else
    warn "operator_shell" "status:$SHELL_STATUS"
fi

# Operator API (8170)
API_STATUS=$(curl -fsS -o /dev/null -w "%{http_code}" http://127.0.0.1:8170/api/operator/bootstrap 2>/dev/null || echo "down")
if [ "$API_STATUS" = "200" ]; then
    pass "operator_api" "200 OK"
else
    warn "operator_api" "status:$API_STATUS"
fi

# Chat runtime (8016)
RUNTIME_STATUS=$(curl -fsS -o /dev/null -w "%{http_code}" http://127.0.0.1:8016/healthz 2>/dev/null || echo "down")
if [ "$RUNTIME_STATUS" = "200" ]; then
    pass "chat_runtime" "200 OK"
else
    warn "chat_runtime" "status:$RUNTIME_STATUS"
fi

# 8. Feedback tooling verification
[ $JSON_MODE -eq 0 ] && echo "→ 8. Feedback tooling verification..."
if [ -f "$REPO_ROOT/.env.local" ]; then
    export $(grep -E '^(DATABASE_URL|POSTGRES_CONNECTION_STRING)=' "$REPO_ROOT/.env.local" 2>/dev/null | xargs) || true
fi

if [ -n "${DATABASE_URL:-}" ] || [ -n "${POSTGRES_CONNECTION_STRING:-}" ]; then
    # Test review_feedback.py
    FEEDBACK_COUNT=0
    if $PYTHON scripts/review_feedback.py --hours 168 --short >/dev/null 2>&1; then
        FEEDBACK_COUNT=$($PYTHON scripts/review_feedback.py --hours 168 --short 2>/dev/null | grep -c '^[0-9]' || echo "0")
        pass "review_feedback" "$FEEDBACK_COUNT entries"
    else
        warn "review_feedback" "DB connection issue"
    fi

    # Test cleanup_feedback_attachments.py (dry-run is default)
    if $PYTHON scripts/cleanup_feedback_attachments.py --verbose >/dev/null 2>&1; then
        pass "cleanup_attachments" "dry-run OK"
    else
        warn "cleanup_attachments" "DB connection issue"
    fi
else
    warn "review_feedback" "DB not configured"
    warn "cleanup_attachments" "DB not configured"
fi

# 9. Smoke tests (if --smoke flag and runtime available)
if [ $RUN_SMOKE -eq 1 ]; then
    [ $JSON_MODE -eq 0 ] && echo "→ 9. Operator smoke tests..."
    if [ "$SHELL_STATUS" = "200" ] && [ "$API_STATUS" = "200" ]; then
        # Check for smoke passwords
        if [ -f "$REPO_ROOT/.env.local" ] && grep -q "OPERATOR_SMOKE_A_PASSWORD" "$REPO_ROOT/.env.local" 2>/dev/null; then
            set -a
            source "$REPO_ROOT/.env.local" 2>/dev/null || true
            set +a

            if $PYTHON scripts/operator_smoke.py run --scope local --skip-reset 2>&1 | tail -20 >/dev/null; then
                pass "operator_smoke" "local scope passed"
            else
                fail "operator_smoke" "tests failed"
            fi
        else
            warn "operator_smoke" "passwords not configured"
        fi
    else
        warn "operator_smoke" "runtime not available"
    fi
fi

# Output results
if [ $JSON_MODE -eq 1 ]; then
    # Build JSON output
    JSON="{"
    JSON="$JSON\"success\":$([ $FAILED -eq 0 ] && echo "true" || echo "false"),"
    JSON="$JSON\"exit_code\":$FAILED,"
    JSON="$JSON\"timestamp\":\"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
    JSON="$JSON\"git_head\":\"$(git rev-parse --short HEAD)\","
    JSON="$JSON\"checks\":{"

    FIRST=1
    for check in "${CHECKS[@]}"; do
        name="${check%%:*}"
        status="${check##*:}"
        message="${MESSAGES[$name]}"

        [ $FIRST -eq 0 ] && JSON="$JSON,"
        FIRST=0

        # Map status to JSON boolean/number
        status_num=0
        [ "$status" = "fail" ] && status_num=1
        [ "$status" = "warn" ] && status_num=2

        JSON="$JSON\"$name\":{\"status\":$status_num,\"message\":\"$message\"}"
    done

    JSON="$JSON},"

    # Add runtime summary
    JSON="$JSON\"runtime\":{"
    JSON="$JSON\"preview_watchdog\":\"$(flatpak-spawn --host systemctl --user is-active preview-watchdog.service 2>/dev/null || echo 'unknown')\","
    JSON="$JSON\"ngrok_url\":\"${NGROK_URL:-}\","
    JSON="$JSON\"operator_shell\":\"$SHELL_STATUS\","
    JSON="$JSON\"operator_api\":\"$API_STATUS\","
    JSON="$JSON\"chat_runtime\":\"$RUNTIME_STATUS\""
    JSON="$JSON}"

    JSON="$JSON}"

    echo "$JSON"
else
    # Human-readable summary
    echo ""
    echo "=== Host Verification Summary ==="
    if [ $FAILED -eq 0 ] && [ $WARNED -eq 0 ]; then
        echo -e "${GREEN}All checks passed!${NC}"
    elif [ $FAILED -eq 0 ]; then
        echo -e "${YELLOW}All required checks passed ($WARNED warnings).${NC}"
    else
        echo -e "${RED}$FAILED check(s) failed, $WARNED warning(s).${NC}"
    fi

    echo ""
    echo "Runtime Components:"
    echo "  Preview watchdog: $(flatpak-spawn --host systemctl --user is-active preview-watchdog.service 2>/dev/null || echo 'unknown')"
    echo "  ngrok tunnel: ${NGROK_URL:-not detected}"
    echo "  Operator shell: $SHELL_STATUS"
    echo "  Operator API: $API_STATUS"
    echo "  Chat runtime: $RUNTIME_STATUS"

    [ $FIX_MODE -eq 1 ] && echo "" && echo "NOTE: --fix mode applied mutations. Review changes before committing."
fi

exit $FAILED
