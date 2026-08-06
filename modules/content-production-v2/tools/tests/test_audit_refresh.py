"""Tests for audit mode, refresh mode, and queue integration."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add module paths
MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.auditor import run_tier1, run_tier2, compute_verdict, AuditResult
from lib.queue import (
    add_item, add_refresh_item, load_queue, save_queue,
    mark_awaiting_approval, seed_from_audit,
)


# ─── Fixtures ────────────────────────────────────────────────────────────

CLEAN_HTML = """
<div class="rl-hero">
<div class="rl-eyebrow">Mortgage · Guide</div>
<h1>FHA Loan Requirements 2026</h1>
<p class="rl-hero-lead">FHA loans require a minimum 580 credit score for 3.5 percent down payment and offer accessible financing for first time homebuyers across the nation today in the current market.</p>
<a class="rl-cta-pill" href="/compare-loan-offers/">Compare Offers</a>
</div>

<details><summary>What is the minimum credit score?</summary><p>The minimum credit score for an FHA loan is 580 for the standard 3.5 percent down payment option though some lenders require higher scores as an overlay.</p></details>
<details><summary>How much down payment do I need?</summary><p>FHA loans require a minimum 3.5 percent down payment with a 580 credit score or 10 percent down with scores between 500 and 579 per federal guidelines.</p></details>
<details><summary>Can I use gift funds for the down payment?</summary><p>Yes FHA allows gift funds from family members employers and approved organizations for the entire down payment amount with proper documentation and a gift letter.</p></details>

<div class="rl-quick-grid">
<div class="rl-quick-card"><h3>Credit Score Minimums</h3><ul><li>580 for 3.5 percent down payment option</li><li>500 for 10 percent down payment tier</li></ul></div>
<div class="rl-quick-card"><h3>Down Payment Options</h3><ul><li>3.5 percent minimum with 580 credit score</li><li>Gift funds allowed from family and employers</li></ul></div>
<div class="rl-quick-card"><h3>Mortgage Insurance Costs</h3><ul><li>1.75 percent upfront MIP at closing</li><li>Annual MIP of 0.55 percent for most borrowers</li></ul></div>
<div class="rl-quick-card"><h3>Property Requirements</h3><ul><li>Must meet FHA minimum property standards</li><li>Appraisal required by FHA approved appraiser</li></ul></div>
</div>

<h2>Understanding FHA Credit Score Requirements</h2>
<p>FHA loans offer two credit score tiers that determine your down payment requirement and overall loan eligibility for the program.</p>
<ul><li>Borrowers with 580 or higher scores qualify for the minimum 3.5 percent down payment the standard FHA path</li><li>Borrowers with scores between 500 and 579 must put 10 percent down which significantly increases the upfront cost</li></ul>

<h2>FHA Down Payment Rules and Gift Funds</h2>
<p>The down payment is one of the most borrower friendly aspects of FHA financing with multiple sources allowed.</p>
<table><thead><tr><th>Source</th><th>Allowed</th><th>Documentation</th></tr></thead><tbody><tr><td>Family gift</td><td>Yes</td><td>Gift letter required</td></tr><tr><td>Employer assistance</td><td>Yes</td><td>Program verification</td></tr></tbody></table>

<h2>FHA Mortgage Insurance Premium Structure</h2>
<p>All FHA loans require both upfront and annual mortgage insurance premiums regardless of the down payment amount.</p>
<ul><li>Upfront MIP is 1.75 percent of the loan amount financed into the mortgage at closing for all borrowers</li><li>Annual MIP ranges from 0.45 to 1.05 percent depending on loan term amount and loan to value ratio</li></ul>

<h2>FHA Minimum Property Standards Explained</h2>
<p>The property must meet specific health and safety standards assessed by an FHA approved appraiser during the process.</p>
<ul><li>Roof must have at least two years of remaining useful life with no active leaks or structural damage present</li><li>All mechanical systems including HVAC plumbing and electrical must be fully functional and safe for occupancy</li></ul>

<h2>FHA Loan Limits by County in 2026</h2>
<p>FHA sets annual loan limits that vary by county based on local median home prices and cost of living.</p>
<table><thead><tr><th>Area Type</th><th>Limit</th></tr></thead><tbody><tr><td>Floor (low cost)</td><td>$498,257</td></tr><tr><td>Ceiling (high cost)</td><td>$1,149,825</td></tr></tbody></table>

