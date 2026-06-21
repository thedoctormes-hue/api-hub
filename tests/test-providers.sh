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
TMPFILE=$(mktemp)
bash "$SCRIPTS_DIR/search-parallel.sh" "test" 3 > "$TMPFILE" 2>/dev/null
total=$(python3 -c "import json,sys; d=json.load(open('$TMPFILE')); print(d.get('total_results',0))" 2>/dev/null || echo "0")
rm -f "$TMPFILE"
if [ "$total" -gt 0 ] 2>/dev/null; then
    echo "  ✅ Parallel search works ($total total results)"
    PASS=$((PASS + 1))
else
    echo "  ❌ Parallel search failed (total=$total)"
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

# ─── Test 8: Cyclic key rotation ────────────────────────────────

echo "--- Test 8: Cyclic Key Rotation ---"
# Reset state
echo "0" > "$(dirname "$0")/../config/.key-index-tavily"
echo "0" > "$(dirname "$0")/../config/.key-index-firecrawl"
echo "0" > "$(dirname "$0")/../config/.key-index-tinyfish"

# Run 6 queries — should cycle through 5 keys and wrap
for i in 1 2 3 4 5 6; do
    bash "$SCRIPTS_DIR/search-orchestrator.sh" "rotation test $i" factual 1 > /dev/null 2>&1
done

t_idx=$(cat "$(dirname "$0")/../config/.key-index-tavily")
# After 6 queries starting from 0: 1→2→3→4→0→1 = index should be 1
if [[ "$t_idx" -eq 1 ]]; then
    echo "  ✅ Cyclic rotation works (6 queries, 5 keys, index=$t_idx)"
    PASS=$((PASS + 1))
else
    echo "  ⚠️  Rotation index unexpected (expected 1, got $t_idx)"
    WARN=$((WARN + 1))
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
