"""Shared internal-linking primitives for pool-mode and corpus-mode linkers.

All site-specific values (CSS prefix, skip slugs, zone suffixes) are passed
via config dicts — nothing is hardcoded to a particular site.

Dependencies:
  - beautifulsoup4  (HTML parsing)
  - nltk            (POS tagging for corpus candidate quality gating)
    Data: averaged_perceptron_tagger_eng (auto-downloaded on first use)

Used by:
  - tools/inject-internal-links.py  (pipeline pool-mode linker)
  - tools/link-injector.py          (unified pool+corpus linker)
  - tests/test_linker.py            (regression harness)
"""

import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag


# ───────────────────────────────────────────────────────────────────────────
# 1. Text-node-safe link injection
# ───────────────────────────────────────────────────────────────────────────

_SKIP_PARENT_TAGS = frozenset({
    "a", "h1", "h2", "h3", "h4", "h5", "h6",
    "script", "style", "code", "pre",
})


def inject_link_in_paragraph(para: Tag, anchor_text: str, url: str) -> bool:
    """Inject a link by replacing the first matching text node in a paragraph.

    Walks NavigableString descendants of *para*. Only matches in visible text
    nodes that are NOT inside existing <a> tags, headings, or code/script blocks.
    Uses word-boundary regex, case-insensitive, preserving original case.

    Returns True if a link was injected.
    """
    pattern = re.compile(r"\b" + re.escape(anchor_text) + r"\b", re.IGNORECASE)

    for text_node in list(para.descendants):
        if not isinstance(text_node, NavigableString):
            continue

        if any(
            isinstance(p, Tag) and p.name in _SKIP_PARENT_TAGS
            for p in text_node.parents
        ):
            continue

        text = str(text_node)
        m = pattern.search(text)
        if not m:
            continue

        before = text[: m.start()]
        matched = text[m.start() : m.end()]
        after = text[m.end() :]

        parent_tag = text_node.parent
        node_idx = next(i for i, c in enumerate(parent_tag.contents) if c is text_node)
        text_node.extract()

        pos = node_idx
        if before:
            parent_tag.insert(pos, NavigableString(before))
            pos += 1

        new_a = Tag(name="a", attrs={"href": url})
        new_a.string = matched
        parent_tag.insert(pos, new_a)
        pos += 1

        if after:
            parent_tag.insert(pos, NavigableString(after))

        return True

    return False


# ───────────────────────────────────────────────────────────────────────────
# 2. Zone guard — prefix-driven, element-level
# ───────────────────────────────────────────────────────────────────────────

# Structural tags that are always restricted (no prefix needed)
_STRUCTURAL_RESTRICTED_TAGS = frozenset({"li", "th", "td", "table", "details", "blockquote"})

# Default zone suffixes. Config can override.
DEFAULT_ZONE_SUFFIXES = (
    "hero", "quickcard", "quickgrid", "callout", "faq", "table",
    "bluf", "disclosure",
)


def is_restricted_zone(element, zone_config: dict | None = None) -> bool:
    """Return True if *element* is inside a restricted zone.

    zone_config keys (all optional):
        prefixes:  list of CSS class prefixes, e.g. ["tln", "rl-"]
        suffixes:  list of zone suffixes, e.g. ["hero", "callout", "faq"]
                   Defaults to DEFAULT_ZONE_SUFFIXES.
        extra_classes: additional full class names to block, e.g. ["rl-resources"]
    """
    if zone_config is None:
        zone_config = {}
    prefixes = zone_config.get("prefixes", ["tln", "rl-"])
    suffixes = zone_config.get("suffixes", DEFAULT_ZONE_SUFFIXES)
    extra = set(zone_config.get("extra_classes", []))

    # Pre-build the set of blocked class substrings
    blocked = set()
    for pfx in prefixes:
        for sfx in suffixes:
            blocked.add(f"{pfx}{sfx}".lower())
    blocked.update(c.lower() for c in extra)

    for parent in element.parents:
        if not isinstance(parent, Tag):
            continue

        if parent.name in _STRUCTURAL_RESTRICTED_TAGS:
            return True

        classes = " ".join(parent.get("class", [])).lower()
        for marker in blocked:
            if marker in classes:
                return True

    return False


