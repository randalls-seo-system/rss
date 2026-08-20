"""Adversarial review — second-model critique via OpenAI.

Bounded: exactly one review -> one revision -> one confirmation review.
Evidence-verified: reviewer's factual corrections are verified against
fetched primary sources before being applied.

See docs/GATES.md for the incident that motivated this.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str  # critical, high, medium, low
    category: str  # factual, legal, structural, editorial, coverage
    location: str
    issue: str
    proposed_fix: str
    authority: str | None = None

    @property
    def is_actionable(self) -> bool:
        return self.severity in ("critical", "high") and self.category in ("factual", "legal")

    @property
    def is_subtractive(self) -> bool:
        lower = self.proposed_fix.lower()
        return any(w in lower for w in ("remove", "delete", "drop", "cut", "omit", "hedge"))


@dataclass
class ReviewReport:
    findings: list[Finding] = field(default_factory=list)
    overall_score: float = 0.0
    top_priorities: list[str] = field(default_factory=list)
    raw_response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0
    model: str = ""


@dataclass
class TriageResult:
    fix_queue: list[Finding] = field(default_factory=list)
    advisory: list[Finding] = field(default_factory=list)


@dataclass
class VerifiedFix:
    finding: Finding
    status: str  # verified, disputed, not_stated, subtractive_no_auth
    evidence_text: str = ""
    evidence_url: str = ""


@dataclass
class RevisionResult:
    revised_html: str = ""
    fixes_applied: list[VerifiedFix] = field(default_factory=list)
    advisory_additions: list[Finding] = field(default_factory=list)
    confirmation_passed: bool = False
    confirmation_unresolved: list[str] = field(default_factory=list)
    total_cost: float = 0.0
    review_calls: int = 0


# ---------------------------------------------------------------------------
# OpenAI client (minimal, mirrors llm_client retry/backoff)
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
BACKOFF_BASE = 2

# Per-million-token pricing
PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.6":      (2.50, 10.00),
    "gpt-5.4":      (2.50, 20.00),
    "gpt-5.4-mini": (0.75,  4.50),
    "o3-mini":      (1.10,  4.40),
}


def _load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        env_path = REPO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError("OPENAI_API_KEY not found in environment or .env")
    return key


def _call_openai(
    messages: list[dict[str, str]],
    *,
    model: str = "gpt-5.6",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> tuple[str, int, int]:
    """Call OpenAI chat API. Returns (text, input_tokens, output_tokens)."""
    from openai import OpenAI

    client = OpenAI(api_key=_load_api_key())

    # Reasoning models (o3, gpt-5.x) don't support temperature
    _no_temp_models = ("gpt-5.6", "gpt-5.4", "o3", "o3-mini", "o4-mini")
    supports_temp = not any(model.startswith(p) for p in _no_temp_models)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            create_kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
            )
            if supports_temp:
                create_kwargs["temperature"] = temperature
            resp = client.chat.completions.create(**create_kwargs)
            text = resp.choices[0].message.content or ""
            usage = resp.usage
            return text, usage.prompt_tokens, usage.completion_tokens
        except Exception as e:
            last_error = e
            err_lower = str(e).lower()
            if any(p in err_lower for p in ("invalid api key", "auth", "permission")):
                raise
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE * (2 ** attempt)
                print(f"  [review] OpenAI retry {attempt+1}/{MAX_RETRIES}: {e}",
                      file=sys.stderr)
                time.sleep(wait)

    raise RuntimeError(f"OpenAI call failed after {MAX_RETRIES+1} attempts: {last_error}")


def _estimate_cost(model: str, inp: int, out: int) -> float:
    rates = PRICING.get(model, (2.50, 10.00))
    return (inp * rates[0] + out * rates[1]) / 1_000_000


def _parse_review_json(raw: str) -> dict:
    """Parse review response JSON defensively."""
    text = raw.strip()
    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # Try to find JSON object
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
    # Find matching close brace
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i+1])
    raise ValueError("Unclosed JSON object")


# ---------------------------------------------------------------------------
# Vertical-aware review prompt
# ---------------------------------------------------------------------------

_VERTICAL_CONTEXT = {
    "mortgage": "You are reviewing mortgage/VA-loan content for a licensed mortgage operation. "
                "Pay special attention to: TILA/RESPA compliance, VA loan eligibility rules, "
                "rate/APR claims, fee disclosures, NMLS requirements, and state-specific licensing. "
                "Flag any claim that could create regulatory liability.",
    "real_estate": "You are reviewing real estate content for a licensed brokerage. "
                   "Pay special attention to: Fair Housing compliance (no demographic targeting), "
                   "TREC advertising rules, NAR settlement compliance, property tax claims, "
                   "school district accuracy, and MLS data attribution. "
                   "Flag any claim that could create regulatory or legal liability.",
    "insurance": "You are reviewing insurance content. Pay special attention to: "
                 "state licensing requirements, coverage claim accuracy, premium estimates, "
                 "and regulatory compliance. Flag misleading coverage descriptions.",
}

_REVIEW_SYSTEM = """You are an adversarial domain-expert reviewer. Your job is to find factual errors, legal risks, and structural problems in the article below. You are NOT trying to improve style — focus on correctness and liability.

