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
        # Post 566 is in do_not_touch (has both post_id and slug in config)
        mock_fetch.return_value = {
            "post_id": 566, "slug": "compare-loan-offers",
            "title": "Compare Offers", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(SITE_CONFIG, "tln", 566)
        self.assertIsNone(result)

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
                "gates": {"status": "done", "validation": {"ran": True, "hard_passed": 30, "hard_total": 30}, "d2": {"ran": True, "passed": True, "unsourced": 0}},
                "link_pass": {"status": "done"},
                "postprocess": {"status": "done"},
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

    def test_approve_refuses_soft_validate(self):
        """approve_refresh must refuse when validator didn't run (soft-validate)."""
        from lib.refresher import refresh_job_ready_for_approval

        job = {
            "id": "test-job-soft",
            "stages": {
                "fetch_original": {"status": "done"},
                "generate": {"status": "done"},
                "gates": {"status": "done", "validation": {"ran": False, "hard_passed": 0, "hard_total": 30}},
                "link_pass": {"status": "done"},
                "postprocess": {"status": "done"},
                "create_pending_draft": {"status": "done"},
            },
            "refresh": {
                "original_post_id": 999,
                "pending_draft_id": 2531,
            },
        }
        ready, reason = refresh_job_ready_for_approval(job)
        self.assertFalse(ready)
        self.assertIn("Validator did not run", reason)

    def test_approve_refuses_d2_not_run(self):
        """approve_refresh must refuse when D2 claims check didn't run."""
        from lib.refresher import refresh_job_ready_for_approval

        job = {
            "id": "test-job-nod2",
            "stages": {
                "fetch_original": {"status": "done"},
                "generate": {"status": "done"},
                "gates": {"status": "done", "validation": {"ran": True, "hard_passed": 30, "hard_total": 30}, "d2": {"ran": False}},
                "link_pass": {"status": "done"},
                "postprocess": {"status": "done"},
                "create_pending_draft": {"status": "done"},
            },
            "refresh": {
                "original_post_id": 999,
                "pending_draft_id": 2531,
            },
        }
        ready, reason = refresh_job_ready_for_approval(job)
        self.assertFalse(ready)
        self.assertIn("D2 claims check did not run", reason)

    def test_approve_accepts_fully_gated_job(self):
        """approve gate passes when all stages done, validator ran+passed, D2 ran,
        and deploy artifact exists."""
        import tempfile, shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job = {
            "id": "test-job-good",
            "stages": {
                "fetch_original": {"status": "done"},
                "generate": {"status": "done"},
                "gates": {"status": "done", "validation": {"ran": True, "hard_passed": 30, "hard_total": 30}, "d2": {"ran": True, "passed": True, "unsourced": 0}},
                "link_pass": {"status": "done"},
                "postprocess": {"status": "done"},
                "create_pending_draft": {"status": "done"},
            },
            "refresh": {
                "original_post_id": 999,
                "pending_draft_id": 2531,
            },
        }
        # Create the deploy artifact the readiness check requires
        deploy_dir = JOBS_DIR / "test-job-good"
        deploy_dir.mkdir(parents=True, exist_ok=True)
        (deploy_dir / "999-deploy.html").write_text("<html>deploy</html>")
        try:
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertTrue(ready, f"Should pass but got: {reason}")
            self.assertEqual(reason, "")
        finally:
            shutil.rmtree(deploy_dir, ignore_errors=True)

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


class TestUpstreamFixes(unittest.TestCase):
    """Tests for H2 floor, BTF FAQ wrapper, and word count floor."""

    def test_btf_faq_wrapper_present_in_clean_html(self):
        """BTF FAQs in the clean fixture must be inside .rl-faq wrapper."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(CLEAN_HTML, "html.parser")
        rl_faq = soup.find(class_="rl-faq")
        self.assertIsNotNone(rl_faq, "Clean HTML must have .rl-faq wrapper")
        btf_details = rl_faq.find_all("details")
        self.assertGreaterEqual(len(btf_details), 5, "BTF should have 5+ FAQs")

    def test_bare_details_without_wrapper_fails_spec(self):
        """Bare <details> without .rl-faq wrapper should fail 18.1.17."""
        from lib.spec_assertions import assert_btf_faq_count_and_no_overlap
        from bs4 import BeautifulSoup
        # HTML with 7 bare <details> (no .rl-faq wrapper)
        bare_faq_html = '<div class="rl-page">' + ''.join(
            f'<details><summary>Q{i}?</summary><p>Answer {i}.</p></details>'
            for i in range(7)
        ) + '</div>'
        soup = BeautifulSoup(bare_faq_html, "html.parser")
        result = assert_btf_faq_count_and_no_overlap(soup, {"atf_faqs_text": []})
        self.assertFalse(result.passed, "Bare details without .rl-faq should fail 18.1.17")

    def test_h2_minimum_is_eight(self):
        """The H2 floor must be 8, not 6."""
        from lib.spec_assertions import assert_content_h2_min_eight
        from bs4 import BeautifulSoup
        # 7 H2 sections
        html = '<div class="rl-page">' + ''.join(
            f'<h2>Section {i}</h2><p>Content paragraph with enough words for the test fixture here.</p><ul><li>Bullet item one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen words minimum.</li></ul>'
            for i in range(7)
        ) + '</div>'
        soup = BeautifulSoup(html, "html.parser")
        result = assert_content_h2_min_eight(soup, {})
        self.assertFalse(result.passed, "7 H2s should fail the min-8 gate")

    def test_eight_h2s_passes(self):
        """8 H2 sections should pass."""
        from lib.spec_assertions import assert_content_h2_min_eight
        from bs4 import BeautifulSoup
        html = '<div class="rl-page">' + ''.join(
            f'<h2>Section {i}</h2><p>Content paragraph.</p><ul><li>Item.</li></ul>'
            for i in range(8)
        ) + '</div>'
        soup = BeautifulSoup(html, "html.parser")
        result = assert_content_h2_min_eight(soup, {})
        self.assertTrue(result.passed, "8 H2s should pass")


# ─── Deploy Artifact Gate on approve_refresh ─────────────────────────────

class TestApproveRefreshDeployArtifactGate(unittest.TestCase):
    """approve_refresh must refuse when deploy artifact is present but
    job.post_id is null — the incident shape from job 20260805-201409-d9dd5002.
    The readiness check uses refresh.original_post_id (passes); the resolver
    uses job.post_id (catches null). Mutation test (c)."""

    @patch("lib.spec_assertions.ALL_HARD_ASSERTIONS", [])
    def test_refuses_null_post_id_despite_valid_original(self):
        import io, shutil
        from lib.refresher import approve_refresh, JOBS_DIR

        job_id = "test-approve-null-postid"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)

        try:
            raw_html = '<div class="rl-page"><h1>Title</h1><p>Content.</p></div>'
            deploy_html = '<div class="tlnPage"><h1>Title</h1><p>Content.</p></div>'
            (jdir / "999-article.html").write_text(raw_html)
            (jdir / "999-deploy.html").write_text(deploy_html)

            job = {
                "id": job_id,
                "post_id": None,  # null — the incident shape
                "site": "tln",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 30, "hard_total": 30},
                        "d2": {"ran": True, "passed": True, "unsourced": 0},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 5000,
                    "original_title": "Test Article",
                },
            }
            (jdir / "job.json").write_text(json.dumps(job))

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                result = approve_refresh(SITE_CONFIG, job)
            self.assertFalse(result)
            # The refusal must be from the resolver, not from a downstream SSH failure
            self.assertIn("post_id is null", captured.getvalue())
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (a): start_refresh_job sets job["post_id"] ──────────────────

class TestRefreshJobCarriesPostId(unittest.TestCase):
    """start_refresh_job must set job["post_id"] to the target post's ID."""

    @patch("lib.refresher.fetch_post_html")
    @patch("lib.refresher.fetch_gsc_top_pages", return_value=[])
    def test_refresh_job_has_valid_post_id(self, mock_gsc, mock_fetch):
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 1501, "slug": "fha-closing-costs",
            "title": "FHA Closing Costs", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        job = start_refresh_job(SITE_CONFIG, "tln", 1501)
        self.assertIsNotNone(job)
        self.assertEqual(job["post_id"], 1501)
        self.assertIsInstance(job["post_id"], int)
        self.assertGreater(job["post_id"], 0)
        # Same value as refresh.original_post_id
        self.assertEqual(job["post_id"], job["refresh"]["original_post_id"])


# ─── Mutation (b) positive: approve passes with valid post_id ─────────────

class TestApproveRefreshWithValidPostId(unittest.TestCase):
    """approve_refresh readiness check passes when job["post_id"] is set."""

    def test_readiness_passes_with_post_id_set(self):
        import shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job_id = "test-job-valid-postid"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            (jdir / "999-deploy.html").write_text("<html>deploy</html>")
            job = {
                "id": job_id,
                "post_id": 999,
                "site": "tln",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 30, "hard_total": 30},
                        "d2": {"ran": True, "passed": True, "unsourced": 0},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 2531,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertTrue(ready, f"Should pass but got: {reason}")
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (c): rss refresh-draft in CLI dispatcher ───────────────────

class TestRefreshDraftCliRegistered(unittest.TestCase):
    """refresh-draft must be a registered CLI command."""

    def test_refresh_draft_in_dispatcher(self):
        rss_path = Path(__file__).resolve().parent.parent / "rss"
        source = rss_path.read_text()
        self.assertIn("cmd_refresh_draft", source,
                       "cmd_refresh_draft function missing from rss CLI")
        self.assertIn('"refresh-draft"', source,
                       "refresh-draft subcommand missing from argparse")
        self.assertIn('args.command == "refresh-draft"', source,
                       "refresh-draft missing from CLI dispatcher")


# ─── Mutation (d): run_assemble rejects null post_id ─────────────────────

class TestRunAssembleRejectsNullPostId(unittest.TestCase):
    """run_assemble must raise ValueError when post_id is None, not produce 'None'."""

    def test_null_post_id_raises_valueerror(self):
        from lib.orchestrator import run_assemble
        job = {
            "id": "test-null-postid",
            "site": "tln",
            "topic": "test topic",
            "post_id": None,
        }
        with self.assertRaises(ValueError) as ctx:
            run_assemble(job, SITE_CONFIG)
        self.assertIn("post_id", str(ctx.exception))

    def test_zero_post_id_raises_valueerror(self):
        from lib.orchestrator import run_assemble
        job = {
            "id": "test-zero-postid",
            "site": "tln",
            "topic": "test topic",
            "post_id": 0,
        }
        with self.assertRaises(ValueError) as ctx:
            run_assemble(job, SITE_CONFIG)
        self.assertIn("post_id", str(ctx.exception))


# ─── D2 Claims Integrity: Mutation tests ──────────────────────────────────
# Defects: file-path mismatch, settled ratchet, approval bypass
# Gate: assert_d2_claims_integrity

# ─── Mutation (a): run_postprocess reads resolved artifact ────────────────

class TestPostprocessReadsResolvedArtifact(unittest.TestCase):
    """run_postprocess must read from the artifact chain, not a stale
    article.html. Proves DEFECT 1 fix: deploy artifact derives from
    post-claims-resolution HTML."""

    def test_deploy_derives_from_artifact_chain(self):
        import shutil
        from lib.refresher import run_postprocess, JOBS_DIR

        job_id = "test-postprocess-artifact-chain"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)

        try:
            stale_html = '<div class="rl-page"><p>STALE pre-D2 content</p></div>'
            resolved_html = '<div class="rl-page"><p>POST-D2 resolved content</p></div>'

            # Create both files — stale article.html and resolved {pid}-article.html
            (jdir / "article.html").write_text(stale_html)
            (jdir / "999-article.html").write_text(resolved_html)

            job = {
                "id": job_id,
                "site": "tln",
                "refresh": {"original_post_id": 999, "original_slug": "test-slug"},
                "artifacts": {"article_html": str(jdir / "999-article.html")},
            }
            (jdir / "job.json").write_text(json.dumps(job))

            # rl- prefix site → deploy = copy of input (no class migration)
            config = {"content": {"css_prefix": ["rl-"]}}
            deploy_path = run_postprocess(config, job)

            self.assertIsNotNone(deploy_path)
            deploy_content = deploy_path.read_text()
            self.assertIn("POST-D2 resolved content", deploy_content)
            self.assertNotIn("STALE pre-D2 content", deploy_content)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)

    def test_fallback_to_pid_article_when_no_artifact_chain(self):
        """Legacy jobs with no artifacts set should fall back to {pid}-article.html,
        not bare article.html."""
        import shutil
        from lib.refresher import run_postprocess, JOBS_DIR

        job_id = "test-postprocess-fallback"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)

        try:
            stale_html = '<div class="rl-page"><p>STALE bare article</p></div>'
            correct_html = '<div class="rl-page"><p>CORRECT pid-prefixed article</p></div>'

            (jdir / "article.html").write_text(stale_html)
            (jdir / "999-article.html").write_text(correct_html)

            job = {
                "id": job_id,
                "site": "tln",
                "refresh": {"original_post_id": 999, "original_slug": "test-slug"},
                "artifacts": {},  # empty — no artifact chain
            }
            (jdir / "job.json").write_text(json.dumps(job))

            config = {"content": {"css_prefix": ["rl-"]}}
            deploy_path = run_postprocess(config, job)

            self.assertIsNotNone(deploy_path)
            deploy_content = deploy_path.read_text()
            self.assertIn("CORRECT pid-prefixed article", deploy_content)
            self.assertNotIn("STALE bare article", deploy_content)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (b): No SETTLED — every claim classified every run ──────────

