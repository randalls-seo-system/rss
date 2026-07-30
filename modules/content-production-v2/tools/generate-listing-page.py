#!/usr/bin/env python3
"""
generate-listing-page.py — Data-driven listing page generator for LRG.

Creates listing_page CPT posts matching the 12-section full-city pattern.
Reference pages: Timberwood Park (5109), Boerne (5070).
Pure template — all editorial content comes from the per-place JSON data file.
No LLM prose generation.

Usage:
    python generate-listing-page.py --data-file listing-data/places/stone-oak.json \\
        --install lrgrealtybgstg --noindex
    python generate-listing-page.py --data-file listing-data/places/stone-oak.json --dry-run

Sections (matching live pattern):
    1.  ls-intro-band   — eyebrow, H1, intro paragraph, CTA
    2.  ls-iframe-band  — Ylopo search iframe
    3.  Market Data     — 5-stat row
    4.  Demographics    — canvas chart + city-vs-county KV (bg-soft)
    5.  Commute Times   — table (bg-soft)
    6.  Buyer Briefing  — good/warn panels
    7.  Costs           — property tax, closing, HOA (bg-soft)
    8.  Neighborhoods   — hood cards with optional guide links
    9.  Schools         — tabbed tables (bg-soft)
    10. Link Grid       — 8-col Ylopo search links
    11. FAQ             — accordion + FAQPage JSON-LD
    12. End CTA         — (embedded in FAQ section)

Spec discrepancies (live page wins):
    - FAQ JSON-LD is inline <script> in post_content on listing pages.
      CLAUDE.md says no scripts in post_content, but live pages work this way.
      Neighborhood guides use _lrg_faq_jsonld meta instead, but listing_page
      CPT does not have that mu-plugin hook.
    - Demographics + Commute are consecutive bg-soft sections (not alternating).
    - _rl_pre_nbhd_link meta exists on live pages (link injector backup);
      NOT set at creation time.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import html as html_mod


YLOPO_BASE = "https://search.lrgrealty.com/search"
CONNECT_URL = "https://lrgrealty.com/lrg-blog/connect-with-lrg/"
PAYMENT_CHECKLIST = "https://lrgrealty.com/lrg-blog/monthly-payment-stack-checklist"

SSH_CONFIGS = {
    "lrgrealtyblog": {
        "host": "lrgrealtyblog@lrgrealtyblog.ssh.wpengine.net",
        "key": "~/.ssh/wpengine_valn",
    },
    "lrgrealtybgstg": {
        "host": "lrgrealtybgstg@lrgrealtybgstg.ssh.wpengine.net",
        "key": "~/.ssh/id_ed25519_wpe_staging",
    },
}


# ── URL Helpers ───────────────────────────────────────────────────


def _enc(raw):
    """Encode Ylopo param string: [] -> %5B%5D, , -> %2C, space -> %20."""
    return (raw.replace("[", "%5B").replace("]", "%5D")
               .replace(",", "%2C").replace(" ", "%20"))


def _ylopo(scope_params, extra=""):
    """Build full Ylopo search URL from raw scope + optional extra filter."""
    raw = "s[orderBy]=sourceCreationDate,desc&s[page]=1&" + scope_params
    if extra:
        raw += "&" + extra
    return YLOPO_BASE + "?" + _enc(raw)


def ylopo_scope(d, extra=""):
    """Ylopo URL using the page's IDX scope."""
    idx = d["idx"]
    key = {"city": "city", "neighborhood": "neighborhood",
           "subdivision": "subdivision"}[idx["scope_type"]]
    params = (f"s[locations][0][{key}]={idx['scope_value']}"
              f"&s[locations][0][state]={d.get('state', 'TX')}")
    return _ylopo(params, extra)


def ylopo_city(city, state="TX"):
    return _ylopo(f"s[locations][0][city]={city}&s[locations][0][state]={state}")


def ylopo_county(county, state="TX"):
    return _ylopo(f"s[locations][0][county]={county}&s[locations][0][state]={state}")


