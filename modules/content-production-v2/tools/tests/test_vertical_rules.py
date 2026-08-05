"""Tests for vertical rules overlay system.

Covers:
  - Loader returns RE block for config declaring real_estate, "" for no vertical
  - Unknown vertical fails config validation with expected message
  - Declared vertical + missing file raises (loud, not empty)
  - Rendered h2 prompt for LRG contains FAIR HOUSING; no-vertical config does not
  - Universal rules (superlatives, VOLATILE) appear in BOTH
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.brand_rules import (
    VALID_VERTICALS,
    load_vertical_rules_block,
    validate_vertical,
)
from lib.tool_utils import load_prompt_template, render_prompt


# ---------------------------------------------------------------------------
# Fixture configs
# ---------------------------------------------------------------------------

def _make_config(vertical: str = "") -> dict:
    """Build a minimal site config dict with optional vertical."""
    config = {
        "SITE_NAME": "Test Site",
        "content": {
            "css_prefix": ["rl-"],
            "brand_voice_archetype": "realtor",
            "default_post_status": "draft",
        },
        "access": {
            "ssh_host": "test.ssh.wpengine.net",
            "ssh_user": "test",
            "ssh_key_path": "~/.ssh/test",
            "wp_path": "/nas/content/live/test/",
        },
        "authors": {"author_map": {"primary": {"wp_user_id": 1, "name": "Test", "scope": "all-content"}}},
        "linking": {"zone_suffixes": [], "skip_slugs": []},
    }
    if vertical:
        config["content"]["vertical"] = vertical
    return config


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

def test_loader_returns_re_block():
    """Config with real_estate vertical should return content with FAIR HOUSING."""
    # Patch load_site_config to return our fixture
    with patch("lib.brand_rules.load_vertical_rules_block.__module__"):
        pass
    # Direct test: read the real file
    re_path = MODULE_DIR / "prompts" / "verticals" / "real-estate.md"
    assert re_path.exists(), f"Real estate vertical file missing: {re_path}"
    content = re_path.read_text()
    assert "FAIR HOUSING" in content
    assert "SCHOOL CLAIMS" in content
    assert "SAFER" in content


def test_loader_returns_empty_for_no_vertical():
    """Config without vertical field should return empty string."""
    config = _make_config()
    # load_vertical_rules_block reads from site config, so we mock load_site_config
    with patch("lib.site_config.load_site_config", return_value=config):
        # Call with any slug — the mock intercepts
        result = load_vertical_rules_block("test-site")
    assert result == ""


def test_loader_returns_content_for_real_estate():
    """Config with real_estate should return the vertical file contents."""
    config = _make_config("real_estate")
    with patch("lib.site_config.load_site_config", return_value=config):
        result = load_vertical_rules_block("test-site")
    assert "FAIR HOUSING" in result
    assert "VERTICAL RULES" in result


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_unknown_vertical_fails_validation():
    """Unknown vertical value should produce a validation error."""
    config = _make_config("pizza_delivery")
    errors = validate_vertical(config)
    assert len(errors) == 1
    assert "pizza_delivery" in errors[0]
    assert "real_estate" in errors[0]  # lists valid options


def test_valid_vertical_passes():
    config = _make_config("real_estate")
    errors = validate_vertical(config)
    assert errors == []


def test_no_vertical_passes():
    config = _make_config()
    errors = validate_vertical(config)
    assert errors == []


# ---------------------------------------------------------------------------
# Missing file test
# ---------------------------------------------------------------------------

def test_declared_vertical_missing_file_raises():
    """Declared vertical with no file should raise FileNotFoundError."""
    config = _make_config("real_estate")
    # Point to a non-existent verticals dir
    import lib.brand_rules as br
    original_dir = br.VERTICALS_DIR
    try:
        br.VERTICALS_DIR = Path("/nonexistent/verticals")
        with patch("lib.site_config.load_site_config", return_value=config):
            raised = False
            try:
                load_vertical_rules_block("test-site")
            except FileNotFoundError as e:
                raised = True
                assert "real_estate" in str(e)
            assert raised, "Expected FileNotFoundError for missing vertical file"
    finally:
        br.VERTICALS_DIR = original_dir


# ---------------------------------------------------------------------------
# Prompt rendering tests
# ---------------------------------------------------------------------------

def test_rendered_prompt_lrg_contains_fair_housing():
    """LRG-style config renders FAIR HOUSING in the h2 prompt."""
    template = load_prompt_template("h2-section.md")
    re_path = MODULE_DIR / "prompts" / "verticals" / "real-estate.md"
    vertical_rules = re_path.read_text()
    rendered = render_prompt(template, {
        "TARGET_KEYWORD": "test keyword",
        "H2_TITLE": "Test Section",
        "H2_FORMAT": "statement",
        "SECTION_ROLE": "body",
        "STRUCTURAL_ELEMENT_PREFERENCE": "bullets",
        "TEMPLATE_HINT": "",
        "CALLOUT_KEY": "",
        "CALLOUT_LABEL": "",
        "TARGET_WORD_COUNT": "300",
        "TOPIC_CONTEXT": "test context",
        "EVIDENCE_BLOCK": "",
        "VERTICAL_RULES": vertical_rules,
        "PRIOR_SECTIONS_SUMMARY": "",
        "INJECT_BRAND_VOICE": "",
    }, inject_spec=False)
    assert "FAIR HOUSING" in rendered
    assert "TEA" in rendered


def test_rendered_prompt_no_vertical_has_no_re_rules():
    """No-vertical config renders without FAIR HOUSING or TEA."""
    template = load_prompt_template("h2-section.md")
    rendered = render_prompt(template, {
        "TARGET_KEYWORD": "test keyword",
        "H2_TITLE": "Test Section",
        "H2_FORMAT": "statement",
        "SECTION_ROLE": "body",
        "STRUCTURAL_ELEMENT_PREFERENCE": "bullets",
        "TEMPLATE_HINT": "",
        "CALLOUT_KEY": "",
        "CALLOUT_LABEL": "",
        "TARGET_WORD_COUNT": "300",
        "TOPIC_CONTEXT": "test context",
        "EVIDENCE_BLOCK": "",
        "VERTICAL_RULES": "",
        "PRIOR_SECTIONS_SUMMARY": "",
        "INJECT_BRAND_VOICE": "",
    }, inject_spec=False)
    assert "FAIR HOUSING" not in rendered
    assert "TEA" not in rendered
    # No orphan header
    assert "## VERTICAL RULES" not in rendered


def test_universal_rules_present_in_both():
    """Both with-vertical and without-vertical prompts contain universal rules."""
    template = load_prompt_template("h2-section.md")
    # With vertical
    re_path = MODULE_DIR / "prompts" / "verticals" / "real-estate.md"
    vertical_rules = re_path.read_text()
    rendered_with = render_prompt(template, {
        "TARGET_KEYWORD": "test",
        "H2_TITLE": "Test",
        "H2_FORMAT": "statement",
        "SECTION_ROLE": "body",
        "STRUCTURAL_ELEMENT_PREFERENCE": "bullets",
        "TEMPLATE_HINT": "",
        "CALLOUT_KEY": "",
        "CALLOUT_LABEL": "",
        "TARGET_WORD_COUNT": "300",
        "TOPIC_CONTEXT": "",
        "EVIDENCE_BLOCK": "",
        "VERTICAL_RULES": vertical_rules,
        "PRIOR_SECTIONS_SUMMARY": "",
        "INJECT_BRAND_VOICE": "",
    }, inject_spec=False)
    # Without vertical
    rendered_without = render_prompt(template, {
        "TARGET_KEYWORD": "test",
        "H2_TITLE": "Test",
        "H2_FORMAT": "statement",
        "SECTION_ROLE": "body",
        "STRUCTURAL_ELEMENT_PREFERENCE": "bullets",
        "TEMPLATE_HINT": "",
        "CALLOUT_KEY": "",
        "CALLOUT_LABEL": "",
        "TARGET_WORD_COUNT": "300",
        "TOPIC_CONTEXT": "",
        "EVIDENCE_BLOCK": "",
        "VERTICAL_RULES": "",
        "PRIOR_SECTIONS_SUMMARY": "",
        "INJECT_BRAND_VOICE": "",
    }, inject_spec=False)
    # Universal rules present in both
    assert "UNSUPPORTED SUPERLATIVES" in rendered_with
    assert "UNSUPPORTED SUPERLATIVES" in rendered_without
    assert "VOLATILE" in rendered_with
    assert "VOLATILE" in rendered_without
