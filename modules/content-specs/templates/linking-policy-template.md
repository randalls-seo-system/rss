# {{CLIENT_NAME}} — Internal Linking Policy

Applies to article body content only. Excludes nav, footer, breadcrumbs, TOC, related-post widgets, author boxes, pagination, and comments.

## Self-Link Prohibition

A page must never contain an internal link pointing to its own URL. Includes exact matches, trailing-slash variants, query-string variants, and hash variants.

## Linking Hierarchy

Every topic cluster must be woven together. No page should exist as an island.

### Cluster Structure — Three Tiers

**Tier 1 — Hub / Pillar Page:** Main landing page for the topic.
- Links DOWN to every spoke page in its cluster
- Links ACROSS to other related hub pages
- Receives inbound links from every spoke in its cluster

**Tier 2 — Spoke / Subtopic Pages:** Articles covering specific aspects.
- Links UP to parent hub within first 25% of content
- Links ACROSS to sibling spokes when intent overlaps
- Links DOWN to tool pages that help the reader act

**Tier 3 — Tool / Calculator Pages:** Interactive tools.
- Links UP to parent hub
- Receives inbound from EVERY spoke where tool is relevant

### Hierarchy Enforcement
- Spoke MUST link to parent hub
- Spoke MUST link to relevant tool pages at first contextual mention
- Hub MUST link to every published spoke
- New spoke published → hub MUST be updated

## Cluster Map

<!-- Define your site's topic clusters below -->
<!-- Format: Hub → spoke1 → spoke2 → tool1 → tool2 -->

- {{CLUSTER_1_NAME}}: {{CLUSTER_1_PAGES}}
- {{CLUSTER_2_NAME}}: {{CLUSTER_2_PAGES}}
- {{CLUSTER_3_NAME}}: {{CLUSTER_3_PAGES}}

## Per-Page Link Constraints

- Each destination URL: at most once per page
- Keep only first eligible contextual mention
- No same anchor text for different destinations
- No source page's primary keyword as anchor to different page
- No generic anchors: "click here", "read more", "learn more"
- One internal link per paragraph max
- No internal links in headings

## Restricted Zones — No Links Inside

- Callout boxes
- Table cells
- FAQ answers
- Disclaimer/legal blocks
- Bullet-section info boxes

## Link Targets Per Article

| Word Count | Internal Links |
|-----------|---------------|
| Under 1,000 | 3-6 |
| 1,000-1,800 | 5-10 |
| 1,800+ | 8-15 |

Never add links solely to hit a quota.

## Anchor Text Rules

- Use anchor-map.csv primary anchors 60%, variation 30%, natural phrases 10%
- Anchor text describes TARGET page, not current page
- 3-12 words, descriptive
- No bare acronyms (always expand)
- No single-word anchors (unless it IS the topic name)
- Word-boundary matching only (no sub-word splits)

## URL Repetition Rule

- Each URL: max 2 times per article (first body mention + Resources Used)
- Exception: primary CTA URL may appear up to 3 times

## External Link Rules

- External .gov/source links must NOT use anchor text matching an internal page topic
- Internal links must equal or exceed external links in count
- Each external source URL: max 3 times per article

---

*RSS Internal Linking Policy v1.1*
