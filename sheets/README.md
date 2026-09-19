# Send responses to a Google Sheet

No server. The survey page posts straight to a Google Apps Script web app that is bound to your results spreadsheet. One row per response, plus a live Summary tab.

## Setup (about 5 minutes)

1. Create a new Google Sheet. Name it something like "Jeani onboarding feedback".
2. Extensions → Apps Script. Delete the placeholder and paste the whole of `sheets/Code.gs`. Save.
3. In the editor's function dropdown pick `setup` and click Run. Authorise when prompted (it only touches this spreadsheet). Two tabs appear: **Responses** and **Summary**.
4. Optionally run `testInsert` to see a fake row land and confirm the Summary tab updates.
5. Deploy → New deployment → type **Web app**. Settings:
   - Execute as: **Me**
   - Who has access: **Anyone** (the page posts anonymously; the sheet itself stays private)
   Click Deploy and copy the URL ending in `/exec`.
6. Open `survey/memberfeedback/index.html` and paste that URL into `SURVEY_ENDPOINT` near the top of the script.
7. Host the page (see the main README: GitHub Pages is wired up) and test with `?r=4&src=test`.

## Notes

- **Updating the script later** needs Deploy → Manage deployments → edit → New version. Saving alone does not change the live URL.
- **Why text/plain?** The page sends the JSON body with a `text/plain` content type. That avoids a CORS preflight, which Apps Script cannot answer. The script parses the body as JSON regardless.
- **Upsert.** Each visitor gets a random `response_id`. The rating from the email tap is stored immediately as a partial row, and the full submission overwrites that same row. A late partial ping never overwrites a full answer.
- **Summary tab** counts every option dynamically, so you can add or reword options in the page without touching the sheet.
- **Rate limits.** Apps Script web apps handle a few thousand requests a day on a normal Google account, far above what an onboarding email produces.
- **Privacy.** The sheet stores what the page sends: answers, a random id, an optional `u` id you choose to put in the email link, source tag, and user agent. No email address.