{vertical_context}

{claims_policy_block}

Return STRICT JSON only. No markdown, no commentary outside the JSON.

Schema:
{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "category": "factual|legal|structural|editorial|coverage",
      "location": "<quoted snippet or H2 title>",
      "issue": "<one sentence describing the problem>",
      "proposed_fix": "<concrete fix>",
      "authority": "<primary source URL or citation if factual/legal, else null>"
    }}
  ],
  "overall_score": <0-100>,
  "top_priorities": ["<max 5 one-sentence priorities>"]
}}

Rules:
- severity=critical: factual error that could cause financial harm or legal liability
- severity=high: incorrect fact or misleading claim, not immediately harmful
- severity=medium: structural issue, missing context, or suboptimal coverage
- severity=low: editorial suggestion, style preference
- For factual/legal findings, ALWAYS include an authority (URL or document citation)
- Do NOT flag style preferences as critical/high
- Do NOT flag valid hedging language ("may", "can", "check with your lender") as errors
- Limit findings to 15 maximum — focus on the most important issues"""


def _build_review_prompt(
    html: str,
    *,
    vertical: str = "real_estate",
    claims_policy_text: str = "",
    target_keyword: str = "",
) -> list[dict[str, str]]:
    vert_ctx = _VERTICAL_CONTEXT.get(vertical, _VERTICAL_CONTEXT["real_estate"])
    policy_block = ""
    if claims_policy_text:
        policy_block = (
            "The site has the following claims policy. Flag any violations:\n\n"
            + claims_policy_text[:3000]
        )

    system = _REVIEW_SYSTEM.format(
        vertical_context=vert_ctx,
        claims_policy_block=policy_block,
    )

    user = f"Target keyword: {target_keyword}\n\nArticle HTML:\n\n{html[:60000]}"

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_confirmation_prompt(
    original_findings: list[Finding],
    revised_sections: str,
) -> list[dict[str, str]]:
    findings_text = "\n".join(
        f"- [{f.severity}/{f.category}] {f.issue} (location: {f.location})"
        for f in original_findings
    )
    system = (
        "You are reviewing whether specific critical/high findings were resolved. "
        "Return STRICT JSON only:\n"
        '{"resolved": ["<finding description>"], "unresolved": ["<finding description>"]}'
    )
    user = (
        f"Original findings to check:\n{findings_text}\n\n"
        f"Revised content:\n{revised_sections[:30000]}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Core: run_review
# ---------------------------------------------------------------------------

def run_review(
    article_html: str,
    *,
    site_slug: str = "",
    content_type: str = "article",
    target_keyword: str = "",
    claims_policy_text: str = "",
    model: str = "gpt-5.6",
    config: dict | None = None,
) -> ReviewReport:
    """Run adversarial review on article HTML. Returns ReviewReport."""
    vertical = "real_estate"
    if config:
        vertical = config.get("content", {}).get("vertical", "real_estate")

    messages = _build_review_prompt(
        article_html,
        vertical=vertical,
        claims_policy_text=claims_policy_text,
        target_keyword=target_keyword,
    )

    # Token estimate check (rough: 4 chars per token)
    est_input_tokens = sum(len(m["content"]) for m in messages) // 4
    budget_cap = 100000  # default 100k input tokens
    if config:
        budget_cap = config.get("content", {}).get("adversarial_review", {}).get(
            "budget_cap_tokens", 100000)
    if est_input_tokens > budget_cap:
        raise RuntimeError(
            f"Review input estimate ({est_input_tokens} tokens) exceeds budget cap ({budget_cap})")

    raw, inp, out = _call_openai(messages, model=model, max_tokens=4096)
    cost = _estimate_cost(model, inp, out)

    # Parse defensively
    try:
        data = _parse_review_json(raw)
    except (ValueError, json.JSONDecodeError):
        # One retry with format reminder
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": (
            "Your response was not valid JSON. Please return ONLY a JSON object "
            "matching the schema above. No markdown fences, no commentary."
        )})
        raw2, inp2, out2 = _call_openai(messages, model=model, max_tokens=4096)
        cost += _estimate_cost(model, inp2, out2)
        inp += inp2
        out += out2
        try:
            data = _parse_review_json(raw2)
        except (ValueError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"Adversarial review returned malformed JSON after retry: {e}\n"
                f"Raw: {raw2[:500]}"
            )

    findings = []
    for f in data.get("findings", []):
        findings.append(Finding(
            severity=f.get("severity", "low"),
            category=f.get("category", "editorial"),
            location=f.get("location", ""),
            issue=f.get("issue", ""),
            proposed_fix=f.get("proposed_fix", ""),
            authority=f.get("authority"),
        ))

    return ReviewReport(
        findings=findings,
        overall_score=data.get("overall_score", 0),
        top_priorities=data.get("top_priorities", []),
        raw_response=raw,
        input_tokens=inp,
        output_tokens=out,
        cost_estimate=round(cost, 6),
        model=model,
    )


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

def triage_findings(findings: list[Finding]) -> TriageResult:
    """Split findings into fix queue (auto-apply) vs advisory (human review)."""
    fix_queue = []
    advisory = []
    for f in findings:
        if f.is_actionable:
            fix_queue.append(f)
        else:
            advisory.append(f)
    return TriageResult(fix_queue=fix_queue, advisory=advisory)


# ---------------------------------------------------------------------------
# Evidence verification — LLM judge + search fallback
# ---------------------------------------------------------------------------

# Authority domains for claim verification. These are the only domains
# accepted as verification sources. The content-sourcing blocklist in
# page_fetch.py is intentionally NOT used here — a reviewer citing WSJ
# or Forbes should not be silently downgraded.
VERIFICATION_AUTHORITY_TLDS = (".gov", ".mil")
VERIFICATION_AUTHORITY_DOMAINS = (
    "fanniemae.com", "freddiemac.com",
    "ecfr.gov", "federalregister.gov",
)
# Lender blogs and aggregators are not authoritative verification sources.
VERIFICATION_REJECTED_DOMAINS = (
    "veteransunited.com", "rocketmortgage.com", "lendingtree.com",
    "bankrate.com", "nerdwallet.com", "investopedia.com",
    "zillow.com", "realtor.com", "redfin.com", "movoto.com",
)


def _is_authority_domain(url: str) -> bool:
    """Check if URL is from an authority domain suitable for verification."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().lstrip("www.")
    if any(domain.endswith(tld) for tld in VERIFICATION_AUTHORITY_TLDS):
        return True
    return any(domain == d or domain.endswith("." + d)
               for d in VERIFICATION_AUTHORITY_DOMAINS)


