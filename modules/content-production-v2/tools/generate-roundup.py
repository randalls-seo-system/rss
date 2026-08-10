#!/usr/bin/env python3
"""generate-roundup.py — Multi-neighborhood roundup generator.

Produces nh-rank format pages matching the flagship standard (2794/2790/2797/2095).
Each roundup ranks N neighborhoods with scorecard, meters, prose, and callout.

Usage:
    python3 generate-roundup.py \\
        --site lrg \\
        --metro "Austin" \\
        --title "Best Neighborhoods in Buda, TX (2026)" \\
        --neighborhoods neighborhoods.json \\
        --post-id 0 \\
        --output-dir ~/lrg-rewrite/roundups/ \\
        [--skip-deploy]

neighborhoods.json format:
[
  {
    "rank": 1,
    "name": "Sunfield",
    "tagline": "Best for new construction under $400K",
    "price_range": "$320K–$450K",
    "district": "Hays Cons ISD",
    "commute": "25 min to Austin",
    "walk_label": "Car-dependent",
    "meters": {"walkability": 3.0, "dining": 4.0, "value": 8.5, "commute": 6.0},
    "priority": "New construction value"
  },
  ...
]
"""
import argparse, json, os, re, sys, time, hashlib
from pathlib import Path
from datetime import datetime, timezone

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))

# Load .env
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

from lib.llm_client import LLMClient
from lib.site_config import load_site_config
from lib.tool_utils import eprint, extract_html, load_brand_voice

MIN_NEIGHBORHOODS = 5


# ---------------------------------------------------------------------------
# HTML Builders (deterministic skeleton)
# ---------------------------------------------------------------------------

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _slug_no_year(title):
    """Derive a URL slug from a title, stripping year suffixes.
    'Best Neighborhoods in Buda, TX (2026)' → 'best-neighborhoods-in-buda-tx'
    """
    # Strip (2026), (2025), etc.
    clean = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    return _slug(clean)


def _meter_color(val):
    if val >= 7.0:
        return "green"
    elif val >= 5.0:
        return "navy"
    elif val >= 3.0:
        return "gold"
    else:
        return "red"


def _price_tier(price_range):
    """Assign a tier class based on price range for the bar chart."""
    # Extract the lower bound
    m = re.search(r'\$(\d+)', price_range.replace(',', ''))
    if not m:
        return "tier1"
    low = int(m.group(1))
    if low >= 800:
        return "tier4"
    elif low >= 500:
        return "tier3"
    elif low >= 350:
        return "tier2"
    else:
        return "tier1"


def _price_low_bound(price_range):
    """Extract numeric lower bound from a price range string."""
    m = re.search(r'\$(\d+)', price_range.replace(',', ''))
    return int(m.group(1)) if m else 0


def _price_width(price_range, max_price):
    """Compute bar width as percentage of max price. max_price required."""
    low = _price_low_bound(price_range)
    return min(100, max(15, int(low / max(max_price, 1) * 100)))


def _article(word):
    """Return 'an' if word starts with a vowel sound, else 'a'."""
    return "an" if word and word[0].lower() in "aeiou" else "a"


def build_hero(city, title, answer_html, qstats, cta_ref):
    """Hero block with answer, CTAs, and qstats. Uses city, not metro."""
    qs_items = "\n".join(
        f'<div class="nh-qs"><div class="v">{s["val"]}</div><div class="l">{s["label"]}</div></div>'
        for s in qstats
    )
    article = _article(city)
    return f'''<div class="nh-hero">
<div class="nh-wrap">
<p class="nh-answer">{answer_html}</p>
<a class="nh-cta" href="/lrg-blog/connect-with-lrg/?ref={cta_ref}">Talk to {article} {city} Agent &rarr;</a>
<a class="nh-cta ghost" href="https://lrgrealty.com/listings/homes-for-sale-{_slug(city)}/">Search {city} Homes for Sale</a>
<div class="nh-qstats">
{qs_items}
</div>
</div>
</div>'''


