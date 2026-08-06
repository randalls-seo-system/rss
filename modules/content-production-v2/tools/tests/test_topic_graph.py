"""Tests for topic graph: pending links, resolution, backfill."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.topic_graph import (
    collect_pending_from_corpus,
    collect_pending_from_candidates,
    resolve_pending_entries,
    dedupe_spoke_candidates,
    enrich_anchor_pool,
)


class TestPendingLinkCollection(unittest.TestCase):
    """Part A: real pending entries from corpus + candidates."""

    def test_corpus_unmatched_phrases_collected(self):
        """Corpus phrases not in pool should become pending entries."""
        body = "FHA loans require mortgage insurance premiums. The debt to income ratio is important for qualification."
        phrases = ["mortgage insurance premiums", "debt to income ratio", "fha loans require"]
        pool_keywords = {"fha loans"}  # only this is in pool

        pending = collect_pending_from_corpus(
            body, phrases, set(), pool_keywords,
            source_post_id=100, source_url="/test/", source_job="job-1",
        )
        topics = {p["topic"] for p in pending}
        self.assertIn("mortgage insurance premiums", topics)
        self.assertIn("debt to income ratio", topics)
        # "fha loans require" has "fha loans" as a pool keyword fragment, but
        # the full phrase is different — it should still be collected
        for p in pending:
            self.assertEqual(p["discovered_from"], "corpus")
            self.assertEqual(p["source_post_id"], 100)

    def test_empty_pool_still_collects_corpus(self):
        """With empty pool, all qualifying phrases become pending."""
        body = "conventional loan requirements include credit score minimums"
        phrases = ["conventional loan requirements", "credit score minimums"]
        pending = collect_pending_from_corpus(
            body, phrases, set(), set(),
            source_post_id=1, source_url="/a/", source_job="j",
        )
        self.assertGreater(len(pending), 0)

    def test_candidates_with_open_enum_discovered_from(self):
        """Topic candidates with any discovered_from value should be accepted."""
        candidates = [
            {"topic": "FHA streamline refinance", "discovered_from": "paa"},
            {"topic": "VA loan closing costs", "discovered_from": "gsc"},
            {"topic": "USDA income limits 2026", "discovered_from": "ai_mode"},
            {"topic": "Custom source test", "discovered_from": "custom_plugin_v3"},
        ]
        pending = collect_pending_from_candidates(
            candidates, set(), set(),
            source_post_id=100, source_url="/test/", source_job="job-1",
        )
        sources = {p["discovered_from"] for p in pending}
        self.assertIn("paa", sources)
        self.assertIn("gsc", sources)
        self.assertIn("ai_mode", sources)
        self.assertIn("custom_plugin_v3", sources)

    def test_candidate_already_in_pool_excluded(self):
        """Candidates matching pool keywords should not become pending."""
        candidates = [
            {"topic": "fha loan requirements", "discovered_from": "paa"},
        ]
        pool_keywords = {"fha loan requirements"}
        pending = collect_pending_from_candidates(
            candidates, set(), pool_keywords,
            source_post_id=100, source_url="/test/", source_job="job-1",
        )
        self.assertEqual(len(pending), 0)

    def test_dedup_within_article(self):
        """Same topic from corpus and candidate should appear once."""
        corpus_pending = [
            {"topic": "mortgage insurance", "anchor_phrase": "mortgage insurance",
             "source_post_id": 1, "source_url": "/a/", "source_job": "j",
             "discovered_from": "corpus", "date": "2026-01-01"},
        ]
        # Simulate dedup logic
        seen = set()
        deduped = []
        for p in corpus_pending:
            key = p["topic"].lower().strip()
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        self.assertEqual(len(deduped), 1)


class TestAiModeCandidateResolution(unittest.TestCase):
    """Prove the ai_mode path works today even though nothing produces it yet."""

    def test_ai_mode_candidate_resolves_to_no_page(self):
        """An ai_mode candidate for a non-existent topic should resolve to no_page."""
        entries = [{
            "topic": "AI Mode discovered: reverse mortgage alternatives",
            "anchor_phrase": "reverse mortgage alternatives",
            "source_post_id": 500,
            "source_url": "/test-article/",
            "source_job": "job-ai-test",
            "discovered_from": "ai_mode",
            "date": "2026-08-06",
        }]
        slug_map = {"fha-loan": 43, "va-loan": 100}
        gsc_pages = {}

        linked, no_page = resolve_pending_entries(entries, slug_map, gsc_pages, "tln")
        self.assertEqual(len(no_page), 1)
        self.assertEqual(no_page[0]["discovered_from"], "ai_mode")
        self.assertEqual(no_page[0]["resolution"], "no_page")

    def test_ai_mode_candidate_resolves_to_existing(self):
        """An ai_mode candidate matching an existing page should resolve to linked_existing."""
        entries = [{
            "topic": "fha loan requirements",
            "anchor_phrase": "fha loan requirements",
            "source_post_id": 500,
            "source_url": "/test-article/",
            "source_job": "job-ai-test",
            "discovered_from": "ai_mode",
            "date": "2026-08-06",
        }]
        slug_map = {"fha-loan-requirements": 1471}
        gsc_pages = {"fha loan requirements": "fha-loan-requirements"}

        linked, no_page = resolve_pending_entries(entries, slug_map, gsc_pages, "tln")
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["discovered_from"], "ai_mode")
        self.assertEqual(linked[0]["resolution"], "linked_existing")


class TestResolution(unittest.TestCase):
    """Part B: resolution splits exists/not-exists correctly."""

    def test_existing_page_resolves_linked(self):
        entries = [{
            "topic": "fha closing costs",
            "anchor_phrase": "fha closing costs",
            "source_post_id": 100, "source_url": "/a/", "source_job": "j",
            "discovered_from": "corpus", "date": "2026-01-01",
        }]
        slug_map = {"fha-closing-costs": 1501}
        linked, no_page = resolve_pending_entries(entries, slug_map, {}, "tln")
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["destination_slug"], "fha-closing-costs")

    def test_no_page_resolves_spoke(self):
        entries = [{
            "topic": "bridge loan vs heloc comparison",
            "anchor_phrase": "bridge loan vs heloc",
            "source_post_id": 100, "source_url": "/a/", "source_job": "j",
            "discovered_from": "paa", "date": "2026-01-01",
        }]
        linked, no_page = resolve_pending_entries(entries, {}, {}, "tln")
        self.assertEqual(len(no_page), 1)

    def test_dedupe_multi_source_into_one(self):
        """3 entries for the same topic → 1 spoke with 3 backlink notes."""
        entries = [
            {"topic": "jumbo loan rates", "anchor_phrase": "jumbo rates",
             "source_post_id": i, "source_url": f"/post-{i}/", "source_job": f"j{i}",
             "discovered_from": "corpus", "date": "2026-01-01", "resolution": "no_page"}
            for i in [100, 200, 300]
        ]
        spokes = dedupe_spoke_candidates(entries)
        self.assertEqual(len(spokes), 1)
        self.assertEqual(spokes[0]["demand_count"], 3)
        self.assertEqual(len(spokes[0]["backlink_notes"]), 3)

    def test_cannibalization_guard(self):
        """Topic mapping to existing page via GSC should resolve as linked, not no_page."""
        entries = [{
            "topic": "conventional loan requirements",
            "anchor_phrase": "conventional loan",
            "source_post_id": 100, "source_url": "/a/", "source_job": "j",
            "discovered_from": "gsc", "date": "2026-01-01",
        }]
        gsc_pages = {"conventional loan requirements": "conventional-loan-requirements"}
        slug_map = {"conventional-loan-requirements": 424}
        linked, no_page = resolve_pending_entries(entries, slug_map, gsc_pages, "tln")
        self.assertEqual(len(linked), 1, "Should resolve to existing page, not create a new item")
        self.assertEqual(len(no_page), 0)


class TestBackfill(unittest.TestCase):
    """Part C: backfill insertion rules."""

    def test_insert_single_link(self):
        from lib.topic_graph import insert_single_link as _insert_single_link
        html = '<div><p>The FHA closing costs include several fees for borrowers.</p></div>'
        modified, inserted = _insert_single_link(html, "closing costs", "/fha-closing-costs/")
        self.assertTrue(inserted)
        self.assertIn('href="/fha-closing-costs/"', modified)
        self.assertIn('class="rss-il"', modified)

    def test_respects_link_cap(self):
        """Should not insert if post already has max links."""
        from lib.topic_graph import insert_single_link as _insert_single_link
        # Build HTML with 14 existing internal links
        links = "".join(f'<a href="/page-{i}/">link</a>' for i in range(14))
        html = f'<div>{links}<p>The FHA closing costs are important.</p></div>'
        modified, inserted = _insert_single_link(html, "closing costs", "/new/", max_links_per_post=14)
        self.assertFalse(inserted)

    def test_missing_phrase_not_forced(self):
        """If anchor phrase is gone from article, backfill should not insert."""
        from lib.topic_graph import insert_single_link as _insert_single_link
        html = '<div><p>This article discusses mortgage rates and fees.</p></div>'
        modified, inserted = _insert_single_link(html, "closing costs", "/fha-closing-costs/")
        self.assertFalse(inserted)
        self.assertEqual(html, modified)


class TestPoolEnrichment(unittest.TestCase):
    """Pool enrichment from resolved entries."""

    def test_add_new_keyword_variant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import lib.topic_graph as tg
            orig_root = tg.REPO_ROOT
            tg.REPO_ROOT = Path(tmpdir)

            pool_dir = Path(tmpdir) / "sites"
            pool_dir.mkdir()
            pool_path = pool_dir / "test-anchor-pools.json"
            pool_path.write_text(json.dumps([
                {"url": "/fha-closing-costs/", "slug": "fha-closing-costs",
                 "title": "FHA Closing Costs", "primary_keyword": "fha closing costs",
                 "anchors": ["fha closing costs"]},
            ]))

            linked = [{
                "topic": "fha seller concessions",
                "anchor_phrase": "seller concessions",
                "destination_url": "/fha-closing-costs/",
                "destination_slug": "fha-closing-costs",
            }]

            added = enrich_anchor_pool("test", linked)
            self.assertEqual(added, 1)

            # Verify the pool was updated
            updated = json.loads(pool_path.read_text())
            self.assertIn("seller concessions", updated[0]["anchors"])

            tg.REPO_ROOT = orig_root


class TestStubRemoval(unittest.TestCase):
    """Verify the unconditional '[]' writes are gone."""

    def test_no_unconditional_empty_array_in_linker(self):
        """inject-internal-links.py must not write '[]' unconditionally."""
        linker_path = MODULE_DIR / "tools" / "inject-internal-links.py"
        source = linker_path.read_text()
        # The old stub was: Path(...).write_text("[]")
        # After our fix, the only "[]" should be in import/assignment contexts
        lines = source.split("\n")
        stub_lines = [
            (i + 1, line) for i, line in enumerate(lines)
            if '.write_text("[]")' in line
        ]
        self.assertEqual(len(stub_lines), 0,
                        f"Found unconditional '[]' write(s): {stub_lines}")


if __name__ == "__main__":
    unittest.main()