def ylopo_zip(zip_code, state="TX"):
    return _ylopo(f"s[locations][0][postalCode]={zip_code}"
                  f"&s[locations][0][state]={state}")


def esc(text):
    """HTML-escape text for safe embedding."""
    return html_mod.escape(str(text)) if text else ""


# ── Section Builders ──────────────────────────────────────────────
# Each returns (html_string, list_of_gap_messages).


def sec_intro(d):
    gaps = []
    intro = d.get("intro", {})
    place = d["place_name"]
    text = intro.get("text")
    if not text:
        gaps.append("intro: missing intro text")
        return "", gaps
    eyebrow = intro.get("eyebrow",
                        f"LRG Realty &middot; {esc(d.get('county', ''))} County")
    ref = intro.get("cta_ref",
                    place.lower().replace(" ", "-") + "-listing")
    cta = intro.get("cta_label",
                    f"Talk to an LRG Agent About {esc(place)}")
    return (
        f'<div class="ls-intro-band"><div class="wrap">'
        f'<div class="ls-eyebrow">{eyebrow}</div>'
        f'<h1 class="ls-h1">Homes for Sale in {esc(place)}, TX</h1>'
        f'<p class="ls-intro-text">{text}</p>'
        f'<a href="{CONNECT_URL}?ref={esc(ref)}" class="ls-cta">'
        f'{cta} <span class="arr">&rarr;</span></a>'
        f'</div></div>'
    ), gaps


def sec_iframe(d):
    if "idx" not in d or not d["idx"].get("scope_value"):
        return "", ["iframe: missing IDX scope"]
    place = d["place_name"]
    src = ylopo_scope(d)
    return (
        f'<div class="ls-iframe-band"><div class="ls-iframe-wrap">'
        f'<iframe src="{src}" width="100%" height="100%" loading="lazy" '
        f'title="Homes for Sale in {esc(place)}, TX"></iframe>'
        f'</div></div>'
    ), []


def sec_market(d):
    gaps = []
    m = d.get("market")
    if not m:
        return "", ["market: section data missing"]
    place = d["place_name"]
    fields = [("median_price", "Median Price"), ("dom", "Days on Market"),
              ("active_listings", "Active Listings"),
              ("price_per_sqft", "Per Sq Ft"), ("median_rent", "Median Rent")]
    missing = [lab for key, lab in fields if not m.get(key)]
    if missing:
        gaps.append(f"market: missing {', '.join(missing)}")
    stats = "".join(
        f'<div class="stat"><div class="v">{esc(m.get(k, "\u2014"))}</div>'
        f'<div class="l">{esc(lab)}</div></div>'
        for k, lab in fields)
    src = m.get("source_note_html", "")
    if not src:
        gaps.append("market: missing source note")
    return (
        f'<section class="blk"><div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Market Data</div>'
        f'<h2 class="sec-title">{esc(place)} Market Snapshot</h2></div>'
        f'<div class="stat-row">{stats}</div>'
        f'<p class="src-note">{src}</p>'
        f'</div></section>'
    ), gaps


