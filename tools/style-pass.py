#!/usr/bin/env python3
"""style-pass — tiered AI-pattern cleanup for existing corpora.

Tier 1 (auto-fix, diff-gated): em dashes, excess semicolons.
  - Extracts sentences with target punctuation + HTML context.
  - Batches through gpt-5.4-mini: rewrite sentence replacing the
    dash/semicolon (split to two sentences, comma, or parens).
  - DIFF GATE: reject any rewrite that touched facts, links, or
    other text beyond the punctuation region.
  - Restricted zones: never touch JSON-LD, shortcodes, code blocks,
    or anchor text without flagging.

Tier 2 (detect + report only): AI-lexicon hits, "not X it's Y"
  constructions, prose rule-of-three triplets, bold-phrase density.
  Outputs per-page CSV sortable by total score.

Tier 3: not in this tool. Rhythm/specificity are rewrite-queue concerns.

Usage:
    python3 style-pass.py --site valn --tier 1 [--execute] [--staging]
    python3 style-pass.py --site valn --tier 2 --output report.csv
    python3 style-pass.py --site valn --tier 1 --tier 2 [--staging]

    Default is dry-run. --execute requires deploy_lock + full discipline.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))

from lib.site_config import load_site_config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EM_DASH = "\u2014"  # —
SEMICOLON = ";"

# Restricted zones: never rewrite inside these
RESTRICTED_ZONE_RES = [
    re.compile(r"<script[^>]*>.*?</script>", re.S | re.I),
    re.compile(r"<style[^>]*>.*?</style>", re.S | re.I),
    re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>.*?</script>', re.S | re.I),
    re.compile(r"\[et_pb_\w+[^\]]*\]", re.S),   # Divi shortcodes
    re.compile(r"\[/et_pb_\w+\]", re.S),
    re.compile(r"\[wpcode[^\]]*\]", re.S),
    re.compile(r"<code[^>]*>.*?</code>", re.S | re.I),
    re.compile(r"<pre[^>]*>.*?</pre>", re.S | re.I),
]

# Tier 2 AI-lexicon
TIER2_LEXICON = [
    "delve", "navigate", "leverage", "robust", "comprehensive",
    "crucial", "essential", "seamless", "holistic",
]

TIER2_PHRASE_PATTERNS = [
    re.compile(r"in today'?s\s+\w+\s+landscape", re.I),
    re.compile(r"it'?s important to note", re.I),
    re.compile(r"when it comes to\b", re.I),
]

# "It's not X, it's Y" pattern
NOT_X_ITS_Y_RE = re.compile(
    r"(?:it'?s|that'?s)\s+not\s+\w[\w\s,]{2,40}[,;]\s*(?:it'?s|that'?s)\s+\w",
    re.I,
)

# Rule-of-three: three comma-separated adjectives/nouns before a noun
RULE_OF_THREE_RE = re.compile(
    r"\b(\w+),\s+(\w+),\s+and\s+(\w+)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SentenceMatch:
    """A sentence containing a target pattern, with context for reinsertion."""
    post_id: int
    sentence: str
    char_offset: int          # offset within post_content
    context_before: str       # ~40 chars before for reinsertion safety
    context_after: str        # ~40 chars after
    in_anchor: bool           # inside <a> tag — flag, don't fix
    in_restricted: bool       # inside restricted zone — skip entirely
    pattern_type: str         # "em_dash" or "semicolon"


@dataclass
class RewriteResult:
    """Result of an LLM rewrite attempt."""
    original: str
    rewritten: str
    accepted: bool
    rejection_reason: str | None


@dataclass
class Tier2Hit:
    """A single Tier 2 detection."""
    category: str
    match_text: str
    context: str  # surrounding sentence


@dataclass
class PostReport:
    """Per-post results for logging and CSV."""
    post_id: int
    url: str
    tier1_fixes: int = 0
    tier1_rejections: int = 0
    tier1_anchor_flags: int = 0
    tier2_lexicon_hits: int = 0
    tier2_phrase_hits: int = 0
    tier2_not_x_its_y: int = 0
    tier2_triple_hits: int = 0
    tier2_bold_density: float = 0.0
    tier2_total: int = 0
    sentences_fixed: list = field(default_factory=list)
    sentences_rejected: list = field(default_factory=list)
    sentences_flagged: list = field(default_factory=list)
    tier2_details: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Zone detection
# ---------------------------------------------------------------------------

def _build_restricted_spans(html: str) -> list[tuple[int, int]]:
    """Find all character spans in html that are restricted zones."""
    spans = []
    for pattern in RESTRICTED_ZONE_RES:
        for m in pattern.finditer(html):
            spans.append((m.start(), m.end()))
    return sorted(spans)


def _in_restricted_zone(offset: int, length: int, spans: list[tuple[int, int]]) -> bool:
    """Check if a character range overlaps any restricted span."""
    end = offset + length
    for s, e in spans:
        if offset < e and end > s:
            return True
    return False


def _in_anchor_tag(html: str, offset: int) -> bool:
    """Check if offset falls inside an <a ...>...</a> tag."""
    # Find the nearest preceding <a or </a
    before = html[:offset]
    last_open = before.rfind("<a ")
    if last_open == -1:
        last_open = before.rfind("<a\t")
    if last_open == -1:
        last_open = before.rfind("<a\n")
    last_close = before.rfind("</a>")
    if last_open == -1:
        return False
    if last_close == -1 or last_open > last_close:
        # We're after an <a> open but before its close
        return True
    return False


# ---------------------------------------------------------------------------
# Sentence extraction (BeautifulSoup text-node approach)
# ---------------------------------------------------------------------------

def _extract_sentences_with_pattern(
    post_id: int,
    html: str,
    pattern_char: str,
    pattern_type: str,
    restricted_spans: list[tuple[int, int]],
) -> list[SentenceMatch]:
    """Find prose sentences containing the target character via text nodes.

    Uses BeautifulSoup to walk text nodes. Skips restricted elements
    (script, style, code, pre) and Divi shortcodes. For each text node
    containing the pattern char, extracts the sentence around it using
    sentence-boundary heuristics on the plain text.
    """
    from bs4 import BeautifulSoup as BS, NavigableString

    soup = BS(html, "html.parser")
    matches = []

    SKIP_TAGS = {"script", "style", "code", "pre", "noscript"}

    for text_node in soup.descendants:
        if not isinstance(text_node, NavigableString):
            continue

        text = str(text_node)
        if pattern_char not in text:
            continue

        # Skip restricted parent elements
        parent = text_node.parent
        if parent is None:
            continue
        if parent.name in SKIP_TAGS:
            continue

        # Skip if inside a Divi shortcode text (contains [et_pb_)
        if "[et_pb_" in text or "[/et_pb_" in text:
            continue

        # Detect if inside <a> tag
        in_anchor = False
        p = parent
        while p:
            if getattr(p, "name", None) == "a":
                in_anchor = True
                break
            p = getattr(p, "parent", None)

        # Split text node into sentences and find those with the pattern
        # Use regex sentence splitter that preserves boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sentence in sentences:
            if pattern_char not in sentence:
                continue

            sentence = sentence.strip()
            if len(sentence) < 5:
                continue

            # Skip sentences that are mostly HTML-like (shortcodes, attributes)
            if sentence.count("=") > 2 or sentence.count('"') > 4:
                continue

            matches.append(SentenceMatch(
                post_id=post_id,
                sentence=sentence,
                char_offset=0,  # not used for replacement
                context_before="",
                context_after="",
                in_anchor=in_anchor,
                in_restricted=False,
                pattern_type=pattern_type,
            ))

    # Deduplicate by sentence text
    seen = set()
    deduped = []
    for sm in matches:
        key = (sm.post_id, sm.sentence)
        if key not in seen:
            seen.add(key)
            deduped.append(sm)

    return deduped


# ---------------------------------------------------------------------------
# Diff gate
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple word-level tokenizer preserving HTML tags as single tokens."""
    return re.findall(r'<[^>]+>|[^\s<]+', text)


