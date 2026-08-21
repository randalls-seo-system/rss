"""L30 mutation red runs — D2 verbatim matching fix.

Mutation tests:
  (a) verbatim_text NOT in source HTML → caught, reported with reason
      verbatim_not_in_source, not silently passed through
  (b) verbatim_text IS present in source HTML → resolved correctly
  (c) Paraphrase-only matching on a real fixture → test asserts
      miss rate proves the old path produces misses
  (d) Legacy claim record with no verbatim_text field → handled
      gracefully (falls back to old matching), no crash
  (e) extraction_failed (verbatim_not_in_source) claim silently excluded
      from unresolved_count → test fails. Proves the correction is
      load-bearing.
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


# ─── Mutation (a): verbatim_not_in_source is caught and reported ─────────

class TestVerbatimNotInSourceCaught(unittest.TestCase):
    """A claim with verbatim_text that does NOT appear in the article HTML
    must be reported as unresolved with reason 'verbatim_not_in_source'.
    If it is silently skipped, this test fails."""

    def test_verbatim_mismatch_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-verbatim-mismatch", tmp)
                jdir = Path(tmp) / "test-verbatim-mismatch"

                report = {
                    "classified_claims": [
                        {
                            "claim": "The waiting period is two years after foreclosure",
                            "verbatim_text": "Borrowers must wait 24 months following a completed foreclosure",
                            "verbatim_verified": False,
                            "verbatim_mismatch": True,
                            "section": "Waiting Periods",
                            "classification": "UNSOURCED",
                            "suggestion": "Verify against VA Circular.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(
                    "<p>The actual foreclosure recovery timeline varies by lender.</p>"
                )

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                self.assertEqual(len(resolved), 0, "Should not have resolved anything")
                self.assertEqual(len(unresolved), 1, "Must report exactly 1 unresolved claim")
                self.assertEqual(unresolved[0]["reason"], "verbatim_not_in_source")
                self.assertIn("claim", unresolved[0])
                self.assertIn("section", unresolved[0])
                self.assertEqual(unresolved[0]["section"], "Waiting Periods")

                # Must also be in the job history
                history = job.get("history", [])
                approve_entries = [h for h in history if h.get("stage") == "approve_claims"]
                self.assertEqual(len(approve_entries), 1)
                self.assertEqual(len(approve_entries[0]["unresolved"]), 1)
                self.assertEqual(
                    approve_entries[0]["unresolved"][0]["reason"],
                    "verbatim_not_in_source",
                )


# ─── Mutation (b): verbatim_text present → resolved correctly ────────────

class TestVerbatimPresentResolved(unittest.TestCase):
    """A claim with verbatim_text that IS present in the article HTML must
    be resolved correctly. The verbatim_text is used for matching instead
    of the paraphrased claim field."""

    def test_verbatim_match_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-verbatim-match", tmp)
                jdir = Path(tmp) / "test-verbatim-match"

                verbatim = "VA loans require no down payment for qualified Veterans"
                report = {
                    "classified_claims": [
                        {
                            "claim": "No down payment required for VA loans",
                            "verbatim_text": verbatim,
                            "verbatim_verified": True,
                            "section": "Benefits",
                            "classification": "UNSOURCED",
                            "suggestion": "Verify with VA circular.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                original = (
                    f"<p>Introduction sentence. {verbatim} and that saves money. "
                    f"More content follows.</p>"
                )
                article.write_text(original)

                result_path, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                self.assertEqual(len(resolved), 1, "Verbatim-verified claim must resolve")
                self.assertEqual(len(unresolved), 0, "No claims should be unresolved")
                self.assertEqual(resolved[0]["action"], "removed")

                # Verify the verbatim text is gone from the article
                result_html = result_path.read_text()
                self.assertNotIn(verbatim, result_html)
                # Surrounding content preserved
                self.assertIn("Introduction sentence", result_html)
                self.assertIn("More content follows", result_html)

    def test_verbatim_used_over_paraphrase(self):
        """When verbatim_text is verified, matching uses it — NOT the
        paraphrased claim field. Proves the resolver prefers verbatim."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-verbatim-preferred", tmp)
                jdir = Path(tmp) / "test-verbatim-preferred"

                # The paraphrase does NOT appear in the HTML.
                # Only the verbatim_text does.
                paraphrase = "No down payment needed on VA mortgages"
                verbatim = "VA loans require zero down payment for eligible service members"
                report = {
                    "classified_claims": [
                        {
                            "claim": paraphrase,
                            "verbatim_text": verbatim,
                            "verbatim_verified": True,
                            "section": "Benefits",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(
                    f"<p>Start here. {verbatim} and more text. End.</p>"
                )

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                # Must resolve via verbatim_text even though paraphrase ≠ article
                self.assertEqual(len(resolved), 1)
                self.assertEqual(len(unresolved), 0)


# ─── Mutation (c): paraphrase-only matching fails on real fixture ────────

class TestParaphraseOnlyMisses(unittest.TestCase):
    """Prove that matching on the paraphrased claim field (the old behavior)
    produces misses. This test constructs a fixture where the paraphrase
    does NOT appear in the HTML but the verbatim_text does, then runs
    the resolver with the paraphrase-only path (no verbatim_text).
    The miss is the expected result — proving the old path is broken."""

    def test_paraphrase_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-paraphrase-miss", tmp)
                jdir = Path(tmp) / "test-paraphrase-miss"

                # Simulate the old path: claim is a paraphrase, no verbatim_text
                paraphrase = "The foreclosure waiting period is typically two years for VA borrowers"
                actual_text = "Veterans who have experienced a foreclosure must complete a minimum waiting period of 24 months before applying for a new VA loan"

                report = {
                    "classified_claims": [
                        {
                            "claim": paraphrase,
                            # No verbatim_text — simulates legacy/old extraction
                            "section": "Waiting Periods",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(
                    f"<p>Introduction. {actual_text} according to current guidelines. End.</p>"
                )

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                # The paraphrase does NOT match the article — this is the defect
                self.assertEqual(len(resolved), 0, "Paraphrase must NOT match")
                self.assertEqual(len(unresolved), 1, "Must report as unresolved")
                self.assertEqual(unresolved[0]["reason"], "pattern_not_found")


# ─── Mutation (d): legacy claim with no verbatim_text → no crash ─────────

class TestLegacyClaimFallback(unittest.TestCase):
    """A claim record with no verbatim_text field must be handled
    gracefully — falls back to old claim[:60] matching, no crash."""

    def test_legacy_claim_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-legacy-fallback", tmp)
                jdir = Path(tmp) / "test-legacy-fallback"

                claim_text = "The standard VA funding fee is 2.15 percent for first-time use"
                report = {
                    "classified_claims": [
                        {
                            "claim": claim_text,
                            # No verbatim_text, no verbatim_verified — legacy format
                            "section": "Fees",
                            "classification": "UNSOURCED",
                            "suggestion": "Verify.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(
                    f"<p>Fee overview. {claim_text} for regular military. More text.</p>"
                )

                # Must not crash and should resolve via old claim[:60] path
                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                self.assertEqual(len(resolved), 1, "Legacy claim must resolve via fallback")
                self.assertEqual(len(unresolved), 0)

    def test_legacy_claim_no_crash_on_miss(self):
        """Legacy claim that also misses — still no crash, reports correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-legacy-miss", tmp)
                jdir = Path(tmp) / "test-legacy-miss"

                report = {
                    "classified_claims": [
                        {
                            "claim": "A paraphrased claim that does not appear in the article",
                            "section": "Intro",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        }
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text("<p>Totally different content here.</p>")

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                self.assertEqual(len(resolved), 0)
                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "pattern_not_found")


# ─── Mutation (e): verbatim_not_in_source MUST count toward unresolved ───

class TestVerbatimMismatchCountsAsUnresolved(unittest.TestCase):
    """An extraction_failed claim (verbatim_not_in_source) must count
    toward unresolved_count and trigger fail_unresolved in the approval
    gate. If excluded from unresolved_count, this test fails.

    This proves the correction is load-bearing: the system must not
    sail through when it found a problem it cannot act on."""

    def test_verbatim_mismatch_in_unresolved_count(self):
        """The resolver must include verbatim_not_in_source claims
        in the unresolved list, which the rss tool uses to compute
        unresolved_count and set status to fail_unresolved."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-mismatch-counts", tmp)
                jdir = Path(tmp) / "test-mismatch-counts"

                # Two claims: one matchable, one with verbatim mismatch
                matchable_verbatim = "The VA funding fee is waived for disabled Veterans"
                report = {
                    "classified_claims": [
                        {
                            "claim": "Funding fee waiver for disabled vets",
                            "verbatim_text": matchable_verbatim,
                            "verbatim_verified": True,
                            "section": "Fees",
                            "classification": "UNSOURCED",
                            "suggestion": "Verify.",
                        },
                        {
                            "claim": "Credit score of 620 needed",
                            "verbatim_text": "Most lenders want a minimum FICO around six-twenty",
                            "verbatim_verified": False,
                            "verbatim_mismatch": True,
                            "section": "Credit",
                            "classification": "UNSOURCED",
                            "suggestion": "Remove.",
                        },
                    ]
                }
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))

                article = jdir / "999-article.html"
                article.write_text(
                    f"<p>Overview. {matchable_verbatim} per VA guidelines. "
                    f"Credit requirements vary by lender. End.</p>"
                )

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove"
                )

                # The matchable claim resolves
                self.assertEqual(len(resolved), 1)
                # The mismatched claim is in unresolved — NOT silently excluded
                self.assertEqual(
                    len(unresolved), 1,
                    "verbatim_not_in_source claim MUST appear in unresolved list"
                )
                self.assertEqual(unresolved[0]["reason"], "verbatim_not_in_source")

    def test_approval_gate_blocks_on_verbatim_mismatch(self):
        """The approval gate must refuse when unresolved_count > 0 due
        to verbatim_not_in_source claims. Uses the same gate path as
        pattern_not_found and boundary_failure."""
        from lib.refresher import refresh_job_ready_for_approval, JOBS_DIR as RJOBS

        job_id = "test-mismatch-blocks-approval"
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
                        "unsourced": 3,
                        "resolutions": 2,
                        "unresolved_count": 1,
                        "unresolved": [
                            {
                                "claim": "credit score claim",
                                "section": "Credit",
                                "reason": "verbatim_not_in_source",
                                "pattern_tried": "Most lenders want a minimum...",
                            },
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
            self.assertFalse(ready, "Must refuse approval on verbatim_not_in_source unresolved")
            self.assertIn("unresolved", reason)
        finally:
            shutil.rmtree(jdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
