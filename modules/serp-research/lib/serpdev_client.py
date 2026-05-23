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

    Key resolution order:
        SERPER_API_KEY → SERPDEV_API_KEY (backward compat)
    Fallback key:
        SERPER_API_KEY_FALLBACK (retried on quota/rate-limit errors only)
    """

    name = "serper"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY") or os.environ.get("SERPDEV_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "SERPER_API_KEY not set. "
                "Get your key at https://serper.dev/dashboard"
            )
        self._fallback_key = os.environ.get("SERPER_API_KEY_FALLBACK", "")
        self._active_key_name = "SERPER_API_KEY"
        self.endpoint = "https://google.serper.dev/search"
        self.rate_limiter = RateLimiter(min_interval=2.0)

    def _do_request(self, payload: dict, api_key: str) -> dict:
        """Execute a single API request with the given key."""
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        response = requests.post(
            self.endpoint, headers=headers,
            data=json_module.dumps(payload), timeout=30,
        )
        response.raise_for_status()
        return response.json()

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
        try:
            result = self._do_request(payload, self.api_key)
            self._active_key_name = "SERPER_API_KEY"
            return result
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (429, 402) and self._fallback_key:
                import sys
                print(f"[serper] Primary key hit quota ({e.response.status_code}), "
                      f"retrying with SERPER_API_KEY_FALLBACK", file=sys.stderr)
                self.rate_limiter.wait()
                result = self._do_request(payload, self._fallback_key)
                self._active_key_name = "SERPER_API_KEY_FALLBACK"
                return result
            raise

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
