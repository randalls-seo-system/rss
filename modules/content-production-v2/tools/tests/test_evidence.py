"""Tests for lib/evidence.py — evidence layer.

Covers:
  - Passage extraction skips nav/footer and enforces 15-90 word window
  - Dedup drops near-duplicates
  - Facts-file parsing yields correct CONFIRMED/VERIFY tiers
  - Selection ranks confirmed business fact above low-overlap competitor
  - Empty/missing store falls back cleanly (no exceptions)
  - Rendered evidence block respects max_chars

All tests use fixture strings — no network calls.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add module root to path
MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.evidence import (
    EvidenceItem,
    _deduplicate,
    _extract_passages,
    _parse_business_facts,
    render_evidence_block,
    select_evidence_for_section,
)


# ---------------------------------------------------------------------------
# Fixture HTML
# ---------------------------------------------------------------------------

FIXTURE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
<nav><a href="/">Home</a> <a href="/about">About</a></nav>
<header><h1>Page Title</h1></header>
<main>
  <p>This is a short paragraph with fewer than fifteen words so it should be skipped.</p>
  <p>This paragraph has exactly the right number of words to pass the filter because it contains
     enough content to be meaningful and useful for evidence extraction from competitor pages in
     the SERP results that we are analyzing.</p>
  <p>Too short.</p>
  <ul>
    <li>A list item that is long enough to contain at least fifteen words of useful content for
        the evidence extraction system to pick up and use.</li>
    <li>Short item.</li>
  </ul>
</main>
<footer><p>Copyright 2026. This footer paragraph has enough words to pass the filter but it
   should be stripped by the boilerplate removal step because it is inside a footer element
   and therefore not real content.</p></footer>
<aside><p>Sidebar content that should also be stripped by the boilerplate removal step because
   it lives inside an aside element which is considered navigation or supplementary material.</p></aside>
</body>
</html>
"""


def test_extract_passages_skips_nav_footer():
    """Passages from nav, footer, aside should not appear."""
    passages = _extract_passages(FIXTURE_HTML)
    for p in passages:
        assert "Copyright" not in p, f"Footer passage leaked: {p[:60]}"
        assert "Sidebar" not in p, f"Aside passage leaked: {p[:60]}"
        assert "Home" not in p or len(p.split()) >= 15, f"Nav passage leaked: {p[:60]}"


def test_extract_passages_enforces_word_window():
    """Only passages with 15-90 words should be returned."""
    passages = _extract_passages(FIXTURE_HTML)
    assert len(passages) >= 1, "Expected at least one passage"
    for p in passages:
        wc = len(p.split())
        assert 15 <= wc <= 90, f"Passage has {wc} words (expected 15-90): {p[:60]}"


def test_extract_passages_skips_short():
    """Very short paragraphs should be excluded."""
    passages = _extract_passages(FIXTURE_HTML)
    for p in passages:
        assert "Too short" not in p


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_dedup_drops_exact_duplicates():
    items = [
        EvidenceItem(text="The VA funding fee is 2.15% for first-time use with no down payment.", kind="competitor_page"),
        EvidenceItem(text="The VA funding fee is 2.15% for first-time use with no down payment.", kind="competitor_page"),
        EvidenceItem(text="Something completely different about loan limits and requirements.", kind="competitor_page"),
    ]
    result = _deduplicate(items)
    assert len(result) == 2


def test_dedup_drops_near_duplicates():
    items = [
        EvidenceItem(text="The VA funding fee is 2.15% for first-time use with no down payment applied.", kind="competitor_page"),
        EvidenceItem(text="The VA funding fee is 2.15% for first-time use with no down payment.", kind="competitor_page"),
        EvidenceItem(text="A totally different passage about mortgage rates and their impact on borrowers.", kind="competitor_page"),
    ]
    result = _deduplicate(items)
    assert len(result) == 2, f"Expected 2 after dedup, got {len(result)}"


# ---------------------------------------------------------------------------
# Business facts parsing
# ---------------------------------------------------------------------------

FIXTURE_FACTS_MD = """# Test Business Facts

## Location

| Fact | Value | Status |
|------|-------|--------|
| Address | 123 Main St, San Antonio, TX | CONFIRMED |
| Phone | (210) 555-1234 | CONFIRMED |
| Fax | (210) 555-5678 | VERIFY |
| Holiday hours | Unknown | NEVER-CLAIM |

## Delivery

| Fact | Value | Status |
|------|-------|--------|
| Delivery radius | 5 miles | VERIFY |
| Min order | $15 | CONFIRMED |
"""


