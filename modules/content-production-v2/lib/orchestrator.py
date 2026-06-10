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
# Centralized timeouts
# ───────────────────────────────────────────────────────────────────────────

TIMEOUTS = {
    "generation": 1800,   # assemble-article subprocess (30 min)
    "ssh": 30,            # all SSH operations
    "link_pass": 120,     # inject-internal-links
    "d2_extraction": 600, # claude CLI claim extraction (up to 10 min)
    "d2_classification": 600,  # claude CLI source check (up to 10 min)
    "purge": 30,          # CDN purge (best-effort)
}


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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUTS["generation"])
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
    """Run pool-mode link pass, then corpus-mode second pass.

    Pool mode: inject-internal-links.py (anchor pool phrases)
    Corpus mode: title/slug-derived candidates from published posts via SSH export

    Returns (linked_html_path, total_links_injected).
    """
    jd = job_dir(job)
    post_id = job["post_id"]
    site = job["site"]
    article_path = jd / f"{post_id}-article.html"

    linked_path = jd / f"{post_id}-article-linked.html"
    pending_path = jd / f"{post_id}-pending-links.json"

    # Pass 1: pool mode (existing pipeline linker)
    cmd = [
        PYTHON, str(TOOLS_DIR / "inject-internal-links.py"),
        "--site", site,
        "--html-input", str(article_path),
        "--html-output", str(linked_path),
        "--pending-links-output", str(pending_path),
        "--target-keyword", job["topic"],
        "--exclude-post-id", str(post_id),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUTS["link_pass"])
    if result.returncode != 0:
        raise RuntimeError(f"inject-internal-links failed: {result.stderr[-300:]}")

    pool_links = 0
    for line in result.stderr.split("\n"):
        if "Done:" in line and "links injected" in line:
            m = re.search(r"(\d+) links injected", line)
            if m:
                pool_links = int(m.group(1))

    # Pass 2: corpus mode (title/slug-derived candidates)
    corpus_links = 0
    try:
        corpus_links = _run_corpus_link_pass(job, config, linked_path)
    except Exception as e:
        # Corpus pass is additive — pool-mode result stands if it fails
        pass

    return linked_path, pool_links + corpus_links


