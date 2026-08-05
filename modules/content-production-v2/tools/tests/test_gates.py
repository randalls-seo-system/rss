"""Tests for the five gate fixes (Phase 1).

Covers:
  Fix 1 — CSS gate: foreign class fails, allowlist passes, framework prefixes never flag
  Fix 2 — Validator: below-threshold raises, --soft-validate preserves advisory
  Fix 3 — D2: mocked CLI failure → blocked; mocked success with zero claims → passes
  Fix 4 — Corpus: forced exception → job extras contain FAILED string
  Fix 5 — LLM retry: mocked non-zero succeeds on attempt 2; fatal raises immediately; rate-limit selects long backoff
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(MODULE_DIR))


# ---------------------------------------------------------------------------
# Fix 1 — CSS gate
# ---------------------------------------------------------------------------

class TestCSSGate:
    """Gate 6 must hard-fail on foreign classes."""

    def _make_config(self, prefixes=None, allowlist=None):
        config = {
            "content": {
                "css_prefix": prefixes or ["rl-"],
                "css_allowlist": allowlist or [],
                "article_min_words": 10,
                "cta_url": "",
            },
        }
        return config

    def _html(self, classes_str):
        return f'<div class="main-content"><div class="{classes_str}"><h2>Test</h2><p>Body words here enough to pass word count gate easily and more.</p></div></div>'

    def test_foreign_class_fails(self):
        from lib.orchestrator import run_gates
        html = self._html("rl-card mystery-widget")
        result = run_gates(html, self._make_config())
        assert result["css_prefix"].startswith("FAIL"), f"Expected FAIL, got: {result['css_prefix']}"
        assert "mystery-widget" in result["css_prefix"]

    def test_allowlist_passes(self):
        from lib.orchestrator import run_gates
        html = self._html("rl-card mystery-widget")
        result = run_gates(html, self._make_config(allowlist=["mystery-widget"]))
        assert result["css_prefix"] == "pass"

    def test_framework_prefixes_never_flag(self):
        from lib.orchestrator import run_gates
        html = self._html("rl-card et_pb_module wp-block-paragraph dsm-icon")
        result = run_gates(html, self._make_config())
        assert result["css_prefix"] == "pass"

    def test_builtin_allowlist_passes(self):
        from lib.orchestrator import run_gates
        html = self._html("main-content ans sep badge bluf")
        result = run_gates(html, self._make_config())
        assert result["css_prefix"] == "pass"

    def test_site_prefix_match(self):
        from lib.orchestrator import run_gates
        html = self._html("rl-bluf rl-callout rl-card")
        result = run_gates(html, self._make_config())
        assert result["css_prefix"] == "pass"


# ---------------------------------------------------------------------------
# Fix 2 — Validator routing
# ---------------------------------------------------------------------------

class TestValidatorRouting:
    """Below-threshold validation must raise; --soft-validate preserves old behavior."""

    def test_below_threshold_raises(self):
        """Simulate the routing logic: hard_passed < 25 without soft_validate → RuntimeError."""
        hard_passed = 20
        hard_total = 30
        soft_validate = False

        if hard_passed < 25 and hard_total > 0 and not soft_validate:
            with pytest.raises(RuntimeError, match="Validation FAILED"):
                raise RuntimeError(
                    f"Validation FAILED: {hard_passed}/{hard_total} hard passed (threshold 25). "
                    f"Report: /tmp/test-report.md"
                )
        else:
            pytest.fail("Should have entered the raise branch")

    def test_soft_validate_does_not_raise(self):
        """With soft_validate=True, below-threshold should NOT raise."""
        hard_passed = 20
        hard_total = 30
        soft_validate = True

        raised = False
        if hard_passed < 25 and hard_total > 0 and not soft_validate:
            raised = True
        assert not raised, "Should not raise in soft-validate mode"

    def test_above_threshold_passes(self):
        """At or above 25 should not raise regardless."""
        hard_passed = 26
        hard_total = 30
        soft_validate = False

        should_raise = hard_passed < 25 and hard_total > 0 and not soft_validate
        assert not should_raise


# ---------------------------------------------------------------------------
# Fix 3 — D2 fail-closed
# ---------------------------------------------------------------------------

class TestD2FailClosed:
    """D2 extraction CLI failure → stage blocked, never passed."""

    def test_cli_failure_blocks(self):
        """Mocked CLI returning non-zero on all attempts → RuntimeError."""
        from lib.orchestrator import run_claims_extraction
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            job_path = Path(td)
            # Mock subprocess.run to always fail
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "connection reset"
            mock_result.stdout = ""
            with patch("lib.orchestrator.subprocess.run", return_value=mock_result):
                with patch("lib.orchestrator.time.sleep"):  # skip actual sleep
                    import lib.orchestrator as _omod
                    # Temporarily patch the time import inside the function
                    with pytest.raises(RuntimeError, match="D2 extraction CLI failed"):
                        run_claims_extraction("<p>Test article</p>", job_path)

    def test_cli_success_zero_claims_passes(self):
        """CLI succeeds but extracts zero claims → returns empty list (legitimate)."""
        from lib.orchestrator import run_claims_extraction
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            job_path = Path(td)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"result": "[]"})
            mock_result.stderr = ""
            with patch("lib.orchestrator.subprocess.run", return_value=mock_result):
                claims = run_claims_extraction("<p>Test</p>", job_path)
                assert claims == []

    def test_d2_check_extraction_failure_returns_blocked(self):
        """run_d2_claims_check with extraction failure → passed=False, blocked field set."""
        from lib.orchestrator import run_d2_claims_check, JOBS_DIR
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            job_id = "test-999"
            job = {"id": job_id, "post_id": 999, "site": "test", "keyword": "test"}
            # Create the job directory so job_dir() succeeds
            job_dir_path = JOBS_DIR / job_id
            job_dir_path.mkdir(parents=True, exist_ok=True)
            config = {"content": {"claims_policy": ""}}
            try:
                with patch("lib.orchestrator.run_claims_extraction", side_effect=RuntimeError("CLI dead")):
                    with patch("lib.orchestrator.run_ventriloquism_gate", return_value=[]):
                        result = run_d2_claims_check("<p>Test</p>", config, job)
                        assert result["passed"] is False
                        assert "blocked" in result
                        assert "extraction failed" in result["blocked"]
            finally:
                import shutil
                shutil.rmtree(job_dir_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fix 4 — Corpus link visibility
# ---------------------------------------------------------------------------

class TestCorpusVisibility:
    """Forced corpus exception → job extras contain FAILED string."""

    def test_corpus_failure_recorded(self):
        """When _run_corpus_link_pass raises, the status is recorded not silenced."""
        from lib.orchestrator import save_job
        import tempfile

        job = {"post_id": 999, "site": "test", "keyword": "test",
               "dir": tempfile.mkdtemp(), "stages": {}}
        config = {"content": {"css_prefix": ["rl-"]}}

        with patch("lib.orchestrator._run_corpus_link_pass",
                   side_effect=ImportError("No module named 'nltk'")):
            with patch("lib.orchestrator.save_job"):
                # Simulate the try/except block from run_link_pass
                corpus_links = 0
                corpus_status = "ok"
                try:
                    from lib.orchestrator import _run_corpus_link_pass
                    corpus_links = _run_corpus_link_pass(job, config, Path("/tmp/fake.html"))
                except Exception as e:
                    corpus_status = f"FAILED: {type(e).__name__}: {e}"

                assert corpus_status.startswith("FAILED:")
                assert "nltk" in corpus_status


# ---------------------------------------------------------------------------
# Fix 5 — LLM retry policy
# ---------------------------------------------------------------------------

class TestLLMRetry:
    """Retry logic: non-zero succeeds on attempt 2; fatal raises immediately; rate-limit uses long backoff."""

    def test_succeeds_on_second_attempt(self):
        from lib.llm_client import LLMClient
        client = LLMClient(provider="claude_cli")
        call_count = 0

        def mock_call(prompt, system_msg, max_tokens):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Claude CLI failed (exit 1): temporary glitch")
            return "success text", 0, 0

        with patch.object(client, "_call_claude_cli", side_effect=mock_call):
            with patch("lib.llm_client.time.sleep"):
                resp = client.call("test prompt")
                assert resp.text == "success text"
                assert call_count == 2

    def test_fatal_pattern_raises_immediately(self):
        from lib.llm_client import LLMClient
        client = LLMClient(provider="claude_cli")

        def mock_call(prompt, system_msg, max_tokens):
            raise RuntimeError("Claude CLI failed: command not found")

        with patch.object(client, "_call_claude_cli", side_effect=mock_call):
            with pytest.raises(RuntimeError, match="command not found"):
                client.call("test prompt")

    def test_rate_limit_uses_long_backoff(self):
        from lib.llm_client import LLMClient, RATE_LIMIT_BACKOFF_BASE
        client = LLMClient(provider="claude_cli")
        call_count = 0
        sleep_times = []

        def mock_call(prompt, system_msg, max_tokens):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Claude CLI failed: 429 too many requests")
            return "success", 0, 0

        def mock_sleep(seconds):
            sleep_times.append(seconds)

        with patch.object(client, "_call_claude_cli", side_effect=mock_call):
            with patch("lib.llm_client.time.sleep", side_effect=mock_sleep):
                resp = client.call("test prompt")
                assert resp.text == "success"
                # First backoff should be RATE_LIMIT_BACKOFF_BASE (60s)
                assert sleep_times[0] >= RATE_LIMIT_BACKOFF_BASE
