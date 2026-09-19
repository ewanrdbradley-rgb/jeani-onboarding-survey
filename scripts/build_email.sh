#!/usr/bin/env bash
# Fills the live survey URL into the email templates and drops the optional user id parameter.
# Usage: scripts/build_email.sh [SURVEY_URL]
set -euo pipefail
cd "$(dirname "$0")/.."
LIVE="${1:-https://www.jeanihealth.com/memberfeedback}"
for f in email/onboarding-snippet.html email/onboarding-snippet.txt; do
  out="${f%.*}.ready.${f##*.}"
  sed -e "s|{{SURVEY_URL}}|$LIVE|g" -e 's|&u={{USER_ID}}||g' \
      -e "s|    {{SURVEY_URL}}  -> e.g. .*|    Survey URL already filled in: $LIVE|" \
      -e 's|    {{USER_ID}}     -> a non-PII identifier (hashed email or internal id). Optional.|    (User id parameter removed in this copy. To join answers to a user, add \&u=<your-id> to each link.)|' \
      "$f" > "$out"
  echo "wrote $out"
done
