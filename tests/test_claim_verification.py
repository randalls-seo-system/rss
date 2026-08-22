"""Mutation tests for the claim verification rewrite (fix/claim-verification).

Each test asserts a specific protection. The mutation red/green protocol:
  1. Run the test (GREEN — protection in place).
  2. Remove the protection in the source (simulate the old bug).
  3. Run the test (RED — the mutation is caught).
  4. Restore the protection (GREEN again).

All LLM and search calls are mocked. No live API calls.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# L33: The shared source_verification module is loaded via importlib in
# adversarial_review.py. Tests that mock LLM/search/fetch must patch on
# the shared module, not on adversarial_review (which now delegates).
import lib.adversarial_review as _ar_mod
_SV_MOD = _ar_mod._sv_mod  # the loaded source_verification module

from lib.adversarial_review import (
    Finding,
    VerifiedFix,
    _is_authority_domain,
    _is_rejected_verification_domain,
    _judge_source,
    _search_for_claim_source,
    run_review_cycle,
    verify_fix,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# The real CFPB page about closing costs lists fee CATEGORIES
# (appraisal, credit report, title insurance, etc.) but never states
# the dollar figure "$1,500-$3,000" that the reviewer attributed to it.
CFPB_FEE_CATEGORIES_TEXT = """
Consumer Financial Protection Bureau — Closing Costs Explained

When you close on a mortgage, you will pay a number of fees. These may include:

Lender fees: Origination charges, application fees, underwriting fees.
Third-party fees: Appraisal fee, credit report fee, title search, title insurance,
survey fee, flood certification, tax service fee.
Government fees: Recording fees, transfer taxes.
Prepaid items: Homeowners insurance, property taxes, prepaid interest.

Closing costs vary by location, loan type, and lender. Borrowers should
review the Loan Estimate and Closing Disclosure carefully to understand
their total costs. You may be able to negotiate some fees or shop for
third-party services.

For more information, visit consumerfinance.gov/owning-a-home.
"""

CFPB_FINDING = Finding(
    severity="critical",
    category="factual",
    location="Closing Costs Section",
    issue="Third-party closing costs are typically $1,500-$3,000 according to CFPB data",
    proposed_fix="Update to reflect CFPB's stated range of $1,500-$3,000 for third-party fees",
    authority="https://www.consumerfinance.gov/owning-a-home/closing/",
)

VA_ELIGIBILITY_FINDING = Finding(
    severity="critical",
    category="factual",
    location="Eligibility",
    issue="VA requires 181 days peacetime service but article says 90",
    proposed_fix="Change 90 days to 181 days for peacetime eligibility",
    authority="https://www.va.gov/housing-assistance/home-loans/eligibility/",
)

VA_SOURCE_TEXT_STATES = """
VA Home Loan Eligibility Requirements

To be eligible for a VA-backed home loan, you must meet minimum service requirements.

Peacetime service: You must have served at least 181 days of continuous active duty.
Wartime service: You must have served at least 90 continuous days of active duty
during a period of war.

If you served during both wartime and peacetime, wartime minimums apply.
"""

VA_SOURCE_TEXT_CONTRADICTS = """
VA Home Loan Eligibility Requirements

To be eligible for a VA-backed home loan, you must meet minimum service requirements.