def sec_demographics(d):
    dem = d.get("demographics")
    if not dem:
        return "", ["demographics: section data missing"]
    place = d["place_name"]
    county = d.get("county", "")
    owner = dem.get("owner_pct", 0)
    renter = dem.get("renter_pct", 0)
    kvs = [
        ("Population",
         f'{dem.get("city_population", "\u2014")} / '
         f'{dem.get("county_population", "\u2014")}'),
        ("Median household income",
         f'{dem.get("city_median_income", "\u2014")} / '
         f'{dem.get("county_median_income", "\u2014")}'),
        ("Median home value", dem.get("median_home_value", "\u2014")),
        ("Median age", f'{dem.get("median_age", "\u2014")} yrs'),
        ("Population growth",
         f'{dem.get("population_growth", "\u2014")} '
         f'({dem.get("growth_period", "")})'),
    ]
    kv_html = "".join(
        f'<li><b>{esc(k)}</b><span class="val">{esc(v)}</span></li>'
        for k, v in kvs)
    src = dem.get("source_note_html",
        'Source: <a href="https://data.census.gov/" target="_blank" '
        'rel="noopener">U.S. Census Bureau</a>, American Community Survey '
        '5-Year Estimates (2019&ndash;2023).')
    return (
        f'<section class="blk" style="background:var(--bg-soft);">'
        f'<div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Census ACS 5-Year</div>'
        f'<h2 class="sec-title">{esc(place)} Demographics</h2>'
        f'<p class="sec-sub">Population, income, and housing tenure for the '
        f'city and surrounding {esc(county)} County.</p></div>'
        f'<div class="grid2">'
        f'<div class="card"><div class="card-h">Housing Tenure &amp; '
        f'Population</div><div class="card-b"><div class="chart-box">'
        f'<canvas id="tenureChart" data-owner="{owner}" '
        f'data-renter="{renter}"></canvas></div>'
        f'<div class="mini-legend">'
        f'<span><i class="dot" style="background:#1A365D"></i>'
        f'Owner-occupied</span>'
        f'<span><i class="dot" style="background:#C9A961"></i>'
        f'Renter-occupied</span></div></div></div>'
        f'<div class="card"><div class="card-h">City vs County</div>'
        f'<div class="card-b"><ul class="kv">{kv_html}</ul>'
        f'</div></div></div>'
        f'<p class="src-note">{src}</p>'
        f'</div></section>'
    ), []


def sec_commute(d):
    com = d.get("commute")
    if not com or not com.get("routes"):
        return "", ["commute: section data missing or no routes"]
    place = d["place_name"]
    desc = com.get("description", "")
    sub = f'<p class="sec-sub">{desc}</p>' if desc else ""
    rows = "".join(
        f'<tr><td>{esc(r["destination"])}</td><td>{esc(r["distance"])}</td>'
        f'<td>{esc(r["off_peak"])}</td><td>{esc(r["rush_hour"])}</td></tr>'
        for r in com["routes"])
    src = com.get("source_note",
        f"Drive times are approximate estimates from {place}. "
        f"Actual times vary by route and traffic conditions.")
    return (
        f'<section class="blk" style="background:var(--bg-soft);">'
        f'<div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Drive Times</div>'
        f'<h2 class="sec-title">{esc(place)} Commute Times</h2>{sub}</div>'
        f'<div class="tbl-wrap"><table><thead><tr>'
        f'<th>Destination</th><th>Distance</th>'
        f'<th>Off-Peak</th><th>Rush Hour</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>'
        f'<p class="src-note">{esc(src)}</p>'
        f'</div></section>'
    ), []


def sec_briefing(d):
    b = d.get("briefing")
    if not b:
        return "", ["briefing: section data missing"]
    place = d["place_name"]
    good = b.get("good", [])
    warn = b.get("warn", [])
    if not good and not warn:
        return "", ["briefing: no good or warn items"]

    def dl(items):
        return "".join(
            f'<dt>{esc(i["title"])}</dt><dd>{esc(i["description"])}</dd>'
            for i in items)

    good_h = (
        f'<div class="panel good">'
        f'<div class="panel-h">&#10003; Why Buy in {esc(place)}</div>'
        f'<div class="panel-b"><dl>{dl(good)}</dl></div></div>'
    ) if good else ""
    warn_h = (
        f'<div class="panel warn">'
        f'<div class="panel-h">&#9888; What to Watch For</div>'
        f'<div class="panel-b"><dl>{dl(warn)}</dl></div></div>'
    ) if warn else ""
    src = b.get("source_note_html",
        'Flood data: <a href="https://www.fema.gov/flood-maps" '
        'target="_blank" rel="noopener">FEMA Flood Map Service Center</a>.')
    return (
        f'<section class="blk"><div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Buyer Briefing</div>'
        f'<h2 class="sec-title">{esc(place)} at a Glance</h2></div>'
        f'<div class="glance">{good_h}{warn_h}</div>'
        f'<p class="src-note">{src}</p>'
        f'</div></section>'
    ), []


