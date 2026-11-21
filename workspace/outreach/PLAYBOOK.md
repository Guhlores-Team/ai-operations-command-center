# Website outreach playbook

Working rules for the demo-first outreach pipeline. State lives in this folder so any
session can pick up where the last one stopped.

| File | Purpose |
|---|---|
| `pipeline.csv` | One row per lead: research, demo link, draft ID, send date, status, response, outcome |
| `suppression.csv` | Never contact: opt-outs and anyone already reached by an earlier campaign |
| `emails/<slug>.md` | The exact email text for each lead |
| `demos/<slug>/index.html` | The lead's concept site, deployed at `site-concept-previews.vercel.app/<slug>` |
| `candidates.csv` | Next leads to research (`python scripts/find_directory_leads.py --write`) |

## Qualifying a lead (all four, or skip it)
1. Listed in a current, public source with a published business email.
2. No working website: search the name, and check the obvious domains. A blank "website"
   field is a hint, not proof.
3. Evidence it is operating (current certification, recent listing or reviews).
4. Not in `pipeline.csv` or `suppression.csv`.

## Building a demo
- Use only facts from the public listing: name, services, contact, founding year, certifications.
  No invented reviews, testimonials, prices, hours, licences or history.
- Every demo carries the "Concept preview - not the official website" banner and footer, and
  stays `noindex`. Forms are inert. No street addresses for home-based businesses.
- A distinct design per business. Check desktop and mobile before deploying.
- After deploying, confirm the link returns 200 without a login before it goes in an email.

## Sending rules
- Drafts first. Nothing is sent without the owner's approval of that specific email.
- Plain text, one link, accurate subject line, no attachments, no tracking pixels.
- Every email ends with the sender's name, business name, a valid postal address and a
  one-line opt-out (CAN-SPAM).
- Business hours in the recipient's time zone (9:30-16:30, Mon-Fri), randomised times,
  roughly 2-3 hours apart. Never on public holidays.
- One follow-up at most, 4-5 business days later, only if there was no reply. Then stop.
- Any "no", "stop" or "remove me" goes into `suppression.csv` the same day.

## Volume
The sending account is a new gmail.com address with no history, so volume is earned.
- Day 1: 3. Day 2: 2-3. Hold or step up by 1-2 a day only after a clean day.
- A clean day = zero bounces, zero Gmail warnings, no "this looks like spam" replies.
- Any bounce: fix the address source before sending more. Two in a day, or any Gmail
  warning or sending restriction: stop and investigate.
- No reply is not evidence of inbox placement. Never raise volume to hit a number.

## End-of-day review
1. Search the inbox for `from:mailer-daemon` and Google account alerts.
2. Record replies in `pipeline.csv`; flag interested ones to the owner.
3. Move opt-outs to `suppression.csv`.
4. Decide tomorrow's volume from the rules above and note it here.

## Sales conversations
Never quote a price, a delivery date or a feature without the owner's sign-off.