# H2-text patterns for section-level skipping
_FAQ_H2_PATTERN = re.compile(
    r"frequently\s+asked|faqs?\b|common\s+questions", re.IGNORECASE
)
_SKIP_H2_PATTERN = re.compile(
    r"bottom\s+line(?!\s+up\s+front)|resources?\s+used|in\s+this\s+article|"
    r"resources\b|related\s+coverage",
    re.IGNORECASE,
)


def is_body_section(h2_text: str) -> bool:
    """Return True if an H2's text indicates a body section (not FAQ/BLUF/etc)."""
    if _FAQ_H2_PATTERN.search(h2_text):
        return False
    if _SKIP_H2_PATTERN.search(h2_text):
        return False
    if "bottom line" in h2_text.lower():
        return False
    return True


# ───────────────────────────────────────────────────────────────────────────
# 3. Deploy lock — context manager
# ───────────────────────────────────────────────────────────────────────────

_LOCKS_DIR = Path.home() / "locks"


@contextmanager
def deploy_lock(site_id: str, script_name: str, allow_no_tty: bool = False):
    """Acquire a deploy lock. Abort if held by a live process.

    Foreground enforcement: if stdout is not a TTY (i.e., the script is
    backgrounded or piped), abort with exit 98 unless *allow_no_tty* is True.
    When the override is used, a warning is logged to stderr.

    Usage::

        with deploy_lock("tln", "link-injector"):
            do_deploy()
    """
    # Foreground enforcement
    if not sys.stdout.isatty():
        if not allow_no_tty:
            print(
                "ABORT: Deploy scripts run foreground only (CLAUDE.md Server Safety). "
                "Backgrounded execution blocked. Pass allow_no_tty=True only for "
                "legitimate piped logging.",
                file=sys.stderr,
            )
            raise SystemExit(98)
        else:
            print(
                "WARNING: deploy_lock running with non-TTY stdout (allow_no_tty=True). "
                "Ensure this is a legitimate piped-logging context, not a background job.",
                file=sys.stderr,
            )

    lock_path = _LOCKS_DIR / f"{script_name}-{site_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            data = json.loads(lock_path.read_text())
            old_pid = data.get("pid", -1)
            old_ts = data.get("timestamp", "?")
        except (json.JSONDecodeError, KeyError):
            old_pid, old_ts = -1, "?"

        try:
            os.kill(old_pid, 0)
        except ProcessLookupError:
            # Dead process — stale lock
            print(
                f"WARNING: removing stale lock from dead PID {old_pid} ({old_ts})",
                file=sys.stderr,
            )
            lock_path.unlink()
        except PermissionError:
            # Process alive but owned by another user — treat as alive
            print(
                f"ABORT: lock {lock_path} held by live PID {old_pid} ({old_ts})",
                file=sys.stderr,
            )
            raise SystemExit(99)
        except OSError:
            # Other OS errors — treat as stale
            lock_path.unlink()
        else:
            # kill(pid, 0) succeeded — process alive
            print(
                f"ABORT: lock {lock_path} held by live PID {old_pid} ({old_ts})",
                file=sys.stderr,
            )
            raise SystemExit(99)

    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "timestamp": datetime.now().isoformat(),
    }))
    try:
        yield lock_path
    finally:
        if lock_path.exists():
            try:
                data = json.loads(lock_path.read_text())
                if data.get("pid") == os.getpid():
                    lock_path.unlink()
            except Exception:
                pass


# ───────────────────────────────────────────────────────────────────────────
# 4. Candidate generators
# ───────────────────────────────────────────────────────────────────────────

STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "or", "but", "not", "no", "if", "it", "its", "do", "does",
    "did", "has", "have", "had", "can", "could", "will", "would", "shall",
    "should", "may", "might", "must", "that", "this", "these", "those",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "you", "your", "i", "my", "we", "our", "they", "their", "up",
})


def _has_content_words(phrase: str, min_count: int = 2) -> bool:
    words = phrase.lower().split()
    content = [w for w in words if w not in STOPWORDS]
    return len(content) >= min_count


_EDGE_STRIP = frozenset({
    "a", "an", "the", "and", "or", "vs", "for", "with", "your", "how",
    "what", "why", "to", "in", "of", "on", "is", "are", "by", "at",
    "from", "as", "it", "its", "but", "not", "if", "do", "be", "my",
    "we", "our", "you", "they", "their", "this", "that", "so", "up",
    "much", "most", "more", "very", "all", "each", "every",
})