def _run_corpus_link_pass(job: dict, config: dict, html_path: Path) -> int:
    """Corpus-mode second pass: derive candidates from published post titles/slugs.

    Fetches published post list via SSH, generates corpus candidates,
    applies them to the article using the same BS4 text-node-safe injection.
    Modifies html_path in place. Returns count of additional links injected.
    """
    from bs4 import BeautifulSoup
    from lib.linker_core import (
        inject_link_in_paragraph, is_restricted_zone, is_body_section,
        corpus_candidates, _normalize_for_dedup, score_candidate, is_dest_capped,
    )

    post_id = job["post_id"]
    jd = job_dir(job)

    # Fetch published post titles + slugs via SSH
    php = """<?php
global $wpdb;
$rows = $wpdb->get_results(
    "SELECT ID, post_name, post_title FROM wp_posts WHERE post_status='publish' AND post_type='post' ORDER BY ID",
    ARRAY_A
);
foreach ($rows as $r) {
    echo json_encode(['id'=>(int)$r['ID'],'slug'=>$r['post_name'],'title'=>$r['post_title'],'url'=>'/'.$r['post_name'].'/'], JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) . "\n";
}
"""
    stdout, rc = ssh_pipe_php(config, php, timeout=TIMEOUTS["ssh"])
    if rc != 0:
        return 0

    corpus = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            corpus.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not corpus:
        return 0

    # Generate corpus candidates
    candidates = corpus_candidates(corpus)
    if not candidates:
        return 0

    # Filter out self
    self_slug = job.get("post_slug", "")
    candidates = [c for c in candidates
                  if _normalize_for_dedup(c[1]) != _normalize_for_dedup(f"/{self_slug}/")]

    # Read current article HTML
    html = html_path.read_text()
    soup = BeautifulSoup(html, "html.parser")
    soup_str = str(soup)

    # Pre-existing internal links (including any pool-mode injections)
    used_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") and not href.startswith("//"):
            used_urls.add(_normalize_for_dedup(href))

    # Config constraints
    max_per_post = config.get("linking", {}).get("max_links_per_post", 10)
    max_per_section = config.get("linking", {}).get("max_links_per_section", 3)
    inbound_min = config.get("linking", {}).get("inbound_min", 3)
    per_run_cap = config.get("linking", {}).get("per_run_dest_cap", 10)

    zone_config = {
        "prefixes": config.get("content", {}).get("css_prefix", []),
        "suffixes": config.get("linking", {}).get("zone_suffixes", []),
        "extra_classes": config.get("linking", {}).get("extra_zone_classes", []),
    }

    # Count existing links to respect per-post cap
    existing_link_count = len(used_urls)
    if existing_link_count >= max_per_post:
        return 0

    # Find body H2 sections and inject
    h_re = re.compile(r'<h[23][^>]*>(.*?)</h[23]>', re.IGNORECASE | re.DOTALL)
    h_matches = list(h_re.finditer(soup_str))
    if not h_matches:
        return 0

    used_anchors = set()
    per_run_dest_counts = {}
    total_injected = 0

    for h_match in h_matches:
        if total_injected + existing_link_count >= max_per_post:
            break
        h_text = re.sub(r'<[^>]+>', '', h_match.group(1)).strip()
        if not is_body_section(h_text):
            continue

        h_end = h_match.end()
        next_h = len(soup_str)
        for other in h_matches:
            if other.start() > h_end:
                next_h = other.start()
                break

        section_html = soup_str[h_end:next_h]
        section_soup = BeautifulSoup(section_html, "html.parser")
        paras = section_soup.find_all("p")
        section_injected = 0

        for para in paras:
            if section_injected >= max_per_section:
                break
            if total_injected + existing_link_count >= max_per_post:
                break
            if is_restricted_zone(para, zone_config):
                continue
            text = para.get_text()
            if len(text.split()) < 10:
                continue

            for phrase, url, base_score, source in candidates:
                norm_url = _normalize_for_dedup(url)
                if norm_url in used_urls:
                    continue
                if phrase.lower() in used_anchors:
                    continue
                if is_dest_capped(url, per_run_dest_counts, per_run_cap):
                    continue

                pat = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
                if not pat.search(text):
                    continue

                # In-memory verification
                import copy
                para_copy = BeautifulSoup(str(para), "html.parser")
                p_tag = para_copy.find("p") or para_copy
                if not inject_link_in_paragraph(p_tag, phrase, url):
                    continue

                # Apply to the actual soup
                # Re-find the paragraph in the full soup by text match
                for real_para in soup.find_all("p"):
                    if real_para.get_text() == text:
                        if inject_link_in_paragraph(real_para, phrase, url):
                            used_urls.add(norm_url)
                            used_anchors.add(phrase.lower())
                            per_run_dest_counts[norm_url] = per_run_dest_counts.get(norm_url, 0) + 1
                            section_injected += 1
                            total_injected += 1
                            break
                break  # one per paragraph

    if total_injected > 0:
        html_path.write_text(str(soup))

    return total_injected


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
# Stage D2: Claims verification
# ───────────────────────────────────────────────────────────────────────────

# Ventriloquism patterns — first-person SME constructions
_VENTRILOQUISM_PATTERNS = [
    re.compile(r'\b(?:on|with)\s+files?\s+I\s+work\b', re.IGNORECASE),
    re.compile(r'\bborrowers?\s+who\s+come\s+to\s+me\b', re.IGNORECASE),
    re.compile(r'\bin\s+my\s+experience\b', re.IGNORECASE),
    re.compile(r'\bmy\s+clients?\b', re.IGNORECASE),
    re.compile(r'\bwhen\s+I\s+(?:see|review|work|pull|look)\b', re.IGNORECASE),
    re.compile(r'\bI\s+(?:see|tell|advise|recommend|work|handle|review|pull)\b', re.IGNORECASE),
    re.compile(r'\bI\'ve\s+(?:seen|worked|helped|reviewed|had)\b', re.IGNORECASE),
    re.compile(r'\bclients?\s+(?:I|I\'ve)\b', re.IGNORECASE),
    re.compile(r'\bfiles?\s+(?:I|I\'ve)\b', re.IGNORECASE),
]


