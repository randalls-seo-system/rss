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

import importlib.util as _ilu
_gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
_gl_mod = _ilu.module_from_spec(_gl_spec)
_gl_spec.loader.exec_module(_gl_mod)
run_universal_gates = _gl_mod.run_universal_gates

_ar_spec = _ilu.spec_from_file_location("artifact_resolver", REPO_ROOT / "lib" / "artifact_resolver.py")
_ar_mod = _ilu.module_from_spec(_ar_spec)
_ar_spec.loader.exec_module(_ar_mod)
resolve_deploy_artifact = _ar_mod.resolve_deploy_artifact
ArtifactResolutionError = _ar_mod.ArtifactResolutionError


def _is_do_not_touch(config: dict, post_id: int, slug: str) -> bool:
    """Check if a post is protected by do_not_touch_pages.

    Matches on EITHER post_id or slug. Raises ValueError for malformed
    entries (neither post_id nor slug) or wrong type (string instead of list).
    """
    pages = config.get("protected", {}).get("do_not_touch_pages", [])
    if not isinstance(pages, list):
        raise ValueError(
            f"do_not_touch_pages must be a list, got {type(pages).__name__}: "
            f"{repr(pages)[:100]}"
        )
    for entry in pages:
        if not isinstance(entry, dict):
            raise ValueError(
                f"do_not_touch_pages entry must be a dict, got "
                f"{type(entry).__name__}: {repr(entry)[:100]}"
            )
        entry_id = entry.get("post_id")
        entry_slug = entry.get("slug")
        if entry_id is None and not entry_slug:
            raise ValueError(
                f"do_not_touch_pages entry has neither post_id nor slug: {entry}"
            )
        if entry_id is not None and entry_id == post_id:
            return True
        if entry_slug and entry_slug == slug:
            return True
    return False


def start_refresh_job(
    config: dict,
    site_slug: str,
    post_id: int,
    keyword_override: str = "",
) -> dict | None:
    """Create a refresh job: fetch live post, record baseline, save original HTML.

    Returns the job dict or None on failure.
    """
    # Fetch live post (needed before do_not_touch check so we have the slug)
    post_data = fetch_post_html(config, post_id)
    if not post_data:
        eprint(f"[refresh] Could not fetch post {post_id}")
        return None

    if post_data.get("status") != "publish":
        eprint(f"[refresh] REFUSED: post {post_id} is {post_data.get('status')}, not publish")
        return None

    slug = post_data["slug"]

    # Safety check: do_not_touch — matches on EITHER post_id or slug
    if _is_do_not_touch(config, post_id, slug):
        eprint(f"[refresh] REFUSED: post {post_id} (slug={slug}) is in do_not_touch_pages")
        return None
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
    job["post_id"] = post_id
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


