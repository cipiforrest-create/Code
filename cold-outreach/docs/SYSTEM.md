# Cold outreach system: design

## What it is

A campaign pipeline for B2B cold email. It takes a prospect list and produces a capped, compliant send plan, lints each message against the playbook, routes replies, and reports the funnel. It does not send email. A person approves each send through an approved sender. Keeping the send step separate is deliberate: it is the one place where a mistake reaches a real inbox.

## Flow

```
prospects.csv
   │ prepare ── reject: invalid, role mailbox, suppressed, no lawful basis, off-ICP, duplicate
   ▼
run/prospects_scored.csv
   │ render ── fill template + sender footer (postal address, opt-out)
   │ lint ──── BLOCK → fix the copy   WARN → read it
   ▼
run/send_plan.csv  (pending_approval)   ← plan: due first steps and due follow-ups, per-mailbox caps
   │ human approves; approved sender sends
   ▼
log --event sent ──► run/tracking.csv
   │
   ├─ log --event reply  ──► category → action (triage rules)     ─┐
   ├─ log --event bounced / complaint / opt_out ──► suppression.csv ┤ excluded from every later plan
   ▼                                                                 │
plan (daily) ── next follow-up, due from the logged send date ◄─────┘
report ── funnel totals, complaint and bounce alerts
```

Two properties hold by construction:

- A follow-up is planned only after the previous step is logged as sent. A missing first email cannot trigger a follow-up.
- Anyone who replied, bounced, complained or opted out is excluded from every later plan, including plans built before the event was logged.

## Where each installed skill fits

The pipeline is the engine. The skills supply the judgment at each stage. Use them to design and review a campaign; the scripts enforce the mechanical parts.

| Stage | Skill | What it contributes |
|---|---|---|
| ICP and targeting | sales-icp, sales-qualify (BANT + MEDDIC) | ICP titles and size range in `campaign.json`; qualification criteria for `signal` |
| Prospect research | sales-research, sales-contacts, sales-prospect | Finds the observation for each `signal` and checks decision-maker titles |
| Hook and personalization | f13i cold-email (warm-signal check, hook types), awesome cold-email | Hook selection, the one-observation personalization rule |
| Copy | cold-email (real estate), cold-email (awesome), copywriting (marketing-skills), email-creative-builder | Rules encoded in `lint`; copy for each template |
| Subject lines | subject-line-lab | Subject candidates; `lint` enforces 2–4 words, lowercase |
| Sequence and throttle | cold-outbound-sequencer | Step timing, exit rules, reply-triage branches, warmup ramp |
| Compliance | consent-registry, cold-outbound-sequencer (CAN-SPAM guardrails) | Lawful-basis records (`lawful_basis_ref`), footer and opt-out |
| Deliverability | deliverability-qa | Pre-send SPF/DKIM/DMARC check, inbox placement, complaint and bounce read |
| Pre-send gate | email-quality-auditor | Full EQS score and the S1, S2, N1, D1 vetoes, if you want the audited number |
| Reply handling | sales-followup, sales-objections, outreach-manager | Objection rebuttals and referral handling behind the `triage` categories |
| Funnel review | send-experiment-designer, performance-analyzer | Tests of subject, angle or cadence, read from `report` output |

## Decisions

- **Stdlib Python, no service dependency.** Campaign state is CSV and JSON, so you can read and edit it. There is no hosted dependency and no credential in the repo.
- **Scripts enforce; humans judge.** `lint` catches mechanical violations. The A-to-B grade, the choice of observation, and every reply that is not clearly categorized stay with a person.
- **Opt-out wins.** Any opt-out phrase anywhere in a reply suppresses the sender, even if the reply also says something positive.
- **Caps are per mailbox and ramp weekly.** Volume grows only as fast as the warmup allows. The ramp numbers are category defaults, labeled Estimated.
- **Lawful basis is an input, not something the pipeline decides.** A prospect in a basis-required country without a `lawful_basis_ref` is rejected. The pipeline does not decide whether a basis is valid; consent-registry and counsel do.
- **Nothing is sent by the pipeline.** Sending adds a second human gate, which is the point.

## Not included

- Automatic sending and reply ingestion. Both need credentials and an approval path, and both are easy to add once the gate is trusted.
- Multi-campaign tracking. One campaign per `--run` directory.
- Personalization by an LLM. Observations are written or checked by a person, which is what the playbook requires.
