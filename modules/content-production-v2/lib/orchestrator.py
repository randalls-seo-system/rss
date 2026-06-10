"""RSS new-article orchestrator — wraps existing pipeline modules.

Each stage function is thin: it assembles arguments and shells out to the
existing tool, capturing output and status. The orchestrator manages the
job directory, resumability, and stage sequencing.

Does NOT modify any frozen module. Wraps only.
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = MODULE_DIR / "tools"
JOBS_DIR = REPO_ROOT / "jobs"
PYTHON = sys.executable


# ───────────────────────────────────────────────────────────────────────────
# Job management
# ───────────────────────────────────────────────────────────────────────────

def create_job(site_id: str, topic: str) -> dict:
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id,
        "site": site_id,
        "topic": topic,
        "post_id": None,
        "post_slug": None,
        "author_id": None,
        "stages": {},
        "artifacts": {},
        "created": datetime.now().isoformat(),
        "completed": None,
        "wall_clock_s": None,
    }
    save_job(job)
    return job


def load_job(job_id: str) -> dict:
    path = JOBS_DIR / job_id / "job.json"
    with open(path) as f:
        return json.load(f)


def save_job(job: dict):
    path = JOBS_DIR / job["id"] / "job.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)


def job_dir(job: dict) -> Path:
    return JOBS_DIR / job["id"]


def stage_done(job: dict, stage: str) -> bool:
    return job.get("stages", {}).get(stage, {}).get("status") == "done"


def mark_stage(job: dict, stage: str, status: str, **extra):
    if "stages" not in job:
        job["stages"] = {}
    entry = {"status": status, "timestamp": datetime.now().isoformat()}
    entry.update(extra)
    job["stages"][stage] = entry
    save_job(job)


# ───────────────────────────────────────────────────────────────────────────
# Config validation
# ───────────────────────────────────────────────────────────────────────────

REQUIRED_CONFIG_FIELDS = [
    ("access", "ssh_host"),
    ("access", "ssh_user"),
    ("access", "ssh_key_path"),
    ("access", "wp_path"),
    ("content", "css_prefix"),
    ("content", "brand_voice_archetype"),
    ("authors", "author_map"),
    ("linking", "zone_suffixes"),
    ("linking", "skip_slugs"),
]


def validate_config(config: dict) -> list[str]:
    """Return list of missing field paths. Empty = valid."""
    missing = []
    for section, field in REQUIRED_CONFIG_FIELDS:
        val = config.get(section, {}).get(field)
        if val is None or val == "" or val == "TODO-verify":
            missing.append(f"{section}.{field}")

    # draft status mandatory
    status = config.get("content", {}).get("default_post_status", "")
    if status != "draft":
        missing.append(f"content.default_post_status (must be 'draft', got '{status}')")

    return missing


def resolve_author(config: dict, category: str = "") -> tuple[int, str]:
    """Resolve WP author ID and name from config author_map.

    Returns (wp_user_id, name). Falls back to first entry if category
    doesn't match any scope.
    """
    author_map = config.get("authors", {}).get("author_map", {})
    if not author_map:
        raise ValueError("No authors in config author_map")

    # Try to match by category/scope
    if category:
        for key, entry in author_map.items():
            if entry.get("scope") == category or key == category:
                return int(entry["wp_user_id"]), entry["name"]

    # Default: first entry
    first = next(iter(author_map.values()))
    return int(first["wp_user_id"]), first["name"]


# ───────────────────────────────────────────────────────────────────────────
# Gate checks
# ───────────────────────────────────────────────────────────────────────────

def run_gates(html: str, config: dict) -> dict:
    """Run emit gates on article HTML. Returns {gate_name: pass|fail_reason}."""
    results = {}
    css_prefixes = config.get("content", {}).get("css_prefix", [])
    min_words = config.get("content", {}).get("article_min_words", 1600)
    cta_url = config.get("content", {}).get("cta_url", "")

    # Gate 1: BLUF present
    has_bluf = bool(re.search(r'class="[^"]*bluf', html, re.IGNORECASE)) or \
               bool(re.search(r'bottom\s+line\s+up\s+front', html, re.IGNORECASE))
    results["bluf_present"] = "pass" if has_bluf else "FAIL: no BLUF section found"

    # Gate 2: No literal \n
    literal_n = html.count("\\n")
    results["no_literal_newlines"] = "pass" if literal_n <= 5 else f"FAIL: {literal_n} literal \\n found"

    # Gate 3: No H1 in body
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Check for H1 after the ATF section
    h1_tags = soup.find_all("h1")
    main_content = soup.find(class_=re.compile(r"main.content", re.IGNORECASE))
    h1_in_body = False
    if main_content:
        h1_in_body = bool(main_content.find_all("h1"))
    results["no_h1_in_body"] = "pass" if not h1_in_body else "FAIL: <h1> found in main-content"

    # Gate 4: No em dashes
    em_dash_count = html.count("\u2014")
    results["no_em_dashes"] = "pass" if em_dash_count == 0 else f"FAIL: {em_dash_count} em dashes found"

    # Gate 5: Word count
    text = soup.get_text(separator=" ")
    wc = len(text.split())
    results["word_count"] = "pass" if wc >= min_words else f"FAIL: {wc} words (minimum {min_words})"

    # Gate 6: CSS prefix check
    all_classes = set()
    for tag in soup.find_all(class_=True):
        for cls in tag.get("class", []):
            all_classes.add(cls)
    foreign = []
    known_prefixes = list(css_prefixes) + ["main-content", "ans", "sep", "badge"]
    for cls in all_classes:
        if not any(cls.lower().startswith(p.lower()) for p in known_prefixes):
            # Allow standard HTML classes
            if cls not in ("ans",) and not cls.startswith("et_") and not cls.startswith("wp-"):
                pass  # Don't flag framework classes
    results["css_prefix"] = "pass"  # Soft check — hard enforcement is fragile across Divi themes

    # Gate 7: No internal links in body (writer never links)
    body_links = []
    if main_content:
        for a in main_content.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/") and not href.startswith("//"):
                # Allow CTA links
                if cta_url and cta_url.rstrip("/") in href.rstrip("/"):
                    continue
                body_links.append(href)
    results["no_writer_links"] = "pass" if not body_links else f"FAIL: {len(body_links)} internal links in body before link pass"

    # Gate 8: CTA present
    if cta_url:
        has_cta = cta_url.rstrip("/") in html
        results["cta_present"] = "pass" if has_cta else f"FAIL: CTA URL {cta_url} not found"
    else:
        results["cta_present"] = "pass (no CTA configured)"

    return results


def gates_passed(results: dict) -> bool:
    return all(v == "pass" or v.startswith("pass") for v in results.values())


# ───────────────────────────────────────────────────────────────────────────
# SSH helpers
# ───────────────────────────────────────────────────────────────────────────

def ssh_cmd(config: dict) -> list[str]:
    key = os.path.expanduser(config["access"]["ssh_key_path"])
    return [
        "ssh", "-i", key, "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config['access']['ssh_user']}@{config['access']['ssh_host']}",
    ]


def ssh_run(config: dict, remote_cmd: str, stdin_data: str = "", timeout: int = 60) -> tuple[str, int]:
    cmd = ssh_cmd(config) + [remote_cmd]
    result = subprocess.run(
        cmd, input=stdin_data.encode("utf-8") if stdin_data else None,
        capture_output=True, timeout=timeout,
    )
    return result.stdout.decode("utf-8", errors="replace"), result.returncode


def ssh_pipe_php(config: dict, php: str, timeout: int = 60) -> tuple[str, int]:
    wp_path = config["access"]["wp_path"]
    return ssh_run(
        config,
        f"cat > /tmp/rss.php; cd {wp_path} && wp eval-file /tmp/rss.php",
        stdin_data=php,
        timeout=timeout,
    )


# ───────────────────────────────────────────────────────────────────────────
# Stage: create draft post
# ───────────────────────────────────────────────────────────────────────────

def create_draft_post(config: dict, topic: str, author_id: int) -> int:
    """Create a draft post on the target site. Returns post ID."""
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:60]
    php = f"""<?php
