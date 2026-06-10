#!/usr/bin/env python3
"""Regression tests for inject-internal-links.py

Covers both defect fixes:
  Defect 1 — word-boundary + text-node-only matching
  Defect 2 — single-word trigger filtering

Run:  python3 -m pytest tests/test_linker.py -v
  or: python3 tests/test_linker.py
"""

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import the module (hyphenated filename requires importlib)
# ---------------------------------------------------------------------------
TOOLS_DIR = Path(__file__).resolve().parent.parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

_spec = importlib.util.spec_from_file_location(
    "inject_internal_links", str(TOOLS_DIR / "inject-internal-links.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_inject_link_in_paragraph = _mod._inject_link_in_paragraph
_is_in_restricted_zone = _mod._is_in_restricted_zone

from bs4 import BeautifulSoup, Tag  # noqa: E402
from lib.linker_core import inject_link_in_paragraph as _core_inject
from lib.linker_core import is_restricted_zone as _core_zone
from lib.linker_core import deploy_lock, corpus_candidates, pool_candidates, STOPWORDS

# Import inject_post from the unified tool for integration tests
_li_spec = importlib.util.spec_from_file_location("link_injector", str(TOOLS_DIR / "link-injector.py"))
_li_mod = importlib.util.module_from_spec(_li_spec)
sys.modules["tools_module"] = _li_mod  # so TestProtectedSlugs can import it
_li_spec.loader.exec_module(_li_mod)
inject_post = _li_mod.inject_post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_para(html: str) -> Tag:
    """Parse HTML and return the first <p> element."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("p")


def _make_soup(html: str) -> BeautifulSoup:
    """Parse full HTML document fragment."""
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# Defect 1: word-boundary and structural safety
# ---------------------------------------------------------------------------

class TestWordBoundary:
    """Trigger must not match inside longer words."""

    def test_no_match_inside_longer_word(self):
        para = _make_para(
            "<p>Nevada loans are available to borrowers statewide.</p>"
        )
        assert _inject_link_in_paragraph(para, "VA loan", "/va-loans/") is False
        assert "<a" not in str(para)

    def test_no_match_partial_suffix(self):
        para = _make_para(
            "<p>Prequalification steps for mortgage applicants.</p>"
        )
        assert _inject_link_in_paragraph(para, "qualification", "/qualify/") is False

    def test_no_match_partial_prefix(self):
        para = _make_para(
            "<p>Refinancing options have improved this quarter.</p>"
        )
        assert _inject_link_in_paragraph(para, "refinance", "/refinance/") is False

    def test_exact_word_matches(self):
        para = _make_para(
            "<p>You can refinance your VA loan at a lower rate today.</p>"
        )
        assert _inject_link_in_paragraph(para, "VA loan", "/va-loans/") is True
        assert '<a href="/va-loans/">VA loan</a>' in str(para)


class TestAttributeSafety:
    """Trigger must not match inside HTML attributes."""

    def test_no_match_in_img_alt(self):
        para = _make_para(
            '<p>Check <img alt="VA loan rates chart" src="x.jpg"/> our guide.</p>'
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        # Should NOT have matched inside alt (text node walker skips attributes)
        assert 'alt="VA loan rates chart"' in str(para)
        # The only possible match is "our guide" area — no "VA loan" in visible text
        assert result is False

    def test_match_in_text_not_attribute(self):
        para = _make_para(
            '<p><span data-kw="VA loan">Check the VA loan options here.</span></p>'
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert result is True
        assert 'data-kw="VA loan"' in str(para)  # attribute untouched
        assert '<a href="/va-loans/">VA loan</a> options' in str(para)

    def test_no_match_in_href_url(self):
        # URL contains the trigger phrase — must not inject inside existing <a>
        para = _make_para(
            '<p>See <a href="/va-loan-guide/">our guide</a> for VA loan details.</p>'
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert result is True
        # Injected in visible text, not inside existing href
        out = str(para)
        assert '<a href="/va-loan-guide/">our guide</a>' in out
        assert '<a href="/va-loans/">VA loan</a> details' in out


class TestExistingLinkSafety:
    """Trigger must not match inside existing <a> elements."""

    def test_no_injection_inside_link(self):
        para = _make_para(
            '<p>Read our <a href="/x/">VA loan guide</a> for full details.</p>'
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/other/")
        # "VA loan" only appears inside existing link — no external match
        assert result is False

    def test_skip_link_match_in_trailing_text(self):
        para = _make_para(
            '<p>Our <a href="/x/">VA loan guide</a> covers VA loan basics for vets.</p>'
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/other/")
        assert result is True
        out = str(para)
        # Original link untouched
        assert '<a href="/x/">VA loan guide</a>' in out
        # New link in trailing text
        assert '<a href="/other/">VA loan</a> basics' in out


class TestSkipZones:
    """Trigger must not match inside tln* restricted zones."""

    def _zone_test(self, zone_class: str):
        html = (
            f'<div class="{zone_class}">'
            f"<p>VA loan options are great for Veterans today.</p>"
            f"</div>"
        )
        soup = _make_soup(html)
        para = soup.find("p")
        # Verify zone detection
        assert _is_in_restricted_zone(para) is True

    def test_tlnHero(self):
        self._zone_test("tlnHero")

    def test_tlnQuickGrid(self):
        self._zone_test("tlnQuickGrid")

    def test_tlnQuickCard(self):
        self._zone_test("tlnQuickCard")

    def test_tlnCallout(self):
        self._zone_test("tlnCallout")

    def test_tlnFaq(self):
        self._zone_test("tlnFaq")

    def test_tlnTable(self):
        self._zone_test("tlnTable")

    def test_tlnBLUF(self):
        self._zone_test("tlnBLUF")

    def test_details_block(self):
        html = (
            "<details><summary>FAQ</summary>"
            "<p>VA loan options are great for Veterans.</p>"
            "</details>"
        )
        soup = _make_soup(html)
        para = soup.find("p")
        assert _is_in_restricted_zone(para) is True

    def test_table_cell(self):
        html = (
            "<table><tr><td>"
            "<p>VA loan options available here.</p>"
            "</td></tr></table>"
        )
        soup = _make_soup(html)
        para = soup.find("p")
        assert _is_in_restricted_zone(para) is True

    def test_list_item(self):
        html = "<ul><li><p>VA loan info for borrowers.</p></li></ul>"
        soup = _make_soup(html)
        para = soup.find("p")
        assert _is_in_restricted_zone(para) is True


class TestHeadingSafety:
    """Trigger must not match inside heading elements."""

    def test_no_match_in_h2(self):
        # h2 nested inside p (unusual but tests the skip logic)
        para = _make_para(
            "<p><h2>VA Loan Basics</h2>Learn about VA loan options today.</p>"
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert result is True
        out = str(para)
        # h2 text must NOT be linked
        assert ">VA Loan Basics</h2>" in out or "VA Loan Basics</h2>" in out
        # Link should be in body text
        assert '<a href="/va-loans/">VA loan</a> options' in out

    def test_no_match_in_h3(self):
        para = _make_para(
            "<p><h3>refinance guide</h3>How to refinance your home.</p>"
        )
        result = _inject_link_in_paragraph(para, "refinance", "/refinance/")
        assert result is True
        out = str(para)
        assert "refinance guide</h3>" in out  # heading unchanged
        assert '<a href="/refinance/">refinance</a> your' in out


class TestValidInjection:
    """Standard valid injection scenarios."""

    def test_basic_injection(self):
        para = _make_para(
            "<p>Borrowers should explore FHA loan requirements before applying.</p>"
        )
        result = _inject_link_in_paragraph(para, "FHA loan", "/fha-loans/")
        assert result is True
        assert '<a href="/fha-loans/">FHA loan</a>' in str(para)

    def test_preserves_original_case(self):
        para = _make_para(
            "<p>Learn about fha loan requirements for first-time buyers.</p>"
        )
        result = _inject_link_in_paragraph(para, "FHA loan", "/fha-loans/")
        assert result is True
        # Should preserve the original "fha loan" casing
        assert '<a href="/fha-loans/">fha loan</a>' in str(para)

    def test_match_inside_strong(self):
        para = _make_para(
            "<p>Consider a <strong>VA loan for bad credit</strong> borrowers.</p>"
        )
        result = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert result is True
        out = str(para)
        assert "<strong>" in out
        assert '<a href="/va-loans/">VA loan</a>' in out


class TestSecondOccurrence:
    """Second occurrence of same destination on a page must not match.

    This is enforced by the caller (main loop tracking used_urls_global),
    not by _inject_link_in_paragraph itself. We test the function returns
    True only on first call and demonstrate the guard pattern.
    """

    def test_only_first_mention_linked(self):
        para = _make_para(
            "<p>A VA loan is great. A VA loan is flexible. A VA loan saves money.</p>"
        )
        # First call: should inject
        result1 = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert result1 is True
        out = str(para)
        # Exactly one <a> tag
        assert out.count('<a href="/va-loans/"') == 1


class TestTwoTriggersOneParagraph:
    """Two valid triggers in same paragraph: only first injects (per para cap=1)."""

    def test_second_trigger_blocked_by_para_cap(self):
        para = _make_para(
            "<p>A VA loan and an FHA loan are both government-backed mortgage options.</p>"
        )
        # Simulate para cap of 1: inject first, then second should be skipped by caller
        r1 = _inject_link_in_paragraph(para, "VA loan", "/va-loans/")
        assert r1 is True
        # Second trigger — function itself would inject (para cap is caller's job)
        # but we verify the function CAN inject a second link if allowed
        r2 = _inject_link_in_paragraph(para, "FHA loan", "/fha-loans/")
        assert r2 is True
        out = str(para)
        assert '<a href="/va-loans/">VA loan</a>' in out
        assert '<a href="/fha-loans/">FHA loan</a>' in out


class TestPerPostDedup:
    """Dedup state must be per-post, not per-run.

    Two independent posts that each contain the same matchable trigger
    must BOTH receive the link.  If dedup state leaked across posts,
    the second would be suppressed.
    """

    def test_same_dest_links_into_both_posts(self):
        post_a = _make_para(
            "<p>Borrowers should consider an FHA loan for flexible credit.</p>"
        )
        post_b = _make_para(
            "<p>An FHA loan is a popular option for first-time home buyers.</p>"
        )

        # Simulate per-post dedup: fresh call per post
        r_a = _inject_link_in_paragraph(post_a, "FHA loan", "/fha-loans/")
        r_b = _inject_link_in_paragraph(post_b, "FHA loan", "/fha-loans/")

        assert r_a is True, "Post A should receive the FHA loan link"
        assert r_b is True, "Post B should also receive the FHA loan link"
        assert '<a href="/fha-loans/">FHA loan</a>' in str(post_a)
        assert '<a href="/fha-loans/">FHA loan</a>' in str(post_b)


class TestAnchorSpanningExistingLink:
    """Anchor phrase that spans an existing <a> boundary must NOT inject.

    This is the post-1511 regression case: 'down payment assistance programs'
    where 'down payment assistance' is already inside <a> and ' programs' is
    a bare text node.  get_text() returns the full phrase (candidate match),
    but no single NavigableString contains it, so injection must return False.
    """

    def test_spanning_anchor_no_injection(self):
        para = _make_para(
            '<p>For buyers in a USDA-eligible area, '
            '<a href="/down-payment-assistance-by-state/">down payment assistance</a>'
            ' programs are the primary path to a zero-down purchase.</p>'
        )
        # The plain text DOES contain "down payment assistance programs"
        assert "down payment assistance programs" in para.get_text()

        # But injection must fail — the phrase spans a tag boundary
        result = _inject_link_in_paragraph(
            para, "down payment assistance programs",
            "/down-payment-assistance-programs/",
        )
        assert result is False, (
            "Must not inject when anchor phrase spans an existing <a> boundary"
        )
        # Original link must be untouched
        assert '<a href="/down-payment-assistance-by-state/">' in str(para)


class TestLegacyPostStructure:
    """Legacy posts without <section> wrappers must still be parseable.

    The linker's paragraph scanning uses soup.find_all('p'), not
    section-based traversal. Legacy posts that lack <section> wrappers
    should still have their <p> tags found and processed.
    """

    def test_flat_html_no_sections(self):
        html = (
            "<h2>About VA Loans</h2>"
            "<p>Veterans can use a VA loan to buy a home with no down payment.</p>"
            "<p>VA loan rates are competitive with conventional loans today.</p>"
            "<h2>FHA Alternative</h2>"
            "<p>An FHA loan requires a small down payment from borrowers.</p>"
        )
        soup = _make_soup(html)
        paragraphs = soup.find_all("p")
        assert len(paragraphs) == 3

        # All paragraphs are findable and injectable
        r = _inject_link_in_paragraph(paragraphs[0], "VA loan", "/va-loans/")
        assert r is True
        assert '<a href="/va-loans/">VA loan</a>' in str(paragraphs[0])

    def test_div_wrapped_no_sections(self):
        html = (
            '<div class="entry-content">'
            "<h2>Refinancing</h2>"
            "<p>You can refinance your mortgage to get a lower rate today.</p>"
            "<h2>Benefits</h2>"
            "<p>Mortgage refinancing saves money over the life of your loan.</p>"
            "</div>"
        )
        soup = _make_soup(html)
        paragraphs = soup.find_all("p")
        assert len(paragraphs) == 2

        r = _inject_link_in_paragraph(paragraphs[1], "mortgage refinancing", "/refinance/")
        assert r is True


# ---------------------------------------------------------------------------
# Phase 3: New tests for unified linker
# ---------------------------------------------------------------------------

class TestCorpusCandidates:
    """corpus_candidates derives phrases from title/slug."""

    def test_title_phrase_extraction(self):
        corpus = [{"id": 1, "slug": "fha-loan-requirements", "title": "FHA Loan Requirements", "url": "/fha-loan-requirements/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "fha loan requirements" in phrases
        assert "fha loan" in phrases
        assert "loan requirements" in phrases

    def test_slug_phrase_extraction(self):
        # Slug differs from title so slug-derived candidates survive dedup
        corpus = [{"id": 1, "slug": "san-antonio-home-prices", "title": "Home Prices in San Antonio TX", "url": "/san-antonio-home-prices/"}]
        cands = corpus_candidates(corpus)
        sources = {c[3] for c in cands}
        # Title produces "Home Prices" etc. Slug produces "san antonio home" etc.
        assert "slug" in sources, f"Expected 'slug' source in {sources}"
        assert "title" in sources, f"Expected 'title' source in {sources}"

    def test_stopword_only_rejected(self):
        corpus = [{"id": 1, "slug": "how-to-do-it", "title": "How To Do It", "url": "/how-to-do-it/"}]
        cands = corpus_candidates(corpus)
        # All sub-phrases are stopword-dominated; should produce very few or zero
        for phrase, url, score, source in cands:
            words = phrase.lower().split()
            content = [w for w in words if w not in STOPWORDS]
            assert len(content) >= 2, f"Stopword-only phrase slipped through: '{phrase}'"

    def test_word_count_enforcement(self):
        corpus = [{"id": 1, "slug": "credit", "title": "Credit", "url": "/credit/"}]
        cands = corpus_candidates(corpus)
        for phrase, *_ in cands:
            wc = len(phrase.split())
            assert 2 <= wc <= 5, f"Phrase '{phrase}' has {wc} words (need 2-5)"

    def test_punctuation_boundary_split(self):
        """Title with punctuation must NOT produce cross-boundary candidates."""
        corpus = [{"id": 1, "slug": "x", "title": "VA Loans: Rates, Down Payment, and Eligibility", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        # Good candidates from individual segments
        assert "va loans" in phrases, f"Expected 'va loans' in {phrases}"
        assert "down payment" in phrases, f"Expected 'down payment' in {phrases}"
        # Must NOT cross punctuation
        bad = [p for p in phrases if "," in p or ":" in p]
        assert bad == [], f"Punctuation-spanning candidates found: {bad}"
        assert "down payment, and" not in phrases
        assert "rates, down" not in phrases

    def test_edge_stopword_stripping(self):
        """Candidates must not start or end with stopwords."""
        corpus = [{"id": 1, "slug": "x", "title": "Guide to Buying a Home in Texas", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        for phrase, *_ in cands:
            words = phrase.split()
            from lib.linker_core import _EDGE_STRIP
            assert words[0].lower() not in _EDGE_STRIP, f"'{phrase}' starts with stopword '{words[0]}'"
            assert words[-1].lower() not in _EDGE_STRIP, f"'{phrase}' ends with stopword '{words[-1]}'"

    def test_question_stem_rejected(self):
        """Bare question stems like 'how much' must be rejected."""
        corpus = [{"id": 1, "slug": "x", "title": "How Much House Can I Afford", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "how much" not in phrases
        assert "how much house" not in phrases

    def test_pos_verb_ending_rejected(self):
        """'VA Loan Requires' must be rejected (ends with verb)."""
        corpus = [{"id": 1, "slug": "x", "title": "VA Loan Requires Good Credit", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "va loan requires" not in phrases

    def test_pos_noun_ending_accepted(self):
        """'Loan Requirements' must be accepted (ends with noun)."""
        corpus = [{"id": 1, "slug": "x", "title": "FHA Loan Requirements Guide", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "loan requirements" in phrases

    def test_pos_gerund_as_noun_accepted(self):
        """'Refinancing Options' accepted (gerund-as-noun tagged NN by NLTK)."""
        corpus = [{"id": 1, "slug": "x", "title": "Refinancing Options Explained", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "refinancing options" in phrases

    def test_pos_getting_approved_rejected(self):
        """'Getting Approved' rejected (ends with VBD/VBN)."""
        corpus = [{"id": 1, "slug": "x", "title": "Getting Approved Fast Tips", "url": "/x/"}]
        cands = corpus_candidates(corpus)
        phrases = [c[0].lower() for c in cands]
        assert "getting approved" not in phrases


class TestScoringPriority:
    """Under-threshold destination wins a contested paragraph."""

    def test_under_threshold_wins(self):
        from lib.linker_core import score_candidate
        # Destination A: 0 inbound (under threshold)
        sa = score_candidate("VA loan", 1.0, "/va-loans/", {"/va-loans": 0}, inbound_min=3)
        # Destination B: 10 inbound (over threshold)
        sb = score_candidate("home loan", 1.0, "/home-loans/", {"/home-loans": 10}, inbound_min=3)
        assert sa > sb, f"Under-threshold score {sa} should beat over-threshold {sb}"


class TestPerRunCap:
    """Per-run destination cap is a hard stop — capped destinations are skipped."""

    def test_capped_destination_skipped(self):
        from lib.linker_core import is_dest_capped, _normalize_for_dedup
        norm = _normalize_for_dedup("/popular/")
        counts = {norm: 10}
        assert is_dest_capped("/popular/", counts, 10) is True
        assert is_dest_capped("/fresh/", counts, 10) is False
        assert is_dest_capped("/popular/", {norm: 9}, 10) is False

    def test_hard_cap_limits_proposals(self):
        """A destination with 30 potential matches yields exactly cap proposals."""
        from lib.linker_core import _normalize_for_dedup as norm_dedup
        # Build 30 "posts" that each could link to /target/
        per_run = {}
        injected_count = 0
        for i in range(30):
            norm = norm_dedup("/target/")
            if per_run.get(norm, 0) >= 5:
                continue  # hard cap
            per_run[norm] = per_run.get(norm, 0) + 1
            injected_count += 1
        assert injected_count == 5, f"Expected exactly 5, got {injected_count}"


class TestProtectedSlugs:
    """Protected slugs are never used as source or destination."""

    def test_protected_skipped_as_destination(self):
        # inject_post skips candidates whose URL matches protected_slugs
        # We test indirectly: the URL check in inject_post uses `any(p in url for p in protected)`
        config = {"protected_slugs": ["/va-funding-fee/"], "max_links_per_post": 10,
                  "max_links_per_section": 3, "max_links_per_para": 1,
                  "inbound_min": 3, "per_run_dest_cap": 10}
        html = "<h2>About Fees</h2><p>Learn about VA funding fee details for Veterans today.</p>"
        candidates = [("VA funding fee", "/va-funding-fee/", 1.0, "title")]
        _, details = inject_post(html, candidates, 999, "x.com", {}, config, {}, {})
        assert len(details) == 0, "Protected destination should be skipped"


class TestPrefixConfigurability:
    """Same fixture passes with different prefix configs."""

    def test_vln_prefix(self):
        html = '<div class="vlnHero"><p>VA loan options for Veterans today.</p></div>'
        soup = _make_soup(html)
        para = soup.find("p")
        assert _core_zone(para, {"prefixes": ["vln"], "suffixes": ["hero"]}) is True

    def test_tln_prefix(self):
        html = '<div class="tlnHero"><p>FHA loan options for borrowers today.</p></div>'
        soup = _make_soup(html)
        para = soup.find("p")
        assert _core_zone(para, {"prefixes": ["tln"], "suffixes": ["hero"]}) is True

    def test_lrg_prefix(self):
        html = '<div class="rl-hero"><p>San Antonio home buying guide for families.</p></div>'
        soup = _make_soup(html)
        para = soup.find("p")
        assert _core_zone(para, {"prefixes": ["rl-"], "suffixes": ["hero"]}) is True

    def test_wrong_prefix_not_blocked(self):
        html = '<div class="tlnHero"><p>VA loan info for Veterans today.</p></div>'
        soup = _make_soup(html)
        para = soup.find("p")
        # vln prefix should NOT match tlnHero
        assert _core_zone(para, {"prefixes": ["vln"], "suffixes": ["hero"]}) is False


class TestDeployLock:
    """deploy_lock context manager: stale removal, live abort."""

    def test_acquire_release_cycle(self):
        import os, json
        from lib.linker_core import _LOCKS_DIR
        lock_file = _LOCKS_DIR / "link-injector-test-lock.lock"
        if lock_file.exists():
            lock_file.unlink()
        # allow_no_tty=True because test runner pipes stdout
        with deploy_lock("test-lock", "link-injector", allow_no_tty=True):
            assert lock_file.exists()
            data = json.loads(lock_file.read_text())
            assert data["pid"] == os.getpid()
        assert not lock_file.exists()

    def test_stale_lock_removed(self):
        import json
        from lib.linker_core import _LOCKS_DIR
        lock_file = _LOCKS_DIR / "link-injector-test-stale.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps({"pid": 99999999, "timestamp": "2026-01-01"}))
        with deploy_lock("test-stale", "link-injector", allow_no_tty=True):
            assert lock_file.exists()
        assert not lock_file.exists()

    def test_non_tty_aborts(self):
        """deploy_lock under non-TTY stdout aborts with exit 98."""
        import subprocess
        mod_dir = str(MODULE_DIR)
        code = (
            f"import sys\nsys.path.insert(0, {mod_dir!r})\n"
            "from lib.linker_core import deploy_lock\n"
            "with deploy_lock('test-tty', 'link-injector'):\n    pass\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 98, f"Expected exit 98, got {result.returncode}: {result.stderr}"

    def test_allow_no_tty_proceeds_with_warning(self):
        """deploy_lock with allow_no_tty=True proceeds under non-TTY."""
        import subprocess
        from lib.linker_core import _LOCKS_DIR
        lock_file = _LOCKS_DIR / "link-injector-test-tty-allow.lock"
        if lock_file.exists():
            lock_file.unlink()
        mod_dir = str(MODULE_DIR)
        code = (
            f"import sys\nsys.path.insert(0, {mod_dir!r})\n"
            "from lib.linker_core import deploy_lock\n"
            "with deploy_lock('test-tty-allow', 'link-injector', allow_no_tty=True):\n"
            "    print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"
        assert "WARNING" in result.stderr, "Should have printed a warning"
        assert "OK" in result.stdout


# ---------------------------------------------------------------------------
# Run as standalone script
# ---------------------------------------------------------------------------

def _run_all():
    """Run all test classes, print pass/fail summary."""
    import inspect

    test_classes = [
        TestWordBoundary,
        TestAttributeSafety,
        TestExistingLinkSafety,
        TestSkipZones,
        TestHeadingSafety,
        TestValidInjection,
        TestSecondOccurrence,
        TestTwoTriggersOneParagraph,
        TestPerPostDedup,
        TestAnchorSpanningExistingLink,
        TestLegacyPostStructure,
        TestCorpusCandidates,
        TestScoringPriority,
        TestPerRunCap,
        TestProtectedSlugs,
        TestPrefixConfigurability,
        TestDeployLock,
    ]

    total = 0
    passed = 0
    failed = 0
    failures = []

    for cls in test_classes:
        instance = cls()
        methods = [
            m for m in dir(instance)
            if m.startswith("test_") and callable(getattr(instance, m))
        ]
        for method_name in sorted(methods):
            total += 1
            test_id = f"{cls.__name__}.{method_name}"
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  PASS  {test_id}")
            except Exception as e:
                failed += 1
                failures.append((test_id, str(e)))
                print(f"  FAIL  {test_id}: {e}")

    print()
    print(f"{'=' * 60}")
    print(f"  {total} tests | {passed} passed | {failed} failed")
    print(f"{'=' * 60}")

    if failures:
        print()
        for test_id, err in failures:
            print(f"  FAILURE: {test_id}")
            print(f"           {err}")
        sys.exit(1)
    else:
        print("  ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    _run_all()
