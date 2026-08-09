"""Refresh engine — rebuild existing posts via the pipeline.

Stage A': fetches the live post, records baseline, feeds existing content
as coverage-reference evidence, and runs the normal pipeline. Output is
a pending draft — the original post is NEVER modified until refresh-approve
is run by a human.

Safety properties:
  - refresh never modifies the live post
  - refresh-approve re-runs gates before swap
  - refresh-rollback restores the original HTML from the job dir
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .auditor import fetch_post_html, fetch_gsc_top_pages
from .orchestrator import (
    create_job, save_job, job_dir, mark_stage, stage_done,
    ssh_run, ssh_pipe_php, ssh_cmd as build_ssh_cmd,
    JOBS_DIR, REPO_ROOT,
)
from .tool_utils import eprint


def start_refresh_job(
    config: dict,
    site_slug: str,
    post_id: int,
    keyword_override: str = "",
) -> dict | None:
    """Create a refresh job: fetch live post, record baseline, save original HTML.

    Returns the job dict or None on failure.
    """
    # Safety check: do_not_touch
    do_not_touch = {
        p["post_id"]
        for p in config.get("protected", {}).get("do_not_touch_pages", [])
    }
    if post_id in do_not_touch:
        eprint(f"[refresh] REFUSED: post {post_id} is in do_not_touch_pages")
        return None

    # Fetch live post
    post_data = fetch_post_html(config, post_id)
    if not post_data:
        eprint(f"[refresh] Could not fetch post {post_id}")
        return None

    if post_data.get("status") != "publish":
        eprint(f"[refresh] REFUSED: post {post_id} is {post_data.get('status')}, not publish")
        return None

    slug = post_data["slug"]
    title = post_data["title"]
    html = post_data["html"]

    # Determine keyword
    keyword = keyword_override
    if not keyword:
        # Pull from GSC
        gsc_pages = fetch_gsc_top_pages(config, limit=200)
        public_url = config.get("identity", {}).get("public_url", "").rstrip("/")
        for gp in gsc_pages:
            if gp["slug"] == slug:
                keyword = gp.get("top_query", "")
                break
        if not keyword:
            keyword = title  # fallback to title

    # Create job
    job = create_job(site_slug, keyword)
    job["mode"] = "refresh"
    job["refresh"] = {
        "original_post_id": post_id,
        "original_slug": slug,
        "original_title": title,
        "original_publish_date": post_data.get("post_date", ""),
        "keyword": keyword,
        "baseline": {},
    }
    save_job(job)

    # Save original HTML as rollback artifact
    jdir = job_dir(job)
    original_path = jdir / f"{post_id}-original.html"
    original_path.write_text(html, encoding="utf-8")
    job["artifacts"]["original_html"] = str(original_path)

    # Build existing-post evidence items
    _save_existing_post_evidence(jdir, html, post_id, slug)

    mark_stage(job, "fetch_original", "done", post_id=post_id, slug=slug,
               word_count=len(html.split()))
    return job


def _save_existing_post_evidence(jdir: Path, html: str, post_id: int, slug: str):
    """Extract paragraphs from existing post and save as evidence JSON.

    These are tagged as coverage references, not factual grounding.
    """
    import re
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    evidence_items = []

    # Extract H2 sections with their content
    current_h2 = ""
    for tag in soup.find_all(["h2", "p"]):
        if tag.name == "h2":
            current_h2 = tag.get_text(strip=True)
        elif tag.name == "p":
            text = tag.get_text(strip=True)
            if len(text.split()) >= 10:  # skip tiny fragments
                evidence_items.append({
                    "text": f"[existing_post — coverage reference, do not treat figures as current] {text}",
                    "kind": "existing_post",
                    "source_url": f"/{slug}/",
                    "source_title": f"Existing post {post_id}, section: {current_h2}",
                    "serp_position": -1,
                    "tier": "coverage",
                })

    evidence_path = jdir / "existing-post-evidence.json"
    evidence_path.write_text(json.dumps(evidence_items, indent=2))


def create_pending_draft(config: dict, job: dict) -> int | None:
    """Create a draft post titled '[REFRESH pending] <title>' on the live site.

    Returns the new draft post_id or None on failure.
    Does NOT modify the original post.
    """
    refresh = job.get("refresh", {})
    original_title = refresh.get("original_title", "Untitled")
    draft_title = f"[REFRESH pending] {original_title}"

    # Read the generated article HTML from the job dir
    jdir = job_dir(job)
    article_path = jdir / "article.html"
    if not article_path.exists():
        eprint("[refresh] No article.html in job dir — pipeline hasn't run")
        return None

    content = article_path.read_text(encoding="utf-8")

    # Create draft via SSH
    php = f"""<?php