def _is_rejected_verification_domain(url: str) -> bool:
    """Check if URL is from a rejected domain (lender blogs, aggregators)."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith("." + d)
               for d in VERIFICATION_REJECTED_DOMAINS)


def _load_page_fetch():
    """Load page_fetch module via importlib (avoids top-level lib package conflict)."""
    import importlib.util as _ilu
    _pf_path = REPO_ROOT / "modules" / "content-production-v2" / "lib" / "page_fetch.py"
    spec = _ilu.spec_from_file_location("_page_fetch", _pf_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fetch_for_verification(url: str) -> str | None:
    """Fetch a URL for verification purposes.

    Does NOT use the content-sourcing blocklist from page_fetch.py.
    Reviewer citations may point to paywalled or competitor sources that
    are blocked for content sourcing but valid as verification evidence.
    Shares the page cache with page_fetch for efficiency.
    """
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
        print(f"  [review] Failed to fetch {url[:80]}: {e}", file=sys.stderr)
        return None


def _get_llm_client():
    """Get LLMClient for verification judge calls (claude_cli/haiku)."""
    import importlib.util as _ilu
    _llm_path = REPO_ROOT / "modules" / "content-production-v2" / "lib" / "llm_client.py"
    spec = _ilu.spec_from_file_location("_llm_client", _llm_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LLMClient(provider="claude_cli", model="haiku")


def _judge_source(
    source_text: str,
    finding: Finding,
    source_url: str = "",
) -> tuple[str, str]:
    """LLM judge: does this source text STATE the finding's claim?

    Returns (verdict, quoted_text) where verdict is one of:
      STATES      — source explicitly states the claim; quote included.
      CONTRADICTS — source states something incompatible; quote included.
      NOT_STATED  — source does not address the specific claim.
    """
    import hashlib as _hl

    source_excerpt = source_text[:8000]

    prompt = (
        "You are verifying whether a source document states a specific claim.\n\n"
        f'CLAIM: "{finding.issue}"\n'
        f'PROPOSED FIX: "{finding.proposed_fix}"\n\n'
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
        f"verify-judge|{finding.issue[:100]}|{source_url}".encode()
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
            return verdict, quote
    except Exception as e:
        print(f"  [review] Judge call failed: {e}", file=sys.stderr)

    return "NOT_STATED", ""


def _search_for_claim_source(finding: Finding) -> list[dict]:
    """Search Serper.dev for authority sources that might state this claim.

    Returns up to 3 results from authority domains (.gov, .mil, GSE guides).
    N=3 because: authority domains are a narrow set, each requires a fetch +
    LLM call (~5s), and if the top 3 authority-domain results from a broad
    search don't state the claim, deeper results won't either.
    """
    import os as _os
    api_key = _os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return []

    try:
        import requests
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": finding.issue, "num": 10},
            timeout=15,
        )
        data = resp.json()

        results = []
        for item in data.get("organic", []):
            link = item.get("link", "")
            if not _is_authority_domain(link):
                continue
            if _is_rejected_verification_domain(link):
                continue
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": link,
            })
            if len(results) >= 3:
                break
        return results
    except Exception as e:
        print(f"  [review] Search failed: {e}", file=sys.stderr)
        return []


def verify_fix(finding: Finding) -> VerifiedFix:
    """Verify a finding's proposed fix against its cited authority.

    Uses an LLM judge (claude_cli/haiku) to determine whether the source
    STATES the specific claim, then falls back to a Serper.dev search for
    an authority-domain source if the cited URL is unfetchable or does not
    state the claim.
    """
    if not finding.authority:
        if finding.is_subtractive:
            return VerifiedFix(
                finding=finding,
                status="subtractive_no_auth",
            )
        return VerifiedFix(
            finding=finding,
            status="disputed",
            evidence_text="No authority cited for additive fix",
        )

    # Step 1: Fetch the cited authority (no content blocklist)
    html = _fetch_for_verification(finding.authority)

    if html:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(html, "html.parser").get_text(
            separator=" ", strip=True)

        # Step 2: LLM judge — does the source STATE the claim?
        verdict, quote = _judge_source(text, finding, finding.authority)

        if verdict == "STATES":
            return VerifiedFix(
                finding=finding,
                status="verified",
                evidence_url=finding.authority,
                evidence_text=quote,
            )
        elif verdict == "CONTRADICTS":
            return VerifiedFix(
                finding=finding,
                status="disputed",
                evidence_url=finding.authority,
                evidence_text=f"Source contradicts the claim: {quote}",
            )
        # NOT_STATED falls through to search

    # Step 3: Search for an authority source that states the claim
    # (triggered when cited URL is unfetchable OR returned NOT_STATED)
    search_results = _search_for_claim_source(finding)
    sources_checked = 0

    for sr in search_results:
        sr_html = _fetch_for_verification(sr["url"])
        if not sr_html:
            continue

        from bs4 import BeautifulSoup
        sr_text = BeautifulSoup(sr_html, "html.parser").get_text(
            separator=" ", strip=True)
        sr_verdict, sr_quote = _judge_source(sr_text, finding, sr["url"])
        sources_checked += 1

        if sr_verdict == "STATES":
            return VerifiedFix(
                finding=finding,
                status="verified",
                evidence_url=sr["url"],
                evidence_text=sr_quote,
            )
        elif sr_verdict == "CONTRADICTS":
            return VerifiedFix(
                finding=finding,
                status="disputed",
                evidence_url=sr["url"],
                evidence_text=f"Authority source contradicts: {sr_quote}",
            )

    # No source states the claim after fetch + search
    reason = (
        f"Cited URL {'could not be fetched' if not html else 'does not state the claim'}; "
        f"searched {sources_checked} authority-domain source(s), none state this claim"
    )
    return VerifiedFix(
        finding=finding,
        status="not_stated",
        evidence_url=finding.authority,
        evidence_text=reason,
    )


# ---------------------------------------------------------------------------
# Revision pass
# ---------------------------------------------------------------------------

def apply_verified_fixes(
    html: str,
    fixes: list[VerifiedFix],
    *,
    model: str = "gpt-5.6",
    vertical: str = "real_estate",
) -> tuple[str, float]:
    """Apply verified fixes via LLM. Returns (revised_html, cost)."""
    applicable = [f for f in fixes if f.status in ("verified", "subtractive_no_auth")]
    if not applicable:
        return html, 0.0

    fixes_text = "\n".join(
        f"- LOCATION: {f.finding.location}\n"
        f"  ISSUE: {f.finding.issue}\n"
        f"  FIX: {f.finding.proposed_fix}\n"
        f"  EVIDENCE: {f.evidence_text[:200] if f.evidence_text else 'N/A'}"
        for f in applicable
    )

    messages = [
        {"role": "system", "content": (
            "You are a precise copy editor. Apply ONLY the listed fixes to the article HTML. "
            "Do not change anything else. Do not add new content. Do not restructure. "
            "Return the complete revised HTML."
        )},
        {"role": "user", "content": (
            f"Apply these fixes:\n\n{fixes_text}\n\n"
            f"Article HTML:\n\n{html[:60000]}"
        )},
    ]

    raw, inp, out = _call_openai(messages, model=model, max_tokens=16384)
    cost = _estimate_cost(model, inp, out)

    # Extract HTML from response
    revised = raw.strip()
    if revised.startswith("```"):
        revised = re.sub(r'^```(?:html)?\s*', '', revised)
        revised = re.sub(r'\s*```$', '', revised)

    return revised, cost


# ---------------------------------------------------------------------------
# Full review cycle
# ---------------------------------------------------------------------------

def run_review_cycle(
    article_html: str,
    *,
    site_slug: str = "",
    content_type: str = "article",
    target_keyword: str = "",
    claims_policy_text: str = "",
    model: str = "gpt-5.6",
    config: dict | None = None,
    job_dir: Path | None = None,
    post_id: int = 0,
) -> RevisionResult:
    """Full bounded review cycle: review -> triage -> verify -> revise -> confirm -> re-gate.

    Exactly one review + one revision + one confirmation. Never loops.
    """
    result = RevisionResult()
    vertical = "real_estate"
    if config:
        vertical = config.get("content", {}).get("vertical", "real_estate")

    eprint = lambda msg: print(f"  [review] {msg}", file=sys.stderr)

    # Step 1: Review
    eprint("Running adversarial review...")
    report = run_review(
        article_html,
        site_slug=site_slug,
        content_type=content_type,
        target_keyword=target_keyword,
        claims_policy_text=claims_policy_text,
        model=model,
        config=config,
    )
    result.total_cost += report.cost_estimate
    result.review_calls += 1
    eprint(f"Review complete: {len(report.findings)} findings, score={report.overall_score}")

    if not report.findings:
        eprint("No findings — article passes review")
        result.revised_html = article_html
        result.confirmation_passed = True
        return result

    # Step 2: Triage
    triage = triage_findings(report.findings)
    eprint(f"Triage: {len(triage.fix_queue)} actionable, {len(triage.advisory)} advisory")
    result.advisory_additions = triage.advisory

    # Write advisory file
    if job_dir and triage.advisory:
        advisory_path = job_dir / f"{post_id}-review-advisory.md"
        lines = [
            f"# Adversarial Review Advisory — Post {post_id}",
            f"",
            f"Score: {report.overall_score}/100",
            f"Model: {report.model}",
            f"",
            f"## Top Priorities",
            *[f"- {p}" for p in report.top_priorities],
            f"",
            f"## Advisory Findings (human review — not auto-applied)",
            f"",
        ]
        for f in triage.advisory:
            lines.append(f"### [{f.severity}/{f.category}] {f.issue}")
            lines.append(f"- Location: {f.location}")
            lines.append(f"- Suggested fix: {f.proposed_fix}")
            if f.authority:
                lines.append(f"- Authority: {f.authority}")
            lines.append("")
        advisory_path.write_text("\n".join(lines))
        eprint(f"Advisory: {advisory_path.name}")

    if not triage.fix_queue:
        eprint("No actionable fixes — advisory only")
        result.revised_html = article_html
        result.confirmation_passed = True
        return result

    # Step 3: Verify each fix
    verified_fixes: list[VerifiedFix] = []
    unverified_criticals: list[VerifiedFix] = []
    for finding in triage.fix_queue:
        eprint(f"Verifying: {finding.issue[:60]}...")
        vf = verify_fix(finding)
        verified_fixes.append(vf)
        if vf.status == "disputed":
            eprint(f"  DISPUTED: {vf.evidence_text[:80]}")
            result.advisory_additions.append(finding)
        elif vf.status == "not_stated":
            eprint(f"  NOT_STATED: {vf.evidence_text[:80]}")
            if finding.is_actionable:
                unverified_criticals.append(vf)
            else:
                result.advisory_additions.append(finding)
        elif vf.status == "verified":
            eprint(f"  VERIFIED against {vf.evidence_url[:60]}")
        elif vf.status == "subtractive_no_auth":
            eprint(f"  SUBTRACTIVE (no auth needed): {finding.proposed_fix[:60]}")

    result.fixes_applied = verified_fixes

    # PARK if any critical/high factual/legal findings could not be verified.
    # A dead authority URL or a NOT_STATED result on a critical finding must
    # not silently become an advisory note — it must block the job.
    if unverified_criticals:
        reasons = [
            f"[{vf.finding.severity}/{vf.finding.category}] "
            f"{vf.finding.issue}: {vf.evidence_text}"
            for vf in unverified_criticals
        ]
        eprint(f"PARKING: {len(unverified_criticals)} critical finding(s) "
               f"could not be verified against any authority source")
        for r in reasons:
            eprint(f"  {r[:120]}")
        result.revised_html = article_html
        result.confirmation_passed = False
        result.confirmation_unresolved = reasons
        if job_dir and triage.fix_queue:
            _append_disputed_to_advisory(job_dir, post_id, verified_fixes)
        return result

    applicable = [f for f in verified_fixes if f.status in ("verified", "subtractive_no_auth")]

    if not applicable:
        eprint("No fixes verified — all disputed/not_stated")
        result.revised_html = article_html
        result.confirmation_passed = True
        # Update advisory with disputed annotations
        if job_dir and triage.fix_queue:
            _append_disputed_to_advisory(job_dir, post_id, verified_fixes)
        return result

    # Step 4: Apply fixes
    eprint(f"Applying {len(applicable)} verified fixes...")
    revised_html, rev_cost = apply_verified_fixes(
        article_html, applicable, model=model, vertical=vertical,
    )
    result.total_cost += rev_cost
    result.revised_html = revised_html

    # Step 5: Confirmation review (only checks critical/high resolution)
    eprint("Running confirmation review...")
    actionable_findings = [f.finding for f in applicable]
    conf_messages = _build_confirmation_prompt(actionable_findings, revised_html)
    conf_raw, conf_inp, conf_out = _call_openai(conf_messages, model=model, max_tokens=2048)
    result.total_cost += _estimate_cost(model, conf_inp, conf_out)
    result.review_calls += 1

    try:
        conf_data = _parse_review_json(conf_raw)
        unresolved = conf_data.get("unresolved", [])
    except (ValueError, json.JSONDecodeError):
        unresolved = []

    result.confirmation_unresolved = unresolved
    result.confirmation_passed = len(unresolved) == 0
    if unresolved:
        eprint(f"Confirmation: {len(unresolved)} unresolved (parking for human review)")
    else:
        eprint("Confirmation: all critical/high fixes resolved")

    # Step 6: Re-run gates on revised artifact
    import importlib.util as _ilu
    _gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
    _gl_mod = _ilu.module_from_spec(_gl_spec)
    _gl_spec.loader.exec_module(_gl_mod)

    gate_report = _gl_mod.run_universal_gates(
        revised_html,
        site_slug=site_slug,
        content_type=content_type,
        config=config,
    )
    if not gate_report.passed:
        eprint(f"GATE FAILED on revised artifact: {gate_report.summary()}")
        result.confirmation_passed = False
        result.confirmation_unresolved.append(f"Gate failures: {gate_report.summary()}")

    eprint(f"Review cycle complete: cost=${result.total_cost:.4f}, "
           f"{result.review_calls} review calls")

    return result


def _append_disputed_to_advisory(job_dir: Path, post_id: int, fixes: list[VerifiedFix]):
    """Append DISPUTED annotations to the advisory file."""
    path = job_dir / f"{post_id}-review-advisory.md"
    lines = []
    if path.exists():
        lines = path.read_text().splitlines()
    lines.append("")
    lines.append("## DISPUTED Fixes (reviewer claim vs. source)")
    lines.append("")
    for vf in fixes:
        if vf.status == "disputed":
            lines.append(f"### {vf.finding.issue}")
            lines.append(f"- Reviewer says: {vf.finding.proposed_fix}")
            lines.append(f"- Source ({vf.evidence_url}): {vf.evidence_text}")
            lines.append(f"- **Decision: NOT APPLIED — source does not support reviewer's claim**")
            lines.append("")
        elif vf.status == "not_stated":
            lines.append(f"### {vf.finding.issue}")
            lines.append(f"- Reviewer says: {vf.finding.proposed_fix}")
            lines.append(f"- Cited: {vf.evidence_url}")
            lines.append(f"- {vf.evidence_text}")
            lines.append(f"- **Decision: NOT APPLIED — no authority source states this claim**")
            lines.append("")
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI: rss review
# ---------------------------------------------------------------------------

def cli_review(args: list[str] | None = None) -> int:
    """CLI entry point: rss review --site <slug> --job <id>."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="rss review",
        description="Run adversarial review on a pipeline job's deploy artifact",
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--job", required=True, help="Job ID")
    parser.add_argument("--model", default="gpt-5.6", help="OpenAI model")
    parser.add_argument("--dry-run", action="store_true", help="Show findings only, no fixes")

    parsed = parser.parse_args(args)

    sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))
    from lib.orchestrator import load_job, job_dir as get_job_dir

    job = load_job(parsed.job)
    jdir = get_job_dir(job)

    # Resolve deploy artifact — no candidate list, no glob, no fallback
    from lib.artifact_resolver import resolve_deploy_artifact, ArtifactResolutionError
    try:
        resolved = resolve_deploy_artifact(job, jdir)
    except ArtifactResolutionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    html_path = resolved.path
    post_id = resolved.post_id
    html = html_path.read_text()
    print(f"Reviewing: {html_path.name} ({len(html)} bytes)")

    # Load config
    config_path = REPO_ROOT / "sites" / parsed.site / "config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}

    # Load claims policy
    policy_text = ""
    policy_path = config.get("content", {}).get("claims_policy", "")
    if policy_path:
        expanded = Path(policy_path).expanduser()
        if not expanded.is_absolute():
            expanded = REPO_ROOT / policy_path
        if expanded.exists():
            policy_text = expanded.read_text()[:3000]

    if parsed.dry_run:
        report = run_review(
            html,
            site_slug=parsed.site,
            content_type="article",
            target_keyword=job.get("topic", ""),
            claims_policy_text=policy_text,
            model=parsed.model,
            config=config,
        )
        print(f"\nScore: {report.overall_score}/100")
        print(f"Findings: {len(report.findings)}")
        print(f"Cost: ${report.cost_estimate:.4f}")
        print(f"\nTop priorities:")
        for p in report.top_priorities:
            print(f"  - {p}")
        print(f"\nFindings:")
        for f in report.findings:
            print(f"  [{f.severity}/{f.category}] {f.issue}")
            print(f"    Location: {f.location[:60]}")
            print(f"    Fix: {f.proposed_fix[:80]}")
            if f.authority:
                print(f"    Authority: {f.authority}")
        return 0

    # Full cycle
    result = run_review_cycle(
        html,
        site_slug=parsed.site,
        content_type="article",
        target_keyword=job.get("topic", ""),
        claims_policy_text=policy_text,
        model=parsed.model,
        config=config,
        job_dir=jdir,
        post_id=post_id,
    )

    print(f"\nReview cycle complete:")
    print(f"  Review calls: {result.review_calls}")
    print(f"  Total cost: ${result.total_cost:.4f}")
    print(f"  Fixes applied: {len([f for f in result.fixes_applied if f.status in ('verified', 'subtractive_no_auth')])}")
    print(f"  Advisory items: {len(result.advisory_additions)}")
    print(f"  Confirmation: {'PASSED' if result.confirmation_passed else 'PARKED'}")
    if result.confirmation_unresolved:
        print(f"  Unresolved:")
        for u in result.confirmation_unresolved:
            print(f"    - {u}")

    # Write revised artifact if fixes were applied
    if result.revised_html and result.revised_html != html:
        revised_path = jdir / f"{post_id}-reviewed.html"
        revised_path.write_text(result.revised_html)
        print(f"  Revised artifact: {revised_path.name}")

    return 0 if result.confirmation_passed else 1