def sec_costs(d):
    c = d.get("costs")
    if not c or not c.get("items"):
        return "", ["costs: section data missing"]
    place = d["place_name"]
    # Description may contain $ amounts; kept as pre-sanitized text
    dl = "".join(
        f'<dt>{esc(i["title"])}</dt><dd>{i["description"]}</dd>'
        for i in c["items"])
    tax_p = ""
    if c.get("tax_source_html"):
        tax_p = (f'<p class="src-note" style="margin-top:14px;">'
                 f'{c["tax_source_html"]}</p>')
    pay_p = (f'<p class="tbl-note" style="margin-top:8px;">Use our '
             f'<a href="{PAYMENT_CHECKLIST}">monthly payment stack '
             f'checklist</a> to estimate your all-in housing cost.</p>')
    return (
        f'<section class="blk" style="background:var(--bg-soft);">'
        f'<div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Costs &amp; '
        f'Timeline</div>'
        f'<h2 class="sec-title">What It Costs to Buy in {esc(place)}</h2>'
        f'</div>'
        f'<div class="costs"><div class="panel-b"><dl>{dl}</dl></div></div>'
        f'{tax_p}{pay_p}'
        f'</div></section>'
    ), []


def sec_neighborhoods(d):
    nb = d.get("neighborhoods")
    if not nb or not nb.get("items"):
        return "", ["neighborhoods: section data missing"]
    place = d["place_name"]
    sub = ""
    if nb.get("hub_guide_url"):
        text = nb.get("hub_guide_text", f"{place} neighborhood guide")
        sub = (f'<p class="sec-sub">For detailed neighborhood comparisons, '
               f'see our <a href="{esc(nb["hub_guide_url"])}">'
               f'{esc(text)}</a>.</p>')
    hoods = ""
    for item in nb["items"]:
        link = ""
        if item.get("guide_url"):
            link = (f'\n<a class="hood-link" '
                    f'href="{esc(item["guide_url"])}">'
                    f'{esc(item["name"])} guide &rarr;</a>')
        hoods += (f'<div class="hood"><h4>{esc(item["name"])}</h4>'
                  f'<p>{esc(item["description"])}</p>{link}\n</div>\n')
    return (
        f'<section class="blk"><div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Where to Look</div>'
        f'<h2 class="sec-title">{esc(place)} Neighborhoods</h2>{sub}</div>'
        f'<div class="hoods">\n{hoods}</div></div></section>'
    ), []


def sec_schools(d):
    sch = d.get("schools")
    if not sch:
        return "", ["schools: section data missing"]
    place = d["place_name"]

    tabs_spec = [
        ("elem", "Elementary", sch.get("elementary", []),
         [("School", "name"), ("Grades", "grades"),
          ("Enrollment", "enrollment"), ("District", "district")]),
        ("mid", "Middle", sch.get("middle", []),
         [("School", "name"), ("Grades", "grades"),
          ("District", "district")]),
        ("high", "High", sch.get("high", []),
         [("School", "name"), ("Grades", "grades"),
          ("District", "district")]),
        ("dist", "District", sch.get("district_summary", []),
         [("District", "name"), ("Schools", "schools"),
          ("Enrollment", "enrollment")]),
    ]

    btns = ""
    panels = ""
    for i, (key, label, items, cols) in enumerate(tabs_spec):
        sel = "true" if i == 0 else "false"
        on = " on" if i == 0 else ""
        btns += (f'<button class="tab" role="tab" aria-selected="{sel}" '
                 f'data-tab="{key}">{label}</button>')
        if items:
            hdrs = "".join(f"<th>{h}</th>" for h, _ in cols)
            rows = "".join(
                "<tr>" + "".join(
                    f"<td>{esc(s.get(k, ''))}</td>" for _, k in cols
                ) + "</tr>" for s in items)
            tbl = (f"<table><thead><tr>{hdrs}</tr></thead>"
                   f"<tbody>{rows}</tbody></table>")
        else:
            tbl = ""
        panels += f'<div class="tab-panel{on}" data-panel="{key}">{tbl}</div>'

    gs_slug = place.lower().replace(" ", "-")
    src = sch.get("source_note_html",
        f'School data: <a href="https://www.greatschools.org/texas/'
        f'{gs_slug}/" target="_blank" rel="noopener">GreatSchools.org</a> '
        f'&amp; <a href="https://nces.ed.gov/ccd/schoolsearch/" '
        f'target="_blank" rel="noopener">NCES Common Core of Data</a>. '
        f'Verify enrollment eligibility directly with the district.')
    return (
        f'<section class="blk" style="background:var(--bg-soft);">'
        f'<div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Education</div>'
        f'<h2 class="sec-title">{esc(place)} Schools</h2></div>'
        f'<div class="tabs" role="tablist">{btns}</div>'
        f'<div class="tbl-wrap" style="border-top-left-radius:0;'
        f'border-top-right-radius:0;border-top:0;">{panels}</div>'
        f'<p class="src-note">{src}</p>'
        f'</div></section>'
    ), []


