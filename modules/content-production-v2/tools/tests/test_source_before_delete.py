"""Source-before-delete mutation red runs.

Tests the verification step inserted between D2 classification and
resolution. UNSOURCED claims are verified against authority sources
before deletion, producing four verdicts: source_recovered, contradicts,
not_stated, verification_failed.

Mutation tests:
  (a) Search fails → verification_failed, claim NOT deleted.
      Map to not_stated → test fails.
  (b) CONTRADICTS → blocks, article unmodified, correction in safi-questions.
      Auto-apply → test fails.
  (c) source_recovered → kept, not sent to resolver.
      Send it → test fails.
  (d) not_stated → deleted as today.
  (e) Structural: local judge/authority-domain list outside shared module → fails.
  (f) Judge returns STATES without quote → treated as NOT_STATED.
"""

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(REPO_ROOT / "lib"))


# ── Helpers ──────────────────────────────────────────────────────────

def _make_d2_report(claims_with_verification):
    """Build a d2-claims-report.json with verification fields."""
    classified = []
    for c in claims_with_verification:
        entry = {
            "id": c["id"],
            "claim": c["claim"],
            "verbatim_text": c.get("verbatim_text", c["claim"]),
            "verbatim_verified": True,
            "section": c.get("section", "Test"),
            "claim_type": c.get("claim_type", "general_fact"),
            "classification": c.get("classification", "UNSOURCED"),
        }
        if "verification" in c:
            entry["verification"] = c["verification"]
        if "verification_url" in c:
            entry["verification_url"] = c["verification_url"]
        if "verification_quote" in c:
            entry["verification_quote"] = c["verification_quote"]
        if "verification_attempts" in c:
            entry["verification_attempts"] = c["verification_attempts"]
        if "suggestion" in c:
            entry["suggestion"] = c["suggestion"]
        classified.append(entry)

    unsourced = [c for c in classified
                 if c.get("classification") == "UNSOURCED"
                 and c.get("verification", "not_stated") == "not_stated"]
    contradicts = [c for c in classified if c.get("verification") == "contradicts"]
    vf = [c for c in classified if c.get("verification") == "verification_failed"]
    recovered = [c for c in classified if c.get("verification") == "source_recovered"]

    return {
        "ventriloquism_hits": [],
        "ventriloquism_licensed": False,
        "total_claims": len(classified),
        "classified_claims": classified,
        "unsourced_count": len(unsourced),
        "contradicts_count": len(contradicts),
        "verification_failed_count": len(vf),
        "source_recovered_count": len(recovered),
        "policy_count": 0,
        "source_count": 0,
        "sme_sourced_count": 0,
        "passed": len(unsourced) == 0 and len(contradicts) == 0 and len(vf) == 0,
    }


