"""Shared utilities for section-builder tools.

Common functions used across build-card, build-h2-section, build-bluf,
build-faqs, and build-resources tools.
"""

import re
import sys
from pathlib import Path

import yaml

MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = MODULE_DIR.parent.parent
PROMPTS_DIR = MODULE_DIR / "prompts"
TEMPLATES_DIR = MODULE_DIR / "templates"
ARTICLE_SPEC_PATH = REPO_ROOT / "docs" / "article-spec.md"
STRUCTURAL_TEMPLATES_PATH = TEMPLATES_DIR / "structural-templates.yaml"

# Cached article spec text (loaded once per process)
_article_spec_cache: str | None = None

# Cached structural templates (loaded once per process)
_structural_templates_cache: dict | None = None


def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


def extract_html(text: str) -> str:
    """Extract HTML from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    # Fix literal \n (two chars: backslash + n) that LLMs sometimes emit in HTML
    text = text.replace("\\n", "\n")
    return text.strip()


def load_article_spec() -> str:
    """Load docs/article-spec.md, cached for the process lifetime.

    Returns the full spec text, or empty string if the file is missing.
    """
    global _article_spec_cache
    if _article_spec_cache is not None:
        return _article_spec_cache

    if ARTICLE_SPEC_PATH.exists():
        _article_spec_cache = ARTICLE_SPEC_PATH.read_text()
        eprint(f"  [spec] Loaded article spec ({len(_article_spec_cache)} chars)")
    else:
        eprint(f"  [spec] Warning: article spec not found at {ARTICLE_SPEC_PATH}")
        _article_spec_cache = ""

    return _article_spec_cache


def load_structural_template(intent: str) -> dict:
    """Load the structural template for a given intent, cached per process.

    Returns the template dict (with 'sections' list) for the intent.
    Falls back to 'default' if intent not found. Returns empty dict
    and logs a warning if the YAML file is missing.
    """
    global _structural_templates_cache
    if _structural_templates_cache is None:
        if STRUCTURAL_TEMPLATES_PATH.exists():
            _structural_templates_cache = yaml.safe_load(
                STRUCTURAL_TEMPLATES_PATH.read_text()
            )
            eprint(f"  [templates] Loaded structural templates ({len(_structural_templates_cache)} intents)")
        else:
            eprint(f"  [templates] Warning: structural templates not found at {STRUCTURAL_TEMPLATES_PATH}")
            _structural_templates_cache = {}

    if not _structural_templates_cache:
        return {}

    if intent in _structural_templates_cache:
        return _structural_templates_cache[intent]

    eprint(f"  [templates] Intent '{intent}' not in templates, using 'default'")
    return _structural_templates_cache.get("default", {})


_SPEC_PREAMBLE = """
=== ARTICLE SPEC (BINDING — this is the authoritative structure layer) ===

The following is the master Article Spec. It defines the required structure,
section order, content rules, and validation criteria for every article.

RULE: If the per-section template instructions below conflict with this spec,
the SPEC WINS. The template provides framing; the spec provides law.

{spec_text}

=== END ARTICLE SPEC ===

"""


def render_prompt(template: str, variables: dict, inject_spec: bool = True) -> str:
    """Substitute {{VARIABLE}} placeholders in a prompt template.

    When inject_spec is True (the default for all content-generation calls),
    the full article spec is prepended to the rendered prompt so the LLM
    always sees the canonical structure rules.
    """
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))

    if inject_spec:
        spec_text = load_article_spec()
        if spec_text:
            result = _SPEC_PREAMBLE.format(spec_text=spec_text) + result

    return result


def load_prompt_template(prompt_name: str) -> str:
    """Load a prompt markdown file from prompts/ directory.

    Args:
        prompt_name: Filename without directory (e.g., 'atf-card.md').
    """
    path = PROMPTS_DIR / prompt_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text()


def load_brand_voice(archetype: str) -> str:
    """Load brand voice markdown for an archetype.

    Returns empty string if archetype file doesn't exist.
    """
    voice_path = REPO_ROOT / "modules" / "brand-voice" / "archetypes" / f"{archetype}.md"
    if not voice_path.exists():
        eprint(f"Warning: brand voice archetype '{archetype}' not found at {voice_path}")
        return ""
    return voice_path.read_text()


def build_topic_context(serp, filter_topic: str, max_results: int = 5) -> str:
    """Build topic context string from SERP data filtered by topic relevance.

    Args:
        serp: SerpData instance.
        filter_topic: Topic string to filter results by relevance.
        max_results: Maximum number of results to include.

    Returns:
        Formatted context string with relevant titles and snippets.
    """
    if not serp:
        return "(No SERP data available)"

    topic_words = set(re.findall(r"[a-z]+", filter_topic.lower()))

    scored = []
    for r in serp.top_results[:10]:
        text = f"{r.title} {r.snippet}".lower()
        result_words = set(re.findall(r"[a-z]+", text))
        overlap = len(topic_words & result_words)
        scored.append((overlap, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    lines = []
    for _, r in scored[:max_results]:
        lines.append(f"- [{r.title}]: {r.snippet}")

    ai_text = serp.ai_overview_text
    if ai_text:
        lines.append(f"\nAI Overview summary: {ai_text[:500]}")

    return "\n".join(lines) if lines else "(No relevant SERP context found)"


def write_output(html: str, output_path: str | None) -> None:
    """Write HTML to output file or stdout."""
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html)
        eprint(f"Output written to: {output_path}")
    else:
        print(html)


def validate_or_retry(
    html: str,
    validate_fn,
    llm_client,
    prompt: str,
    cache_key: str,
    tool_name: str,
    target_keyword: str,
) -> str:
    """Validate HTML output, re-prompt once on failure.

    If second attempt also fails, writes debug file and exits non-zero
    with a clear error including which assertion failed and what the spec expected.

    Args:
        html: HTML to validate.
        validate_fn: Returns list of error strings (empty = pass).
        llm_client: LLMClient for re-prompt.
        prompt: Original prompt to augment with feedback.
        cache_key: Cache key prefix.
        tool_name: Tool name for debug file.
        target_keyword: For debug file naming.

    Returns:
        Validated HTML string.
    """
    errors = validate_fn(html)
    if not errors:
        return html

    eprint(f"[{tool_name}] Validation failed (attempt 1):")
    for err in errors:
        eprint(f"  - {err}")
    eprint("Re-prompting with validation feedback...")

    retry_prompt = (
        f"{prompt}\n\n"
        f"## VALIDATION FAILED — FIX THESE ISSUES:\n\n"
    )
    for err in errors:
        retry_prompt += f"- {err}\n"
    retry_prompt += "\nReturn corrected HTML only. No markdown fences. No preamble."

    response = llm_client.call(retry_prompt, cache_key=f"{cache_key}__retry")
    html2 = extract_html(response.text)
    errors2 = validate_fn(html2)

    if not errors2:
        eprint(f"[{tool_name}] Retry succeeded.")
        return html2

    # Write debug file and exit
    safe_kw = re.sub(r"[^a-z0-9-]", "-", target_keyword.lower())[:40]
    debug_path = Path(f"/tmp/rss-debug-{tool_name}-{safe_kw}.html")
    debug_path.write_text(html2)

    eprint(f"\n[{tool_name}] Validation FAILED after retry:")
    for err in errors2:
        eprint(f"  FAILED: {err}")
    eprint(f"\nDebug output written to: {debug_path}")
    eprint(f"Spec expected: see docs/article-spec.md for section requirements")
    sys.exit(1)