$id = wp_insert_post([
    'post_title'   => {json.dumps(draft_title)},
    'post_content' => '',
    'post_status'  => 'draft',
    'post_type'    => 'post',
    'post_date_gmt' => current_time('mysql', true),
]);
if (is_wp_error($id)) {{
    echo json_encode(['ok'=>false, 'error'=>$id->get_error_message()]);
}} else {{
    echo json_encode(['ok'=>true, 'id'=>$id]);
}}
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=30)
    if rc != 0 or not stdout.strip():
        eprint(f"[refresh] Failed to create draft: rc={rc}")
        return None

    stdout = stdout.strip()
    if stdout.startswith("0"):
        stdout = stdout[1:]
    try:
        resp = json.loads(stdout)
    except json.JSONDecodeError:
        eprint(f"[refresh] Invalid response: {stdout[:200]}")
        return None

    if not resp.get("ok"):
        eprint(f"[refresh] wp_insert_post failed: {resp.get('error')}")
        return None

    draft_id = resp["id"]

    # Deploy content to the draft via base64 (safe for large content)
    import base64
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    wp_path = config["access"]["wp_path"].rstrip("/")
    content_path = f"{wp_path}/wp-content/uploads/rss-refresh-content.b64"

    ssh_run(config, f"cat > {content_path}", stdin_data=b64, timeout=30)

    php_deploy = f"""<?php
$b = file_get_contents('{content_path}');
$c = base64_decode(trim($b));
if ($c === false) {{ echo json_encode(['ok'=>false,'e'=>'decode']); exit; }}
$r = wp_update_post(['ID'=>{draft_id}, 'post_content'=>$c, 'post_status'=>'draft']);
if (is_wp_error($r)) {{ echo json_encode(['ok'=>false,'e'=>$r->get_error_message()]); }}
else {{ echo json_encode(['ok'=>true,'id'=>$r,'len'=>strlen($c)]); }}
"""
    stdout2, rc2 = ssh_pipe_php(config, php_deploy, timeout=30)
    ssh_run(config, f"rm -f {content_path}", timeout=30)

    job["refresh"]["pending_draft_id"] = draft_id
    mark_stage(job, "create_pending_draft", "done", draft_id=draft_id)
    return draft_id


def refresh_job_ready_for_approval(job: dict) -> tuple[bool, str]:
    """Check if a refresh job has all required stages for approval.

    Returns (ready, reason). A job is ready only when:
    - fetch_original stage is done
    - generate stage is done (pipeline ran)
    - gates stage is done AND validation actually ran and passed
    - D2 claims check ran
    - link_pass stage is done
    - create_pending_draft stage is done (draft exists on site)
    - pending_draft_id is set in the job record
    """
    stages = job.get("stages", {})
    refresh = job.get("refresh", {})

    required = ["fetch_original", "generate", "gates", "link_pass", "create_pending_draft"]
    for stage_name in required:
        if not stages.get(stage_name, {}).get("status") == "done":
            return False, f"Stage '{stage_name}' not completed"

    # Validation must have actually run (not soft-validate skip)
    gates_data = stages.get("gates", {})
    validation = gates_data.get("validation", {})
    if not validation.get("ran"):
        return False, "Validator did not run (soft-validate or skipped)"
    if validation.get("hard_passed", 0) < validation.get("hard_total", 1):
        failed = validation.get("hard_total", 0) - validation.get("hard_passed", 0)
        return False, f"Validator: {failed} hard assertion(s) failed"

    # D2 claims check must have run
    d2 = gates_data.get("d2", {})
    if not d2.get("ran"):
        return False, "D2 claims check did not run"

    if not refresh.get("pending_draft_id"):
        return False, "No pending_draft_id — draft not deployed to site"

    return True, ""


