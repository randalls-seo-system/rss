"""Universal deploy gate library — single chokepoint for all content writes.

Every deploy path (push-post-content, deploy_draft, refresher swap,
batch-inject-links, backfill-links, LRG generators) must call
run_universal_gates() on the final artifact immediately before the write.
Failure = refuse to write.

Gate incidents are logged in docs/GATES.md.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str | None = None


@dataclass
class GateReport:
    passed: bool
    results: list[GateResult] = field(default_factory=list)
    failures: list[GateResult] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"GATE PASSED ({len(self.results)} checks)"
        names = [f.name for f in self.failures]
        return f"GATE FAILED ({len(self.failures)}/{len(self.results)}): {', '.join(names)}"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_site_json_config(site_slug: str) -> dict:
    """Load sites/<slug>/config.json if it exists."""
    path = REPO_ROOT / "sites" / site_slug / "config.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _load_site_conf(site_slug: str) -> dict:
    """Load sites/<slug>.conf (shell-style KEY=value)."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))
    try:
        from lib.site_config import load_site_config
        return load_site_config(site_slug)
    except (ImportError, FileNotFoundError):
        return {}


def _get_gate_profiles(config: dict) -> dict:
    """Extract gate_profiles from config, with defaults."""
    profiles = config.get("content", {}).get("gate_profiles", {})
    defaults = {
        "article": {"min_words": 1200, "require_headline": True, "min_sections": 6},
        "roundup": {"min_words": 800, "require_headline": True, "min_sections": 3},
        "guide": {"min_words": 1000, "require_headline": True, "min_sections": 4},
        "pillar": {"min_words": 1500, "require_headline": True, "min_sections": 5},
        "page": {"min_words": 200, "require_headline": False, "min_sections": 0},
        "link_update": {"min_words": 0, "require_headline": False, "min_sections": 0},
    }
    for k, v in defaults.items():
        if k not in profiles:
            profiles[k] = v
    return profiles


def _get_css_allowlist(config: dict) -> set[str]:
    """Build the combined CSS class allowlist from config."""
    prefixes = config.get("content", {}).get("css_prefix", [])
    explicit = set(config.get("content", {}).get("css_allowlist", []))
    # Built-in classes used across all sites
    builtin = {
        "main-content", "ans", "sep", "badge", "bluf",
        "rss-il",  # injected internal link class
    }
    # Framework prefixes (Divi, WP core)
    framework = ("et_", "wp-", "dsm-")
    return builtin | explicit, prefixes, framework


def _get_sourcing_claims_patterns(config: dict) -> list[str]:
    """Get per-site patterns that require evidence when claimed."""
    defaults = [
        r"MLS data",
        r"CAD records",
        r"county records",
        r"according to our analysis of",
    ]
    configured = config.get("content", {}).get("sourcing_claims_require_evidence", [])
    return configured if configured else defaults


# ---------------------------------------------------------------------------
# Individual gate assertions
# ---------------------------------------------------------------------------

_EDITORIAL_MARKERS = [
    r"\[FLAG",
    r"\[TODO",
    r"\[VERIFY",
    r"\[REVIEW",
    r"\[PLACEHOLDER",
    r"FIXME",
    r"XXX:",
    r"Lorem ipsum",
    r"\[INSERT",
    r"\{\{",
]
_EDITORIAL_RE = re.compile("|".join(_EDITORIAL_MARKERS), re.IGNORECASE)


def gate_no_editorial_markup(html: str, **kw: Any) -> GateResult:
    """Body contains no editorial/placeholder markers."""
    matches = _EDITORIAL_RE.findall(html)
    if matches:
        unique = list(dict.fromkeys(m.strip() for m in matches))[:5]
        return GateResult("no_editorial_markup", False,
                          f"Editorial markers found: {unique}")
    return GateResult("no_editorial_markup", True)


