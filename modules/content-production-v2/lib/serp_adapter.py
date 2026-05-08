"""Read serp-research/analyze-serp.py output JSON and expose typed accessors.

Replaces v1's inline JSON spelunking. Provides typed access to top_results,
paa_questions, ai_overview_text, related_searches, and computed accessors
like average_word_count_top_5() and subtopic_gap_analysis().

See docs/article-spec.md Section 17 for SERP-derived input requirements.
See docs/v2-module-architecture.md "lib/serp_adapter.py" for API contract.
"""

# SHAPE_NOTES — verified against modules/serp-research/ source code:
#
# analyze-serp.py output JSON shape (from provider.py SerpProviderRouter):
# {
#   "keyword": str,
#   "providers_used": [str],
#   "queried_at": str (ISO 8601),
#   "intent_signals": {has_local_pack, has_ai_overview, has_paa, ...},
#   "top_results": [
#     {"position": int, "title": str, "url": str, "snippet": str}
#   ] | null,
#   "paa": [
#     {"question": str, "answer": str, "position": int}
#   ] | null,
#   "related_searches": [str] | null,
#   "ai_overview": {
#     "text_blocks": [
#       {"type": "paragraph"|"list", "snippet": str, "list": [str]} | str
#     ],
#     "references": [
#       {"title": str, "link": str, "source": str} | str
#     ]
#   } | null,
#   "knowledge_panel": {...} | null,
#   "local_pack": [...] | null,
#   "has_featured_snippet": bool | null
# }
#
# LIMITATIONS:
# - top_results do NOT include page word counts or full page content.
#   average_word_count_top_5() returns 0 when content is unavailable.
#   The caller (compute-target-wc.py) should fall back to default range.
# - ai_overview.references entries may be dicts or plain strings.
# - ai_overview.text_blocks entries may be dicts or plain strings.

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class OrganicResult:
    position: int
    title: str
    url: str
    snippet: str
    domain: str = ""

    def __post_init__(self):
        if not self.domain:
            self.domain = urlparse(self.url).netloc.lower().lstrip("www.")


@dataclass
class Reference:
    url: str
    title: str
    source: str = ""
    domain: str = ""

    def __post_init__(self):
        if not self.domain:
            self.domain = urlparse(self.url).netloc.lower().lstrip("www.")
        if not self.source:
            self.source = self.domain


# Domains considered authoritative for primary_sources filtering
_AUTHORITATIVE_TLDS = {".gov", ".edu", ".mil"}
_AUTHORITATIVE_DOMAINS = {
    "va.gov", "benefits.va.gov", "ecfr.gov", "fhfa.gov",
    "hud.gov", "consumerfinance.gov", "freddiemac.com",
    "fanniemae.com", "realtor.org", "nar.realtor",
    "nmlsconsumeraccess.org",
}


def _is_authoritative(domain: str) -> bool:
    for tld in _AUTHORITATIVE_TLDS:
        if domain.endswith(tld):
            return True
    return domain in _AUTHORITATIVE_DOMAINS


