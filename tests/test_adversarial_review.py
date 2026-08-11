"""Tests for lib/adversarial_review.py — mocked OpenAI throughout."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.adversarial_review import (
    Finding,
    ReviewReport,
    TriageResult,
    VerifiedFix,
    _parse_review_json,
    apply_verified_fixes,
    run_review,
    run_review_cycle,
    triage_findings,
    verify_fix,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLEAN_REVIEW_JSON = json.dumps({
    "findings": [
        {
            "severity": "critical",
            "category": "factual",
            "location": "VA Loan Eligibility",
            "issue": "Article states 90 days active duty required; actual minimum is 90 continuous days for wartime, 181 days for peacetime",
            "proposed_fix": "Specify both wartime (90 days) and peacetime (181 days) minimums",
            "authority": "https://www.va.gov/housing-assistance/home-loans/eligibility/"
        },
        {
            "severity": "high",
            "category": "legal",
            "location": "Funding Fee Section",
            "issue": "Missing exemption for Veterans with service-connected disability",
            "proposed_fix": "Add: Veterans with service-connected disability rating are exempt from the VA funding fee",
            "authority": "https://www.va.gov/housing-assistance/home-loans/funding-fee/"
        },
        {
            "severity": "medium",
            "category": "structural",
            "location": "Introduction",
            "issue": "No clear thesis statement in opening paragraph",
            "proposed_fix": "Add a one-sentence thesis after the lede",
            "authority": None
        },
        {
            "severity": "low",
            "category": "editorial",
            "location": "Closing section",
            "issue": "Could use stronger call to action",
            "proposed_fix": "Rewrite CTA to be more specific",
            "authority": None
        },
    ],
    "overall_score": 72,
    "top_priorities": [
        "Fix active duty eligibility requirement (critical)",
        "Add funding fee exemption for disabled Veterans",
    ]
})

MALFORMED_RESPONSE = "Here are my findings:\n- Issue 1\n- Issue 2\nNo JSON here."

CONFIRMATION_RESOLVED = json.dumps({
    "resolved": ["Fix active duty eligibility requirement", "Add funding fee exemption"],
    "unresolved": []
})

CONFIRMATION_UNRESOLVED = json.dumps({
    "resolved": ["Add funding fee exemption"],
    "unresolved": ["Active duty requirement still incorrect"]
})


def _mock_call_openai(messages, *, model="gpt-5.6", max_tokens=4096, temperature=0.3):
    """Return predetermined responses based on message content."""
    user_msg = messages[-1]["content"] if messages else ""

    if "Your response was not valid JSON" in user_msg:
        return CLEAN_REVIEW_JSON, 500, 200

    if "whether specific critical/high findings were resolved" in (messages[0]["content"] if messages else ""):
        return CONFIRMATION_RESOLVED, 300, 100

    if "Apply these fixes" in user_msg:
        return "<h1>Revised Article</h1><p>Fixed content with correct eligibility.</p>", 1000, 500

    return CLEAN_REVIEW_JSON, 1000, 400


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseReviewJson(unittest.TestCase):

    def test_clean_json(self):
        data = _parse_review_json(CLEAN_REVIEW_JSON)
        self.assertEqual(len(data["findings"]), 4)
        self.assertEqual(data["overall_score"], 72)

    def test_fenced_json(self):
        fenced = f"```json\n{CLEAN_REVIEW_JSON}\n```"
        data = _parse_review_json(fenced)
        self.assertEqual(len(data["findings"]), 4)

    def test_malformed_raises(self):
        with self.assertRaises(ValueError):
            _parse_review_json(MALFORMED_RESPONSE)


class TestTriageFindings(unittest.TestCase):

    def test_routes_severities_correctly(self):
        findings = [
            Finding("critical", "factual", "H2", "Wrong rate", "Fix rate", "https://x.com"),
            Finding("high", "legal", "H3", "Missing disclosure", "Add it", "https://y.com"),
            Finding("medium", "structural", "Intro", "Weak thesis", "Rewrite", None),
            Finding("low", "editorial", "CTA", "Weak CTA", "Rewrite", None),
        ]
        result = triage_findings(findings)
        self.assertEqual(len(result.fix_queue), 2)  # critical/factual + high/legal
        self.assertEqual(len(result.advisory), 2)  # medium + low
        self.assertEqual(result.fix_queue[0].severity, "critical")
        self.assertEqual(result.fix_queue[1].severity, "high")

    def test_high_editorial_goes_to_advisory(self):
        """high/editorial is NOT actionable — only factual/legal are."""
        findings = [
            Finding("high", "editorial", "Body", "Awkward phrasing", "Rewrite", None),
        ]
        result = triage_findings(findings)
        self.assertEqual(len(result.fix_queue), 0)
        self.assertEqual(len(result.advisory), 1)


class TestVerifyFix(unittest.TestCase):

    def test_subtractive_no_auth_applied(self):
        """Subtractive fix without authority → applied (safe)."""
        f = Finding("critical", "factual", "Body", "Unsupported figure",
                    "Remove the 15% claim", None)
        vf = verify_fix(f)
        self.assertEqual(vf.status, "subtractive_no_auth")

    def test_additive_no_auth_disputed(self):
        """Additive fix without authority → advisory, not applied."""
        f = Finding("critical", "factual", "Body", "Missing context",
                    "Add that Texas requires 180-day residency", None)
        vf = verify_fix(f)
        self.assertEqual(vf.status, "disputed")
        self.assertIn("No authority", vf.evidence_text)


class TestRunReview(unittest.TestCase):

    @patch("lib.adversarial_review._call_openai", side_effect=_mock_call_openai)
    def test_returns_parsed_findings(self, mock_call):
        report = run_review(
            "<h1>Test</h1><p>Content.</p>",
            site_slug="lrg",
            target_keyword="va loan eligibility",
        )
        self.assertEqual(len(report.findings), 4)
        self.assertEqual(report.overall_score, 72)
        self.assertGreater(report.cost_estimate, 0)

    @patch("lib.adversarial_review._call_openai")
    def test_malformed_retry_then_fail(self, mock_call):
        """Malformed JSON → one retry → then loud fail."""
        mock_call.return_value = (MALFORMED_RESPONSE, 500, 200)
        with self.assertRaises(RuntimeError) as ctx:
            run_review("<h1>Test</h1>", site_slug="lrg")
        self.assertIn("malformed JSON", str(ctx.exception))
        self.assertEqual(mock_call.call_count, 2)  # original + retry

    @patch("lib.adversarial_review._call_openai")
    def test_malformed_then_valid_retry(self, mock_call):
        """Malformed first, valid retry."""
        mock_call.side_effect = [
            (MALFORMED_RESPONSE, 500, 200),
            (CLEAN_REVIEW_JSON, 500, 200),
        ]
        report = run_review("<h1>Test</h1>", site_slug="lrg")
        self.assertEqual(len(report.findings), 4)


class TestBoundedCycle(unittest.TestCase):

    @patch("lib.adversarial_review._call_openai", side_effect=_mock_call_openai)
    @patch("lib.adversarial_review.verify_fix")
    def test_cycle_caps_at_one_revision(self, mock_verify, mock_call):
        """Assert exactly 2 review calls (initial + confirmation), never more.
        Mock a never-satisfied reviewer — assert exactly 2 review calls."""
        mock_verify.return_value = VerifiedFix(
            finding=Finding("critical", "factual", "Body", "Wrong",
                            "Remove the claim", None),
            status="subtractive_no_auth",
        )
        html = "<h1>Test Article</h1><p>VA loans require 90 days active duty.</p>"
        result = run_review_cycle(
            html,
            site_slug="lrg",
            content_type="article",
            target_keyword="va loan",
        )
        # 2 review calls: initial review + confirmation review
        self.assertEqual(result.review_calls, 2)

    @patch("lib.adversarial_review._call_openai")
    def test_disputed_fix_not_applied(self, mock_call):
        """When fetched source contradicts reviewer → advisory, not applied."""
        # Reviewer claims X, but verify_fix returns disputed
        review_json = json.dumps({
            "findings": [{
                "severity": "critical",
                "category": "factual",
                "location": "Tax Section",
                "issue": "Property tax rate is wrong",
                "proposed_fix": "Change rate to 2.5%",
                "authority": "https://example.com/tax-rates"
            }],
            "overall_score": 60,
            "top_priorities": ["Fix tax rate"]
        })
        mock_call.return_value = (review_json, 500, 200)

        with patch("lib.adversarial_review.verify_fix") as mock_verify:
            mock_verify.return_value = VerifiedFix(
                finding=Finding("critical", "factual", "Tax Section",
                                "Property tax rate is wrong",
                                "Change rate to 2.5%",
                                "https://example.com/tax-rates"),
                status="disputed",
                evidence_url="https://example.com/tax-rates",
                evidence_text="Source says rate is 2.1%, not 2.5%",
            )
            result = run_review_cycle(
                "<h1>Test</h1><p>Tax rate is 2.1%.</p>",
                site_slug="lrg",
            )
            # Fix was disputed — should NOT be in applied fixes with verified status
            verified_applied = [f for f in result.fixes_applied
                                if f.status in ("verified", "subtractive_no_auth")]
            self.assertEqual(len(verified_applied), 0)

    @patch("lib.adversarial_review._call_openai", side_effect=_mock_call_openai)
    def test_advisory_file_written(self, mock_call):
        """Advisory findings go to advisory file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_review_cycle(
                "<h1>Test</h1><p>Content.</p>",
                site_slug="lrg",
                job_dir=Path(tmpdir),
                post_id=9999,
            )
            advisory_path = Path(tmpdir) / "9999-review-advisory.md"
            self.assertTrue(advisory_path.exists())
            text = advisory_path.read_text()
            self.assertIn("structural", text.lower())

    @patch("lib.adversarial_review._call_openai", side_effect=_mock_call_openai)
    def test_gates_rerun_on_revised(self, mock_call):
        """Revised artifact re-runs gates (verified by gate import in cycle)."""
        # The cycle calls run_universal_gates on the revised HTML
        # We verify it doesn't crash (gate library is imported via importlib)
        result = run_review_cycle(
            "<h1>Test Article Title Long Enough</h1><p>Content here. " * 100 + "</p>",
            site_slug="lrg",
            content_type="article",
        )
        # If gates ran without import error, the test passes
        self.assertIsNotNone(result.revised_html)


