# Jeani onboarding survey

A one-minute product feedback survey that lives inside the onboarding email.

- `email/onboarding-snippet.html` — the block to paste into the onboarding email. Five one-tap rating buttons, each a plain link. A plain-text version is in `onboarding-snippet.txt`.
- `survey/index.html` — the mobile-first landing page. Reads the rating from the link, asks five tap-only questions plus one optional free-text question, and posts the answers.
- `server/app.py` — zero-dependency collector (Python stdlib, SQLite). Serves the page, stores responses, exports CSV, prints a summary.
- `docs/SURVEY_DESIGN.md` — the questions, why they are shaped this way, and how to read the results.

## Flow

```
onboarding email  --tap 1..5-->  survey page (?r=4&u=<id>&src=onboarding_email)
                                    |  rating stored immediately (partial=1)
                                    |  user taps chips, hits Send
                                    v
                               POST /api/feedback  -->  data/feedback.db
                                                          |
                                     python3 server/app.py summary / export
```

## Run locally

```bash
SURVEY_ADMIN_TOKEN=dev python3 server/app.py
```

Then open http://127.0.0.1:8787/?r=4&src=test. Summary at http://127.0.0.1:8787/api/summary?token=dev.

Smoke test the whole thing:

```bash
scripts/smoke_test.sh
```

## Deploy on the VPS

Same pattern as the analytics report (systemd user unit, no Docker).

1. `git clone` this repo to `~/jeani-onboarding-survey` on the VPS.
2. `cp .env.example .env` and set a real `SURVEY_ADMIN_TOKEN`.
3. Install the unit: see the comments at the top of `server/jeani-survey.service`.
4. Put it behind HTTPS. `server/Caddyfile.example` shows a Caddy reverse proxy; nginx or the existing proxy on the box works too. DNS: `feedback.jeanihealth.com` A record to the VPS.
5. Check `https://feedback.jeanihealth.com/healthz`.

Static hosting instead: the survey page is plain HTML. Host `survey/index.html` anywhere and set `window.SURVEY_ENDPOINT` to the collector's URL before the script runs (add a one-line inline `<script>` in the head). Set `SURVEY_CORS_ORIGIN` on the collector to the page's origin.

## Put it into the onboarding flow

1. In the email tool, replace `{{SURVEY_URL}}` with `https://feedback.jeanihealth.com/` and `{{USER_ID}}` with a non-PII id (or leave it out).
2. Paste the table from `email/onboarding-snippet.html` below the main content of the day 3 to day 5 onboarding email. Add the text version to the plain-text part.
3. Send yourself a test. Tap "4". Confirm the page opens with 4 selected and that `summary` shows one partial response with `source=onboarding_email`.
4. Reuse the block in later emails with a different `src` value (`day14_email`, `trial_end_email`) so the sources can be compared.

## Reading results

```bash
python3 server/app.py summary
python3 server/app.py export > feedback.csv
```

Or over HTTP: `/api/summary?token=...` and `/api/export.csv?token=...`.