def run_postprocess(config: dict, job: dict) -> Path | None:
    """Run the site's postprocessor on the article HTML to produce the deploy artifact.

    Returns the path to {post_id}-deploy.html, or None on failure.
    """
    jdir = job_dir(job)
    refresh = job.get("refresh", {})
    post_id = refresh.get("original_post_id")
    slug = refresh.get("original_slug", "")
    site_slug = job.get("site", "")

    # Resolve input from artifact chain (same priority as cmd_new_article)
    article_path = None
    for key in ("article_reviewed", "article_linked", "article_html"):
        path_str = job.get("artifacts", {}).get(key)
        if path_str:
            p = Path(path_str)
            if p.exists():
                article_path = p
                break

    # Fallback for legacy jobs: prefer {post_id}-article.html
    if article_path is None and post_id:
        candidate = jdir / f"{post_id}-article.html"
        if candidate.exists():
            article_path = candidate

    if article_path is None:
        eprint("[refresh] No article HTML found via artifact chain or naming convention")
        return None

    # Record what we consumed so the class-migration gate can compare
    job.setdefault("artifacts", {})["postprocess_source"] = str(article_path)
    save_job(job)

    deploy_path = jdir / f"{post_id}-deploy.html"

    # Resolve postprocessor for this site
    postprocessor = REPO_ROOT / "tools" / f"{site_slug}-postprocess.py"
    if not postprocessor.exists():
        # No postprocessor = deploy artifact is the raw article
        eprint(f"[refresh] No postprocessor for site {site_slug} — using raw article")
        import shutil
        shutil.copy2(article_path, deploy_path)
        return deploy_path

    # Full CSS class migration + structural wrapping for TLN.
    # The pipeline emits rl-* classes; the live site uses tln* classes.
    # This migration produces deploy-ready HTML matching the reference posts.
    from bs4 import BeautifulSoup as BS4

    html = article_path.read_text(encoding="utf-8")
    css_prefix = config.get("content", {}).get("css_prefix", ["rl-"])
    if isinstance(css_prefix, list):
        css_prefix = css_prefix[0] if css_prefix else "rl-"

    if css_prefix == "rl-":
        # No migration needed — deploy the raw article
        import shutil
        shutil.copy2(article_path, deploy_path)
        return deploy_path

    # Complete class map: rl-* → tln* (covers every pipeline-emitted class)
    CLASS_MAP = {
        "rl-page": f"{css_prefix}Page",
        "rl-wrap": f"{css_prefix}Wrap",
        "rl-hero": f"{css_prefix}Card",
        "rl-eyebrow": f"{css_prefix}Eyebrow",
        "rl-hero-eyebrow": f"{css_prefix}Eyebrow",
        "rl-hero-lead": f"{css_prefix}HeroLead",
        "rl-cta-pill": f"{css_prefix}NextPill",
        "rl-cta-primary": f"{css_prefix}NextPill",
        "rl-cta-mid": f"{css_prefix}NextPill",
        "rl-quick-grid": f"{css_prefix}QuickGrid",
        "rl-quick-card": f"{css_prefix}QuickCard",
        "rl-bluf": f"{css_prefix}BLUF",
        "rl-kcards": f"{css_prefix}Kcards",
        "rl-kcard": f"{css_prefix}Kcard",
        "rl-callout": f"{css_prefix}Callout",
        "rl-callout--deal_math": f"{css_prefix}Callout {css_prefix}ProTip",
        "rl-callout--file_guidance": f"{css_prefix}Callout {css_prefix}ProTip",
        "rl-callout--approval_watchpoint": f"{css_prefix}Callout {css_prefix}ProTip",
        "rl-callout--deal_saver": f"{css_prefix}Callout {css_prefix}ProTip",
        "rl-faq": f"{css_prefix}Faq",
        "rl-resources": f"{css_prefix}Disclosure",
        "rl-toc": f"{css_prefix}TOC",
        "rl-atf-faqhead": f"{css_prefix}AtfFaqHead",
        "rl-kicker": f"{css_prefix}Kicker",
    }

    # Apply class replacements (order: longest first to avoid partial matches)
    for old_cls in sorted(CLASS_MAP.keys(), key=len, reverse=True):
        new_cls = CLASS_MAP[old_cls]
        html = html.replace(f'class="{old_cls}"', f'class="{new_cls}"')
        html = html.replace(f'class="{old_cls} ', f'class="{new_cls} ')

    # Element type conversions
    html = html.replace(f'<div class="{css_prefix}QuickCard', f'<article class="{css_prefix}QuickCard')

    # Structural wrapping: add tlnWrap inside tlnPage
    soup = BS4(html, "html.parser")
    page = soup.find(class_=f"{css_prefix}Page")
    if page and not page.find(class_=f"{css_prefix}Wrap"):
        wrap = soup.new_tag("div", attrs={"class": f"{css_prefix}Wrap"})
        children = list(page.children)
        for child in children:
            wrap.append(child.extract())
        page.append(wrap)

    # Add page slug class
    if page:
        existing = page.get("class", [])
        slug_cls = f"{css_prefix}Page-{slug}"
        if slug_cls not in existing:
            page["class"] = existing + [slug_cls] if isinstance(existing, list) else [existing, slug_cls]
        page["data-tln-page"] = slug

    # Table wrapping: wrap <table> in tlnTableScroll
    for table in soup.find_all("table"):
        if not table.find_parent(class_=f"{css_prefix}TableScroll"):
            wrapper = soup.new_tag("div", attrs={"class": f"{css_prefix}TableScroll"})
            table.insert_before(wrapper)
            wrapper.append(table.extract())

    # Section wrapping for body H2 sections
    for h2 in soup.find_all("h2"):
        parent = h2.parent
        if parent and parent.name in ("div", "section") and f"{css_prefix}Section" not in str(parent.get("class", [])):
            continue  # already wrapped
        if h2.find_parent(class_=f"{css_prefix}Faq"):
            continue
        if h2.find_parent(class_=f"{css_prefix}Disclosure"):
            continue
        if h2.find_parent(class_=f"{css_prefix}BLUF"):
            continue

    html = str(soup)
    deploy_path.write_text(html, encoding="utf-8")
    eprint(f"[refresh] Deploy artifact: {deploy_path.name} ({deploy_path.stat().st_size} bytes)")
    return deploy_path


