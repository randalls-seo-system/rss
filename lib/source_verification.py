"""Shared source-verification functions — single implementation for both
adversarial_review.py and D2 claims verification in orchestrator.py.

L33: extracted from adversarial_review.py to prevent the duplicate-module
pattern (two CSS allowlists, two banned-phrase lists, four .conf parsers).
Both consumers import from here.

Functions:
  judge_claim_against_source — LLM judge: STATES / CONTRADICTS / NOT_STATED
  search_authority_sources   — Serper.dev search filtered to authority domains
  fetch_for_verification     — URL fetch with page cache, no content blocklist
  is_authority_domain        — .gov / .mil / GSE domain check
  is_rejected_domain         — lender blog / aggregator blocklist

  verify_claim               — full pipeline: fetch cited URL → judge →
                                search fallback → judge search results.
                                Returns (verdict, source_url, quote, attempt_log).
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Authority domain constants ───────────────────────────────────────

VERIFICATION_AUTHORITY_TLDS = (".gov", ".mil")
VERIFICATION_AUTHORITY_DOMAINS = (
    "fanniemae.com", "freddiemac.com",
    "ecfr.gov", "federalregister.gov",
)
VERIFICATION_REJECTED_DOMAINS = (
    "veteransunited.com", "rocketmortgage.com", "lendingtree.com",
    "bankrate.com", "nerdwallet.com", "investopedia.com",
    "zillow.com", "realtor.com", "redfin.com", "movoto.com",
)


def is_authority_domain(url: str) -> bool:
    """Check if URL is from an authority domain suitable for verification."""
    domain = urlparse(url).netloc.lower().lstrip("www.")
    if any(domain.endswith(tld) for tld in VERIFICATION_AUTHORITY_TLDS):
        return True
    return any(domain == d or domain.endswith("." + d)
               for d in VERIFICATION_AUTHORITY_DOMAINS)


def is_rejected_domain(url: str) -> bool:
    """Check if URL is from a rejected domain (lender blogs, aggregators)."""
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith("." + d)
               for d in VERIFICATION_REJECTED_DOMAINS)


# ── Fetch ────────────────────────────────────────────────────────────

def _load_page_fetch():
    import importlib.util as _ilu
    _pf_path = REPO_ROOT / "modules" / "content-production-v2" / "lib" / "page_fetch.py"
    spec = _ilu.spec_from_file_location("_page_fetch", _pf_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch_for_verification(url: str) -> str | None:
    """Fetch a URL for verification. No content-sourcing blocklist.
    Shares the page cache with page_fetch for efficiency."""
    pf = _load_page_fetch()
    cached = pf.cache_get(url)
    if cached is not None:
        return cached
    try:
        import requests
        resp = requests.get(
            url,
            headers={"User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )},
            timeout=15,
        )
        resp.raise_for_status()
        html = resp.text
        pf.cache_set(url, html)
        return html
    except Exception as e:
        print(f"  [verify] Failed to fetch {url[:80]}: {e}", file=sys.stderr)
        return None


# ── LLM judge ────────────────────────────────────────────────────────

def _get_llm_client():
    import importlib.util as _ilu
    _llm_path = REPO_ROOT / "modules" / "content-production-v2" / "lib" / "llm_client.py"
    spec = _ilu.spec_from_file_location("_llm_client", _llm_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LLMClient(provider="claude_cli", model="haiku")


def judge_claim_against_source(
    source_text: str,
    claim_text: str,
    proposed_fix: str = "",
    source_url: str = "",
) -> tuple[str, str]:
    """LLM judge: does this source text STATE the claim?

    Returns (verdict, quoted_text) where verdict is one of:
      STATES      — source explicitly states the claim; quote included.
      CONTRADICTS — source states something incompatible; quote included.
      NOT_STATED  — source does not address the specific claim.

    If verdict is STATES but quote is empty, downgrades to NOT_STATED.
    The quote is the evidence — a STATES verdict without it is unverifiable.
    """
    import hashlib as _hl

    source_excerpt = source_text[:8000]
    fix_line = f'\nPROPOSED FIX: "{proposed_fix}"' if proposed_fix else ""

    prompt = (
        "You are verifying whether a source document states a specific claim.\n\n"
        f'CLAIM: "{claim_text}"\n'
        f'{fix_line}\n\n'
        f"SOURCE TEXT (from {source_url}):\n{source_excerpt}\n\n"
        "Does this source STATE the specific claim above? Answer ONE of:\n\n"
        "STATES — The source explicitly states this claim. Quote the exact sentence.\n"
        "CONTRADICTS — The source states something incompatible with this claim. "
        "Quote the exact sentence.\n"
        "NOT_STATED — The source does not address this specific claim.\n\n"
        "IMPORTANT: A source that discusses the general CATEGORY or TOPIC of the "
        "claim without stating the specific FIGURE, RATE, THRESHOLD, or FACT "
        "claimed is NOT_STATED. For example, a page that lists fee categories "
        "without stating dollar amounts does NOT state a claim about specific "
        "dollar figures. A page that discusses a program's existence without "
        "confirming the reviewer's specific assertion about that program is "
        "NOT_STATED.\n\n"
        "Return ONLY a JSON object:\n"
        '{"verdict": "STATES|CONTRADICTS|NOT_STATED", '
        '"quote": "exact sentence from source, or empty string"}'
    )

    h = _hl.md5(
        f"verify-judge|{claim_text[:100]}|{source_url}".encode()
    ).hexdigest()[:12]

    try:
        client = _get_llm_client()
        response = client.call(prompt, cache_key=f"verify-judge|{h}")
        text = response.text.strip()

        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            verdict = result.get("verdict", "NOT_STATED").upper()
            quote = result.get("quote", "")
            if verdict not in ("STATES", "CONTRADICTS", "NOT_STATED"):
                verdict = "NOT_STATED"
            # L33: STATES without a quote is unverifiable — downgrade.
            if verdict == "STATES" and not quote.strip():
                verdict = "NOT_STATED"
            return verdict, quote
    except Exception as e:
        print(f"  [verify] Judge call failed: {e}", file=sys.stderr)

    return "NOT_STATED", ""


# ── Search ───────────────────────────────────────────────────────────

def search_authority_sources(claim_text: str, max_results: int = 3) -> list[dict]:
    """Search Serper.dev for authority sources (.gov, .mil, GSE) that might
    state this claim. Returns up to max_results dicts with {title, snippet, url}."""
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return []

    try:
        import requests
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": claim_text, "num": 10},
            timeout=15,
        )
        data = resp.json()

        results = []
        for item in data.get("organic", []):
            link = item.get("link", "")
            if not is_authority_domain(link):
                continue
            if is_rejected_domain(link):
                continue
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": link,
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"  [verify] Search failed: {e}", file=sys.stderr)
        return []


# ── Attempt log ──────────────────────────────────────────────────────

@dataclass
class VerificationAttemptLog:
    """Records what was attempted during verification — enables diagnosing
    verification_failed vs genuine not_stated."""
    searches_run: int = 0
    search_results_returned: int = 0
    fetches_attempted: int = 0
    fetches_succeeded: int = 0
    judges_run: int = 0


# ── Full verify pipeline ────────────────────────────────────────────

def verify_claim(
    claim_text: str,
    proposed_fix: str = "",
    authority_url: str | None = None,
) -> tuple[str, str, str, VerificationAttemptLog]:
    """Verify a claim against authority sources.

    Pipeline: fetch cited authority → judge → search fallback → judge.

    Returns (verdict, source_url, quote, attempt_log) where verdict is:
      source_recovered    — authority source STATES the claim
      contradicts         — authority source CONTRADICTS the claim
      not_stated          — looked and no source states it
      verification_failed — could not look (search failed, all fetches failed)
    """
    log = VerificationAttemptLog()

    # Step 1: If an authority URL is provided, try it first
    if authority_url:
        log.fetches_attempted += 1
        html = fetch_for_verification(authority_url)
        if html:
            log.fetches_succeeded += 1
            from bs4 import BeautifulSoup
            text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
            log.judges_run += 1
            verdict, quote = judge_claim_against_source(text, claim_text, proposed_fix, authority_url)
            if verdict == "STATES":
                return "source_recovered", authority_url, quote, log
            if verdict == "CONTRADICTS":
                return "contradicts", authority_url, quote, log

    # Step 2: Search for authority sources
    log.searches_run += 1
    results = search_authority_sources(claim_text)
    log.search_results_returned += len(results)

    for sr in results:
        log.fetches_attempted += 1
        sr_html = fetch_for_verification(sr["url"])
        if not sr_html:
            continue
        log.fetches_succeeded += 1

        from bs4 import BeautifulSoup
        sr_text = BeautifulSoup(sr_html, "html.parser").get_text(separator=" ", strip=True)
        log.judges_run += 1
        verdict, quote = judge_claim_against_source(sr_text, claim_text, proposed_fix, sr["url"])

        if verdict == "STATES":
            return "source_recovered", sr["url"], quote, log
        if verdict == "CONTRADICTS":
            return "contradicts", sr["url"], quote, log

    # Step 3: Determine not_stated vs verification_failed
    # verification_failed: we could not look successfully
    # not_stated: we looked and nothing stated it
    if log.fetches_succeeded == 0 and log.fetches_attempted > 0:
        # All fetches failed — we didn't actually check anything
        return "verification_failed", "", "", log
    if log.searches_run > 0 and log.search_results_returned == 0 and log.fetches_succeeded == 0:
        # Search returned nothing and no cited URL worked
        return "verification_failed", "", "", log
    if log.judges_run == 0:
        # Never ran a judge — either no search results and no cited URL,
        # or search failed entirely
        return "verification_failed", "", "", log

    return "not_stated", "", "", log