# Question stems that are never useful anchors
_QUESTION_STEMS = frozenset({
    "how much", "how many", "how long", "how often", "how do",
    "what is", "what are", "what does", "when to", "when is",
    "why do", "why is", "where to", "where is", "who is",
    "can you", "do you", "is it", "should you", "will you",
})


def _strip_edge_stopwords(phrase: str) -> str:
    """Strip leading/trailing stopwords and conjunctions from a phrase."""
    words = phrase.split()
    while words and words[0].lower() in _EDGE_STRIP:
        words.pop(0)
    while words and words[-1].lower() in _EDGE_STRIP:
        words.pop()
    return " ".join(words)


def _tokenize_for_phrases(text: str) -> list[list[str]]:
    """Split text on punctuation boundaries, return list of word-lists.

    Splits on: commas, colons, semicolons, dashes (—, –, -), pipes, parens.
    Each segment is a separate pool for phrase windowing.
    """
    # Split on punctuation delimiters
    segments = re.split(r'[,:;|()—–\-]+', text)
    result = []
    for seg in segments:
        words = seg.strip().split()
        if words:
            result.append(words)
    return result


def _is_valid_candidate_phrase(phrase: str, require_noun_ending: bool = False) -> bool:
    """Check word count (2-5), content-word density, edge stopwords, question stems.

    If require_noun_ending is True, the phrase's last token must POS-tag as
    NOUN (NN/NNS) or PROPN (NNP/NNPS) when lowercased. This rejects verb-
    phrase and adjective-phrase candidates like "Getting Approved" or
    "Most Common".
    """
    phrase = phrase.strip()
    if not phrase:
        return False
    words = phrase.split()
    wc = len(words)
    if wc < 2 or wc > 5:
        return False
    if not _has_content_words(phrase, 2):
        return False
    # Reject if starts or ends with a stopword
    if words[0].lower() in _EDGE_STRIP or words[-1].lower() in _EDGE_STRIP:
        return False
    # Reject question stems
    two_word = " ".join(words[:2]).lower()
    if two_word in _QUESTION_STEMS:
        return False
    if require_noun_ending:
        if not _ends_with_noun(phrase):
            return False
    return True


# ── POS gating (NLTK) ─────────────────────────────────────────────────

_nltk_ready = False

def _ensure_nltk():
    global _nltk_ready
    if _nltk_ready:
        return
    import nltk
    try:
        nltk.data.find("taggers/averaged_perceptron_tagger_eng")
    except LookupError:
        nltk.download("averaged_perceptron_tagger_eng", quiet=True)
    _nltk_ready = True

# POS tags that count as "noun ending"
_NOUN_TAGS = frozenset({"NN", "NNS", "NNP", "NNPS"})

# First-token POS tags that signal a verb-phrase start (reject the whole phrase)
_VERB_START_TAGS = frozenset({"VB", "VBD", "VBG", "VBN", "VBP", "VBZ"})


def _ends_with_noun(phrase: str) -> bool:
    """Return True if the last token POS-tags as a noun.

    Lowercases before tagging to avoid NLTK capitalisation bias (it tags
    unknown capitalised words as NNP by default).
    """
    _ensure_nltk()
    from nltk import pos_tag
    words = phrase.lower().split()
    if not words:
        return False
    tags = pos_tag(words)
    last_tag = tags[-1][1]
    if last_tag not in _NOUN_TAGS:
        return False
    # Also reject if first token is a finite verb (e.g., "makes sense")
    first_tag = tags[0][1]
    if first_tag in _VERB_START_TAGS:
        return False
    return True