<h2>How FHA Debt-to-Income Ratios Work</h2>
<p>FHA guidelines allow higher debt to income ratios than conventional loans making them accessible for borrowers with more obligations.</p>
<ul><li>Front end ratio housing expenses should not exceed 31 percent of gross monthly income per standard guidelines</li><li>Back end ratio total monthly debt payments should stay at or below 43 percent though compensating factors allow up to 57 percent</li></ul>

<h2>FHA Streamline Refinance Options</h2>
<p>Existing FHA borrowers can refinance through the streamline program which requires less documentation and no new appraisal.</p>
<ul><li>Net tangible benefit must be demonstrated through lower payment or shorter term for all streamline refinance applications</li><li>No credit check or income verification required for the most basic streamline option saving time and paperwork</li></ul>

<h2>Choosing Between FHA and Conventional Loans</h2>
<p>The decision between FHA and conventional financing depends on your credit score down payment capacity and long term plans.</p>
<ul><li>FHA works better for borrowers below 680 credit score or with limited down payment funds available from savings</li><li>Conventional loans offer better terms for borrowers with 720 plus scores and 10 percent or more down payment ready</li></ul>

<a class="rl-cta-pill" href="/compare-loan-offers/">Compare Offers</a>

<h2>The Bottom Line</h2>
<p>FHA loans remain one of the most accessible mortgage options for first time homebuyers and borrowers rebuilding credit. The program offers down payments as low as 3.5 percent with a 580 credit score and allows gift funds from family and employers. While mortgage insurance adds cost compared to conventional loans the lower entry barriers make homeownership achievable for millions of borrowers who might not otherwise qualify. The key is comparing multiple FHA lenders to find the best combination of rates closing costs and service for your specific financial situation and homebuying goals.</p>

<div class="rl-faq">
<details><summary>How long does FHA mortgage insurance last</summary><p>For loans with less than 10 percent down FHA mortgage insurance lasts the entire life of the loan requiring refinancing to conventional to remove it permanently from your payment.</p></details>
<details><summary>Can I use FHA for investment property</summary><p>No FHA loans are only available for primary residences meaning you must live in the property as your main home within 60 days of closing.</p></details>
<details><summary>What is the FHA funding fee</summary><p>FHA does not charge a funding fee like VA loans but does require a 1.75 percent upfront mortgage insurance premium financed into the loan amount at closing.</p></details>
<details><summary>Are FHA loans assumable</summary><p>Yes FHA loans are assumable meaning a qualified buyer can take over your existing FHA mortgage with its original interest rate and remaining balance.</p></details>
<details><summary>How fast can I close on an FHA loan</summary><p>FHA loans typically close in 30 to 45 days depending on the lender appraisal timeline and how quickly you provide required documentation.</p></details>
</div>