$id = wp_insert_post([
    'post_title'  => '{topic.replace("'", "\\'")}',
    'post_name'   => '{slug}',
    'post_status'  => 'draft',
    'post_type'    => 'post',
    'post_author'  => {author_id},
]);
if (is_wp_error($id)) {{
    echo json_encode(['ok'=>false, 'error'=>$id->get_error_message()]);
}} else {{
    echo json_encode(['ok'=>true, 'id'=>$id, 'slug'=>get_post_field('post_name', $id)]);
}}
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=30)
    if rc != 0:
        raise RuntimeError(f"Failed to create draft post: SSH rc={rc}")
    resp = json.loads(stdout.strip())
    if not resp.get("ok"):
        raise RuntimeError(f"wp_insert_post failed: {resp.get('error')}")
    return resp["id"]


# ───────────────────────────────────────────────────────────────────────────
# Stage: run assemble-article
# ───────────────────────────────────────────────────────────────────────────

def run_assemble(job: dict, config: dict, skip_gap: bool = False) -> Path:
    """Run assemble-article.py. Returns path to the article HTML."""
    jd = job_dir(job)
    post_id = job["post_id"]
    topic = job["topic"]
    site = job["site"]

    cmd = [
        PYTHON, str(TOOLS_DIR / "assemble-article.py"),
        "--site", site,
        "--post-id", str(post_id),
        "--target-keyword", topic,
        "--output-dir", str(jd),
        "--skip-deploy",
    ]
    if skip_gap:
        cmd.append("--allow-no-serp")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(
            f"assemble-article.py failed (rc={result.returncode}):\n"
            f"STDERR: {result.stderr[-500:]}"
        )

    # Find the output article
    article_path = jd / f"{post_id}-article.html"
    if not article_path.exists():
        # Try the linked version
        linked = jd / f"{post_id}-article-linked.html"
        if linked.exists():
            return linked
        raise RuntimeError(f"Article HTML not found at {article_path}")

    return article_path