def _strip_punct(token: str) -> str:
    """Strip trailing/leading punctuation from a token for comparison."""
    return token.strip(".,;:!?()\"'\u2014\u2013-")


def _diff_gate(original: str, rewritten: str, pattern_char: str) -> tuple[bool, str | None]:
    """Verify rewrite only changed the punctuation region.

    Returns (accepted, rejection_reason).
    Compares word stems (stripped of punctuation) so that token boundary
    shifts caused by dash→comma don't false-reject.
    """
    if original == rewritten:
        return False, "no_change"

    # The rewrite must not contain the target pattern anymore
    if pattern_char in rewritten:
        return False, "pattern_still_present"

    # Normalize: strip the pattern char, compare word-level content
    # Extract only word tokens (ignore punctuation tokens entirely)
    def _words(text: str) -> list[str]:
        """Extract lowercase word tokens, ignoring punctuation-only tokens."""
        tokens = re.findall(r'<[^>]+>|[^\s<]+', text)
        return [_strip_punct(t).lower() for t in tokens
                if _strip_punct(t) and not t.startswith("<")]

    def _tags(text: str) -> list[str]:
        """Extract HTML tags."""
        return re.findall(r'<[^>]+>', text)

    orig_words = _words(original)
    new_words = _words(rewritten)

    # Verify no HTML tags changed (links, structure)
    if _tags(original) != _tags(rewritten):
        return False, "html_tags_changed"

    # Verify numbers didn't change (strip trailing punctuation from numbers
    # since dash→comma rewrites can attach a comma to the preceding number)
    def _clean_nums(text: str) -> list[str]:
        raw = re.findall(r'\d[\d,.]*%?', text)
        return [n.rstrip(".,;") for n in raw]

    if _clean_nums(original) != _clean_nums(rewritten):
        return False, f"numbers_changed: {_clean_nums(original)} -> {_clean_nums(rewritten)}"

    # Compare words: allow removal of the pattern char and addition of
    # limited connective words
    import difflib
    connectives = {"and", "but", "so", "which", "that", "while", "whereas",
                   "because", "since", "although", "though", "however",
                   "instead", "rather", "or", "yet", "then"}

    sm = difflib.SequenceMatcher(None, orig_words, new_words)
    removed_words = []
    added_words = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        removed_words.extend(orig_words[i1:i2])
        added_words.extend(new_words[j1:j2])

    # Filter: ignore pattern char artifacts from word extraction
    removed_meaningful = [w for w in removed_words if w and w != pattern_char]
    added_non_connective = [w for w in added_words
                            if w and w not in connectives]

    if removed_meaningful:
        return False, f"removed_content: {removed_meaningful[:3]}"

    if len(added_non_connective) > 2:
        return False, f"added_too_much: {added_non_connective[:5]}"

    return True, None