class TestVerificationFailed(unittest.TestCase):
    """(a) Search fails → verification_failed → claim NOT deleted."""

    def test_verification_failed_not_deleted(self):
        """A claim with verification=verification_failed is not sent to resolver.
        Mutation: treat verification_failed as not_stated → test fails."""
        from lib.orchestrator import resolve_unsourced_claims, JOBS_DIR

        report = _make_d2_report([
            {"id": "c000", "claim": "TLA can be advanced",
             "verbatim_text": "TLA can be advanced before you secure permanent quarters.",
             "classification": "UNSOURCED", "verification": "verification_failed",
             "verification_attempts": {
                 "searches_run": 1, "search_results_returned": 0,
                 "fetches_attempted": 0, "fetches_succeeded": 0, "judges_run": 0,
             }},
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            job = {"id": "test-vf", "stages": {}}
            os.makedirs(JOBS_DIR / "test-vf", exist_ok=True)
            try:
                (JOBS_DIR / "test-vf" / "d2-claims-report.json").write_text(
                    json.dumps(report, indent=2))

                # Multi-sentence so resolver CAN remove if the filter lets it through
                article = (
                    "<p>There are several important rules. "
                    "TLA can be advanced before you secure permanent quarters. "
                    "Check with your finance office. "
                    "Filing early helps avoid delays.</p>"
                )
                article_path = job_path / "article.html"
                article_path.write_text(article)

                _, resolutions, unresolved = resolve_unsourced_claims(
                    job, article_path, mode="remove")

                # verification_failed claim should NOT be in resolutions or unresolved
                all_acted = [r.get("claim", "") for r in resolutions] + [u.get("claim", "") for u in unresolved]
                self.assertTrue(
                    all("TLA can be advanced" not in c for c in all_acted),
                    "verification_failed claim was sent to resolver — search failure "
                    "must not license a deletion."
                )
                # Article should still contain the claim
                self.assertIn("advanced", article_path.read_text())
            finally:
                import shutil
                shutil.rmtree(JOBS_DIR / "test-vf", ignore_errors=True)

    def test_verification_failed_blocks(self):
        """verification_failed in d2 report → passed=False."""
        report = _make_d2_report([
            {"id": "c000", "claim": "test claim",
             "classification": "UNSOURCED", "verification": "verification_failed"},
        ])
        self.assertFalse(report["passed"])


class TestContradicts(unittest.TestCase):
    """(b) CONTRADICTS → blocks, article unmodified."""

    def test_contradicts_not_deleted(self):
        """A contradicts claim is not sent to the resolver.
        Mutation: auto-apply the correction → test fails."""
        from lib.orchestrator import resolve_unsourced_claims, JOBS_DIR

        report = _make_d2_report([
            {"id": "c000", "claim": "TLE lasts up to 14 days",
             "classification": "UNSOURCED", "verification": "contradicts",
             "verification_url": "https://travel.dod.mil/tla",
             "verification_quote": "TLE is authorized for up to 21 days"},
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            job = {"id": "test-contra", "stages": {}}
            os.makedirs(JOBS_DIR / "test-contra", exist_ok=True)
            try:
                (JOBS_DIR / "test-contra" / "d2-claims-report.json").write_text(
                    json.dumps(report, indent=2))

                article = "<p>TLE lasts up to 14 days of lodging.</p>"
                article_path = job_path / "article.html"
                article_path.write_text(article)

                _, resolutions, unresolved = resolve_unsourced_claims(
                    job, article_path, mode="remove")

                resolved_claims = [r["claim"] for r in resolutions]
                self.assertNotIn(
                    "TLE lasts up to 14 days", resolved_claims,
                    "CONTRADICTS claim was deleted — corrections must not "
                    "be auto-applied."
                )
                self.assertIn("14 days", article_path.read_text(),
                              "Article was modified — CONTRADICTS must not touch the article.")
            finally:
                import shutil
                shutil.rmtree(JOBS_DIR / "test-contra", ignore_errors=True)

    def test_contradicts_blocks(self):
        """contradicts in d2 report → passed=False."""
        report = _make_d2_report([
            {"id": "c000", "claim": "test",
             "classification": "UNSOURCED", "verification": "contradicts"},
        ])
        self.assertFalse(report["passed"])


class TestSourceRecovered(unittest.TestCase):
    """(c) source_recovered → kept, not sent to resolver."""

    def test_source_recovered_not_deleted(self):
        """A source_recovered claim is kept — not sent to resolver.
        Mutation: send it → test fails."""
        from lib.orchestrator import resolve_unsourced_claims, JOBS_DIR

        report = _make_d2_report([
            {"id": "c000", "claim": "TLE requires government quarters first",
             "classification": "UNSOURCED", "verification": "source_recovered",
             "verification_url": "https://travel.dod.mil/tla",
             "verification_quote": "Members must use government quarters when available."},
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            job = {"id": "test-recovered", "stages": {}}
            os.makedirs(JOBS_DIR / "test-recovered", exist_ok=True)
            try:
                (JOBS_DIR / "test-recovered" / "d2-claims-report.json").write_text(
                    json.dumps(report, indent=2))

                article = "<p>TLE requires government quarters first before booking a hotel.</p>"
                article_path = job_path / "article.html"
                article_path.write_text(article)

                _, resolutions, unresolved = resolve_unsourced_claims(
                    job, article_path, mode="remove")

                resolved_claims = [r["claim"] for r in resolutions]
                self.assertNotIn(
                    "TLE requires government quarters first", resolved_claims,
                    "source_recovered claim was deleted — verified claims "
                    "must be kept."
                )
                self.assertEqual(article_path.read_text(), article)
            finally:
                import shutil
                shutil.rmtree(JOBS_DIR / "test-recovered", ignore_errors=True)


class TestNotStatedDeleted(unittest.TestCase):
    """(d) not_stated → deleted as today."""

    def test_not_stated_is_removed(self):
        from lib.orchestrator import resolve_unsourced_claims, JOBS_DIR

        report = _make_d2_report([
            {"id": "c000", "claim": "TLA can be advanced",
             "verbatim_text": "TLA can be advanced before securing quarters.",
             "classification": "UNSOURCED", "verification": "not_stated"},
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            job = {"id": "test-ns", "stages": {}}
            os.makedirs(JOBS_DIR / "test-ns", exist_ok=True)
            try:
                (JOBS_DIR / "test-ns" / "d2-claims-report.json").write_text(
                    json.dumps(report, indent=2))

                # Multi-sentence paragraph so removal doesn't empty the container
                article = (
                    "<p>There are several important rules about TLA. "
                    "TLA can be advanced before securing quarters. "
                    "Check with your finance office for details. "
                    "Filing early helps avoid delays.</p>"
                )
                article_path = job_path / "article.html"
                article_path.write_text(article)

                _, resolutions, _ = resolve_unsourced_claims(
                    job, article_path, mode="remove")

                self.assertTrue(len(resolutions) > 0, "not_stated claim was not removed")
                self.assertNotIn("advanced", article_path.read_text())
            finally:
                import shutil
                shutil.rmtree(JOBS_DIR / "test-ns", ignore_errors=True)


class TestStructuralNoLocalVerification(unittest.TestCase):
    """(e) No local judge or authority-domain list outside shared module."""

    def _scan_for_local_definitions(self, filepath, forbidden_patterns):
        """Scan a Python file for forbidden local definitions."""
        source = filepath.read_text()
        tree = ast.parse(source)
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for pattern in forbidden_patterns:
                    if pattern in node.name.lower():
                        # Allow if it's a thin wrapper delegating to the shared module
                        body_src = ast.get_source_segment(source, node)
                        if body_src and ("_impl(" in body_src or "_judge_claim_impl" in body_src
                                         or "_search_authority_impl" in body_src
                                         or "verify_claim" in body_src):
                            continue
                        violations.append(
                            f"line {node.lineno}: def {node.name}()")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        for pattern in forbidden_patterns:
                            if pattern in name.lower():
                                # Allow re-exports from shared module
                                if isinstance(node.value, ast.Name):
                                    continue  # simple alias
                                violations.append(
                                    f"line {node.lineno}: {name} = ...")

        return violations

    def test_adversarial_review_uses_shared_module(self):
        """adversarial_review.py must not define its own judge, search, or
        authority domain list. It must load from source_verification.py."""
        ar_path = REPO_ROOT / "lib" / "adversarial_review.py"
        source = ar_path.read_text()
        self.assertIn(
            "source_verification",
            source,
            "adversarial_review.py does not reference source_verification"
        )

    def test_orchestrator_uses_shared_module(self):
        """orchestrator.py must not define its own judge, search, or
        authority domain list. It must import verify_claim from source_verification."""
        orch_path = MODULE_DIR / "lib" / "orchestrator.py"
        source = orch_path.read_text()
        self.assertIn(
            "source_verification",
            source,
            "orchestrator.py does not reference source_verification"
        )
        # Must NOT define a local judge or search
        violations = self._scan_for_local_definitions(
            orch_path,
            ["judge_source", "judge_claim", "search_authority",
             "search_for_claim", "verification_authority"],
        )
        self.assertEqual(
            violations, [],
            f"orchestrator.py defines local verification functions that "
            f"should be in lib/source_verification.py:\n"
            + "\n".join(violations)
        )


class TestJudgeStatesWithoutQuote(unittest.TestCase):
    """(f) Judge returns STATES without quote → NOT_STATED."""

    def test_states_without_quote_is_not_stated(self):
        """A STATES verdict with empty quote is downgraded to NOT_STATED."""
        from source_verification import judge_claim_against_source

        mock_response = MagicMock()
        mock_response.text = '{"verdict": "STATES", "quote": ""}'

        with patch("source_verification._get_llm_client") as mock_client:
            mock_client.return_value.call.return_value = mock_response
            verdict, quote = judge_claim_against_source(
                "Some source text about TLE.",
                "TLE lasts 14 days",
                source_url="https://example.gov",
            )

        self.assertEqual(verdict, "NOT_STATED",
                         "STATES without a quote must downgrade to NOT_STATED")
        self.assertEqual(quote, "")

    def test_states_with_quote_is_states(self):
        """A STATES verdict with a quote is preserved."""
        from source_verification import judge_claim_against_source

        mock_response = MagicMock()
        mock_response.text = '{"verdict": "STATES", "quote": "TLE is authorized for 21 days."}'

        with patch("source_verification._get_llm_client") as mock_client:
            mock_client.return_value.call.return_value = mock_response
            verdict, quote = judge_claim_against_source(
                "Some source text.",
                "TLE lasts 21 days",
                source_url="https://example.gov",
            )

        self.assertEqual(verdict, "STATES")
        self.assertEqual(quote, "TLE is authorized for 21 days.")


if __name__ == "__main__":
    unittest.main()
