"""Evidence layer — gives section writers real source material.

Two public functions:
  build_evidence_store  — runs once per article, produces {post_id}-evidence.json
  select_evidence_for_section — picks best items for a given section title

See docs/article-spec.md Section 17.3 for the spec.
"""

import difflib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lib.page_fetch import fetch_page, strip_boilerplate

MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = MODULE_DIR.parent.parent

MAX_ITEMS = 400
MAX_BYTES = 200_000  # ~200KB cap on store


def _eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    text: str
    kind: str  # competitor_page | google_paa | google_ai_overview | business_facts
    source_url: str = ""
    source_title: str = ""
    serp_position: int = -1
    tier: str = ""  # confirmed | verify (business_facts only)


# ---------------------------------------------------------------------------
# Passage extraction from competitor pages
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def _extract_passages(html: str) -> list[str]:
    """Extract <p> and <li> text nodes of 15-90 words from body HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    strip_boilerplate(soup)

    passages = []
    for el in soup.find_all(["p", "li"]):
        text = el.get_text(separator=" ", strip=True)
        wc = _word_count(text)
        if 15 <= wc <= 90:
            passages.append(text)
    return passages


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize_for_dedup(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _deduplicate(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Drop exact and >0.9 SequenceMatcher duplicates."""
    kept: list[EvidenceItem] = []
    seen_normalized: list[str] = []

    for item in items:
        norm = _normalize_for_dedup(item.text)
        is_dup = False
        for prev in seen_normalized:
            if norm == prev:
                is_dup = True
                break
            if difflib.SequenceMatcher(None, norm, prev).ratio() > 0.9:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
            seen_normalized.append(norm)
    return kept


# ---------------------------------------------------------------------------
# Business-facts parsing
# ---------------------------------------------------------------------------

