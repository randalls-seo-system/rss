"""Stage 4: Existing-Content Scrape.

Determines which topic candidates the site already covers by checking
the site's own sitemap.xml or WP REST API against the candidate list.

No LLM calls. HTTP + string matching.

Input: Deduped candidates in topics table, site domain from config.
Output: topics.we_have_it and topics.existing_url updated for matches.
"""