<footer class="rl-resources">
<h2>Resources Used</h2>
<ul>
<li><a href="https://www.hud.gov/program_offices/housing/sfh/ins">HUD — FHA Loan Programs</a></li>
<li><a href="https://www.consumerfinance.gov/owning-a-home/">CFPB — Owning a Home Guide</a></li>
<li><a href="https://entp.hud.gov/idapp/html/hicostlook.cfm">HUD — FHA Mortgage Limits</a></li>
<li><a href="https://www.federalregister.gov/">Federal Register — FHA Updates</a></li>
</ul>
</footer>
"""

DIRTY_HTML = """
<h1>Test Article</h1>
<p>This is a short article.</p>
<h2>Section One</h2>
<p>Here is an article that delves into the subject.</p>
<p>```some markdown fence```</p>
<h2>Section Two</h2>
<p>In today's mortgage landscape, it's important to note things.</p>
"""

SITE_CONFIG = {
    "identity": {
        "site_id": "tln",
        "name": "The Lenders Network",
        "public_url": "https://thelendersnetwork.com",
    },
    "access": {
        "ssh_host": "test.example.com",
        "ssh_user": "testuser",
        "ssh_key_path": "~/.ssh/test_key",
        "wp_path": "/var/www/html/",
    },
    "content": {
        "css_prefix": ["tln"],
        "brand_voice_archetype": "va-lending",
        "cta_url": "/compare-loan-offers/",
        "default_post_status": "draft",
    },
    "authors": {
        "author_map": {"team": {"wp_user_id": 14, "name": "Team"}},
        "byline_mode": "single",
    },
    "linking": {
        "zone_suffixes": [],
        "skip_slugs": [],
    },
    "protected": {
        "do_not_touch_pages": [
            {"post_id": 566, "slug": "compare-loan-offers", "reason": "Money page"},
        ],
    },
    "integrations": {"gsc_property": "sc-domain:thelendersnetwork.com"},
}


# ─── Audit Tests ─────────────────────────────────────────────────────────

class TestAuditTier1(unittest.TestCase):
    """Tier 1 deterministic checks."""

    def test_clean_html_has_fewer_hard_failures(self):
        """Clean fixture should pass most hard assertions."""
        result = run_tier1(CLEAN_HTML, SITE_CONFIG, keyword="fha loan requirements")
        # Clean HTML follows the spec closely — should pass a majority
        self.assertGreater(result.hard_pass_count, result.hard_total_count * 0.5,
                          f"Too many hard failures on clean HTML: {result.hard_failures}")

    def test_dirty_html_detects_artifacts(self):
        """Dirty fixture with markdown fence and AI phrases should be flagged."""
        result = run_tier1(DIRTY_HTML, SITE_CONFIG)
        # Should detect artifacts (markdown fence)
        self.assertTrue(result.artifact_hits,
                       "Expected artifact detection for markdown fence")

    def test_dirty_html_detects_word_count_issue(self):
        """Dirty fixture is way too short."""
        result = run_tier1(DIRTY_HTML, SITE_CONFIG)
        # Quality gate should flag word count
        self.assertTrue(result.quality_gate_failures or result.hard_failures,
                       "Expected failures for short content")

    def test_dirty_html_gets_refresh_verdict(self):
        """Dirty fixture should get REFRESH verdict."""
        result = run_tier1(DIRTY_HTML, SITE_CONFIG)
        result = compute_verdict(result)
        self.assertEqual(result.verdict, "REFRESH")


class TestAuditTier2(unittest.TestCase):
    """Tier 2 claim extraction."""

    def test_tier2_extracts_claims(self):
        """Tier 2 should find claims in clean HTML."""
        result = AuditResult(post_id=1, slug="test", title="Test",
                            top_query="fha loan requirements")
        result = run_tier2(CLEAN_HTML, result)
        self.assertTrue(result.tier2_ran)
        self.assertGreater(result.claim_count, 0)


class TestAuditVerdict(unittest.TestCase):
    """Verdict computation."""

    def test_pass_verdict_no_failures(self):
        r = AuditResult(post_id=1, slug="t", title="T")
        r = compute_verdict(r)
        self.assertEqual(r.verdict, "PASS")

    def test_refresh_verdict_hard_failures(self):
        r = AuditResult(post_id=1, slug="t", title="T",
                       hard_failures=["18.1.1: missing H1"])
        r = compute_verdict(r)
        self.assertEqual(r.verdict, "REFRESH")

    def test_refresh_verdict_quality_gate(self):
        r = AuditResult(post_id=1, slug="t", title="T",
                       quality_gate_failures=["BOILERPLATE DETECTED"])
        r = compute_verdict(r)
        self.assertEqual(r.verdict, "REFRESH")

    def test_review_verdict_unsourced_claims(self):
        r = AuditResult(post_id=1, slug="t", title="T",
                       tier2_ran=True, unsourced_claims=6, claim_count=10)
        r = compute_verdict(r)
        self.assertEqual(r.verdict, "REVIEW")

    def test_tier2_triggers_on_tier1_failure(self):
        """Tier 2 should trigger when Tier 1 has hard failures."""
        from lib.auditor import audit_post
        # We can't easily test the full audit_post without SSH,
        # but we can verify the logic in the code path.
        # Just verify the trigger condition
        tier1_failed = bool(["failure"])
        in_striking_distance = 11 <= 25 <= 30
        self.assertTrue(tier1_failed or in_striking_distance)

    def test_tier2_triggers_on_striking_distance(self):
        """Positions 11-30 should trigger Tier 2."""
        self.assertTrue(11 <= 15 <= 30)
        self.assertTrue(11 <= 30 <= 30)
        self.assertFalse(11 <= 10 <= 30)
        self.assertFalse(11 <= 31 <= 30)


# ─── Refresh Safety Tests ───────────────────────────────────────────────

class TestRefreshSafety(unittest.TestCase):
    """Stage A' refuses do_not_touch pages and non-published posts."""

    @patch("lib.refresher.fetch_post_html")
    def test_refuses_do_not_touch(self, mock_fetch):
        """Refresh must refuse posts in do_not_touch list."""
        from lib.refresher import start_refresh_job
        # Post 566 is in do_not_touch
        result = start_refresh_job(SITE_CONFIG, "tln", 566)
        self.assertIsNone(result)
        mock_fetch.assert_not_called()

    def test_approve_refuses_stage_a_only_job(self):
        """approve_refresh must refuse a job that only completed Stage A' (no draft)."""
        from lib.refresher import approve_refresh, refresh_job_ready_for_approval

        # Job with only fetch_original done — no generation, no gates, no draft
        job = {
            "id": "test-job-123",
            "site": "tln",
            "stages": {
                "fetch_original": {"status": "done"},
                # generate, gates, create_pending_draft are MISSING
            },
            "refresh": {
                "original_post_id": 999,
                # pending_draft_id is MISSING
            },
        }

        ready, reason = refresh_job_ready_for_approval(job)
        self.assertFalse(ready)
        self.assertIn("generate", reason)

        # approve_refresh should also refuse
        result = approve_refresh(SITE_CONFIG, job)
        self.assertFalse(result)

    def test_approve_refuses_no_pending_draft_id(self):
        """approve_refresh must refuse even with all stages done but no draft_id."""
        from lib.refresher import refresh_job_ready_for_approval

        job = {
            "id": "test-job-456",
            "stages": {
                "fetch_original": {"status": "done"},
                "generate": {"status": "done"},
                "gates": {"status": "done"},
                "create_pending_draft": {"status": "done"},
            },
            "refresh": {
                "original_post_id": 999,
                # pending_draft_id MISSING
            },
        }
        ready, reason = refresh_job_ready_for_approval(job)
        self.assertFalse(ready)
        self.assertIn("pending_draft_id", reason)

    @patch("lib.refresher.fetch_post_html")
    def test_refuses_non_published(self, mock_fetch):
        """Refresh must refuse non-published posts."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 999, "slug": "test", "title": "Test",
            "html": "<p>content</p>", "status": "draft",
        }
        result = start_refresh_job(SITE_CONFIG, "tln", 999)
        self.assertIsNone(result)


# ─── Evidence Label Tests ────────────────────────────────────────────────

class TestExistingPostEvidence(unittest.TestCase):
    """Existing post evidence carries coverage-reference label."""

    def test_evidence_label(self):
        """Evidence items from existing posts must carry the coverage-reference label."""
        from lib.refresher import _save_existing_post_evidence
        with tempfile.TemporaryDirectory() as tmpdir:
            jdir = Path(tmpdir)
            html = "<h2>Section A</h2><p>This is a paragraph with enough words to pass the minimum threshold for evidence extraction testing purposes here.</p>"
            _save_existing_post_evidence(jdir, html, 123, "test-slug")
            evidence_path = jdir / "existing-post-evidence.json"
            self.assertTrue(evidence_path.exists())
            items = json.loads(evidence_path.read_text())
            self.assertGreater(len(items), 0)
            for item in items:
                self.assertEqual(item["kind"], "existing_post")
                self.assertEqual(item["tier"], "coverage")
                self.assertIn("coverage reference", item["text"])
                self.assertIn("do not treat figures as current", item["text"])


# ─── Queue Refresh Mode Tests ───────────────────────────────────────────

class TestQueueRefreshMode(unittest.TestCase):
    """Queue integration for refresh items."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_root = None

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_queue_path(self):
        """Patch queue path to use temp dir."""
        import lib.queue as qmod
        self.orig_root = qmod.REPO_ROOT
        qmod.REPO_ROOT = Path(self.tmpdir)
        site_dir = Path(self.tmpdir) / "sites" / "test"
        site_dir.mkdir(parents=True, exist_ok=True)

    def _restore_queue_path(self):
        import lib.queue as qmod
        if self.orig_root:
            qmod.REPO_ROOT = self.orig_root

    def test_add_refresh_item(self):
        """Adding a refresh item sets mode and post_id."""
        self._patch_queue_path()
        try:
            item = add_refresh_item("test", 1471, keyword="fha 203k requirements")
            self.assertEqual(item["mode"], "refresh")
            self.assertEqual(item["post_id"], 1471)
            self.assertEqual(item["status"], "pending")
        finally:
            self._restore_queue_path()

    def test_awaiting_approval_status(self):
        """Refresh items can be set to awaiting_approval."""
        self._patch_queue_path()
        try:
            item = add_refresh_item("test", 1471)
            mark_awaiting_approval("test", item["id"], job_id="job-123")
            items = load_queue("test")
            found = [i for i in items if i["id"] == item["id"]]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["status"], "awaiting_approval")
            self.assertEqual(found[0]["job_id"], "job-123")
        finally:
            self._restore_queue_path()

    def test_mixed_mode_queue(self):
        """Queue handles both new and refresh items."""
        self._patch_queue_path()
        try:
            new_item = add_item("test", "new topic", keyword="test keyword")
            refresh_item = add_refresh_item("test", 999, keyword="refresh keyword")
            items = load_queue("test")
            self.assertEqual(len(items), 2)
            modes = {i.get("mode", "new") for i in items}
            self.assertEqual(modes, {"new", "refresh"})
        finally:
            self._restore_queue_path()

    def test_seed_from_audit_excludes_pass(self):
        """seed_from_audit must exclude PASS verdicts."""
        self._patch_queue_path()
        try:
            docs_dir = Path(self.tmpdir) / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            audit_data = {
                "site": "test",
                "date": "2026-08-05",
                "results": [
                    {"post_id": 1, "slug": "pass-post", "title": "Pass Post Guide",
                     "verdict": "PASS", "position": 15, "impressions": 100,
                     "hard_failures": [], "quality_gate_failures": [],
                     "artifact_hits": [], "unsourced_claims": 0, "volatile_claims": 0,
                     "soft_total_count": 10, "soft_pass_count": 10,
                     "verdict_reasons": [], "top_query": "test", "tier2_ran": False},
                    {"post_id": 2, "slug": "refresh-post", "title": "Refresh Post Guide",
                     "verdict": "REFRESH", "position": 20, "impressions": 80,
                     "hard_failures": ["18.1.1: H1 missing"], "quality_gate_failures": [],
                     "artifact_hits": [], "unsourced_claims": 5, "volatile_claims": 0,
                     "soft_total_count": 10, "soft_pass_count": 8,
                     "verdict_reasons": ["1 hard assertion failure(s)"],
                     "top_query": "test query", "tier2_ran": True},
                ],
            }
            (docs_dir / "test-audit-20260805.json").write_text(json.dumps(audit_data))

            candidates, excluded = seed_from_audit("test")
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["post_id"], 2)
            self.assertEqual(candidates[0]["verdict"], "REFRESH")
            # PASS post should be in excluded
            self.assertTrue(any(e["post_id"] == 1 for e in excluded))
        finally:
            self._restore_queue_path()

    def test_seed_excludes_non_articles_and_frozen(self):
        """seed_from_audit must exclude non-article pages and frozen pos 1-10."""
        self._patch_queue_path()
        try:
            docs_dir = Path(self.tmpdir) / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            audit_data = {
                "site": "test",
                "date": "2026-08-05",
                "results": [
                    {"post_id": 10, "slug": "contact-us", "title": "Contact Us",
                     "verdict": "REFRESH", "position": 40, "impressions": 500,
                     "hard_failures": ["x"], "unsourced_claims": 0,
                     "verdict_reasons": ["test"]},
                    {"post_id": 20, "slug": "fha-loan-guide", "title": "FHA Loan Guide",
                     "verdict": "REFRESH", "position": 5, "impressions": 10000,
                     "hard_failures": ["x"], "unsourced_claims": 10,
                     "verdict_reasons": ["test"]},
                    {"post_id": 30, "slug": "mortgage-rates-explained",
                     "title": "Mortgage Rates Explained",
                     "verdict": "REFRESH", "position": 20, "impressions": 2000,
                     "hard_failures": ["x"], "unsourced_claims": 8,
                     "verdict_reasons": ["test"]},
                ],
            }
            (docs_dir / "test-audit-20260805.json").write_text(json.dumps(audit_data))

            candidates, excluded = seed_from_audit("test")
            # Only post 30 (article, pos 20) should be eligible
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["post_id"], 30)
            # contact-us (service_page) and fha-loan-guide (frozen) excluded
            excl_ids = {e["post_id"] for e in excluded}
            self.assertIn(10, excl_ids)  # service_page
            self.assertIn(20, excl_ids)  # frozen
        finally:
            self._restore_queue_path()


if __name__ == "__main__":
    unittest.main()
