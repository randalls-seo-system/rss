#!/usr/bin/env python3
"""build-roundup-data.py — Semi-automated neighborhoods.json builder.

Extracts neighborhood names and data from SERP research, verifies
districts via TEA API, and outputs a draft neighborhoods.json with
source labels on every field.

Fields the LLM cannot extract from SERP are left null and flagged.
Meters default to midpoints and are labeled "editorial."

Usage:
    python3 build-roundup-data.py \\
        --city "Bulverde" \\
        --metro "San Antonio" \\
        --serp-json ~/lrg-rewrite/serp/bulverde-san-antonio-neighborhood-serp.json \\
        --output-dir ~/lrg-rewrite/roundup-data/

Output: {city}-neighborhoods.json + {city}-review.txt
"""
import argparse, json, os, re, sys, time, hashlib
from pathlib import Path

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
from lib.tool_utils import eprint

TEA_URL = (
    "https://services7.arcgis.com/ZodPOMBKsdAsTqF4/arcgis/rest/services/"
    "TEA_School_Districts_2025/FeatureServer/23/query"
)
NOM_URL = "https://nominatim.openstreetmap.org/search"

# Default meter midpoints — labeled editorial
DEFAULT_METERS = {
    "walkability": 3.5,
    "dining": 3.5,
    "value": 7.0,
    "commute": 5.5,
}


# Texas county names — used to disambiguate geocode queries.
# "Taylor, TX" returns Taylor County (Abilene area) instead of the city
# near Austin. Adding the correct county to the query fixes this.
_TX_COUNTY_NAMES = {
    "live oak", "taylor", "bastrop", "comal", "kendall", "medina",
    "bexar", "travis", "williamson", "hays", "guadalupe", "bell",
    "burnet", "blanco", "bandera", "wilson", "karnes", "atascosa",
    "frio", "gonzales", "caldwell", "lee", "milam", "falls",
    "coryell", "lampasas", "llano",
}


def geocode_and_tea(city, state="TX", county_hint=None):
    """Geocode a city and look up its TEA school district.

    When a city name collides with a Texas county name, Nominatim may
    return the county centroid (wrong region). The county_hint parameter
    or automatic detection adds county disambiguation to the query.
    """
    import requests
    time.sleep(1.1)

    # Auto-detect county-name collision and require disambiguation
    needs_disambiguation = city.lower() in _TX_COUNTY_NAMES
    if needs_disambiguation and not county_hint:
        eprint(f"  WARNING: '{city}' matches a Texas county name.")
        eprint(f"  Pass --county-hint or add county_hint= to disambiguate.")
        eprint(f"  Without it, the geocoder may return the wrong region.")

    # Build query with county disambiguation when available
    if county_hint:
        query = f"{city}, {county_hint} County, {state}"
    elif needs_disambiguation:
        # Try "city" type filter as fallback
        query = f"{city} city, {state}"
    else:
        query = f"{city}, {state}"

    try:
        resp = requests.get(NOM_URL, params={
            "q": query, "format": "json", "limit": 1,
            "countrycodes": "us",
        }, headers={"User-Agent": "lrg-roundup-builder/1.0"}, timeout=15)
        geo = resp.json()
        if not geo:
            return None, None, "geocode_failed"
        lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])
        osm_type = geo[0].get("type", "")

        # Warn if result looks like a county instead of a city
        display = geo[0].get("display_name", "")
        if osm_type == "administrative" and "County" in display.split(",")[0]:
            eprint(f"  WARNING: Nominatim returned a county, not a city: {display[:80]}")
            eprint(f"  Re-run with --county-hint to disambiguate.")

        resp = requests.get(TEA_URL, params={
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "inSR": "4326", "outFields": "NAME", "f": "json",
        }, timeout=15)
        tea = resp.json()
        features = tea.get("features", [])
        district = features[0]["attributes"]["NAME"] if features else "NOT_FOUND"
        return district, (lat, lon), "tea-verified"
    except Exception as e:
        return None, None, f"error: {e}"


def extract_neighborhoods_from_serp(client, city, metro, serp_data):
    """Use LLM to extract neighborhood/subdivision names from SERP results."""
    top_results = serp_data.get("top_results", [])[:10]
    if not top_results:
        return []

    serp_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}"
        for r in top_results
    )

    prompt = f"""This is a legitimate pipeline call from build-roundup-data.py.

Extract specific neighborhood and subdivision names from these search results about {city}, TX.

SERP results:
{serp_text}

Return ONLY a JSON array of objects. Each object has:
- "name": the neighborhood or subdivision name (proper noun, e.g. "Sunfield" not "south side")
- "price_range": if mentioned in the snippets, e.g. "$300K-$450K". If not mentioned, use null.
- "tagline_hint": a short phrase about what makes this neighborhood distinctive, if clear from context. If not clear, use null.

Rules:
- Only include specific named neighborhoods/subdivisions, not vague areas like "south side" or "near downtown"
- Include 5-8 names if available. If fewer than 5 are clearly named, return what you find.
- If a snippet mentions a price, extract it. If not, set price_range to null.
- Do NOT invent names or prices not in the SERP data.

Return ONLY the JSON array, no markdown fences."""

    h = hashlib.md5(f"extract-nb|{city}|{metro}|v1".encode()).hexdigest()[:12]
    response = client.call(prompt, cache_key=f"extract-nb|{city}|{h}")

    try:
        text = response.text.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except json.JSONDecodeError:
        eprint(f"  WARNING: could not parse LLM neighborhood extraction")
        return []