class SerpData:
    """Typed accessor over serp-research/analyze-serp.py output JSON.

    Args:
        json_path: Path to the analyze-serp.py output JSON file.
    """

    def __init__(self, json_path: Path):
        self._path = Path(json_path)
        with open(self._path) as f:
            self._raw: dict = json.load(f)
        self._top_results: list[OrganicResult] | None = None
        self._paa_questions: list[str] | None = None
        self._ai_text: str | None = object  # sentinel — None is valid
        self._ai_refs: list[Reference] | None = None
        self._related: list[str] | None = None

    @property
    def keyword(self) -> str:
        return self._raw.get("keyword", "")

    @property
    def top_results(self) -> list[OrganicResult]:
        if self._top_results is None:
            raw = self._raw.get("top_results") or []
            self._top_results = [
                OrganicResult(
                    position=r.get("position", 0),
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("snippet", ""),
                )
                for r in raw
            ]
        return self._top_results

    @property
    def paa_questions(self) -> list[str]:
        if self._paa_questions is None:
            raw = self._raw.get("paa") or []
            self._paa_questions = [
                q.get("question", "") for q in raw if q.get("question")
            ]
        return self._paa_questions

    @property
    def paa_raw(self) -> list[dict]:
        """Full PAA entries with question, answer, position."""
        return self._raw.get("paa") or []

    @property
    def ai_overview_text(self) -> str | None:
        if self._ai_text is object:  # sentinel check
            ai = self._raw.get("ai_overview")
            if ai is None:
                self._ai_text = None
            else:
                blocks = ai.get("text_blocks", [])
                parts = []
                for block in blocks:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        if block.get("type") == "list":
                            for item in block.get("list", []):
                                if isinstance(item, str):
                                    parts.append(item)
                                elif isinstance(item, dict):
                                    parts.append(item.get("snippet", ""))
                        else:
                            parts.append(block.get("snippet", ""))
                self._ai_text = " ".join(parts).strip() or None
        return self._ai_text

    @property
    def ai_overview_references(self) -> list[Reference]:
        if self._ai_refs is None:
            ai = self._raw.get("ai_overview")
            if ai is None:
                self._ai_refs = []
            else:
                refs_raw = ai.get("references", [])
                refs = []
                for ref in refs_raw:
                    if isinstance(ref, dict):
                        refs.append(Reference(
                            url=ref.get("link", ref.get("url", "")),
                            title=ref.get("title", ""),
                            source=ref.get("source", ""),
                        ))
                    elif isinstance(ref, str) and ref.startswith("http"):
                        refs.append(Reference(url=ref, title=ref))
                self._ai_refs = refs
        return self._ai_refs

    @property
    def related_searches(self) -> list[str]:
        if self._related is None:
            self._related = [
                s for s in (self._raw.get("related_searches") or []) if s
            ]
        return self._related

    def average_word_count_top_5(self) -> int:
        """Average word count of top 5 organic results' page content.

        Returns 0 if page content is not available in the SERP data.
        The caller should fall back to the default 1800-2400 range.
        """
        # SERP JSON does not currently store full page content or word counts.
        # When serp-research adds word_count to top_results, this will use it.
        counts = []
        for r in self.top_results[:5]:
            raw_results = self._raw.get("top_results") or []
            for raw_r in raw_results:
                if raw_r.get("url") == r.url and "word_count" in raw_r:
                    counts.append(raw_r["word_count"])
                    break
        if counts:
            return sum(counts) // len(counts)
        return 0

    def subtopic_gap_analysis(self) -> dict[str, list[int]]:
        """Extract subtopic frequency map from top results' titles and snippets.

        Returns dict mapping subtopic phrases to list of result indices
        (0-based) that mention them. Useful for identifying coverage gaps.

        This is a heuristic based on available SERP data (titles + snippets).
        For production use, tools/extract-subtopic-gaps.py provides a more
        thorough LLM-assisted analysis.
        """
        # Extract meaningful phrases from each result
        result_phrases: list[set[str]] = []
        for r in self.top_results[:10]:
            text = f"{r.title} {r.snippet}".lower()
            # Extract 2-4 word noun phrases (simple heuristic)
            words = re.findall(r"[a-z]+(?:'[a-z]+)?", text)
            phrases: set[str] = set()
            for n in (3, 2):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i + n])
                    # Skip phrases that are mostly stopwords
                    stopwords = {"the", "a", "an", "in", "of", "to", "for", "and", "is", "are", "on", "at", "by", "or", "with"}
                    content_words = [w for w in words[i:i + n] if w not in stopwords]
                    if len(content_words) >= max(1, n - 1):
                        phrases.add(phrase)
            result_phrases.append(phrases)

        # Find phrases that appear across multiple results
        all_phrases: dict[str, list[int]] = {}
        for idx, phrases in enumerate(result_phrases):
            for phrase in phrases:
                if phrase not in all_phrases:
                    all_phrases[phrase] = []
                all_phrases[phrase].append(idx)

        # Filter to phrases appearing in 2+ results (meaningful subtopics)
        return {
            phrase: indices
            for phrase, indices in sorted(all_phrases.items(), key=lambda x: -len(x[1]))
            if len(indices) >= 2
        }

    def primary_sources(self, max: int = 3) -> list[Reference]:
        """Authoritative external references filtered for .gov/.edu/recognized domains.

        Deduplicates by domain. Returns up to `max` references.
        """
        seen_domains: set[str] = set()
        sources: list[Reference] = []

        # Check AI overview references first (often most authoritative)
        for ref in self.ai_overview_references:
            if _is_authoritative(ref.domain) and ref.domain not in seen_domains:
                seen_domains.add(ref.domain)
                sources.append(ref)
                if len(sources) >= max:
                    return sources

        # Then check top organic results
        for r in self.top_results:
            if _is_authoritative(r.domain) and r.domain not in seen_domains:
                seen_domains.add(r.domain)
                sources.append(Reference(url=r.url, title=r.title, source=r.domain))
                if len(sources) >= max:
                    return sources

        return sources
