"""Tests for scripts/outreach.py. Run: python3 -m unittest discover -s tests -v"""

import datetime as dt
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "outreach", Path(__file__).resolve().parent.parent / "scripts" / "outreach.py"
)
outreach = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(outreach)

CFG = {
    "sender": {"name": "Sam Example", "postal_address": "1 Example Street, Springfield, USA"},
    "mailboxes": ["a@mail.example.com", "b@mail.example.com"],
    "warmup": {"warmup_started": "2026-01-05", "start_per_mailbox": 5, "increment_per_week": 5, "steady_cap": 30},
    "icp": {"titles": ["head of sales", "vp sales", "founder"], "employee_range": [20, 300], "min_score": 60},
    "basis_required_countries": ["DE"],
    "sequence": [
        {"name": "first", "day": 0, "template": "examples/templates/first.txt"},
        {"name": "follow_up", "day": 3, "template": "examples/templates/follow_up.txt"},
        {"name": "breakup", "day": 10, "template": "examples/templates/breakup.txt"},
    ],
}

GOOD_FIRST = """Subject: pricing after the limit

Hi Jane,

Quick thing I noticed on Acme's pricing page. Your plans list three tiers with no overage price.

Buyers who hit a usage cap with no stated price usually stop comparing instead of asking sales. That makes the trial convert less than it should, and the gap shows up before anyone talks to your team.

Is this something your team has looked at yet?

Sam Example
"""


def footer_render(text, cfg=CFG):
    return text + f"\n--\n{cfg['sender']['name']}\n{cfg['sender']['postal_address']}\nReply 'unsubscribe' to opt out.\n"


class ClassifyTests(unittest.TestCase):
    def test_opt_out_beats_other_signals(self):
        self.assertEqual(outreach.classify_reply("Not interested in a call, but unsubscribe me"), "opt_out")

    def test_decline(self):
        self.assertEqual(outreach.classify_reply("Not interested, thanks"), "decline")

    def test_referral(self):
        self.assertEqual(outreach.classify_reply("Talk to Jane Doe, she owns this"), "referral")

    def test_not_now(self):
        self.assertEqual(outreach.classify_reply("Not now, check back in Q3"), "not_now")

    def test_objection(self):
        self.assertEqual(outreach.classify_reply("We already use a competitor"), "objection")

    def test_positive(self):
        self.assertEqual(outreach.classify_reply("Sounds good, let's talk Tuesday"), "positive")

    def test_not_now_wins_over_positive_word(self):
        self.assertEqual(outreach.classify_reply("Interested, but not now"), "not_now")

    def test_unclear_goes_to_human(self):
        self.assertEqual(outreach.classify_reply("Ok"), "needs_human")


class LintTests(unittest.TestCase):
    def lint(self, text, step="first", company="Acme"):
        return outreach.lint_text(text, step, CFG, company)

    def test_good_first_email_passes(self):
        findings, blocked = self.lint(footer_render(GOOD_FIRST))
        self.assertFalse(blocked, findings)

    def test_html_blocks(self):
        _, blocked = self.lint(footer_render(GOOD_FIRST.replace("Hi Jane,", "<p>Hi Jane,</p>")))
        self.assertTrue(blocked)

    def test_link_in_first_email_blocks(self):
        _, blocked = self.lint(footer_render(GOOD_FIRST.replace("Acme's pricing page", "https://acme.example/pricing")))
        self.assertTrue(blocked)

    def test_missing_postal_address_blocks(self):
        text = GOOD_FIRST + "\n--\nSam Example\nReply 'unsubscribe' to opt out.\n"
        findings, blocked = self.lint(text)
        self.assertTrue(blocked)
        self.assertIn("can-spam-address", [r for _, r, _ in findings])

    def test_missing_opt_out_blocks(self):
        text = GOOD_FIRST + f"\n--\nSam Example\n{CFG['sender']['postal_address']}\n"
        findings, blocked = self.lint(text)
        self.assertTrue(blocked)
        self.assertIn("can-spam-optout", [r for _, r, _ in findings])

    def test_banned_phrase_blocks(self):
        _, blocked = self.lint(footer_render(GOOD_FIRST.replace("usually", "usually leverage")))
        self.assertTrue(blocked)

    def test_two_questions_warn_but_do_not_block(self):
        findings, blocked = self.lint(footer_render(GOOD_FIRST.replace("yet?", "yet? Worth a look?")))
        self.assertFalse(blocked)
        self.assertIn("cta", [r for _, r, _ in findings])

    def test_missing_company_blocks(self):
        _, blocked = self.lint(footer_render(GOOD_FIRST), company="Initech")
        self.assertTrue(blocked)

    def test_long_subject_blocks(self):
        _, blocked = self.lint(footer_render(GOOD_FIRST.replace("pricing after the limit", "a very long subject line here")))
        self.assertTrue(blocked)


