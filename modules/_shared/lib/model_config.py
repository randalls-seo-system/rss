"""Centralized model configuration for RSS.

Updated when new models are released. Other modules import from here.
"""

# OpenAI models (for supporting tasks: meta tags, FAQ extraction, voice validation)
OPENAI_FAST_MODEL = "gpt-5.4-mini"      # high-throughput, $0.75/$4.50 per M
OPENAI_QUALITY_MODEL = "gpt-5.4"        # complex reasoning when needed

# Claude (for article body content via subscription)
CLAUDE_CONTENT_MODEL = "opus"           # passed to claude CLI as --model
CLAUDE_AUDIT_MODEL = "sonnet"           # for audits per CLAUDE.md "sonnet acceptable for non-content"

# Cost notes (as of 2026-05-06):
# gpt-5.4-mini: $0.75/M input, $4.50/M output
# gpt-5.4:      $2.50/M input, $20/M output
# Claude Opus:  Subscription (no per-token cost via CLI)
