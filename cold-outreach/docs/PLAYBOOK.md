# Cold outreach playbook

These are the rules the pipeline enforces and the rules a human applies before sending. Each rule names its source. Where a rule is a default and not a measured fact, it says so.

## 1. Who to contact

- Define the ICP in `campaign.json` (titles, employee range). Score on fit and signal, not on list size.
- One contact per company per campaign. The highest-scoring contact wins.
- No role mailboxes (`info@`, `sales@`, `hello@`). They do not have a buyer's inbox and they hurt complaint rates.
- Research before writing. The `signal` column is a specific, checkable observation about the prospect: their pricing page, a job post, a launch, a funding round. No signal, no send. (Source: f13i warm-signal and hook rules.)

## 2. Lawful basis and suppression

- Every send checks the suppression list first. Opt-outs, hard bounces and complaints are permanent.
- Recipients in `basis_required_countries` need a lawful-basis record (`lawful_basis_ref`) before they can be contacted. The pipeline never invents that record. Keep it in consent-registry. (Source: cold-outbound-sequencer, consent-registry.)
- The footer names the sender and a postal address, and includes a working opt-out line. The skill guidance is CAN-SPAM: accurate From and reply-to, a non-deceptive subject, a physical address, and an opt-out honored promptly. This is operational guidance, not legal advice. Confirm jurisdiction-specific requirements with counsel.
- Opt-out wording is honored by `log --event reply --text ...`. It suppresses the prospect on the spot and stops every step.

## 3. Copy

Rules for the first email:

| Rule | Value | Source |
|---|---|---|
| Length | 50–120 words in the body | cold-email (real estate), cold-email (f13i) |
| Format | Plain text. No HTML, buttons or images | cold-email (real estate) |
| Links | None in the first email | cold-email (real estate), cold-email (f13i) |
| Problem | One problem per email | cold-email (real estate) |
| Ask | One soft question. No "book a call" | cold-email (real estate), cold-email (awesome) |
| Subject | 2–4 words, lowercase, no punctuation or emoji, no first name | cold-email (awesome) |
| Voice | Peer to peer. Contractions. "You" beats "I" and "we" | cold-email (awesome), cold-email (f13i) |
| Banned | "leverage", "synergy", "circle back", "I hope this email finds you well", "schedule a call", and similar | cold-email (awesome), cold-email (real estate) |

Structure, in order: a specific observation about their business, the problem it implies, the consequence if nothing changes, and one soft ask. If the personalization sentence could be removed without breaking the email, the personalization is not working. (Source: cold-email (awesome) personalization rule.)

Grade every first email before it goes out. The f13i rubric is A+ to B, and nothing below B is sent. That grade is a human judgment; the linter only catches mechanical violations.

## 4. Sequence

Default cadence: three touches over ten days, then stop.

| Step | Day | Purpose |
|---|---|---|
| first | 0 | Observation, problem, soft ask |
| follow_up | 3 | Add one new fact or a useful example. Never "just checking in" |
| breakup | 10 | Close the loop, give an easy no |

The cadence is a default labeled Estimated, not a measured optimum. Each step must have an exit rule: any reply, any opt-out, any bounce, or the end of the sequence. No reply type falls through to "continue the sequence". (Source: cold-outbound-sequencer.)

## 5. Reply triage

Every reply is classified. Each category has one action, and an unclear reply goes to a human.

| Category | Example | Action |
|---|---|---|
| opt_out | "unsubscribe me" | Suppress now, stop all steps |
| decline | "not interested, thanks" | Stop the sequence. No more touches |
| referral | "talk to our CFO, Dana" | Stop this sequence. Check the referral, then add them as a new prospect |
| not_now | "check back in Q3" | Pause. A human re-enrols on the date agreed |
| objection | "we already use a competitor" | Stop automated steps. A human writes the rebuttal |
| positive | "sounds good, let's talk" | Stop automated steps. Hand to sales today |
| needs_human | anything unclear | A human reads it |

Opt-out always wins. Order matters: "interested, but not now" is `not_now`. The keyword rules are heuristics. They do not read tone, so a human still reviews the `objection` and `needs_human` queues. (Source: cold-outbound-sequencer reply-triage branches.)

## 6. Deliverability and warmup

- Before the first send, verify SPF, DKIM and DMARC for the sending domain. Missing or failing authentication is a blocker. A DMARC `p=none` policy with aligned SPF and DKIM is a flag, not a block. (Source: deliverability-qa.)
- Warm up new mailboxes. The default ramp is 5 per mailbox per day in week one, plus 5 per week, capped at 30. These numbers are category defaults labeled Estimated, not measured from your domain. Set `warmup_started` to the day warmup began.
- Spread volume across mailboxes. The planner balances across them and never exceeds a cap.
- Spam complaints must stay under 0.1%. At or above that, `report` alerts and you pause sending. (Source: SEND benchmark.)
- Bounces above 2% trigger a warning. This is a heuristic. Re-verify addresses before the next send.

## 7. Pre-send gate

1. `prepare` the list and read the reject reasons.
2. `render` one prospect per template and `lint` the rendered output. Every `BLOCK` must be fixed.
3. Read every `WARN`. Fix it or accept it on purpose.
4. Grade the first email (A or better).
5. `plan`, review `run/send_plan.csv`, then send through an approved sender.
6. `log --event sent` for each send. The log drives follow-ups and suppression.

Optional: run email-quality-auditor on the whole program for a full EQS score and the S1, S2, N1 and D1 vetoes.

## 8. Reporting

Run `report` weekly. Watch reply rate, opt-out rate, bounce rate and complaint rate. A rising opt-out rate usually means the ICP or the observation is wrong, not the volume.
