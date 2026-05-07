"""Serper.dev provider implementation.

Serper.dev (serper.dev) is the default provider — high credit allowance,
low cost per query. Uses POST with X-API-KEY header.

Does NOT return AI Overview. PAA and knowledge graph may require paid
plan — falls back to SerpAPI for those features when not present.

Dashboard: https://serper.dev/dashboard
Docs: https://serper.dev/docs
"""

import json as json_module
import os
import requests

try:
    from .provider import SerpProvider, FeatureNotSupported
    from .rate_limiter import RateLimiter
except ImportError:
    from provider import SerpProvider, FeatureNotSupported
    from rate_limiter import RateLimiter


class SerperDevClient(SerpProvider):
    """Serper.dev provider — default for organic results and related searches.

    Setup:
        export SERPDEV_API_KEY="your-serper-dev-key"
    """

    name = "serper"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SERPDEV_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "SERPDEV_API_KEY not set. "
                "Get your key at https://serper.dev/dashboard"
            )
        self.endpoint = "https://google.serper.dev/search"
        self.rate_limiter = RateLimiter(min_interval=2.0)

    def search(self, keyword: str, location: str = "United States",
               device: str = "desktop") -> dict:
        self.rate_limiter.wait()
        payload = {
            "q": keyword,
            "location": location,
            "gl": "us",
            "hl": "en",
            "num": 10,
        }
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self.endpoint, headers=headers,
            data=json_module.dumps(payload), timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_top_results(self, response: dict, top_n: int = 10) -> list[dict]:
        organic = response.get("organic", [])
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
        questions = response.get("peopleAlsoAsk", [])
        results = []
        for i, q in enumerate(questions):
            results.append({
                "question": q.get("question", ""),
                "answer": q.get("snippet", ""),
                "position": i + 1,
            })
        return results

    def get_related_searches(self, response: dict) -> list[str]:
        related = response.get("relatedSearches", [])
        return [r.get("query", "") for r in related if r.get("query")]

    def get_ai_overview(self, response: dict) -> dict | None:
        raise FeatureNotSupported("Serper.dev does not provide AI Overview data")

    def get_knowledge_panel(self, response: dict) -> dict | None:
        kg = response.get("knowledgeGraph")
        if not kg:
            return None
        return {
            "title": kg.get("title", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
            "source": kg.get("source", {}),
        }

    def get_local_pack(self, response: dict) -> list | None:
        places = response.get("places", [])
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
        return "answerBox" in response