def _parse_business_facts(facts_path: Path) -> list[EvidenceItem]:
    """Parse a business-facts markdown file into evidence items.

    Lines/cells after CONFIRMED or VERIFY markers get the appropriate tier.
    Falls back to scanning for the keywords in each line.
    """
    if not facts_path.exists():
        return []

    text = facts_path.read_text()
    items: list[EvidenceItem] = []

    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#") or line_stripped.startswith(">"):
            continue

        # Table rows: | Fact | Value | Status |
        if "|" in line_stripped:
            cells = [c.strip() for c in line_stripped.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            # Skip header-separator rows
            if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                continue
            # Skip header rows
            if cells[-1].upper() in ("STATUS", "STATUS?"):
                continue
            status_cell = cells[-1].upper() if len(cells) >= 3 else ""
            fact_text = " | ".join(cells[:-1]) if len(cells) >= 3 else " | ".join(cells)
            if "CONFIRMED" in status_cell:
                items.append(EvidenceItem(
                    text=fact_text, kind="business_facts", tier="confirmed"
                ))
            elif "VERIFY" in status_cell:
                items.append(EvidenceItem(
                    text=fact_text, kind="business_facts", tier="verify"
                ))
            elif "NEVER" not in status_cell:
                # Rows without explicit status — try to infer
                if "CONFIRMED" in line_stripped.upper():
                    items.append(EvidenceItem(
                        text=fact_text, kind="business_facts", tier="confirmed"
                    ))
                elif "VERIFY" in line_stripped.upper():
                    items.append(EvidenceItem(
                        text=fact_text, kind="business_facts", tier="verify"
                    ))
        else:
            # Non-table lines with markers
            if "CONFIRMED" in line_stripped.upper():
                items.append(EvidenceItem(
                    text=line_stripped, kind="business_facts", tier="confirmed"
                ))
            elif "VERIFY" in line_stripped.upper():
                items.append(EvidenceItem(
                    text=line_stripped, kind="business_facts", tier="verify"
                ))

    return items


# ---------------------------------------------------------------------------
# Public API: build_evidence_store
# ---------------------------------------------------------------------------

def build_evidence_store(serp, site_slug: str, output_dir: Path, post_id: int,
                         exclude_url: str = "") -> tuple[Path, dict]:
    """Build the evidence store JSON for one article.

    Args:
        serp: SerpData instance (from lib.serp_adapter).
        site_slug: Site identifier (e.g. "valn", "lrg").
        output_dir: Directory to write {post_id}-evidence.json.
        post_id: Post ID for filename.
        exclude_url: Canonical URL to exclude from competitor evidence
            (used on refresh to prevent scraping the page being refreshed).
            Empty string = no exclusion.

    Returns:
        (path, exclusion_info) — path to evidence JSON, and a dict with
        exclusion details (empty dict if no exclusion fired).

    Raises:
        RuntimeError: On unrecoverable errors (always with context message).
    """
    items: list[EvidenceItem] = []
    exclusion_info: dict = {}

    # Normalize exclude_url for comparison
    _exclude = exclude_url.rstrip("/").lower() if exclude_url else ""

    # --- 1. Competitor passages (top-5 organic results) ---
    if serp and hasattr(serp, "top_results"):
        for i, result in enumerate(serp.top_results[:5]):
            url = result.url
            title = result.title

            # Self-exclusion: skip the page being refreshed
            if _exclude and url.rstrip("/").lower() == _exclude:
                _eprint(f"  [evidence] EXCLUDED (self): position {i+1}: {url[:70]}")
                exclusion_info = {
                    "excluded_url": url,
                    "excluded_position": i + 1,
                    "excluded_title": title,
                }
                continue

            _eprint(f"  [evidence] Fetching result {i+1}/5: {url[:70]}")
            html = fetch_page(url)
            if html is None:
                _eprint(f"  [evidence] SKIP: could not fetch result {i+1}")
                continue

            passages = _extract_passages(html)
            for p in passages:
                items.append(EvidenceItem(
                    text=p,
                    kind="competitor_page",
                    source_url=url,
                    source_title=title,
                    serp_position=i + 1,
                ))
            _eprint(f"  [evidence]   {len(passages)} passages from position {i+1}")

    # --- 2. PAA pairs ---
    if serp and hasattr(serp, "paa_questions"):
        paa_questions = serp.paa_questions or []
        # SerpData stores questions as strings; some adapters also carry answers
        paa_answers = []
        if hasattr(serp, "paa_answers"):
            paa_answers = serp.paa_answers or []

        for j, q in enumerate(paa_questions):
            answer = paa_answers[j] if j < len(paa_answers) else ""
            text = f"Q: {q} A: {answer}" if answer else f"Q: {q}"
            items.append(EvidenceItem(text=text, kind="google_paa"))

    # --- 3. AI Overview blocks ---
    if serp and hasattr(serp, "ai_overview_text"):
        ai_text = serp.ai_overview_text
        if ai_text:
            # Split into blocks on double newlines or keep as one
            blocks = [b.strip() for b in re.split(r"\n{2,}", ai_text) if b.strip()]
            for block in blocks:
                items.append(EvidenceItem(text=block, kind="google_ai_overview"))

    # --- 4. Business facts ---
    facts_path = REPO_ROOT / "sites" / f"{site_slug}-business-facts.md"
    if facts_path.exists():
        fact_items = _parse_business_facts(facts_path)
        items.extend(fact_items)
        _eprint(f"  [evidence] {len(fact_items)} business facts loaded from {facts_path.name}")
    else:
        _eprint(f"  [evidence] No business-facts file for site '{site_slug}' (non-fatal)")

    # --- Deduplicate ---
    before = len(items)
    items = _deduplicate(items)
    if before > len(items):
        _eprint(f"  [evidence] Deduped: {before} -> {len(items)} items")

    # --- Cap at limits ---
    if len(items) > MAX_ITEMS:
        items = items[:MAX_ITEMS]
        _eprint(f"  [evidence] Capped at {MAX_ITEMS} items")

    # Serialize and check byte cap
    data = [asdict(item) for item in items]
    json_str = json.dumps(data, indent=2)
    if len(json_str.encode()) > MAX_BYTES:
        # Trim items until under budget
        while len(items) > 10 and len(json.dumps([asdict(i) for i in items]).encode()) > MAX_BYTES:
            items.pop()
        data = [asdict(item) for item in items]
        json_str = json.dumps(data, indent=2)
        _eprint(f"  [evidence] Trimmed to {len(items)} items to fit {MAX_BYTES} byte budget")

    # --- Write ---
    output_path = output_dir / f"{post_id}-evidence.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_str)
    _eprint(f"  [evidence] Store written: {output_path} ({len(items)} items, {len(json_str)} bytes)")

    if exclusion_info:
        _eprint(f"  [evidence] Self-exclusion: dropped {exclusion_info['excluded_url']} "
                f"(SERP position {exclusion_info['excluded_position']})")

    return output_path, exclusion_info


# ---------------------------------------------------------------------------
# Public API: select_evidence_for_section
# ---------------------------------------------------------------------------

def select_evidence_for_section(
    store_path: Path | str,
    section_title: str,
    target_keyword: str,
    max_items: int = 8,
    max_chars: int = 2500,
) -> list[dict]:
    """Select the best evidence items for a section.

    Args:
        store_path: Path to the evidence JSON file.
        section_title: H2 title (or FAQ question, or target keyword for BLUF).
        target_keyword: Article-level target keyword.
        max_items: Maximum items to return.
        max_chars: Maximum total characters of evidence text.

    Returns:
        List of evidence item dicts, sorted by relevance. Empty list on error.
    """
    store_path = Path(store_path)
    if not store_path.exists():
        return []

    try:
        items = json.loads(store_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    if not items:
        return []

    # Build query words
    query = f"{section_title} {target_keyword}".lower()
    query_words = set(re.findall(r"[a-z]+", query))

    # Score each item
    scored: list[tuple[float, int, dict]] = []
    for idx, item in enumerate(items):
        text_lower = item.get("text", "").lower()
        item_words = set(re.findall(r"[a-z]+", text_lower))
        overlap = len(query_words & item_words)

        # Base score from word overlap
        score = overlap

        # Boost confirmed business facts heavily
        if item.get("kind") == "business_facts" and item.get("tier") == "confirmed":
            score += 5
        # Boost PAA
        elif item.get("kind") == "google_paa":
            score += 2
        # Boost AI overview mildly
        elif item.get("kind") == "google_ai_overview":
            score += 1

        # Mild preference for lower SERP position (higher ranked pages)
        serp_pos = item.get("serp_position", -1)
        if serp_pos > 0:
            score += (6 - min(serp_pos, 5)) * 0.3  # 1.5 for pos 1, 0.3 for pos 5

        scored.append((score, idx, item))

    # Sort by score descending, then by original order for ties
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Select top items within char budget, deduplicating near-identical passages
    selected: list[dict] = []
    total_chars = 0
    selected_norms: list[str] = []

    for score, _, item in scored:
        if len(selected) >= max_items:
            break
        text = item.get("text", "")
        if total_chars + len(text) > max_chars:
            continue

        # Near-dedup against already-selected
        norm = _normalize_for_dedup(text)
        is_dup = False
        for prev in selected_norms:
            if difflib.SequenceMatcher(None, norm, prev).ratio() > 0.9:
                is_dup = True
                break
        if is_dup:
            continue

        selected.append(item)
        selected_norms.append(norm)
        total_chars += len(text)

    return selected


# ---------------------------------------------------------------------------
# Render evidence block for prompt injection
# ---------------------------------------------------------------------------

_EVIDENCE_RULES = """
**Evidence rules:**
- Ground specific factual assertions (numbers, percentages, timelines, dollar figures, named rules/programs/forms, thresholds) in the evidence above or in `[business_facts | CONFIRMED]` items. If the evidence does not support a specific figure, use directional or conditional language instead of inventing one.
- `[business_facts | VERIFY]` items get conditional phrasing: "check current...", "call for...", "verify with...".
- NEVER copy competitor passages verbatim or near-verbatim. Evidence is for factual grounding only. All prose must be original and in brand voice.
- Never mention or cite competitor URLs or brand names in the article body.
- Evidence informs; it does not dictate structure.
"""


def render_evidence_block(items: list[dict]) -> str:
    """Render selected evidence items into a full evidence section for prompt injection.

    Returns the complete section (header + items + rules) when items exist,
    or "" when empty. This makes the {{EVIDENCE_BLOCK}} placeholder fully
    conditional — no orphan headers or rules when no evidence is available.

    Format per item:
      [competitor_page | position 2 | example.com] <passage text>
      [google_paa] Q: ... A: ...
      [business_facts | CONFIRMED] <fact>
    """
    if not items:
        return ""

    lines = []
    for item in items:
        kind = item.get("kind", "unknown")
        text = item.get("text", "")

        if kind == "competitor_page":
            pos = item.get("serp_position", "?")
            # Extract domain from source_url
            source_url = item.get("source_url", "")
            try:
                from urllib.parse import urlparse
                domain = urlparse(source_url).netloc.lstrip("www.")
            except Exception:
                domain = source_url[:40]
            lines.append(f"[competitor_page | position {pos} | {domain}] {text}")
        elif kind == "google_paa":
            lines.append(f"[google_paa] {text}")
        elif kind == "google_ai_overview":
            lines.append(f"[google_ai_overview] {text}")
        elif kind == "business_facts":
            tier = item.get("tier", "").upper()
            lines.append(f"[business_facts | {tier}] {text}")
        else:
            lines.append(f"[{kind}] {text}")

    items_text = "\n".join(lines)
    return f"## EVIDENCE (source material for factual grounding)\n\n{items_text}\n{_EVIDENCE_RULES}"
