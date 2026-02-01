#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${MT5_BRIDGE_URL:-http://137.74.116.242:8000}"

check() {
  local url="$1"
  local name="$2"
  local response http_code body

  response=$(curl -s -w "\n%{http_code}" "$url" || true)
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n1)

  if [ "$http_code" = "200" ]; then
    echo "PASS $name -> $url"
  else
    echo "FAIL $name -> $url (HTTP $http_code)"
    echo "Body: ${body:0:200}"
  fi
}

check "${BASE_URL}/health" "health"
check "${BASE_URL}/tick?symbol=XAUUSD" "tick"
check "${BASE_URL}/spread?symbol=XAUUSD" "spread"
check "${BASE_URL}/candles?symbol=XAUUSD&timeframe=M15&count=10" "candles(timeframe/count)"
check "${BASE_URL}/candles?symbol=XAUUSD&tf=M15&n=10" "candles(tf/n)"
