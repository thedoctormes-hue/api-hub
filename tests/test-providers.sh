#!/bin/bash
# Test all search providers — тестирование всех провайдеров и ключей
# Usage: ./test-providers.sh

set -euo pipefail

SCRIPTS_DIR="$(dirname "$0")/../scripts"
CONFIG_FILE="$(dirname "$0")/../config/search-keys.yaml"
PASS=0
FAIL=0
WARN=0

echo "=== Search Provider Tests ==="
echo "Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ─── Test 1: Key check script ───────────────────────────────────

echo "--- Test 1: Key Check ---"
if bash "$SCRIPTS_DIR/search-check-keys.sh" > /dev/null 2>&1; then
    echo "  ✅ Key check script runs"
    PASS=$((PASS + 1))
else
    echo "  ❌ Key check script failed"
    FAIL=$((FAIL + 1))
fi

# ─── Test 2: Factual query via orchestrator ─────────────────────

echo "--- Test 2: Factual Query (Tavily) ---"
result=$(bash "$SCRIPTS_DIR/search-orchestrator.sh" "test query" factual 3 2>/dev/null)
if echo "$result" | grep -q '"results"'; then
    echo "  ✅ Tavily factual query works"
    PASS=$((PASS + 1))
else
    echo "  ❌ Tavily factual query failed"
    FAIL=$((FAIL + 1))
fi

# ─── Test 3: Broad query via orchestrator ───────────────────────

echo "--- Test 3: Broad Query (SearXNG) ---"
result=$(bash "$SCRIPTS_DIR/search-orchestrator.sh" "test query" broad 3 2>/dev/null)
if echo "$result" | grep -q '"results"'; then
    echo "  ✅ SearXNG broad query works"
    PASS=$((PASS + 1))
else
    echo "  ❌ SearXNG broad query failed (maybe local instance down)"
    WARN=$((WARN + 1))
fi

# ─── Test 4: Dynamic query via orchestrator ─────────────────────

echo "--- Test 4: Dynamic Query (TinyFish) ---"
result=$(bash "$SCRIPTS_DIR/search-orchestrator.sh" "test query" dynamic 3 2>/dev/null)
if echo "$result" | grep -q '"results"'; then
    echo "  ✅ TinyFish dynamic query works"
    PASS=$((PASS + 1))
else
    echo "  ❌ TinyFish dynamic query failed"
    FAIL=$((FAIL + 1))
fi

# ─── Test 5: Deep Research mode ─────────────────────────────────

echo "--- Test 5: Deep Research (Parallel) ---"
result=$(bash "$SCRIPTS_DIR/search-orchestrator.sh" "test" deep_research 3 2>/dev/null)
if echo "$result" | grep -q '"providers"'; then
    providers_count=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('providers',{})))" 2>/dev/null || echo "0")
    if [[ "$providers_count" -ge 3 ]]; then
        echo "  ✅ Deep Research works ($providers_count providers responded)"
        PASS=$((PASS + 1))
    else
        echo "  ⚠️  Deep Research partial ($providers_count/4 providers)"
        WARN=$((WARN + 1))
    fi
else
    echo "  ❌ Deep Research failed"
    FAIL=$((FAIL + 1))
fi

# ─── Test 6: Parallel search script ─────────────────────────────

echo "--- Test 6: Parallel Search Script ---"
result=$(bash "$SCRIPTS_DIR/search-parallel.sh" "test" 3 2>/dev/null)
if echo "$result" | grep -q '"total_results"'; then
    total=$(echo "$result" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_results',0))" 2>/dev/null || echo "0")
    echo "  ✅ Parallel search works ($total total results)"
    PASS=$((PASS + 1))
else
    echo "  ❌ Parallel search failed"
    FAIL=$((FAIL + 1))
fi

# ─── Test 7: Invalid type handling ──────────────────────────────

echo "--- Test 7: Invalid Type Handling ---"
if ! bash "$SCRIPTS_DIR/search-orchestrator.sh" "test" invalid_type 2>/dev/null; then
    echo "  ✅ Invalid type correctly rejected"
    PASS=$((PASS + 1))
else
    echo "  ❌ Invalid type not rejected"
    FAIL=$((FAIL + 1))
fi

# ─── Test 8: Key rotation state files ───────────────────────────

echo "--- Test 8: Key Rotation State ---"
# Run 3 queries to same provider, check state advances
bash "$SCRIPTS_DIR/search-orchestrator.sh" "test1" factual 1 > /dev/null 2>&1
bash "$SCRIPTS_DIR/search-orchestrator.sh" "test2" factual 1 > /dev/null 2>&1
bash "$SCRIPTS_DIR/search-orchestrator.sh" "test3" factual 1 > /dev/null 2>&1

state_file="$(dirname "$0")/../config/.key-index-tavily"
if [[ -f "$state_file" ]]; then
    idx=$(cat "$state_file")
    if [[ "$idx" -ge 1 ]]; then
        echo "  ✅ Key rotation state advances (index=$idx)"
        PASS=$((PASS + 1))
    else
        echo "  ⚠️  Key rotation state not advancing (index=$idx)"
        WARN=$((WARN + 1))
    fi
else
    echo "  ❌ No state file created"
    FAIL=$((FAIL + 1))
fi

# ─── Summary ────────────────────────────────────────────────────

echo ""
echo "=== Test Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo "  Warnings: $WARN"
echo "  Total:  $((PASS + FAIL + WARN))"

if [[ "$FAIL" -gt 0 ]]; then
    echo ""
    echo "❌ SOME TESTS FAILED"
    exit 1
else
    echo ""
    echo "✅ ALL TESTS PASSED"
    exit 0
fi