def sec_linkgrid(d):
    gaps = []
    if "idx" not in d:
        return "", ["linkgrid: no IDX scope"]
    place = d["place_name"]
    lg = d.get("link_grid", {})

    def yu(extra=""):
        return ylopo_scope(d, extra)

    # 5 fixed columns derived from IDX scope
    c1 = ('<div class="lg-col"><h5>Popular Searches</h5><ul>'
          f'<li><a href="{yu()}" target="_blank" rel="noopener">'
          f'Newest Listings</a></li>'
          f'<li><a href="{yu("s[reduced]=t")}" target="_blank" '
          f'rel="noopener">Price Reduced</a></li>'
          f'<li><a href="{yu("s[status]=sold")}" target="_blank" '
          f'rel="noopener">Recently Sold</a></li>'
          f'<li><a href="{yu("s[openHouse]=t")}" target="_blank" '
          f'rel="noopener">Open Houses</a></li>'
          f'<li><a href="{yu("s[amenities][0]=sa_has_virtual_tour")}" '
          f'target="_blank" rel="noopener">Virtual Tours</a></li>'
          '</ul></div>')

    c2 = ('<div class="lg-col"><h5>Property Types</h5><ul>'
          f'<li><a href="{yu("s[propertyTypes][0]=house")}" target="_blank" '
          f'rel="noopener">Single Family</a></li>'
          f'<li><a href="{yu("s[propertyTypes][0]=condo")}" target="_blank" '
          f'rel="noopener">Condos</a></li>'
          f'<li><a href="{yu("s[propertyTypes][0]=townhouse")}" '
          f'target="_blank" rel="noopener">Townhouses</a></li>'
          f'<li><a href="{yu("s[propertyTypes][0]=land")}" target="_blank" '
          f'rel="noopener">Land &amp; Lots</a></li>'
          f'<li><a href="{yu("s[amenities][0]=sa_is_new_construction")}" '
          f'target="_blank" rel="noopener">New Construction</a></li>'
          '</ul></div>')

    c3 = ('<div class="lg-col"><h5>Homes by Price</h5><ul>'
          f'<li><a href="{yu("s[maxPrice]=200000")}" target="_blank" '
          f'rel="noopener">Under $200K</a></li>'
          f'<li><a href="{yu("s[maxPrice]=300000")}" target="_blank" '
          f'rel="noopener">Under $300K</a></li>'
          f'<li><a href="{yu("s[maxPrice]=400000")}" target="_blank" '
          f'rel="noopener">Under $400K</a></li>'
          f'<li><a href="{yu("s[maxPrice]=500000")}" target="_blank" '
          f'rel="noopener">Under $500K</a></li>'
          f'<li><a href="{yu("s[minPrice]=500000&s[maxPrice]=750000")}" '
          f'target="_blank" rel="noopener">$500K&ndash;$750K</a></li>'
          f'<li><a href="{yu("s[minPrice]=750000")}" target="_blank" '
          f'rel="noopener">$750K+</a></li>'
          '</ul></div>')

    c4 = ('<div class="lg-col"><h5>Homes by Bedrooms</h5><ul>'
          f'<li><a href="{yu("s[beds]=2")}" target="_blank" '
          f'rel="noopener">2+ Bedrooms</a></li>'
          f'<li><a href="{yu("s[beds]=3")}" target="_blank" '
          f'rel="noopener">3+ Bedrooms</a></li>'
          f'<li><a href="{yu("s[beds]=4")}" target="_blank" '
          f'rel="noopener">4+ Bedrooms</a></li>'
          f'<li><a href="{yu("s[beds]=5")}" target="_blank" '
          f'rel="noopener">5+ Bedrooms</a></li>'
          '</ul></div>')

    c5 = ('<div class="lg-col"><h5>Amenities</h5><ul>'
          f'<li><a href="{yu("s[amenities][0]=sa_pool")}" target="_blank" '
          f'rel="noopener">Pool Homes</a></li>'
          f'<li><a href="{yu("s[amenities][0]=sa_garage")}" target="_blank" '
          f'rel="noopener">With Garage</a></li>'
          '</ul></div>')

    # 3 data-driven columns
    cities = lg.get("nearby_cities", [])
    c6 = ""
    if cities:
        links = "".join(
            f'<li><a href="{ylopo_city(c["name"], c.get("state", "TX"))}" '
            f'target="_blank" rel="noopener">{esc(c["name"])} Homes</a></li>'
            for c in cities)
        c6 = f'<div class="lg-col"><h5>Nearby Cities</h5><ul>{links}</ul></div>'
    else:
        gaps.append("linkgrid: no nearby cities data")

    counties = lg.get("counties", [])
    c7 = ""
    if counties:
        links = "".join(
            f'<li><a href="{ylopo_county(c["name"], c.get("state", "TX"))}'
            f'" target="_blank" rel="noopener">'
            f'{esc(c["name"])} County</a></li>'
            for c in counties)
        c7 = f'<div class="lg-col"><h5>Counties</h5><ul>{links}</ul></div>'
    else:
        gaps.append("linkgrid: no counties data")

    zips = lg.get("zips", [])
    c8 = ""
    if zips:
        links = "".join(
            f'<li><a href="{ylopo_zip(z)}" target="_blank" '
            f'rel="noopener">{esc(z)}</a></li>'
            for z in zips)
        c8 = f'<div class="lg-col"><h5>ZIP Codes</h5><ul>{links}</ul></div>'
    else:
        gaps.append("linkgrid: no ZIP codes data")

    return (
        f'<section class="blk linkgrid-band"><div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Browse Listings</div>'
        f'<h2 class="sec-title">Search {esc(place)} Homes</h2></div>'
        f'<div class="linkgrid">{c1}{c2}{c3}{c4}{c5}{c6}{c7}{c8}</div>'
        f'</div></section>'
    ), gaps


