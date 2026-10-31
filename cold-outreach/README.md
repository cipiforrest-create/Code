# Cold outreach

A B2B cold-email pipeline. It scores prospects, enforces suppression and lawful-basis rules, lints copy against the playbook, plans capped sends with follow-ups, routes replies, and reports the funnel.

It does not send email. `plan` writes a schedule for a person to approve.

- [docs/PLAYBOOK.md](docs/PLAYBOOK.md): the rules, and where each comes from
- [docs/SYSTEM.md](docs/SYSTEM.md): how the pieces fit, and which installed skill covers each stage

## Quick start

Python 3.9 or later. No packages to install.

```bash
cd cold-outreach
cp examples/campaign.json campaign.json      # edit: sender, mailboxes, warmup start, ICP

# 1. Score and filter the list
python3 scripts/outreach.py prepare my_prospects.csv

# 2. Write the first email for one prospect, then check it
python3 scripts/outreach.py render --email jane@acme.example --template examples/templates/first.txt --out run/preview.txt
python3 scripts/outreach.py lint run/preview.txt --step first --company Acme

# 3. Plan today's sends. Review run/send_plan.csv, then send by hand or through an approved sender
python3 scripts/outreach.py plan

# 4. Record what happened
python3 scripts/outreach.py log --email jane@acme.example --event sent --step first
python3 scripts/outreach.py log --email jane@acme.example --event reply --text "Sounds good, let's talk Tuesday"
python3 scripts/outreach.py log --email lee@globex.example --event bounced
python3 scripts/outreach.py log --email rob@globex.example --event opt_out --source "reply to first"

# 5. Read the funnel and the alerts
python3 scripts/outreach.py report
```

Run `plan` every day. It adds the follow-ups that have come due from your logged sends. Never edit `tracking.csv` or `suppression.csv` by hand. Use `log`, so every change is recorded.

## Input format

`prospects.csv` has these columns. Only `email` is required, but a prospect without a `signal` scores low and usually fails the threshold.

| Column | Use |
|---|---|
| email | Required. Lowercased and checked |
| first_name, last_name, company | Personalization and one-contact-per-company |
| title | Must contain one of `icp.titles` |
| country | ISO code. Compared to `basis_required_countries` |
| employees | Digits. Must fall inside `icp.employee_range` when present |
| website | Reference only |
| signal | A specific, checkable observation about the prospect. Written by a person |
| lawful_basis_ref | Consent-registry record ID for basis-required countries |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Privacy and safety

- `run/` and `campaign.json` are gitignored. They hold real prospect data.
- Check every prospect list for consent before you import it. The pipeline only enforces the rules you put into `campaign.json`.
- Compliance content is operational guidance, not legal advice. Confirm jurisdiction-specific requirements with counsel.