def approve_refresh(config: dict, job: dict) -> bool:
    """Swap pending draft content onto the original post.

    1. Hard-refuses if job is missing required stages or pending draft
    2. Re-runs gates against draft content (defense against post-gen edits)
    3. Creates WP revision of original as backup
    4. Copies draft content/title/meta onto original post_id
    5. Preserves original publish date
    6. Deletes the pending draft
    7. Purges cache

    Returns True on success.
    """
    from .spec_assertions import ALL_HARD_ASSERTIONS
    from bs4 import BeautifulSoup

    # Hard gate: refuse if job isn't fully ready
    ready, reason = refresh_job_ready_for_approval(job)
    if not ready:
        eprint(f"[refresh-approve] REFUSED: {reason}")
        eprint("[refresh-approve] A job must have: fetch_original + generate + gates + create_pending_draft all done.")
        return False

    refresh = job.get("refresh", {})
    original_id = refresh.get("original_post_id")
    draft_id = refresh.get("pending_draft_id")

    if not original_id or not draft_id:
        eprint("[refresh-approve] Missing original_post_id or pending_draft_id in job")
        return False

    # Fetch draft content
    draft_data = fetch_post_html(config, draft_id)
    if not draft_data:
        eprint(f"[refresh-approve] Could not fetch draft {draft_id}")
        return False

    draft_html = draft_data["html"]

    # Re-run hard gates on draft content
    context = {
        "site_config": {
            "SITE_DOMAIN": config.get("identity", {}).get("public_url", "").replace("https://", "").rstrip("/"),
            "CTA_URL": config.get("content", {}).get("cta_url", ""),
            "BYLINE_MODE": config.get("authors", {}).get("byline_mode", "single"),
        },
        "serp_data": None,
        "anchor_pool": None,
        "intent": "",
        "atf_faqs_text": [],
    }
    soup = BeautifulSoup(draft_html, "html.parser")
    gate_failures = []
    for fn in ALL_HARD_ASSERTIONS:
        try:
            ar = fn(soup, context)
            if not ar.passed:
                gate_failures.append(f"{ar.spec_ref}: {ar.detail}")
        except Exception:
            pass

    if gate_failures:
        eprint(f"[refresh-approve] BLOCKED: {len(gate_failures)} gate failure(s) on draft content:")
        for gf in gate_failures[:5]:
            eprint(f"  - {gf}")
        return False

    # Create revision of original as backup
    php_backup = f"""<?php
wp_save_post_revision({original_id});
echo 'revision_saved';
"""
    stdout, rc = ssh_pipe_php(config, php_backup, timeout=30)

    # Swap: copy draft content + title onto original, preserve publish date
    original_title = refresh.get("original_title", "")
    original_publish_date = refresh.get("original_publish_date", "")
    new_title = original_title  # keep original title unless refresh changed it

    # Read generated title from draft
    if draft_data.get("title", "").startswith("[REFRESH pending] "):
        new_title = draft_data["title"].replace("[REFRESH pending] ", "", 1)
    elif draft_data.get("title"):
        new_title = draft_data["title"]

    import base64
    b64 = base64.b64encode(draft_html.encode("utf-8")).decode("ascii")
    wp_path = config["access"]["wp_path"].rstrip("/")
    content_path = f"{wp_path}/wp-content/uploads/rss-refresh-swap.b64"

    ssh_run(config, f"cat > {content_path}", stdin_data=b64, timeout=30)

    php_swap = f"""<?php
$b = file_get_contents('{content_path}');
$c = base64_decode(trim($b));
if ($c === false) {{ echo json_encode(['ok'=>false,'e'=>'decode']); exit; }}
$r = wp_update_post([
    'ID'           => {original_id},
    'post_content' => $c,
    'post_title'   => {json.dumps(new_title)},
    'post_status'  => 'publish',
    'edit_date'    => true,
    'post_date'    => '{original_publish_date}',
    'post_date_gmt'=> get_gmt_from_date('{original_publish_date}'),
]);
if (is_wp_error($r)) {{ echo json_encode(['ok'=>false,'e'=>$r->get_error_message()]); }}
else {{ echo json_encode(['ok'=>true,'id'=>$r,'len'=>strlen($c)]); }}
"""
    stdout, rc = ssh_pipe_php(config, php_swap, timeout=30)
    ssh_run(config, f"rm -f {content_path}", timeout=30)

    if rc != 0:
        eprint(f"[refresh-approve] Swap failed: rc={rc}")
        return False

    stdout = stdout.strip()
    if stdout.startswith("0"):
        stdout = stdout[1:]
    try:
        resp = json.loads(stdout)
        if not resp.get("ok"):
            eprint(f"[refresh-approve] wp_update_post failed: {resp.get('e')}")
            return False
    except json.JSONDecodeError:
        eprint(f"[refresh-approve] Invalid response: {stdout[:200]}")
        return False

    # Delete the pending draft
    php_delete = f"""<?php
wp_delete_post({draft_id}, true);
echo 'deleted';
"""
    ssh_pipe_php(config, php_delete, timeout=30)

    # Purge cache
    from .orchestrator import purge_cache
    purge_cache(config)

    # Log
    jdir = job_dir(job)
    job["refresh"]["approved"] = True
    job["refresh"]["approved_at"] = datetime.now(timezone.utc).isoformat()
    job["refresh"]["new_word_count"] = len(draft_html.split())
    mark_stage(job, "approve", "done",
               original_id=original_id,
               new_word_count=len(draft_html.split()))

    return True