def sec_faq(d):
    faqs = d.get("faq", [])
    if not faqs:
        return "", ["faq: no FAQ items"]
    place = d["place_name"]
    ref = d.get("intro", {}).get(
        "cta_ref", place.lower().replace(" ", "-") + "-listing")
    cta = d.get("intro", {}).get(
        "cta_label", f"Talk to an LRG Agent About {esc(place)}")

    details = ""
    for i, q in enumerate(faqs):
        op = " open" if i == 0 else ""
        details += (f'<details{op}><summary>{esc(q["question"])}</summary>'
                    f'<div class="ans">{esc(q["answer"])}</div></details>')

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q["question"],
             "acceptedAnswer": {"@type": "Answer", "text": q["answer"]}}
            for q in faqs
        ],
    }
    jsonld = json.dumps(schema)

    return (
        f'<section class="blk"><div class="wrap">'
        f'<div class="sec-head"><div class="sec-kicker">Common Questions'
        f'</div>'
        f'<h2 class="sec-title">{esc(place)} Buyer FAQs</h2></div>'
        f'<div class="faq">{details}</div>'
        f'<div class="end-cta">'
        f'<a href="{CONNECT_URL}?ref={esc(ref)}-bottom" class="ls-cta">'
        f'{cta} <span class="arr">&rarr;</span></a></div>'
        f'</div></section>'
        f'<script type="application/ld+json">{jsonld}</script>'
    ), []


