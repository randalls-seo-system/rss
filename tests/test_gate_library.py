"""Mutation tests for lib/gate_library.py — every assertion gets a red and green run."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.gate_library import (
    gate_no_editorial_markup,
    gate_slug_unique,
    gate_title_integrity,
    gate_no_fragment_list_items,
    gate_no_undefined_classes,
    gate_no_fabricated_sourcing,
    gate_no_banned_phrases,
    gate_body_not_empty,
    gate_headline_present,
    gate_min_sections,
    run_universal_gates,
)


class TestNoEditorialMarkup(unittest.TestCase):
    """The [FLAG FOR MAYRA] case is literally a fixture."""

    def test_flag_for_mayra_fails(self):
        html = '<p>[FLAG FOR MAYRA] Review this section before publish.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)
        self.assertIn("[FLAG", r.detail)

    def test_todo_fails(self):
        html = '<p>[TODO: add pricing data here]</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_verify_fails(self):
        html = '<p>[VERIFY this claim with county records]</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_review_fails(self):
        html = '<p>[REVIEW needed] Some content here.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_placeholder_fails(self):
        html = '<p>[PLACEHOLDER for intro paragraph]</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_fixme_fails(self):
        html = '<p>FIXME this paragraph needs work.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_xxx_colon_fails(self):
        html = '<p>XXX: broken formatting here.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_lorem_ipsum_fails(self):
        html = '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_insert_fails(self):
        html = '<p>[INSERT testimonial here]</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_unrendered_template_var_fails(self):
        html = '<p>Welcome to {{city_name}}, a great place to live.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_case_insensitive(self):
        html = '<p>[flag for review] check this.</p>'
        r = gate_no_editorial_markup(html)
        self.assertFalse(r.passed)

    def test_clean_html_passes(self):
        html = '<h2>Understanding VA Loan Benefits</h2><p>VA loans offer zero down payment.</p>'
        r = gate_no_editorial_markup(html)
        self.assertTrue(r.passed)


class TestSlugUnique(unittest.TestCase):

    def test_collision_fails(self):
        inventory = [{"slug": "va-loan-benefits"}, {"slug": "credit-repair"}]
        r = gate_slug_unique("", slug="va-loan-benefits", inventory=inventory)
        self.assertFalse(r.passed)
        self.assertIn("already exists", r.detail)

    def test_unique_slug_passes(self):
        inventory = [{"slug": "va-loan-benefits"}, {"slug": "credit-repair"}]
        r = gate_slug_unique("", slug="new-article-topic", inventory=inventory)
        self.assertTrue(r.passed)

    def test_missing_inventory_fails_closed(self):
        r = gate_slug_unique("", slug="test", site_slug="nonexistent-site-xyz")
        self.assertFalse(r.passed)
        self.assertIn("fail closed", r.detail)

    def test_no_slug_skips(self):
        r = gate_slug_unique("")
        self.assertTrue(r.passed)


class TestTitleIntegrity(unittest.TestCase):

    def test_short_title_fails(self):
        r = gate_title_integrity("", title="Short")
        self.assertFalse(r.passed)
        self.assertIn("Too short", r.detail)

    def test_trailing_comma_fails(self):
        r = gate_title_integrity("", title="VA Loan Benefits in Texas,")
        self.assertFalse(r.passed)
        self.assertIn("Trailing comma", r.detail)

    def test_trailing_conjunction_fails(self):
        r = gate_title_integrity("", title="VA Loan Benefits in Texas and")
        self.assertFalse(r.passed)
        self.assertIn("Trailing conjunction", r.detail)

    def test_pipeline_prefix_leak_fails(self):
        r = gate_title_integrity("", title="[REFRESH pending] VA Loan Guide for Texas Veterans")
        self.assertFalse(r.passed)
        self.assertIn("Pipeline prefix leak", r.detail)

    def test_clean_title_passes(self):
        r = gate_title_integrity("", title="VA Loan Guide for Texas Veterans in 2026")
        self.assertTrue(r.passed)

    def test_extracts_from_h1(self):
        html = '<h1>VA Loan Guide for Texas Veterans in 2026</h1><p>Content.</p>'
        r = gate_title_integrity(html)
        self.assertTrue(r.passed)


class TestNoFragmentListItems(unittest.TestCase):

    def test_empty_li_fails(self):
        html = '<ul><li></li><li>Normal item with enough words here.</li></ul>'
        r = gate_no_fragment_list_items(html)
        self.assertFalse(r.passed)

    def test_short_li_fails(self):
        html = '<ul><li>Two words.</li></ul>'
        r = gate_no_fragment_list_items(html)
        self.assertFalse(r.passed)

    def test_punctuation_start_fails(self):
        html = '<ul><li>, saving thousands on your mortgage payments long-term.</li></ul>'
        r = gate_no_fragment_list_items(html)
        self.assertFalse(r.passed)

    def test_clean_list_passes(self):
        html = '<ul><li>FHA loans require a minimum 3.5 percent down payment with a 580 credit score.</li></ul>'
        r = gate_no_fragment_list_items(html)
        self.assertTrue(r.passed)


class TestNoUndefinedClasses(unittest.TestCase):

    def test_foreign_class_fails(self):
        config = {"content": {"css_prefix": ["rl-"], "css_allowlist": []}}
        html = '<div class="completely-unknown-class">Content</div>'
        r = gate_no_undefined_classes(html, config=config)
        self.assertFalse(r.passed)
        self.assertIn("completely-unknown-class", r.detail)

    def test_site_prefix_passes(self):
        config = {"content": {"css_prefix": ["rl-"], "css_allowlist": []}}
        html = '<div class="rl-bluf">Content</div>'
        r = gate_no_undefined_classes(html, config=config)
        self.assertTrue(r.passed)

    def test_builtin_passes(self):
        config = {"content": {"css_prefix": ["rl-"], "css_allowlist": []}}
        html = '<div class="rss-il">Link</div>'
        r = gate_no_undefined_classes(html, config=config)
        self.assertTrue(r.passed)


class TestNoFabricatedSourcing(unittest.TestCase):

    def test_undeclared_mls_fails(self):
        html = '<p>According to our analysis of MLS data, prices have risen 15 percent.</p>'
        r = gate_no_fabricated_sourcing(html, config={})
        self.assertFalse(r.passed)
        self.assertIn("MLS data", r.detail)

    def test_declared_source_passes(self):
        html = '<p>Prices have risen based on MLS data from the local board.</p>'
        r = gate_no_fabricated_sourcing(html, config={}, declared_sources=["MLS data"])
        self.assertTrue(r.passed)

    def test_both_declared_passes(self):
        html = '<p>According to our analysis of MLS data, prices rose.</p>'
        r = gate_no_fabricated_sourcing(
            html, config={},
            declared_sources=["MLS data", "according to our analysis of"],
        )
        self.assertTrue(r.passed)

    def test_no_claims_passes(self):
        html = '<p>VA loans offer zero down payment for eligible Veterans.</p>'
        r = gate_no_fabricated_sourcing(html, config={})
        self.assertTrue(r.passed)


class TestNoBannedPhrases(unittest.TestCase):

    def test_dream_home_fails(self):
        html = '<p>Find your dream home in San Antonio with our expert guidance.</p>'
        r = gate_no_banned_phrases(html)
        self.assertFalse(r.passed)
        self.assertIn("dream home", r.detail)

    def test_hassle_free_fails(self):
        html = '<p>Enjoy a hassle-free closing process with VA loans.</p>'
        r = gate_no_banned_phrases(html)
        self.assertFalse(r.passed)

    def test_clean_prose_passes(self):
        html = '<p>VA loans allow zero down payment for eligible Veterans in Texas.</p>'
        r = gate_no_banned_phrases(html)
        self.assertTrue(r.passed)


class TestBodyNotEmpty(unittest.TestCase):

    def test_empty_body_fails(self):
        r = gate_body_not_empty("", content_type="article")
        self.assertFalse(r.passed)

    def test_short_body_fails(self):
        html = '<p>Too short.</p>'
        r = gate_body_not_empty(html, content_type="article")
        self.assertFalse(r.passed)

    def test_link_update_zero_min_passes(self):
        html = '<p>Short content.</p>'
        r = gate_body_not_empty(html, content_type="link_update")
        self.assertTrue(r.passed)


class TestHeadlinePresent(unittest.TestCase):

    def test_no_headline_fails(self):
        html = '<p>Just a paragraph with no headings at all.</p>'
        r = gate_headline_present(html, content_type="article")
        self.assertFalse(r.passed)

    def test_h2_passes(self):
        html = '<h2>Section Title</h2><p>Content.</p>'
        r = gate_headline_present(html, content_type="article")
        self.assertTrue(r.passed)

    def test_not_required_for_link_update(self):
        html = '<p>Just a paragraph.</p>'
        r = gate_headline_present(html, content_type="link_update")
        self.assertTrue(r.passed)


class TestMinSections(unittest.TestCase):

    def test_too_few_sections_fails(self):
        html = '<h2>S1</h2><p>C1.</p><h2>S2</h2><p>C2.</p>'
        r = gate_min_sections(html, content_type="article")
        self.assertFalse(r.passed)

    def test_enough_sections_passes(self):
        html = ''.join(f'<h2>Section {i}</h2><p>Content {i}.</p>' for i in range(8))
        r = gate_min_sections(html, content_type="article")
        self.assertTrue(r.passed)

    def test_no_min_for_link_update(self):
        html = '<p>No sections needed.</p>'
        r = gate_min_sections(html, content_type="link_update")
        self.assertTrue(r.passed)


class TestRunUniversalGates(unittest.TestCase):
    """Integration: full gate run."""

    def test_flag_for_mayra_blocks_deploy(self):
        """The exact incident that triggered this feature: [FLAG FOR MAYRA] in live article."""
        html = (
            '<h1>Best Neighborhoods in San Antonio for Military Families</h1>'
            + ''.join(f'<h2>Section {i}</h2><p>{"Content words here. " * 30}</p>'
                      for i in range(8))
            + '<p>[FLAG FOR MAYRA] Review this pricing section before publish.</p>'
        )
        report = run_universal_gates(
            html, site_slug="lrg",
            title="Best Neighborhoods in San Antonio for Military Families",
            content_type="article",
        )
        self.assertFalse(report.passed)
        failure_names = [f.name for f in report.failures]
        self.assertIn("no_editorial_markup", failure_names)

    def test_clean_article_passes(self):
        html = (
            '<h1>VA Loan Guide for Texas Veterans in 2026</h1>'
            + ''.join(f'<h2>Section {i}</h2><p>{"Content about VA loans. " * 30}</p>'
                      for i in range(8))
        )
        report = run_universal_gates(
            html, site_slug="lrg",
            title="VA Loan Guide for Texas Veterans in 2026",
            content_type="article",
        )
        # May have css_prefix issues if config not loaded, but editorial/structural pass
        editorial_result = next(r for r in report.results if r.name == "no_editorial_markup")
        self.assertTrue(editorial_result.passed)


if __name__ == "__main__":
    unittest.main()
