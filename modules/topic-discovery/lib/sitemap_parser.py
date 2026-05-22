"""XML sitemap parser for own-site and competitor sitemaps.

Handles:
- Standard sitemap.xml files (<urlset> with <url><loc> entries)
- Sitemap index files (<sitemapindex> with <sitemap><loc> entries)
- Graceful fallback when sitemap is missing or malformed

Uses lxml for fast XML parsing. Returns a list of SitemapEntry dataclasses
with url, lastmod (if present), and title (extracted from URL slug).

Provides:
- parse_sitemap(domain): fetch and parse sitemap, follow index if needed
- extract_title_from_slug(url): derive a rough page title from URL path
"""
