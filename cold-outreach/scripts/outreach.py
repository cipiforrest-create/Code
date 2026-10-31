#!/usr/bin/env python3
"""Cold outreach pipeline for one campaign.

Commands:
  prepare  score and filter prospects; reject suppressed, unbased, off-ICP rows
  render   fill a template for one prospect and add the sender footer
  lint     check a rendered email against the playbook; exit 1 on any BLOCK
  plan     build the next send schedule (new prospects + due follow-ups), capped per mailbox
  log      record a send, bounce, complaint, opt-out or reply; updates suppression
  triage   classify reply text without writing anything
  report   funnel totals and deliverability alerts

Stdlib only. Nothing here sends email. `plan` writes a schedule for a human to approve.
"""

import argparse
import csv
import datetime as dt
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROLE_LOCALPARTS = {
    "info", "sales", "hello", "hi", "support", "admin", "contact", "team", "hr",
    "careers", "jobs", "press", "marketing", "billing", "noreply", "no-reply",
}
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$")

# Phrases from the playbook's banned list. Any hit is a BLOCK.
BANNED_PHRASES = [
    "i hope this email finds you well", "leverage", "synergy", "cutting-edge",
    "best-in-class", "we specialize", "circle back", "schedule a call",
    "book a call", "jump on a call", "quick call", "touch base", "game-changer",
]
SPAM_WORDS = ["guarantee", "act now", "limited time", "free!", "winner", "100%", "urgent", "risk-free"]

# Ordered: the first matching category wins, so opt-out always beats everything else.
REPLY_RULES = [
    ("opt_out", [
        r"\bunsubscribe\b", r"\bremove me\b", r"\btake me off\b",
        r"\bstop (emailing|contacting|messaging|sending)\b", r"\bdo not (contact|email)\b", r"\bopt[ -]?out\b",
    ]),
    ("decline", [r"\bnot interested\b", r"\bno,? thank(s| you)\b", r"\bnot a fit\b", r"\bwe'?re (good|all set)\b"]),
    ("referral", [
        r"\b(talk|speak|reach out|get in touch) (to|with) (?!me\b|us\b)\w+",
        r"\b(forward|passing|pass) (this|you|it|your)\b", r"\bright person\b", r"\bwrong (person|contact)\b", r"\bloop in\b",
    ]),
    ("not_now", [
        r"\bnot (right )?now\b", r"\bcheck back\b", r"\bcircle back\b", r"\bnext (quarter|year|month)\b",
        r"\b(reach|follow) (out|up) (later|in \w+)\b",
    ]),
    ("objection", [
        r"\balready (have|use|using|got)\b", r"\bno budget\b", r"\btoo expensive\b", r"\bnot a priority\b",
        r"\bhappy with\b", r"\bcurrent (vendor|provider|tool)\b", r"\bprice\b",
    ]),
    ("positive", [
        r"(?<!not )\binterested\b", r"\bsounds good\b", r"\blet'?s (talk|chat|meet|connect|do it)\b",
        r"\bsend (it|me|over)\b", r"\bhappy to (talk|chat|meet|learn)\b", r"\btell me more\b",
        r"\byes,? (please|let'?s)\b", r"\bbook\b", r"\bwhen (are you|can we)\b",
    ]),
]

ACTIONS = {
    "opt_out": "Suppress now. Stop every step. Keep the request on record in consent-registry.",
    "decline": "Stop the sequence. No further touches. Log it.",
    "referral": "Stop this sequence. Check the referred person, then add them as a new prospect.",
    "not_now": "Pause. A human re-enrols them on the date agreed in the reply.",
    "objection": "Stop automated steps. A human writes the rebuttal from the objection branch.",
    "positive": "Stop automated steps. Hand to sales today.",
    "needs_human": "Stop automated steps. A human reads the reply.",
}

# Length bounds in words for the main body (footer excluded).
LENGTH = {"first": (50, 120)}
DEFAULT_LENGTH = (20, 120)