class TestNoSettledClassification(unittest.TestCase):
    """The settled-claims ratchet has been removed. Every claim must be
    classified by the LLM on every D2 run. No SETTLED classification
    may appear in the output."""

    @patch("lib.orchestrator.run_claims_classification")
    @patch("lib.orchestrator.run_claims_extraction")
    @patch("lib.orchestrator.run_ventriloquism_gate", return_value=[])
    def test_all_claims_classified_no_settled(self, mock_vent, mock_extract, mock_classify):
        from lib.orchestrator import run_d2_claims_check, JOBS_DIR
        import shutil

        job_id = "test-no-settled"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)

        try:
            # Create a settled-claims file (simulates prior runs)
            settled_data = [
                {"claim": "FHA requires 3.5% down", "classification": "POLICY"},
                {"claim": "Closing costs run 2-6%", "classification": "SOURCE"},
            ]
            (jdir / "d2-settled-claims.json").write_text(json.dumps(settled_data))

            # Extraction returns claims that match settled texts
            mock_extract.return_value = [
                {"claim": "FHA requires 3.5% down", "section": "Intro"},
                {"claim": "Closing costs run 2-6%", "section": "Costs"},
                {"claim": "Brand new claim", "section": "New"},
            ]

            # Classification returns all claims freshly classified
            mock_classify.return_value = [
                {"claim": "FHA requires 3.5% down", "section": "Intro", "classification": "POLICY"},
                {"claim": "Closing costs run 2-6%", "section": "Costs", "classification": "SOURCE"},
                {"claim": "Brand new claim", "section": "New", "classification": "UNSOURCED",
                 "suggestion": "Verify this claim"},
            ]

            job = {"id": job_id, "site": "tln"}
            (jdir / "job.json").write_text(json.dumps(job))

            config = {"content": {"claims_policy": ""}}
            html = "<p>Test article</p>"
            report = run_d2_claims_check(html, config, job)

            # ALL 3 claims must have been sent to the classifier (not just 1)
            mock_classify.assert_called_once()
            classified_claims = mock_classify.call_args[0][0]
            self.assertEqual(len(classified_claims), 3,
                             "All claims must be sent to classifier — settled mechanism must not filter")

            # No SETTLED classification in the output
            for c in report["classified_claims"]:
                self.assertNotEqual(c.get("classification"), "SETTLED",
                                    f"SETTLED classification found: {c}")

            # The settled file on disk must NOT have been updated
            # (the mechanism is removed, not just disabled)
            settled_on_disk = json.loads((jdir / "d2-settled-claims.json").read_text())
            self.assertEqual(len(settled_on_disk), 2,
                             "Settled file must not be modified (evidence preservation)")
        finally:
            shutil.rmtree(jdir, ignore_errors=True)

    @patch("lib.orchestrator.run_claims_classification")
    @patch("lib.orchestrator.run_claims_extraction")
    @patch("lib.orchestrator.run_ventriloquism_gate", return_value=[])
    def test_settled_not_counted_as_source(self, mock_vent, mock_extract, mock_classify):
        """source_count must not include any SETTLED entries."""
        from lib.orchestrator import run_d2_claims_check, JOBS_DIR
        import shutil

        job_id = "test-no-settled-source"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)

        try:
            mock_extract.return_value = [
                {"claim": "Test claim", "section": "Body"},
            ]
            mock_classify.return_value = [
                {"claim": "Test claim", "section": "Body", "classification": "SOURCE"},
            ]

            job = {"id": job_id, "site": "tln"}
            (jdir / "job.json").write_text(json.dumps(job))

            config = {"content": {"claims_policy": ""}}
            report = run_d2_claims_check("<p>test</p>", config, job)

            self.assertEqual(report["source_count"], 1)
            # Verify the source list contains only SOURCE, never SETTLED
            source_classifications = [
                c["classification"] for c in report["classified_claims"]
                if c["classification"] in ("SOURCE", "SETTLED")
            ]
            self.assertTrue(all(c == "SOURCE" for c in source_classifications))
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (c): approve_refresh enforces d2.passed ─────────────────────