# ── Assembly ──────────────────────────────────────────────────────


SECTION_BUILDERS = [
    sec_intro, sec_iframe, sec_market, sec_demographics,
    sec_commute, sec_briefing, sec_costs, sec_neighborhoods,
    sec_schools, sec_linkgrid, sec_faq,
]


def assemble(data):
    """Run all section builders. Returns (html, all_gaps)."""
    all_gaps = []
    parts = []
    for fn in SECTION_BUILDERS:
        html_str, gaps = fn(data)
        all_gaps.extend(gaps)
        if html_str:
            parts.append(html_str)
    return "\n".join(parts), all_gaps


# ── Deployment ────────────────────────────────────────────────────


def _b64(text):
    """Base64-encode a string for safe PHP embedding."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _ssh(install, ssh_key, cmd_str, stdin_data=None, timeout=60):
    """Run a command on the remote install via SSH. Returns stdout."""
    cfg = SSH_CONFIGS[install]
    key = ssh_key or cfg["key"]
    host = cfg["host"]
    full_cmd = f"ssh -i {key} {host} {cmd_str}"
    result = subprocess.run(
        full_cmd, input=stdin_data, shell=True,
        capture_output=True, timeout=timeout)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        out = result.stdout.decode("utf-8", errors="replace").strip()
        print(f"SSH ERROR (rc={result.returncode}): {err} {out}",
              file=sys.stderr)
        sys.exit(1)
    return result.stdout.decode("utf-8").strip()


def deploy(html_content, data, args):
    """Create listing_page post on target install.

    Uses a two-step approach to avoid WPE PrivateTmp and large-PHP issues:
    1. Upload HTML content to /nas/content/live/{install}/backups/
    2. Run a small PHP script that reads the file and creates the post.
    """
    place = data["place_name"]
    slug = data.get("slug",
                    f'homes-for-sale-{place.lower().replace(" ", "-")}')
    title = f"Homes for Sale in {place}, TX"
    metadesc = data.get(
        "metadesc",
        f"Search homes for sale in {place}, TX. Browse neighborhoods, "
        f"market data, and listings. Updated daily.")
    yoast_title = f"{title} | LRG Realty"
    noindex_val = "1" if args.noindex else "0"
    author_id = args.author

    install = args.install
    if install not in SSH_CONFIGS:
        print(f"ERROR: Unknown install '{install}'. "
              f"Known: {', '.join(SSH_CONFIGS.keys())}", file=sys.stderr)
        sys.exit(1)

    ssh_key = args.ssh_key
    content_path = f"/nas/content/live/{install}/backups/listing-content-{slug}.html"

    # Step 1: Upload HTML content to persistent path
    _ssh(install, ssh_key,
         f"'mkdir -p /nas/content/live/{install}/backups && "
         f"cat > {content_path}'",
         stdin_data=html_content.encode("utf-8"))
    print(f"  Content uploaded: {content_path} ({len(html_content)} bytes)",
          file=sys.stderr)

    # Step 2: Small PHP script reads the file and creates the post.
    # Base64-encode only the short metadata strings (safe for inline).
    php = f"""<?php
