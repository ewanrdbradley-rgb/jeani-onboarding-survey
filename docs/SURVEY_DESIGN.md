# Survey design

Goal: real product feedback from new users in about a minute, from an email, on a phone.

## Shape

1. **One tap in the email.** The email shows "How's Jeani so far?" with five buttons (1 to 5). Each button is a link. Tapping records the rating immediately, even if the user closes the page that opens. This is the only question most people will answer, so it stands alone.
2. **Five tap-only questions on the landing page.** Chips, no typing. The rating from the email is pre-selected so the page starts 1/6 done.
3. **One optional free-text question** and an optional "happy to do a call" checkbox.

No name, email, or account details are asked for. A `u` parameter can carry your own non-PII user id from the email tool if you want to join answers to usage data.

## Questions and what each one tells you

| # | Question | Type | Answers |
|---|----------|------|---------|
| 1 | Overall, how's Jeani reading for you right now? | 1 to 5 scale | Sentiment. Slice every other answer by this. Anchors: not for me, working well. |
| 2 | What's the goal you're using Jeani for? | multi-select | Goal frame: a marathon or road race, trail or ultra, a first 5k, a comeback from injury, moving well for life, sleep and rest, pickleball or rec sports, strength, something else (free text). |
| 3 | Which parts have been useful so far? | multi-select | Good features: the texts, the Today tab, asking Jeani things, sleep readings, heart rate and HRV, training load and rest, the plan and its reasons, lab work in one place, wearable sync, not enough time yet. |
| 4 | How do you mostly use it? | single-select | Usage pattern: texts only, app most days, after a workout, weekly check-in, asks questions, no rhythm yet. |
| 5 | Anything about the look and feel that works for you? | multi-select | Design: quiet, feels like mine, compares me to my own normal, easy to read on the move, tone of the texts, white cards and trends, nothing yet. |
| 6 | If one thing changed, what should it be? | free text, optional | Improvements, in their words. |
| 7 | Happy to talk it through with the team for 15 minutes? | checkbox | Recruits interview candidates for free. |

Every option list ends with an honest escape ("Not enough time with it yet", "Nothing stands out yet"). Those answers are useful: a high share of "not used enough" on day 3 means the email is too early or activation is weak.

## Why it is built this way

- **Rating in the email, not on the page.** Email clients cannot submit forms. A link per rating value is the only reliable way to collect anything with one tap, and it captures data from people who never finish the page.
- **Chips instead of dropdowns or text.** Tapping is faster than typing on a phone and gives you countable data. The single free-text field gets the qualitative colour.
- **Everything optional after the rating.** Partial answers still get stored. Forcing completion lowers the response count more than it raises the quality.
- **Answer options mirror the brand's goal frame and product surfaces** (a marathon, a comeback, moving well for life, the texts, the Today and Jeani tabs, the plan and its reasons, labs, wearables). Wording follows the brand principles: sentence case, plain words, wellness words, no cheering. See `docs/BRAND.md`. That makes results directly comparable to the positioning: if nobody picks "Lab work in one place", that is a finding.
- **A late partial ping never overwrites a full submission.** The collector checks for that.

## Reading the results

- `python3 server/app.py summary` prints counts per option plus every free-text answer tagged with the rating.
- Look for gaps between the goal and what has been useful. Users training for a race who do not tick "Training load and rest" are a product signal.
- Split "usage pattern" by rating. If the 5s are "texts only" and the 2s are "open the app most days", the app surface is the weak spot, not the agent.
- Free text from 1s and 2s is the improvement backlog. Free text from 5s is the marketing copy.

## Editing the questions

All answer options live in one place: the `OPTIONS` object near the top of the script in `survey/memberfeedback/index.html`. Add or reword there. The collector stores whatever strings it receives, so no server change is needed.

## Timing recommendation

The welcome email (day 0) is too early for questions 2 to 5. Send the survey block in the day 3 to day 5 onboarding email, after the first sync and a few texts have landed. Repeat it once at day 14 with `src=day14_email` to compare.