# ---------------------------------------------------------------------------
# LLM rewrite
# ---------------------------------------------------------------------------

def _call_rewrite_llm(sentences: list[str], pattern_type: str) -> list[str]:
    """Call gpt-5.4-mini to rewrite sentences, removing target punctuation.

    Sends a batch of sentences and gets rewrites back.
    """
    if not sentences:
        return []

    if pattern_type == "em_dash":
        target_name = "em dash (\u2014)"
        instruction = (
            "Replace each em dash with a period (splitting into two sentences), "
            "a comma, or parentheses \u2014 whichever reads most naturally."
        )
    else:
        target_name = "semicolon"
        instruction = (
            "Replace each semicolon with a period (splitting into two sentences) "
            "or restructure as a comma splice fix. Whichever reads most naturally."
        )

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))

    prompt = f"""Rewrite each numbered sentence below to remove every {target_name}.
{instruction}

RULES:
- Change ONLY the punctuation region. Do NOT alter facts, numbers, names, percentages, HTML tags, or links.
- Preserve all <strong>, <a>, <li>, and other HTML markup exactly.
- Do not add words beyond minimal connectives (and, but, so).
- Do not change capitalization except where a new sentence begins after a period.
- Output ONLY the rewritten sentences, one per line, numbered to match.

SENTENCES:
{numbered}"""

    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": "You are a precise copy editor. You only fix punctuation. You never change facts, numbers, or meaning."},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=4096,
        temperature=0.3,
    )
    text = resp.choices[0].message.content or ""

    # Parse numbered responses
    results = []
    for line in text.strip().split("\n"):
        line = line.strip()
        # Strip leading number and period/parenthesis
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
        if cleaned:
            results.append(cleaned)

    # Pad if we got fewer results than expected
    while len(results) < len(sentences):
        results.append(sentences[len(results)])

    return results


# ---------------------------------------------------------------------------
# Tier 1: em dash + semicolon fix
# ---------------------------------------------------------------------------

