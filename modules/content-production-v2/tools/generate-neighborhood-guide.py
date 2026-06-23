#!/usr/bin/env python3
"""generate-neighborhood-guide.py — Standalone neighborhood guide generator.

Produces nh-* HTML matching the Stone Oak / East Austin gold standard.
Uses LLM for prose, deterministic skeleton for structure.

Usage:
    python3 generate-neighborhood-guide.py \\
        --site lrg \\
        --neighborhood "South Austin" \\
        --city "Austin" \\
        --metro "Austin" \\
        --post-id 99999 \\
        --output-dir ~/lrg-rewrite/guides/ \\
        [--data-json data.json]    # pre-researched data (optional) \\
        [--skip-deploy]
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

# ---------------------------------------------------------------------------
# HTML Builders (deterministic skeleton, LLM-generated prose)
# ---------------------------------------------------------------------------

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def build_hero(nb, city, metro, data, cta_ref, listings_url):
    """Hero: BLUF answer + dual CTA + 4 stat cards."""
    answer = data.get("hero_answer", f"{nb} is a neighborhood in {city}, TX.")
    stats = data.get("hero_stats", [
        {"val": "$400K–$600K", "label": "Price Range"},
        {"val": "—", "label": "School District"},
        {"val": "20 min", "label": "To Downtown"},
        {"val": "8.0", "label": "Walk Score"},
    ])

    stat_html = "\n".join(
        f'<div class="nh-qs"><div class="v">{s["val"]}</div><div class="l">{s["label"]}</div></div>'
        for s in stats[:4]
    )

    return f'''<div class="nh-hero">
<div class="nh-wrap">
<p class="nh-answer">{answer}</p>
<a href="/lrg-blog/connect-with-lrg/?ref={cta_ref}" class="nh-cta">Talk to a {metro} Agent &rarr;</a>
<a href="{listings_url}" class="nh-cta ghost">Search {city} Homes for Sale</a>
<div class="nh-qstats">{stat_html}</div>
</div>
</div>'''


def build_section(kicker, h2_title, content_html, alt=False):
    """Generic nh-blk section wrapper."""
    alt_cls = " alt" if alt else ""
    return f'''<section class="nh-blk{alt_cls}"><div class="nh-wrap">
<div class="nh-sec-head"><div class="nh-sec-kicker">{kicker}</div>
<h2 class="nh-sec-title">{h2_title}</h2></div>
{content_html}
</div></section>'''


def build_scorecard(items):
    """At-a-glance scorecard (4–7 items)."""
    cards = "\n".join(
        f'<div class="nh-sc-item"><div class="sc-val">{it["val"]}</div><div class="sc-label">{it["label"]}</div></div>'
        for it in items
    )
    return f'<div class="nh-scorecard">{cards}</div>'


def build_meters(meters):
    """Scored progress bars (5–8 items)."""
    color_map = {"green": "green", "navy": "navy", "gold": "gold", "red": "red"}
    bars = []
    for m in meters:
        score = m.get("score", 7.0)
        pct = int(min(score / 10.0, 1.0) * 100)
        color = m.get("color", "navy")
        bars.append(
            f'<div class="nh-meter">'
            f'<span class="m-label">{m["label"]}</span>'
            f'<div class="m-track"><div class="m-fill {color}" style="width:{pct}%"></div></div>'
            f'<span class="m-val">{score}</span>'
            f'</div>'
        )
    return f'<div class="nh-meters">\n' + "\n".join(bars) + '\n</div>'


def build_facts(cards):
    """Fact cards (2–4 cards, each with key-value rows)."""
    card_htmls = []
    for card in cards:
        rows = "\n".join(
            f'<div class="row"><b>{r["key"]}</b><span>{r["val"]}</span></div>'
            for r in card["rows"]
        )
        card_htmls.append(f'<div class="nh-fact-card"><div class="h">{card["title"]}</div><div class="b"><dl>{rows}</dl></div></div>')
    return f'<div class="nh-facts">\n' + "\n".join(card_htmls) + '\n</div>'


def build_fit(good_items, think_items, verify_text):
    """Good-fit / Think-twice panel + verify box."""
    good = "\n".join(f'<dt>{g["title"]}</dt><dd>{g["desc"]}</dd>' for g in good_items)
    think = "\n".join(f'<dt>{t["title"]}</dt><dd>{t["desc"]}</dd>' for t in think_items)

    return f'''<div class="nh-fit">
<div class="nh-panel good"><div class="ph2">Good fit if you want</div><div class="pb">{good}</div></div>
<div class="nh-panel warn"><div class="ph2">Think twice if</div><div class="pb">{think}</div></div>
</div>
<div class="nh-verify"><b>Before you commit:</b> {verify_text}</div>'''


def build_faqs(faqs):
    """FAQ section with schema."""
    details = ""
    schema_items = []
    for f in faqs:
        details += f'<details><summary>{f["q"]}</summary><div class="ans">{f["a"]}</div></details>\n'
        schema_items.append({
            "@type": "Question",
            "name": f["q"],
            "acceptedAnswer": {"@type": "Answer", "text": f["a"]}
        })

    schema = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": schema_items}, ensure_ascii=False)

    return f'''<div class="nh-faq">{details}</div>
<script type="application/ld+json">{schema}</script>'''


def build_resources(sources):
    """Linked sources section."""
    items = "\n".join(
        f'<li><a href="{s["url"]}" rel="noopener noreferrer" target="_blank">{s["name"]}</a>{" " + s.get("desc","") if s.get("desc") else ""}</li>'
        for s in sources
    )
    return f'<div class="nh-resources"><h3>Sources</h3><ul>{items}</ul></div>'


def build_related(guides):
    """Related guides links."""
    items = "\n".join(f'<li><a href="{g["url"]}">{g["label"]}</a></li>' for g in guides)
    return f'<ul>{items}</ul>'


def build_callout(items, tint="gray"):
    """Tinted callout box — scannable summary panel after a prose section.

    Stone Oak pattern: nh-callout with color rotation gray→beige→blue→green.
    Each callout has 3-5 bulleted key points summarizing the section.
    """
    bullets = "\n".join(f"<li>{item}</li>" for item in items)
    return f'<div class="nh-callout {tint}"><ul>\n{bullets}\n</ul></div>'


def build_endcta(nb, cta_ref, listings_url, city):
    """Bottom CTA."""
    return f'''<div class="nh-endcta">
<a href="/lrg-blog/connect-with-lrg/?ref={cta_ref}" class="nh-cta">Talk to an Agent About {nb} &rarr;</a>
<a href="{listings_url}" class="nh-cta ghost" style="margin-left:8px">Search {city} Homes &rarr;</a>
</div>'''


# ---------------------------------------------------------------------------
# LLM Prose Generation
# ---------------------------------------------------------------------------

def generate_section_prose(client, nb, city, h2_title, section_context, brand_voice, prior_summary="", serp_context=""):
    """Generate prose for a body section via LLM."""
    prompt = f"""You are writing one section of a neighborhood guide for {nb} in {city}, TX.