error_reporting(E_ALL);
$slug        = base64_decode('{_b64(slug)}');
$title       = base64_decode('{_b64(title)}');
$metadesc    = base64_decode('{_b64(metadesc)}');
$yoast_title = base64_decode('{_b64(yoast_title)}');
$content     = file_get_contents('{content_path}');
$noindex     = {noindex_val};
$author_id   = {author_id};

if ($content === false || strlen($content) < 50) {{
    echo "ERROR:content_read_failed\\n";
    return;
}}

$existing = get_posts(array(
    'post_type'   => 'listing_page',
    'name'        => $slug,
    'numberposts' => 1,
    'post_status' => 'any',
));
if (!empty($existing)) {{
    echo "EXISTING:" . $existing[0]->ID . "\\n";
    return;
}}

$post_id = wp_insert_post(array(
    'post_type'      => 'listing_page',
    'post_status'    => 'draft',
    'post_name'      => $slug,
    'post_title'     => $title,
    'post_content'   => $content,
    'post_author'    => $author_id,
    'comment_status' => 'closed',
    'post_excerpt'   => $metadesc,
    'post_date'      => current_time('mysql'),
    'post_date_gmt'  => current_time('mysql', true),
));

if (is_wp_error($post_id)) {{
    echo "ERROR:" . $post_id->get_error_message() . "\\n";
    return;
}}

update_post_meta($post_id, '_yoast_wpseo_title', $yoast_title);
update_post_meta($post_id, '_yoast_wpseo_metadesc', $metadesc);
if ($noindex) {{
    update_post_meta($post_id, '_yoast_wpseo_meta-robots-noindex', '1');
}}

echo "CREATED:" . $post_id . "\\n";
"""

    stdout = _ssh(install, ssh_key,
                  "'cat > /tmp/deploy-listing.php && "
                  "wp eval-file /tmp/deploy-listing.php'",
                  stdin_data=php.encode("utf-8"))

    if stdout.startswith("EXISTING:"):
        pid = stdout.split(":")[1]
        print(f"SKIP: Post already exists slug='{slug}' (ID {pid})")
        return int(pid)
    if stdout.startswith("CREATED:"):
        pid = stdout.split(":")[1]
        print(f"CREATED: listing_page {pid} slug='{slug}' on {install}")
        return int(pid)
    if stdout.startswith("ERROR:"):
        print(f"WP ERROR: {stdout}", file=sys.stderr)
        sys.exit(1)

    print(f"UNEXPECTED: {stdout}", file=sys.stderr)
    sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(
        description="Generate LRG listing page from per-place data file.")
    p.add_argument("--data-file", required=True,
                   help="Path to per-place JSON data file")
    p.add_argument("--install",
                   help="WP Engine install name (required unless --dry-run)")
    p.add_argument("--ssh-key", help="SSH key path override")
    p.add_argument("--dry-run", action="store_true",
                   help="Output HTML to stdout, do not deploy")
    p.add_argument("--noindex", action="store_true",
                   help="Set Yoast noindex=1 on the post")
    p.add_argument("--author", type=int, default=1,
                   help="WP user ID for post_author (default: 1 = Levi)")
    args = p.parse_args()

    if not args.dry_run and not args.install:
        p.error("--install is required unless --dry-run is set")

    with open(args.data_file) as f:
        data = json.load(f)

    required = ["place_name", "idx"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"ERROR: Data file missing required fields: "
              f"{', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    html_content, gaps = assemble(data)

    if gaps:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"GAPS ({len(gaps)}):", file=sys.stderr)
        for g in gaps:
            print(f"  - {g}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)

    if args.dry_run:
        print(html_content)
        print(f"\n<!-- {len(gaps)} gap(s) logged to stderr -->",
              file=sys.stderr)
    else:
        post_id = deploy(html_content, data, args)
        slug = data.get(
            "slug",
            f'homes-for-sale-{data["place_name"].lower().replace(" ", "-")}')
        print(f"\nSlug: {slug}")
        print(f"Gaps: {len(gaps)}")
        if gaps:
            for g in gaps:
                print(f"  - {g}")


if __name__ == "__main__":
    main()
