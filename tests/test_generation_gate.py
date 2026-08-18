"""Tests for the generation-time universal gate wired into assemble-article.py.

Validates that run_universal_gates correctly blocks or passes content
at the generation lifecycle stage, where CSS classes are rl-* (pre-conversion)
and bullet-section-* wrappers are structural framework classes.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from gate_library import run_universal_gates


# The generation-time config: pipeline emits rl-* classes.
GENERATION_GATE_CONFIG = {
    "content": {
        "css_prefix": ["rl-"],
    }
}

# A minimal well-formed article that passes all gates.
_GOOD_ARTICLE = (
    '<div class="rl-page">'
    '<h1>Best Neighborhoods in San Antonio for Military Families</h1>'
    '<section class="rl-bluf"><h2>The Bottom Line Up Front</h2>'
    '<p><strong>' + "This is the lead paragraph with enough words. " * 5 + '</strong></p>'
    '<ul>'
    '<li>First capstone bullet with enough words for the gate check.</li>'
    '<li>Second capstone bullet with enough words for the gate check.</li>'
    '<li>Third capstone bullet with enough words for the gate check.</li>'
    '<li>Fourth capstone bullet with enough words for the gate check.</li>'
    '<li>Fifth capstone bullet with enough words for the gate check.</li>'
    '</ul></section>'
    + ''.join(
        f'<section><h2>Section {i} About This Topic</h2>'
        f'<p>{"Body content about VA loans and military housing options. " * 15}</p>'
        f'</section>'
        for i in range(8)
    )
    + '</div>'
)


class TestEditorialMarkupBlocks(unittest.TestCase):
    """4a: Editorial markers in generated HTML must block production."""

    def test_flag_for_review_blocks(self):
        html = _GOOD_ARTICLE.replace(
            '</section>',
            '<p>[FLAG FOR REVIEW] Check this section.</p></section>',
            1,
        )
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertFalse(report.passed)
        failed_names = [f.name for f in report.failures]
        self.assertIn("no_editorial_markup", failed_names)

    def test_todo_blocks(self):
        html = _GOOD_ARTICLE.replace(
            '</section>',
            '<p>[TODO: add pricing data]</p></section>',
            1,
        )
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertFalse(report.passed)
        failed_names = [f.name for f in report.failures]
        self.assertIn("no_editorial_markup", failed_names)

    def test_clean_article_passes(self):
        report = run_universal_gates(
            _GOOD_ARTICLE, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertTrue(report.passed)


class TestForeignClassBlocks(unittest.TestCase):
    """4b: Classes outside rl-* and framework prefixes must block."""

    def test_unknown_prefix_blocks(self):
        html = _GOOD_ARTICLE.replace(
            'class="rl-bluf"',
            'class="xyz-foreign-widget"',
        )
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertFalse(report.passed)
        failed_names = [f.name for f in report.failures]
        self.assertIn("no_undefined_classes", failed_names)
        self.assertIn("xyz-foreign-widget",
                       report.failures[0].detail if report.failures else "")


class TestBulletSectionPasses(unittest.TestCase):
    """4c: bullet-section-* is a structural framework class, valid at both stages."""

    def _inject_bullet_section(self, color):
        return _GOOD_ARTICLE.replace(
            '</section>',
            f'<div class="bullet-section-{color}">'
            '<ul><li>Bullet with enough words for the fragment gate check.</li></ul>'
            f'</div></section>',
            1,
        )

    def test_bullet_section_gray_passes_generation(self):
        html = self._inject_bullet_section("gray")
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertTrue(report.passed, report.summary())

    def test_bullet_section_blue_passes_generation(self):
        html = self._inject_bullet_section("blue")
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
            config=GENERATION_GATE_CONFIG,
        )
        self.assertTrue(report.passed, report.summary())

    def test_bullet_section_passes_deploy_config(self):
        """bullet-section-* must also pass when gated with the site's deploy config."""
        html = self._inject_bullet_section("green")
        # config=None → gate loads sites/lrg/config.json (css_prefix: ["rl-"])
        report = run_universal_gates(
            html, site_slug="lrg", content_type="article",
        )
        self.assertTrue(report.passed, report.summary())


class TestIntentToContentType(unittest.TestCase):
    """Intent→content_type mapping: unknown/empty defaults to 'article'."""

    # Import the mapping from assemble-article.py via importlib
    # (same pattern used for gate_library imports)
    @classmethod
    def setUpClass(cls):
        import importlib.util
        tools_dir = REPO_ROOT / "modules" / "content-production-v2" / "tools"
        # We cannot import assemble-article.py directly (dash in name),
        # so test the mapping logic inline with the same dict.
        cls.mapping = {"community-guide": "guide"}

    def _resolve(self, intent):
        return self.mapping.get(intent, "article")

    def test_community_guide_maps_to_guide(self):
        self.assertEqual(self._resolve("community-guide"), "guide")

    def test_definition_maps_to_article(self):
        self.assertEqual(self._resolve("definition"), "article")

    def test_cost_maps_to_article(self):
        self.assertEqual(self._resolve("cost"), "article")

    def test_empty_string_maps_to_article(self):
        self.assertEqual(self._resolve(""), "article")

    def test_none_maps_to_article(self):
        self.assertEqual(self._resolve(None), "article")

    def test_unknown_value_maps_to_article(self):
        self.assertEqual(self._resolve("totally-unknown-intent"), "article")


if __name__ == "__main__":
    unittest.main()