This is a legitimate pipeline call from generate-neighborhood-guide.py.

Section heading: "{h2_title}"
Context: {section_context}
{f"SERP competitor context: {serp_context}" if serp_context else ""}

Write 80-160 words of expert, practical prose about this topic. Rules:
- Write like a local real estate agent who knows the area
- Lead with the key insight, not background
- Include specific names, numbers, and local details
- No em dashes, use commas or periods instead
- No parentheses in body prose, restructure or use commas
- Capitalize Veteran and Military
- No filler: "it's important to note", "when it comes to", "discover", "vibrant"
- Short paragraphs, 2-3 sentences max

{f"Prior sections covered: {prior_summary}" if prior_summary else ""}
{f"Brand voice: {brand_voice}" if brand_voice else ""}

Return ONLY the prose HTML using <p> tags. No headings, no wrapper divs."""

    h = hashlib.md5(f"{nb}|{h2_title}|v2".encode()).hexdigest()[:12]
    cache_key = f"nh-guide-v2|{nb}|{h2_title}|{h}"
    response = client.call(prompt, cache_key=cache_key)
    return extract_html(response.text)


def generate_callout_bullets(client, nb, city, section_key, section_context, prose_text, serp_context=""):
    """Generate 3-5 scannable bullet points for a tinted callout box."""
    prompt = f"""You are writing a scannable summary callout for a neighborhood guide about {nb} in {city}, TX.