def tier1_process_post(
    post_id: int,
    url: str,
    html: str,
    execute: bool = False,
    pattern_types: list[str] | None = None,
) -> tuple[str, PostReport]:
    """Run Tier 1 on a single post's HTML.

    Returns (modified_html, report).
    """
    if pattern_types is None:
        pattern_types = ["em_dash", "semicolon"]

    report = PostReport(post_id=post_id, url=url)
    restricted_spans = _build_restricted_spans(html)
    all_matches: list[SentenceMatch] = []

    for pt in pattern_types:
        char = EM_DASH if pt == "em_dash" else SEMICOLON
        matches = _extract_sentences_with_pattern(
            post_id, html, char, pt, restricted_spans
        )
        all_matches.extend(matches)

    if not all_matches:
        return html, report

    # Separate anchor-flagged from fixable
    fixable = [m for m in all_matches if not m.in_anchor]
    anchor_flagged = [m for m in all_matches if m.in_anchor]

    report.tier1_anchor_flags = len(anchor_flagged)
    for af in anchor_flagged:
        report.sentences_flagged.append({
            "sentence": af.sentence,
            "reason": "in_anchor_text",
            "pattern": af.pattern_type,
        })

    if not fixable:
        return html, report

    # Batch through LLM (groups of 20)
    BATCH_SIZE = 20
    modified_html = html
    replacements_made = 0

    for batch_start in range(0, len(fixable), BATCH_SIZE):
        batch = fixable[batch_start:batch_start + BATCH_SIZE]
        originals = [m.sentence for m in batch]

        try:
            rewrites = _call_rewrite_llm(originals, batch[0].pattern_type)
        except Exception as e:
            eprint(f"  LLM call failed for post {post_id}: {e}")
            for m in batch:
                report.sentences_rejected.append({
                    "original": m.sentence,
                    "rewritten": "",
                    "reason": f"llm_error: {e}",
                })
                report.tier1_rejections += 1
            continue

        for match, original, rewritten in zip(batch, originals, rewrites):
            pattern_char = EM_DASH if match.pattern_type == "em_dash" else SEMICOLON
            accepted, reason = _diff_gate(original, rewritten, pattern_char)

            if accepted:
                report.sentences_fixed.append({
                    "original": original,
                    "rewritten": rewritten,
                })
                report.tier1_fixes += 1

                if execute:
                    # Safe replacement: use the original sentence as-is for
                    # string replacement. Only replace first occurrence to avoid
                    # double-replacing if same sentence appears twice.
                    modified_html = modified_html.replace(original, rewritten, 1)
                    replacements_made += 1
            else:
                report.sentences_rejected.append({
                    "original": original,
                    "rewritten": rewritten,
                    "reason": reason,
                })
                report.tier1_rejections += 1

        # Rate limit between batches
        if batch_start + BATCH_SIZE < len(fixable):
            time.sleep(10)

    return modified_html, report


# ---------------------------------------------------------------------------
# Tier 2: detect + report
# ---------------------------------------------------------------------------

