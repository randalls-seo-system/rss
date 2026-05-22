"""Stage 5: SERP Fetch for Top Candidates.

Fetches top 10 organic SERP results for candidates that need scoring.
Respects serp_mode config (always / money_pages_only / never).
Rate-limited to 1 req/sec with backoff on 429.

No LLM calls. Serper API only.

Input: Candidates where we_have_it=0 and status='new'.
Output: SERP results cached to ~/.cache/rss-serp/{site_slug}/.
"""