This is a legitimate pipeline call from generate-neighborhood-guide.py.

Section topic: {section_key}
Context: {section_context}
Section prose summary: {prose_text[:200]}
{f"SERP context: {serp_context}" if serp_context else ""}

Write exactly 4 bullet points that summarize the key takeaways from this section.
Each bullet: 8-20 words, starts with a concrete fact or number, no filler.
No em dashes. No parentheses. Capitalize Veteran and Military.

Return ONLY a JSON array of 4 strings. Example:
["Price range sits between $350K and $600K for most resale inventory", "NEISD schools rated A by TEA across the feeder pattern", "Rush-hour commute to downtown averages 25 minutes via US-281", "HOA dues range from $50 to $200 monthly depending on subdivision"]

Return ONLY the JSON array. No markdown fences."""

    h = hashlib.md5(f"{nb}|{section_key}|callout-v2".encode()).hexdigest()[:12]
    cache_key = f"nh-callout-v2|{nb}|{section_key}|{h}"
    response = client.call(prompt, cache_key=cache_key)

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        bullets = json.loads(raw)
        if isinstance(bullets, list) and len(bullets) >= 3:
            return bullets[:5]
    except json.JSONDecodeError:
        pass

    # Fallback: extract lines that look like bullets
    lines = [l.strip().strip('"').strip("- ") for l in raw.splitlines() if len(l.strip()) > 10]
    return lines[:4] if lines else ["Key details for this section are covered above"]


def generate_all_prose(client, nb, city, metro, data, brand_voice, serp_context=""):
    """Generate all LLM prose sections + callout bullets.

    Returns dict of section_key -> html for prose,
    and section_key -> list[str] for callout bullets.
    """
    prose = {}
    callouts = {}
    prior = ""

    # Callout color rotation matching Stone Oak: gray, beige, blue, green, gray, beige
    CALLOUT_COLORS = ["gray", "beige", "blue", "green", "gray", "beige"]
    # Sections that get callouts (all prose sections except bottom_line)
    CALLOUT_SECTIONS = ["about", "homes", "subcommunities", "schools", "commute", "buyer_checklist"]

    sections_to_generate = [
        ("about", f"What makes {nb} distinctive in the {city} market", data.get("about_context", "")),
        ("homes", f"Housing stock, price ranges, and property types in {nb}", data.get("homes_context", "")),
        ("subcommunities", f"Key sub-neighborhoods or subdivisions within {nb}", data.get("subcommunities_context", "")),
        ("schools", f"School districts and campuses serving {nb}", data.get("schools_context", "")),
        ("commute", f"Commute routes, distances, and rush-hour realities from {nb}", data.get("commute_context", "")),
        ("buyer_checklist", f"Practical due-diligence steps for buying in {nb}", data.get("checklist_context", "")),
        ("bottom_line", f"Summary verdict on {nb} as a place to buy", data.get("bottom_line_context", "")),
    ]

    from bs4 import BeautifulSoup
    for key, h2, context in sections_to_generate:
        eprint(f"  Generating prose: {key}")
        html = generate_section_prose(client, nb, city, h2, context, brand_voice, prior, serp_context)
        prose[key] = html
        text = BeautifulSoup(html, "html.parser").get_text(strip=True)[:150]
        prior += f"[{key}]: {text}\n"
        time.sleep(1)

        # Generate callout bullets for sections that need them
        if key in CALLOUT_SECTIONS:
            color_idx = CALLOUT_SECTIONS.index(key)
            eprint(f"  Generating callout: {key} ({CALLOUT_COLORS[color_idx]})")
            bullets = generate_callout_bullets(client, nb, city, key, context, text, serp_context)
            callouts[key] = {"bullets": bullets, "color": CALLOUT_COLORS[color_idx]}
            time.sleep(1)

    return prose, callouts


# ---------------------------------------------------------------------------
# Main Assembly
# ---------------------------------------------------------------------------

def assemble_guide(nb, city, metro, data, prose, callouts, cta_ref, listings_url):
    """Assemble the full nh-* HTML from data + prose + callouts.

    Matches the Stone Oak gold standard component-for-component:
    hero → about (scorecard+meters+prose+callout) → facts → homes (prose+callout)
    → subcommunities (prose+callout) → schools (prose+callout) → commute
    (prose+callout) → fit panels → checklist (prose+callout) → bottom line
    → FAQs → related+resources
    """
    parts = []

    def _prose_with_callout(section_key, prose_html):
        """Wrap prose in nh-prose div and append tinted callout if available."""
        block = f'<div class="nh-prose">{prose_html}</div>'
        if section_key in callouts:
            co = callouts[section_key]
            block += "\n" + build_callout(co["bullets"], co["color"])
        return block

    # 1. Hero
    parts.append(build_hero(nb, city, metro, data, cta_ref, listings_url))

    # 2. About section (scorecard + meters + prose + callout gray)
    scorecard = build_scorecard(data.get("scorecard", []))
    meters = build_meters(data.get("meters", []))
    about_block = _prose_with_callout("about", prose["about"])
    about_content = f'{scorecard}\n{meters}\n{about_block}'
    parts.append(build_section("About the Neighborhood", data.get("h2_about", f"{city}'s {nb} corridor"), about_content))

    # 3. Facts section (no callout — data tables only)
    facts_html = build_facts(data.get("fact_cards", []))
    parts.append(build_section("Key Facts", f"{nb} at a glance", facts_html, alt=True))

    # 4. Homes section (prose + callout beige)
    homes_block = _prose_with_callout("homes", prose["homes"])
    parts.append(build_section("Homes & Property Types", data.get("h2_homes", f"What {nb} offers buyers"), homes_block))

    # 5. Sub-communities (prose + callout blue)
    sub_block = _prose_with_callout("subcommunities", prose["subcommunities"])
    parts.append(build_section("Top Sub-Communities", data.get("h2_subcommunities", f"Where to focus inside {nb}"), sub_block, alt=True))

    # 6. Schools (prose + callout green)
    schools_block = _prose_with_callout("schools", prose["schools"])
    parts.append(build_section("Schools", data.get("h2_schools", f"Campuses that serve {nb}"), schools_block))

    # 7. Commute (prose + callout gray)
    commute_block = _prose_with_callout("commute", prose["commute"])
    parts.append(build_section("Location & Commute", data.get("h2_commute", f"Getting around from {nb}"), commute_block, alt=True))

    # 8. Fit section (good/think-twice + verify — no callout)
    fit_html = build_fit(
        data.get("good_fit", []),
        data.get("think_twice", []),
        data.get("verify_text", f"Verify school zone, HOA dues, tax rate, and commute time before committing to {nb}.")
    )
    parts.append(build_section("Is It Right For You?", data.get("h2_fit", f"Who {nb} fits"), fit_html))

    # 9. Buyer checklist (prose + callout beige)
    checklist_block = _prose_with_callout("buyer_checklist", prose["buyer_checklist"])
    parts.append(build_section("Buyer Checklist", data.get("h2_checklist", f"How to buy well in {nb}"), checklist_block, alt=True))

    # 10. Bottom line + endcta (no callout)
    bottom_prose = f'<div class="nh-prose">{prose["bottom_line"]}</div>'
    endcta = build_endcta(nb, cta_ref, listings_url, city)
    bottom_content = f'{bottom_prose}\n{endcta}'
    parts.append(build_section("The Bottom Line", data.get("h2_bottom", f"The verdict on {nb}"), bottom_content))

    # 11. FAQs
    faqs_html = build_faqs(data.get("faqs", []))
    parts.append(build_section("Common Questions", f"{nb} FAQs", faqs_html, alt=True))

    # 12. Related + Resources (populated with real links)
    related_html = build_related(data.get("related_guides", []))
    resources_html = build_resources(data.get("sources", []))
    related_section = f'{related_html}\n{resources_html}' if related_html.strip() != '<ul></ul>' else resources_html
    parts.append(build_section("Keep Exploring", f"Related {city} resources", related_section))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_guide_data(data_path):
    """Load pre-researched data from JSON file."""
    if data_path and Path(data_path).exists():
        with open(data_path) as f:
            return json.load(f)
    return {}


def build_default_data(nb, city, metro):
    """Build minimal default data structure. Caller should override with real data."""
    slug = _slug(nb)
    city_slug = _slug(city)

    return {
        "hero_answer": f"{nb} is a neighborhood in {city}, TX. [REPLACE WITH REAL BLUF]",
        "hero_stats": [
            {"val": "$XXX–$XXX", "label": "Price Range"},
            {"val": "—", "label": "School District"},
            {"val": "XX min", "label": "To Downtown"},
            {"val": "X.X", "label": "Walk Score"},
        ],
        "scorecard": [
            {"val": "$XXX–$XXX", "label": "Price Range"},
            {"val": "XX+", "label": "Subdivisions"},
            {"val": "XX min", "label": "To Downtown"},
            {"val": "—", "label": "School District"},
        ],
        "meters": [
            {"label": "Schools", "score": 7.0, "color": "green"},
            {"label": "Walkability", "score": 5.0, "color": "navy"},
            {"label": "Amenities", "score": 7.0, "color": "gold"},
            {"label": "Value", "score": 6.0, "color": "green"},
            {"label": "Safety", "score": 7.0, "color": "green"},
            {"label": "Commute", "score": 6.0, "color": "navy"},
        ],
        "fact_cards": [
            {"title": "Neighborhood Profile", "rows": [
                {"key": "Type", "val": "[TYPE]"},
                {"key": "Price range", "val": "$XXX to $XXX"},
                {"key": "Median", "val": "$XXXK"},
                {"key": "Housing stock", "val": "[YEARS AND TYPES]"},
                {"key": "Lot sizes", "val": "[RANGE]"},
            ]},
            {"title": "Location & Access", "rows": [
                {"key": "ZIP", "val": "XXXXX"},
                {"key": "Downtown", "val": "XX min via [ROUTE]"},
                {"key": "Airport", "val": "XX min"},
                {"key": "Grocery", "val": "[NEAREST]"},
            ]},
        ],
        "good_fit": [
            {"title": "[REASON 1]", "desc": "[EXPLANATION]"},
            {"title": "[REASON 2]", "desc": "[EXPLANATION]"},
            {"title": "[REASON 3]", "desc": "[EXPLANATION]"},
        ],
        "think_twice": [
            {"title": "[CONCERN 1]", "desc": "[EXPLANATION]"},
            {"title": "[CONCERN 2]", "desc": "[EXPLANATION]"},
            {"title": "[CONCERN 3]", "desc": "[EXPLANATION]"},
        ],
        "verify_text": f"Verify school zone, HOA dues, tax rate, flood zone, and commute time before committing to {nb}.",
        "faqs": [
            {"q": f"What is the median home price in {nb}?", "a": "[ANSWER]"},
            {"q": f"What school district serves {nb}?", "a": "[ANSWER]"},
            {"q": f"How far is {nb} from downtown {city}?", "a": "[ANSWER]"},
            {"q": f"Is {nb} a good place to buy?", "a": "[ANSWER]"},
            {"q": f"Is there new construction in {nb}?", "a": "[ANSWER]"},
        ],
        "sources": [
            {"name": "U.S. Census Bureau", "url": "https://data.census.gov/", "desc": "demographic data"},
            {"name": "FEMA Flood Maps", "url": "https://msc.fema.gov/portal/home", "desc": "flood zone verification"},
        ],
        "related_guides": [
            {"url": f"/listings/homes-for-sale-{city_slug}/", "label": f"{city} Homes for Sale"},
        ],
        "about_context": f"General overview of {nb} in {city}",
        "homes_context": f"Housing types and prices in {nb}",
        "subcommunities_context": f"Sub-areas within {nb}",
        "schools_context": f"Schools serving {nb}",
        "commute_context": f"Commute from {nb} to {city} employment centers",
        "checklist_context": f"Due diligence for buying in {nb}",
        "bottom_line_context": f"Overall verdict on {nb}",
    }


def populate_data_via_llm(client, nb, city, metro, data):
    """LLM-populate the data scaffold so no placeholders reach the final HTML.

    Calls the LLM once with a structured prompt to fill: hero stats,
    fact cards, good-fit/think-twice panels, FAQs, and hero answer.
    Returns updated data dict.
    """
    eprint("  Populating data scaffold via LLM...")

    prompt = f"""You are a local real estate data researcher for {city}, Texas.

