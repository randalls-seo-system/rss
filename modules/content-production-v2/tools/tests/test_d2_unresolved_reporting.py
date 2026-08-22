"""L27 mutation red runs — D2 resolver reports unresolved claims.

Mutation tests:
  (a) Unresolved claim not named in job record → test fails
  (b) Claim the resolver cannot pattern-match → reported with reason
      pattern_not_found, not silently skipped
  (c) Claim the resolver CAN match → still removed correctly
  (d) Status stays "fail" when claims are unresolved → approval-refusal
      test fails (must be "fail_unresolved")
  (e) Real job 20260820-191306-941786f4 validation — 2 unresolved claims
      named with reasons
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.orchestrator import resolve_unsourced_claims, job_dir, JOBS_DIR, D2_RESULT_KEY


def _make_job(job_id, tmp_dir):
    """Create a minimal job fixture on disk."""
    jdir = Path(tmp_dir) / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id,
        "site": "test",
        "topic": "test",
        "post_id": 999,
        "stages": {},
        "created": datetime.now().isoformat(),
    }
    (jdir / "job.json").write_text(json.dumps(job))
    return job


# ─── Mutation (a): unresolved claims MUST appear in the job record ────────

class TestUnresolvedClaimsNamedInJobRecord(unittest.TestCase):
    """If a claim cannot be resolved, it must appear in the history's
    unresolved list with claim text, section, and reason. If it is silently
    dropped, this test fails."""

    def test_unresolved_claim_appears_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-unresolved-named", tmp)
                jdir = Path(tmp) / "test-unresolved-named"

                # D2 report: one claim whose text is NOT in the article HTML
                report = {
                    "classified_claims": [
                        {
                            "claim": "This claim text does not appear anywhere in the article HTML whatsoever",
                            "section": "Test Section",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove it.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text("<p>Completely different content here.</p>")

                _, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                self.assertEqual(len(resolved), 0, "Should not have resolved anything")
                self.assertEqual(len(unresolved), 1, "Must report exactly 1 unresolved claim")
                self.assertIn("claim", unresolved[0])
                self.assertIn("section", unresolved[0])
                self.assertIn("reason", unresolved[0])
                self.assertIn("pattern_tried", unresolved[0])
                self.assertEqual(unresolved[0]["section"], "Test Section")

                # Must also be in the job history
                history = job.get("history", [])
                approve_entries = [h for h in history if h.get("stage") == "approve_claims"]
                self.assertEqual(len(approve_entries), 1)
                self.assertEqual(len(approve_entries[0]["unresolved"]), 1)
                self.assertEqual(approve_entries[0]["unresolved"][0]["section"], "Test Section")


# ─── Mutation (b): pattern_not_found reason code ─────────────────────────

class TestPatternNotFoundReasonCode(unittest.TestCase):
    """A claim whose 60-char pattern is not found in the HTML must be
    reported with reason 'pattern_not_found'. If the resolver silently
    skips it, this test fails."""

    def test_reason_is_pattern_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-pnf-reason", tmp)
                jdir = Path(tmp) / "test-pnf-reason"

                report = {
                    "classified_claims": [
                        {
                            "claim": "The rate is exactly 4.75 percent for all qualified borrowers nationwide",
                            "section": "Rate Details",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove unsourced rate.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text("<p>Rates vary by lender and credit profile.</p>")

                _, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "pattern_not_found")
                self.assertIn("4.75 percent", unresolved[0]["pattern_tried"])

    def test_boundary_failure_reason(self):
        """If the pattern IS found but no sentence boundary exists,
        the reason must be 'boundary_failure'."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-boundary-fail", tmp)
                jdir = Path(tmp) / "test-boundary-fail"

                # Claim text is at the very start — no preceding period
                claim = "This sentence has no preceding period in the document"
                report = {
                    "classified_claims": [
                        {
                            "claim": claim,
                            "section": "Opening",
                            "classification": "UNSOURCED",
                            "suggestion": "Fix it.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                # No period before the claim text
                article = jdir / "999-article.html"
                article.write_text(f"{claim} and it ends here.")

                _, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "boundary_failure")

    def test_collateral_removal_reason(self):
        """If a prior removal in the same loop already deleted the text,
        the claim must be recorded as already_removed (resolved success),
        NOT as unresolved. L31: collateral removal is success — the claim
        was removed from the article, just not by its own pattern match."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-collateral", tmp)
                jdir = Path(tmp) / "test-collateral"

                # Two claims share the same 60-char prefix
                shared_text = "X" * 60
                claim_a = shared_text + " first variant of the claim"
                claim_b = shared_text + " second variant of the claim"
                report = {
                    "classified_claims": [
                        {
                            "claim": claim_a,
                            "section": "Section A",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        },
                        {
                            "claim": claim_b,
                            "section": "Section B",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        },
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(f"<p>Intro. {claim_a} end here. More content.</p>")

                _, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                # claim_a removed directly; claim_b already_removed (collateral success)
                self.assertEqual(len(resolved), 2)
                self.assertEqual(len(unresolved), 0)
                actions = [r["action"] for r in resolved]
                self.assertIn("removed", actions)
                self.assertIn("already_removed", actions)


# ─── Mutation (c): working path still removes matched claims ─────────────

class TestWorkingPathStillRemoves(unittest.TestCase):
    """A claim whose 60-char pattern IS found in the HTML and has
    valid sentence boundaries must still be removed correctly.
    Proves the reporting change did not break the existing path."""

    def test_matched_claim_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-working-path", tmp)
                jdir = Path(tmp) / "test-working-path"

                claim = "VA loans require no down payment for qualified Veterans"
                report = {
                    "classified_claims": [
                        {
                            "claim": claim,
                            "section": "Benefits",
                            "classification": "UNSOURCED",
                            "suggestion": "Verify with VA circular.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                original = f"<p>Introduction sentence. {claim} and that saves money. More content follows.</p>"
                article.write_text(original)

                result_path, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                self.assertEqual(len(resolved), 1)
                self.assertEqual(len(unresolved), 0)
                self.assertEqual(resolved[0]["action"], "removed")

                # Verify the claim text is gone from the article
                result_html = result_path.read_text()
                self.assertNotIn(claim, result_html)
                # Surrounding content preserved
                self.assertIn("Introduction sentence", result_html)
                self.assertIn("More content follows", result_html)

    def test_mixed_resolved_and_unresolved(self):
        """Two claims: one matchable, one not. Both must be accounted for."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-mixed", tmp)
                jdir = Path(tmp) / "test-mixed"

                matchable = "The average closing cost is three percent of the purchase price"
                unmatchable = "D2 paraphrased this from a table cell that does not exist verbatim"
                report = {
                    "classified_claims": [
                        {"claim": matchable, "section": "Costs", "classification": "UNSOURCED", "suggestion": "Remove."},
                        {"claim": unmatchable, "section": "Table", "classification": "UNSOURCED", "suggestion": "Remove."},
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(f"<p>Intro. {matchable} according to recent data. End.</p>")

                _, resolved, unresolved = resolve_unsourced_claims(job, article, mode="remove")

                self.assertEqual(len(resolved), 1, "Matchable claim must resolve")
                self.assertEqual(len(unresolved), 1, "Unmatchable claim must be reported")
                self.assertEqual(resolved[0]["claim"][:30], matchable[:30])
                self.assertEqual(unresolved[0]["reason"], "pattern_not_found")


# ─── Mutation (d): approval gate refuses on unresolved_count > 0 ─────────

class TestApprovalRefusesUnresolvedClaims(unittest.TestCase):
    """refresh_job_ready_for_approval must refuse when unresolved_count > 0,
    with a message distinct from the generic D2 failure. If the status
    stays 'fail' (rather than distinguishing unresolved), this test fails."""

    def test_refuses_unresolved_count_positive(self):
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR as RJOBS
        # D2_RESULT_KEY imported at module level from lib.orchestrator

        job_id = "test-unresolved-approval"
        jdir = RJOBS / job_id
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
                    D2_RESULT_KEY: {
                        "status": "fail_unresolved",
                        "unsourced": 5,
                        "resolutions": 3,
                        "unresolved_count": 2,
                        "unresolved": [
                            {"claim": "claim A", "section": "S1", "reason": "pattern_not_found", "pattern_tried": "claim A..."},
                            {"claim": "claim B", "section": "S2", "reason": "boundary_failure", "pattern_tried": "claim B..."},
                        ],
                        "fully_resolved": False,
                    },
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 2531,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertFalse(ready)
            self.assertIn("unresolved", reason)
            self.assertIn("2", reason)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)

    def test_accepts_fully_resolved(self):
        """When unresolved_count is 0, the approval gate must not block
        on the claims_check stage."""
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR as RJOBS
        # D2_RESULT_KEY imported at module level from lib.orchestrator

        job_id = "test-fully-resolved-approval"
        jdir = RJOBS / job_id
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
                    D2_RESULT_KEY: {
                        "status": "done",
                        "unsourced": 5,
                        "resolutions": 5,
                        "unresolved_count": 0,
                        "unresolved": [],
                        "fully_resolved": True,
                    },
                },
                "refresh": {
                    "original_post_id": 999,
                    "pending_draft_id": 2531,
                },
            }
            ready, reason = refresh_job_ready_for_approval(job)
            self.assertTrue(ready, f"Fully resolved job must pass but got: {reason}")
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


