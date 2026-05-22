"""Serper.dev API wrapper with fallback key support.

Wraps Serper's search, related searches, PAA, and autocomplete endpoints.
Uses the same fallback key pattern as content-production-v2: primary key
from SERPER_API_KEY env var, automatic retry with SERPER_API_KEY_FALLBACK
on quota errors (429).

Provides:
- search(query): top 10 organic results
- related_searches(query): related search suggestions
- paa(query): People Also Ask questions
- autocomplete(query): autocomplete suggestions for seed expansion

All methods return typed dataclass results and cache responses to
~/.cache/rss-serp/{site_slug}/ with configurable TTL.
"""