Fill in the following neighborhood data for **{nb}** in **{city}**, **{metro}** metro.
Return ONLY a valid JSON object with these exact keys. Use real, verifiable data.
If you cannot confirm a number, use a reasonable estimate clearly labeled with "est."

{{
  "hero_answer": "A 3-sentence answer: what {nb} is, its key draw for buyers, and one concrete differentiator. Target 50-70 words.",
  "hero_stats": [
    {{"val": "$___K–$___K", "label": "Price Range"}},
    {{"val": "_____ ISD", "label": "School District"}},
    {{"val": "___ min", "label": "To Downtown"}},
    {{"val": "_._ est.", "label": "Walk Score"}}
  ],
  "fact_cards": [
    {{"title": "Neighborhood Profile", "rows": [
      {{"key": "Type", "val": "Gated / Master-planned / etc."}},
      {{"key": "Price range", "val": "$___K to $___K"}},
      {{"key": "Median", "val": "$___K"}},
      {{"key": "Housing stock", "val": "19XX–20XX, ranch/two-story/etc."}},
      {{"key": "Lot sizes", "val": "0.X–0.X acres"}}
    ]}},
    {{"title": "Location & Access", "rows": [
      {{"key": "ZIP", "val": "7XXXX"}},
      {{"key": "Downtown", "val": "XX min via Highway"}},
      {{"key": "Airport", "val": "XX min"}},
      {{"key": "Grocery", "val": "Name, X min"}}
    ]}}
  ],
  "good_fit": [
    {{"title": "Short reason 1", "desc": "1-2 sentence explanation"}},
    {{"title": "Short reason 2", "desc": "1-2 sentence explanation"}},
    {{"title": "Short reason 3", "desc": "1-2 sentence explanation"}}
  ],
  "think_twice": [
    {{"title": "Short concern 1", "desc": "1-2 sentence explanation"}},
    {{"title": "Short concern 2", "desc": "1-2 sentence explanation"}},
    {{"title": "Short concern 3", "desc": "1-2 sentence explanation"}}
  ],
  "faqs": [
    {{"q": "What is the median home price in {nb}?", "a": "1-2 sentence answer with a number"}},
    {{"q": "What school district serves {nb}?", "a": "1-2 sentence answer"}},
    {{"q": "How far is {nb} from downtown {city}?", "a": "1-2 sentence answer with drive time"}},
    {{"q": "Is {nb} a good place to buy?", "a": "1-2 sentence answer"}},
    {{"q": "Is there new construction in {nb}?", "a": "1-2 sentence answer"}}
  ]
}}