class PrepareTests(unittest.TestCase):
    def row(self, **kw):
        base = {"email": "jane@acme.example", "first_name": "Jane", "last_name": "", "company": "Acme",
                "title": "Head of Sales", "country": "US", "employees": "120", "website": "",
                "signal": "x", "lawful_basis_ref": ""}
        base.update(kw)
        return base

    def test_full_score(self):
        self.assertEqual(outreach.score_prospect(self.row(), CFG, {}), (100, ""))

    def test_suppressed_is_rejected(self):
        _, reason = outreach.score_prospect(self.row(), CFG, {"jane@acme.example": "opt_out"})
        self.assertEqual(reason, "suppressed:opt_out")

    def test_role_mailbox_is_rejected(self):
        _, reason = outreach.score_prospect(self.row(email="info@acme.example"), CFG, {})
        self.assertEqual(reason, "role_mailbox")

    def test_basis_required_without_record_is_rejected(self):
        _, reason = outreach.score_prospect(self.row(country="DE"), CFG, {})
        self.assertEqual(reason, "no_lawful_basis_on_file")

    def test_basis_required_with_record_passes(self):
        score, reason = outreach.score_prospect(self.row(country="DE", lawful_basis_ref="CR-101"), CFG, {})
        self.assertEqual(reason, "")

    def test_title_mismatch_is_rejected(self):
        _, reason = outreach.score_prospect(self.row(title="Marketing Director"), CFG, {})
        self.assertEqual(reason, "title_mismatch")

    def test_size_out_of_range_is_rejected(self):
        _, reason = outreach.score_prospect(self.row(employees="900"), CFG, {})
        self.assertEqual(reason, "size_out_of_range")


class PlanTests(unittest.TestCase):
    TODAY = dt.date(2026, 1, 5)

    def people(self, n):
        return {f"p{i}@co{i}.example": {"email": f"p{i}@co{i}.example", "company": f"Co{i}"} for i in range(n)}

    def test_day_one_respects_mailbox_cap(self):
        people = self.people(12)
        queue = outreach.build_queue(list(people.values()), [], CFG["sequence"], set(), self.TODAY)
        rows, pending = outreach.build_plan(queue, people, CFG["sequence"], CFG["mailboxes"],
                                            CFG["warmup"], self.TODAY, horizon=1)
        self.assertEqual(len(rows), 10)  # 2 mailboxes x week-0 cap of 5
        per_box = {m: sum(1 for r in rows if r["mailbox"] == m) for m in CFG["mailboxes"]}
        self.assertEqual(set(per_box.values()), {5})
        self.assertEqual(len(pending), 2)  # the two prospects over today's cap wait for tomorrow

    def test_follow_up_not_planned_before_first_is_sent(self):
        people = {"a@x.example": {"email": "a@x.example", "company": "X"}}
        queue = outreach.build_queue(list(people.values()), [], CFG["sequence"], set(), self.TODAY)
        rows, _ = outreach.build_plan(queue, people, CFG["sequence"], CFG["mailboxes"], CFG["warmup"], self.TODAY, 7)
        self.assertEqual([r["step"] for r in rows], ["first"])

    def test_cap_ramps_weekly_then_holds(self):
        warm = CFG["warmup"]
        self.assertEqual(outreach.cap_for_day(dt.date(2026, 1, 5), warm), 5)
        self.assertEqual(outreach.cap_for_day(dt.date(2026, 1, 12), warm), 10)
        self.assertEqual(outreach.cap_for_day(dt.date(2026, 6, 1), warm), 30)

    def test_due_follow_up_is_scheduled(self):
        people = {"a@x.example": {"email": "a@x.example", "company": "X"}}
        tracking = [{"date": "2026-01-02", "email": "a@x.example", "event": "sent", "step": "first", "category": ""}]
        queue = outreach.build_queue(list(people.values()), tracking, CFG["sequence"], set(), self.TODAY)
        rows, _ = outreach.build_plan(queue, people, CFG["sequence"], CFG["mailboxes"], CFG["warmup"], self.TODAY, 1)
        self.assertEqual([(r["email"], r["step"]) for r in rows], [("a@x.example", "follow_up")])

    def test_replied_prospect_is_excluded(self):
        people = {"a@x.example": {"email": "a@x.example", "company": "X"}}
        tracking = [
            {"date": "2026-01-02", "email": "a@x.example", "event": "sent", "step": "first", "category": ""},
            {"date": "2026-01-03", "email": "a@x.example", "event": "reply", "step": "", "category": "not_now"},
        ]
        excluded = outreach.excluded_emails(tracking, {})
        queue = outreach.build_queue(list(people.values()), tracking, CFG["sequence"], excluded, self.TODAY)
        self.assertEqual(queue, [])

    def test_bounced_prospect_is_excluded(self):
        tracking = [{"date": "2026-01-02", "email": "a@x.example", "event": "bounced", "step": "", "category": ""}]
        self.assertIn("a@x.example", outreach.excluded_emails(tracking, {}))


if __name__ == "__main__":
    unittest.main()