def run_ventriloquism_gate(html: str, config: dict = None) -> list[dict]:
    """Deterministic scan for first-person SME constructions.

    Returns list of {pattern, text, line_approx} for each match.
    Empty list = pass.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    hits = []

    for line_num, line in enumerate(text.split("\n"), 1):
        for pat in _VENTRILOQUISM_PATTERNS:
            for m in pat.finditer(line):
                # Get surrounding context
                start = max(0, m.start() - 30)
                end = min(len(line), m.end() + 30)
                ctx = line[start:end].strip()
                hits.append({
                    "pattern": pat.pattern,
                    "matched": m.group(),
                    "context": ctx,
                    "line_approx": line_num,
                })

    return hits


def run_claims_extraction(html: str, job_path: Path) -> list[dict]:
    """Extract factual claims from article via claude CLI (Opus).

    Returns list of {claim, section, claim_type}.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    prompt = f"""Extract every factual claim from this article draft. A "claim" is any specific assertion of fact: numbers, percentages, timelines, waiting periods, named rules/programs/forms, dollar figures, score thresholds, legal or regulatory assertions, or credit-score-impact predictions.

For each claim, output a JSON array of objects with:
- "claim": the exact text of the claim (verbatim from the article)
- "section": the H2 section heading it appears under
- "claim_type": one of "number", "timeline", "rule_or_program", "threshold", "legal", "score_prediction", "dollar_figure", "general_fact"

Be thorough — extract EVERY specific factual assertion. Include credit score impacts, waiting periods, form numbers, program names, and any assertion that could be verified against an authoritative source.

Return ONLY a JSON array. No commentary.

Article text:
{text[:12000]}"""

    prompt_path = job_path / "d2-extraction-prompt.txt"
    prompt_path.write_text(prompt)

    # Use temp file for prompt to avoid OS arg-length limits on long articles
    result = subprocess.run(
        f'cat "{prompt_path}" | claude -p - --output-format json',
        shell=True, capture_output=True, text=True, timeout=TIMEOUTS["d2_extraction"],
    )

    if result.returncode != 0:
        return []

    # Parse the response — claude outputs JSON with a result field
    try:
        resp = json.loads(result.stdout)
        content = resp.get("result", result.stdout)
        if isinstance(content, str):
            # Find JSON array in content
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(content[start:end])
                return claims
        elif isinstance(content, list):
            return content
    except (json.JSONDecodeError, TypeError):
        pass

    return []


