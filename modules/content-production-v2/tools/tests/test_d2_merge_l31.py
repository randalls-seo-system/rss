"""L31 mutation red runs — D2 extraction→classification merge fix.

Tests the CODE between the two LLM calls: the id-based join that carries
verbatim_text from extraction to the final report. Mocks both LLM calls
with realistic responses — classification omits verbatim_text exactly as
the real model does.

Mutation tests:
  (a) Classification omits verbatim_text (realistic) → merged report still
      carries it. Remove the merge → test fails.
  (b) Classification returns a claim with an unknown id → hard failure.
  (c) Classification returns fewer claims than extraction → hard failure.
  (d) Join by claim text instead of id, with the model having altered one
      claim → test fails (proves id-join is load-bearing).
  (e) Validator runs only at extraction → the report the resolver reads
      has no post-merge validation. Test asserts the report IS validated.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.orchestrator import D2_RESULT_KEY


def _make_extraction_response(claims_with_verbatim):
    """Build a mock subprocess result for the extraction LLM call.
    claims_with_verbatim is a list of {claim, verbatim_text, section, claim_type}."""
    return MagicMock(
        returncode=0,
        stdout=json.dumps({"result": claims_with_verbatim}),
        stderr="",
    )


def _make_classification_response(classified):
    """Build a mock subprocess result for the classification LLM call.
    classified is a list of {id, classification, suggestion?} — NO verbatim_text."""
    return MagicMock(
        returncode=0,
        stdout=json.dumps({"result": classified}),
        stderr="",
    )


# ─── Fixtures: realistic extraction + classification outputs ──────────

EXTRACTION_CLAIMS = [
    {
        "claim": "TLE covers up to 14 days",
        "verbatim_text": "TLE covers up to 14 days of lodging and meals during your CONUS PCS move.",
        "section": "TLE at a Glance",
        "claim_type": "timeline",
    },
    {
        "claim": "TLA reimburses for up to 60 days overseas",
        "verbatim_text": "TLA reimburses for up to 60 days of temporary lodging at your overseas duty station.",
        "section": "TLA at a Glance",
        "claim_type": "timeline",
    },
    {
        "claim": "TLE capped at $290 per night",
        "verbatim_text": "TLE is capped at approximately $290 per night for lodging.",
        "section": "TLE Payment Amounts",
        "claim_type": "dollar_figure",
    },
]

# Classification response: realistic — only id + classification + suggestion.
# No verbatim_text, no claim, no section. Exactly what the real model returns.
CLASSIFICATION_RESPONSE = [
    {"id": "c000", "classification": "UNSOURCED", "suggestion": "Replace 14 days with 21 days."},
    {"id": "c001", "classification": "SOURCE"},
    {"id": "c002", "classification": "SOURCE"},
]

# Article HTML that contains the verbatim text
ARTICLE_HTML = """<div class="rl-page">
<p>TLE covers up to 14 days of lodging and meals during your CONUS PCS move.</p>
<p>TLA reimburses for up to 60 days of temporary lodging at your overseas duty station.</p>
<p>TLE is capped at approximately $290 per night for lodging.</p>
</div>"""


def _run_d2(article_html, extraction_claims, classification_response,
            tmp_dir, config=None):
    """Run run_d2_claims_check with mocked LLM calls."""
    from lib.orchestrator import run_d2_claims_check, JOBS_DIR

    if config is None:
        config = {"content": {}}

    job_id = f"test-l31-{id(extraction_claims)}"
    jdir = Path(tmp_dir) / job_id
    jdir.mkdir(parents=True, exist_ok=True)

    job = {
        "id": job_id,
        "site": "test",
        "topic": "test",
        "post_id": 999,
        "stages": {},
        "created": "2026-08-21T00:00:00",
    }
    (jdir / "job.json").write_text(json.dumps(job))

    ext_resp = _make_extraction_response(extraction_claims)
    cls_resp = _make_classification_response(classification_response)

    call_count = [0]
    def mock_subprocess_run(cmd, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return ext_resp
        return cls_resp

    with patch("lib.orchestrator.JOBS_DIR", Path(tmp_dir)):
        with patch("subprocess.run", side_effect=mock_subprocess_run):
            return run_d2_claims_check(article_html, config, job)


# ─── Mutation (a): Classification omits verbatim_text → merged report
#     still carries it. Remove the merge → test fails. ─────────────────

class TestMergeCarriesVerbatim(unittest.TestCase):
    def test_merged_report_has_verbatim_on_every_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                             CLASSIFICATION_RESPONSE, tmp)

            for claim in report["classified_claims"]:
                self.assertIn("verbatim_text", claim,
                              f"Claim {claim.get('id')} missing verbatim_text in merged report")
                self.assertTrue(len(claim["verbatim_text"]) > 0,
                                f"Claim {claim.get('id')} has empty verbatim_text")
                self.assertIn("verbatim_verified", claim,
                              f"Claim {claim.get('id')} missing verbatim_verified")
                self.assertIn("claim_type", claim,
                              f"Claim {claim.get('id')} missing claim_type")

    def test_verbatim_text_matches_extraction(self):
        """The verbatim_text in the report must be the extraction's value,
        not anything from classification."""
        with tempfile.TemporaryDirectory() as tmp:
            report = _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                             CLASSIFICATION_RESPONSE, tmp)

            for claim, expected in zip(report["classified_claims"],
                                       EXTRACTION_CLAIMS):
                self.assertEqual(claim["verbatim_text"],
                                 expected["verbatim_text"])

    def test_classification_fields_present(self):
        """Classification and suggestion must come from the classifier."""
        with tempfile.TemporaryDirectory() as tmp:
            report = _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                             CLASSIFICATION_RESPONSE, tmp)

            c000 = [c for c in report["classified_claims"] if c["id"] == "c000"][0]
            self.assertEqual(c000["classification"], "UNSOURCED")
            self.assertEqual(c000["suggestion"], "Replace 14 days with 21 days.")

            c001 = [c for c in report["classified_claims"] if c["id"] == "c001"][0]
            self.assertEqual(c001["classification"], "SOURCE")


# ─── Mutation (b): Unknown id → hard failure ──────────────────────────

class TestUnknownIdHardFailure(unittest.TestCase):
    def test_unknown_id_raises(self):
        bad_classification = [
            {"id": "c000", "classification": "SOURCE"},
            {"id": "c001", "classification": "SOURCE"},
            {"id": "c999", "classification": "UNSOURCED", "suggestion": "Bad id."},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                        bad_classification, tmp)
            self.assertIn("c999", str(ctx.exception))
            self.assertIn("unknown id", str(ctx.exception).lower())


# ─── Mutation (c): Fewer claims from classification → hard failure ────

class TestCountMismatchHardFailure(unittest.TestCase):
    def test_fewer_classified_raises(self):
        short_classification = [
            {"id": "c000", "classification": "SOURCE"},
            {"id": "c001", "classification": "SOURCE"},
            # c002 missing
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                        short_classification, tmp)
            self.assertIn("mismatch", str(ctx.exception).lower())

    def test_more_classified_raises(self):
        """Classification returns more claims than extraction — also a hard failure
        because the extra claim has an id not in extraction."""
        extra_classification = CLASSIFICATION_RESPONSE + [
            {"id": "c003", "classification": "SOURCE"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                        extra_classification, tmp)
            self.assertIn("c003", str(ctx.exception))


# ─── Mutation (d): Join by claim text with altered claim → fails ──────

class TestIdJoinNotTextJoin(unittest.TestCase):
    def test_altered_claim_text_still_joins_by_id(self):
        """The classification model slightly altered the claim text.
        If joining by text, this would silently drop the claim.
        ID-based join must succeed regardless."""
        altered_classification = [
            {"id": "c000", "classification": "UNSOURCED",
             "suggestion": "Fix it.", "claim": "TLE covers approx 14 days"},
            {"id": "c001", "classification": "SOURCE",
             "claim": "TLA reimburses up to sixty days overseas"},
            {"id": "c002", "classification": "SOURCE",
             "claim": "TLE capped around $290/night"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                             altered_classification, tmp)

            # All 3 claims present with correct verbatim from extraction
            self.assertEqual(len(report["classified_claims"]), 3)
            for claim, expected in zip(report["classified_claims"],
                                       EXTRACTION_CLAIMS):
                # claim text comes from EXTRACTION, not classification
                self.assertEqual(claim["claim"], expected["claim"])
                self.assertEqual(claim["verbatim_text"],
                                 expected["verbatim_text"])


# ─── Mutation (e): Post-merge validator runs on the report file ───────

class TestPostMergeValidatorRuns(unittest.TestCase):
    def test_report_file_has_verbatim_on_every_claim(self):
        """The d2-claims-report.json file (what the resolver reads) must
        have verbatim_text on every claim. This test reads the actual file,
        not just the return value."""
        with tempfile.TemporaryDirectory() as tmp:
            from lib.orchestrator import JOBS_DIR
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                report = _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                                 CLASSIFICATION_RESPONSE, tmp)

                # Find the report file
                job_dirs = [d for d in Path(tmp).iterdir() if d.is_dir()]
                self.assertEqual(len(job_dirs), 1)
                report_path = job_dirs[0] / "d2-claims-report.json"
                self.assertTrue(report_path.exists(),
                                "d2-claims-report.json must exist")

                file_report = json.loads(report_path.read_text())
                for claim in file_report["classified_claims"]:
                    self.assertIn("verbatim_text", claim,
                                  f"Report FILE claim {claim.get('id')} missing verbatim_text")
                    self.assertTrue(len(claim["verbatim_text"]) > 0,
                                    f"Report FILE claim {claim.get('id')} has empty verbatim_text")
                    self.assertIn("verbatim_verified", claim)

    def test_no_id_field_in_classification_raises(self):
        """If classification omits the id field entirely, hard failure."""
        no_id_classification = [
            {"classification": "SOURCE"},
            {"classification": "SOURCE"},
            {"classification": "UNSOURCED", "suggestion": "Fix."},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                        no_id_classification, tmp)
            self.assertIn("no 'id' field", str(ctx.exception).lower())


# ─── Mutation (extra): duplicate id in classification → hard failure ──

class TestDuplicateIdHardFailure(unittest.TestCase):
    def test_duplicate_id_raises(self):
        dup_classification = [
            {"id": "c000", "classification": "SOURCE"},
            {"id": "c000", "classification": "UNSOURCED", "suggestion": "Dup."},
            {"id": "c002", "classification": "SOURCE"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                _run_d2(ARTICLE_HTML, EXTRACTION_CLAIMS,
                        dup_classification, tmp)
            self.assertIn("duplicate", str(ctx.exception).lower())


# ─── Mutation: classification guard refuses id-less claims ────────────

class TestClassificationGuardRefusesIdless(unittest.TestCase):
    """run_claims_classification must raise if any claim lacks an id.
    Remove the guard → this test fails."""

    def test_idless_claim_raises(self):
        from lib.orchestrator import run_claims_classification
        claims_no_id = [
            {"claim": "Some factual assertion", "section": "Body"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                run_claims_classification(
                    claims_no_id, "", Path(tmp), Path(tmp)
                )
            self.assertIn("without 'id'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
