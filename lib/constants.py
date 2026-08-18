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