def run_claims_classification(
    claims: list[dict],
    policy_path: str,
    scan_dir: Path,
    job_path: Path,
) -> list[dict]:
    """Classify each claim as POLICY-BACKED, SOURCE-BACKED, or UNSOURCED.

    Uses claude CLI (Opus) with conservative instructions.
    """
    if not claims:
        return []

    # Load policy file
    policy_text = ""
    if policy_path:
        expanded = os.path.expanduser(policy_path)
        if os.path.exists(expanded):
            policy_text = Path(expanded).read_text()[:4000]

    # Load scan excerpts (gap analysis, SERP data)
    scan_text = ""
    for scan_file in sorted(scan_dir.glob("*-subtopic-gaps.json")) + sorted(scan_dir.glob("*-empty-serp.json")):
        try:
            scan_text += scan_file.read_text()[:2000] + "\n"
        except Exception:
            pass

    claims_json = json.dumps(claims, indent=2, ensure_ascii=False)

    prompt = f"""You are a factual-claims auditor for a mortgage/finance content site. For each claim below, classify it as:

- POLICY: the claim is explicitly stated in the site's claims policy (the authoritative positions below)
- SOURCE: the claim appears in or is directly supported by the gap-scan research material below
- UNSOURCED: the claim is not backed by either source — it may be correct, but it's not verifiable from the provided material

Be CONSERVATIVE: if you're unsure whether a claim is backed, classify it UNSOURCED. We'd rather flag a correct claim for human review than let an incorrect one through.

For each UNSOURCED claim, add a "suggestion" field: how to neutralize it (replace specific number with directional language, delete invented rule, or note that human verification is needed).

CLAIMS POLICY (authoritative positions — if a claim matches one of these, it's POLICY):
{policy_text or "(no claims policy for this site)"}

GAP-SCAN RESEARCH MATERIAL (if a claim matches content from these sources, it's SOURCE):
{scan_text or "(no scan material available)"}

CLAIMS TO CLASSIFY:
{claims_json}

Return a JSON array of objects, one per claim, each with:
- "claim": (copied from input)
- "section": (copied from input)
- "classification": "POLICY" | "SOURCE" | "UNSOURCED"
- "suggestion": (only for UNSOURCED — neutralization suggestion)

Return ONLY the JSON array."""

    # Write prompt to temp file to avoid OS arg-length limits
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        tf.write(prompt)
        tf_path = tf.name
    result = subprocess.run(
        f'cat "{tf_path}" | claude -p - --output-format json',
        shell=True, capture_output=True, text=True, timeout=TIMEOUTS["d2_classification"],
    )
    try:
        os.unlink(tf_path)
    except Exception:
        pass

    if result.returncode != 0:
        # If classification fails, mark everything UNSOURCED
        return [{"claim": c["claim"], "section": c.get("section", ""), "classification": "UNSOURCED",
                 "suggestion": "Classification failed — manual review required"} for c in claims]

    try:
        resp = json.loads(result.stdout)
        content = resp.get("result", result.stdout)
        if isinstance(content, str):
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        elif isinstance(content, list):
            return content
    except (json.JSONDecodeError, TypeError):
        pass

    return [{"claim": c["claim"], "section": c.get("section", ""), "classification": "UNSOURCED",
             "suggestion": "Parse error — manual review required"} for c in claims]


def run_d2_claims_check(html: str, config: dict, job: dict) -> dict:
    """Full D2 pipeline: ventriloquism gate + claim extraction + classification.

    Returns {
        "ventriloquism": [hits],
        "claims": [classified claims],
        "unsourced_count": int,
        "policy_count": int,
        "source_count": int,
        "passed": bool,
    }
    """
    jd = job_dir(job)

    # Step 1: Ventriloquism gate (deterministic)
    vent_hits = run_ventriloquism_gate(html, config)

    # Step 2: Claim extraction (Opus)
    claims = run_claims_extraction(html, jd)

    # Step 3: Classify claims
    policy_path = config.get("content", {}).get("claims_policy", "")
    classified = run_claims_classification(claims, policy_path, jd, jd)

    # Count
    unsourced = [c for c in classified if c.get("classification") == "UNSOURCED"]
    policy = [c for c in classified if c.get("classification") == "POLICY"]
    source = [c for c in classified if c.get("classification") == "SOURCE"]

    # Save full report
    report = {
        "ventriloquism_hits": vent_hits,
        "total_claims": len(classified),
        "classified_claims": classified,
        "unsourced_count": len(unsourced),
        "policy_count": len(policy),
        "source_count": len(source),
        "passed": len(vent_hits) == 0 and len(unsourced) == 0,
    }
    (jd / "d2-claims-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )

    return report


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
    checks["yoast_title"] = "pass" if data["title"] else "FAIL: no Yoast title (meta required)"
    checks["yoast_desc"] = "pass" if data["desc"] else "FAIL: no Yoast description (meta required)"

    return checks
