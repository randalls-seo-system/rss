"""Load site configuration from sites/<slug>.conf or sites/<slug>/config.json.

Migrated sites (config.json has "_migrated": true) are served from config.json.
The returned dict is flattened to look like a .conf parse so callers don't change.

Unmigrated sites are parsed from .conf as before.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _json_config_path(site_slug: str) -> Path:
    return REPO_ROOT / "sites" / site_slug / "config.json"


def _is_migrated(site_slug: str) -> bool:
    """Check whether a site has been migrated to config.json."""
    path = _json_config_path(site_slug)
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text()).get("_migrated", False) is True
    except (json.JSONDecodeError, AttributeError):
        return False


def _flatten_json_config(site_slug: str) -> dict:
    """Load config.json and flatten to .conf-style KEY=value dict.

    This produces the same dict shape that callers of load_site_config()
    expect: flat top-level keys like SSH_HOST, SITE_DOMAIN, AI_PROVIDER,
    plus a nested "branding" dict if present.
    """
    path = _json_config_path(site_slug)
    raw = json.loads(path.read_text())

    config: dict = {}

    # identity
    ident = raw.get("identity", {})
    config["SITE_NAME"] = ident.get("name", "")
    config["SITE_DOMAIN"] = ident.get("domain", "")
    config["SITE_URL"] = ident.get("public_url", "")
    config["SITE_PREFIX"] = ident.get("prefix", ident.get("site_id", ""))
    config["SITE_SLUG"] = ident.get("site_id", "")

    # access
    acc = raw.get("access", {})
    config["SSH_HOST"] = acc.get("ssh_host", "")
    config["SSH_USER"] = acc.get("ssh_user", "")
    config["SSH_KEY_PATH"] = acc.get("ssh_key_path", "")
    config["WP_PATH"] = acc.get("wp_path", "")
    config["MU_PLUGINS_PATH"] = acc.get("mu_plugins_path", "")

    # staging
    staging = acc.get("staging") or {}
    if staging:
        config["STAGING_URL"] = staging.get("url", "")
        config["STAGING_SSH_USER"] = staging.get("ssh_user", "")
        config["STAGING_SSH_KEY"] = staging.get("ssh_key_path", "")
        config["STAGING_WP_PATH"] = staging.get("wp_path", "")

    # content
    content = raw.get("content", {})
    config["PRIMARY_COLOR"] = content.get("primary_color", "")
    config["SECONDARY_COLOR"] = content.get("secondary_color", "")
    config["LOGO_URL"] = content.get("logo_url", "")
    config["SITE_PHONE"] = content.get("phone", "")
    config["FORM_PAGE_SLUG"] = content.get("form_page_slug", "")
    config["CTA_URL"] = content.get("cta_url", "")
    config["CTA_TEXT"] = content.get("cta_text", "")
    config["GEO_FOCUS"] = content.get("geo_focus", "")
    config["AI_PROVIDER"] = content.get("ai_provider", "claude_cli")
    config["AI_MODEL"] = content.get("ai_model", "opus")
    config["AI_API_KEY_ENV_VAR"] = content.get("ai_api_key_env_var", "")
    config["AI_MAX_RETRIES"] = content.get("ai_max_retries", "")
    config["AI_REQUEST_TIMEOUT"] = content.get("ai_request_timeout", "")
    config["ARTICLE_MIN_WORDS"] = str(content.get("article_min_words", ""))
    config["ARTICLE_MAX_WORDS"] = str(content.get("article_max_words", ""))
    config["DEFAULT_POST_STATUS"] = content.get("default_post_status", "")
    config["PRIMARY_AUDIENCE"] = content.get("primary_audience", "")
    config["SPECIALTY"] = content.get("specialty", "")
    config["CONFIG_URLS_FILE"] = content.get("config_urls_file", "")

    # authors
    authors = raw.get("authors", {})
    config["BYLINE_MODE"] = authors.get("byline_mode", "")
    author_map = authors.get("author_map", {})
    if author_map:
        first = next(iter(author_map.values()))
        config["PRIMARY_AUTHOR_ID"] = str(first.get("wp_user_id", ""))
        config["PRIMARY_AUTHOR_NAME"] = first.get("name", "")

    # brand voice rules (GFP-style)
    config["BRAND_VOICE_NOTES"] = content.get("brand_voice_notes", "")
    config["PRICE_POLICY"] = content.get("price_policy", "")
    config["COMPETITOR_MENTION_POLICY"] = content.get("competitor_mention_policy", "")
    config["FORBIDDEN_TERMS"] = content.get("forbidden_terms", "")
    config["FORBIDDEN_DOMAINS"] = content.get("forbidden_domains", "")
    config["REQUIRED_TONE"] = content.get("required_tone", "")

    # linking
    linking = raw.get("linking", {})
    config["LINKING_V2_ENABLED"] = str(linking.get("linking_v2_enabled", "")).lower()
    config["ANCHOR_POOL_SIZE_MIN"] = str(linking.get("anchor_pool_size_min", ""))
    config["ANCHOR_POOL_SIZE_MAX"] = str(linking.get("anchor_pool_size_max", ""))
    config["ANCHOR_POOL_PATH"] = linking.get("pool_path", "")

    # module toggles
    toggles = raw.get("toggles", {})
    config["TECHNICAL_SEO_ENABLED"] = str(toggles.get("technical_seo", "")).lower()
    config["QA_GATES_ENABLED"] = str(toggles.get("qa_gates", "")).lower()
    config["LLM_INFRASTRUCTURE_ENABLED"] = str(toggles.get("llm_infrastructure", "")).lower()

    # integrations
    integ = raw.get("integrations", {})
    config["GSC_PROPERTY"] = integ.get("gsc_property", "")
    config["GSC_SERVICE_ACCOUNT"] = integ.get("gsc_service_account", "")

    # ops
    ops = raw.get("ops", {})
    config["SERVICE_TIER"] = ops.get("service_tier", "")

    # branding section (for render-prompt.py)
    branding = raw.get("branding")
    if branding:
        config["branding"] = branding

    return config


def load_site_config(site_slug: str) -> dict:
    """Load and parse a site configuration.

    Migrated sites (config.json has "_migrated": true) are loaded from
    config.json and flattened to the same dict shape as .conf parsing.

    Unmigrated sites are parsed from the .conf file as before.

    Args:
        site_slug: Site identifier (e.g., 'lrg', 'valn').

    Returns:
        Dict with top-level config values and nested section dicts
        (e.g., config["branding"]["archetype"]).

    Raises:
        FileNotFoundError: If neither config source exists.
    """
    if _is_migrated(site_slug):
        return _flatten_json_config(site_slug)

    conf_path = REPO_ROOT / "sites" / f"{site_slug}.conf"
    if not conf_path.exists():
        raise FileNotFoundError(f"Site config not found: {conf_path}")

    config: dict = {}
    current_section: str | None = None
    sections: dict[str, dict] = {}

    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                if current_section not in sections:
                    sections[current_section] = {}
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if current_section:
                    sections[current_section][key] = val
                else:
                    config[key] = val

    for section_name, section_data in sections.items():
        config[section_name] = section_data

    return config
