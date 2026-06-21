#!/bin/bash
# Parallel Search — параллельный запрос ко всем провайдерам с агрегацией
# Usage: ./search-parallel.sh <query> [count]
#
# Для Deep Research: запускает всех 4 провайдеров одновременно,
# собирает результаты, дедуплицирует по URL

set -euo pipefail

QUERY="${1:?Usage: $0 <query> [count]}"
COUNT="${2:-5}"
CONFIG_FILE="$(dirname "$0")/../config/search-keys.yaml"
TMPDIR=$(mktemp -d)
TRAP_CMD="rm -rf $TMPDIR"
trap "$TRAP_CMD" EXIT

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" >> "$(dirname "$0")/../logs/search-parallel.log"
}

mkdir -p "$(dirname "$0")/../logs"
log "Parallel search: QUERY='$QUERY' COUNT='$COUNT'"

# Read first key from config
get_first_key() {
    local provider="$1"
    grep "^  ${provider}:" -A 6 "$CONFIG_FILE" | grep "^    - " | head -1 | sed 's/^    - //'
}

TAVILY_KEY=$(get_first_key tavily)
FIRECRAWL_KEY=$(get_first_key firecrawl)
TINYFISH_KEY=$(get_first_key tinyfish)

# URL-encode query
ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY")

# ─── Launch all providers in parallel ───────────────────────────

# Tavily
curl -s -X POST "https://api.tavily.com/search" \
    -H "Content-Type: application/json" \
    -d "{\"api_key\":\"${TAVILY_KEY}\",\"query\":\"${QUERY}\",\"max_results\":${COUNT},\"include_answer\":true}" \
    --max-time 30 > "$TMPDIR/tavily.json" 2>/dev/null &

# Firecrawl
curl -s -X POST "https://api.firecrawl.dev/v1/search" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${FIRECRAWL_KEY}" \
    -d "{\"query\":\"${QUERY}\",\"limit\":${COUNT}}" \
    --max-time 30 > "$TMPDIR/firecrawl.json" 2>/dev/null &

# TinyFish
curl -s "https://api.search.tinyfish.ai?query=${ENCODED_QUERY}&location=US&language=en" \
    -H "X-API-Key: ${TINYFISH_KEY}" \
    --max-time 30 > "$TMPDIR/tinyfish.json" 2>/dev/null &

# SearXNG
curl -s "http://localhost:8889/search?q=${ENCODED_QUERY}&format=json&categories=general" \
    --max-time 15 > "$TMPDIR/searxng.json" 2>/dev/null &

# Wait for all
wait

log "All providers responded"

# ─── Aggregate results ──────────────────────────────────────────

python3 << 'PYEOF'
import json, sys, os

tmpdir = os.environ.get("TMPDIR", "/tmp")
query = os.environ.get("QUERY", "")

results = {
    "query": query,
    "providers": {},
    "aggregated_urls": [],
    "total_results": 0
}

def extract_urls(data, provider):
    urls = []
    if provider == "tavily" and isinstance(data, dict):
        for r in data.get("results", []):
            urls.append({"url": r.get("url",""), "title": r.get("title",""), "snippet": r.get("content","")[:200]})
    elif provider == "firecrawl" and isinstance(data, dict):
        for r in data.get("data", []):
            urls.append({"url": r.get("url","") or r.get("metadata",{}).get("url",""), "title": r.get("title","") or r.get("metadata",{}).get("title",""), "snippet": (r.get("markdown","") or "")[:200]})
    elif provider == "tinyfish" and isinstance(data, dict):
        for r in data.get("results", []):
            urls.append({"url": r.get("url",""), "title": r.get("title",""), "snippet": r.get("snippet","")[:200]})
    elif provider == "searxng" and isinstance(data, dict):
        for r in data.get("results", []):
            urls.append({"url": r.get("url",""), "title": r.get("title",""), "snippet": r.get("content","")[:200]})
    return urls

seen_urls = set()

for provider in ["tavily", "firecrawl", "tinyfish", "searxng"]:
    filepath = f"{tmpdir}/{provider}.json"
    try:
        with open(filepath) as f:
            data = json.load(f)
        urls = extract_urls(data, provider)
        # Dedup
        unique = []
        for u in urls:
            if u["url"] and u["url"] not in seen_urls:
                seen_urls.add(u["url"])
                unique.append(u)
        results["providers"][provider] = {"status": "ok", "count": len(unique), "results": unique}
        results["total_results"] += len(unique)
        results["aggregated_urls"].extend(unique)
    except Exception as e:
        results["providers"][provider] = {"status": "error", "error": str(e)}

print(json.dumps(results, indent=2, ensure_ascii=False))
PYEOF

log "Aggregation done. Total: $results['total_results'] results"
