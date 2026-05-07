"""SerpDev provider implementation.

SerpDev is the default provider (cheaper, more credits).
Does NOT support AI Overview — falls back to SerpAPI for that feature.

TODO: Set endpoint URL once SerpDev API key is provided and endpoint
      is discovered. Currently a ready stub.
"""

import os
import requests

try:
    from .provider import SerpProvider, FeatureNotSupported
    from .rate_limiter import RateLimiter
except ImportError:
    from provider import SerpProvider, FeatureNotSupported
    from rate_limiter import RateLimiter


class SerpDevClient(SerpProvider):
    """SerpDev provider — high credit allowance, no AI Overview.

    Endpoint and response shape TBD. This is a ready stub that will
    be completed once the SerpDev API key is provided and the endpoint
    is discovered via their documentation.

    Expected setup:
        export SERPDEV_API_KEY="your-key-here"
    """

    name = "serpdev"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SERPDEV_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "SERPDEV_API_KEY not set. "
                "Set env var or pass api_key= to constructor."
            )
        # TODO: Confirm endpoint from SerpDev docs
        self.endpoint = "https://api.serpdev.com/search"
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
        }
        response = requests.get(self.endpoint, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_top_results(self, response: dict, top_n: int = 10) -> list[dict]:
        # TODO: Adjust field names per SerpDev's actual response shape
        organic = response.get("organic_results", response.get("results", []))
        results = []
        for item in organic[:top_n]:
            results.append({
                "position": item.get("position", item.get("rank", 0)),
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "snippet": item.get("snippet", item.get("description", "")),
            })
        return results

    def get_paa(self, response: dict) -> list[dict]:
        # TODO: Adjust field names per SerpDev's actual response shape
        questions = response.get("related_questions", response.get("people_also_ask", []))
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
        if isinstance(related, list) and related and isinstance(related[0], dict):
            return [r.get("query", r.get("text", "")) for r in related]
        return related

    def get_ai_overview(self, response: dict) -> dict | None:
        raise FeatureNotSupported("SerpDev does not provide AI Overview data")

    def get_knowledge_panel(self, response: dict) -> dict | None:
        kg = response.get("knowledge_graph", response.get("knowledge_panel"))
        if not kg:
            return None
        return {
            "title": kg.get("title", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
            "source": kg.get("source", {}),
        }

    def get_local_pack(self, response: dict) -> list | None:
        local = response.get("local_results", response.get("local_pack", {}))
        places = local.get("places", local.get("results", []))
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