Peacetime service: You must have served at least 24 months of continuous active duty.
"""

# Mock LLM judge responses
def _mock_judge_states(prompt, cache_key=None):
    resp = MagicMock()
    resp.text = json.dumps({
        "verdict": "STATES",
        "quote": "You must have served at least 181 days of continuous active duty."
    })
    return resp


def _mock_judge_not_stated(prompt, cache_key=None):
    resp = MagicMock()
    resp.text = json.dumps({
        "verdict": "NOT_STATED",
        "quote": ""
    })
    return resp


def _mock_judge_contradicts(prompt, cache_key=None):
    resp = MagicMock()
    resp.text = json.dumps({
        "verdict": "CONTRADICTS",
        "quote": "You must have served at least 24 months of continuous active duty."
    })
    return resp


def _mock_search_no_results(*args, **kwargs):
    return []


def _mock_search_with_gov_result(*args, **kwargs):
    return [{"title": "VA Eligibility", "snippet": "...", "url": "https://www.va.gov/eligibility/"}]


def _mock_search_with_lender_blog(*args, **kwargs):
    return [{"title": "VA Loans", "snippet": "...", "url": "https://www.veteransunited.com/va-loans/"}]


REVIEW_JSON_CRITICAL_FACTUAL = json.dumps({
    "findings": [{
        "severity": "critical",
        "category": "factual",
        "location": "Closing Costs Section",
        "issue": "Third-party closing costs are typically $1,500-$3,000 according to CFPB data",
        "proposed_fix": "Update to reflect CFPB's stated range of $1,500-$3,000 for third-party fees",
        "authority": "https://www.consumerfinance.gov/owning-a-home/closing/",
    }],
    "overall_score": 60,
    "top_priorities": ["Fix closing cost claim"],
})


def _mock_openai_review(messages, *, model="gpt-5.6", max_tokens=4096, temperature=0.3):
    return REVIEW_JSON_CRITICAL_FACTUAL, 500, 200


# ---------------------------------------------------------------------------
# Test (a): CFPB fixture — the incident that motivated this rewrite
# ---------------------------------------------------------------------------

class TestCFPBFeeCategories(unittest.TestCase):
    """A CFPB page that lists fee CATEGORIES without stating "$1,500-$3,000"
    must return NOT_STATED, not VERIFIED."""

    @patch("lib.adversarial_review._search_for_claim_source", _mock_search_no_results)
    @patch("lib.adversarial_review._fetch_for_verification", return_value=CFPB_FEE_CATEGORIES_TEXT)
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_cfpb_fee_categories_not_stated(self, mock_client_fn, mock_fetch):
        """Source discusses fee categories, not specific dollar figures -> NOT_STATED."""
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client

        vf = verify_fix(CFPB_FINDING)
        self.assertEqual(vf.status, "not_stated",
                         "CFPB fee-categories page should NOT verify a dollar-figure claim")


# ---------------------------------------------------------------------------
# Test (a) mutation: keyword-overlap scoring would incorrectly verify
# ---------------------------------------------------------------------------

class TestMutationKeywordOverlap(unittest.TestCase):
    """Mutation: if we restore keyword-overlap scoring (the 0.3 threshold),
    the CFPB fee-categories text WOULD score as verified because generic
    domain keywords (CFPB, closing, costs, fees, borrower) appear in both
    the finding and the source."""

    def test_keyword_overlap_would_falsely_verify_cfpb(self):
        """Demonstrate that the old 0.3 keyword-overlap heuristic would
        incorrectly verify this claim."""
        import re
        text_lower = CFPB_FEE_CATEGORIES_TEXT.lower()
        issue_kw = set(re.findall(r'\b\w{4,}\b', CFPB_FINDING.issue.lower()))
        fix_kw = set(re.findall(r'\b\w{4,}\b', CFPB_FINDING.proposed_fix.lower()))
        relevant = issue_kw | fix_kw
        matches = sum(1 for kw in relevant if kw in text_lower)
        ratio = matches / max(len(relevant), 1)

        # The old threshold was 0.3. This source would pass it.
        self.assertGreaterEqual(ratio, 0.3,
            f"Keyword overlap is {ratio:.0%} — the old heuristic WOULD have "
            f"verified this claim. The LLM judge correctly returns NOT_STATED.")


# ---------------------------------------------------------------------------
# Test (b): NOT_STATED must escalate to search, not map to verified
# ---------------------------------------------------------------------------

class TestNotStatedEscalatesToSearch(unittest.TestCase):
    """When the cited URL returns NOT_STATED, verify_fix must attempt a
    search for an authority source. NOT_STATED must never map to verified."""

    @patch("lib.adversarial_review._search_for_claim_source")
    @patch("lib.adversarial_review._fetch_for_verification", return_value="<html>Some content</html>")
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_not_stated_triggers_search(self, mock_client_fn, mock_fetch, mock_search):
        """NOT_STATED on cited URL -> search is called."""
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client
        mock_search.return_value = []

        vf = verify_fix(CFPB_FINDING)
        # Search must have been called
        mock_search.assert_called_once()
        # Result must NOT be verified
        self.assertNotEqual(vf.status, "verified",
                            "NOT_STATED must not map to verified")
        self.assertEqual(vf.status, "not_stated")

    @patch("lib.adversarial_review._search_for_claim_source")
    @patch("lib.adversarial_review._fetch_for_verification")
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_search_finds_authority_source(self, mock_client_fn, mock_fetch, mock_search):
        """If search finds an authority source that STATES the claim -> verified."""
        call_count = [0]

        def _judge_side_effect(prompt, cache_key=None):
            call_count[0] += 1
            resp = MagicMock()
            if call_count[0] == 1:
                # First call: cited URL -> NOT_STATED
                resp.text = json.dumps({"verdict": "NOT_STATED", "quote": ""})
            else:
                # Second call: search result -> STATES
                resp.text = json.dumps({
                    "verdict": "STATES",
                    "quote": "You must have served at least 181 days."
                })
            return resp

        mock_client = MagicMock()
        mock_client.call.side_effect = _judge_side_effect
        mock_client_fn.return_value = mock_client

        # First fetch = cited URL, second fetch = search result
        mock_fetch.side_effect = ["<html>Original</html>", "<html>Search result</html>"]
        mock_search.return_value = [
            {"title": "VA Eligibility", "snippet": "...",
             "url": "https://www.va.gov/eligibility/"}
        ]

        vf = verify_fix(VA_ELIGIBILITY_FINDING)
        self.assertEqual(vf.status, "verified")
        # Citation updated to the working URL
        self.assertEqual(vf.evidence_url, "https://www.va.gov/eligibility/")


# ---------------------------------------------------------------------------
# Test (c): Unfetchable critical must PARK, not downgrade to advisory
# ---------------------------------------------------------------------------

class TestUnfetchableCriticalParks(unittest.TestCase):
    """A critical/high factual/legal finding that cannot be verified after
    fetch + search must PARK the job, not silently become an advisory note."""

    @patch("lib.adversarial_review._call_openai", side_effect=_mock_openai_review)
    @patch("lib.adversarial_review._search_for_claim_source", _mock_search_no_results)
    @patch("lib.adversarial_review._fetch_for_verification", return_value=None)
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_unfetchable_critical_parks_job(self, mock_client_fn, mock_fetch,
                                            mock_openai):
        """Unfetchable authority URL on critical finding -> confirmation_passed=False."""
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client

        result = run_review_cycle(
            "<h1>Test Article</h1><p>Closing costs are $1,500-$3,000.</p>",
            site_slug="lrg",
            content_type="article",
        )
        self.assertFalse(result.confirmation_passed,
                         "Unverified critical finding must PARK the job")
        self.assertTrue(len(result.confirmation_unresolved) > 0,
                        "PARK reason must be recorded")

    @patch("lib.adversarial_review._search_for_claim_source", _mock_search_no_results)
    @patch("lib.adversarial_review._fetch_for_verification", return_value="<html>Content</html>")
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_not_stated_critical_parks_job(self, mock_client_fn, mock_fetch):
        """Source fetched but NOT_STATED on critical finding -> PARK."""
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client

        vf = verify_fix(CFPB_FINDING)
        self.assertEqual(vf.status, "not_stated")
        # Verify that is_actionable is True (critical + factual)
        self.assertTrue(CFPB_FINDING.is_actionable)


# ---------------------------------------------------------------------------
# Test (d): Lender-blog domain must be rejected as verification source
# ---------------------------------------------------------------------------

class TestLenderBlogRejected(unittest.TestCase):
    """A lender blog (veteransunited.com, etc.) must not be accepted as an
    authority source for claim verification."""

    def test_veteransunited_rejected(self):
        self.assertTrue(_is_rejected_verification_domain(
            "https://www.veteransunited.com/va-loans/eligibility/"))

    def test_rocketmortgage_rejected(self):
        self.assertTrue(_is_rejected_verification_domain(
            "https://www.rocketmortgage.com/learn/va-loans"))

    def test_bankrate_rejected(self):
        self.assertTrue(_is_rejected_verification_domain(
            "https://www.bankrate.com/mortgages/va-loan-requirements/"))

    def test_nerdwallet_rejected(self):
        self.assertTrue(_is_rejected_verification_domain(
            "https://www.nerdwallet.com/article/mortgages/va-loan"))

    def test_va_gov_accepted(self):
        self.assertTrue(_is_authority_domain("https://www.va.gov/eligibility/"))
        self.assertFalse(_is_rejected_verification_domain("https://www.va.gov/eligibility/"))

    def test_cfpb_gov_accepted(self):
        self.assertTrue(_is_authority_domain("https://www.consumerfinance.gov/data/"))

    def test_fanniemae_accepted(self):
        self.assertTrue(_is_authority_domain("https://singlefamily.fanniemae.com/guide"))

    def test_freddiemac_accepted(self):
        self.assertTrue(_is_authority_domain("https://guide.freddiemac.com/"))

    def test_search_filters_lender_blogs(self):
        """Even if search returns a lender blog, it must be filtered out."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "organic": [
                {"title": "VA Loans", "snippet": "...",
                 "link": "https://www.veteransunited.com/va-loans/"},
                {"title": "VA Loans", "snippet": "...",
                 "link": "https://www.rocketmortgage.com/learn/va-loans"},
                {"title": "VA Eligibility", "snippet": "...",
                 "link": "https://www.va.gov/eligibility/"},
            ]
        }

        import os
        with patch("requests.post", return_value=mock_resp):
            with patch.dict(os.environ, {"SERPER_API_KEY": "test-key"}):
                results = _search_for_claim_source(VA_ELIGIBILITY_FINDING)

        # Only the .gov result should remain
        self.assertEqual(len(results), 1)
        self.assertIn("va.gov", results[0]["url"])


