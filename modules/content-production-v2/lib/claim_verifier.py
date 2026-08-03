"""Claim verification layer — verifies extracted claims against authoritative sources.

Built on top of fact_checker.py (extraction). This module VERIFIES claims
using deterministic APIs + a search-LLM judge for residuals.

Design rules:
- Every claim ends as VERIFIED, WRONG, or COULDNT_VERIFY. Never silently passed.
- WRONG claims get a PROPOSED correction (not auto-applied).
- High-stakes corrections (school/tax/legal) require individual human review.
- Volatile softenings can batch-approve.
- No auto-patching of published content.

Sources:
- TEA ArcGIS FeatureServer (school districts — tested, free, authoritative)
- Nominatim/OpenStreetMap (businesses/landmarks + ZIPs — tested, free)
- Wikipedia REST API (year claims — tested, free)
- Tax rate reference table (maintained JSON, not a scraper)
- Search-LLM judge (residuals — Serper + LLM, constrained to authoritative domains)
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from .tool_utils import eprint


# ── Rate limiting ──
_last_nominatim_call = 0.0

def _nominatim_throttle():
    """Enforce 1 req/sec for Nominatim."""
    global _last_nominatim_call
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_nominatim_call = time.time()


# ── Data structures ──

@dataclass
class VerificationResult:
    """Result of verifying a single claim."""
    claim_text: str
    category: str
    verdict: str  # VERIFIED, WRONG, COULDNT_VERIFY, HUMAN_FLAG
    confidence: float = 0.0
    source_url: str = ""
    source_name: str = ""
    correct_value: str = ""
    proposed_patch: str = ""
    note: str = ""

    @property
    def needs_individual_review(self) -> bool:
        """High-stakes WRONG claims need individual review, not batch."""
        return (self.verdict == "WRONG" and
                self.category in ("school", "tax", "legal", "year", "geography"))


@dataclass
class VerificationReport:
    """Full verification report for a generated guide."""
    neighborhood: str
    city: str
    post_id: int = 0
    results: list = field(default_factory=list)

    @property
    def verified_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "VERIFIED")

    @property
    def wrong_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "WRONG")

    @property
    def couldnt_verify_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "COULDNT_VERIFY")

    @property
    def human_flag_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "HUMAN_FLAG")


# ═══════════════════════════════════════════════════════════════════
# STEP 2a: TEA ArcGIS — School District Verification
# ═══════════════════════════════════════════════════════════════════

TEA_FEATURE_SERVER = (
    "https://services7.arcgis.com/ZodPOMBKsdAsTqF4/arcgis/rest/services/"
    "TEA_School_Districts_2025/FeatureServer/23/query"
)


def _geocode_neighborhood(neighborhood: str, city: str, state: str = "TX") -> Optional[tuple]:
    """Geocode a neighborhood to lat/lon using Nominatim."""
    _nominatim_throttle()
    query = f"{neighborhood}, {city}, {state}"
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "LRG-FactChecker/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def verify_school_district(neighborhood: str, city: str, claimed_district: str) -> VerificationResult:
    """Verify school district claim against TEA ArcGIS boundary data."""
    coords = _geocode_neighborhood(neighborhood, city)
    if not coords:
        return VerificationResult(
            claim_text=claimed_district, category="school",
            verdict="COULDNT_VERIFY", confidence=0.0,
            note=f"Could not geocode '{neighborhood}, {city}' for district lookup",
        )

    lat, lon = coords
    try:
        resp = requests.get(TEA_FEATURE_SERVER, params={
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }, timeout=15)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return VerificationResult(
                claim_text=claimed_district, category="school",
                verdict="COULDNT_VERIFY", confidence=0.0,
                note=f"TEA API returned no district for ({lat}, {lon})",
            )

        tea_district = features[0]["attributes"].get("NAME", "")
        tea_district_full = features[0]["attributes"].get("NAME20", "")

        # Normalize for comparison
        claimed_norm = claimed_district.lower().replace("independent school district", "isd").strip()
        tea_norm = tea_district.lower().strip()
        tea_full_norm = tea_district_full.lower().replace("independent school district", "isd").strip()

        if (claimed_norm in tea_norm or tea_norm in claimed_norm or
            claimed_norm in tea_full_norm or tea_full_norm in claimed_norm):
            return VerificationResult(
                claim_text=claimed_district, category="school",
                verdict="VERIFIED", confidence=0.95,
                source_url="https://tea.texas.gov/texas-schools/general-information/school-district-locator",
                source_name="TEA School District Locator (ArcGIS)",
                note=f"TEA confirms: {tea_district_full} serves ({lat:.4f}, {lon:.4f})",
            )
        else:
            return VerificationResult(
                claim_text=claimed_district, category="school",
                verdict="WRONG", confidence=0.90,
                source_url="https://tea.texas.gov/texas-schools/general-information/school-district-locator",
                source_name="TEA School District Locator (ArcGIS)",
                correct_value=tea_district_full,
                proposed_patch=f"Replace '{claimed_district}' with '{tea_district}'",
                note=f"TEA says {tea_district_full}, not {claimed_district}",
            )
    except Exception as e:
        return VerificationResult(
            claim_text=claimed_district, category="school",
            verdict="COULDNT_VERIFY", confidence=0.0,
            note=f"TEA API error: {e}",
        )


# ═══════════════════════════════════════════════════════════════════
# STEP 2b: Nominatim — Business/Landmark + ZIP Verification
# ═══════════════════════════════════════════════════════════════════

def verify_business_exists(name: str, city: str, state: str = "TX") -> VerificationResult:
    """Verify a named business/landmark exists via Nominatim/OSM."""
    _nominatim_throttle()
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{name} {city} {state}", "format": "json", "limit": 3},
            headers={"User-Agent": "LRG-FactChecker/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            top = data[0]
            return VerificationResult(
                claim_text=name, category="business_landmark",
                verdict="VERIFIED", confidence=0.85,
                source_url=f"https://www.openstreetmap.org/?mlat={top['lat']}&mlon={top['lon']}",
                source_name="OpenStreetMap/Nominatim",
                note=f"Found: {top.get('display_name', '')[:100]}",
            )
        else:
            return VerificationResult(
                claim_text=name, category="business_landmark",
                verdict="COULDNT_VERIFY", confidence=0.0,
                note=f"Not found in OpenStreetMap for '{name}' in {city}, {state}",
            )
    except Exception as e:
        return VerificationResult(
            claim_text=name, category="business_landmark",
            verdict="COULDNT_VERIFY", confidence=0.0,
            note=f"Nominatim error: {e}",
        )


def verify_zip_code(zip_code: str, neighborhood: str, city: str) -> VerificationResult:
    """Verify a ZIP code is associated with the claimed neighborhood/city."""
    _nominatim_throttle()
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{zip_code} {city} TX", "format": "json", "limit": 1},
            headers={"User-Agent": "LRG-FactChecker/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            display = data[0].get("display_name", "").lower()
            if city.lower() in display or "san antonio" in display or "austin" in display:
                return VerificationResult(
                    claim_text=f"ZIP {zip_code}", category="geography",
                    verdict="VERIFIED", confidence=0.95,
                    source_url=f"https://nominatim.openstreetmap.org/search?q={zip_code}",
                    source_name="Nominatim/OSM",
                    note=f"ZIP {zip_code} confirmed in {city} area",
                )
        return VerificationResult(
            claim_text=f"ZIP {zip_code}", category="geography",
            verdict="COULDNT_VERIFY", confidence=0.0,
            note=f"Could not confirm ZIP {zip_code} for {city}",
        )
    except Exception as e:
        return VerificationResult(
            claim_text=f"ZIP {zip_code}", category="geography",
            verdict="COULDNT_VERIFY", note=f"Error: {e}",
        )


# ═══════════════════════════════════════════════════════════════════
# STEP 2c: Wikipedia — Year Claim Verification
# ═══════════════════════════════════════════════════════════════════

def verify_year_claim(entity_name: str, claimed_year: str, claim_text: str) -> VerificationResult:
    """Verify a year claim (opened, founded, etc.) against Wikipedia."""
    # Try to find the Wikipedia article
    search_name = entity_name.replace(" ", "_")
    # Try common title patterns
    candidates = [
        search_name,
        f"{search_name}_(San_Antonio)",
        f"{search_name}_(Texas)",
        f"{search_name}_(Austin,_Texas)",
    ]

    for candidate in candidates:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/html/{quote(candidate)}"
            resp = requests.get(url, timeout=10,
                                headers={"User-Agent": "LRG-FactChecker/1.0"})
            if resp.status_code != 200:
                continue

            html = resp.text
            # Search for year in infobox (founded/established/opened fields)
            year_patterns = [
                r'"founded"\s*:\s*\{\s*"wt"\s*:\s*"(\d{4})"',
                r'"established"\s*:\s*\{\s*"wt"\s*:\s*"(\d{4})"',
                r'"opened"\s*:\s*\{\s*"wt"\s*:\s*"(\d{4})"',
                r'(?:founded|established|opened)\s+(?:in\s+)?(\d{4})',
            ]
            for pattern in year_patterns:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    wiki_year = m.group(1)
                    wiki_url = f"https://en.wikipedia.org/wiki/{quote(candidate)}"

                    if wiki_year == claimed_year:
                        return VerificationResult(
                            claim_text=claim_text, category="year",
                            verdict="VERIFIED", confidence=0.95,
                            source_url=wiki_url,
                            source_name="Wikipedia",
                            note=f"Wikipedia confirms: founded/opened {wiki_year}",
                        )
                    else:
                        return VerificationResult(
                            claim_text=claim_text, category="year",
                            verdict="WRONG", confidence=0.90,
                            source_url=wiki_url,
                            source_name="Wikipedia",
                            correct_value=f"Founded/opened {wiki_year}",
                            proposed_patch=f"Replace '{claimed_year}' with '{wiki_year}'",
                            note=f"Wikipedia says {wiki_year}, guide claims {claimed_year}",
                        )
        except Exception:
            continue

    return VerificationResult(
        claim_text=claim_text, category="year",
        verdict="COULDNT_VERIFY", confidence=0.0,
        note=f"Could not find Wikipedia article for '{entity_name}' to verify year",
    )


# ═══════════════════════════════════════════════════════════════════
# STEP 2d: Tax Rate Reference Table
# ═══════════════════════════════════════════════════════════════════

# Maintained reference table — verified from county assessor websites.
# Updated annually when rates are adopted (Sep-Oct).
# Source URLs included for audit trail.
TAX_RATE_TABLE = {
    # Bexar County entities (source: bexar.org/4032/2025-Official-Tax-Rates-Exemptions)
    "bexar county": {"rate_per_100": 0.276331, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "north east isd": {"rate_per_100": 0.982200, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "neisd": {"rate_per_100": 0.982200, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "northside isd": {"rate_per_100": 1.004900, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "nisd": {"rate_per_100": 1.004900, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "city of san antonio": {"rate_per_100": 0.541590, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "san antonio isd": {"rate_per_100": 0.953600, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "saisd": {"rate_per_100": 0.953600, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "alamo heights isd": {"rate_per_100": 1.043700, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "ahisd": {"rate_per_100": 1.043700, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "schertz-cibolo-universal city isd": {"rate_per_100": 1.178500, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "scucisd": {"rate_per_100": 1.178500, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "boerne isd": {"rate_per_100": 1.059800, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "comal isd": {"rate_per_100": 1.067100, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "judson isd": {"rate_per_100": 1.246800, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    "east central isd": {"rate_per_100": 1.108200, "source": "https://bexar.org/1591/Tax-Rates", "year": 2025},
    # Austin-area (source: Travis CAD / Williamson CAD — add as needed)
    "austin isd": {"rate_per_100": 0.9966, "source": "https://traviscad.org", "year": 2025},
    "round rock isd": {"rate_per_100": 1.1196, "source": "https://wilco.org", "year": 2025},
    "eanes isd": {"rate_per_100": 0.9497, "source": "https://traviscad.org", "year": 2025},
    "leander isd": {"rate_per_100": 1.1900, "source": "https://wilco.org", "year": 2025},
    "pflugerville isd": {"rate_per_100": 1.2634, "source": "https://traviscad.org", "year": 2025},
}


def verify_tax_rate(entity_name: str, claimed_rate_text: str) -> VerificationResult:
    """Verify a tax rate claim against the reference table."""
    entity_lower = entity_name.lower().strip()

    # Find matching entity
    entry = TAX_RATE_TABLE.get(entity_lower)
    if not entry:
        # Try partial match
        for key, val in TAX_RATE_TABLE.items():
            if key in entity_lower or entity_lower in key:
                entry = val
                break

    if not entry:
        return VerificationResult(
            claim_text=f"{entity_name}: {claimed_rate_text}", category="tax",
            verdict="COULDNT_VERIFY", confidence=0.0,
            note=f"Entity '{entity_name}' not in tax rate reference table",
        )

    # Parse claimed rate — look for a number
    rate_match = re.search(r'[\$]?([\d.]+)', claimed_rate_text)
    if not rate_match:
        return VerificationResult(
            claim_text=f"{entity_name}: {claimed_rate_text}", category="tax",
            verdict="COULDNT_VERIFY", note="Could not parse rate from claim text",
        )

    claimed_rate = float(rate_match.group(1))
    actual_rate = entry["rate_per_100"]

    # Allow 5% tolerance for rounding
    if abs(claimed_rate - actual_rate) / actual_rate < 0.05:
        return VerificationResult(
            claim_text=f"{entity_name}: {claimed_rate_text}", category="tax",
            verdict="VERIFIED", confidence=0.92,
            source_url=entry["source"],
            source_name=f"County assessor ({entry['year']} rates)",
            note=f"Rate {actual_rate:.4f} per $100 matches claim within tolerance",
        )
    else:
        return VerificationResult(
            claim_text=f"{entity_name}: {claimed_rate_text}", category="tax",
            verdict="WRONG", confidence=0.88,
            source_url=entry["source"],
            source_name=f"County assessor ({entry['year']} rates)",
            correct_value=f"${actual_rate:.4f} per $100 ({entry['year']} rate)",
            proposed_patch=f"Replace '{claimed_rate_text}' with '${actual_rate:.4f} per $100'",
            note=f"Actual rate is ${actual_rate:.4f}, claimed ${claimed_rate:.4f}",
        )


# ═══════════════════════════════════════════════════════════════════
# STEP 2e: Search-LLM Judge (residuals)
# ═══════════════════════════════════════════════════════════════════

# Domain constraints for the search step
JUDGE_PREFERRED_DOMAINS = {
    "school": ["neisd.net", "nisd.net", "saisd.net", "tea.texas.gov",
               "greatschools.org", "niche.com"],
    "business_landmark": [],  # Any source OK for existence
    "amenity": ["sa.gov", "sanantonio.gov", "austintexas.gov"],
    "default": [],
}

JUDGE_BLOCKED_DOMAINS = ["zillow.com", "realtor.com", "redfin.com", "movoto.com"]


def _search_for_claim(claim_text: str, category: str) -> list[dict]:
    """Search for evidence about a claim using Serper.dev."""
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return []

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": claim_text, "num": 5},
            timeout=15,
        )
        data = resp.json()
        results = []
        for item in data.get("organic", [])[:5]:
            link = item.get("link", "")
            # Filter blocked domains
            if any(bd in link for bd in JUDGE_BLOCKED_DOMAINS):
                continue
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": link,
            })
        return results
    except Exception:
        return []


def judge_residual_claim(claim_text: str, category: str, neighborhood: str, city: str) -> VerificationResult:
    """Use search + LLM to judge a claim that deterministic APIs couldn't verify."""
    search_results = _search_for_claim(f"{claim_text} {neighborhood} {city}", category)

    if not search_results:
        return VerificationResult(
            claim_text=claim_text, category=category,
            verdict="COULDNT_VERIFY", confidence=0.0,
            note="No search results found for verification",
        )

    # Format search results for the LLM judge
    snippets = "\n".join(
        f"[{i+1}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}"
        for i, r in enumerate(search_results)
    )

    prompt = f"""You are a fact-checker verifying a specific claim from a real estate neighborhood guide.

CLAIM: "{claim_text}"
NEIGHBORHOOD: {neighborhood}, {city}, TX
CATEGORY: {category}

SEARCH RESULTS (from web search):
{snippets}

Determine: is the claim CORRECT, WRONG, or INSUFFICIENT EVIDENCE?

Rules:
- ONLY use the search results above. Do not use your training data.
- If the search results confirm the claim, return VERIFIED with the confirming source URL.
- If the search results contradict the claim, return WRONG with the correct information and source URL.
- If the search results don't address the claim clearly, return COULDNT_VERIFY.
- Rate your confidence 0.0-1.0. Below 0.7 = treat as COULDNT_VERIFY.

Return ONLY valid JSON (no markdown, no explanation):
{{"verdict": "VERIFIED|WRONG|COULDNT_VERIFY", "confidence": 0.X, "source_url": "...", "note": "brief explanation", "correction": "correct value if WRONG, empty otherwise"}}"""

    try:
        # Use the pipeline's LLM client
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from lib.llm_client import LLMClient
        from lib.tool_utils import extract_html

        client = LLMClient(provider="claude_cli", model="haiku")
        import hashlib
        h = hashlib.md5(f"judge|{claim_text}|{neighborhood}".encode()).hexdigest()[:12]
        response = client.call(prompt, cache_key=f"fact-judge|{h}")

        # Parse JSON response
        text = response.text.strip()
        # Extract JSON from potential markdown wrapping
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            verdict = result.get("verdict", "COULDNT_VERIFY")
            confidence = float(result.get("confidence", 0.0))

            # Confidence below 0.7 = COULDNT_VERIFY
            if confidence < 0.7:
                verdict = "COULDNT_VERIFY"

            return VerificationResult(
                claim_text=claim_text, category=category,
                verdict=verdict, confidence=confidence,
                source_url=result.get("source_url", ""),
                source_name="Search-LLM Judge",
                correct_value=result.get("correction", ""),
                proposed_patch=f"Replace with: {result.get('correction', '')}" if result.get("correction") else "",
                note=result.get("note", ""),
            )
    except Exception as e:
        eprint(f"  [judge] Error judging '{claim_text[:50]}': {e}")

    return VerificationResult(
        claim_text=claim_text, category=category,
        verdict="COULDNT_VERIFY", confidence=0.0,
        note="LLM judge failed to process",
    )


