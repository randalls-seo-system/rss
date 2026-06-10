#!/usr/bin/env python3
"""Tests for the rss new-article orchestrator.

Covers: config validation failure modes, gate enforcement, resumability.
"""

import json
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MODULE_DIR))

from lib.orchestrator import (
    validate_config, resolve_author, run_gates, gates_passed,
    create_job, save_job, load_job, stage_done, mark_stage,
)


# ───────────────────────────────────────────────────────────────────────────
# Config validation
# ───────────────────────────────────────────────────────────────────────────

class TestConfigValidation:

    def _base_config(self):
        return {
            "access": {"ssh_host": "x", "ssh_user": "x", "ssh_key_path": "x", "wp_path": "/x/"},
            "content": {"css_prefix": ["vln"], "brand_voice_archetype": "va-lending",
                        "default_post_status": "draft", "article_min_words": 1600},
            "authors": {"author_map": {"primary": {"wp_user_id": 1, "name": "Test", "scope": "all"}}},
            "linking": {"zone_suffixes": ["hero"], "skip_slugs": ["legal"], "pool_path": "x.json"},
        }

    def test_valid_config_passes(self):
        missing = validate_config(self._base_config())
        assert missing == [], f"Expected no missing, got: {missing}"

    def test_missing_ssh_host(self):
        cfg = self._base_config()
        del cfg["access"]["ssh_host"]
        missing = validate_config(cfg)
        assert "access.ssh_host" in missing

    def test_missing_css_prefix(self):
        cfg = self._base_config()
        cfg["content"]["css_prefix"] = ""
        missing = validate_config(cfg)
        assert "content.css_prefix" in missing

    def test_missing_author_map(self):
        cfg = self._base_config()
        cfg["authors"]["author_map"] = ""
        missing = validate_config(cfg)
        assert "authors.author_map" in missing

    def test_publish_status_rejected(self):
        cfg = self._base_config()
        cfg["content"]["default_post_status"] = "publish"
        missing = validate_config(cfg)
        assert any("default_post_status" in m for m in missing)

    def test_todo_verify_treated_as_missing(self):
        cfg = self._base_config()
        cfg["linking"]["zone_suffixes"] = "TODO-verify"
        missing = validate_config(cfg)
        assert "linking.zone_suffixes" in missing


class TestAuthorResolution:

    def test_default_first_entry(self):
        cfg = {"authors": {"author_map": {
            "primary": {"wp_user_id": 941, "name": "Matt", "scope": "mortgage"},
            "secondary": {"wp_user_id": 234, "name": "Levi", "scope": "lifestyle"},
        }}}
        uid, name = resolve_author(cfg)
        assert uid == 941

    def test_category_match(self):
        cfg = {"authors": {"author_map": {
            "primary": {"wp_user_id": 941, "name": "Matt", "scope": "mortgage"},
            "secondary": {"wp_user_id": 234, "name": "Levi", "scope": "lifestyle"},
        }}}
        uid, name = resolve_author(cfg, "lifestyle")
        assert uid == 234


# ───────────────────────────────────────────────────────────────────────────
# Gate enforcement
# ───────────────────────────────────────────────────────────────────────────

class TestGates:

    _config = {
        "content": {"css_prefix": ["vln"], "article_min_words": 100, "cta_url": "/compare/"},
    }

    def test_h1_in_body_fails(self):
        html = '<div class="vlnPage main-content"><h1>Bad Title</h1><p>Content here.</p></div>'
        results = run_gates(html, self._config)
        assert "FAIL" in results["no_h1_in_body"]

    def test_em_dash_fails(self):
        html = '<div class="vlnPage main-content"><p>This sentence \u2014 has an em dash.</p></div>'
        results = run_gates(html, self._config)
        assert "FAIL" in results["no_em_dashes"]

    def test_internal_link_fails(self):
        html = '<div class="vlnPage main-content"><p>See our <a href="/va-loans/">guide</a>.</p></div>'
        results = run_gates(html, self._config)
        assert "FAIL" in results["no_writer_links"]

    def test_clean_article_passes(self):
        words = " ".join(["word"] * 200)
        html = f'<div class="vlnBLUF"><p>Bottom line up front.</p></div><div class="vlnPage main-content"><p>{words}</p><a href="/compare/">CTA</a></div>'
        results = run_gates(html, self._config)
        assert gates_passed(results), f"Gates failed: {results}"

    def test_low_word_count_fails(self):
        html = '<div class="vlnBLUF"><p>BLUF</p></div><div class="vlnPage main-content"><p>Short.</p><a href="/compare/">CTA</a></div>'
        cfg = dict(self._config)
        cfg["content"] = {**cfg["content"], "article_min_words": 500}
        results = run_gates(html, cfg)
        assert "FAIL" in results["word_count"]


# ───────────────────────────────────────────────────────────────────────────
# Resumability
# ───────────────────────────────────────────────────────────────────────────

class TestResumability:

    def test_create_and_load_job(self):
        job = create_job("test", "test topic")
        loaded = load_job(job["id"])
        assert loaded["site"] == "test"
        assert loaded["topic"] == "test topic"
        # Cleanup
        import shutil
        shutil.rmtree(Path(__file__).resolve().parents[4] / "jobs" / job["id"])

    def test_stage_done_tracking(self):
        job = create_job("test", "resumability test")
        assert not stage_done(job, "config")
        mark_stage(job, "config", "done")
        assert stage_done(job, "config")
        assert not stage_done(job, "generate")
        # Cleanup
        import shutil
        shutil.rmtree(Path(__file__).resolve().parents[4] / "jobs" / job["id"])

    def test_resume_skips_completed_stages(self):
        """Simulate: config + gap_scan done, generate not done."""
        job = create_job("test", "resume test")
        mark_stage(job, "config", "done")
        mark_stage(job, "gap_scan", "done")
        # Reload
        loaded = load_job(job["id"])
        assert stage_done(loaded, "config")
        assert stage_done(loaded, "gap_scan")
        assert not stage_done(loaded, "generate")  # first incomplete stage
        # Cleanup
        import shutil
        shutil.rmtree(Path(__file__).resolve().parents[4] / "jobs" / job["id"])


# ───────────────────────────────────────────────────────────────────────────
# Runner
# ───────────────────────────────────────────────────────────────────────────

def _run_all():
    test_classes = [
        TestConfigValidation,
        TestAuthorResolution,
        TestGates,
        TestResumability,
    ]
    total = passed = failed = 0
    failures = []

    for cls in test_classes:
        instance = cls()
        methods = sorted(m for m in dir(instance) if m.startswith("test_") and callable(getattr(instance, m)))
        for method in methods:
            total += 1
            test_id = f"{cls.__name__}.{method}"
            try:
                getattr(instance, method)()
                passed += 1
                print(f"  PASS  {test_id}")
            except Exception as e:
                failed += 1
                failures.append((test_id, str(e)))
                print(f"  FAIL  {test_id}: {e}")

    print(f"\n{'='*60}")
    print(f"  {total} tests | {passed} passed | {failed} failed")
    print(f"{'='*60}")
    if failures:
        for tid, err in failures:
            print(f"  FAILURE: {tid}\n           {err}")
        sys.exit(1)
    else:
        print("  ALL TESTS PASSED")


if __name__ == "__main__":
    _run_all()
