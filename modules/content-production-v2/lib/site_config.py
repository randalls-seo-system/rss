"""Load site configuration from sites/<slug>.conf.

The .conf format uses shell-style KEY="value" for the main section
and INI-style key = value under [branding] and other named sections.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def load_site_config(site_slug: str) -> dict:
    """Load and parse a site configuration file.

    Args:
        site_slug: Site identifier (e.g., 'lrg', 'valn').

    Returns:
        Dict with top-level config values and nested section dicts
        (e.g., config["branding"]["archetype"]).

    Raises:
        FileNotFoundError: If the config file doesn't exist.
    """
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