def build_quick_match_table(neighborhoods):
    """Priority → neighborhood → price quick-match table."""
    rows = "\n".join(
        f'<tr><td>{nb["priority"]}</td><td>{nb["name"]} (#{nb["rank"]})</td><td>{nb["price_range"]}</td></tr>'
        for nb in neighborhoods if nb.get("priority")
    )
    return f'''<section class="nh-blk">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">Quick Match</div>
<h2 class="nh-sec-title">Match your priority to a neighborhood</h2>
</div>
<div class="nh-tbl-wrap">
<table>
<thead><tr><th>Your Priority</th><th>Start With</th><th>Price Range</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
</div>
</section>'''


def build_price_bars(neighborhoods):
    """Visual price comparison bar chart, sorted by price descending."""
    # Sort by lower price bound descending
    def _price_sort(nb):
        m = re.search(r'\$(\d+)', nb["price_range"].replace(',', ''))
        return int(m.group(1)) if m else 0

    sorted_nbs = sorted(neighborhoods, key=_price_sort, reverse=True)
    max_p = max(_price_low_bound(nb["price_range"]) for nb in sorted_nbs) if sorted_nbs else 500

    bars = "\n".join(
        f'<div class="nh-pbar"><span class="pb-name">{nb["name"]}</span>'
        f'<div class="pb-track"><div class="pb-fill {_price_tier(nb["price_range"])}" '
        f'style="width:{_price_width(nb["price_range"], max_p)}%">{nb["price_range"]}</div></div></div>'
        for nb in sorted_nbs
    )
    return f'''<section class="nh-blk alt">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">Price Comparison</div>
<h2 class="nh-sec-title">How the {len(neighborhoods)} stack up on price</h2>
</div>
<div class="nh-price-bars">
{bars}
</div>
<div class="nh-data-note">Prices are approximate ranges compiled from publicly available listings and market research. Verify current pricing with a local agent before making an offer.</div>
</div>
</section>'''


def build_rank_block(nb, prose_html, callout_bullets, alt=False):
    """Per-neighborhood nh-rank block with scorecard, meters, prose, callout."""
    alt_cls = " alt" if alt else ""

    # Scorecard
    sc_items = [
        {"val": nb["price_range"], "label": "Price Range"},
        {"val": nb["district"], "label": "School District"},
        {"val": nb.get("commute", "See guide"), "label": "Commute (off-peak)"},
        {"val": nb.get("walk_label", "See guide"), "label": "Walkability"},
    ]
    scorecard = "\n".join(
        f'<div class="nh-sc-item"><div class="sc-val">{s["val"]}</div><div class="sc-label">{s["label"]}</div></div>'
        for s in sc_items
    )

    # Meters
    meters_data = nb.get("meters", {})
    meter_items = []
    for key, label in [("walkability", "Walkability"), ("dining", "Dining/Retail"),
                       ("value", "Value"), ("commute", "Commute")]:
        val = meters_data.get(key, 5.0)
        color = _meter_color(val)
        width = int(val * 10)
        meter_items.append(
            f'<div class="nh-meter"><span class="m-label">{label}</span>'
            f'<div class="m-track"><div class="m-fill {color}" style="width:{width}%"></div></div>'
            f'<span class="m-val">{val:.1f}</span></div>'
        )
    meters_html = "\n".join(meter_items)

    # Callout
    bullets = "\n".join(f"<li>{b}</li>" for b in callout_bullets)
    callout_colors = ["gray", "beige", "blue", "green"]
    color = callout_colors[(nb["rank"] - 1) % len(callout_colors)]

    return f'''<div class="nh-rank{alt_cls}">
<div class="nh-wrap">
<div class="nh-rank-num">{nb["rank"]}</div>
<div class="nh-rank-head">
<div class="nh-rank-title">
<h2>{nb["name"]}</h2>
<div class="nh-rank-tagline">{nb["tagline"]}</div>
</div>
</div>
<div class="nh-scorecard">
{scorecard}
</div>
<div class="nh-meters">
{meters_html}
</div>
<div class="nh-prose">{prose_html}</div>
<div class="nh-callout {color}"><ul>
{bullets}
</ul></div>
</div>
</div>'''