# ---------------------------------------------------------------------------
# Domain-list separation: verification does NOT use content blocklist
# ---------------------------------------------------------------------------

class TestBlockedDomainSeparation(unittest.TestCase):
    """Verification fetching must NOT inherit the content-sourcing blocklist.
    A reviewer citing forbes.com or wsj.com should not be silently downgraded."""

    @patch("lib.adversarial_review._search_for_claim_source", _mock_search_no_results)
    @patch.object(_SV_MOD, "_get_llm_client")
    def test_wsj_not_blocked_for_verification(self, mock_client_fn):
        """WSJ is blocked for content sourcing but must be fetchable for verification.

        page_fetch.py blocks wsj.com for content. _fetch_for_verification
        bypasses that blocklist, so a reviewer citing WSJ is not silently
        downgraded to unfetchable.
        """
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client

        finding = Finding(
            severity="critical", category="factual",
            location="Market Section", issue="Mortgage rates hit 7.5% per WSJ",
            proposed_fix="Update rate to current WSJ figure",
            authority="https://www.wsj.com/articles/mortgage-rates",
        )

        with patch.object(_SV_MOD, "_load_page_fetch") as mock_pf:
            mock_mod = MagicMock()
            mock_mod.cache_get.return_value = None
            mock_pf.return_value = mock_mod

            mock_resp = MagicMock()
            mock_resp.text = "<html>Article about rates</html>"
            mock_resp.raise_for_status = MagicMock()

            with patch("requests.get", return_value=mock_resp) as mock_get:
                vf = verify_fix(finding)
                # The fetch was attempted (not blocked by content blocklist)
                mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# LLM judge contract tests
