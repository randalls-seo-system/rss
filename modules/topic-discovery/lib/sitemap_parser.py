"""XML sitemap parser for own-site and competitor sitemaps.

Handles:
- Standard sitemap.xml files (<urlset> with <url><loc> entries)
- Sitemap index files (<sitemapindex> with <sitemap><loc> entries)
- Fallback: when a competitor has no public sitemap.xml, crawls top-level
  category pages and extracts linked article URLs. Logs a warning when
  this fallback path is used. Default behavior is sitemap-only.

Uses lxml for fast XML parsing. Returns a list of SitemapEntry dataclasses
with url, lastmod (if present), and title (extracted from URL slug).

Provides:
- parse_sitemap(domain): fetch and parse sitemap, follow index if needed
- crawl_category_pages(domain): fallback when sitemap is unavailable
- extract_title_from_slug(url): derive a rough page title from URL path
"""
