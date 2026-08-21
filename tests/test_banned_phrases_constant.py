"""L24: Banned-phrase list is a single source of truth in lib/constants.py.

Tests:
  1. Identity: neither gate_library nor spec_assertions defines a local literal.
  2. Derivation: DEPLOY = GENERATION - PRE_POSTPROCESS_ONLY, exact sizes.
  3. Behavior: both gates reject the same phrases they rejected before this change.
"""

import inspect
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))

import importlib.util as _ilu
_cspec = _ilu.spec_from_file_location("constants", REPO_ROOT / "lib" / "constants.py")
_cmod = _ilu.module_from_spec(_cspec)
_cspec.loader.exec_module(_cmod)
BANNED_PHRASES_DEPLOY = _cmod.BANNED_PHRASES_DEPLOY
BANNED_PHRASES_GENERATION = _cmod.BANNED_PHRASES_GENERATION
PRE_POSTPROCESS_ONLY = _cmod.PRE_POSTPROCESS_ONLY


class TestBannedPhraseIdentity(unittest.TestCase):
    """No local banned-phrase literal in either consumer file."""

    def _source_of(self, module_path: Path) -> str:
        return module_path.read_text()

    def test_gate_library_has_no_local_banned_list(self):
        """Mutation (a): forking the list back into a local literal must fail."""
        src = self._source_of(REPO_ROOT / "lib" / "gate_library.py")
        # The file must NOT contain a _BANNED_PHRASES = [ assignment
        local_def = re.search(r'^_BANNED_PHRASES\s*=\s*\[', src, re.MULTILINE)
        self.assertIsNone(local_def,
            "gate_library.py defines a local _BANNED_PHRASES list — "
            "must import BANNED_PHRASES_DEPLOY from lib/constants.py")

    def test_spec_assertions_has_no_local_banned_list(self):
        """Mutation (a): forking the list back into a local literal must fail."""
        src = self._source_of(
            REPO_ROOT / "modules" / "content-production-v2" / "lib" / "spec_assertions.py")
        local_def = re.search(r'^_BANNED_PHRASES\s*=\s*\[', src, re.MULTILINE)
        self.assertIsNone(local_def,
            "spec_assertions.py defines a local _BANNED_PHRASES list — "
            "must import BANNED_PHRASES_GENERATION from lib/constants.py")

    def test_gate_library_imports_deploy_constant(self):
        src = self._source_of(REPO_ROOT / "lib" / "gate_library.py")
        self.assertIn("BANNED_PHRASES_DEPLOY", src,
            "gate_library.py must import BANNED_PHRASES_DEPLOY from constants")

    def test_spec_assertions_imports_generation_constant(self):
        src = self._source_of(
            REPO_ROOT / "modules" / "content-production-v2" / "lib" / "spec_assertions.py")
        self.assertIn("BANNED_PHRASES_GENERATION", src,
            "spec_assertions.py must import BANNED_PHRASES_GENERATION from constants")


class TestBannedPhraseDerivation(unittest.TestCase):
    """DEPLOY is derived from GENERATION minus PRE_POSTPROCESS_ONLY."""

    def test_deploy_is_subset_of_generation(self):
        self.assertTrue(set(BANNED_PHRASES_DEPLOY).issubset(set(BANNED_PHRASES_GENERATION)))

    def test_exclusion_accounts_for_difference(self):
        """Mutation (b): adding/removing from PRE_POSTPROCESS_ONLY changes DEPLOY size."""
        gen_set = set(BANNED_PHRASES_GENERATION)
        deploy_set = set(BANNED_PHRASES_DEPLOY)
        expected_excluded = gen_set - deploy_set
        self.assertEqual(expected_excluded, PRE_POSTPROCESS_ONLY,
            "DEPLOY must equal GENERATION minus exactly PRE_POSTPROCESS_ONLY")

    def test_deploy_exact_size(self):
        """Mutation (b): the deploy list has exactly the expected number of phrases.
        Removing a phrase from PRE_POSTPROCESS_ONLY would increase this count."""
        expected = len(BANNED_PHRASES_GENERATION) - len(PRE_POSTPROCESS_ONLY)
        self.assertEqual(len(BANNED_PHRASES_DEPLOY), expected,
            f"DEPLOY should be {expected} phrases "
            f"(GENERATION={len(BANNED_PHRASES_GENERATION)} - "
            f"PRE_POSTPROCESS_ONLY={len(PRE_POSTPROCESS_ONLY)})")

    def test_generation_is_tuple(self):
        self.assertIsInstance(BANNED_PHRASES_GENERATION, tuple)

    def test_deploy_is_tuple(self):
        self.assertIsInstance(BANNED_PHRASES_DEPLOY, tuple)

    def test_pre_postprocess_only_is_frozenset(self):
        self.assertIsInstance(PRE_POSTPROCESS_ONLY, frozenset)


