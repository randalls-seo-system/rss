"""Tests for config migration: migrated sites must never read .conf.

The structural test monkeypatches builtins.open so that ANY code path
opening sites/<migrated_slug>.conf raises AssertionError. This catches
all four existing .conf parsers and any future fifth parser.
"""

import builtins
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = REPO_ROOT / "sites"


def _load_module_from_file(name: str, filepath: Path):
    """Load a Python module by file path (avoids lib/ namespace collision)."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_site_config = _load_module_from_file(
    "site_config",
    REPO_ROOT / "modules" / "content-production-v2" / "lib" / "site_config.py",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _migrated_slugs() -> list[str]:
    """Return all site slugs that have _migrated: true in config.json."""
    slugs = []
    for d in SITES_DIR.iterdir():
        if not d.is_dir():
            continue
        cfg = d / "config.json"
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text())
                if data.get("_migrated") is True:
                    slugs.append(d.name)
            except (json.JSONDecodeError, AttributeError):
                pass
    return slugs


def _conf_trap(migrated_slugs: list[str]):
    """Return a wrapper around builtins.open that blocks .conf reads for migrated sites."""
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        path_str = str(file)
        for slug in migrated_slugs:
            needle = os.path.join("sites", f"{slug}.conf")
            if path_str.endswith(needle) or path_str.endswith(needle.replace(os.sep, "/")):
                raise AssertionError(
                    f"MIGRATION VIOLATION: code attempted to open {path_str} "
                    f"but site '{slug}' is migrated to config.json"
                )
        return real_open(file, *args, **kwargs)

    return guarded_open


# ---------------------------------------------------------------------------
# Test: migrated sites exist
# ---------------------------------------------------------------------------

def test_at_least_one_migrated_site():
    slugs = _migrated_slugs()
    assert len(slugs) > 0, "No sites are marked _migrated — nothing to test"


def test_ahn_is_migrated():
    assert "ahn" in _migrated_slugs()


# ---------------------------------------------------------------------------
# Structural test: no .conf reads for migrated sites
# ---------------------------------------------------------------------------

class TestNoConfReadsForMigratedSites:
    """Monkeypatch open() and call every config-loading code path.

    Any path that opens sites/<slug>.conf for a migrated site will hit
    the trap and fail, whether it's one of the four known parsers or a
    new fifth one.
    """

    @pytest.fixture(autouse=True)
    def trap_conf_opens(self):
        slugs = _migrated_slugs()
        assert slugs, "No migrated sites"
        with mock.patch("builtins.open", side_effect=_conf_trap(slugs)):
            yield

    def test_load_site_config(self):
        """Parser 1: site_config.py load_site_config()"""
        for slug in _migrated_slugs():
            cfg = _site_config.load_site_config(slug)
            assert cfg.get("SSH_HOST"), f"{slug}: SSH_HOST missing from migrated config"
            assert cfg.get("SITE_DOMAIN"), f"{slug}: SITE_DOMAIN missing"

    def test_load_site_ssh_config(self):
        """Parser 2: ssh_session.py load_site_ssh_config()"""
        mod = _load_module_from_file(
            "ssh_session",
            REPO_ROOT / "modules" / "wp-deploy" / "lib" / "ssh_session.py",
        )
        for slug in _migrated_slugs():
            cfg = mod.load_site_ssh_config(slug)
            assert cfg.get("SSH_HOST"), f"{slug}: SSH_HOST missing"

    def test_render_prompt_load_site_config(self):
        """Parser 3: render-prompt.py load_site_config() (takes a file path)"""
        mod = _load_module_from_file(
            "render_prompt",
            REPO_ROOT / "modules" / "brand-voice" / "tools" / "render-prompt.py",
        )
        for slug in _migrated_slugs():
            conf_path = SITES_DIR / f"{slug}.conf"
            result = mod.load_site_config(str(conf_path))
            assert isinstance(result, dict)

    def test_build_css_bundle_read_site_config(self):
        """Parser 4a: build-css-bundle.py read_site_config()"""
        mod = _load_module_from_file(
            "build_css_bundle",
            REPO_ROOT / "modules" / "css-deployment" / "tools" / "build-css-bundle.py",
        )
        for slug in _migrated_slugs():
            cfg = mod.read_site_config(slug)
            assert isinstance(cfg, dict)

    def test_verify_css_rendered_read_site_config(self):
        """Parser 4b: verify-css-rendered.py read_site_config()"""
        mod = _load_module_from_file(
            "verify_css_rendered",
            REPO_ROOT / "modules" / "css-deployment" / "tools" / "verify-css-rendered.py",
        )
        for slug in _migrated_slugs():
            cfg = mod.read_site_config(slug)
            assert isinstance(cfg, dict)

    def test_gate_library_load_site_conf(self):
        """Parser 5 (delegating): gate_library._load_site_conf()"""
        # gate_library._load_site_conf does sys.path.insert + from lib.site_config import.
        # Ensure content-production-v2 is on sys.path first so lib.site_config resolves.
        cpv2 = str(REPO_ROOT / "modules" / "content-production-v2")
        if cpv2 not in sys.path:
            sys.path.insert(0, cpv2)
        mod = _load_module_from_file(
            "gate_library", REPO_ROOT / "lib" / "gate_library.py")
        for slug in _migrated_slugs():
            cfg = mod._load_site_conf(slug)
            assert cfg.get("SSH_HOST"), f"{slug}: SSH_HOST missing from gate_library path"


# ---------------------------------------------------------------------------
# Type assertions: config.json values have correct Python types
# ---------------------------------------------------------------------------

class TestMigratedConfigTypes:
    """Verify that config.json values have the correct types after flattening."""

    def test_article_min_words_is_string_in_flat(self):
        """Flat dict returns ARTICLE_MIN_WORDS as a string (matching .conf behavior)."""
        for slug in _migrated_slugs():
            cfg = _site_config.load_site_config(slug)
            val = cfg.get("ARTICLE_MIN_WORDS", "")
            assert isinstance(val, str), (
                f"{slug}: ARTICLE_MIN_WORDS should be str in flat dict, got {type(val).__name__}"
            )
            if val:
                int(val)  # must be parseable as int

    def test_json_config_has_int_min_words(self):
        """The raw config.json stores article_min_words as an int."""
        for slug in _migrated_slugs():
            path = SITES_DIR / slug / "config.json"
            data = json.loads(path.read_text())
            val = data.get("content", {}).get("article_min_words")
            if val is not None:
                assert isinstance(val, int), (
                    f"{slug}: config.json article_min_words should be int, got {type(val).__name__}: {val!r}"
                )

    def test_css_prefix_is_list_in_json(self):
        """config.json css_prefix must be a list."""
        for slug in _migrated_slugs():
            path = SITES_DIR / slug / "config.json"
            data = json.loads(path.read_text())
            val = data.get("content", {}).get("css_prefix")
            assert isinstance(val, list), f"{slug}: css_prefix should be list"

    def test_zone_suffixes_is_list_in_json(self):
        """config.json zone_suffixes must be a list, not a string."""
        for slug in _migrated_slugs():
            path = SITES_DIR / slug / "config.json"
            data = json.loads(path.read_text())
            val = data.get("linking", {}).get("zone_suffixes")
            if val is not None:
                assert isinstance(val, list), (
                    f"{slug}: zone_suffixes should be list, got {type(val).__name__}: {val!r}"
                )


# ---------------------------------------------------------------------------
# Parity test: flattened config.json == .conf for every non-empty key
# ---------------------------------------------------------------------------

def _parse_conf_directly(slug: str) -> dict:
    """Parse .conf with the original algorithm, no migration shim."""
    conf_path = SITES_DIR / f"{slug}.conf"
    if not conf_path.exists():
        return {}
    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                continue  # skip section headers for flat comparison
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                conf[key] = val
    return conf


class TestFlattenParity:
    """Every non-empty .conf key must appear with the same value in the
    flattened config.json dict. A missing or mismatched key means
    _flatten_json_config will silently drop config that .conf provided.
    """

    def test_parity_all_migrated_sites(self):
        for slug in _migrated_slugs():
            conf = _parse_conf_directly(slug)
            flat = _site_config._flatten_json_config(slug)

            missing = []
            mismatched = []
            for key, conf_val in sorted(conf.items()):
                if not conf_val:
                    continue
                flat_val = flat.get(key)
                if flat_val is None or flat_val == "":
                    missing.append(key)
                elif flat_val != conf_val:
                    mismatched.append(f"{key}: conf={conf_val!r} flat={flat_val!r}")

            errors = []
            if missing:
                errors.append(f"Missing from flat dict: {missing}")
            if mismatched:
                errors.append(f"Value mismatches: {mismatched}")
            assert not errors, (
                f"Site '{slug}' flatten parity FAILED:\n" + "\n".join(errors)
            )


# ---------------------------------------------------------------------------
# Unmigrated sites still read .conf normally
# ---------------------------------------------------------------------------

def test_unmigrated_sites_still_work():
    """Unmigrated sites must still parse their .conf files."""
    migrated = set(_migrated_slugs())
    for conf_file in SITES_DIR.glob("*.conf"):
        slug = conf_file.stem
        if slug in migrated:
            continue
        assert not _site_config._is_migrated(slug)
        cfg = _site_config.load_site_config(slug)
        assert cfg.get("SSH_HOST"), f"{slug}: unmigrated .conf should return SSH_HOST"
        return  # one is enough
    pytest.skip("No unmigrated sites with .conf files found")
