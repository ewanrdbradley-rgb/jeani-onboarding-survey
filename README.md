# Jeani onboarding survey

A one-minute product feedback survey that lives inside the onboarding email. Answers land in a Google Sheet.

- `email/onboarding-snippet.html` — the block to paste into the onboarding email. Five one-tap rating buttons, each a plain link. Plain-text version in `onboarding-snippet.txt`.
- `survey/index.html` — the mobile-first landing page. Reads the rating from the link, asks five tap-only questions plus one optional free-text question, and posts the answers.
- `sheets/Code.gs` — Google Apps Script that receives the answers and writes one row per response to your Sheet, with a live Summary tab. Setup in `sheets/README.md`.
- `docs/SURVEY_DESIGN.md` — the questions, why they are shaped this way, and how to read the results.
- `server/` — optional self-hosted collector (Python, SQLite) if you ever want the data off Google. Not needed for the Sheet path.

## Flow

```
onboarding email  --tap 1..5-->  survey page on GitHub Pages (?r=4&u=<id>&src=onboarding_email)
                                    |  rating stored immediately (partial = TRUE)
                                    |  user taps chips, hits Send
                                    v
                         POST to Apps Script web app  -->  Google Sheet "Responses" tab
                                                             "Summary" tab updates live
```

## Set up (three parts)

### 1. The Google Sheet (5 minutes)

Follow `sheets/README.md`. You end up with a web app URL ending in `/exec`.

### 2. The survey page

1. Paste the `/exec` URL into `SURVEY_ENDPOINT` near the top of the script in `survey/index.html`.
2. Push to GitHub. In the repo: Settings → Pages → Source: **GitHub Actions**. The workflow in `.github/workflows/pages.yml` publishes the `survey/` folder on every push to `main`.
3. The page is at `https://<github-user>.github.io/jeani-onboarding-survey/`. For `feedback.jeanihealth.com` instead, add a CNAME record pointing there and set the custom domain in the same Pages settings screen.
4. Open the page with `?r=4&src=test`, submit, and watch the row appear in the Sheet.

### 3. The email

1. In the email tool, replace `{{SURVEY_URL}}` with the page URL and `{{USER_ID}}` with a non-PII id (or delete that parameter).
2. Paste the table from `email/onboarding-snippet.html` below the main content of the day 3 to day 5 onboarding email. Add the text version to the plain-text part.
3. Send yourself a test. Tap "4". Confirm the page opens with 4 selected and a partial row appears in the Sheet with `source = onboarding_email`.
4. Reuse the block in later emails with a different `src` value (`day14_email`, `trial_end_email`) so the sources can be compared in the Sheet.

## Reading results

The **Summary** tab shows response counts, average rating, rating distribution, and a ranked breakdown of use cases, useful features, usage pattern and design likes, plus every "one thing to improve" answer tagged with its rating. Filter the **Responses** tab by `partial = FALSE` for completed surveys only.

## Editing the questions

All answer options live in the `OPTIONS` object near the top of the script in `survey/index.html`. The Sheet counts whatever strings arrive, so nothing else needs to change.

## Run locally

```bash
SURVEY_ADMIN_TOKEN=dev python3 server/app.py
```

Opens the page at http://127.0.0.1:8787/?r=4&src=test using the local SQLite collector. `scripts/smoke_test.sh` exercises that collector end to end.