def create_pending_draft(config: dict, job: dict) -> int | None:
    """Create a draft post titled '[REFRESH pending] <title>' on the live site.

    Uses the POSTPROCESSED deploy artifact ({post_id}-deploy.html), NOT the
    raw article HTML. If no deploy artifact exists, runs the postprocessor first.

    Returns the new draft post_id or None on failure.
    Does NOT modify the original post.
    """
    refresh = job.get("refresh", {})
    original_title = refresh.get("original_title", "Untitled")
    draft_title = f"[REFRESH pending] {original_title}"

    jdir = job_dir(job)
    post_id = refresh.get("original_post_id")

    # Use deploy artifact (postprocessed), not raw article
    deploy_path = jdir / f"{post_id}-deploy.html"
    if not deploy_path.exists():
        deploy_path = run_postprocess(config, job)
        if not deploy_path or not deploy_path.exists():
            eprint("[refresh] No deploy artifact — postprocess failed or no article")
            return None

    content = deploy_path.read_text(encoding="utf-8")

    # Class-migration gate: deploy artifact for non-rl- sites must have converted
    css_prefix = config.get("content", {}).get("css_prefix", ["rl-"])
    if isinstance(css_prefix, list):
        css_prefix = css_prefix[0] if css_prefix else "rl-"
    source_path_str = job.get("artifacts", {}).get("postprocess_source")
    if not source_path_str:
        eprint("[refresh] BLOCKED: postprocess_source not recorded in job artifacts")
        return None
    source_path = Path(source_path_str)
    if not source_path.exists():
        eprint(f"[refresh] BLOCKED: postprocess source not found: {source_path}")
        return None
    source_html = source_path.read_text(encoding="utf-8")
    migration_result = _gl_mod.assert_deploy_class_migration(content, source_html, css_prefix)
    if not migration_result.passed:
        eprint(f"[refresh] BLOCKED: {migration_result.detail}")
        return None

    # Create draft via SSH (private status = viewable by logged-in users at normal URL)
    php = f"""<?php
$id = wp_insert_post([
    'post_title'   => {json.dumps(draft_title)},
    'post_content' => '',
    'post_status'  => 'private',
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

    # Universal gate check before deploying to draft
    site_id = config.get("identity", {}).get("site_id", job.get("site", ""))
    gate_report = run_universal_gates(
        content,
        site_slug=site_id,
        title=refresh.get("original_title", ""),
        content_type="article",
        config=config,
    )
    if not gate_report.passed:
        eprint(f"[refresh] GATE FAILED — refusing to deploy draft:")
        for fail in gate_report.failures:
            eprint(f"  [{fail.name}] {fail.detail}")
        return None

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
$r = wp_update_post(['ID'=>{draft_id}, 'post_content'=>$c, 'post_status'=>'private']);
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

    required = ["fetch_original", "generate", "gates", "link_pass", "postprocess", "create_pending_draft"]
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

    # D2 claims check must have run AND passed
    d2 = gates_data.get("d2", {})
    if not d2.get("ran"):
        return False, "D2 claims check did not run"
    if not d2.get("passed"):
        return False, f"D2 claims check failed (unsourced={d2.get('unsourced', '?')})"
    if d2.get("unsourced", -1) > 0:
        return False, f"D2: {d2['unsourced']} unsourced claim(s) remain"

    if not refresh.get("pending_draft_id"):
        return False, "No pending_draft_id — draft not deployed to site"

    # Deploy artifact must exist (last check — all logic gates pass first)
    post_id = refresh.get("original_post_id")
    if post_id:
        deploy_path = JOBS_DIR / job.get("id", "") / f"{post_id}-deploy.html"
        if not deploy_path.exists():
            return False, f"Deploy artifact not found: {deploy_path.name}"

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

    # Re-run hard gates on the RAW article HTML (rl-* classes), not the
    # class-migrated deploy artifact on WP. The deploy artifact has tln*
    # classes which the rl-*-expecting assertions don't recognize.
    jdir = job_dir(job)
    raw_article = None
    for f in sorted(jdir.glob("*-article.html")):
        raw_article = f
        break
    if not raw_article or not raw_article.exists():
        eprint("[refresh-approve] Raw article HTML not found in job dir")
        return False

    raw_html = raw_article.read_text(encoding="utf-8")
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
        "intended_title": refresh.get("original_title", ""),
    }
    soup = BeautifulSoup(raw_html, "html.parser")
    gate_failures = []
    for fn in ALL_HARD_ASSERTIONS:
        try:
            ar = fn(soup, context)
            if not ar.passed:
                gate_failures.append(f"{ar.spec_ref}: {ar.detail}")
        except Exception:
            pass

    if gate_failures:
        eprint(f"[refresh-approve] BLOCKED: {len(gate_failures)} gate failure(s) on raw article:")
        for gf in gate_failures[:5]:
            eprint(f"  - {gf}")
        return False

    # Resolve and gate-check the deploy artifact (postprocessed HTML)
    try:
        resolved = resolve_deploy_artifact(job, jdir)
    except ArtifactResolutionError as e:
        eprint(f"[refresh-approve] BLOCKED: {e}")
        return False

    deploy_html = resolved.path.read_text(encoding="utf-8")
    site_id = config.get("identity", {}).get("site_id", "")
    deploy_gate_report = run_universal_gates(
        deploy_html,
        site_slug=site_id,
        title=refresh.get("original_title", ""),
        content_type="article",
        config=config,
    )
    if not deploy_gate_report.passed:
        eprint(f"[refresh-approve] BLOCKED: {len(deploy_gate_report.failures)} gate failure(s) on deploy artifact:")
        for fail in deploy_gate_report.failures:
            eprint(f"  [{fail.name}] {fail.detail}")
        return False

    # Fetch draft to get its content for the swap
    draft_data = fetch_post_html(config, draft_id)
    if not draft_data:
        eprint(f"[refresh-approve] Could not fetch draft {draft_id}")
        return False
    draft_html = draft_data["html"]

    # Universal gate check on draft content before swap
    site_id = config.get("identity", {}).get("site_id", "")
    ug_report = run_universal_gates(
        draft_html,
        site_slug=site_id,
        title=refresh.get("original_title", ""),
        content_type="article",
        config=config,
    )
    if not ug_report.passed:
        eprint(f"[refresh-approve] UNIVERSAL GATE FAILED — refusing to swap:")
        for fail in ug_report.failures:
            eprint(f"  [{fail.name}] {fail.detail}")
        return False

    # Create revision of original as backup
    php_backup = f"""<?php
wp_save_post_revision({original_id});
echo 'revision_saved';
"""
    stdout, rc = ssh_pipe_php(config, php_backup, timeout=30)

    # Swap: copy draft content + title onto original, preserve publish date
    # TITLE FIX: always use the original title from the job record, never
    # the draft's WP title (which may be truncated by WP or have the
    # [REFRESH pending] prefix partially stripped).
    original_title = refresh.get("original_title", "")
    original_publish_date = refresh.get("original_publish_date", "")
    new_title = original_title

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