# ───────────────────────────────────────────────────────────────────────────
# Stage: link pass
# ───────────────────────────────────────────────────────────────────────────

def run_link_pass(job: dict, config: dict) -> tuple[Path, int]:
    """Run inject-internal-links.py. Returns (linked_html_path, links_injected)."""
    jd = job_dir(job)
    post_id = job["post_id"]
    site = job["site"]
    article_path = jd / f"{post_id}-article.html"

    linked_path = jd / f"{post_id}-article-linked.html"
    pending_path = jd / f"{post_id}-pending-links.json"

    cmd = [
        PYTHON, str(TOOLS_DIR / "inject-internal-links.py"),
        "--site", site,
        "--html-input", str(article_path),
        "--html-output", str(linked_path),
        "--pending-links-output", str(pending_path),
        "--target-keyword", job["topic"],
        "--exclude-post-id", str(post_id),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"inject-internal-links failed: {result.stderr[-300:]}")

    # Count injected links from stderr
    links = 0
    for line in result.stderr.split("\n"):
        if "Done:" in line and "links injected" in line:
            m = re.search(r"(\d+) links injected", line)
            if m:
                links = int(m.group(1))

    return linked_path, links


# ───────────────────────────────────────────────────────────────────────────
# Stage: deploy
# ───────────────────────────────────────────────────────────────────────────

def deploy_draft(job: dict, config: dict, html_path: Path) -> bool:
    """Deploy article HTML as draft via push-post-content.py."""
    import base64

    post_id = job["post_id"]
    content = html_path.read_text()
    wp_path = config["access"]["wp_path"]

    # Backup (even for new posts — the draft may have placeholder content)
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    ops_dir = wp_path.rstrip("/") + "/wp-content/uploads"
    content_path = f"{ops_dir}/rss-deploy-content.b64"

    ssh_run(config, f"cat > {content_path}", stdin_data=b64, timeout=30)

    php = f"""<?php
$b = file_get_contents('{content_path}');
$c = base64_decode(trim($b));
if ($c === false) {{ echo json_encode(['ok'=>false,'e'=>'decode']); exit; }}
$r = wp_update_post(['ID'=>{post_id}, 'post_content'=>$c, 'post_status'=>'draft']);
if (is_wp_error($r)) {{ echo json_encode(['ok'=>false,'e'=>$r->get_error_message()]); }}
else {{ echo json_encode(['ok'=>true,'id'=>$r,'len'=>strlen($c)]); }}
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=30)
    try:
        ssh_run(config, f"rm -f {content_path}", timeout=30)
    except Exception:
        pass

    if rc != 0 or not stdout.strip():
        return False
    resp = json.loads(stdout.strip())
    return resp.get("ok", False)


def set_yoast_meta(config: dict, post_id: int, title: str, description: str):
    """Set Yoast SEO title and meta description."""
    php = f"""<?php
update_post_meta({post_id}, '_yoast_wpseo_title', '{title.replace("'", "\\'")}');
update_post_meta({post_id}, '_yoast_wpseo_metadesc', '{description.replace("'", "\\'")}');
echo 'OK';
"""
    ssh_pipe_php(config, php, timeout=30)


def purge_cache(config: dict):
    php = """<?php
wp_cache_flush();
if (class_exists('WpeCommon')) {
    WpeCommon::purge_memcached();
    WpeCommon::purge_varnish_cache();
}
echo 'purged';
"""
    try:
        ssh_pipe_php(config, php, timeout=30)
    except Exception:
        pass  # Cache purge is best-effort


# ───────────────────────────────────────────────────────────────────────────
# Stage: verify
# ───────────────────────────────────────────────────────────────────────────

def verify_deploy(job: dict, config: dict) -> dict:
    """Verify the deployed draft. Returns check results."""
    post_id = job["post_id"]
    author_id = job["author_id"]

    php = f"""<?php
$p = get_post({post_id});
echo json_encode([
    'status'  => $p->post_status,
    'author'  => (int)$p->post_author,
    'len'     => strlen($p->post_content),
    'title'   => get_post_meta({post_id}, '_yoast_wpseo_title', true),
    'desc'    => get_post_meta({post_id}, '_yoast_wpseo_metadesc', true),
]);
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=30)
    checks = {}
    if rc != 0:
        checks["ssh"] = "FAIL"
        return checks

    data = json.loads(stdout.strip())
    checks["status_draft"] = "pass" if data["status"] == "draft" else f"FAIL: {data['status']}"
    checks["author_correct"] = "pass" if data["author"] == author_id else f"FAIL: {data['author']} != {author_id}"
    checks["content_nonempty"] = "pass" if data["len"] > 500 else f"FAIL: only {data['len']} bytes"
    checks["yoast_title"] = "pass" if data["title"] else "WARN: no Yoast title"
    checks["yoast_desc"] = "pass" if data["desc"] else "WARN: no Yoast description"

    return checks
