"""Tests for deploy-integrity assertions (18.4.12-14)."""

import sys
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup
from lib.spec_assertions import (
    assert_no_fragment_list_items,
    assert_atf_document_order,
    assert_title_integrity,
)


class TestFragmentListItems(unittest.TestCase):
    """18.4.12: every <li> >=4 words, no leading punctuation."""

    def test_empty_li_fails(self):
        soup = BeautifulSoup('<ul><li></li><li>Normal item with enough words here.</li></ul>', 'html.parser')
        r = assert_no_fragment_list_items(soup, {})
        self.assertFalse(r.passed)
        self.assertIn("empty", r.detail.lower())

    def test_fragment_li_fails(self):
        soup = BeautifulSoup('<ul><li>Two words.</li></ul>', 'html.parser')
        r = assert_no_fragment_list_items(soup, {})
        self.assertFalse(r.passed)

    def test_punctuation_start_li_fails(self):
        soup = BeautifulSoup('<ul><li>, saving thousands long-term on your mortgage payments.</li></ul>', 'html.parser')
        r = assert_no_fragment_list_items(soup, {})
        self.assertFalse(r.passed)
        self.assertIn("starts with", r.detail)

    def test_clean_li_passes(self):
        soup = BeautifulSoup(
            '<ul>'
            '<li>FHA loans require a minimum 3.5 percent down payment with a 580 credit score.</li>'
            '<li>Conventional loans offer PMI removal at 80 percent equity.</li>'
            '</ul>', 'html.parser')
        r = assert_no_fragment_list_items(soup, {})
        self.assertTrue(r.passed)


class TestATFDocumentOrder(unittest.TestCase):
    """18.4.13: ATF elements in correct sequence."""

    def test_correct_order_passes(self):
        """Spec order: eyebrow → cards → ATF FAQs → BLUF → body H2."""
        html = '''
        <div class="rl-eyebrow">Mortgage · Guide</div>
        <div class="rl-quick-grid"><div class="rl-quick-card"><h3>C</h3></div></div>
        <details><summary>Q?</summary><p>A.</p></details>
        <div class="rl-bluf"><p><strong>Lead</strong></p><p>Body</p><ul><li>B1</li></ul></div>
        <h2>First Body Section</h2><p>Content.</p><ul><li>Item.</li></ul>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_atf_document_order(soup, {})
        self.assertTrue(r.passed)

    def test_bluf_before_cards_fails(self):
        """BLUF before cards violates spec component order (#5 cards, #8 BLUF)."""
        html = '''
        <div class="rl-eyebrow">Mortgage · Guide</div>
        <div class="rl-bluf"><p><strong>Lead</strong></p><p>Body</p><ul><li>B1</li></ul></div>
        <div class="rl-quick-grid"><div class="rl-quick-card"><h3>C</h3></div></div>
        <details><summary>Q?</summary><p>A.</p></details>
        <h2>First Body Section</h2><p>Content.</p><ul><li>Item.</li></ul>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_atf_document_order(soup, {})
        self.assertFalse(r.passed)
        self.assertIn("bluf", r.detail.lower())

    def test_tln_prefix_also_works(self):
        """Post-postprocessor HTML uses tln* classes."""
        html = '''
        <div class="tlnEyebrow">Mortgage · Guide</div>
        <section class="tlnQuickGrid"><article class="tlnQuickCard"><h3>C</h3></article></section>
        <div class="tlnBLUF"><p>Lead</p></div>
        <h2>Body</h2><p>Content.</p><ul><li>Item.</li></ul>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_atf_document_order(soup, {})
        self.assertTrue(r.passed)


class TestTitleIntegrity(unittest.TestCase):
    """18.4.14: title integrity checks."""

    def test_trailing_comma_fails(self):
        html = '<h1>FHA Closing Costs: What Buyers Pay, Seller Concessions, and </h1>'
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_title_integrity(soup, {})
        self.assertFalse(r.passed)
        self.assertIn("trailing", r.detail.lower())

    def test_trailing_and_fails(self):
        html = '<h1>FHA Closing Costs: What Buyers Pay and</h1>'
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_title_integrity(soup, {})
        self.assertFalse(r.passed)

    def test_short_title_fails(self):
        html = '<h1>FHA Costs</h1>'
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_title_integrity(soup, {})
        self.assertFalse(r.passed)
        self.assertIn("short", r.detail.lower())

    def test_mismatch_with_intended_fails(self):
        html = '<h1>FHA Closing Costs Truncated</h1>'
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_title_integrity(soup, {"intended_title": "FHA Closing Costs: The Full Title Here"})
        self.assertFalse(r.passed)
        self.assertIn("mismatch", r.detail.lower())

    def test_clean_title_passes(self):
        html = '<h1>FHA Closing Costs: What Buyers Pay, Seller Concessions, and the 6% Rule</h1>'
        soup = BeautifulSoup(html, 'html.parser')
        r = assert_title_integrity(soup, {"intended_title": "FHA Closing Costs: What Buyers Pay, Seller Concessions, and the 6% Rule"})
        self.assertTrue(r.passed)


if __name__ == "__main__":
    unittest.main()
