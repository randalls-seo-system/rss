"""Duplicate-prevention guards for the content pipeline.

Prevents the pipeline from generating content for a topic/neighborhood
that already has a published post, and detects WordPress slug collisions
(-2 suffix) that indicate a duplicate was created.

Root cause (2026-08-03 audit): three batch events (Sep-Oct 2025,
Dec 2025, Jun 2026) each created duplicate posts because the pipeline
had no pre-generation dupe check. This module closes that gap.
"""

import os
import re
import subprocess
from pathlib import Path

from .site_config import load_site_config
from .tool_utils import eprint


def _ssh_base(config: dict) -> list[str]:
    """Build SSH command prefix from site config."""
    ssh_host = config.get("SSH_HOST", "")
    ssh_user = config.get("SSH_USER", "")
    ssh_key = config.get("SSH_KEY_PATH", "")
    if ssh_key:
        ssh_key = os.path.expanduser(ssh_key)

    if not ssh_host or not ssh_user:
        return []

    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]
    if ssh_key:
        cmd += ["-i", ssh_key, "-o", "IdentitiesOnly=yes"]
    cmd.append(f"{ssh_user}@{ssh_host}")
    return cmd


def _run_wp_cli(config: dict, wp_cli_cmd: str) -> str:
    """Run a WP-CLI command via SSH and return stdout."""
    ssh = _ssh_base(config)
    if not ssh:
        return ""
    cmd = ssh + [wp_cli_cmd]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _run_sql_query(config: dict, sql: str) -> str:
    """Run a SQL query via SSH + wp db query with stdin piping."""
    ssh = _ssh_base(config)
    if not ssh:
        return ""
    cmd = ssh + ["wp db query --skip-column-names"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            input=sql,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _slug_tokens(text: str) -> set[str]:
    """Extract meaningful tokens from a neighborhood/topic name."""
    stop = {
        "best", "top", "guide", "neighborhood", "neighborhoods", "in",
        "to", "the", "for", "live", "living", "of", "a", "and", "how",
        "your", "tx", "texas", "san", "antonio", "austin", "killeen",
    }
    parts = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return {p for p in parts if p not in stop and len(p) > 1}


def check_existing_neighborhood_guide(
    site_slug: str,
    neighborhood: str,
    post_id: int,
) -> list[dict]:
    """Check if a published guide already exists for this neighborhood.

    Returns a list of existing post dicts: [{"id": int, "slug": str, "title": str}]
    Empty list means no duplicates found.
    """
    config = load_site_config(site_slug)
    ssh = _ssh_base(config)
    if not ssh:
        eprint("[dupe-guard] WARNING: Cannot SSH to check for duplicates (no SSH config)")
        return []

    tokens = _slug_tokens(neighborhood)
    if not tokens:
        return []

    # Strategy: run TWO searches and union the results.
    # 1. Slug compound match: "Circle C Ranch" → search for "circle-c" in slugs
    #    (catches differently-named guides for the same neighborhood)
    # 2. All-tokens-in-slug match: all tokens must appear in the slug
    #    (catches exact-format duplicates)
    # 3. Title match: all tokens appear in the title
    #    (catches guides with non-standard slugs like "2025-guide-circle-c-...")

    # Build the slug compound (e.g., "circle-c" from "Circle C Ranch")
    slug_compound = re.sub(r"[^a-z0-9]+", "-", neighborhood.lower()).strip("-")
    # Use the first 2-3 hyphenated segments as the core compound
    compound_parts = slug_compound.split("-")
    if len(compound_parts) >= 2:
        core_compound = "-".join(compound_parts[:2])  # "circle-c"
    else:
        core_compound = compound_parts[0]

    # Build WHERE clauses
    all_slug_likes = " AND ".join(f"post_name LIKE '%{t}%'" for t in tokens)
    all_title_likes = " AND ".join(f"post_title LIKE '%{t}%'" for t in tokens)
    compound_like = f"post_name LIKE '%{core_compound}%'"

    sql = (
        f"SELECT DISTINCT ID, post_name, post_title FROM wp_posts "
        f"WHERE post_status='publish' AND post_type='post' "
        f"AND ID != {int(post_id)} "
        f"AND (({all_slug_likes}) OR ({compound_like}) OR ({all_title_likes}));"
    )

    output = _run_sql_query(config, sql)

    if not output:
        return []

    matches = []
    for line in output.strip().split("\n"):
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            matches.append({
                "id": int(parts[0]),
                "slug": parts[1],
                "title": parts[2],
            })

    return matches


def check_slug_collision(
    site_slug: str,
    post_id: int,
) -> str | None:
    """Check if the given post's slug has a -2/-3/-N suffix (collision evidence).

    Returns the _wp_old_slug value if collision detected, None otherwise.
    """
    config = load_site_config(site_slug)

    # Check for _wp_old_slug meta (WP sets this when auto-deduplicating)
    old_slug = _run_wp_cli(
        config,
        f"wp post meta get {post_id} _wp_old_slug"
    )
    if old_slug:
        return old_slug

    # Also check if the current slug ends in -2, -3, etc.
    current_slug = _run_wp_cli(
        config,
        f"wp post get {post_id} --field=post_name"
    )
    if current_slug and re.search(r"-\d+$", current_slug):
        return f"(slug ends with numeric suffix: {current_slug})"

    return None


def check_existing_by_keyword(
    site_slug: str,
    target_keyword: str,
    post_id: int,
) -> list[dict]:
    """Check if a published post already targets a similar keyword.

    Used by assemble-article.py. Matches slug tokens from the keyword
    against existing published post slugs.
    """
    config = load_site_config(site_slug)
    tokens = _slug_tokens(target_keyword)
    if len(tokens) < 2:
        return []

    # Use top 3 most distinctive tokens (skip very short ones)
    ranked = sorted(tokens, key=len, reverse=True)[:3]
    like_parts = " AND ".join(
        f"post_name LIKE '%{t}%'" for t in ranked
    )

    sql = (
        f"SELECT ID, post_name, post_title FROM wp_posts "
        f"WHERE post_status='publish' AND post_type='post' "
        f"AND ID != {int(post_id)} AND ({like_parts});"
    )

    output = _run_sql_query(config, sql)

    if not output:
        return []

    matches = []
    for line in output.strip().split("\n"):
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            matches.append({
                "id": int(parts[0]),
                "slug": parts[1],
                "title": parts[2],
            })
    return matches


def run_dupe_guard_neighborhood(
    site_slug: str,
    neighborhood: str,
    post_id: int,
    force_new: bool = False,
) -> int | None:
    """Full dupe guard for neighborhood guide generation.

    Returns:
        None if no duplicate found (safe to proceed).
        Existing post ID if duplicate found and force_new=False (caller should stop).
        None if duplicate found but force_new=True (proceed with warning).

    Raises SystemExit if slug collision detected (always fatal).
    """
    eprint(f"[dupe-guard] Checking for existing guides: '{neighborhood}'")

    # 1. Check for slug collision on the target post
    collision = check_slug_collision(site_slug, post_id)
    if collision:
        eprint(f"[dupe-guard] SLUG COLLISION DETECTED on post {post_id}")
        eprint(f"[dupe-guard]   Evidence: {collision}")
        eprint(f"[dupe-guard]   WordPress auto-appended a suffix because this slug")
        eprint(f"[dupe-guard]   already existed. This post is likely a duplicate.")
        eprint(f"[dupe-guard]   HARD STOP — resolve the collision before proceeding.")
        raise SystemExit(1)

    # 2. Check for existing published guides covering this neighborhood
    existing = check_existing_neighborhood_guide(site_slug, neighborhood, post_id)
    if not existing:
        eprint(f"[dupe-guard] No existing guides found for '{neighborhood}' — clear to proceed")
        return None

    eprint(f"[dupe-guard] DUPLICATE DETECTED — {len(existing)} existing post(s) "
           f"cover '{neighborhood}':")
    for ex in existing:
        eprint(f"[dupe-guard]   ID {ex['id']:>5} | {ex['slug']}")
        eprint(f"[dupe-guard]           {ex['title']}")

    if force_new:
        eprint(f"[dupe-guard] --force-new specified — proceeding despite duplicate.")
        eprint(f"[dupe-guard] WARNING: This will create a SECOND guide for '{neighborhood}'.")
        eprint(f"[dupe-guard] Consider using --post-id {existing[0]['id']} to UPDATE instead.")

        # Persistent log — catchable after batch runs
        log_dir = Path.home() / "randalls-seo-system" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "dupe-guard-overrides.log"
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        existing_ids = ", ".join(str(ex["id"]) for ex in existing)
        entry = (
            f"[{ts}] FORCE-NEW OVERRIDE: site={site_slug} "
            f"neighborhood='{neighborhood}' new_post_id={post_id} "
            f"existing_post_ids=[{existing_ids}]\n"
        )
        with open(log_path, "a") as f:
            f.write(entry)
        eprint(f"[dupe-guard] Override logged to {log_path}")

        return None
    else:
        eprint(f"[dupe-guard] HARD STOP — a guide already exists for '{neighborhood}'.")
        eprint(f"[dupe-guard] To UPDATE the existing guide, use: --post-id {existing[0]['id']}")
        eprint(f"[dupe-guard] To force a new post anyway, add: --force-new")
        return existing[0]["id"]


def run_dupe_guard_article(
    site_slug: str,
    target_keyword: str,
    post_id: int,
    force: bool = False,
) -> int | None:
    """Lightweight dupe guard for assemble-article.py.

    Returns None if safe to proceed, existing post ID if duplicate found.
    """
    # 1. Slug collision check
    collision = check_slug_collision(site_slug, post_id)
    if collision:
        eprint(f"[dupe-guard] SLUG COLLISION DETECTED on post {post_id}")
        eprint(f"[dupe-guard]   Evidence: {collision}")
        eprint(f"[dupe-guard]   HARD STOP — resolve the collision before proceeding.")
        raise SystemExit(1)

    # 2. Keyword similarity check (only when force is not set)
    if force:
        return None

    existing = check_existing_by_keyword(site_slug, target_keyword, post_id)
    if existing:
        eprint(f"[dupe-guard] WARNING — {len(existing)} existing post(s) may cover "
               f"'{target_keyword}':")
        for ex in existing:
            eprint(f"[dupe-guard]   ID {ex['id']:>5} | {ex['slug']}")
        eprint(f"[dupe-guard] If this is an intentional update, the existing post ID is correct.")
        eprint(f"[dupe-guard] If this is a NEW article, verify it doesn't duplicate the above.")
        # Soft warning only — assemble-article always requires a post_id,
        # so the operator already chose which post to target.

    return None