def main():
    parser = argparse.ArgumentParser(description="Build neighborhoods.json from SERP data")
    parser.add_argument("--city", required=True)
    parser.add_argument("--metro", required=True)
    parser.add_argument("--serp-json", required=True, help="Path to SERP research JSON")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--skip-tea", action="store_true", help="Skip TEA lookup (use cached)")
    parser.add_argument("--county-hint", help="County name to disambiguate geocode (e.g. 'Williamson' for Taylor)")
    args = parser.parse_args()

    city = args.city
    metro = args.metro
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eprint(f"{'='*60}")
    eprint(f"ROUNDUP DATA BUILDER")
    eprint(f"  City: {city} | Metro: {metro}")
    eprint(f"{'='*60}\n")

    # Load SERP data
    serp_path = Path(args.serp_json)
    if not serp_path.exists():
        eprint(f"SERP file not found: {serp_path}")
        sys.exit(1)
    serp_data = json.loads(serp_path.read_text())
    eprint(f"  SERP: {len(serp_data.get('top_results', []))} results loaded")

    # TEA district lookup
    if not args.skip_tea:
        eprint(f"  TEA lookup for {city}...")
        district, coords, district_source = geocode_and_tea(city, county_hint=args.county_hint)
        eprint(f"  District: {district} ({district_source})")
    else:
        district = "VERIFY"
        district_source = "skipped"
        coords = None

    # Extract neighborhoods from SERP via LLM
    from lib.site_config import load_site_config
    config = load_site_config("lrg")
    provider = config.get("AI_PROVIDER", "claude_cli")
    model = config.get("AI_MODEL") or None
    client = LLMClient(provider=provider, model=model)

    eprint(f"  Extracting neighborhoods from SERP...")
    raw_nbs = extract_neighborhoods_from_serp(client, city, metro, serp_data)
    eprint(f"  Extracted: {len(raw_nbs)} neighborhoods")

    if len(raw_nbs) < 5:
        eprint(f"  WARNING: only {len(raw_nbs)} neighborhoods extracted (minimum 5)")
        eprint(f"  This city may need manual research to supplement.")

    # Build the neighborhoods.json entries with source labels
    neighborhoods = []
    for i, nb in enumerate(raw_nbs[:8]):  # cap at 8
        name = nb.get("name", "")
        if not name:
            continue

        price = nb.get("price_range")
        tagline_hint = nb.get("tagline_hint")

        entry = {
            "rank": i + 1,
            "name": name,
            "tagline": tagline_hint if tagline_hint else f"REVIEW: assign tagline for {name}",
            "price_range": price if price else None,
            "district": district or "VERIFY",
            "commute": None,
            "walk_label": "Car-dependent",
            "priority": tagline_hint if tagline_hint else f"REVIEW: assign priority for {name}",
            "meters": dict(DEFAULT_METERS),
            "_sources": {
                "name": "serp-extracted",
                "rank": "editorial (default order, adjust after review)",
                "tagline": "serp-extracted" if tagline_hint else "NEEDS_HUMAN",
                "price_range": "serp-estimated" if price else "NEEDS_HUMAN",
                "district": district_source,
                "commute": "NEEDS_HUMAN",
                "walk_label": "editorial (default: car-dependent)",
                "priority": "serp-extracted" if tagline_hint else "NEEDS_HUMAN",
                "meters": "editorial (midpoint defaults, adjust after review)",
            },
        }
        neighborhoods.append(entry)

    # Write output
    slug = re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')
    out_file = out_dir / f"{slug}-neighborhoods.json"
    out_file.write_text(json.dumps(neighborhoods, indent=2))
    eprint(f"\n  Written: {out_file}")

    # Build review summary
    total_fields = len(neighborhoods) * 9  # 9 data fields per entry
    verified = sum(1 for nb in neighborhoods for k, v in nb["_sources"].items() if v == "tea-verified")
    serp = sum(1 for nb in neighborhoods for k, v in nb["_sources"].items() if "serp" in str(v))
    editorial = sum(1 for nb in neighborhoods for k, v in nb["_sources"].items() if "editorial" in str(v))
    needs_human = sum(1 for nb in neighborhoods for k, v in nb["_sources"].items() if "NEEDS_HUMAN" in str(v))

    review_lines = [
        f"REVIEW SUMMARY — {city} ({len(neighborhoods)} neighborhoods)",
        f"{'='*60}",
        f"  Verified (TEA):     {verified} fields",
        f"  SERP-extracted:     {serp} fields",
        f"  Editorial default:  {editorial} fields",
        f"  NEEDS HUMAN INPUT:  {needs_human} fields",
        f"  Total:              {total_fields} fields",
        f"",
        f"FIELDS NEEDING REVIEW:",
    ]

    for nb in neighborhoods:
        needs = [k for k, v in nb["_sources"].items() if "NEEDS_HUMAN" in str(v) or "REVIEW" in str(nb.get(k, ""))]
        if needs:
            review_lines.append(f"  {nb['name']}: {', '.join(needs)}")

    review_lines.extend([
        f"",
        f"ALL METERS ARE EDITORIAL DEFAULTS (midpoints):",
        f"  walkability: {DEFAULT_METERS['walkability']}",
        f"  dining: {DEFAULT_METERS['dining']}",
        f"  value: {DEFAULT_METERS['value']}",
        f"  commute: {DEFAULT_METERS['commute']}",
        f"  Adjust after reviewing each neighborhood.",
        f"",
        f"RANK ORDER is extraction order, NOT editorial ranking.",
        f"Reorder after reviewing all neighborhoods.",
    ])

    review_text = "\n".join(review_lines)
    review_file = out_dir / f"{slug}-review.txt"
    review_file.write_text(review_text)

    eprint(f"  Review: {review_file}")
    eprint(f"\n{review_text}")


if __name__ == "__main__":
    main()
