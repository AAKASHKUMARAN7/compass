#!/usr/bin/env bash
#
# Retrieval gate regression harness.
#
# Guards the two properties the product depends on: in-policy questions get
# answered, and out-of-policy questions get refused. Run against a seeded API
# after any change to retrieval, chunking, the corpus, or the relevance floor.
# Adding documents changes IDF, so the corpus counts as a change.
#
#   bash eval/run.sh
#
# known_gaps.txt holds cases that currently fail. They are reported separately
# rather than deleted, so a real weakness stays visible and gets promoted back
# into the main set the moment it starts passing.

set -uo pipefail

API="${COMPASS_API:-http://127.0.0.1:8010}"
HERE="$(cd "$(dirname "$0")" && pwd)"

ask() {
  curl -s --max-time 60 -X POST "$API/api/chat/ask" \
    -H "Content-Type: application/json" \
    -d "$(python -c "import json,sys;print(json.dumps({'question':sys.argv[1]}))" "$1")"
}

verdict() {
  ask "$1" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('unreachable 0.0'); raise SystemExit
print(d['status'], round(d['top_score'], 3))
"
}

TOTAL_PASS=0
TOTAL_FAIL=0

run() {
  local want="$1" file="$2" pass=0 fail=0
  while IFS= read -r q; do
    [ -z "$q" ] && continue
    case "$q" in \#*) continue ;; esac

    read -r status score <<< "$(verdict "$q")"
    if [ "$status" = "$want" ]; then
      pass=$((pass + 1)); mark="PASS"
    else
      fail=$((fail + 1)); mark="FAIL"
    fi
    printf "  %s  %-7s %s\n" "$mark" "$score" "$q"
  done < "$file"
  echo "  -> $pass passed, $fail failed"
  TOTAL_PASS=$((TOTAL_PASS + pass))
  TOTAL_FAIL=$((TOTAL_FAIL + fail))
}

# Expected failures: reported, but not counted against the suite.
run_known_gaps() {
  local file="$1" fixed=0 still=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac

    local want="${line%%|*}"
    local q="${line#*|}"
    read -r status score <<< "$(verdict "$q")"
    if [ "$status" = "$want" ]; then
      fixed=$((fixed + 1))
      printf "  FIXED %-7s %s  <- now passing, promote it\n" "$score" "$q"
    else
      still=$((still + 1))
      printf "  gap   %-7s %s\n" "$score" "$q"
    fi
  done < "$file"
  echo "  -> $still still failing, $fixed newly fixed"
}

if ! curl -s --max-time 5 -o /dev/null "$API/api/health"; then
  echo "Cannot reach $API - start the backend and seed it first." >&2
  exit 2
fi

echo "=== SHOULD ANSWER ==="
run answered "$HERE/should_answer.txt"

echo
echo "=== SHOULD REFUSE ==="
run no_coverage "$HERE/should_refuse.txt"

echo
echo "=== KNOWN GAPS (expected failures) ==="
run_known_gaps "$HERE/known_gaps.txt"

echo
echo "TOTAL: $TOTAL_PASS passed, $TOTAL_FAIL failed"
[ "$TOTAL_FAIL" -eq 0 ]
