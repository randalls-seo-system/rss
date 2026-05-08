"""Spec-driven article validator — replaces v1's validate-structure.py.

Runs all spec assertions from lib/spec_assertions.py against assembled HTML.
Outputs per-assertion pass/fail report. Exits non-zero on hard assertion failure.
Soft warnings logged but don't affect exit code unless --strict flag set.

Usage: python3 validate-article-v2.py --html-file <path> --intent <intent> --serp-json <path> --site <slug> --output-format text|json|markdown

See docs/v2-module-architecture.md "tools/validate-article-v2.py" for spec.
"""

raise NotImplementedError("validate-article-v2.py is a stub — implement per architecture spec")