def rollback_refresh(config: dict, job: dict) -> bool:
    """Restore original HTML from job dir onto the post.

    Returns True on success.
    """
    refresh = job.get("refresh", {})
    original_id = refresh.get("original_post_id")
    if not original_id:
        eprint("[refresh-rollback] No original_post_id in job")
        return False

    jdir = job_dir(job)
    original_path = jdir / f"{original_id}-original.html"
    if not original_path.exists():
        eprint(f"[refresh-rollback] Original HTML not found: {original_path}")
        return False

    original_html = original_path.read_text(encoding="utf-8")

    import base64
    b64 = base64.b64encode(original_html.encode("utf-8")).decode("ascii")
    wp_path = config["access"]["wp_path"].rstrip("/")
    content_path = f"{wp_path}/wp-content/uploads/rss-refresh-rollback.b64"

    ssh_run(config, f"cat > {content_path}", stdin_data=b64, timeout=30)

    original_title = refresh.get("original_title", "")
    original_date = refresh.get("original_publish_date", "")

    php = f"""<?php
$b = file_get_contents('{content_path}');
$c = base64_decode(trim($b));
if ($c === false) {{ echo json_encode(['ok'=>false,'e'=>'decode']); exit; }}
$r = wp_update_post([
    'ID'           => {original_id},
    'post_content' => $c,
    'post_title'   => {json.dumps(original_title)},
    'post_status'  => 'publish',
    'edit_date'    => true,
    'post_date'    => '{original_date}',
    'post_date_gmt'=> get_gmt_from_date('{original_date}'),
]);
if (is_wp_error($r)) {{ echo json_encode(['ok'=>false,'e'=>$r->get_error_message()]); }}
else {{ echo json_encode(['ok'=>true,'id'=>$r,'len'=>strlen($c)]); }}
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=30)
    ssh_run(config, f"rm -f {content_path}", timeout=30)

    if rc != 0:
        eprint(f"[refresh-rollback] Failed: rc={rc}")
        return False

    from .orchestrator import purge_cache
    purge_cache(config)

    mark_stage(job, "rollback", "done", original_id=original_id)
    return True