def build_fit_panel(good_fit_items, think_twice_items):
    """Metro-level fit panel."""
    good_dts = "\n".join(f"<dt>{item}</dt><dd></dd>" for item in good_fit_items)
    warn_dts = "\n".join(f"<dt>{item}</dt><dd></dd>" for item in think_twice_items)
    return f'''<section class="nh-blk">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">Is It Right For You?</div>
<h2 class="nh-sec-title">Which lane fits your goals?</h2>
</div>
<div class="nh-fit">
<div class="nh-panel good"><div class="ph2">Good fit if you want</div><div class="pb">
{good_dts}
</div></div>
<div class="nh-panel warn"><div class="ph2">Think twice if</div><div class="pb">
{warn_dts}
</div></div>
</div>
</div>
</section>'''


def build_faq_section(faqs):
    """FAQ section with details/summary and JSON-LD."""
    details = "\n".join(
        f'<details><summary>{faq["q"]}</summary><div class="ans">{faq["a"]}</div></details>'
        for faq in faqs
    )
    schema_items = ",".join(
        json.dumps({"@type": "Question", "name": faq["q"],
                     "acceptedAnswer": {"@type": "Answer", "text": faq["a"]}})
        for faq in faqs
    )
    schema = f'{{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{schema_items}]}}'
    return f'''<section class="nh-blk alt">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">Common Questions</div>
<h2 class="nh-sec-title">Neighborhood FAQs</h2>
</div>
<div class="nh-faq">
{details}
</div>
<script type="application/ld+json">{schema}</script>
</div>
</section>'''


def build_prose_section(kicker, h2, prose_html, alt=False, data_note=None):
    """Generic prose section wrapper."""
    alt_cls = " alt" if alt else ""
    note = f'\n<div class="nh-data-note">{data_note}</div>' if data_note else ""
    return f'''<section class="nh-blk{alt_cls}">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">{kicker}</div>
<h2 class="nh-sec-title">{h2}</h2>
</div>
<div class="nh-prose">{prose_html}</div>{note}
</div>
</section>'''


# ---------------------------------------------------------------------------
# LLM Prose Generation
# ---------------------------------------------------------------------------

def generate_rank_prose(client, nb, metro, brand_voice, serp_context, vertical_rules):
    """Generate 60-80 word paragraph for one ranked neighborhood."""
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

You are writing ONE short paragraph (60-80 words) for a ranked neighborhood entry in a "Best Neighborhoods in {metro}" roundup guide.

Neighborhood: {nb['name']}
Tagline: {nb['tagline']}
Price range: {nb['price_range']}
School district: {nb['district']}
Commute: {nb.get('commute', 'varies')}

SERP research context:
{serp_context}

{vertical_rules}

Write 60-80 words of expert, practical prose. Lead with the key differentiator. Balance pros and cons. No em dashes. No unsupported superlatives. Capitalize Veteran and Military. District-level school references only — do NOT name specific campuses.

{brand_voice}