class TestFailurePaths(unittest.TestCase):
    """Explicit tests for the two failure handling paths per Randall's fix."""

    @patch("lib.adversarial_review._call_openai")
    def test_infrastructure_failure_is_nonblocking(self, mock_call):
        """OpenAI down / malformed JSON after retry → RuntimeError raised.
        The PIPELINE handles this as non-blocking (try/except in rss CLI)."""
        mock_call.return_value = ("not json at all {broken", 500, 200)
        with self.assertRaises(RuntimeError) as ctx:
            run_review("<h1>Test</h1>", site_slug="lrg")
        self.assertIn("malformed JSON", str(ctx.exception))

    @patch("lib.adversarial_review._call_openai")
    @patch("lib.adversarial_review.verify_fix")
    def test_unresolved_criticals_mark_not_passed(self, mock_verify, mock_call):
        """Confirmation says critical unresolved → confirmation_passed=False.
        Pipeline must park the job (not proceed to deploy)."""
        # Mock review with a critical finding
        review_json = json.dumps({
            "findings": [{
                "severity": "critical",
                "category": "factual",
                "location": "Rate Section",
                "issue": "VA funding fee rate is incorrect",
                "proposed_fix": "Remove the incorrect rate",
                "authority": None
            }],
            "overall_score": 55,
            "top_priorities": ["Fix funding fee rate"]
        })
        confirmation_unresolved = json.dumps({
            "resolved": [],
            "unresolved": ["VA funding fee rate still incorrect after revision"]
        })

        # First call = review, second = revision, third = confirmation
        mock_call.side_effect = [
            (review_json, 500, 200),
            ("<h1>Revised</h1><p>Still wrong.</p>", 1000, 500),
            (confirmation_unresolved, 300, 100),
        ]
        mock_verify.return_value = VerifiedFix(
            finding=Finding("critical", "factual", "Rate Section",
                            "VA funding fee rate is incorrect",
                            "Remove the incorrect rate", None),
            status="subtractive_no_auth",
        )

        result = run_review_cycle(
            "<h1>Test Article</h1><p>The funding fee is 5%.</p>",
            site_slug="lrg",
            content_type="article",
        )
        # confirmation_passed must be False — pipeline parks the job
        self.assertFalse(result.confirmation_passed)
        self.assertTrue(len(result.confirmation_unresolved) > 0)
        self.assertIn("funding fee", result.confirmation_unresolved[0].lower())


if __name__ == "__main__":
    unittest.main()
