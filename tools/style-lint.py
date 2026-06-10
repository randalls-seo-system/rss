#!/usr/bin/env python3
"""style-lint — standalone style gate for pipeline or CLI use.

Checks a single HTML file for style violations that should block emit.
Hard-fails with the offending sentence printed.

Gates:
  1. Em dash exists anywhere in body text
  2. Semicolon density > 1 per 300 words
  3. Any Tier 2 AI-lexicon hit (delve, navigate, leverage, etc.)
  4. AI phrase patterns (in today's * landscape, it's important to note, etc.)
  5. "It's not X, it's Y" construction

Usage:
    python3 style-lint.py article.html
    python3 style-lint.py --html-string '<div>content here</div>'

Exit 0 = clean. Exit 1 = violations found (printed to stderr).
"""

import re
import sys
from pathlib import Path

EM_DASH = "\u2014"

AI_LEXICON = [
    "delve", "navigate", "leverage", "robust", "comprehensive",
    "crucial", "essential", "seamless", "holistic",
]
AI_LEXICON_RE = re.compile(
    "|".join(r"\b" + re.escape(w) + r"\b" for w in AI_LEXICON),
    re.IGNORECASE,
)

AI_PHRASE_PATTERNS = [
    re.compile(r"in today'?s\s+\w+\s+landscape", re.I),
    re.compile(r"it'?s important to note", re.I),
    re.compile(r"when it comes to\b", re.I),
]

NOT_X_ITS_Y_RE = re.compile(
    r"(?:it'?s|that'?s)\s+not\s+\w[\w\s,]{2,40}[,;]\s*(?:it'?s|that'?s)\s+\w",
    re.IGNORECASE,
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _extract_text(html: str) -> str:
    """Extract visible text from HTML, stripping tags."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "code", "pre"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _find_sentence_around(text: str, pos: int) -> str:
    """Extract the sentence containing position `pos`."""
    start = max(0, text.rfind(". ", 0, pos) + 2)
    end = text.find(". ", pos)
    if end == -1:
        end = len(text)
    else:
        end += 1
    return text[start:end].strip()[:150]


def lint(html: str) -> list[str]:
    """Run all style gates. Returns list of violation messages (empty = clean)."""
    text = _extract_text(html)
    violations = []

    # Gate 1: em dash
    idx = text.find(EM_DASH)
    if idx != -1:
        sentence = _find_sentence_around(text, idx)
        violations.append(f"EM DASH found: \"{sentence}\"")

    # Gate 2: semicolon density
    wc = _word_count(text)
    entity_semis = len(re.findall(r"&\w+;", text))
    prose_semis = text.count(";") - entity_semis
    if wc > 0 and prose_semis > max(1, wc // 300):
        idx = text.find(";")
        sentence = _find_sentence_around(text, idx) if idx != -1 else ""
        violations.append(
            f"SEMICOLON DENSITY {prose_semis} in {wc} words "
            f"(max {max(1, wc // 300)}): \"{sentence}\""
        )

    # Gate 3: AI lexicon
    for m in AI_LEXICON_RE.finditer(text):
        sentence = _find_sentence_around(text, m.start())
        violations.append(f"AI LEXICON \"{m.group()}\": \"{sentence}\"")

    # Gate 4: AI phrases
    for pat in AI_PHRASE_PATTERNS:
        for m in pat.finditer(text):
            sentence = _find_sentence_around(text, m.start())
            violations.append(f"AI PHRASE \"{m.group()}\": \"{sentence}\"")

    # Gate 5: not X, it's Y
    for m in NOT_X_ITS_Y_RE.finditer(text):
        sentence = _find_sentence_around(text, m.start())
        violations.append(f"NOT-X-ITS-Y \"{m.group()[:60]}\": \"{sentence}\"")

    return violations


def main():
    if len(sys.argv) < 2:
        print("Usage: style-lint.py <html-file> [--html-string '<html>']",
              file=sys.stderr)
        sys.exit(2)

    if sys.argv[1] == "--html-string":
        html = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
    else:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(2)
        html = path.read_text()

    violations = lint(html)

    if violations:
        print(f"STYLE LINT FAILED — {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  FAIL: {v}", file=sys.stderr)
        sys.exit(1)
    else:
        print("STYLE LINT PASSED", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