def pool_candidates(pool_path: str | Path) -> list[tuple[str, str, float, str]]:
    """Generate candidates from a pre-built anchor-pool JSON.

    Returns list of (phrase, dest_url, score, source_type).
    """
    pool_path = Path(pool_path)
    if not pool_path.exists():
        return []
    with open(pool_path) as f:
        data = json.load(f)

    candidates = []
    for dest in data.get("destinations", []):
        url = dest.get("url", "")
        kw = dest.get("primary_keyword", "")
        anchors = dest.get("anchors", [])
        dest_id = dest.get("id")

        # Primary keyword
        if kw and _is_valid_candidate_phrase(kw):
            candidates.append((kw, url, 1.0, "pool_kw", dest_id))

        # Sub-phrases from long keywords
        kw_words = kw.split()
        if len(kw_words) > 5:
            for size in [4, 3]:
                for i in range(len(kw_words) - size + 1):
                    chunk = " ".join(kw_words[i : i + size])
                    if _is_valid_candidate_phrase(chunk):
                        candidates.append((chunk, url, 0.8, "pool_kw_sub", dest_id))

        # AI-generated anchors
        for anchor in anchors:
            if _is_valid_candidate_phrase(anchor):
                candidates.append((anchor, url, 0.9, "pool_anchor", dest_id))

    return _dedup_candidates(candidates)


def corpus_candidates(
    corpus: list[dict],
) -> list[tuple[str, str, float, str]]:
    """Generate candidates from a corpus of published posts.

    Each corpus entry: {"id": int, "slug": str, "title": str, "url": str}
    Derives phrases from title words, slug (hyphens→spaces).

    Returns list of (phrase, dest_url, score, source_type).
    """
    candidates = []
    for post in corpus:
        url = post.get("url", "")
        title = post.get("title", "")
        slug = post.get("slug", "")
        dest_id = post.get("id")

        # Title-derived: tokenize on punctuation, then window within each segment
        for segment_words in _tokenize_for_phrases(title):
            for size in range(min(5, len(segment_words) + 1), 1, -1):
                for i in range(len(segment_words) - size + 1):
                    chunk = " ".join(segment_words[i : i + size])
                    chunk = _strip_edge_stopwords(chunk)
                    if _is_valid_candidate_phrase(chunk, require_noun_ending=True):
                        candidates.append((chunk, url, 1.0, "title", dest_id))

        # Slug-derived: hyphens to spaces, same tokenize + window
        slug_phrase = slug.replace("-", " ")
        for segment_words in _tokenize_for_phrases(slug_phrase):
            for size in range(min(5, len(segment_words) + 1), 1, -1):
                for i in range(len(segment_words) - size + 1):
                    chunk = " ".join(segment_words[i : i + size])
                    chunk = _strip_edge_stopwords(chunk)
                    if _is_valid_candidate_phrase(chunk, require_noun_ending=True):
                        candidates.append((chunk, url, 0.7, "slug", dest_id))

    return _dedup_candidates(candidates)


def _dedup_candidates(
    raw: list[tuple],
) -> list[tuple[str, str, float, str]]:
    """Deduplicate by (phrase_lower, url), keep highest score. Strip dest_id."""
    seen = {}
    for entry in raw:
        phrase, url, score, source = entry[0], entry[1], entry[2], entry[3]
        key = (phrase.lower(), url)
        if key not in seen or score > seen[key][2]:
            seen[key] = (phrase, url, score, source)
    # Sort by phrase length desc (longer = more specific = tried first)
    return sorted(seen.values(), key=lambda x: -len(x[0]))


# ───────────────────────────────────────────────────────────────────────────
# 5. Scoring with inbound-priority
# ───────────────────────────────────────────────────────────────────────────

def is_dest_capped(
    dest_url: str,
    per_run_dest_counts: dict[str, int],
    per_run_dest_cap: int,
) -> bool:
    """Return True if the destination has reached its per-run hard cap."""
    normalized = _normalize_for_dedup(dest_url)
    return per_run_dest_counts.get(normalized, 0) >= per_run_dest_cap


def score_candidate(
    phrase: str,
    base_score: float,
    dest_url: str,
    inbound_counts: dict[str, int],
    inbound_min: int = 3,
) -> float:
    """Score a candidate for ranking when multiple destinations compete.

    Priority order:
    1. Under-inbound-threshold destinations get +2.0 boost
    2. Longer anchor text scores higher (built into base_score sort)

    Per-run cap is enforced as a hard skip BEFORE scoring (see is_dest_capped).
    """
    score = base_score
    normalized = _normalize_for_dedup(dest_url)
    current_inbound = inbound_counts.get(normalized, 0)

    if current_inbound < inbound_min:
        score += 2.0

    return score


def _normalize_for_dedup(url: str) -> str:
    """Normalize URL for dedup/counting: lowercase path, strip trailing slash."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").lower()
    return path or "/"
