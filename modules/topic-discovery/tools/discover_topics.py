"""CLI entry point for topic discovery.

Reads site config, runs Stages 1-7 in order, writes results to SQLite,
and dumps a CSV report for human review.

Usage:
    python3 discover_topics.py --site <slug> [--stages 1-7] [--dry-run]
                               [--force-refresh]

Flags:
    --site            Site slug (e.g., 'valn', 'tln'). Required.
    --stages          Run specific stages only (e.g., '1-3' or '5,6,7').
                      Default: all stages (1-7).
    --dry-run         Print what would be done without writing to DB.
    --force-refresh   Bypass SERP cache (default 30-day TTL) and re-fetch
                      all SERP results. Use when competition landscape has
                      changed significantly.
    --verbose         Verbose logging.

Loads config from sites/<slug>.conf [topic_discovery] section.
Uses lib/db.py for database access, lib/serper_client.py for SERP,
lib/classifier.py for intent classification, lib/scorer.py for scoring.
"""