Return ONLY the HTML paragraph using <p> tags. No headings, no wrappers."""

    h = hashlib.md5(f"roundup|{metro}|{nb['name']}|v1".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-rank-v3|{metro}|{nb['name']}|{h}")
    return extract_html(response.text)


def generate_rank_callout(client, nb, metro, prose_text):
    """Generate 4 scannable bullets for a ranked neighborhood."""
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

Write exactly 4 scannable bullet points for {nb['name']} in a {metro} neighborhood roundup.

Context: {prose_text[:200]}
Price: {nb['price_range']}
District: {nb['district']}

Each bullet: bold lead phrase, then 8-15 word explanation. No em dashes.
Format: plain text, one per line, no HTML, no bullet markers.

DISTRICT-LEVEL school references only. Do NOT name specific campuses — use the district name ({nb['district']}).

Return exactly 4 lines."""

    h = hashlib.md5(f"roundup-co-v3|{metro}|{nb['name']}|v1".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-co-v3|{metro}|{nb['name']}|{h}")
    lines = [l.strip().lstrip("•-*123456789. ") for l in response.text.strip().split("\n") if l.strip()]
    return lines[:4] if lines else [f"{nb['name']} offers buyers a competitive option in {metro}."]


def generate_page_prose(client, metro, section_key, context, brand_voice, vertical_rules, neighborhoods):
    """Generate page-level prose section (methodology, Q&A, etc.)."""
    nb_list = ", ".join(nb["name"] for nb in neighborhoods)
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

You are writing one section of a "Best Neighborhoods in {metro}" roundup guide.

Section: {section_key}
Context: {context}
Neighborhoods covered: {nb_list}

{vertical_rules}

Write 60-120 words of practical prose. No em dashes. No unsupported superlatives. Capitalize Veteran and Military. DISTRICT-LEVEL school references only — no specific campus names.

{brand_voice}

Return ONLY the HTML using <p> tags. No headings."""

    h = hashlib.md5(f"roundup-page-v3|{metro}|{section_key}|v1".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-page-v3|{metro}|{section_key}|{h}")
    return extract_html(response.text)


def generate_hero_answer(client, metro, neighborhoods, brand_voice):
    """Generate the hero answer paragraph (~80 words)."""
    nb_summary = "; ".join(f"{nb['name']} ({nb['price_range']}, {nb['district']})" for nb in neighborhoods[:5])
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

Write an 80-word summary paragraph for a "Best Neighborhoods in {metro}" guide.

Top neighborhoods: {nb_summary}
Total ranked: {len(neighborhoods)}

Lead with the count and price range spread. Mention 3-4 specific neighborhoods by name with their key differentiator. End with the overall range. No em dashes.

Return ONLY the paragraph text, no HTML tags."""

    h = hashlib.md5(f"roundup-hero|{metro}|v3|{len(neighborhoods)}".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-hero|{metro}|{h}")
    return response.text.strip()


def generate_faqs(client, metro, neighborhoods, vertical_rules):
    """Generate 5-8 FAQs about the metro's neighborhoods."""
    nb_list = ", ".join(nb["name"] for nb in neighborhoods)
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

Write 6 FAQs about neighborhoods in {metro}, TX for a roundup guide.

Neighborhoods covered: {nb_list}

{vertical_rules}

Each FAQ: a question homebuyers actually ask about {metro} neighborhoods, and a 2-3 sentence answer. DISTRICT-LEVEL school references only. No em dashes. No "safest neighborhood" claims.

Return as JSON array: [{{"q": "...", "a": "..."}}, ...]"""

    h = hashlib.md5(f"roundup-faq|{metro}|v3|{len(neighborhoods)}".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-faq|{metro}|{h}")
    try:
        # Try to parse JSON from response
        text = response.text.strip()
        # Strip markdown fences if present
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except json.JSONDecodeError:
        return [{"q": f"What are the best neighborhoods in {metro}?",
                 "a": f"The top neighborhoods in {metro} vary by buyer priorities. See the ranked list above for details."}]


def generate_qa_sections(client, metro, neighborhoods, vertical_rules, brand_voice):
    """Generate 4 topical Q&A sections for the roundup."""
    nb_list = ", ".join(nb["name"] for nb in neighborhoods)
    districts = sorted(set(nb["district"] for nb in neighborhoods))
    prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

Write 4 topical Q&A sections for a "Best Neighborhoods in {metro}" roundup.

Neighborhoods: {nb_list}
Districts: {', '.join(districts)}

Each section needs a question as H2 and a 60-100 word answer. Topics:
1. How neighborhoods compare on affordability (reference specific neighborhoods and price ranges)
2. Which neighborhoods have the best school district access (district-level only, no campus names)
3. How commutes compare across neighborhoods (reference specific routes and times)
4. What buyers should know about property taxes in this area (do NOT state exact tax rates, say "verify with county CAD")

Do NOT use "safest neighborhood" framing. No em dashes. Feature-based language only, no demographic labels.

{vertical_rules}
{brand_voice}

Return as JSON array: [{{"kicker": "...", "h2": "...", "prose": "<p>...</p>"}}]"""

    h = hashlib.md5(f"roundup-qa|{metro}|v3|{len(neighborhoods)}".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"roundup-qa|{metro}|{h}")
    try:
        text = re.sub(r'^```json\s*', '', response.text.strip())
        text = re.sub(r'\s*```$', '', text)
        sections = json.loads(text)
        for i, s in enumerate(sections):
            s["alt"] = (i % 2 == 1)
        return sections[:4]
    except json.JSONDecodeError:
        return []


def inject_roundup_links(html, metro, neighborhoods):
    """Inject inline contextual links into roundup HTML.

    Links each neighborhood name in prose to its guide page (if exists),
    plus directory and listings links in page-level sections.
    """
    # Known guide pages (slug patterns for existing guides)
    guide_urls = {}
    for nb in neighborhoods:
        nb_slug = _slug(nb["name"])
        city_slug = _slug(metro)
        # Standard guide URL patterns
        guide_urls[nb["name"]] = f"/lrg-blog/{nb_slug}-neighborhood-guide/"

    # Also add directory and listings
    metro_slug = _slug(metro)
    directory_url = f"/{metro_slug}-neighborhoods/"
    listings_url = f"/listings/homes-for-sale-{metro_slug}/"

    # Split HTML into tags and text, only link in text nodes
    tag_or_text = re.compile(r'(<[^>]+>)', re.DOTALL)
    parts = tag_or_text.split(html)

    linked = set()  # track which neighborhoods already linked (first occurrence only)
    link_count = 0
    in_anchor = False

    for i, part in enumerate(parts):
        if part.startswith('<'):
            if part.startswith('<a ') or part.startswith('<a>'):
                in_anchor = True
            elif part.startswith('</a'):
                in_anchor = False
            continue
        if in_anchor:
            continue

        # Link neighborhood names (first occurrence of each)
        for nb_name, url in guide_urls.items():
            if nb_name in linked:
                continue
            # Match the exact name, not inside another word
            pattern = re.compile(r'\b' + re.escape(nb_name) + r'\b')
            m = pattern.search(part)
            if m:
                replacement = f'<a href="{url}">{nb_name}</a>'
                parts[i] = part[:m.start()] + replacement + part[m.end():]
                part = parts[i]  # update for subsequent matches
                linked.add(nb_name)
                link_count += 1

    html = ''.join(parts)

    # Add directory link to methodology section if not already present
    if directory_url not in html:
        # Insert into a prose section
        insert_marker = 'How we rank'
        idx = html.find(insert_marker)
        if idx > 0:
            p_end = html.find('</p>', idx)
            if p_end > 0:
                html = (html[:p_end] +
                        f' For a side-by-side comparison, see the <a href="{directory_url}">{metro} neighborhood directory</a>.' +
                        html[p_end:])
                link_count += 1

    # Add listings link
    if listings_url not in html:
        insert_marker = 'The Bottom Line'
        idx = html.find(insert_marker)
        if idx < 0:
            insert_marker = 'different paths'
            idx = html.find(insert_marker)
        if idx > 0:
            p_end = html.find('</p>', idx)
            if p_end > 0:
                html = (html[:p_end] +
                        f' Browse <a href="{listings_url}">{metro} homes for sale</a> to see current inventory.' +
                        html[p_end:])
                link_count += 1

    return html, link_count


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_roundup(city, metro, title, neighborhoods, prose_parts, faqs, cta_ref):
    """Assemble the full roundup HTML."""
    parts = []

    # 1. Hero
    # Numeric extraction for hero qstat price range
    all_lows = [_price_low_bound(nb["price_range"]) for nb in neighborhoods]
    def _price_high_bound(pr):
        nums = re.findall(r'\$(\d+)', pr.replace(',', ''))
        return int(nums[-1]) if nums else 0
    all_highs = [_price_high_bound(nb["price_range"]) for nb in neighborhoods]
    low_k = min(all_lows) if all_lows else 0
    high_k = max(all_highs) if all_highs else 0
    price_low = f"${low_k}K" if low_k < 1000 else f"${low_k/1000:.1f}M"
    price_high = f"${high_k}K+" if high_k < 1000 else f"${high_k/1000:.1f}M+"
    districts = sorted(set(nb["district"] for nb in neighborhoods))
    qstats = [
        {"val": f"{price_low}–{price_high}" if price_low != price_high else price_low, "label": "Price Range"},
        {"val": str(len(neighborhoods)), "label": "Neighborhoods Ranked"},
        {"val": f"{len(districts)} ISDs" if len(districts) > 1 else districts[0], "label": "School Districts"},
    ]
    parts.append(build_hero(city, title, prose_parts["hero"], qstats, cta_ref))

    # 2. Quick-match table
    parts.append(build_quick_match_table(neighborhoods))

    # 3. Price bars
    parts.append(build_price_bars(neighborhoods))

    # 4. Rank blocks (alternating)
    for i, nb in enumerate(neighborhoods):
        alt = (i % 2 == 1)
        parts.append(build_rank_block(nb, prose_parts["ranks"][i], prose_parts["callouts"][i], alt=alt))

    # 5. Methodology
    parts.append(build_prose_section(
        "Methodology", f"How we rank {metro} neighborhoods",
        prose_parts.get("methodology", "<p>Rankings reflect editorial assessment.</p>"),
        data_note="The final ranking is an editorial assessment informed by these factors rather than a purely mathematical calculation."
    ))

    # 6. Page-level Q&A sections
    for qa in prose_parts.get("qa_sections", []):
        parts.append(build_prose_section(qa["kicker"], qa["h2"], qa["prose"], alt=qa.get("alt", False)))

    # 7. Fit panel
    if prose_parts.get("fit_good") and prose_parts.get("fit_warn"):
        parts.append(build_fit_panel(prose_parts["fit_good"], prose_parts["fit_warn"]))

    # 8. Closing prose
    if prose_parts.get("closing"):
        parts.append(build_prose_section(
            "The Bottom Line",
            f"{len(neighborhoods)} neighborhoods, {len(neighborhoods)} different paths",
            prose_parts["closing"]
        ))

    # 9. FAQ
    parts.append(build_faq_section(faqs))

    # 10. Related guides
    parts.append(f'''<section class="nh-blk">
<div class="nh-wrap">
<div class="nh-sec-head">
<div class="nh-sec-kicker">Keep Exploring</div>
<h2 class="nh-sec-title">{metro} neighborhood guides</h2>
</div>
<ul>
<li><a href="/{_slug(metro)}-neighborhoods/">{metro} Neighborhood Directory</a></li>
<li><a href="/listings/homes-for-sale-{_slug(metro)}/">{metro} Homes for Sale</a></li>
</ul>
</div>
</section>''')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a multi-neighborhood roundup page")
    parser.add_argument("--site", required=True)
    parser.add_argument("--city", required=True, help="City name for hero, CTAs, listings (e.g. Belton, Buda)")
    parser.add_argument("--metro", required=True, help="Metro area for regional context (e.g. Austin, Killeen)")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--neighborhoods", required=True, help="JSON file with neighborhood list")
    parser.add_argument("--post-id", type=int, default=0)
    parser.add_argument("--author", type=int, default=28, help="WP user ID for post_author (default: 28 Jason Szakel)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--skip-llm", action="store_true", help="Use placeholder prose")
    args = parser.parse_args()

    city = args.city
    metro = args.metro
    post_id = args.post_id

    # Load neighborhoods
    nbs = json.loads(Path(args.neighborhoods).read_text())
    if len(nbs) < MIN_NEIGHBORHOODS:
        eprint(f"HARD STOP: {len(nbs)} neighborhoods (minimum {MIN_NEIGHBORHOODS})")
        sys.exit(1)

    # Sort by rank
    nbs.sort(key=lambda x: x.get("rank", 99))

    # Config
    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    brand_voice = load_brand_voice(archetype) if archetype else ""

    # Vertical rules
    from lib.brand_rules import load_vertical_rules_block
    vertical_block = load_vertical_rules_block(args.site)

    # Output
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # SERP context
    serp_context = ""
    serp_dir = Path.home() / f"{args.site}-rewrite" / "serp"
    metro_slug = _slug(metro)
    serp_candidates = list(serp_dir.glob(f"*{metro_slug}*-serp.json"))
    if serp_candidates:
        try:
            serp_data = json.loads(serp_candidates[0].read_text())
            top = serp_data.get("top_results", [])[:5]
            serp_context = "\n".join(f"- {r.get('title','')}: {r.get('snippet','')[:100]}" for r in top)
        except Exception:
            pass

    eprint(f"{'='*60}")
    eprint(f"ROUNDUP GENERATOR")
    eprint(f"  Metro: {metro}")
    eprint(f"  Title: {args.title}")
    eprint(f"  Neighborhoods: {len(nbs)}")
    eprint(f"  Post ID: {post_id}")
    eprint(f"  Output: {out_dir}")
    eprint(f"{'='*60}\n")

    # Generate prose
    prose_parts = {"ranks": [], "callouts": []}

    if args.skip_llm:
        eprint("--skip-llm: using placeholder prose")
        prose_parts["hero"] = f"{metro}'s {len(nbs)} strongest neighborhoods for buyers in 2026."
        for nb in nbs:
            prose_parts["ranks"].append(f"<p>{nb['name']} placeholder prose.</p>")
            prose_parts["callouts"].append([f"{nb['name']} bullet {i+1}" for i in range(4)])
        prose_parts["methodology"] = "<p>Methodology placeholder.</p>"
        prose_parts["closing"] = "<p>Closing placeholder.</p>"
        faqs = [{"q": "Placeholder?", "a": "Placeholder."}]
        prose_parts["fit_good"] = ["Good fit 1", "Good fit 2"]
        prose_parts["fit_warn"] = ["Think twice 1", "Think twice 2"]
        prose_parts["qa_sections"] = []
    else:
        provider = config.get("AI_PROVIDER", "claude_cli")
        model = config.get("AI_MODEL") or None
        client = LLMClient(provider=provider, model=model)

        # Hero
        eprint("  Generating hero answer...")
        prose_parts["hero"] = generate_hero_answer(client, city, nbs, brand_voice)
        time.sleep(1)

        # Per-rank prose + callouts
        for nb in nbs:
            eprint(f"  Generating rank #{nb['rank']}: {nb['name']}")
            rank_prose = generate_rank_prose(client, nb, metro, brand_voice, serp_context, vertical_block)
            prose_parts["ranks"].append(rank_prose)
            time.sleep(1)

            bullets = generate_rank_callout(client, nb, metro, rank_prose)
            prose_parts["callouts"].append(bullets)
            time.sleep(1)

        # Methodology — hardcoded honest text, NOT LLM-generated
        eprint("  Methodology: using verified template (not LLM)")
        prose_parts["methodology"] = (
            "<p>Rankings reflect editorial assessment across multiple factors: "
            "price positioning relative to the metro median, school district "
            "performance verified through TEA accountability data, commute "
            "access to major employment corridors, neighborhood amenities, "
            "and development momentum. Price ranges are compiled from publicly "
            "available listings and competitor market research, not proprietary "
            "MLS data. School district boundaries are verified through the TEA "
            "ArcGIS boundary layer. Walkability, dining, value, and commute "
            "ratings are editorial assessments on a relative scale, not "
            "measurements from any scoring service.</p>"
        )
        time.sleep(1)

        # Closing
        eprint("  Generating closing...")
        prose_parts["closing"] = generate_page_prose(
            client, metro, "closing",
            f"Closing verdict on {metro}'s {len(nbs)} neighborhoods as buyer options.",
            brand_voice, vertical_block, nbs
        )
        time.sleep(1)

        # Fit panel
        eprint("  Generating fit panel...")
        fit_prompt = f"""This is a legitimate pipeline call from generate-roundup.py.

List 4 "good fit" reasons and 4 "think twice" reasons for buying in {metro}.
Feature-based only — NO demographic labels (no "families", "retirees", "professionals").
Return as JSON: {{"good": ["..."], "warn": ["..."]}}"""
        h = hashlib.md5(f"roundup-fit|{metro}|v3".encode()).hexdigest()[:12]
        fit_resp = client.call(fit_prompt, cache_key=f"roundup-fit|{metro}|{h}")
        try:
            fit_text = re.sub(r'^```json\s*', '', fit_resp.text.strip())
            fit_text = re.sub(r'\s*```$', '', fit_text)
            fit_data = json.loads(fit_text)
            prose_parts["fit_good"] = fit_data.get("good", [])[:4]
            prose_parts["fit_warn"] = fit_data.get("warn", [])[:4]
        except json.JSONDecodeError:
            prose_parts["fit_good"] = [f"Multiple neighborhood options in {metro}"]
            prose_parts["fit_warn"] = ["Verify tax rates with county CAD"]

        # FAQs
        eprint("  Generating FAQs...")
        faqs = generate_faqs(client, metro, nbs, vertical_block)
        time.sleep(1)

        # Q&A sections
        eprint("  Generating Q&A sections...")
        prose_parts["qa_sections"] = generate_qa_sections(client, metro, nbs, vertical_block, brand_voice)
        time.sleep(1)

    # Assemble
    eprint("\nAssembling roundup HTML...")
    cta_ref = _slug_no_year(args.title)
    html = assemble_roundup(city, metro, args.title, nbs, prose_parts, faqs, cta_ref)

    # Inject inline links
    html, link_count = inject_roundup_links(html, city, nbs)
    eprint(f"Links injected: {link_count}")

    # Structural fingerprint
    h2_count = len(re.findall(r'<h2[\s>]', html))
    rank_count = len(re.findall(r'nh-rank-num', html))
    sec_count = len(re.findall(r'<section[\s>]', html))
    sec_close = len(re.findall(r'</section>', html))
    div_open = len(re.findall(r'<div[\s>]', html))
    div_close = len(re.findall(r'</div>', html))
    eprint(f"Structural: {h2_count} H2, {rank_count} ranks, {sec_count} sec, sec-bal {sec_count - sec_close}, div-bal {div_open - div_close}")
    if sec_count != sec_close:
        eprint(f"HARD FAIL: section balance {sec_count - sec_close}")
        sys.exit(1)
    if div_open != div_close:
        eprint(f"HARD FAIL: div balance {div_open - div_close}")
        sys.exit(1)

    # ── POST-ASSEMBLY CLEANUP (runs before file write) ──
    from lib.post_assembly import run_all_passes
    html, pass_log = run_all_passes(html)
    for entry in pass_log:
        eprint(f"  {entry}")

    # ── UNIVERSAL GATE (must pass before file write) ──
    from lib.gate_library import run_universal_gates
    gate_report = run_universal_gates(
        html,
        site_slug=args.site,
        title=args.title,
        content_type="roundup",
    )
    if not gate_report.passed:
        eprint(f"\nUNIVERSAL GATE FAILED — refusing to write output:")
        for fail in gate_report.failures:
            eprint(f"  [{fail.name}] {fail.detail}")
        sys.exit(1)
    eprint("Universal gate: PASS")

    # Write output
    article_path = out_dir / f"{post_id}-roundup.html"
    article_path.write_text(html)
    eprint(f"Written: {article_path} ({len(html)} bytes)")

    # 6. Author assignment
    from lib.post_assembly import resolve_author
    override = args.author if hasattr(args, 'author') and args.author else None
    author_id, author_reason = resolve_author(config, target_keyword=args.title, override_id=override)
    eprint(f"  Author: user {author_id} ({author_reason})")

    # Manifest
    manifest = {
        "post_id": post_id,
        "city": city,
        "metro": metro,
        "title": args.title,
        "suggested_slug": _slug_no_year(args.title),
        "suggested_author": author_id,
        "generator": "generate-roundup.py",
        "format": "nh-rank",
        "neighborhood_count": len(nbs),
        "rank_blocks": rank_count,
        "h2_count": h2_count,
        "byte_count": len(html),
        "emdash_count": emdash_count,
        "fh_fixes": fh_fixes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = out_dir / f"{post_id}-roundup-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    eprint(f"Manifest: {manifest_path}")

    eprint(f"\n{'='*60}")
    eprint(f"ROUNDUP COMPLETE: {args.title}")
    eprint(f"  {len(nbs)} neighborhoods, {len(html)} bytes, {rank_count} rank blocks")
    eprint(f"{'='*60}")


if __name__ == "__main__":
    main()