COMPLAINT_RED_LINE = 0.001  # SEND benchmark: spam complaints must stay under 0.1%
BOUNCE_WARN = 0.02          # heuristic: warn above 2% hard bounces

SUPPRESSING_EVENTS = {"opt_out": "opt_out", "bounced": "bounced", "complaint": "complaint"}
PROSPECT_FIELDS = [
    "email", "first_name", "last_name", "company", "title", "country",
    "employees", "website", "signal", "lawful_basis_ref",
]
TRACKING_FIELDS = ["date", "email", "event", "step", "category"]
SUPPRESSION_FIELDS = ["email", "reason", "date", "source"]
PLAN_FIELDS = ["send_date", "mailbox", "email", "company", "step", "template", "status"]


# ---------- file helpers ----------

def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields, append=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not append or not path.exists()
    with path.open("a" if append else "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def load_config(path):
    with resolve(path).open(encoding="utf-8") as f:
        return json.load(f)


def suppressed_emails(run):
    return {r["email"].strip().lower(): r["reason"] for r in read_csv(run / "suppression.csv")}


# ---------- prepare ----------

def score_prospect(row, cfg, suppressed):
    """Return (score, reject_reason). An empty reason means the row is eligible."""
    email = row["email"]
    if not EMAIL_RE.match(email):
        return 0, "invalid_email"
    if email.split("@")[0] in ROLE_LOCALPARTS:
        return 0, "role_mailbox"
    if email in suppressed:
        return 0, f"suppressed:{suppressed[email]}"
    if row["country"].upper() in cfg.get("basis_required_countries", []) and not row["lawful_basis_ref"]:
        return 0, "no_lawful_basis_on_file"
    icp = cfg["icp"]
    if not any(t in row["title"].lower() for t in icp["titles"]):
        return 0, "title_mismatch"
    score = 40
    if row["employees"].isdigit():
        lo, hi = icp["employee_range"]
        if not lo <= int(row["employees"]) <= hi:
            return 0, "size_out_of_range"
        score += 30
    if row["signal"]:
        score += 30
    return score, ""


def cmd_prepare(args):
    cfg = load_config(args.config)
    suppressed = suppressed_emails(args.run)
    min_score = cfg["icp"].get("min_score", 60)

    rows = []
    for raw in read_csv(args.input):
        row = {f: (raw.get(f) or "").strip() for f in PROSPECT_FIELDS}
        row["email"] = row["email"].lower()
        score, reason = score_prospect(row, cfg, suppressed)
        rows.append({**row, "score": score, "decision": "rejected" if reason else "ready", "reason": reason})

    # One contact per company and one row per email. The highest score wins.
    seen_emails, seen_companies = set(), set()
    for row in sorted(rows, key=lambda r: -r["score"]):
        if row["decision"] == "ready" and row["score"] < min_score:
            row["decision"], row["reason"] = "rejected", "low_score"
        if row["decision"] != "ready":
            continue
        company = row["company"].lower()
        if row["email"] in seen_emails:
            row["decision"], row["reason"] = "rejected", "duplicate_email"
        elif company and company in seen_companies:
            row["decision"], row["reason"] = "rejected", "duplicate_company"
        else:
            seen_emails.add(row["email"])
            seen_companies.add(company)

    out = args.run / "prospects_scored.csv"
    write_csv(out, rows, PROSPECT_FIELDS + ["score", "decision", "reason"])
    counts = Counter(r["reason"] or "ready" for r in rows)
    print(f"wrote {out} ({len(rows)} rows)")
    for reason, n in counts.most_common():
        print(f"  {reason}: {n}")
    return 0


# ---------- render and lint ----------

def render_template(template_text, row, cfg):
    values = {
        "first_name": row.get("first_name", ""),
        "company": row.get("company", ""),
        "signal": row.get("signal", ""),
        "sender_name": cfg["sender"]["name"],
    }
    body = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template_text).rstrip()
    footer = (
        f"\n\n--\n{cfg['sender']['name']}\n{cfg['sender']['postal_address']}\n"
        "Not a fit? Reply 'unsubscribe' and I will remove you from this list.\n"
    )
    return body + footer


