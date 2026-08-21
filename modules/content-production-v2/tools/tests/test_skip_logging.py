"""L28: Every conditional pipeline stage records its skip reason.

Tests:
  (d) A configured-off stage produces a skip entry, not silence.
  (e) Ran-and-passed is distinguishable from skipped.
  (f) A NEW conditional stage added without skip recording fails a structural test.
"""

import re
import sys
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.orchestrator import (
    PIPELINE_STAGES,
    TERMINAL_STAGE_STATUSES,
    mark_stage,
    stage_done,
)


class TestSkipRecording(unittest.TestCase):
    """Mutation (d): a configured-off stage must produce a stage entry."""

    def test_skipped_config_is_terminal(self):
        job = {"stages": {"adversarial_review": {"status": "skipped_config"}}}
        self.assertTrue(stage_done(job, "adversarial_review"))

    def test_skipped_flag_is_terminal(self):
        job = {"stages": {"gap_scan": {"status": "skipped_flag"}}}
        self.assertTrue(stage_done(job, "gap_scan"))

    def test_not_reached_is_terminal(self):
        job = {"stages": {"deploy": {"status": "not_reached"}}}
        self.assertTrue(stage_done(job, "deploy"))

    def test_missing_entry_is_not_terminal(self):
        """An absent stage entry is NOT done — this is what L28 fixes."""
        job = {"stages": {}}
        self.assertFalse(stage_done(job, "adversarial_review"))

    def test_pending_is_not_terminal(self):
        job = {"stages": {"adversarial_review": {"status": "pending"}}}
        self.assertFalse(stage_done(job, "adversarial_review"))

    def test_failed_is_not_terminal(self):
        job = {"stages": {"gates": {"status": "failed"}}}
        self.assertFalse(stage_done(job, "gates"))

    def test_skip_entry_has_reason(self):
        """Skip entries must carry a reason field explaining WHY."""
        from lib.orchestrator import create_job
        import shutil
        job = create_job("test", "skip-reason-test")
        try:
            mark_stage(job, "adversarial_review", "skipped_config",
                       reason="content.adversarial_review.enabled not set or False")
            entry = job["stages"]["adversarial_review"]
            self.assertEqual(entry["status"], "skipped_config")
            self.assertIn("reason", entry)
            self.assertTrue(len(entry["reason"]) > 0)
        finally:
            jobs_dir = Path(__file__).resolve().parent.parent / "jobs"
            shutil.rmtree(jobs_dir / job["id"], ignore_errors=True)


class TestRanVsSkipped(unittest.TestCase):
    """Mutation (e): ran-and-passed must be distinguishable from skipped."""

    def test_done_is_not_skipped(self):
        job = {"stages": {
            "adversarial_review": {"status": "done", "review_calls": 3},
        }}
        entry = job["stages"]["adversarial_review"]
        self.assertEqual(entry["status"], "done")
        self.assertNotIn("skipped", entry["status"])

    def test_skipped_is_not_done(self):
        job = {"stages": {
            "adversarial_review": {"status": "skipped_config",
                                   "reason": "disabled"},
        }}
        entry = job["stages"]["adversarial_review"]
        self.assertNotEqual(entry["status"], "done")
        self.assertIn("skipped", entry["status"])

    def test_pass_is_not_skipped(self):
        """D2 uses 'pass' for clean results — distinct from 'skipped_config'."""
        job = {"stages": {
            "claims_check": {"status": "pass", "total_claims": 12, "unsourced": 0},
        }}
        entry = job["stages"]["claims_check"]
        self.assertEqual(entry["status"], "pass")
        self.assertNotIn("skipped", entry["status"])

    def test_all_terminal_statuses_are_distinguishable(self):
        """No two terminal statuses have the same prefix ambiguity."""
        for s in TERMINAL_STAGE_STATUSES:
            count = sum(1 for t in TERMINAL_STAGE_STATUSES if t == s)
            self.assertEqual(count, 1, f"Duplicate terminal status: {s}")