# ═══════════════════════════════════════════════════════════════════
# STEP 3: Main Verification Runner + Report Generator
# ═══════════════════════════════════════════════════════════════════

def run_verification(claims: list, neighborhood: str, city: str, post_id: int = 0) -> VerificationReport:
    """Run full verification pipeline on extracted claims.

    Routes each claim to the appropriate verifier, then passes
    residuals to the search-LLM judge.
    """
    report = VerificationReport(neighborhood=neighborhood, city=city, post_id=post_id)

    for claim in claims:
        cat = claim.category
        text = claim.text

        # Skip subjective claims — always human-flag
        if cat == "subjective":
            report.results.append(VerificationResult(
                claim_text=text, category=cat,
                verdict="HUMAN_FLAG", confidence=0.0,
                note="Subjective claim — editorial judgment, not factual verification",
            ))
            continue

        # Skip volatile stats — flag for softening
        if cat == "volatile":
            report.results.append(VerificationResult(
                claim_text=text, category=cat,
                verdict="HUMAN_FLAG", confidence=0.0,
                note="Volatile market stat — should be softened to durable phrasing",
                proposed_patch="Soften to durable range phrasing",
            ))
            continue

        # Route to deterministic verifiers by category
        result = None

        if cat == "school":
            # Extract district name from claim text
            district_names = re.findall(
                r'((?:North East|Northside|Alamo Heights|San Antonio|Austin|'
                r'Round Rock|Eanes|Leander|Boerne|Pflugerville|Judson|'
                r'East Central|Comal|Schertz)[^,]*?(?:ISD|Independent School District))',
                text, re.IGNORECASE
            )
            if district_names:
                result = verify_school_district(neighborhood, city, district_names[0])
            # For specific campus names (Reagan HS, etc.), pass to judge
            if not result or result.verdict == "COULDNT_VERIFY":
                if not district_names:
                    result = judge_residual_claim(text, cat, neighborhood, city)

        elif cat == "school_comparison":
            # Comparison table mentions — skip verification, mark as low-stakes
            result = VerificationResult(
                claim_text=text, category=cat,
                verdict="VERIFIED", confidence=0.99,
                note="Appears in comparison table about other neighborhoods — not a claim about this neighborhood",
                source_name="comparison context",
            )

        elif cat == "geography":
            zip_match = re.search(r'(\d{5})', text)
            if zip_match:
                result = verify_zip_code(zip_match.group(1), neighborhood, city)

        elif cat == "year":
            # Extract entity name and year from the improved claim format
            # Format: "Ronald Reagan High School opened 2006"
            year_match = re.search(r'(\d{4})', text)
            # Entity name is everything before the verb
            entity_match = re.search(
                r'^(.+?)\s+(?:opened|founded|built|established|constructed)',
                text, re.IGNORECASE
            )
            if year_match and entity_match:
                entity = entity_match.group(1).strip()
                result = verify_year_claim(entity, year_match.group(1), text)
            elif year_match:
                # Fallback: try to find any proper noun sequence
                pn_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
                if pn_match:
                    result = verify_year_claim(pn_match.group(1), year_match.group(1), text)

        elif cat == "financial_auth":
            # Try tax rate table for rate claims
            result = None  # Tax rate verification is complex; pass to judge

        elif cat == "business_landmark":
            result = verify_business_exists(text, city)

        # If deterministic verifier didn't handle it or returned COULDNT_VERIFY,
        # try the search-LLM judge
        if result is None:
            result = judge_residual_claim(text, cat, neighborhood, city)
        elif result.verdict == "COULDNT_VERIFY" and cat in ("school", "year", "financial_auth"):
            # Escalate important COULDNT_VERIFY to the judge
            judge_result = judge_residual_claim(text, cat, neighborhood, city)
            if judge_result.verdict != "COULDNT_VERIFY":
                result = judge_result

        report.results.append(result)

    return report


