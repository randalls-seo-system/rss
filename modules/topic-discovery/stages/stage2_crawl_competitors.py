"""Stage 2: Competitor Crawl.

Fetches competitor sitemaps, extracts page URLs and titles, and cross-
references against the topics table to count how many competitors cover
each candidate keyword.

No LLM calls. HTTP + XML parsing only.

Input: competitors from [topic_discovery] config section.
Output: competitor_pages table populated; topics.competitors_with_it updated.
"""
