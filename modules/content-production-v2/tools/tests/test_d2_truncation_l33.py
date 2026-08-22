"""L33 mutation red runs — silent prompt-text truncation removal.

Seven magic-number truncations in orchestrator.py silently clipped LLM
prompt inputs. The extraction truncation (12K chars) dropped 42-48% of
articles. The classification truncations (2K-6K per source) caused
correctly-sourced claims to be classified UNSOURCED and removed —
content destruction from missing context.

All seven are replaced by _guard_prompt_text which passes text through
unchanged unless it exceeds a pathological ceiling (200K chars). When
the ceiling fires, it logs to stderr and records in the job directory.

Mutation tests:
  (a) Full article text reaches the extraction prompt — not truncated
      at the old 12K limit. Restore the truncation → the test fails.
  (b) Evidence beyond the old 6K cutoff is visible to the classifier.
      A claim whose source evidence is at char 7000 is classified
      SOURCE. Restore the 6K cutoff → it classifies UNSOURCED.
  (c) When the ceiling fires, it is logged and recorded in the job
      directory. Remove the recording → test fails.
  (d) Structural guard: no [:N] slice on a text variable in
      orchestrator.py outside _guard_prompt_text. Prevents the eighth
      silent truncation from accumulating.
"""

import ast
import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))


class TestL33ExtractionNotTruncated(unittest.TestCase):
    """(a) Full article text reaches the extractor — old 12K limit gone."""

    def test_full_article_in_extraction_prompt(self):
        """An article >12K chars appears in full in the extraction prompt.
        Mutation: restore text[:12000] → prompt is truncated → test fails."""
        from lib.orchestrator import run_claims_extraction

        # Build a 20K-char article (realistic size for VALN articles)
        section_a = "<p>" + "A" * 5000 + "</p>"
        section_b = "<p>" + "B" * 5000 + "</p>"
        section_c = "<p>" + "C" * 5000 + "</p>"
        tail_marker = "<p>UNIQUE_TAIL_MARKER_XYZ_789</p>"
        html = f"<div>{section_a}{section_b}{section_c}{tail_marker}</div>"

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)

            # Mock the subprocess call to capture the prompt
            mock_result = MagicMock(
                returncode=0,
                stdout=json.dumps({"result": []}),
                stderr="",
            )
            with patch("subprocess.run", return_value=mock_result):
                run_claims_extraction(html, job_path)

            # Read the prompt file that was written
            prompt_path = job_path / "d2-extraction-prompt.txt"
            self.assertTrue(prompt_path.exists(), "Extraction prompt not written")
            prompt_text = prompt_path.read_text()

            # The tail marker (beyond old 12K) MUST appear in the prompt.
            # If text[:12000] is restored, this fails.
            self.assertIn(
                "UNIQUE_TAIL_MARKER_XYZ_789", prompt_text,
                "Article tail beyond 12K chars was truncated from extraction prompt. "
                "The old text[:12000] truncation may have been restored."
            )

    def test_table_cell_beyond_12k_is_extractable(self):
        """Specific regression: a table cell at char ~13K is visible to the
        extractor. This is the exact failure from job ad111ecd where Table 2
        Row 4 ('Up to 14 days total across both duty stations') was missed."""
        from lib.orchestrator import run_claims_extraction

        # Build an article where a table appears after 12K chars of prose
        prose = "<p>" + ("Lorem ipsum dolor sit amet. " * 200) + "</p>"
        table = textwrap.dedent("""\
            <table>
            <tr><th>Component</th><th>Limit</th></tr>
            <tr><td>Maximum Duration</td><td>Up to 14 days total across both duty stations</td></tr>
            </table>""")
        html = f"<div>{prose}{table}</div>"

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)

            mock_result = MagicMock(
                returncode=0,
                stdout=json.dumps({"result": []}),
                stderr="",
            )
            with patch("subprocess.run", return_value=mock_result):
                run_claims_extraction(html, job_path)

            prompt_text = (job_path / "d2-extraction-prompt.txt").read_text()
            self.assertIn(
                "14 days total across both duty stations", prompt_text,
                "Table cell beyond 12K was truncated from extraction prompt."
            )


class TestL33ClassificationEvidenceNotTruncated(unittest.TestCase):
    """(b) Evidence beyond the old 6K cutoff reaches the classifier."""

    def test_evidence_beyond_6k_visible_to_classifier(self):
        """A claim sourced by evidence at char 7000 classifies as SOURCE.
        Mutation: restore ev_prose[:6000] → evidence clipped → classifier
        cannot see the source → claim classifies UNSOURCED → test fails."""
        from lib.orchestrator import run_claims_classification

        # Build claims
        claims = [
            {"id": "c000", "claim": "TLE lasts up to 21 days", "section": "Overview"},
        ]

        # Build evidence that is 8K chars — the sourcing passage is at char 7000
        padding = "x" * 6500
        source_passage = (
            '\n\nSource: JTR Chapter 10 — "TLE is authorized for up to 21 '
            'calendar days during a CONUS PCS move." '
            '(https://www.travel.dod.mil/jtr)\n\n'
        )
        evidence_tail = "y" * 500
        evidence_text = padding + source_passage + evidence_tail

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            scan_dir = Path(tmpdir)

            # Write evidence file that render_evidence_block will return
            ev_data = [{"url": "https://jtr.example.com", "passages": [evidence_text]}]
            (scan_dir / "30448-evidence.json").write_text(json.dumps(ev_data))

            # Mock the classification LLM call — capture the prompt it receives
            captured_prompts = []

            def mock_run(cmd, **kwargs):
                # Read the temp file that classification writes
                # The command is: cat "<tmpfile>" | claude -p - --output-format json
                import re as _re
                m = _re.search(r'cat "([^"]+)"', cmd)
                if m:
                    prompt_content = Path(m.group(1)).read_text()
                    captured_prompts.append(prompt_content)
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({"result": [
                        {"id": "c000", "classification": "SOURCE"},
                    ]}),
                    stderr="",
                )

            # Mock render_evidence_block to return our long evidence
            with patch("subprocess.run", side_effect=mock_run):
                with patch("lib.evidence.render_evidence_block", return_value=evidence_text):
                    result = run_claims_classification(
                        claims, "", scan_dir, job_path,
                    )

            # The classification prompt must contain the source passage.
            # With the old [:6000] truncation, this passage at char 7000
            # would be clipped and the claim would go UNSOURCED.
            self.assertTrue(len(captured_prompts) > 0, "Classification prompt not captured")
            self.assertIn(
                "TLE is authorized for up to 21", captured_prompts[0],
                "Evidence beyond old 6K cutoff was truncated from classification "
                "prompt. The claim's source material was clipped."
            )

            # Verify the classification result
            self.assertEqual(result[0]["classification"], "SOURCE")


