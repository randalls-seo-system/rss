"""Mutation tests for lib/artifact_resolver.py and deploy class-migration gate.

Each test proves its guard is load-bearing: remove the protection, watch it fail,
restore, watch it pass. A test that passes with the guard removed proves nothing.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.artifact_resolver import (
    validate_post_id,
    resolve_deploy_artifact,
    ArtifactResolutionError,
    ResolvedArtifact,
)
from lib.gate_library import assert_deploy_class_migration


# ── Fixtures ──────────────────────────────────────────────────────────────

DEPLOY_HTML = '<div class="tlnPage"><h1>Title</h1><p>Content here.</p></div>'
RAW_HTML = '<div class="rl-page"><h1>Title</h1><p>Content here.</p></div>'


# ── (a) Job dir with *-article.html, no deploy.html -> resolver raises ───

class TestResolverRejectsRawOnly(unittest.TestCase):
    """A job dir that has only the raw article must not resolve."""

    def test_raw_article_present_no_deploy_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jdir = Path(tmpdir)
            (jdir / "1501-article.html").write_text(RAW_HTML)
            job = {"id": "test-raw-only", "post_id": 1501}

            with self.assertRaises(ArtifactResolutionError) as ctx:
                resolve_deploy_artifact(job, jdir)
            self.assertIn("1501-deploy.html", str(ctx.exception))
            self.assertIn("test-raw-only", str(ctx.exception))


# ── (b) Job record post_id invalid values -> resolver raises ─────────────

class TestValidatePostIdRejects(unittest.TestCase):
    """validate_post_id must reject null, empty, 0, -1, 3.7, True."""

    def test_null_raises(self):
        with self.assertRaises(ArtifactResolutionError) as ctx:
            validate_post_id({"id": "job-null", "post_id": None})
        self.assertIn("null", str(ctx.exception))

    def test_empty_string_raises(self):
        with self.assertRaises(ArtifactResolutionError):
            validate_post_id({"id": "job-empty", "post_id": ""})

    def test_zero_raises(self):
        with self.assertRaises(ArtifactResolutionError) as ctx:
            validate_post_id({"id": "job-zero", "post_id": 0})
        self.assertIn("not positive", str(ctx.exception))

    def test_negative_raises(self):
        with self.assertRaises(ArtifactResolutionError) as ctx:
            validate_post_id({"id": "job-neg", "post_id": -1})
        self.assertIn("not positive", str(ctx.exception))

    def test_float_raises(self):
        with self.assertRaises(ArtifactResolutionError) as ctx:
            validate_post_id({"id": "job-float", "post_id": 3.7})
        self.assertIn("float", str(ctx.exception))

    def test_bool_raises(self):
        with self.assertRaises(ArtifactResolutionError) as ctx:
            validate_post_id({"id": "job-bool", "post_id": True})
        self.assertIn("boolean", str(ctx.exception))

    def test_missing_key_raises(self):
        with self.assertRaises(ArtifactResolutionError):
            validate_post_id({"id": "job-missing"})

    def test_valid_int_passes(self):
        result = validate_post_id({"id": "job-ok", "post_id": 1501})
        self.assertEqual(result, 1501)

    def test_valid_string_passes(self):
        result = validate_post_id({"id": "job-ok-str", "post_id": "1501"})
        self.assertEqual(result, 1501)


# ── (c) is in modules/content-production-v2/tools/tests/test_audit_refresh.py
#    (TestApproveRefreshDeployArtifactGate) to avoid lib/ namespace collision.


# ── (d) Deploy artifact class-migration gate ─────────────────────────────

class TestDeployClassMigration(unittest.TestCase):
    """assert_deploy_class_migration must catch unmigrated rl-* classes on
    non-rl- sites and pass them on rl- sites."""

    def test_d1_rl_classes_on_tln_site_fails(self):
        """d1: deploy artifact with rl-* classes, css_prefix "tln" -> FAILS.
        Deploy differs from source (extra comment) so only the rl-* scan catches it,
        not byte-identity."""
        deploy_with_rl = RAW_HTML + "\n<!-- postprocessed -->"
        result = assert_deploy_class_migration(
            html=deploy_with_rl,
            source_html=RAW_HTML,
            css_prefix="tln",
        )
        self.assertFalse(result.passed)
        self.assertIn("rl-", result.detail)

    def test_d2_rl_classes_on_rl_site_passes(self):
        """d2: deploy artifact with rl-* classes, css_prefix "rl-" -> PASSES"""
        result = assert_deploy_class_migration(
            html=RAW_HTML,
            source_html=RAW_HTML,
            css_prefix="rl-",
        )
        self.assertTrue(result.passed)

    def test_byte_identical_no_rl_classes_on_tln_fails(self):
        """Postprocessor passed through without converting — byte-identical,
        no rl-* classes (e.g. nh-* guide content). Must fail."""
        nh_html = '<div class="nh-hero"><h1>Guide</h1></div>'
        result = assert_deploy_class_migration(
            html=nh_html,
            source_html=nh_html,
            css_prefix="tln",
        )
        self.assertFalse(result.passed)
        self.assertIn("byte-identical", result.detail)

    def test_properly_migrated_passes(self):
        """Deploy artifact with converted classes, different from source -> passes."""
        result = assert_deploy_class_migration(
            html=DEPLOY_HTML,
            source_html=RAW_HTML,
            css_prefix="tln",
        )
        self.assertTrue(result.passed)

    def test_list_css_prefix_raises_typeerror(self):
        """Raw config list must not pass through — TypeError."""
        with self.assertRaises(TypeError) as ctx:
            assert_deploy_class_migration(
                html=DEPLOY_HTML,
                source_html=RAW_HTML,
                css_prefix=["tln"],
            )
        self.assertIn("normalized string", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
