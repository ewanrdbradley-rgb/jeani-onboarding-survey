#!/usr/bin/env bash
# Starts the collector on a scratch DB, posts a partial + full response, checks summary + CSV.
set -euo pipefail
cd "$(dirname "$0")/.."
export PORT=${PORT:-8790}
export SURVEY_DB=$(mktemp -d)/test.db
export SURVEY_ADMIN_TOKEN=testtoken
python3 server/app.py serve & PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.2; done

RID=abcdef0123456789abcdef01
post() { curl -sf -X POST "http://127.0.0.1:$PORT/api/feedback" -H 'Content-Type: application/json' -d "$1"; echo; }
echo "-- partial (email tap)";   post "{\"response_id\":\"$RID\",\"rating\":4,\"source\":\"onboarding_email\",\"partial\":true}"
echo "-- full submission";       post "{\"response_id\":\"$RID\",\"rating\":5,\"source\":\"onboarding_email\",\"partial\":false,\"use_cases\":[\"Trail or ultra\"],\"features\":[\"The texts to my phone\",\"Sleep insights\"],\"usage\":\"I read the texts, rarely open the app\",\"design\":[\"Feels personal to me\"],\"improve\":\"Texts land too early.\",\"contact_ok\":true}"
echo "-- late partial must not overwrite"; post "{\"response_id\":\"$RID\",\"rating\":1,\"partial\":true}"
echo "-- rejected: bad rating";  curl -s -X POST "http://127.0.0.1:$PORT/api/feedback" -H 'Content-Type: application/json' -d "{\"response_id\":\"$RID\",\"rating\":9}"; echo
echo "-- unauthorized summary";  curl -s "http://127.0.0.1:$PORT/api/summary"; echo
echo "-- summary";               curl -sf "http://127.0.0.1:$PORT/api/summary?token=testtoken"; echo
echo "-- csv";                   curl -sf "http://127.0.0.1:$PORT/api/export.csv?token=testtoken"
echo "-- page";                  curl -sf "http://127.0.0.1:$PORT/?r=4&u=test" | grep -c "How's it going so far" >/dev/null && echo "survey page served"
echo "-- cli summary";           python3 server/app.py summary
echo "SMOKE TEST PASSED"