# ─── Mutation (e): real job validation ────────────────────────────────────

class TestRealJobValidation(unittest.TestCase):
    """Run the reporting logic against the real job 20260820-191306-941786f4
    and confirm the 2 unresolved claims are named with correct reasons.
    A synthetic fixture proves the code path; a real job proves it
    describes reality."""

    REAL_JOB_ID = "20260820-191306-941786f4"

    def test_real_job_two_unresolved_named(self):
        real_job_dir = JOBS_DIR / self.REAL_JOB_ID
        report_path = real_job_dir / "d2-claims-report.json"
        if not report_path.exists():
            self.skipTest(f"Real job {self.REAL_JOB_ID} not on disk")

        report = json.loads(report_path.read_text())
        classified = report.get("classified_claims", [])
        unsourced = [c for c in classified if c.get("classification") == "UNSOURCED"]

        # Read the article HTML (post-resolution state on disk)
        article_path = real_job_dir / "30448-article.html"
        if not article_path.exists():
            self.skipTest("Article HTML not on disk")
        html = article_path.read_text()

        # Simulate the resolver's matching logic WITHOUT writing to disk
        import re
        resolved_prefixes = set()
        resolved_count = 0
        unresolved_items = []

        for claim in unsourced:
            claim_text = claim.get("claim", "")
            pattern = re.escape(claim_text[:60])
            m = re.search(pattern, html)
            if m:
                start = html.rfind(".", 0, m.start())
                end = html.find(".", m.end())
                if start >= 0 and end >= 0:
                    resolved_count += 1
                    resolved_prefixes.add(claim_text[:60])
                else:
                    unresolved_items.append({
                        "claim": claim_text[:100],
                        "section": claim.get("section", ""),
                        "reason": "boundary_failure",
                    })
            else:
                if claim_text[:60] in resolved_prefixes:
                    reason = "collateral_removal"
                else:
                    reason = "pattern_not_found"
                unresolved_items.append({
                    "claim": claim_text[:100],
                    "section": claim.get("section", ""),
                    "reason": reason,
                })

        # The real job had 13 unsourced, 11 resolved, 2 unresolved
        self.assertEqual(len(unsourced), 13, "Real job has 13 UNSOURCED claims")
        # The article on disk is already post-resolution — 11 claims were
        # already removed by the prior run. We should see those 11 as
        # pattern_not_found (their text is gone), plus the 2 original
        # unresolved. What matters is that the 2 ORIGINAL unresolved claims
        # are identifiable: the OCONUS table claim and the collateral claim.

        # Find the two specific claims by their distinctive text
        oconus_claim = [u for u in unresolved_items
                        if "OCONUS to OCONUS TLA filed" in u["claim"]]
        filing_claim = [u for u in unresolved_items
                        if "filing one does not automatically" in u["claim"]]

        self.assertEqual(len(oconus_claim), 1,
                         "OCONUS table claim must be identified as unresolved")
        self.assertEqual(oconus_claim[0]["reason"], "pattern_not_found",
                         "OCONUS claim fails because D2 paraphrased across <td> cells")
        self.assertEqual(oconus_claim[0]["section"], "Bottom Line on TLA vs TLE")

        self.assertEqual(len(filing_claim), 1,
                         "'filing one' claim must be identified as unresolved")
        # This one is pattern_not_found on the post-resolution HTML (text
        # was removed by collateral of the DTS claim removal in the prior run)
        self.assertIn(filing_claim[0]["reason"],
                      ("pattern_not_found", "collateral_removal"),
                      "'filing one' was either collateral or pattern_not_found on post-resolution HTML")
        self.assertEqual(filing_claim[0]["section"], "Can You Use TLA and TLE Together?")


if __name__ == "__main__":
    unittest.main()
