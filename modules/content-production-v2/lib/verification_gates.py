"""AI Verification Layer — Gate implementations.

Design principle (non-negotiable): An API judge may PASS, AUTO-FIX-AND-LOG,
or ESCALATE-TO-RANDALL. It may NEVER make an irreversible decision on a
high-cost ambiguous call autonomously. Below a confidence threshold it
ESCALATES WITH A SPECIFIC QUESTION — it does not guess-and-act.

See docs/verification-layer-design.md for the full design.

Gates implemented:
    A: RENDER-VERIFY — wraps verify-deploy.py, judges rendered artifacts
    B: ARTIFACT-SCAN — detects + strips leaked generation meta-commentary
"""

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ───────────────────────────────────────────────────────────────────────────
# Shared types
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    gate: str
    disposition: Literal["pass", "auto-fix", "escalate"]
    detail: str
    confidence: float | None = None
    fixes_applied: list[str] = field(default_factory=list)
    escalation: dict | None = None


@dataclass
class Escalation:
    gate: str
    severity: Literal["high", "medium", "low"]
    question: str
    context: str
    confidence: float | None = None
    api_reasoning: str = ""
    post_id: int | None = None
    url: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


# ───────────────────────────────────────────────────────────────────────────
# Gate A: RENDER-VERIFY
# ───────────────────────────────────────────────────────────────────────────

def gate_render_verify(
    url: str,
    expected_checks: list[dict],
    post_id: int | None = None,
) -> GateResult:
    """Verify the rendered page contains expected artifacts.

    Wraps verify-deploy.py --url (RENDER-TRUTH per VERIFICATION-STANDARD.md).
    Adds structured escalation for any missing element.

    Args:
        url: The live page URL to check.
        expected_checks: List of check dicts for verify-deploy.py
            (same format as verify-spec JSON: type, value, section).
        post_id: Optional post ID for escalation context.

    Returns:
        GateResult with disposition pass or escalate.
    """
    verify_tool = REPO_ROOT / "modules" / "wp-deploy" / "tools" / "verify-deploy.py"

    # Build CLI args from checks
    args = [sys.executable, str(verify_tool), "--url", url, "--output-format", "json", "--timeout", "20"]
    for check in expected_checks:
        ctype = check.get("type", "text")
        value = check.get("value", "")
        if ctype == "text":
            args.extend(["--expect-text", value])
        elif ctype == "head":
            args.extend(["--expect-head", value])
        elif ctype == "forbid":
            args.extend(["--forbid-text", value])
        elif ctype == "element":
            args.extend(["--expect-element", value])

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=45
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            gate="RENDER-VERIFY",
            disposition="escalate",
            detail=f"verify-deploy.py timed out for {url}",
            escalation=asdict(Escalation(
                gate="RENDER-VERIFY",
                severity="high",
                question=f"Render verification timed out for {url}. Page may be down or extremely slow.",
                context="verify-deploy.py exceeded 45s timeout",
                post_id=post_id,
                url=url,
            )),
        )

    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return GateResult(
            gate="RENDER-VERIFY",
            disposition="escalate",
            detail=f"verify-deploy.py returned unparseable output",
            escalation=asdict(Escalation(
                gate="RENDER-VERIFY",
                severity="high",
                question=f"Render verification produced no parseable result for {url}.",
                context=f"stdout: {result.stdout[:300]}",
                post_id=post_id,
                url=url,
            )),
        )

    if not report.get("fetched"):
        return GateResult(
            gate="RENDER-VERIFY",
            disposition="escalate",
            detail=f"Could not fetch {url}: {report.get('error', 'unknown')}",
            escalation=asdict(Escalation(
                gate="RENDER-VERIFY",
                severity="high",
                question=f"Page {url} could not be fetched. Error: {report.get('error', 'unknown')}",
                context="Page may not be deployed, or URL may be wrong.",
                post_id=post_id,
                url=url,
            )),
        )

    if report.get("passed"):
        return GateResult(
            gate="RENDER-VERIFY",
            disposition="pass",
            detail=f"{report.get('summary', 'all checks passed')} for {url}",
        )

    # Some checks failed — build specific escalation
    failed_checks = [c for c in report.get("checks", []) if not c.get("passed")]
    failed_descriptions = []
    for fc in failed_checks:
        check_name = fc.get("check", "unknown")
        detail = fc.get("detail", "")
        failed_descriptions.append(f"{check_name}: {detail}")

    return GateResult(
        gate="RENDER-VERIFY",
        disposition="escalate",
        detail=f"{len(failed_checks)} check(s) failed for {url}",
        escalation=asdict(Escalation(
            gate="RENDER-VERIFY",
            severity="high",
            question=(
                f"Page {url} deployed but {len(failed_checks)} expected element(s) not found in rendered output:\n"
                + "\n".join(f"  - {d}" for d in failed_descriptions)
            ),
            context=f"verify-deploy report: {report.get('summary', '')}",
            post_id=post_id,
            url=url,
        )),
    )


