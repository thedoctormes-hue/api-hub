#!/bin/bash
# Search Orchestrator — маршрутизация по типу задачи + ротация ключей
# Usage: ./search-orchestrator.sh <query> [type] [count]
#
# Types: factual | content | dynamic | broad | deep_research
# Default: factual
#
# Exit codes:
#   0 — success
#   1 — all providers exhausted
#   2 — invalid arguments

set -euo pipefail

QUERY="${1:?Usage: $0 <query> [type] [count]}"
TYPE="${2:-factual}"
COUNT="${3:-5}"
CONFIG_FILE="$(dirname "$0")/../config/search-keys.yaml"
LOG_FILE="$(dirname "$0")/../logs/search-orchestrator.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "QUERY='$QUERY' TYPE='$TYPE' COUNT='$COUNT'"

# ─── Key Rotation ───────────────────────────────────────────────

get_next_key() {
    local provider="$1"
    local state_file="$(dirname "$0")/../config/.key-index-${provider}"

    local idx=0
    [[ -f "$state_file" ]] && idx=$(cat "$state_file" 2>/dev/null || echo 0)

    local keys
    keys=$(grep "^  ${provider}:" -A 6 "$CONFIG_FILE" | grep "^    - " | sed 's/^    - //')
    local total
    total=$(echo "$keys" | wc -l)

    local key
    key=$(echo "$keys" | sed -n "$((idx + 1))p")

    # Advance index
    idx=$(( (idx + 1) % total ))
    echo "$idx" > "$state_file"

    echo "$key"
}

# ─── Provider: Tavily ───────────────────────────────────────────

search_tavily() {
    local query="$1"
    local count="$2"
    local key
    key=$(get_next_key tavily)

    log "Tavily: using key index"

    local response
    response=$(curl -s -X POST "https://api.tavily.com/search" \
        -H "Content-Type: application/json" \
        -d "{\"api_key\":\"${key}\",\"query\":\"${query}\",\"max_results\":${count},\"include_answer\":true}" \
        --max-time 30 2>/dev/null)

    # Check for rate limit
    if echo "$response" | grep -q '"status":429\|"code":429\|rate.limit'; then
        log "Tavily: 429 rate limited, rotating key"
        key=$(get_next_key tavily)
        response=$(curl -s -X POST "https://api.tavily.com/search" \
            -H "Content-Type: application/json" \
            -d "{\"api_key\":\"${key}\",\"query\":\"${query}\",\"max_results\":${count},\"include_answer\":true}" \
            --max-time 30 2>/dev/null)
    fi

    echo "$response"
}

# ─── Provider: Firecrawl ────────────────────────────────────────

search_firecrawl() {
    local query="$1"
    local count="$2"
    local key
    key=$(get_next_key firecrawl)

    log "Firecrawl: using key index"

    local response
    response=$(curl -s -X POST "https://api.firecrawl.dev/v1/search" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${key}" \
        -d "{\"query\":\"${query}\",\"limit\":${count}}" \
        --max-time 30 2>/dev/null)

    if echo "$response" | grep -q '"status":429\|"code":429\|rate.limit\|"success":false'; then
        log "Firecrawl: error/429, rotating key"
        key=$(get_next_key firecrawl)
        response=$(curl -s -X POST "https://api.firecrawl.dev/v1/search" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${key}" \
            -d "{\"query\":\"${query}\",\"limit\":${count}}" \
            --max-time 30 2>/dev/null)
    fi

    echo "$response"
}

# ─── Provider: TinyFish ─────────────────────────────────────────

search_tinyfish() {
    local query="$1"
    local count="$2"
    local key
    key=$(get_next_key tinyfish)

    log "TinyFish: using key index"

    local encoded_query
    encoded_query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))" 2>/dev/null || echo "$query")

    local response
    response=$(curl -s "https://api.search.tinyfish.ai?query=${encoded_query}&location=US&language=en" \
        -H "X-API-Key: ${key}" \
        --max-time 30 2>/dev/null)

    if echo "$response" | grep -q '"code":"MISSING_API_KEY"\|"error"'; then
        log "TinyFish: error, rotating key"
        key=$(get_next_key tinyfish)
        response=$(curl -s "https://api.search.tinyfish.ai?query=${encoded_query}&location=US&language=en" \
            -H "X-API-Key: ${key}" \
            --max-time 30 2>/dev/null)
    fi

    echo "$response"
}