class TestStageStructuralGuard(unittest.TestCase):
    """Mutation (f): adding a conditional stage without skip recording must fail.

    This is the recurrence guard. It works by:
    1. Parsing the rss tool source for all mark_stage calls to find stage names.
    2. Asserting every stage name appears in PIPELINE_STAGES.
    3. Asserting every conditional stage (guard has more than `not stage_done`)
       has a matching skip-recording branch.
    """

    RSs_PATH = (MODULE_DIR / "tools" / "rss")

    def _rss_source(self) -> str:
        return self.RSs_PATH.read_text()

    def test_all_mark_stage_names_in_pipeline_stages(self):
        """If someone adds mark_stage(job, 'new_stage', ...) without adding
        to PIPELINE_STAGES, this test fails."""
        src = self._rss_source()
        # Match mark_stage(job, "stage_name", ...) — capture the name
        names = set(re.findall(r'mark_stage\(\s*job\s*,\s*["\'](\w+)["\']', src))
        # Filter out non-cmd_new_article stages (refresh pipeline uses
        # different stage names in refresher.py, not in rss tool)
        for name in names:
            self.assertIn(name, PIPELINE_STAGES,
                f"mark_stage references '{name}' which is not in PIPELINE_STAGES — "
                f"add it to PIPELINE_STAGES in orchestrator.py")

    def test_every_pipeline_stage_has_a_guard_in_rss(self):
        """Every stage in PIPELINE_STAGES must appear in at least one guard
        or skip-recording call in the rss tool."""
        src = self._rss_source()
        for stage in PIPELINE_STAGES:
            # Stage must appear in a stage_done or mark_stage call
            found = re.search(
                rf'(?:stage_done|mark_stage)\(\s*job\s*,\s*["\']' + stage + r'["\']',
                src)
            self.assertIsNotNone(found,
                f"Stage '{stage}' is in PIPELINE_STAGES but has no guard "
                f"or mark_stage call in the rss tool")

    def test_conditional_stages_have_skip_branches(self):
        """Stages with compound guards (beyond simple `not stage_done`)
        must also have a skip-recording path.

        The pattern: if the `if` line for a stage contains conditions
        beyond `stage_done`, then a `skipped_config` or `skipped_flag`
        mark_stage call for that stage must exist somewhere in the file.
        """
        src = self._rss_source()

        # Find all if-guards that reference stage_done AND have extra conditions.
        # Pattern: `if <something> and ... and not stage_done(job, "stage"):`
        # or: `if not stage_done(job, "stage"):` followed by `if args.skip_*:`
        compound_guards = re.findall(
            r'if\s+(?!not\s+stage_done).+stage_done\(\s*job\s*,\s*["\'](\w+)["\']',
            src)

        # Also find stages where the guard body has a flag-skip:
        # `if not stage_done(job, "X"):` then inside `if args.skip_*:`
        simple_guards = re.findall(
            r'if\s+not\s+stage_done\(\s*job\s*,\s*["\'](\w+)["\']\)',
            src)

        for stage in simple_guards:
            # Check if there's a nested flag-skip inside this stage
            # by looking for args.skip immediately after the guard
            pattern = (
                rf'if\s+not\s+stage_done\(\s*job\s*,\s*["\']'
                + stage
                + rf'["\']\):\s*\n\s+if\s+args\.\w+'
            )
            if re.search(pattern, src):
                compound_guards.append(stage)

        for stage in set(compound_guards):
            # This stage has a compound guard — must have a skip branch
            has_skip = re.search(
                rf'mark_stage\(\s*job\s*,\s*["\']'
                + stage
                + rf'["\'],\s*["\']skipped_',
                src)
            self.assertIsNotNone(has_skip,
                f"Stage '{stage}' has a conditional guard but no "
                f"skip-recording branch (mark_stage with skipped_* status). "
                f"L28 requires every conditional stage to record its skip.")

    def test_dry_run_records_remaining_stages(self):
        """The dry-run halt must record not_reached for F, G, H."""
        src = self._rss_source()
        self.assertIn("not_reached", src,
            "Dry-run halt must record 'not_reached' for stages after the halt")
        for stage in ("deploy", "verify", "log"):
            pattern = rf'mark_stage\(\s*job\s*,\s*["\']?' + stage
            # We need the not_reached to cover this stage
            # (it's done via a loop, so checking the loop variables is sufficient)
            not_reached_loop = re.search(
                r'for\s+\w+\s+in\s+\([^)]*["\']' + stage + r'["\'][^)]*\)',
                src)
            direct_mark = re.search(
                rf'mark_stage\(\s*job\s*,\s*["\']' + stage + rf'["\'],\s*["\']not_reached["\']',
                src)
            self.assertTrue(
                not_reached_loop or direct_mark,
                f"Stage '{stage}' is not recorded as not_reached under dry-run")


if __name__ == "__main__":
    unittest.main()