# ───────────────────────────────────────────────────────────────────────────
# Gate B: ARTIFACT-SCAN
# ───────────────────────────────────────────────────────────────────────────

# Leaked generation artifacts — regex patterns with names
_ARTIFACT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("summary-preamble",
     re.compile(r"^#{1,3}\s*Summary\b.*$", re.MULTILINE | re.IGNORECASE)),
    ("summary-phrase",
     re.compile(r"(?:Here is|Below is|The following is)\s+a\s+summary\b", re.IGNORECASE)),
    ("markdown-fence",
     re.compile(r"```")),
    ("word-count-stat",
     re.compile(r"[~≈]\s*\d{2,5}\s*words?\b", re.IGNORECASE)),
    ("approx-word-stat",
     re.compile(r"\(approximately\s+\d+\s+words?\)", re.IGNORECASE)),
    ("meta-comment-bracket",
     re.compile(r"\[(Note|Editor|TODO|Placeholder|PLACEHOLDER|Insert|Add)\s*:", re.IGNORECASE)),
    ("throat-clearing",
     re.compile(r"(?:In this article,?\s+we (?:will|explore|cover|discuss))|(?:This article (?:covers|explores|discusses|provides))", re.IGNORECASE)),
    ("ai-identity-leak",
     re.compile(r"(?:As an AI|As a language model|I'm an AI)", re.IGNORECASE)),
    ("h1-in-body",
     re.compile(r"<h1\b[^>]*>", re.IGNORECASE)),
]


def gate_artifact_scan(
    html: str,
    post_id: int | None = None,
    auto_fix: bool = True,
) -> tuple[GateResult, str]:
    """Scan HTML for leaked generation artifacts.

    Args:
        html: The article HTML to scan.
        post_id: Optional post ID for logging.
        auto_fix: If True, strip matched artifacts and return cleaned HTML.
            If False, report only.

    Returns:
        (GateResult, cleaned_html). If no fixes, cleaned_html == html.
    """
    fixes: list[str] = []
    cleaned = html

    for name, pattern in _ARTIFACT_PATTERNS:
        matches = list(pattern.finditer(cleaned))
        if not matches:
            continue

        for m in reversed(matches):  # reverse to preserve offsets
            matched_text = m.group(0)
            # For h1-in-body: only flag if it's NOT in the first 500 chars
            # (ATF hero H1 is legitimate)
            if name == "h1-in-body" and m.start() < 500:
                continue

            context_start = max(0, m.start() - 40)
            context_end = min(len(cleaned), m.end() + 40)
            context = cleaned[context_start:context_end].replace("\n", " ")

            fix_desc = f"[{name}] Matched: '{matched_text[:80]}' | Context: ...{context}..."
            fixes.append(fix_desc)

            if auto_fix:
                if name == "h1-in-body":
                    # Replace <h1> with <h2> (don't strip the content)
                    cleaned = cleaned[:m.start()] + cleaned[m.start():m.end()].replace("<h1", "<h2").replace("</h1>", "</h2>") + cleaned[m.end():]
                    # Need to also fix the closing tag if it wasn't in this match
                    fixes[-1] += " → converted to <h2>"
                elif name == "markdown-fence":
                    cleaned = cleaned[:m.start()] + cleaned[m.end():]
                elif name in ("summary-preamble", "summary-phrase", "throat-clearing"):
                    # Remove the entire line
                    line_start = cleaned.rfind("\n", 0, m.start()) + 1
                    line_end = cleaned.find("\n", m.end())
                    if line_end == -1:
                        line_end = len(cleaned)
                    cleaned = cleaned[:line_start] + cleaned[line_end:]
                else:
                    # Remove the matched text
                    cleaned = cleaned[:m.start()] + cleaned[m.end():]

    if not fixes:
        return GateResult(
            gate="ARTIFACT-SCAN",
            disposition="pass",
            detail="No leaked artifacts detected",
        ), html

    return GateResult(
        gate="ARTIFACT-SCAN",
        disposition="auto-fix",
        detail=f"Found and {'stripped' if auto_fix else 'flagged'} {len(fixes)} artifact(s)",
        confidence=1.0,
        fixes_applied=fixes,
    ), cleaned


# ───────────────────────────────────────────────────────────────────────────
# Verification log writer
# ───────────────────────────────────────────────────────────────────────────

def write_verification_log(
    output_dir: Path,
    post_id: int,
    results: list[GateResult],
) -> Path:
    """Write the verification log JSON for a pipeline run.

    Returns the path to the log file.
    """
    escalations = [r.escalation for r in results if r.escalation]
    overall = "pass"
    if any(r.disposition == "escalate" for r in results):
        overall = "escalate"
    elif any(r.disposition == "auto-fix" for r in results):
        overall = "auto-fix"

    log = {
        "post_id": post_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gates": [asdict(r) for r in results],
        "escalations": escalations,
        "overall": overall,
    }

    log_path = output_dir / f"{post_id}-verification.json"
    log_path.write_text(json.dumps(log, indent=2))
    return log_path
