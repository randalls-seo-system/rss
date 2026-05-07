"""Abstract base class for SERP providers + routing logic."""

from abc import ABC, abstractmethod


class FeatureNotSupported(Exception):
    """Raised when a provider doesn't support a requested feature."""
    pass


class SerpProvider(ABC):
    """Abstract base for all SERP data providers."""

    name: str = "unknown"

    @abstractmethod
    def search(self, keyword: str, location: str = "United States",
               device: str = "desktop") -> dict:
        """Execute search. Returns raw provider response."""
        pass

    @abstractmethod
    def get_top_results(self, response: dict, top_n: int = 10) -> list[dict]:
        """Extract top organic results: [{position, title, url, snippet}]."""
        pass

    @abstractmethod
    def get_paa(self, response: dict) -> list[dict]:
        """Extract People Also Ask: [{question, answer, position}]."""
        pass

    @abstractmethod
    def get_related_searches(self, response: dict) -> list[str]:
        """Extract related search queries."""
        pass

    @abstractmethod
    def get_ai_overview(self, response: dict) -> dict | None:
        """Extract AI Overview: {text_blocks, references} or None."""
        pass

    @abstractmethod
    def get_knowledge_panel(self, response: dict) -> dict | None:
        """Extract knowledge panel data or None."""
        pass

    @abstractmethod
    def get_local_pack(self, response: dict) -> list | None:
        """Extract local pack results or None."""
        pass

    @abstractmethod
    def has_featured_snippet(self, response: dict) -> bool:
        """Check if response contains a featured snippet."""
        pass


class SerpProviderRouter:
    """Routes feature extraction across multiple providers with fallback."""

    def __init__(self, providers: list[SerpProvider]):
        if not providers:
            raise ValueError("At least one provider required")
        self.providers = providers

    def search_and_extract(self, keyword: str, location: str = "United States",
                           device: str = "desktop") -> dict:
        """Consolidated analysis using best provider per feature.

        Primary provider handles everything. Falls back to secondary
        only for features the primary doesn't support (e.g., AI Overview).
        """
        result = {
            "keyword": keyword,
            "providers_used": [],
            "top_results": None,
            "paa": None,
            "related_searches": None,
            "ai_overview": None,
            "knowledge_panel": None,
            "local_pack": None,
            "has_featured_snippet": None,
        }

        primary = self.providers[0]
        try:
            response = primary.search(keyword, location=location, device=device)
            result["top_results"] = primary.get_top_results(response)
            result["paa"] = primary.get_paa(response)
            result["related_searches"] = primary.get_related_searches(response)
            result["knowledge_panel"] = primary.get_knowledge_panel(response)
            result["local_pack"] = primary.get_local_pack(response)
            result["has_featured_snippet"] = primary.has_featured_snippet(response)
            result["providers_used"].append(primary.name)

            try:
                result["ai_overview"] = primary.get_ai_overview(response)
            except FeatureNotSupported:
                # Fall back for AI Overview
                for fallback in self.providers[1:]:
                    try:
                        fb_response = fallback.search(keyword, location=location, device=device)
                        result["ai_overview"] = fallback.get_ai_overview(fb_response)
                        result["providers_used"].append(fallback.name)
                        break
                    except FeatureNotSupported:
                        continue

        except Exception:
            # Primary failed entirely — try full fallback
            if len(self.providers) > 1:
                return self._fallback_full(keyword, location, device)
            raise

        return result

    def _fallback_full(self, keyword: str, location: str, device: str) -> dict:
        """Full fallback: try each provider until one works."""
        for provider in self.providers[1:]:
            try:
                response = provider.search(keyword, location=location, device=device)
                return {
                    "keyword": keyword,
                    "providers_used": [provider.name],
                    "top_results": provider.get_top_results(response),
                    "paa": provider.get_paa(response),
                    "related_searches": provider.get_related_searches(response),
                    "ai_overview": self._safe_extract(provider.get_ai_overview, response),
                    "knowledge_panel": provider.get_knowledge_panel(response),
                    "local_pack": provider.get_local_pack(response),
                    "has_featured_snippet": provider.has_featured_snippet(response),
                }
            except Exception:
                continue
        raise RuntimeError("All providers failed")

    @staticmethod
    def _safe_extract(method, response):
        try:
            return method(response)
        except FeatureNotSupported:
            return None