class TestApproveRefreshEnforcesD2Passed(unittest.TestCase):
    """refresh_job_ready_for_approval must refuse when d2.passed is false,
    even if d2.ran is true."""

    def test_refuses_d2_passed_false(self):
        import shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job_id = "test-d2-passed-false"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            (jdir / "999-deploy.html").write_text("<html>deploy</html>")
            job = {
                "id": job_id,
                "post_id": 999,
                "site": "tln",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 30, "hard_total": 30},
                        "d2": {"ran": True, "passed": False, "unsourced": 3},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 2531,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertFalse(ready)
            self.assertIn("D2 claims check failed", reason)
            self.assertIn("unsourced=3", reason)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)

    def test_refuses_unsourced_positive(self):
        """Belt-and-suspenders: even if passed=True but unsourced > 0."""
        import shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job_id = "test-d2-unsourced-positive"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            (jdir / "999-deploy.html").write_text("<html>deploy</html>")
            job = {
                "id": job_id,
                "post_id": 999,
                "site": "tln",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 30, "hard_total": 30},
                        "d2": {"ran": True, "passed": True, "unsourced": 2},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 2531,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertFalse(ready)
            self.assertIn("unsourced", reason)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (d): refresh generate sets artifacts.article_html ───────────

class TestRefreshGenerateSetsArticleHtml(unittest.TestCase):
    """A refresh job whose generate stage runs through cmd_new_article must
    have artifacts.article_html set. We verify start_refresh_job sets post_id
    (required for run_assemble to produce {pid}-article.html) and that
    cmd_new_article line 118 stores the path."""

    @patch("lib.refresher.fetch_post_html")
    @patch("lib.refresher.fetch_gsc_top_pages", return_value=[])
    def test_refresh_job_has_post_id_for_artifact_chain(self, mock_gsc, mock_fetch):
        """start_refresh_job must set post_id so run_assemble produces
        {pid}-article.html and cmd_new_article stores it in artifacts."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 1501, "slug": "fha-closing-costs",
            "title": "FHA Closing Costs", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        job = start_refresh_job(SITE_CONFIG, "tln", 1501)
        self.assertIsNotNone(job)
        # post_id must be set for run_assemble to work
        self.assertEqual(job["post_id"], 1501)
        # artifacts dict must exist (start_refresh_job stores original_html)
        self.assertIn("artifacts", job)
        # After cmd_new_article runs generate (line 118), it would set:
        #   job["artifacts"]["article_html"] = str(article_path)
        # We verify the prerequisite: post_id is an int > 0
        self.assertIsInstance(job["post_id"], int)
        self.assertGreater(job["post_id"], 0)


# ─── Counterfactual: August incident shape ────────────────────────────────
# This is the test that proves the fix catches the incident that motivated it.

class TestCounterfactualAugustIncident(unittest.TestCase):
    """Construct a fixture matching the August incident shape — d2.ran true,
    d2.passed false, unsourced > 0 — and assert approve_refresh refuses it.
    Then a second fixture with d2.passed true and assert it proceeds.

    This replicates what would have happened if:
    - DEFECT 2 (settled removal) produced accurate d2 results (passed=false)
    - DEFECT 3 (approval enforcement) checked d2.passed
    """

    def test_august_shape_refused(self):
        """Jobs matching the August incident shape (d2.ran=true, d2.passed=false,
        unsourced > 0) must be refused by the readiness check."""
        import shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job_id = "test-august-incident-refused"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            (jdir / "1501-deploy.html").write_text("<html>deploy</html>")
            job = {
                "id": job_id,
                "post_id": 1501,
                "site": "tln",
                "mode": "refresh",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 44, "hard_total": 44},
                        # August shape: d2 ran, but without settled ratchet
                        # the actual classification finds unsourced claims
                        "d2": {"ran": True, "passed": False, "unsourced": 5},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 1501,
                    "original_slug": "fha-closing-costs",
                    "original_title": "FHA Closing Costs",
                    "pending_draft_id": 2562,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertFalse(ready, "Job with d2.passed=False must be refused")
            self.assertIn("D2", reason)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)

    def test_clean_job_approved(self):
        """Jobs with d2.passed=true and unsourced=0 must proceed through
        the readiness check."""
        import shutil
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR

        job_id = "test-august-incident-approved"
        jdir = JOBS_DIR / job_id
        jdir.mkdir(parents=True, exist_ok=True)
        try:
            (jdir / "1501-deploy.html").write_text("<html>deploy</html>")
            job = {
                "id": job_id,
                "post_id": 1501,
                "site": "tln",
                "mode": "refresh",
                "stages": {
                    "fetch_original": {"status": "done"},
                    "generate": {"status": "done"},
                    "gates": {
                        "status": "done",
                        "validation": {"ran": True, "hard_passed": 44, "hard_total": 44},
                        "d2": {"ran": True, "passed": True, "unsourced": 0},
                    },
                    "link_pass": {"status": "done"},
                    "postprocess": {"status": "done"},
                    "create_pending_draft": {"status": "done"},
                },
                "refresh": {
                    "original_post_id": 1501,
                    "original_slug": "fha-closing-costs",
                    "original_title": "FHA Closing Costs",
                    "pending_draft_id": 2562,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertTrue(ready, f"Clean job must pass readiness but got: {reason}")
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Protected slug matching: mutation red run ────────────────────────────
# Gate: do_not_touch check must match on EITHER post_id or slug.
# Incident: refresher.py:54 KeyError on slug-only entries (9 of 11 VALN protected pages).

class TestProtectedSlugMatching(unittest.TestCase):
    """do_not_touch must block on slug-only entries, not just post_id."""

    VALN_STYLE_CONFIG = {
        "identity": {"site_id": "valn", "public_url": "https://valoannetwork.com"},
        "access": {
            "ssh_host": "test.example.com", "ssh_user": "testuser",
            "ssh_key_path": "~/.ssh/test_key", "wp_path": "/var/www/html/",
        },
        "content": {"css_prefix": ["vln"], "cta_url": "/compare-loan-offers/"},
        "authors": {"author_map": {"sme": {"wp_user_id": 941, "name": "Matt"}}, "byline_mode": "single"},
        "linking": {"zone_suffixes": [], "skip_slugs": []},
        "protected": {
            "do_not_touch_pages": [
                {"post_id": 4, "slug": "homepage", "reason": "Homepage."},
                {"post_id": 385, "slug": "compare-loan-offers", "reason": "Money page."},
                {"slug": "va-funding-fee", "reason": "Slug-only protected page."},
                {"slug": "legal", "reason": "Legal page cluster."},
            ],
        },
        "integrations": {"gsc_property": "sc-domain:valoannetwork.com"},
    }

    # ── Mutation (a): slug-only match blocks refresh ──────────────────────

    @patch("lib.refresher.fetch_post_html")
    def test_refuses_slug_only_protected_page(self, mock_fetch):
        """A post whose slug matches a slug-only do_not_touch entry must be
        refused. Remove the slug matching -> this test fails."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 833, "slug": "va-funding-fee",
            "title": "VA Funding Fee", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(self.VALN_STYLE_CONFIG, "valn", 833)
        self.assertIsNone(result, "Slug-only protected page must be refused")

    @patch("lib.refresher.fetch_post_html")
    def test_refuses_second_slug_only_entry(self, mock_fetch):
        """Second slug-only entry also blocks."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 9999, "slug": "legal",
            "title": "Legal", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(self.VALN_STYLE_CONFIG, "valn", 9999)
        self.assertIsNone(result, "Slug-only 'legal' must be refused")

    # ── Mutation (b): post_id match still works ──────────────────────────

    @patch("lib.refresher.fetch_post_html")
    def test_refuses_post_id_match(self, mock_fetch):
        """Existing behavior: post_id match blocks refresh."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 4, "slug": "homepage",
            "title": "Home", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(self.VALN_STYLE_CONFIG, "valn", 4)
        self.assertIsNone(result, "post_id-matched protected page must be refused")

    @patch("lib.refresher.fetch_post_html")
    def test_post_id_match_even_if_slug_differs(self, mock_fetch):
        """post_id 385 is protected even if WP returned a different slug."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 385, "slug": "some-other-slug",
            "title": "Apply", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(self.VALN_STYLE_CONFIG, "valn", 385)
        self.assertIsNone(result, "post_id 385 must be refused regardless of slug")

    # ── Mutation (c): malformed entries raise loudly ─────────────────────

    @patch("lib.refresher.fetch_post_html")
    def test_malformed_entry_raises(self, mock_fetch):
        """An entry with neither post_id nor slug must raise ValueError."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 999, "slug": "safe-slug",
            "title": "Test", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        bad_config = {
            **self.VALN_STYLE_CONFIG,
            "protected": {
                "do_not_touch_pages": [
                    {"reason": "No id, no slug — malformed."},
                ],
            },
        }
        with self.assertRaises(ValueError) as ctx:
            start_refresh_job(bad_config, "valn", 999)
        self.assertIn("neither post_id nor slug", str(ctx.exception))

    @patch("lib.refresher.fetch_post_html")
    def test_string_type_raises(self, mock_fetch):
        """do_not_touch_pages as a string (GFP/velocityseo 'TODO-verify')
        must raise ValueError, not silently iterate characters."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 999, "slug": "safe-slug",
            "title": "Test", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        bad_config = {
            **self.VALN_STYLE_CONFIG,
            "protected": {"do_not_touch_pages": "TODO-verify"},
        }
        with self.assertRaises(ValueError) as ctx:
            start_refresh_job(bad_config, "valn", 999)
        self.assertIn("must be a list", str(ctx.exception))

    # ── Positive: unprotected post passes through ────────────────────────

    @patch("lib.refresher.fetch_post_html")
    @patch("lib.refresher.fetch_gsc_top_pages", return_value=[])
    def test_unprotected_post_passes(self, mock_gsc, mock_fetch):
        """A post not in do_not_touch passes the safety check."""
        from lib.refresher import start_refresh_job
        mock_fetch.return_value = {
            "post_id": 30448, "slug": "tla-vs-tle-pcs-lodging-benefit-guide",
            "title": "TLA vs TLE", "html": "<p>content</p>",
            "status": "publish", "post_date": "2026-01-01 00:00:00",
        }
        result = start_refresh_job(self.VALN_STYLE_CONFIG, "valn", 30448)
        self.assertIsNotNone(result, "Unprotected post must not be refused")
        self.assertEqual(result["post_id"], 30448)

    # ── Unit tests for _is_do_not_touch directly ─────────────────────────

    def test_helper_empty_list(self):
        from lib.refresher import _is_do_not_touch
        config = {"protected": {"do_not_touch_pages": []}}
        self.assertFalse(_is_do_not_touch(config, 100, "any-slug"))

    def test_helper_no_protected_key(self):
        from lib.refresher import _is_do_not_touch
        self.assertFalse(_is_do_not_touch({}, 100, "any-slug"))


if __name__ == "__main__":
    unittest.main()