def cmd_render(args):
    cfg = load_config(args.config)
    people = {r["email"]: r for r in read_csv(args.run / "prospects_scored.csv")}
    row = people.get(args.email.strip().lower())
    if row is None:
        print(f"no scored prospect with email {args.email}", file=sys.stderr)
        return 2
    text = render_template(resolve(args.template).read_text(encoding="utf-8"), row, cfg)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    return 0


def lint_text(text, step, cfg, company=""):
    """Return (findings, blocked). Findings are (severity, rule, message)."""
    findings = []

    def add(sev, rule, msg):
        findings.append((sev, rule, msg))

    lines = text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        subject, body = "", text.strip()
        add("BLOCK", "subject", "first line must be 'Subject: ...'")

    words = subject.split()
    if not 2 <= len(words) <= 4:
        add("BLOCK", "subject-length", f"subject has {len(words)} words; use 2-4")
    if subject and subject != subject.lower():
        add("WARN", "subject-case", "subject should be lowercase")
    if re.search(r"[!?]", subject) or re.search(r"[\U0001F300-\U0001FAFF☀-➿]", subject):
        add("WARN", "subject-punctuation", "no '!', '?' or emoji in the subject")

    if re.search(r"\{\{.*?\}\}", text):
        add("BLOCK", "placeholder", "unresolved {{placeholder}} left in the email")
    if re.search(r"<[a-zA-Z/!][^>]*>", text):
        add("BLOCK", "html", "HTML found; cold email is plain text")

    main, _, footer = body.partition("\n--\n")
    lo, hi = LENGTH.get(step, DEFAULT_LENGTH)
    words_in_body = len(re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", main))
    if not lo <= words_in_body <= hi:
        add("BLOCK", "length", f"body is {words_in_body} words; target {lo}-{hi}")

    links = re.findall(r"https?://\S+|www\.\S+", main)
    if links:
        add("BLOCK" if step == "first" else "WARN", "links", f"{len(links)} link(s) in the body")

    questions = main.count("?")
    if questions == 0:
        add("WARN", "cta", "no question; end with one soft ask")
    elif questions > 1:
        add("WARN", "cta", f"{questions} questions; keep to one ask")

    lowered = main.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            add("BLOCK", "banned-phrase", f"contains '{phrase}'")
    for word in SPAM_WORDS:
        if word in (subject + " " + lowered).lower():
            add("WARN", "spam-word", f"contains '{word}'")

    company_key = re.sub(r"[®™©]", "", company).strip().lower()
    if company_key and company_key not in lowered:
        add("BLOCK", "personalization", f"company name '{company}' is not in the body")

    if cfg["sender"]["postal_address"] not in footer:
        add("BLOCK", "can-spam-address", "postal address missing from the footer")
    if not re.search(r"unsubscribe|opt[ -]?out", footer, re.I):
        add("BLOCK", "can-spam-optout", "opt-out line missing from the footer")

    blocked = any(sev == "BLOCK" for sev, _, _ in findings)
    return findings, blocked


def cmd_lint(args):
    cfg = load_config(args.config)
    findings, blocked = lint_text(Path(args.file).read_text(encoding="utf-8"), args.step, cfg, args.company or "")
    for sev, rule, msg in findings:
        print(f"{sev:5} {rule}: {msg}")
    if not findings:
        print("PASS: no findings")
    elif not blocked:
        print("PASS with warnings")
    else:
        print("FAIL: fix every BLOCK before sending")
    return 1 if blocked else 0


# ---------- plan ----------

def cap_for_day(day, warm):
    """Per-mailbox daily cap: ramps weekly from warmup start, then holds at steady_cap."""
    start = dt.date.fromisoformat(warm["warmup_started"])
    week = max(0, (day - start).days // 7)
    return min(warm["steady_cap"], warm["start_per_mailbox"] + warm["increment_per_week"] * week)


def excluded_emails(tracking, suppressed):
    """Anyone suppressed, bounced, complained, opted out or who replied is out of the sequence."""
    out = set(suppressed)
    for r in tracking:
        if r["event"] in SUPPRESSING_EVENTS or r["event"] == "reply":
            out.add(r["email"])
    return out


def build_queue(ready_rows, tracking, steps, excluded, today):
    """Return (offset_days, email, step_index) for every send that could go out."""
    index = {s["name"]: i for i, s in enumerate(steps)}
    last = {}
    for r in tracking:
        if r["event"] != "sent" or r["step"] not in index:
            continue
        k, sent_on = index[r["step"]], dt.date.fromisoformat(r["date"])
        if r["email"] not in last or (k, sent_on) > last[r["email"]]:
            last[r["email"]] = (k, sent_on)

    queue = []
    for row in ready_rows:
        email = row["email"]
        if email in excluded:
            continue
        if email not in last:
            queue.append((0, email, 0))
            continue
        k, sent_on = last[email]
        if k + 1 < len(steps):
            due = sent_on + dt.timedelta(days=steps[k + 1]["day"] - steps[k]["day"])
            queue.append((max(0, (due - today).days), email, k + 1))
    return queue


def build_plan(queue, people, steps, mailboxes, warm, today, horizon):
    """Assign due sends to mailboxes day by day, never exceeding each mailbox's cap.

    Only sends already due are planned. A follow-up is never planned until the
    previous step is logged as sent, so a missing first email cannot trigger a follow-up.
    """
    seq = itertools.count()
    pending = [(offset, next(seq), email, k) for offset, email, k in queue]
    rows = []
    for offset in range(horizon):
        send_day = today + dt.timedelta(days=offset)
        cap = cap_for_day(send_day, warm)
        used = {m: 0 for m in mailboxes}
        for item in sorted(p for p in pending if p[0] <= offset):
            _, _, email, k = item
            open_boxes = [m for m in mailboxes if used[m] < cap]
            if not open_boxes:
                break
            mailbox = min(open_boxes, key=lambda m: used[m])
            used[mailbox] += 1
            pending.remove(item)
            rows.append({
                "send_date": send_day.isoformat(),
                "mailbox": mailbox,
                "email": email,
                "company": people[email]["company"],
                "step": steps[k]["name"],
                "template": steps[k]["template"],
                "status": "pending_approval",
            })
    return rows, pending


def cmd_plan(args):
    cfg = load_config(args.config)
    today = dt.date.fromisoformat(cfg["start_date"]) if cfg.get("start_date") else dt.date.today()
    steps = cfg["sequence"]
    ready = [r for r in read_csv(args.run / "prospects_scored.csv") if r["decision"] == "ready"]
    if not ready:
        print("no ready prospects; run prepare first", file=sys.stderr)
        return 2
    tracking = read_csv(args.run / "tracking.csv")
    excluded = excluded_emails(tracking, suppressed_emails(args.run))
    queue = build_queue(ready, tracking, steps, excluded, today)
    people = {r["email"]: r for r in ready}
    rows, pending = build_plan(queue, people, steps, cfg["mailboxes"], cfg["warmup"], today, args.horizon)

    out = args.run / "send_plan.csv"
    write_csv(out, rows, PLAN_FIELDS)
    print(f"wrote {out}: {len(rows)} sends over {args.horizon} days, {len(pending)} still waiting")
    for step, n in Counter(r["step"] for r in rows).most_common():
        print(f"  {step}: {n}")
    print("Review the plan. Send each row through an approved sender, then log it with `log --event sent`.")
    return 0


# ---------- log, triage, report ----------

def classify_reply(text):
    for category, patterns in REPLY_RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.I):
                return category
    return "needs_human"


def cmd_log(args):
    cfg = load_config(args.config)
    email = args.email.strip().lower()
    step_names = [s["name"] for s in cfg["sequence"]]
    date = args.date or dt.date.today().isoformat()
    if args.event == "sent" and args.step not in step_names:
        print(f"--step must be one of {step_names} when logging a send", file=sys.stderr)
        return 2

    category = args.category or ""
    if args.event == "reply":
        if not category and args.text:
            category = classify_reply(args.text)
        category = category or "needs_human"
        if category not in ACTIONS:
            print(f"unknown reply category '{category}'", file=sys.stderr)
            return 2

    write_csv(args.run / "tracking.csv", [{
        "date": date, "email": email, "event": args.event, "step": args.step or "", "category": category,
    }], TRACKING_FIELDS, append=True)

    reason = SUPPRESSING_EVENTS.get(args.event)
    if args.event == "reply" and category == "opt_out":
        reason = "opt_out"
    if reason:
        write_csv(args.run / "suppression.csv", [{
            "email": email, "reason": reason, "date": date, "source": args.source or "log",
        }], SUPPRESSION_FIELDS, append=True)
        print(f"suppressed {email}: {reason}. Excluded from every future plan.")

    print(f"logged {args.event} for {email}")
    if args.event == "reply":
        print(f"category {category}: {ACTIONS[category]}")
    return 0


def cmd_triage(args):
    category = classify_reply(args.text)
    print(json.dumps({"category": category, "action": ACTIONS[category]}, indent=2))
    return 0


def cmd_report(args):
    cfg = load_config(args.config)
    tracking = read_csv(args.run / "tracking.csv")
    sent = [r for r in tracking if r["event"] == "sent"]
    sent_people = {r["email"] for r in sent}
    replied = {r["email"] for r in tracking if r["event"] == "reply"}

    def events(name):
        return sum(1 for r in tracking if r["event"] == name)

    print(f"touches sent: {len(sent)} to {len(sent_people)} people")
    for step in cfg["sequence"]:
        print(f"  {step['name']}: {sum(1 for r in sent if r['step'] == step['name'])}")

    pct = len(replied) / len(sent_people) if sent_people else 0
    print(f"replies: {len(replied)} people ({pct:.1%} of people contacted)")
    categories = Counter(r["category"] for r in tracking if r["event"] == "reply")
    for category in ACTIONS:
        if categories[category]:
            print(f"  {category}: {categories[category]}")

    bounce_rate = events("bounced") / len(sent) if sent else 0
    complaint_rate = events("complaint") / len(sent) if sent else 0
    print(f"bounce rate: {bounce_rate:.2%}   complaint rate: {complaint_rate:.3%}")
    if complaint_rate >= COMPLAINT_RED_LINE:
        print("ALERT: complaint rate is at or above the 0.1% red line. Pause sending and review the list source.")
    elif bounce_rate > BOUNCE_WARN:
        print("WARN: bounce rate is above 2%. Re-verify addresses before the next send.")
    return 0


# ---------- CLI ----------

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, default=ROOT / "campaign.json", help="campaign config (JSON)")
    common.add_argument("--run", type=Path, default=ROOT / "run", help="directory for run state and outputs")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", parents=[common], help="score and filter a prospect CSV")
    p.add_argument("input", type=Path)
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("render", parents=[common], help="fill a template for one prospect")
    p.add_argument("--email", required=True)
    p.add_argument("--template", required=True, type=Path)
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("lint", parents=[common], help="check a rendered email")
    p.add_argument("file", type=Path)
    p.add_argument("--step", required=True, help="sequence step name, e.g. first")
    p.add_argument("--company", help="company name that must appear in the body")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("plan", parents=[common], help="build the next send schedule")
    p.add_argument("--horizon", type=int, default=7, help="days to plan ahead")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("log", parents=[common], help="record a send, bounce, complaint, opt-out or reply")
    p.add_argument("--email", required=True)
    p.add_argument("--event", required=True, choices=["sent", "reply", "bounced", "complaint", "opt_out"])
    p.add_argument("--step", help="sequence step, required for sent")
    p.add_argument("--text", help="reply text to classify")
    p.add_argument("--category", help="reply category, overrides --text")
    p.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    p.add_argument("--source", help="where this record came from")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("triage", help="classify reply text without writing anything")
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("report", parents=[common], help="funnel totals and deliverability alerts")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