Use real school district names, real highway names, real grocery store names.
Capitalize Veteran and Military. No em dashes. No parentheses in prose.
Return ONLY the JSON. No markdown fences. No preamble."""

    import hashlib
    h = hashlib.md5(f"{nb}|{city}|data-scaffold".encode()).hexdigest()[:12]
    cache_key = f"nh-data|{nb}|{h}"

    response = client.call(prompt, cache_key=cache_key)
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        populated = json.loads(raw)
    except json.JSONDecodeError as e:
        eprint(f"  WARNING: LLM data JSON parse failed: {e}")
        eprint(f"  Raw response (first 300): {raw[:300]}")
        return data  # Return unmodified — publish gate will catch placeholders

    # Merge populated data into the scaffold
    for key in ["hero_answer", "hero_stats", "fact_cards", "good_fit", "think_twice", "faqs"]:
        if key in populated and populated[key]:
            data[key] = populated[key]
            eprint(f"    Populated: {key}")

    # Also update scorecard from hero_stats
    if "hero_stats" in populated:
        data["scorecard"] = populated["hero_stats"]

    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a neighborhood guide (nh-* format)")
    parser.add_argument("--site", required=True, help="Site slug (e.g., lrg)")
    parser.add_argument("--neighborhood", required=True, help="Neighborhood name")
    parser.add_argument("--city", required=True, help="City name")
    parser.add_argument("--metro", required=True, help="Metro (Austin, San Antonio, Killeen)")
    parser.add_argument("--post-id", required=True, type=int, help="WordPress post ID")
    parser.add_argument("--data-json", help="Pre-researched data JSON file")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--skip-llm", action="store_true", help="Use placeholder prose (for testing skeleton)")
    args = parser.parse_args()

    nb = args.neighborhood
    city = args.city
    metro = args.metro
    post_id = args.post_id

    # Config
    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    brand_voice = load_brand_voice(archetype) if archetype else ""

    # Output
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = Path.home() / f"{args.site}-rewrite" / "guides"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Data
    data = build_default_data(nb, city, metro)
    if args.data_json:
        override = load_guide_data(args.data_json)
        data.update(override)

    # LLM-populate the data scaffold (fact cards, fit panels, FAQs, hero)
    # unless --data-json already provided real data or --skip-llm is set
    if not args.skip_llm:
        provider = config.get("AI_PROVIDER", "claude_cli")
        model = config.get("AI_MODEL") or None
        data_client = LLMClient(provider=provider, model=model)
        data = populate_data_via_llm(data_client, nb, city, metro, data)

    # URLs
    nb_slug = _slug(nb)
    city_slug = _slug(city)
    cta_ref = f"{nb_slug}-neighborhood-guide"
    # Use listing page from data if provided, else generic city listings
    listings_url = data.get("listings_url", f"https://lrgrealty.com/listings/homes-for-sale-{city_slug}/")

    eprint(f"{'='*60}")
    eprint(f"NEIGHBORHOOD GUIDE GENERATOR")
    eprint(f"  Neighborhood: {nb}")
    eprint(f"  City: {city} | Metro: {metro}")
    eprint(f"  Post ID: {post_id}")
    eprint(f"  Output: {out_dir}")
    eprint(f"{'='*60}\n")

    # SERP Research — run analyze-serp.py if available
    serp_context = ""
    serp_cache_dir = Path.home() / f"{args.site}-rewrite" / "serp"
    serp_cache_dir.mkdir(parents=True, exist_ok=True)
    serp_slug = _slug(f"{nb} {city} neighborhood")
    serp_path = serp_cache_dir / f"{serp_slug}-serp.json"

    analyze_serp = REPO_ROOT / "modules" / "serp-research" / "tools" / "analyze-serp.py"
    if not args.skip_llm and analyze_serp.exists():
        if not serp_path.exists() or (time.time() - serp_path.stat().st_mtime) / 86400 > 7:
            eprint("  Running SERP analysis...")
            import subprocess
            try:
                subprocess.run(
                    [sys.executable, str(analyze_serp),
                     "--keyword", f"{nb} {city} neighborhood",
                     "--output-json", str(serp_path),
                     "--site", args.site],
                    capture_output=True, text=True, timeout=120
                )
            except Exception as e:
                eprint(f"  SERP analysis failed, continuing without: {e}")
        else:
            eprint(f"  Using cached SERP ({serp_path})")

        if serp_path.exists():
            try:
                serp_data = json.loads(serp_path.read_text())
                # Build SERP context from top results for LLM prompts
                top = serp_data.get("top_results", [])[:5]
                serp_lines = []
                for r in top:
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    if title:
                        serp_lines.append(f"- {title}: {snippet[:100]}")
                if serp_lines:
                    serp_context = "Top-ranking pages for this neighborhood:\n" + "\n".join(serp_lines)
                    eprint(f"  SERP context: {len(serp_lines)} competitors loaded")
            except Exception:
                pass

    # Populate related_guides with real links
    if not data.get("related_guides") or all("[" in g.get("label", "") for g in data.get("related_guides", [])):
        related = []
        # Gated communities article
        related.append({"url": "/lrg-blog/best-gated-communities-san-antonio/", "label": "Best Gated Communities in San Antonio"})
        # Listing page if provided in data
        if "listing_page_url" in data:
            related.append({"url": data["listing_page_url"], "label": f"{nb} Homes for Sale"})
        data["related_guides"] = related

    # Generate prose + callouts
    callouts = {}
    if args.skip_llm:
        eprint("--skip-llm: using placeholder prose")
        prose = {k: f"<p>[Placeholder prose for {k} section. Replace with LLM-generated content.]</p>"
                 for k in ["about", "homes", "subcommunities", "schools", "commute", "buyer_checklist", "bottom_line"]}
    else:
        provider = config.get("AI_PROVIDER", "claude_cli")
        model = config.get("AI_MODEL") or None
        client = LLMClient(provider=provider, model=model)
        prose, callouts = generate_all_prose(client, nb, city, metro, data, brand_voice, serp_context)

    # Assemble
    eprint("\nAssembling guide HTML...")
    html = assemble_guide(nb, city, metro, data, prose, callouts, cta_ref, listings_url)

    # PUBLISH GATE: check for placeholders and refusal text before writing
    from lib.html_sanitizer import _check_placeholder_tokens
    gate_errors = _check_placeholder_tokens(html)
    if gate_errors:
        eprint(f"\nPUBLISH GATE FAILED — {len(gate_errors)} error(s):")
        for err in gate_errors:
            eprint(f"  BLOCKED: {err}")
        eprint("\nContent contains unfilled placeholders or LLM refusal text.")
        eprint("Fix the data (provide --data-json) or re-run LLM prose generation.")
        sys.exit(1)
    eprint("Publish gate: PASS")

    # Write output
    article_path = out_dir / f"{post_id}-nh-guide.html"
    article_path.write_text(html)
    eprint(f"Written: {article_path} ({len(html)} bytes)")

    # Write manifest
    manifest = {
        "post_id": post_id,
        "neighborhood": nb,
        "city": city,
        "metro": metro,
        "site": args.site,
        "generator": "generate-neighborhood-guide.py",
        "format": "nh-guide",
        "word_count": len(html.split()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_json": args.data_json,
        "skip_llm": args.skip_llm,
    }
    manifest_path = out_dir / f"{post_id}-nh-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    eprint(f"Manifest: {manifest_path}")

    # Deploy
    if not args.skip_deploy:
        push_tool = REPO_ROOT / "modules" / "wp-deploy" / "tools" / "push-post-content.py"
        if push_tool.exists():
            eprint(f"\nDeploying to WordPress (post {post_id})...")
            import subprocess
            result = subprocess.run(
                [sys.executable, str(push_tool),
                 "--site", args.site,
                 "--post-id", str(post_id),
                 "--html-file", str(article_path),
                 "--status", "draft",
                 "--allow-no-manifest"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                eprint(f"Deployed as draft (post {post_id})")
            else:
                eprint(f"Deploy failed: {result.stderr[:200]}")
        else:
            eprint(f"Deploy tool not found: {push_tool}")

    eprint(f"\n{'='*60}")
    eprint(f"GUIDE COMPLETE: {nb}, {city}")
    eprint(f"{'='*60}")


if __name__ == "__main__":
    main()
