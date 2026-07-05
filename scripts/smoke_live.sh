#!/usr/bin/env bash
# Validate a DEPLOYED Label Check instance against the sample labels.
#
# Usage:
#   scripts/smoke_live.sh https://your-host
#
# Runs from anywhere with curl + python3 (both standard on macOS). Posts each
# sample to /api/verify, checks the verdict matches the expected result, and
# prints the real round-trip latency so you can confirm the <=5s target.
set -euo pipefail

BASE="${1:?Usage: smoke_live.sh <base-url>}"
BASE="${BASE%/}"
DIR="$(cd "$(dirname "$0")/../samples" && pwd)"

# file | expected overall verdict (rule-check mode)
CASES=(
  "01_compliant.png|pass"
  "02_bad_warning_titlecase.png|fail"
  "03_missing_warning.png|fail"
  "04_missing_net_contents.png|fail"
  "05_other_brand.png|pass"
)

echo "== Health =="
curl -sS "$BASE/api/health"; echo; echo

echo "== Verify samples (mode=rules) =="
matched=0; missed=0
for c in "${CASES[@]}"; do
  file="${c%%|*}"; expect="${c##*|}"
  resp="$(curl -sS -X POST "$BASE/api/verify" -F "image=@$DIR/$file" -F "mode=rules")"
  read -r got elapsed <<<"$(printf '%s' "$resp" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('overall'), d.get('elapsed_ms', 0))
")"
  if [ "$got" = "$expect" ]; then
    printf 'OK    %-32s -> %-10s (%sms)\n' "$file" "$got" "$elapsed"; matched=$((matched+1))
  else
    printf 'MISS  %-32s -> got %s, expected %s (%sms)\n' "$file" "$got" "$expect" "$elapsed"; missed=$((missed+1))
  fi
done

echo "---"
echo "$matched matched, $missed mismatched"
[ "$missed" -eq 0 ] || exit 1