def tier2_scan_post(
    post_id: int,
    url: str,
    html: str,
) -> PostReport:
    """Run Tier 2 detection on a single post. No modifications."""
    from bs4 import BeautifulSoup

    report = PostReport(post_id=post_id, url=url)
    soup = BeautifulSoup(html, "html.parser")

    # Strip restricted zones for text analysis
    for tag in soup.find_all(["script", "style", "code", "pre"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text_lower = text.lower()

    # Lexicon hits
    for word in TIER2_LEXICON:
        count = len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
        if count > 0:
            report.tier2_lexicon_hits += count
            # Find context
            for m in re.finditer(r'\b' + re.escape(word) + r'\b', text_lower):
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                report.tier2_details.append(Tier2Hit(
                    category="lexicon",
                    match_text=word,
                    context=text[start:end],
                ))

    # Phrase patterns
    for pat in TIER2_PHRASE_PATTERNS:
        for m in pat.finditer(text):
            report.tier2_phrase_hits += 1
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            report.tier2_details.append(Tier2Hit(
                category="phrase",
                match_text=m.group(),
                context=text[start:end],
            ))

    # "It's not X, it's Y"
    for m in NOT_X_ITS_Y_RE.finditer(text):
        report.tier2_not_x_its_y += 1
        start = max(0, m.start() - 20)
        end = min(len(text), m.end() + 20)
        report.tier2_details.append(Tier2Hit(
            category="not_x_its_y",
            match_text=m.group(),
            context=text[start:end],
        ))

    # Rule-of-three triplets
    for m in RULE_OF_THREE_RE.finditer(text):
        report.tier2_triple_hits += 1
        report.tier2_details.append(Tier2Hit(
            category="triple",
            match_text=m.group(),
            context=text[max(0, m.start()-20):min(len(text), m.end()+20)],
        ))

    # Bold-phrase density
    bold_tags = soup.find_all("strong")
    bold_word_count = sum(len(t.get_text().split()) for t in bold_tags)
    total_words = len(text.split())
    if total_words > 0:
        report.tier2_bold_density = round(bold_word_count / total_words, 3)

    report.tier2_total = (
        report.tier2_lexicon_hits
        + report.tier2_phrase_hits
        + report.tier2_not_x_its_y
        + report.tier2_triple_hits
    )

    return report


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def _ssh_cmd(site_config: dict, staging: bool = False) -> list[str]:
    """Build SSH command prefix."""
    if staging:
        user = site_config.get("STAGING_SSH_USER", "")
        key = os.path.expanduser(site_config.get("STAGING_SSH_KEY", ""))
        host = site_config.get("SSH_HOST", "")
    else:
        user = site_config.get("SSH_USER", "")
        key = os.path.expanduser(site_config.get("SSH_KEY_PATH", "").rstrip("'").lstrip("'"))
        host = site_config.get("SSH_HOST", "")

    return ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
            "-o", "IdentitiesOnly=yes", f"{user}@{host}"]


def _wp_path(site_config: dict, staging: bool = False) -> str:
    """Get WP install path."""
    if staging:
        return site_config.get("STAGING_WP_PATH", "")
    return site_config.get("WP_PATH", "")


def _ssh_run(ssh_cmd: list[str], remote_cmd: str, timeout: int = 60) -> str:
    """Run a command over SSH and return stdout."""
    result = subprocess.run(
        ssh_cmd + [remote_cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SSH command failed: {result.stderr[:500]}")
    return result.stdout


def _preflight_check(ssh_cmd: list[str], wp_path: str, staging: bool) -> bool:
    """Verify site URL matches expected environment."""
    siteurl = _ssh_run(ssh_cmd, f"wp option get siteurl --path={wp_path}").strip()
    eprint(f"  Preflight: siteurl = {siteurl}")

    if staging:
        if "wpenginepowered.com" not in siteurl and "staging" not in siteurl.lower():
            eprint(f"  ABORT: siteurl '{siteurl}' does not look like staging!")
            return False
    return True


def _get_posts_with_pattern(
    ssh_cmd: list[str],
    wp_path: str,
    pattern_char: str,
    protected_slugs: list[str],
) -> list[dict]:
    """Query WP for posts containing the pattern character."""
    # Use wp eval to find posts with em dashes
    # Use wp db query with UNHEX for reliable em dash matching
    if pattern_char == EM_DASH:
        # Em dash is UTF-8 bytes E2 80 94. Use LOCATE with UNHEX for exact match.
        php = """<?php
global $wpdb;
$emdash = "\\xe2\\x80\\x94";
$results = $wpdb->get_results(
    $wpdb->prepare(
        "SELECT ID, post_name, post_title FROM {$wpdb->posts}
         WHERE post_status = 'publish'
         AND (post_type = 'post' OR post_type = 'page')
         AND LOCATE(%s, post_content) > 0
         ORDER BY ID ASC",
        $emdash
    ),
    ARRAY_A
);
foreach ($results as $r) {
    echo $r['ID'] . "\\t" . $r['post_name'] . "\\t" . $r['post_title'] . "\\n";
}
"""
    else:
        # Semicolons are common in HTML entities — filter more carefully
        # We'll detect in Python after fetching content
        php = """<?php
global $wpdb;
$results = $wpdb->get_results(
    "SELECT ID, post_name, post_title FROM {$wpdb->posts}
     WHERE post_status = 'publish'
     AND (post_type = 'post' OR post_type = 'page')
     ORDER BY ID ASC",
    ARRAY_A
);
foreach ($results as $r) {
    echo $r['ID'] . "\\t" . $r['post_name'] . "\\t" . $r['post_title'] . "\\n";
}
"""

    result = subprocess.run(
        ssh_cmd + [f"cat > /tmp/_sp_query.php && wp eval-file /tmp/_sp_query.php --path={wp_path}"],
        input=php, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Post query failed: {result.stderr[:500]}")

    posts = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        slug = parts[1]
        if slug in protected_slugs:
            continue
        posts.append({
            "ID": int(parts[0]),
            "post_name": slug,
            "post_title": parts[2] if len(parts) > 2 else "",
        })

    return posts


# ---------------------------------------------------------------------------
# Protected slugs
# ---------------------------------------------------------------------------

def _load_protected_slugs(site_slug: str) -> list[str]:
    """Load protected page slugs from valn-reference.md or config."""
    # Hardcoded from valn-reference.md Protected Pages section
    protected = [
        "va-funding-fee", "va-loan-hub", "complex-va-loan-center",
        "legal", "advertising-disclosures", "va-loan-network-editorial-team",
        "privacy-policy", "terms", "disclaimer", "compare-loan-offers",
        "home", "contact-us", "confirmation",
    ]

    # Try to load from config
    config_path = REPO_ROOT / "sites" / f"{site_slug}-reference.md"
    if config_path.exists():
        text = config_path.read_text()
        # Extract slugs from protected pages section
        in_protected = False
        for line in text.split("\n"):
            if "Protected Pages" in line:
                in_protected = True
                continue
            if in_protected and line.startswith("#"):
                break
            if in_protected:
                for slug_match in re.finditer(r'/([a-z0-9-]+)/', line):
                    slug = slug_match.group(1)
                    if slug not in protected:
                        protected.append(slug)

    return protected


# ---------------------------------------------------------------------------
# Deploy lock
# ---------------------------------------------------------------------------

def _acquire_lock(site_slug: str, script_name: str) -> Path:
    """Acquire a deploy lock. Abort if already held."""
    lock_dir = Path.home() / "locks"
    lock_dir.mkdir(exist_ok=True)
    lock_file = lock_dir / f"{script_name}-{site_slug}.lock"

    if lock_file.exists():
        lock_content = lock_file.read_text().strip()
        # Check if PID is alive
        try:
            pid = int(lock_content.split("\n")[0].split("=")[1])
            os.kill(pid, 0)
            raise RuntimeError(
                f"Lock held by PID {pid}: {lock_file}\n"
                f"Content: {lock_content}"
            )
        except (ValueError, ProcessLookupError, IndexError):
            eprint(f"  Removing stale lock: {lock_file}")
            lock_file.unlink()

    lock_file.write_text(
        f"PID={os.getpid()}\n"
        f"TIME={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"SCRIPT={script_name}\n"
    )
    return lock_file


def _release_lock(lock_file: Path):
    """Release deploy lock."""
    if lock_file.exists():
        lock_file.unlink()


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="style-pass: tiered AI-pattern cleanup for existing corpora",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tiers:
  1  Auto-fix (diff-gated): em dashes, excess semicolons.
     Default dry-run. --execute writes changes with deploy discipline.
  2  Detect + report: AI-lexicon, phrase patterns, bold density.
     Outputs CSV. Never modifies content.
  3  Not in this tool. Rhythm/specificity are rewrite-queue concerns.
        """,
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., valn)")
    parser.add_argument("--tier", type=int, action="append", required=True,
                        choices=[1, 2], help="Tier(s) to run (can specify multiple)")
    parser.add_argument("--staging", action="store_true",
                        help="Run on staging environment (required for first runs)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually write changes (Tier 1 only). Default is dry-run.")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path for Tier 2 report")
    parser.add_argument("--post-ids", type=str, default=None,
                        help="Comma-separated post IDs to process (default: all)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max posts to process")
    parser.add_argument("--backup-dir", type=str, default=None,
                        help="Local backup directory (default: ~/backups/style-pass/)")
    parser.add_argument("--production-confirmed", action="store_true",
                        help="Allow --execute on production (for sites without staging)")

    args = parser.parse_args()

    # Load site config
    try:
        site_config = load_site_config(args.site)
    except FileNotFoundError as e:
        eprint(f"ERROR: {e}")
        sys.exit(1)

    # Build SSH command
    ssh_cmd = _ssh_cmd(site_config, args.staging)
    wp_path = _wp_path(site_config, args.staging)

    if not wp_path:
        eprint("ERROR: No WP path configured for this environment")
        sys.exit(1)

    # Preflight
    eprint(f"style-pass v1.0 | site={args.site} | tiers={args.tier} | "
           f"{'staging' if args.staging else 'PRODUCTION'} | "
           f"{'EXECUTE' if args.execute else 'dry-run'}")

    if not _preflight_check(ssh_cmd, wp_path, args.staging):
        sys.exit(1)

    # Protected slugs
    protected = _load_protected_slugs(args.site)
    eprint(f"  Protected slugs ({len(protected)}): {protected[:5]}...")

    # Execute mode requires lock
    lock_file = None
    if args.execute:
        if not args.staging and not args.production_confirmed:
            eprint("ERROR: --execute on production requires --production-confirmed flag.")
            eprint("       Use --staging for staging environments, or")
            eprint("       --production-confirmed for sites without staging.")
            sys.exit(1)
        lock_file = _acquire_lock(args.site, "style-pass")
        eprint(f"  Deploy lock acquired: {lock_file}")

    try:
        # Get posts to process
        if args.post_ids:
            post_ids = [int(x) for x in args.post_ids.split(",")]
            # Fetch post info for these IDs
            posts = []
            for pid in post_ids:
                slug = _ssh_run(ssh_cmd,
                    f"wp post get {pid} --field=post_name --path={wp_path}").strip()
                title = _ssh_run(ssh_cmd,
                    f"wp post get {pid} --field=post_title --path={wp_path}").strip()
                if slug not in protected:
                    posts.append({"ID": pid, "post_name": slug, "post_title": title})
                else:
                    eprint(f"  Skipping protected post {pid} ({slug})")
        else:
            eprint("  Querying posts with em dashes...")
            posts = _get_posts_with_pattern(ssh_cmd, wp_path, EM_DASH, protected)

        eprint(f"  Found {len(posts)} posts to process")

        if args.limit:
            posts = posts[:args.limit]
            eprint(f"  Limited to {len(posts)} posts")

        # Backup dir
        backup_dir = Path(args.backup_dir) if args.backup_dir else Path.home() / "backups" / "style-pass"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Process posts
        all_reports: list[PostReport] = []
        domain = site_config.get("SITE_DOMAIN", "example.com")

        for i, post in enumerate(posts):
            pid = post["ID"]
            slug = post["post_name"]
            url = f"https://{domain}/{slug}/"
            eprint(f"\n  [{i+1}/{len(posts)}] Post {pid}: {slug}")

            # Fetch content via wp post get (safe method)
            try:
                html = _ssh_run(
                    ssh_cmd,
                    f"wp post get {pid} --field=post_content --path={wp_path}",
                    timeout=30,
                )
            except Exception as e:
                eprint(f"    Failed to fetch content: {e}")
                continue

            if not html.strip():
                eprint(f"    Empty content, skipping")
                continue

            # Backup
            backup_path = backup_dir / f"post-{pid}-{slug[:50]}.html"
            backup_path.write_text(html)
            if backup_path.stat().st_size == 0:
                eprint(f"    ABORT: Backup is zero bytes!")
                continue

            report = PostReport(post_id=pid, url=url)

            # Tier 1
            if 1 in args.tier:
                modified_html, t1_report = tier1_process_post(
                    pid, url, html, execute=args.execute,
                )
                report.tier1_fixes = t1_report.tier1_fixes
                report.tier1_rejections = t1_report.tier1_rejections
                report.tier1_anchor_flags = t1_report.tier1_anchor_flags
                report.sentences_fixed = t1_report.sentences_fixed
                report.sentences_rejected = t1_report.sentences_rejected
                report.sentences_flagged = t1_report.sentences_flagged

                if args.execute and modified_html != html:
                    eprint(f"    Writing {report.tier1_fixes} fixes...")
                    # Write back via wp eval-file
                    _write_post_content(ssh_cmd, wp_path, pid, modified_html)
                    eprint(f"    Written.")
                    time.sleep(5)  # deploy pacing

                eprint(f"    Tier 1: {report.tier1_fixes} fixes, "
                       f"{report.tier1_rejections} rejected, "
                       f"{report.tier1_anchor_flags} anchor-flagged")

            # Tier 2
            if 2 in args.tier:
                t2_report = tier2_scan_post(pid, url, html)
                report.tier2_lexicon_hits = t2_report.tier2_lexicon_hits
                report.tier2_phrase_hits = t2_report.tier2_phrase_hits
                report.tier2_not_x_its_y = t2_report.tier2_not_x_its_y
                report.tier2_triple_hits = t2_report.tier2_triple_hits
                report.tier2_bold_density = t2_report.tier2_bold_density
                report.tier2_total = t2_report.tier2_total
                report.tier2_details = t2_report.tier2_details

                eprint(f"    Tier 2: {report.tier2_total} hits "
                       f"(lex={report.tier2_lexicon_hits}, "
                       f"phrase={report.tier2_phrase_hits}, "
                       f"not-x={report.tier2_not_x_its_y}, "
                       f"triple={report.tier2_triple_hits}, "
                       f"bold={report.tier2_bold_density:.1%})")

            all_reports.append(report)

            # SSH session pacing
            if (i + 1) % 25 == 0:
                eprint(f"  Flushing WP cache after batch of 25...")
                _ssh_run(ssh_cmd, f"wp cache flush --path={wp_path}")
                time.sleep(5)

        # Summary
        eprint(f"\n{'='*60}")
        eprint(f"SUMMARY: {len(all_reports)} posts processed")

        if 1 in args.tier:
            total_fixes = sum(r.tier1_fixes for r in all_reports)
            total_rejections = sum(r.tier1_rejections for r in all_reports)
            total_flags = sum(r.tier1_anchor_flags for r in all_reports)
            eprint(f"  Tier 1: {total_fixes} fixes, {total_rejections} rejected, "
                   f"{total_flags} anchor-flagged")

        if 2 in args.tier:
            total_t2 = sum(r.tier2_total for r in all_reports)
            eprint(f"  Tier 2: {total_t2} total hits")

        # Write Tier 2 CSV
        if 2 in args.tier:
            csv_path = args.output or f"style-pass-tier2-{args.site}.csv"
            _write_tier2_csv(all_reports, csv_path)
            eprint(f"  Tier 2 CSV: {csv_path}")

        # Write rejection log
        if 1 in args.tier:
            _print_rejection_log(all_reports)

        # Print sample before/after pairs
        if 1 in args.tier:
            _print_sample_pairs(all_reports, count=30)

    finally:
        if lock_file:
            _release_lock(lock_file)
            eprint(f"  Deploy lock released")


# ---------------------------------------------------------------------------
# Write helper
# ---------------------------------------------------------------------------

def _write_post_content(ssh_cmd: list[str], wp_path: str, post_id: int, html: str):
    """Write post content back via wp eval-file (safe method).

    Uses single SSH session: pipes PHP script that contains hex-encoded
    content, writes to /tmp, and executes — all in one session so WPE's
    session-local /tmp works correctly.
    """
    # Hex-encode content so it survives shell transport without corruption
    hex_content = html.encode("utf-8").hex()

    php = f"""<?php
$hex = '{hex_content}';
$content = hex2bin($hex);
if (empty($content)) {{
    echo "ERROR: empty content after hex2bin\\n";
    exit(1);
}}
$result = wp_update_post(array(
    'ID' => {post_id},
    'post_content' => $content,
), true);
if (is_wp_error($result)) {{
    echo "ERROR: " . $result->get_error_message() . "\\n";
    exit(1);
}}
echo "OK: updated post {post_id}, " . strlen($content) . " bytes\\n";
"""

    # Single SSH session: pipe PHP to /tmp and execute
    result = subprocess.run(
        ssh_cmd + [f"cat > /tmp/_sp_update.php && wp eval-file /tmp/_sp_update.php --path={wp_path}"],
        input=php, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0 or "ERROR" in result.stdout:
        raise RuntimeError(f"Write failed: {result.stdout} {result.stderr[:300]}")

    eprint(f"    {result.stdout.strip()}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_tier2_csv(reports: list[PostReport], path: str):
    """Write Tier 2 results to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "post_id", "url", "lexicon_hits", "phrase_hits",
            "not_x_its_y", "triple_hits", "bold_density", "total_score",
        ])
        # Sort by total descending
        sorted_reports = sorted(reports, key=lambda r: r.tier2_total, reverse=True)
        for r in sorted_reports:
            writer.writerow([
                r.post_id, r.url, r.tier2_lexicon_hits, r.tier2_phrase_hits,
                r.tier2_not_x_its_y, r.tier2_triple_hits,
                f"{r.tier2_bold_density:.3f}", r.tier2_total,
            ])


def _print_rejection_log(reports: list[PostReport]):
    """Print all diff-gate rejected sentences."""
    rejections = []
    for r in reports:
        for rej in r.sentences_rejected:
            rejections.append((r.post_id, r.url, rej))

    if not rejections:
        eprint("\n  No diff-gate rejections.")
        return

    eprint(f"\n{'='*60}")
    eprint(f"DIFF-GATE REJECTIONS ({len(rejections)} total):")
    eprint(f"{'='*60}")
    for pid, url, rej in rejections:
        eprint(f"\n  Post {pid} ({url}):")
        eprint(f"    Original:  {rej['original'][:120]}")
        eprint(f"    Rewritten: {rej.get('rewritten', '')[:120]}")
        eprint(f"    Reason:    {rej['reason']}")


def _print_sample_pairs(reports: list[PostReport], count: int = 30):
    """Print random before/after sentence pairs."""
    import random

    all_pairs = []
    for r in reports:
        for fix in r.sentences_fixed:
            all_pairs.append((r.post_id, r.url, fix))

    if not all_pairs:
        eprint("\n  No fixes to sample.")
        return

    sample = random.sample(all_pairs, min(count, len(all_pairs)))

    eprint(f"\n{'='*60}")
    eprint(f"SAMPLE BEFORE/AFTER PAIRS ({len(sample)} of {len(all_pairs)}):")
    eprint(f"{'='*60}")
    for i, (pid, url, fix) in enumerate(sample, 1):
        eprint(f"\n  [{i}] Post {pid}")
        eprint(f"    BEFORE: {fix['original']}")
        eprint(f"    AFTER:  {fix['rewritten']}")


if __name__ == "__main__":
    main()