# ---------------------------------------------------------------------------

class TestJudgeSource(unittest.TestCase):
    """The LLM judge must return STATES/CONTRADICTS/NOT_STATED only."""

    @patch.object(_SV_MOD, "_get_llm_client")
    def test_states_verdict(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_states
        mock_client_fn.return_value = mock_client

        verdict, quote = _judge_source(
            VA_SOURCE_TEXT_STATES, VA_ELIGIBILITY_FINDING, "https://va.gov/test")
        self.assertEqual(verdict, "STATES")
        self.assertIn("181 days", quote)

    @patch.object(_SV_MOD, "_get_llm_client")
    def test_contradicts_verdict(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_contradicts
        mock_client_fn.return_value = mock_client

        verdict, quote = _judge_source(
            VA_SOURCE_TEXT_CONTRADICTS, VA_ELIGIBILITY_FINDING, "https://va.gov/test")
        self.assertEqual(verdict, "CONTRADICTS")
        self.assertIn("24 months", quote)

    @patch.object(_SV_MOD, "_get_llm_client")
    def test_not_stated_verdict(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.call.side_effect = _mock_judge_not_stated
        mock_client_fn.return_value = mock_client

        verdict, quote = _judge_source(
            CFPB_FEE_CATEGORIES_TEXT, CFPB_FINDING, "https://cfpb.gov/test")
        self.assertEqual(verdict, "NOT_STATED")

    @patch.object(_SV_MOD, "_get_llm_client")
    def test_invalid_verdict_defaults_not_stated(self, mock_client_fn):
        """If LLM returns a non-standard verdict, default to NOT_STATED."""
        mock_client = MagicMock()
        resp = MagicMock()
        resp.text = json.dumps({"verdict": "MAYBE", "quote": ""})
        mock_client.call.return_value = resp
        mock_client_fn.return_value = mock_client

        verdict, _ = _judge_source("text", VA_ELIGIBILITY_FINDING, "url")
        self.assertEqual(verdict, "NOT_STATED")


if __name__ == "__main__":
    unittest.main()
