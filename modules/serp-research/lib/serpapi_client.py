"""SerpAPI provider implementation."""

import os
import requests

try:
    from .provider import SerpProvider, FeatureNotSupported
    from .rate_limiter import RateLimiter
except ImportError:
    from provider import SerpProvider, FeatureNotSupported
    from rate_limiter import RateLimiter


class SerpAPIClient(SerpProvider):
    """SerpAPI (serpapi.com) provider.

    Supports all SERP features including AI Overview.
    Higher cost per query than SerpDev — use as fallback for
    features SerpDev doesn't support.
    """

    name = "serpapi"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SERPAPI_KEY", "")
        if not self.api_key:
            raise ValueError("SERPAPI_KEY not set")
        self.endpoint = "https://serpapi.com/search.json"
        self.rate_limiter = RateLimiter(min_interval=2.0)

    def search(self, keyword: str, location: str = "United States",
               device: str = "desktop") -> dict:
        self.rate_limiter.wait()
        params = {
            "q": keyword,
            "api_key": self.api_key,
            "location": location,
            "device": device,
            "hl": "en",
            "gl": "us",
            "engine": "google",
            "num": 10,
        }
        response = requests.get(self.endpoint, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_top_results(self, response: dict, top_n: int = 10) -> list[dict]:
        organic = response.get("organic_results", [])
        results = []
        for item in organic[:top_n]:
            results.append({
                "position": item.get("position", 0),
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return results

    def get_paa(self, response: dict) -> list[dict]:
        questions = response.get("related_questions", [])
        results = []
        for i, q in enumerate(questions):
            results.append({
                "question": q.get("question", ""),
                "answer": q.get("snippet", q.get("answer", "")),
                "position": i + 1,
            })
        return results

    def get_related_searches(self, response: dict) -> list[str]:
        related = response.get("related_searches", [])
        return [r.get("query", "") for r in related if r.get("query")]

    def get_ai_overview(self, response: dict) -> dict | None:
        ai = response.get("ai_overview")
        if not ai:
            return None
        return {
            "text_blocks": ai.get("text_blocks", []),
            "references": ai.get("references", []),
        }

    def get_knowledge_panel(self, response: dict) -> dict | None:
        kg = response.get("knowledge_graph")
        if not kg:
            return None
        return {
            "title": kg.get("title", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
            "source": kg.get("source", {}),
        }

    def get_local_pack(self, response: dict) -> list | None:
        local = response.get("local_results", {})
        places = local.get("places", [])
        if not places:
            return None
        return [
            {
                "title": p.get("title", ""),
                "address": p.get("address", ""),
                "rating": p.get("rating"),
                "reviews": p.get("reviews"),
            }
            for p in places
        ]

    def has_featured_snippet(self, response: dict) -> bool:
        return "answer_box" in response or "featured_snippet" in response
