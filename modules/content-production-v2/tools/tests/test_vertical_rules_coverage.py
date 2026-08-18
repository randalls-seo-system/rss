"""Structural coverage: prose-generating builders MUST inject vertical rules.

Three gates, all structural (no named-builder enumeration):

1. TEMPLATE GATE — every prompt/*.md with {{INJECT_BRAND_VOICE}} must also
   have {{VERTICAL_RULES}}.  Catches: new template without the slot.

2. BUILDER GATE — every render_prompt() call whose template contains
   {{VERTICAL_RULES}} must pass "VERTICAL_RULES" in its dict argument.
   Per-call granularity: a file with two render_prompt calls is checked
   twice.  Catches: builder or inline function that omits the variable.

3. ORCHESTRATOR GATE — assemble-article.py must assign
   state.vertical_rules from load_vertical_rules_block(), not leave the
   dataclass default "".  Catches: loader removal.

Known gap: build-hub-box.py generates micro-copy via inline LLM prompts
(no template, no render_prompt). It requires a condensed vertical block
that does not yet exist. Tracked under Decision 1.
"""

import re
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = MODULE_DIR / "tools"
PROMPTS_DIR = MODULE_DIR / "prompts"
sys.path.insert(0, str(MODULE_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_render_dicts(source: str) -> list[tuple[int, str]]:
    """Find every render_prompt(var, {...}) call in source.

    Returns [(line_number, dict_text), ...] where dict_text is the raw
    text of the dict literal (including braces).
    """
    results = []
    pattern = re.compile(r'render_prompt\(\s*\w+\s*,\s*\{')
    for m in pattern.finditer(source):
        brace_start = m.end() - 1
        depth = 1
        pos = brace_start + 1
        while pos < len(source) and depth > 0:
            ch = source[pos]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            pos += 1
        dict_text = source[brace_start:pos]
        line_num = source[:m.start()].count('\n') + 1
        results.append((line_num, dict_text))
    return results


def _template_for_render_call(source: str, call_line: int) -> str | None:
    """Find the template filename loaded most recently before call_line.

    Traces the nearest preceding load_prompt_template("X.md") call.
    """
    call_pos = sum(
        len(line) + 1 for line in source.split('\n')[:call_line - 1]
    )
    loads = list(re.finditer(
        r'load_prompt_template\(["\']([^"\']+)["\']\)',
        source[:call_pos],
    ))
    if not loads:
        return None
    return loads[-1].group(1)


def _template_needs_vertical(template_name: str) -> bool:
    """Check whether a prompt template contains {{VERTICAL_RULES}}."""
    path = PROMPTS_DIR / template_name
    if not path.exists():
        return False
    return "{{VERTICAL_RULES}}" in path.read_text()


# ---------------------------------------------------------------------------
# Gate 1: Template completeness
# ---------------------------------------------------------------------------

def test_template_gate():
    """Every prompt template with INJECT_BRAND_VOICE must have VERTICAL_RULES."""
    prose_templates = []
    missing = []

    for path in sorted(PROMPTS_DIR.glob("*.md")):
        text = path.read_text()
        if "{{INJECT_BRAND_VOICE}}" in text:
            prose_templates.append(path.name)
            if "{{VERTICAL_RULES}}" not in text:
                missing.append(path.name)

    assert prose_templates, (
        "No prose-generating templates found — expected at least one "
        "with {{INJECT_BRAND_VOICE}}."
    )
    assert not missing, (
        f"Prose template(s) missing {{{{VERTICAL_RULES}}}}: {missing}"
    )


# ---------------------------------------------------------------------------
# Gate 2: Builder code — per render_prompt call
# ---------------------------------------------------------------------------

def test_builder_code_gate():
    """Every render_prompt call with a VERTICAL_RULES template must pass it."""
    failures = []

    for py_path in sorted(TOOLS_DIR.glob("*.py")):
        if py_path.name.startswith("test_") or py_path.name == "__init__.py":
            continue

        src = py_path.read_text()
        if "render_prompt(" not in src:
            continue

        for line_num, dict_text in _extract_render_dicts(src):
            tname = _template_for_render_call(src, line_num)
            if tname is None:
                continue
            if not _template_needs_vertical(tname):
                continue
            if '"VERTICAL_RULES"' not in dict_text:
                failures.append(
                    f"{py_path.name}:{line_num}: render_prompt() uses "
                    f"template '{tname}' which requires VERTICAL_RULES, "
                    f"but the render dict does not contain it"
                )

    assert not failures, (
        "render_prompt() calls missing VERTICAL_RULES:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


# ---------------------------------------------------------------------------
# Gate 3: Orchestrator must load vertical rules into PipelineState
# ---------------------------------------------------------------------------

def test_orchestrator_loads_vertical_rules():
    """assemble-article.py must populate state.vertical_rules from the loader."""
    src = (TOOLS_DIR / "assemble-article.py").read_text()

    assert "load_vertical_rules_block" in src, (
        "assemble-article.py never references load_vertical_rules_block. "
        "PipelineState.vertical_rules defaults to '' for all sites."
    )
    assert re.search(
        r'state\.vertical_rules\s*=\s*load_vertical_rules_block',
        src,
    ), (
        "assemble-article.py does not assign state.vertical_rules from "
        "load_vertical_rules_block(). The field defaults to '' even when "
        "the site declares a vertical."
    )