def test_facts_parsing_tiers():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(FIXTURE_FACTS_MD)
        f.flush()
        path = Path(f.name)

    try:
        items = _parse_business_facts(path)
        confirmed = [i for i in items if i.tier == "confirmed"]
        verify = [i for i in items if i.tier == "verify"]

        assert len(confirmed) >= 3, f"Expected >=3 confirmed, got {len(confirmed)}"
        assert len(verify) >= 2, f"Expected >=2 verify, got {len(verify)}"

        # NEVER-CLAIM should not appear
        for item in items:
            assert "NEVER" not in item.tier.upper()
            assert "Holiday hours" not in item.text or item.tier != "confirmed"
    finally:
        path.unlink()


def test_facts_missing_file():
    items = _parse_business_facts(Path("/nonexistent/path/facts.md"))
    assert items == []


# ---------------------------------------------------------------------------
# Selection ranking
# ---------------------------------------------------------------------------

def test_selection_ranks_confirmed_fact_above_low_overlap():
    """A confirmed business fact should outrank a low-overlap competitor passage."""
    store = [
        {
            "text": "Unrelated passage about weather patterns and seasonal changes in the midwest region.",
            "kind": "competitor_page",
            "source_url": "https://example.com/weather",
            "source_title": "Weather Page",
            "serp_position": 1,
            "tier": "",
        },
        {
            "text": "Address | 123 Main St, San Antonio, TX",
            "kind": "business_facts",
            "source_url": "",
            "source_title": "",
            "serp_position": -1,
            "tier": "confirmed",
        },
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(store, f)
        f.flush()
        path = Path(f.name)

    try:
        selected = select_evidence_for_section(path, "location address", "business")
        assert len(selected) >= 1
        # The confirmed fact should be first due to the +5 boost
        assert selected[0]["kind"] == "business_facts"
        assert selected[0]["tier"] == "confirmed"
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# Empty/missing store fallback
# ---------------------------------------------------------------------------

def test_select_from_missing_file():
    result = select_evidence_for_section(
        Path("/nonexistent/evidence.json"), "test", "test"
    )
    assert result == []


def test_select_from_empty_store():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([], f)
        f.flush()
        path = Path(f.name)

    try:
        result = select_evidence_for_section(path, "test", "test")
        assert result == []
    finally:
        path.unlink()


def test_render_empty_block():
    assert render_evidence_block([]) == ""


# ---------------------------------------------------------------------------
# Rendered evidence block respects max_chars
# ---------------------------------------------------------------------------

def test_selection_respects_max_chars():
    """Selection should stop adding items when max_chars would be exceeded."""
    # Create a store with items that total well over the budget
    store = []
    for i in range(50):
        store.append({
            "text": f"This is passage number {i} about VA funding fee rates and exemptions for Veterans " * 3,
            "kind": "competitor_page",
            "source_url": f"https://example{i}.com/page",
            "source_title": f"Page {i}",
            "serp_position": (i % 5) + 1,
            "tier": "",
        })

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(store, f)
        f.flush()
        path = Path(f.name)

    try:
        selected = select_evidence_for_section(
            path, "VA funding fee", "VA funding fee",
            max_items=20, max_chars=500,
        )
        total = sum(len(item["text"]) for item in selected)
        assert total <= 500, f"Total chars {total} exceeds max_chars 500"
        assert len(selected) < 20, "Should have been limited by char budget before item count"
    finally:
        path.unlink()


def test_render_evidence_block_format():
    """Verify the rendered block uses correct label format."""
    items = [
        {"text": "Fee is 2.15%", "kind": "competitor_page", "source_url": "https://www.example.com/page", "source_title": "Ex", "serp_position": 2, "tier": ""},
        {"text": "Q: What is the fee? A: It is 2.15%.", "kind": "google_paa", "source_url": "", "source_title": "", "serp_position": -1, "tier": ""},
        {"text": "Overview text about fees.", "kind": "google_ai_overview", "source_url": "", "source_title": "", "serp_position": -1, "tier": ""},
        {"text": "Phone | (210) 555-1234", "kind": "business_facts", "source_url": "", "source_title": "", "serp_position": -1, "tier": "confirmed"},
        {"text": "Delivery radius 5 miles", "kind": "business_facts", "source_url": "", "source_title": "", "serp_position": -1, "tier": "verify"},
    ]
    block = render_evidence_block(items)
    assert "[competitor_page | position 2 | example.com]" in block
    assert "[google_paa]" in block
    assert "[google_ai_overview]" in block
    assert "[business_facts | CONFIRMED]" in block
    assert "[business_facts | VERIFY]" in block
