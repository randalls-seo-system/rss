"""L32 mutation red runs — element-scoped removal.

Tests the resolver's element-scoped sentence-boundary search and the
structural-container guard. Uses real HTML from job ad111ecd for the
concrete 1d case.

Mutation tests:
  (a) Claim in <td> alongside SOURCE claim → only the target flagged,
      row survives. Revert to string arithmetic → test fails.
  (b) Claim as one sentence among several in <p> → only that sentence
      goes, period search bounded to the <p>.
  (c) Claim as whole content of <li> → flagged (would_empty_container),
      <ul> survives. If <li> has siblings, removal goes through.
  (d) Article with no claims to remove → byte-identical output.
  (1d) Real ad111ecd Table 1 Row 4: "Up to 14 days total" claim.
       With string arithmetic: 1,022 chars removed, table destroyed.
       With element-scoped: flagged as would_empty_container, table intact.
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.orchestrator import resolve_unsourced_claims, job_dir, JOBS_DIR


def _make_job(job_id, tmp_dir):
    jdir = Path(tmp_dir) / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id, "site": "test", "topic": "test",
        "post_id": 999, "stages": {},
        "created": datetime.now().isoformat(),
    }
    (jdir / "job.json").write_text(json.dumps(job))
    return job


def _setup_resolver(tmp, job_id, claims, article_html):
    """Create job dir with d2-claims-report.json and article, return (job, article_path)."""
    with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
        job = _make_job(job_id, tmp)
        jdir = Path(tmp) / job_id
        report = {"classified_claims": claims}
        (jdir / "d2-claims-report.json").write_text(json.dumps(report))
        article = jdir / "999-article.html"
        article.write_text(article_html)
        return job, article


# ─── Real HTML fixtures from job ad111ecd ─────────────────────────────

# Table 1 from the real article — the "Up to 14 days" row
REAL_TABLE_HTML = """<p>Previous paragraph with real content about TLE payment structure. Service members receive a per diem rate tied to their duty station.</p>
<table>
<thead>
<tr><th>Component</th><th>What You Receive</th><th>Key Limit</th></tr>
</thead>
<tbody>
<tr><td>Lodging</td><td>Actual nightly cost reimbursed up to the locality per diem lodging rate for your duty station.</td><td>Varies by location, up to $290/night in high-cost areas.</td></tr>
<tr><td>Meals and Incidentals</td><td>Flat daily rate from the per diem schedule for your location.</td><td>Set amount per day, not receipt-based</td></tr>
<tr><td>Maximum Duration</td><td>Up to 14 days total across both duty stations</td><td>Days can split between departing and arriving stations</td></tr>
<tr><td>Solo Member</td><td>Lower combined daily rate under single per diem schedule.</td><td>No dependent multiplier applied</td></tr>
</tbody>
</table>
<p>After the table, more content about filing procedures. Booking a hotel or extended-stay property early saves money.</p>"""

REAL_CLAIM_14_DAYS = {
    "claim": "TLE max duration up to 14 days total across both duty stations",
    "verbatim_text": "Up to 14 days total across both duty stations",
    "verbatim_verified": True,
    "section": "TLE Payment Amounts",
    "classification": "UNSOURCED",
    "suggestion": "Replace 14 days with 21 days per JTR.",
}


# ─── Mutation (1d): Real ad111ecd case — the concrete test ────────────

class TestRealTableClaim1d(unittest.TestCase):
    """The actual case from Phase 1 report: Table 1 Row 4 says
    'Up to 14 days total across both duty stations'. JTR says 21."""

    def test_element_scoped_flags_table_cell(self):
        """Element-scoped removal flags the <td> claim as
        would_empty_container. The table is intact."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job, article = _setup_resolver(
                    tmp, "test-1d-scoped",
                    [REAL_CLAIM_14_DAYS], REAL_TABLE_HTML)

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                # Claim flagged, not removed
                self.assertEqual(len(resolved), 0)
                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "would_empty_container")
                self.assertEqual(unresolved[0]["container_tag"], "td")
                self.assertIn("14 days", unresolved[0]["container_text"])
                self.assertIn("14 days", unresolved[0].get("verbatim_text", ""))

                # Table fully intact
                result_html = article.read_text()
                self.assertEqual(result_html, REAL_TABLE_HTML,
                                 "Article must be byte-identical — nothing removed")
                self.assertIn("<td>Up to 14 days total", result_html)
                self.assertIn("<td>Lodging</td>", result_html)
                self.assertIn("<td>Solo Member</td>", result_html)

    def test_string_arithmetic_destroys_table(self):
        """Prove the OLD behavior: rfind/find('.') on raw HTML spans
        across element boundaries and destroys the table structure.

        The target <td> has no periods. rfind('.') scans back past
        period-free cells to the paragraph before the table. find('.')
        scans forward to the next cell that has a period. The removal
        spans hundreds of characters across multiple HTML elements."""
        match_text = "Up to 14 days total across both duty stations"
        m = re.search(re.escape(match_text[:60]), REAL_TABLE_HTML)
        self.assertIsNotNone(m, "Claim must be found in the HTML")

        # Old boundary search — no element scope
        start = REAL_TABLE_HTML.rfind(".", 0, m.start())
        end = REAL_TABLE_HTML.find(".", m.end())

        # The target <td> has no period, so the backward search must
        # leave the <td> and land elsewhere. Verify it crossed a tag boundary.
        td_start = REAL_TABLE_HTML.rfind("<td", 0, m.start())
        self.assertLess(start, td_start,
                        "rfind('.') must land outside the target <td> — proves cross-element span")

        removal_size = end - start
        self.assertGreater(removal_size, 100,
                           f"Old removal spans {removal_size} chars — must be >100 to prove cross-element damage")

        # The removal would span across HTML tags
        removed_text = REAL_TABLE_HTML[start + 1:end + 1]
        self.assertTrue(
            "<td>" in removed_text or "</td>" in removed_text or "<tr>" in removed_text,
            f"Old removal must cross tag boundaries: {removed_text[:200]}"
        )