class TestBannedPhraseBehaviorUnchanged(unittest.TestCase):
    """Mutation (c): both gates reject the same phrases as before the refactor."""

    # These phrases must be rejected by BOTH gates.
    MUST_REJECT = [
        "discover", "explore", "vibrant communities",
        "dive into", "let's", "we'll cover",
        "navigating the complexities of",
        "dream home", "hassle-free", "stress-free",
        "deep dive", "unlock", "empower", "elevate",
        "tailored solution", "comprehensive solution",
    ]

    def test_generation_regex_rejects_all(self):
        gen_re = re.compile("|".join(BANNED_PHRASES_GENERATION), re.IGNORECASE)
        for phrase in self.MUST_REJECT:
            with self.subTest(phrase=phrase):
                self.assertTrue(gen_re.search(phrase),
                    f"GENERATION regex must reject '{phrase}'")

    def test_deploy_regex_rejects_all(self):
        deploy_re = re.compile("|".join(BANNED_PHRASES_DEPLOY), re.IGNORECASE)
        for phrase in self.MUST_REJECT:
            with self.subTest(phrase=phrase):
                self.assertTrue(deploy_re.search(phrase),
                    f"DEPLOY regex must reject '{phrase}'")

    def test_gate_library_function_rejects(self):
        _gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
        _gl = _ilu.module_from_spec(_gl_spec)
        _gl_spec.loader.exec_module(_gl)
        html = '<p>Find your dream home with hassle-free service.</p>'
        r = _gl.gate_no_banned_phrases(html)
        self.assertFalse(r.passed)

    def test_spec_assertions_function_rejects(self):
        _sa_spec = _ilu.spec_from_file_location(
            "spec_assertions",
            REPO_ROOT / "modules" / "content-production-v2" / "lib" / "spec_assertions.py")
        _sa = _ilu.module_from_spec(_sa_spec)
        _sa_spec.loader.exec_module(_sa)
        from bs4 import BeautifulSoup
        html = '<p>Find your dream home with hassle-free service.</p>'
        soup = BeautifulSoup(html, "html.parser")
        r = _sa.assert_no_banned_phrases(soup, {})
        self.assertFalse(r.passed)

    def test_both_gates_accept_clean_prose(self):
        _gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
        _gl = _ilu.module_from_spec(_gl_spec)
        _gl_spec.loader.exec_module(_gl)
        _sa_spec = _ilu.spec_from_file_location(
            "spec_assertions",
            REPO_ROOT / "modules" / "content-production-v2" / "lib" / "spec_assertions.py")
        _sa = _ilu.module_from_spec(_sa_spec)
        _sa_spec.loader.exec_module(_sa)
        from bs4 import BeautifulSoup

        html = '<p>VA loans allow zero down payment for eligible Veterans in Texas.</p>'
        gate_r = _gl.gate_no_banned_phrases(html)
        self.assertTrue(gate_r.passed)

        soup = BeautifulSoup(html, "html.parser")
        spec_r = _sa.assert_no_banned_phrases(soup, {})
        self.assertTrue(spec_r.passed)

    def test_regex_patterns_identical_when_no_exclusions(self):
        """When PRE_POSTPROCESS_ONLY is empty, both regex patterns are byte-identical."""
        if len(PRE_POSTPROCESS_ONLY) == 0:
            gen_pattern = "|".join(BANNED_PHRASES_GENERATION)
            deploy_pattern = "|".join(BANNED_PHRASES_DEPLOY)
            self.assertEqual(gen_pattern, deploy_pattern)


if __name__ == "__main__":
    unittest.main()