def gate_slug_unique(html: str, *, site_slug: str = "", slug: str = "",
                     inventory: dict | None = None, **kw: Any) -> GateResult:
    """Slug does not collide with existing post inventory."""
    if not slug:
        return GateResult("slug_unique", True, "No slug provided (skipped)")

    # Load inventory
    if inventory is None:
        inv_path = REPO_ROOT / "sites" / site_slug / "post-inventory.json"
        if not inv_path.exists():
            # Fail closed: inventory missing
            return GateResult("slug_unique", False,
                              f"Post inventory not found at {inv_path} — fail closed")
        try:
            inventory = json.loads(inv_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            return GateResult("slug_unique", False,
                              f"Post inventory unreadable: {e} — fail closed")

    # Check for collision
    if isinstance(inventory, list):
        existing_slugs = {p.get("slug") or p.get("post_name", "") for p in inventory}
    elif isinstance(inventory, dict):
        existing_slugs = {v.get("slug") or v.get("post_name", "")
                          for v in inventory.values() if isinstance(v, dict)}
    else:
        return GateResult("slug_unique", False,
                          "Inventory format unrecognized — fail closed")

    if slug in existing_slugs:
        return GateResult("slug_unique", False,
                          f"Slug '{slug}' already exists in post inventory")
    return GateResult("slug_unique", True)


def gate_title_integrity(html: str, *, title: str = "", **kw: Any) -> GateResult:
    """Title non-empty, >20 chars, no trailing conjunction/comma/whitespace,
    no pipeline prefix leaks."""
    if not title:
        # Try to extract from H1
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        return GateResult("title_integrity", True, "No title to check (skipped)")

    issues = []
    if len(title) <= 20:
        issues.append(f"Too short ({len(title)} chars)")

    stripped = title.rstrip()
    if stripped and stripped[-1] in (",",):
        issues.append(f"Trailing comma: '{stripped[-10:]}'")
    for suffix in (" and", " or", " the", " a", " in", " of", " for"):
        if stripped.endswith(suffix):
            issues.append(f"Trailing conjunction '{suffix.strip()}'")
            break

    if stripped != stripped.rstrip():
        issues.append("Trailing whitespace")

    # Pipeline prefix leaks
    leak_patterns = [
        r"\[REFRESH pending\]",
        r"\[DRAFT\]",
        r"\[WIP\]",
        r"\[PENDING\]",
    ]
    for pat in leak_patterns:
        if re.search(pat, title, re.IGNORECASE):
            issues.append(f"Pipeline prefix leak: '{re.search(pat, title, re.IGNORECASE).group()}'")

    if issues:
        return GateResult("title_integrity", False, "; ".join(issues))
    return GateResult("title_integrity", True)


def gate_no_fragment_list_items(html: str, **kw: Any) -> GateResult:
    """Every <li> has >=4 words and does not start with punctuation."""
    soup = BeautifulSoup(html, "html.parser")
    fragments = []
    for li in soup.find_all("li"):
        if li.find_parent("nav"):
            continue
        text = li.get_text(strip=True)
        if not text:
            fragments.append("(empty)")
            continue
        wc = len(re.findall(r"\b\w+\b", text))
        if wc < 4:
            fragments.append(f'{wc}w: "{text[:40]}"')
        elif text[0] in ".,;:!?)>—":
            fragments.append(f'starts with \'{text[0]}\': "{text[:40]}"')
    if fragments:
        return GateResult("no_fragment_list_items", False,
                          f"{len(fragments)} fragment <li>: {'; '.join(fragments[:3])}")
    return GateResult("no_fragment_list_items", True)


def gate_no_undefined_classes(html: str, *, site_slug: str = "",
                              config: dict | None = None, **kw: Any) -> GateResult:
    """Every class maps to the site's stylesheet or allowlist."""
    if config is None:
        config = _load_site_json_config(site_slug)
    if not config:
        return GateResult("no_undefined_classes", True,
                          "No config available (skipped)")

    builtin, prefixes, framework = _get_css_allowlist(config)
    if not prefixes:
        return GateResult("no_undefined_classes", True,
                          "No css_prefix configured (skipped)")

    soup = BeautifulSoup(html, "html.parser")
    foreign = []
    for tag in soup.find_all(class_=True):
        for cls in tag.get("class", []):
            if cls in builtin:
                continue
            if any(cls.startswith(p) for p in framework):
                continue
            if any(cls.lower().startswith(p.lower()) for p in prefixes):
                continue
            foreign.append(cls)

    foreign = sorted(set(foreign))
    if foreign:
        return GateResult("no_undefined_classes", False,
                          f"Foreign classes: {', '.join(foreign[:10])}")
    return GateResult("no_undefined_classes", True)


def gate_no_fabricated_sourcing(html: str, *, site_slug: str = "",
                                config: dict | None = None,
                                declared_sources: list[str] | None = None,
                                **kw: Any) -> GateResult:
    """Body does not claim data sources unless declared in job context."""
    if config is None:
        config = _load_site_json_config(site_slug)

    patterns = _get_sourcing_claims_patterns(config)
    if not patterns:
        return GateResult("no_fabricated_sourcing", True)

    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    declared = set(s.lower() for s in (declared_sources or []))

    hits = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            matched = m.group().lower()
            if matched not in declared and not any(d in matched for d in declared):
                hits.append(m.group())

    if hits:
        unique = list(dict.fromkeys(hits))[:5]
        return GateResult("no_fabricated_sourcing", False,
                          f"Undeclared sourcing claims: {unique}")
    return GateResult("no_fabricated_sourcing", True)


# Reuse the banned-phrase list from spec_assertions
_BANNED_PHRASES = [
    r"\bdiscover\b", r"\bexplore\b", r"\bvibrant communities\b",
    r"\bdive into\b", r"\blet's\b", r"\bwe'll cover\b",
    r"navigating the complexities of",
    r"financial journey", r"homeownership journey",
    r"dream home", r"turn your dreams into reality",
    r"make your dreams come true", r"take the first step",
    r"peace of mind", r"game changer", r"one-stop shop",
    r"look no further", r"we'?ve got you covered",
    r"rest assured", r"it is worth noting",
    r"at the end of the day",
    r"whether you are a first-time buyer",
    r"from first-time buyers to",
    r"not only does this,? but it also",
    r"more than just", r"designed with you in mind",
    r"a wide range of", r"a variety of options",
    r"best-in-class", r"industry-leading",
    r"hassle-free", r"stress-free",
    r"easy and convenient",
    r"expert guidance every step",
    r"deep dive", r"\bunlock\b", r"\bempower\b",
    r"\belevate\b", r"tailored solution",
    r"unique needs", r"comprehensive solution",
]
_BANNED_RE = re.compile("|".join(_BANNED_PHRASES), re.IGNORECASE)


def gate_no_banned_phrases(html: str, **kw: Any) -> GateResult:
    """No banned filler/AI phrases in body text."""
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    matches = _BANNED_RE.findall(text)
    if matches:
        unique = list(dict.fromkeys(m.lower() for m in matches))[:5]
        return GateResult("no_banned_phrases", False,
                          f"Banned phrases: {unique}")
    return GateResult("no_banned_phrases", True)


def gate_body_not_empty(html: str, *, content_type: str = "article",
                        config: dict | None = None, **kw: Any) -> GateResult:
    """Body meets minimum word count for its content type."""
    profiles = _get_gate_profiles(config or {})
    profile = profiles.get(content_type, profiles.get("page", {}))
    min_words = profile.get("min_words", 200)

    if min_words <= 0:
        return GateResult("body_not_empty", True)

    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    wc = len(text.split())
    if wc < min_words:
        return GateResult("body_not_empty", False,
                          f"{wc} words (min {min_words} for {content_type})")
    return GateResult("body_not_empty", True)


def gate_headline_present(html: str, *, content_type: str = "article",
                          config: dict | None = None, **kw: Any) -> GateResult:
    """Content has at least one headline (H1 or H2)."""
    profiles = _get_gate_profiles(config or {})
    profile = profiles.get(content_type, profiles.get("page", {}))
    if not profile.get("require_headline", True):
        return GateResult("headline_present", True, "Not required for this type")

    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    h2 = soup.find("h2")
    if h1 or h2:
        return GateResult("headline_present", True)
    return GateResult("headline_present", False, "No H1 or H2 found")


def gate_min_sections(html: str, *, content_type: str = "article",
                      config: dict | None = None, **kw: Any) -> GateResult:
    """Content has minimum number of H2 sections for its type."""
    profiles = _get_gate_profiles(config or {})
    profile = profiles.get(content_type, profiles.get("page", {}))
    min_sections = profile.get("min_sections", 0)
    if min_sections <= 0:
        return GateResult("min_sections", True)

    soup = BeautifulSoup(html, "html.parser")
    h2_count = len(soup.find_all("h2"))
    if h2_count >= min_sections:
        return GateResult("min_sections", True)
    return GateResult("min_sections", False,
                      f"{h2_count} H2 sections (min {min_sections} for {content_type})")


# ---------------------------------------------------------------------------
# Universal gate runner
# ---------------------------------------------------------------------------

# The UNIVERSAL set: runs on every content type
_UNIVERSAL_GATES = [
    gate_no_editorial_markup,
    gate_title_integrity,
    gate_no_fragment_list_items,
    gate_no_undefined_classes,
    gate_no_fabricated_sourcing,
    gate_no_banned_phrases,
    gate_body_not_empty,
    gate_headline_present,
    gate_min_sections,
]

# slug_unique is separate because it needs slug param
_SLUG_GATE = gate_slug_unique


def run_universal_gates(
    html: str,
    *,
    site_slug: str,
    slug: str = "",
    title: str = "",
    content_type: str = "article",
    config: dict | None = None,
    inventory: dict | None = None,
    declared_sources: list[str] | None = None,
) -> GateReport:
    """Run all universal gates on content HTML.

    Returns GateReport. All gates are hard — any failure = refuse to write.
    """
    if config is None:
        config = _load_site_json_config(site_slug)

    results: list[GateResult] = []
    failures: list[GateResult] = []

    kw = dict(
        site_slug=site_slug,
        slug=slug,
        title=title,
        content_type=content_type,
        config=config,
        inventory=inventory,
        declared_sources=declared_sources,
    )

    # Run universal gates
    for gate_fn in _UNIVERSAL_GATES:
        r = gate_fn(html, **kw)
        results.append(r)
        if not r.passed:
            failures.append(r)

    # Run slug uniqueness check if slug provided
    if slug:
        r = _SLUG_GATE(html, **kw)
        results.append(r)
        if not r.passed:
            failures.append(r)

    return GateReport(
        passed=len(failures) == 0,
        results=results,
        failures=failures,
    )


# ---------------------------------------------------------------------------
# Deploy artifact class-migration gate (refresh path only, not universal)
# ---------------------------------------------------------------------------

_RL_CLASS_RE = re.compile(r'\brl-[a-zA-Z][\w-]*')


def assert_deploy_class_migration(
    html: str,
    source_html: str,
    css_prefix: str,
) -> GateResult:
    """Deploy artifact for a non-rl- site must have migrated CSS classes.

    Fails when css_prefix is not "rl-" AND either:
    - html contains rl-* classes (migration incomplete), OR
    - html is byte-identical to source_html (postprocessor passed through)

    Passes unconditionally when css_prefix is "rl-" (no migration expected).

    css_prefix must be a normalized string (first element of the config list),
    not the raw list. Raises TypeError if a list/tuple is passed.
    """
    if isinstance(css_prefix, (list, tuple)):
        raise TypeError(
            "css_prefix must be a normalized string, not the raw config list"
        )

    if css_prefix == "rl-":
        return GateResult("deploy_class_migration", True,
                          "css_prefix is rl- — no migration expected")

    rl_classes = _RL_CLASS_RE.findall(html)
    if rl_classes:
        unique = sorted(set(rl_classes))[:10]
        return GateResult("deploy_class_migration", False,
                          f"Deploy artifact contains rl-* classes for a "
                          f"{css_prefix!r} site: {', '.join(unique)}")

    if html == source_html:
        return GateResult("deploy_class_migration", False,
                          f"Deploy artifact is byte-identical to source article "
                          f"— postprocessor did not convert classes for "
                          f"{css_prefix!r} site")

    return GateResult("deploy_class_migration", True)


# ---------------------------------------------------------------------------
# CLI: rss gate
# ---------------------------------------------------------------------------

def cli_gate(args: list[str] | None = None) -> int:
    """CLI entry point: rss gate --site <slug> --file <html> --type <type>."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="rss gate",
        description="Run universal deploy gates on an HTML file",
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--file", required=True, help="Path to HTML file")
    parser.add_argument("--type", default="article",
                        help="Content type (article, roundup, guide, pillar, page, link_update)")
    parser.add_argument("--slug", default="", help="Post slug for uniqueness check")
    parser.add_argument("--title", default="", help="Post title for integrity check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    parsed = parser.parse_args(args)

    html_path = Path(parsed.file)
    if not html_path.exists():
        print(f"ERROR: File not found: {html_path}", file=sys.stderr)
        return 1

    html = html_path.read_text(encoding="utf-8")
    report = run_universal_gates(
        html,
        site_slug=parsed.site,
        slug=parsed.slug,
        title=parsed.title,
        content_type=parsed.type,
    )

    if parsed.json:
        out = {
            "passed": report.passed,
            "results": [
                {"name": r.name, "passed": r.passed, "detail": r.detail}
                for r in report.results
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        for r in report.results:
            icon = "PASS" if r.passed else "FAIL"
            detail = f" — {r.detail}" if r.detail else ""
            print(f"  [{icon}] {r.name}{detail}")
        print(f"\n{report.summary()}")

    return 0 if report.passed else 1


def cli_gate_scan(args: list[str] | None = None) -> int:
    """CLI entry point: rss gate-scan --site <slug> --all-published."""
    import argparse
    import subprocess
    import sys
    import time
    from datetime import datetime

    parser = argparse.ArgumentParser(
        prog="rss gate-scan",
        description="Scan all published pages through universal gates (read-only)",
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--all-published", action="store_true", required=True,
                        help="Scan all published posts")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of posts")
    parser.add_argument("--output", default="", help="Output file path (default: docs/)")

    parsed = parser.parse_args(args)

    # Load site config for SSH
    try:
        sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))
        from lib.site_config import load_site_config
        conf = load_site_config(parsed.site)
    except (ImportError, FileNotFoundError) as e:
        print(f"ERROR: Cannot load site config: {e}", file=sys.stderr)
        return 1

    json_config = _load_site_json_config(parsed.site)

    # Get published post list via SSH
    ssh_host = conf.get("SSH_HOST", "")
    ssh_user = conf.get("SSH_USER", "")
    ssh_key = conf.get("SSH_KEY_PATH", "")
    if ssh_key:
        import os
        ssh_key = os.path.expanduser(ssh_key)

    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    if ssh_key:
        ssh_base += ["-i", ssh_key, "-o", "IdentitiesOnly=yes"]
    ssh_base.append(f"{ssh_user}@{ssh_host}")

    print(f"Fetching published post list from {parsed.site}...", file=sys.stderr)
    sql = "SELECT ID, post_name, post_title FROM wp_posts WHERE post_status='publish' AND post_type='post' ORDER BY ID;"
    result = subprocess.run(
        ssh_base + ["wp db query --skip-column-names"],
        input=sql, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"ERROR: SSH failed: {result.stderr[:200]}", file=sys.stderr)
        return 1

    posts = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            posts.append({"id": int(parts[0]), "slug": parts[1], "title": parts[2]})

    if parsed.limit > 0:
        posts = posts[:parsed.limit]

    print(f"Scanning {len(posts)} posts...", file=sys.stderr)

    # Scan each post
    scan_results = []
    for i, post in enumerate(posts):
        pid = post["id"]
        slug = post["slug"]
        print(f"  [{i+1}/{len(posts)}] {slug} (ID {pid})...",
              file=sys.stderr, end="", flush=True)

        # Fetch post_content
        try:
            fetch_result = subprocess.run(
                ssh_base + [f"wp post get {pid} --field=post_content"],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            scan_results.append({
                "id": pid, "slug": slug, "title": post["title"],
                "status": "FETCH_FAILED", "failures": [],
                "failure_details": {"timeout": "SSH fetch timed out (60s)"},
            })
            print(f" TIMEOUT", file=sys.stderr)
            time.sleep(2)
            continue
        if fetch_result.returncode != 0 or not fetch_result.stdout.strip():
            scan_results.append({
                "id": pid, "slug": slug, "title": post["title"],
                "status": "FETCH_FAILED", "failures": [],
            })
            print(f" FETCH FAILED", file=sys.stderr)
            time.sleep(1)
            continue

        html = fetch_result.stdout
        report = run_universal_gates(
            html,
            site_slug=parsed.site,
            slug="",  # Don't check slug uniqueness on existing posts
            title=post["title"],
            content_type="article",
            config=json_config,
        )

        failure_names = [f.name for f in report.failures]
        failure_details = {f.name: f.detail for f in report.failures}
        scan_results.append({
            "id": pid, "slug": slug, "title": post["title"],
            "status": "PASS" if report.passed else "FAIL",
            "failures": failure_names,
            "failure_details": failure_details,
        })

        status = "PASS" if report.passed else f"FAIL ({', '.join(failure_names)})"
        print(f" {status}", file=sys.stderr)
        time.sleep(1)  # SSH pacing

    # Write report
    date_str = datetime.now().strftime("%Y%m%d")
    output_path = Path(parsed.output) if parsed.output else (
        REPO_ROOT / "docs" / f"{parsed.site}-gate-scan-{date_str}.md"
    )

    fail_count = sum(1 for r in scan_results if r["status"] == "FAIL")
    pass_count = sum(1 for r in scan_results if r["status"] == "PASS")
    fetch_fail = sum(1 for r in scan_results if r["status"] == "FETCH_FAILED")

    lines = [
        f"# Gate Scan: {parsed.site} ({date_str})",
        "",
        f"**Total:** {len(scan_results)} | **Pass:** {pass_count} | "
        f"**Fail:** {fail_count} | **Fetch failed:** {fetch_fail}",
        "",
        "| ID | Slug | Status | Failures |",
        "|---:|------|--------|----------|",
    ]
    for r in scan_results:
        failures_str = ", ".join(r["failures"]) if r["failures"] else ""
        lines.append(
            f"| {r['id']} | {r['slug'][:50]} | {r['status']} | {failures_str} |"
        )

    # Failure detail appendix
    if fail_count > 0:
        lines += ["", "## Failure Details", ""]
        for r in scan_results:
            if r["status"] == "FAIL":
                lines.append(f"### {r['slug']} (ID {r['id']})")
                for name, detail in r.get("failure_details", {}).items():
                    lines.append(f"- **{name}**: {detail}")
                lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"\nReport: {output_path}", file=sys.stderr)
    print(f"Summary: {pass_count} pass, {fail_count} fail, {fetch_fail} fetch-failed")

    return 0 if fail_count == 0 else 1
