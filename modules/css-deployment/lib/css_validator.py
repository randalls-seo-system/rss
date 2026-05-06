"""
CSS validation and analysis utilities.

Parse CSS, count selectors, detect class-name patterns, check for issues.
"""

import re
from dataclasses import dataclass, field


@dataclass
class CSSStats:
    file_path: str = ""
    file_size: int = 0
    selector_count: int = 0
    rule_count: int = 0
    variable_count: int = 0
    important_count: int = 0
    prefixed_classes: dict = field(default_factory=dict)  # prefix → count
    errors: list = field(default_factory=list)


# Matches CSS selectors (simplified: everything before { that isn't inside a block)
SELECTOR_RE = re.compile(r"([^{}]+)\{")
# Matches CSS custom properties
VARIABLE_RE = re.compile(r"--[\w-]+\s*:")
# Matches !important
IMPORTANT_RE = re.compile(r"!important")
# Matches class selectors
CLASS_RE = re.compile(r"\.([\w-]+)")


def parse_css(css_text: str, file_path: str = "") -> CSSStats:
    """Parse CSS text and return statistics."""
    stats = CSSStats(file_path=file_path, file_size=len(css_text.encode("utf-8")))

    # Count selectors
    selectors = SELECTOR_RE.findall(css_text)
    stats.selector_count = len(selectors)

    # Count rule blocks (number of { characters not inside comments)
    clean = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    stats.rule_count = clean.count("{")

    # Count variables
    stats.variable_count = len(VARIABLE_RE.findall(clean))

    # Count !important
    stats.important_count = len(IMPORTANT_RE.findall(clean))

    return stats


def detect_class_prefixes(css_text: str, prefixes: list[str] = None) -> dict:
    """Detect class-name prefixes in CSS selectors.

    Args:
        css_text: CSS source
        prefixes: list of prefixes to look for (e.g., ['vln', 'valn', 'lrg', 'rl'])

    Returns:
        dict of prefix → list of class names found
    """
    if prefixes is None:
        prefixes = ["vln", "valn", "lrg", "rl", "cnp"]

    clean = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    classes = CLASS_RE.findall(clean)

    result = {p: [] for p in prefixes}
    for cls in set(classes):
        for prefix in prefixes:
            if cls.startswith(prefix) or cls.startswith(f"{prefix}-"):
                result[prefix].append(cls)
                break

    return {k: sorted(v) for k, v in result.items() if v}


def find_unmapped_classes(css_text: str, source_prefix: str) -> list[str]:
    """Find class names with source_prefix that weren't mapped to rl-* yet."""
    clean = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    classes = set(CLASS_RE.findall(clean))
    return sorted(c for c in classes if c.startswith(source_prefix) and not c.startswith("rl-"))


def validate_css_syntax(css_text: str) -> list[str]:
    """Basic CSS syntax validation. Returns list of error messages."""
    errors = []
    # Check balanced braces
    opens = css_text.count("{")
    closes = css_text.count("}")
    if opens != closes:
        errors.append(f"Unbalanced braces: {opens} opens, {closes} closes")

    # Check for common issues
    if "<<<" in css_text or ">>>" in css_text:
        errors.append("Git merge markers detected")

    # Check for empty rules
    empty_rules = re.findall(r"\{[\s]*\}", css_text)
    if empty_rules:
        errors.append(f"{len(empty_rules)} empty rule blocks")

    return errors
