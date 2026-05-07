"""Tests for SERP provider abstraction and routing."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from provider import SerpProvider, SerpProviderRouter, FeatureNotSupported


class MockPrimary(SerpProvider):
    """Mock primary provider — no AI Overview."""
    name = "mock_primary"

    def search(self, keyword, location="US", device="desktop"):
        return {"keyword": keyword, "results": [{"title": "Result 1", "url": "https://example.com"}]}

    def get_top_results(self, response, top_n=10):
        return [{"position": 1, "title": "Result 1", "url": "https://example.com", "snippet": "Test"}]

    def get_paa(self, response):
        return [{"question": "What is test?", "answer": "A test.", "position": 1}]

    def get_related_searches(self, response):
        return ["related query 1", "related query 2"]

    def get_ai_overview(self, response):
        raise FeatureNotSupported("Mock primary doesn't support AI Overview")

    def get_knowledge_panel(self, response):
        return None

    def get_local_pack(self, response):
        return None

    def has_featured_snippet(self, response):
        return False


class MockFallback(SerpProvider):
    """Mock fallback provider — supports AI Overview."""
    name = "mock_fallback"

    def search(self, keyword, location="US", device="desktop"):
        return {"keyword": keyword, "ai": True}

    def get_top_results(self, response, top_n=10):
        return [{"position": 1, "title": "Fallback Result", "url": "https://fb.com", "snippet": "FB"}]

    def get_paa(self, response):
        return []

    def get_related_searches(self, response):
        return []

    def get_ai_overview(self, response):
        return {"text_blocks": [{"type": "paragraph", "snippet": "AI says..."}], "references": []}

    def get_knowledge_panel(self, response):
        return None

    def get_local_pack(self, response):
        return None

    def has_featured_snippet(self, response):
        return False


def test_router_uses_primary_first():
    router = SerpProviderRouter([MockPrimary(), MockFallback()])
    result = router.search_and_extract("test query")
    assert "mock_primary" in result["providers_used"]
    assert result["top_results"][0]["title"] == "Result 1"
    assert len(result["paa"]) == 1


def test_router_falls_back_for_ai_overview():
    router = SerpProviderRouter([MockPrimary(), MockFallback()])
    result = router.search_and_extract("test query")
    assert result["ai_overview"] is not None
    assert "mock_fallback" in result["providers_used"]
    assert result["ai_overview"]["text_blocks"][0]["snippet"] == "AI says..."


def test_router_single_provider():
    router = SerpProviderRouter([MockFallback()])
    result = router.search_and_extract("test")
    assert result["ai_overview"] is not None
    assert result["providers_used"] == ["mock_fallback"]


def test_feature_not_supported_no_fallback():
    router = SerpProviderRouter([MockPrimary()])
    result = router.search_and_extract("test")
    assert result["ai_overview"] is None  # no fallback, stays None


if __name__ == "__main__":
    test_router_uses_primary_first()
    print("PASS: router uses primary first")
    test_router_falls_back_for_ai_overview()
    print("PASS: router falls back for AI overview")
    test_router_single_provider()
    print("PASS: single provider works")
    test_feature_not_supported_no_fallback()
    print("PASS: no fallback gracefully returns None")
    print("\nAll tests passed.")