class TestL33GuardLogging(unittest.TestCase):
    """(c) When the pathological ceiling fires, it logs and records."""

    def test_guard_records_truncation_in_job_dir(self):
        """Ceiling exceeded → truncation-warnings.json written to job dir.
        Remove the recording → test fails."""
        from lib.orchestrator import _guard_prompt_text, PROMPT_TEXT_CEILING

        # Build text that exceeds the ceiling
        huge_text = "Z" * (PROMPT_TEXT_CEILING + 1000)

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            result = _guard_prompt_text(huge_text, "test_label", job_path)

            # Text should be truncated to ceiling
            self.assertEqual(len(result), PROMPT_TEXT_CEILING)

            # Warning must be recorded in the job directory
            warnings_path = job_path / "truncation-warnings.json"
            self.assertTrue(
                warnings_path.exists(),
                "Guard fired but did not write truncation-warnings.json"
            )
            warnings = json.loads(warnings_path.read_text())
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["label"], "test_label")
            self.assertEqual(warnings[0]["original_chars"], PROMPT_TEXT_CEILING + 1000)
            self.assertEqual(warnings[0]["ceiling"], PROMPT_TEXT_CEILING)
            self.assertIn("timestamp", warnings[0])

    def test_guard_passes_normal_text_unchanged(self):
        """Normal-sized text passes through without truncation or logging."""
        from lib.orchestrator import _guard_prompt_text

        normal_text = "Hello world " * 100  # ~1200 chars

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            result = _guard_prompt_text(normal_text, "test_normal", job_path)

            self.assertEqual(result, normal_text)
            warnings_path = job_path / "truncation-warnings.json"
            self.assertFalse(
                warnings_path.exists(),
                "Guard wrote warnings for normal-sized text"
            )

    def test_guard_appends_to_existing_warnings(self):
        """Multiple guard fires accumulate in the same file."""
        from lib.orchestrator import _guard_prompt_text, PROMPT_TEXT_CEILING

        huge = "A" * (PROMPT_TEXT_CEILING + 100)

        with tempfile.TemporaryDirectory() as tmpdir:
            job_path = Path(tmpdir)
            _guard_prompt_text(huge, "first", job_path)
            _guard_prompt_text(huge, "second", job_path)

            warnings = json.loads((job_path / "truncation-warnings.json").read_text())
            self.assertEqual(len(warnings), 2)
            self.assertEqual(warnings[0]["label"], "first")
            self.assertEqual(warnings[1]["label"], "second")


class TestL33StructuralNoSilentTruncation(unittest.TestCase):
    """(d) No new silent truncation can accumulate in orchestrator.py.

    Scans the source AST for slice operations [:N] where N >= 1000 on
    string-typed expressions. Every such slice must be inside
    _guard_prompt_text itself. A new truncation added anywhere else
    fails this test.
    """

    def test_no_large_slice_outside_guard(self):
        """No hardcoded [:N>=1000] integer slice in orchestrator.py outside
        _guard_prompt_text. A new magic-number truncation → test fails.

        Only catches HARDCODED INTEGER constants (the L33 pattern:
        text[:12000], ev_prose[:6000], etc.). Variable-based slices
        (html[start:end], html[:removal_start]) are programmatic
        substring operations, not silent truncations."""
        src_path = MODULE_DIR / "lib" / "orchestrator.py"
        source = src_path.read_text()
        tree = ast.parse(source)

        violations = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            sl = node.slice
            if not isinstance(sl, ast.Slice):
                continue
            if sl.upper is None:
                continue
            # ONLY hardcoded integer constants >= 1000
            if not isinstance(sl.upper, ast.Constant):
                continue
            if not isinstance(sl.upper.value, int):
                continue
            limit = sl.upper.value
            if limit < 1000:
                continue

            enclosing_func = _find_enclosing_function(tree, node)
            if enclosing_func == "_guard_prompt_text":
                continue

            line = source.split("\n")[node.lineno - 1] if node.lineno else ""

            violations.append(
                f"  line {node.lineno}: [:{limit}] in "
                f"{enclosing_func or '<module>'}: {line.strip()[:100]}"
            )

        self.assertEqual(
            violations, [],
            f"Found hardcoded large-slice truncation(s) outside "
            f"_guard_prompt_text in orchestrator.py. Every prompt-text "
            f"truncation must go through the guard function (L33):\n"
            + "\n".join(violations)
        )


def _find_enclosing_function(tree, target_node):
    """Find the function name that encloses a given AST node."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target_node:
                    return node.name
    return None


if __name__ == "__main__":
    unittest.main()