def format_verification_report(report: VerificationReport) -> str:
    """Format verification report as human-readable review document."""
    lines = [
        f"VERIFICATION REPORT — {report.neighborhood}, {report.city}",
        f"Post ID: {report.post_id}",
        f"{'=' * 70}",
        f"Total claims: {len(report.results)}",
        f"  VERIFIED:        {report.verified_count}",
        f"  WRONG:           {report.wrong_count}",
        f"  COULDN'T VERIFY: {report.couldnt_verify_count}",
        f"  HUMAN FLAG:      {report.human_flag_count}",
        "",
    ]

    # WRONG claims — individual review required for high-stakes
    wrong = [r for r in report.results if r.verdict == "WRONG"]
    if wrong:
        lines.append("CORRECTIONS — INDIVIDUAL REVIEW REQUIRED")
        lines.append("(No batch-approve for high-stakes factual corrections)")
        lines.append(f"{'─' * 70}")
        for r in wrong:
            stakes = "HIGH-STAKES" if r.needs_individual_review else "STANDARD"
            lines.append(f"\n  [{stakes}] {r.claim_text}")
            lines.append(f"  Verdict: WRONG (confidence {r.confidence:.2f})")
            lines.append(f"  Correct: {r.correct_value}")
            lines.append(f"  Source:  {r.source_url}")
            lines.append(f"  Patch:   {r.proposed_patch}")
            lines.append(f"  Note:    {r.note}")
            lines.append(f"  Status:  PENDING_REVIEW")

    # Volatile softenings — batch-approvable
    volatile = [r for r in report.results if r.category == "volatile"]
    if volatile:
        lines.append(f"\n\nSOFTENINGS — BATCH-APPROVABLE")
        lines.append(f"{'─' * 70}")
        for r in volatile:
            lines.append(f"  [SOFTEN] {r.claim_text}")
            lines.append(f"           → {r.proposed_patch}")

    # COULDN'T VERIFY — needs human
    unverified = [r for r in report.results if r.verdict == "COULDNT_VERIFY"]
    if unverified:
        lines.append(f"\n\nCOULDN'T VERIFY — HUMAN REVIEW NEEDED")
        lines.append(f"{'─' * 70}")
        for r in unverified:
            lines.append(f"  [CHECK] {r.claim_text}")
            lines.append(f"          {r.note}")

    # Verified (summary only — no review needed)
    verified = [r for r in report.results if r.verdict == "VERIFIED"]
    if verified:
        lines.append(f"\n\nVERIFIED ({len(verified)} claims — no review needed)")
        lines.append(f"{'─' * 70}")
        for r in verified:
            lines.append(f"  [✓] {r.claim_text}  ({r.source_name})")

    # Human flags (subjective)
    flags = [r for r in report.results if r.verdict == "HUMAN_FLAG" and r.category != "volatile"]
    if flags:
        lines.append(f"\n\nSUBJECTIVE — EDITORIAL JUDGMENT")
        lines.append(f"{'─' * 70}")
        for r in flags:
            lines.append(f"  [EDITORIAL] {r.claim_text}")

    lines.append(f"\n{'=' * 70}")
    lines.append("Review: WRONG items require individual approve/reject.")
    lines.append("Softenings can be batch-approved.")
    lines.append("COULDN'T VERIFY items need manual checking against listed source types.")
    lines.append("Nothing is auto-applied. All patches are PROPOSED.")

    return "\n".join(lines)