# ─── Provider: SearXNG ──────────────────────────────────────────

search_searxng() {
    local query="$1"
    local count="$2"

    log "SearXNG: querying local instance"

    local encoded_query
    encoded_query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))" 2>/dev/null || echo "$query")

    curl -s "http://localhost:8889/search?q=${encoded_query}&format=json&categories=general" \
        --max-time 15 2>/dev/null
}

# ─── Scrape: Firecrawl (full page content) ─────────────────────

scrape_firecrawl() {
    local url="$1"
    local key
    key=$(get_next_key firecrawl)

    log "Firecrawl scrape: $url"

    curl -s -X POST "https://api.firecrawl.dev/v2/scrape" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${key}" \
        -d "{\"url\":\"${url}\",\"formats\":[\"markdown\"],\"onlyMainContent\":true}" \
        --max-time 60 2>/dev/null
}

# ─── Scrape: TinyFish (JS rendering) ────────────────────────────

scrape_tinyfish() {
    local url="$1"
    local key
    key=$(get_next_key tinyfish)

    log "TinyFish fetch: $url"

    curl -s "https://api.fetch.tinyfish.ai?url=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${url}'))")" \
        -H "X-API-Key: ${key}" \
        --max-time 60 2>/dev/null
}

# ─── Deep Research: Parallel search ─────────────────────────────

deep_research() {
    local query="$1"
    local count="$2"
    local tmpdir
    tmpdir=$(mktemp -d)

    log "Deep Research: parallel search"

    # Run all 4 providers in parallel, write to temp files
    search_tavily "$query" "$count" > "$tmpdir/tavily.json" 2>/dev/null &
    search_firecrawl "$query" "$count" > "$tmpdir/firecrawl.json" 2>/dev/null &
    search_tinyfish "$query" "$count" > "$tmpdir/tinyfish.json" 2>/dev/null &
    search_searxng "$query" "$count" > "$tmpdir/searxng.json" 2>/dev/null &

    wait
    sleep 1

    # Output aggregated JSON
    python3 -c "
import json, os

tmpdir = '$tmpdir'
query = '''${query}'''

results = {
    'query': query,
    'type': 'deep_research',
    'providers': {}
}

for name in ['tavily', 'firecrawl', 'tinyfish', 'searxng']:
    filepath = os.path.join(tmpdir, name + '.json')
    try:
        with open(filepath) as f:
            raw = f.read()
        data = json.loads(raw)
        results['providers'][name] = {'status': 'ok', 'data': data}
    except Exception as e:
        results['providers'][name] = {'status': 'error', 'error': str(e)}

print(json.dumps(results, indent=2, ensure_ascii=False))
" 2>/dev/null

    rm -rf "$tmpdir"
}

# ─── Router ─────────────────────────────────────────────────────

case "$TYPE" in
    factual)
        log "Route: factual → Tavily"
        search_tavily "$QUERY" "$COUNT"
        ;;
    content)
        log "Route: content → Firecrawl scrape"
        # If QUERY is a URL, scrape it; otherwise search first
        if [[ "$QUERY" == http* ]]; then
            scrape_firecrawl "$QUERY"
        else
            search_firecrawl "$QUERY" "$COUNT"
        fi
        ;;
    dynamic)
        log "Route: dynamic → TinyFish"
        if [[ "$QUERY" == http* ]]; then
            scrape_tinyfish "$QUERY"
        else
            search_tinyfish "$QUERY" "$COUNT"
        fi
        ;;
    broad)
        log "Route: broad → SearXNG"
        search_searxng "$QUERY" "$COUNT"
        ;;
    deep_research)
        log "Route: deep_research → ALL providers"
        deep_research "$QUERY" "$COUNT"
        ;;
    *)
        echo "Unknown type: $TYPE" >&2
        echo "Valid types: factual | content | dynamic | broad | deep_research" >&2
        exit 2
        ;;
esac

log "Done."
