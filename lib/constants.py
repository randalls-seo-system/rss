"""Shared constants for the RSS pipeline.

Constants that cross module boundaries (repo-root lib/ and
modules/content-production-v2/) live here so there is one
source of truth.
"""

# Every prompt template and assembler hardcodes rl-* classes.
# The postprocessor converts rl-* → site-specific prefixes at deploy time.
# This constant names the generation-time prefix so the generation gate
# checks the right namespace.
GENERATION_CSS_PREFIX = "rl-"

# CSS class allowlists — shared between orchestrator.run_gates and
# gate_library._get_css_allowlist.  One source of truth so framework
# classes added to the pipeline (html_sanitizer, postprocessors) do
# not need per-file patching.
CSS_BUILTIN_ALLOWLIST = {"main-content", "ans", "sep", "badge", "bluf", "rss-il"}
CSS_FRAMEWORK_PREFIXES = ("et_", "wp-", "dsm-", "bullet-section-")

# ---------------------------------------------------------------------------
# L24: Banned-phrase lists — single source of truth
# ---------------------------------------------------------------------------
# GENERATION list: the full set, checked at generation/validation time
# (spec_assertions.py assert_no_banned_phrases).
# DEPLOY list: the subset checked at deploy time (gate_library.py
# gate_no_banned_phrases).  Derived by excluding PRE_POSTPROCESS_ONLY,
# which names phrases that the postprocessor transforms away before deploy.
# Adding a phrase to GENERATION automatically considers it for deploy;
# excluding one from deploy requires naming it in PRE_POSTPROCESS_ONLY.

BANNED_PHRASES_GENERATION = (
    r"\bdiscover\b",
    r"\bexplore\b",
    r"\bvibrant communities\b",
    r"\bdive into\b",
    r"\blet's\b",
    r"\bwe'll cover\b",
    r"navigating the complexities of",
    r"financial journey",
    r"homeownership journey",
    r"dream home",
    r"turn your dreams into reality",
    r"make your dreams come true",
    r"take the first step",
    r"peace of mind",
    r"game changer",
    r"one-stop shop",
    r"look no further",
    r"we'?ve got you covered",
    r"rest assured",
    r"it is worth noting",
    r"at the end of the day",
    r"whether you are a first-time buyer",
    r"from first-time buyers to",
    r"not only does this,? but it also",
    r"more than just",
    r"designed with you in mind",
    r"a wide range of",
    r"a variety of options",
    r"best-in-class",
    r"industry-leading",
    r"hassle-free",
    r"stress-free",
    r"easy and convenient",
    r"expert guidance every step",
    r"deep dive",
    r"\bunlock\b",
    r"\bempower\b",
    r"\belevate\b",
    r"tailored solution",
    r"unique needs",
    r"comprehensive solution",
)

# Phrases that exist only in pre-postprocess HTML and are transformed away
# before deploy.  Excluded from BANNED_PHRASES_DEPLOY because they cannot
# match at deploy time.
# Currently empty — both gates enforce the same 41 phrases.  To exclude a
# phrase from the deploy gate, add it here with a comment explaining why
# it cannot appear post-postprocess.
PRE_POSTPROCESS_ONLY = frozenset()

BANNED_PHRASES_DEPLOY = tuple(
    p for p in BANNED_PHRASES_GENERATION if p not in PRE_POSTPROCESS_ONLY
)