# ─── Mutation (a): Claim in <td> alongside SOURCE claim → row survives

class TestTableCellRowSurvives(unittest.TestCase):
    def test_unsourced_td_flagged_row_intact(self):
        """A <td> with an UNSOURCED claim in a row that also has SOURCE
        cells. The UNSOURCED cell is flagged; the row and its SOURCE
        cells survive."""
        table_html = """<p>Intro sentence here.</p>
<table>
<tr><td>Route</td><td>Entitlement</td><td>Duration</td></tr>
<tr><td>CONUS to CONUS</td><td>TLE</td><td>Up to 14 days</td></tr>
<tr><td>CONUS to OCONUS</td><td>TLA</td><td>Up to 60 days</td></tr>
</table>"""

        claims = [{
            "claim": "TLE duration 14 days",
            "verbatim_text": "Up to 14 days",
            "verbatim_verified": True,
            "section": "Comparison",
            "classification": "UNSOURCED",
            "suggestion": "Should be 21 days.",
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job, article = _setup_resolver(
                    tmp, "test-td-row", claims, table_html)

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "would_empty_container")

                result = article.read_text()
                # Row with SOURCE cells intact
                self.assertIn("<td>CONUS to CONUS</td>", result)
                self.assertIn("<td>TLE</td>", result)
                # Other row intact
                self.assertIn("<td>Up to 60 days</td>", result)


# ─── Mutation (b): Claim as one sentence among several in <p> ─────────

class TestSentenceInParagraph(unittest.TestCase):
    def test_one_sentence_removed_others_survive(self):
        """A <p> with three sentences. The middle one is UNSOURCED.
        Only the middle sentence is removed; the others survive."""
        html = "<p>First sentence is fine. The rate is 14 days which is wrong. Third sentence stays.</p>"
        claims = [{
            "claim": "rate is 14 days",
            "verbatim_text": "The rate is 14 days which is wrong",
            "verbatim_verified": True,
            "section": "Body",
            "classification": "UNSOURCED",
            "suggestion": "Fix.",
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job, article = _setup_resolver(
                    tmp, "test-p-sentence", claims, html)

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                self.assertEqual(len(resolved), 1)
                self.assertEqual(len(unresolved), 0)

                result = article.read_text()
                self.assertIn("First sentence is fine.", result)
                self.assertIn("Third sentence stays.", result)
                self.assertNotIn("14 days", result)


# ─── Mutation (c): Claim as whole <li> → flagged if it would empty ────

class TestListItemRemoval(unittest.TestCase):
    def test_li_with_siblings_removed(self):
        """An <li> containing the UNSOURCED claim, with sibling <li>s.
        The entire <li> element is removed; the <ul> survives."""
        html = """<ul>
<li>First item is sourced.</li>
<li>This item claims 14 days which is wrong.</li>
<li>Third item is fine.</li>
</ul>"""
        claims = [{
            "claim": "claims 14 days",
            "verbatim_text": "This item claims 14 days which is wrong",
            "verbatim_verified": True,
            "section": "List",
            "classification": "UNSOURCED",
            "suggestion": "Fix.",
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job, article = _setup_resolver(
                    tmp, "test-li-siblings", claims, html)

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                self.assertEqual(len(resolved), 1)
                self.assertEqual(len(unresolved), 0)

                result = article.read_text()
                self.assertIn("First item is sourced.", result)
                self.assertIn("Third item is fine.", result)
                self.assertNotIn("14 days", result)
                self.assertIn("<ul>", result, "UL must survive")

    def test_last_li_would_empty_ul(self):
        """Single <li> in a <ul>. Removing it would empty the <ul>.
        Must flag as would_empty_container, not cascade."""
        html = """<div class="rl-quick-card"><ul>
<li>This is the only item claiming 14 days.</li>
</ul></div>"""
        claims = [{
            "claim": "claiming 14 days",
            "verbatim_text": "This is the only item claiming 14 days",
            "verbatim_verified": True,
            "section": "Card",
            "classification": "UNSOURCED",
            "suggestion": "Fix.",
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job, article = _setup_resolver(
                    tmp, "test-li-empty", claims, html)

                _, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                self.assertEqual(len(unresolved), 1)
                self.assertEqual(unresolved[0]["reason"], "would_empty_container")

                result = article.read_text()
                self.assertIn("<ul>", result, "UL must survive")
                self.assertIn("rl-quick-card", result, "Card wrapper must survive")


# ─── Mutation (d): No claims to remove → byte-identical ───────────────

class TestByteIdenticalPassthrough(unittest.TestCase):
    def test_no_unsourced_byte_identical(self):
        """An article with no UNSOURCED claims passes through
        byte-identical — no BS4 parse, no normalization."""
        html = "<p>Clean article. All claims are sourced. No issues here.</p>"
        # All claims are SOURCE — none unsourced
        report_claims = [{
            "claim": "All claims are sourced",
            "verbatim_text": "All claims are sourced",
            "verbatim_verified": True,
            "section": "Body",
            "classification": "SOURCE",
        }]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("lib.orchestrator.JOBS_DIR", Path(tmp)):
                job = _make_job("test-passthrough", tmp)
                jdir = Path(tmp) / "test-passthrough"
                report = {"classified_claims": report_claims}
                (jdir / "d2-claims-report.json").write_text(json.dumps(report))
                article = jdir / "999-article.html"
                article.write_text(html)

                result_path, resolved, unresolved = resolve_unsourced_claims(
                    job, article, mode="remove")

                self.assertEqual(len(resolved), 0)
                self.assertEqual(len(unresolved), 0)
                self.assertEqual(article.read_text(), html,
                                 "Must be byte-identical — no parse, no normalization")


if __name__ == "__main__":
    unittest.main()