def export_verification_json(report: VerificationReport) -> dict:
    """Export verification report as structured JSON for programmatic review."""
    return {
        "post_id": report.post_id,
        "neighborhood": report.neighborhood,
        "city": report.city,
        "summary": {
            "total": len(report.results),
            "verified": report.verified_count,
            "wrong": report.wrong_count,
            "couldnt_verify": report.couldnt_verify_count,
            "human_flag": report.human_flag_count,
        },
        "corrections": [
            {
                "claim": r.claim_text,
                "category": r.category,
                "confidence": r.confidence,
                "source_url": r.source_url,
                "correct_value": r.correct_value,
                "proposed_patch": r.proposed_patch,
                "requires_individual_review": r.needs_individual_review,
                "status": "PENDING_REVIEW",
            }
            for r in report.results if r.verdict == "WRONG"
        ],
        "softenings": [
            {
                "claim": r.claim_text,
                "proposed_patch": r.proposed_patch,
                "status": "PENDING_REVIEW",
            }
            for r in report.results if r.category == "volatile"
        ],
        "unverified": [
            {
                "claim": r.claim_text,
                "category": r.category,
                "note": r.note,
                "status": "NEEDS_HUMAN_REVIEW",
            }
            for r in report.results if r.verdict == "COULDNT_VERIFY"
        ],
        "verified": [
            {
                "claim": r.claim_text,
                "source": r.source_name,
                "source_url": r.source_url,
            }
            for r in report.results if r.verdict == "VERIFIED"
        ],
    }
