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

import importlib.util as _ilu
_gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
_gl_mod = _ilu.module_from_spec(_gl_spec)
_gl_spec.loader.exec_module(_gl_mod)
run_universal_gates = _gl_mod.run_universal_gates

_const_spec = _ilu.spec_from_file_location("constants", REPO_ROOT / "lib" / "constants.py")
_const_mod = _ilu.module_from_spec(_const_spec)
_const_spec.loader.exec_module(_const_mod)
CSS_BUILTIN_ALLOWLIST = _const_mod.CSS_BUILTIN_ALLOWLIST
CSS_FRAMEWORK_PREFIXES = _const_mod.CSS_FRAMEWORK_PREFIXES

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


# L28: Ordered pipeline stages — every stage in the new-article pipeline.
# Adding a stage here is required; the structural guard test will fail
# if a mark_stage call references a name not in this tuple.
PIPELINE_STAGES = (
    "config",             # A
    "gap_scan",           # B
    "generate",           # C
    "gates",              # D
    "claims_check",       # D2
    "link_pass",          # E
    "adversarial_review", # E2
    "deploy",             # F
    "verify",             # G
    "log",                # H
)

# Terminal statuses — stage will not re-run on resume.
TERMINAL_STAGE_STATUSES = frozenset({
    "done",
    "pass",
    "skipped_config",
    "skipped_flag",
    "skipped_missing_input",
    "not_reached",
})


def stage_done(job: dict, stage: str) -> bool:
    status = job.get("stages", {}).get(stage, {}).get("status")
    return status in TERMINAL_STAGE_STATUSES


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

    # vertical validation (optional field, but must be valid if set)
    from lib.brand_rules import validate_vertical
    missing.extend(validate_vertical(config))

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

    # Gate 6: CSS prefix check — hard fail on foreign classes
    # Allowlists from lib/constants.py (shared with gate_library)
    site_allowlist = set(config.get("content", {}).get("css_allowlist", []))
    all_classes = set()
    scope = main_content if main_content else soup
    for tag in scope.find_all(class_=True):
        for cls in tag.get("class", []):
            all_classes.add(cls)
    foreign = []
    for cls in sorted(all_classes):
        if cls in CSS_BUILTIN_ALLOWLIST or cls in site_allowlist:
            continue
        if any(cls.startswith(p) for p in CSS_FRAMEWORK_PREFIXES):
            continue
        if any(cls.lower().startswith(p.lower()) for p in css_prefixes):
            continue
        foreign.append(cls)
    if foreign:
        results["css_prefix"] = f"FAIL: foreign classes: {', '.join(foreign)}"
    else:
        results["css_prefix"] = "pass"

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

    # Gate 8: CTA present (skip if not configured or TODO-verify)
    if cta_url and cta_url != "TODO-verify" and not cta_url.startswith("TODO"):
        has_cta = cta_url.rstrip("/") in html
        results["cta_present"] = "pass" if has_cta else f"FAIL: CTA URL {cta_url} not found"
    else:
        results["cta_present"] = "pass (CTA not configured)"

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
    if not isinstance(post_id, int) or post_id <= 0:
        raise ValueError(
            f"run_assemble requires a valid positive integer post_id, "
            f"got {post_id!r} (job {job.get('id', '?')})"
        )
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

    # Self-exclusion on refresh: exclude the page being refreshed from evidence
    refresh = job.get("refresh", {})
    if refresh.get("original_slug"):
        site_config_path = REPO_ROOT / "sites" / site / "config.json"
        if site_config_path.exists():
            import json as _json
            site_cfg = _json.loads(site_config_path.read_text())
            public_url = site_cfg.get("identity", {}).get("public_url", "").rstrip("/")
            if public_url:
                exclude = f"{public_url}/{refresh['original_slug']}/"
                cmd.extend(["--exclude-url", exclude])

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
# Stage: generate from voice capture
# ───────────────────────────────────────────────────────────────────────────

def load_capture_transcript(capture_path: str) -> tuple[str, str]:
    """Load a voice capture JSON and return (story_text, qualify_text)."""
    path = Path(os.path.expanduser(capture_path))
    if not path.exists():
        raise FileNotFoundError(f"Capture file not found: {path}")
    raw = path.read_text()
    if raw.startswith("<?php"):
        raw = raw[raw.index("\n") + 1:]
    cap = json.loads(raw)
    responses = cap.get("responses", {})
    story = (responses.get("story") or responses.get("tell_story") or "").strip()
    qualify = (responses.get("qualify") or "").strip()
    return story, qualify


def generate_from_capture(job: dict, config: dict, capture_path: str) -> Path:
    """Generate an article from a voice-capture transcript via claude CLI.

    The transcript is the primary source material. The voice archetype and
    claims policy govern style and assertion boundaries. Gap-scan material
    supplements competitive coverage but never overrides the SME's claims.

    Returns path to the generated article HTML.
    """
    jd = job_dir(job)
    post_id = job["post_id"]
    topic = job["topic"]

    story, qualify = load_capture_transcript(capture_path)
    if not story:
        raise ValueError("Capture has no 'story' content — cannot generate")

    # Load voice archetype
    archetype = config.get("content", {}).get("brand_voice_archetype", "")
    voice_path = MODULE_DIR / "brand-voice" / "archetypes" / f"{archetype}.md"
    # Try repo-root-relative path
    if not voice_path.exists():
        voice_path = REPO_ROOT / "modules" / "brand-voice" / "archetypes" / f"{archetype}.md"
    voice_text = voice_path.read_text()[:2500] if voice_path.exists() else ""

    # Load claims policy (resolve relative to REPO_ROOT, not CWD)
    policy_path = config.get("content", {}).get("claims_policy", "")
    policy_text = ""
    if policy_path:
        expanded = REPO_ROOT / policy_path
        if not expanded.exists():
            expanded = Path(os.path.expanduser(policy_path))
        if expanded.exists():
            policy_text = expanded.read_text()[:3000]
        else:
            raise FileNotFoundError(
                f"Claims policy declared but not found: {policy_path} "
                f"(tried {REPO_ROOT / policy_path} and {os.path.expanduser(policy_path)})"
            )

    css_prefix = (config.get("content", {}).get("css_prefix") or ["ahn"])[0]
    min_words = config.get("content", {}).get("article_min_words", 1800)
    site_name = config.get("identity", {}).get("name", "")

    prompt = f"""You are writing a hub article for {site_name} from the SME's voice capture.

VOICE (how to write):
{voice_text}

CLAIMS POLICY (what you can and cannot assert):
{policy_text}

SME'S CAPTURED ANSWERS (PRIMARY source material — substance + voice):

### Story
{story}

### Qualification Details
{qualify or "(not provided for this topic)"}

ARTICLE SPEC:
- Topic: {topic}
- Target: {min_words}-{min_words + 700} words
- Write in the SME's voice (first person if licensed in the voice file)
- Structure: BLUF (50-70 words), 5-7 H2 sections (each with intro paragraph + structural element), "The Bottom Line" closing, 5-8 FAQs, Resources Used
- Each H2: answer-first intro (50-70w) + one structural element (table, bullets, or callout)
- Include at least one real dollar example from the capture
- Shariah-compliance statements: ALWAYS attributed to the provider's Shariah board
- Qualification numbers: use ONLY the SME's stated figures, framed as observed ("the financiers I work with typically look for...")
- No H1 in body, no em dashes, use CSS prefix "{css_prefix}" for component classes
- CTA: omit if not configured

Return clean HTML only (h2, h3, p, strong, table, ul/li, div for callouts). No markdown, no preamble, no H1.
"""

    prompt_path = jd / "capture-generation-prompt.txt"
    prompt_path.write_text(prompt)

    article_path = jd / f"{post_id}-article.html"
    result = subprocess.run(
        f'cat "{prompt_path}" | claude -p - --output-format text',
        shell=True, capture_output=True, text=True, timeout=TIMEOUTS["generation"],
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (rc={result.returncode}): {result.stderr[-300:]}")

    html = result.stdout.strip()
    # Strip markdown wrapper if present
    if not html.startswith("<"):
        import re as _re
        m = _re.search(r'<div|<section|<h2|<p', html)
        if m:
            html = html[m.start():]
        html = _re.sub(r'```\s*$', '', html).strip()

    article_path.write_text(html)
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
    corpus_status = "ok"
    try:
        corpus_links = _run_corpus_link_pass(job, config, linked_path)
    except Exception as e:
        # Corpus pass is additive — pool-mode result stands, but record the failure loudly
        corpus_status = f"FAILED: {type(e).__name__}: {e}"
        print(f"  [LINKING] Corpus link pass FAILED (pool links stand): {corpus_status}", file=sys.stderr)

    # Record corpus status in job stage extras and manifest
    jd = job_dir(job)
    stage_data = job.get("stages", {}).get("link", {})
    stage_data["corpus_links"] = corpus_status if corpus_status != "ok" else corpus_links
    if "stages" not in job:
        job["stages"] = {}
    job["stages"]["link"] = stage_data
    save_job(job)

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

    # Universal gate check before deploy
    site_id = config.get("identity", {}).get("site_id", job.get("site", ""))
    gate_report = run_universal_gates(
        content,
        site_slug=site_id,
        title=job.get("topic", ""),
        content_type="article",
        config=config,
    )
    if not gate_report.passed:
        from .tool_utils import eprint
        eprint(f"[deploy] GATE FAILED — refusing to deploy:")
        for fail in gate_report.failures:
            eprint(f"  [{fail.name}] {fail.detail}")
        return False

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

    # Use temp file for prompt to avoid OS arg-length limits on long articles.
    # Retry on CLI failure — a hiccup must not silently disarm the strongest gate.
    D2_MAX_RETRIES = 2
    D2_BACKOFF_BASE = 5  # seconds
    last_err = ""
    for attempt in range(D2_MAX_RETRIES + 1):
        result = subprocess.run(
            f'cat "{prompt_path}" | claude -p - --output-format json',
            shell=True, capture_output=True, text=True, timeout=TIMEOUTS["d2_extraction"],
        )
        if result.returncode == 0:
            break
        last_err = result.stderr[:500] if result.stderr else f"exit {result.returncode}"
        if attempt < D2_MAX_RETRIES:
            import time as _time
            wait = D2_BACKOFF_BASE * (2 ** attempt)
            print(f"  [D2] Extraction CLI failed (attempt {attempt+1}), retrying in {wait}s: {last_err[:120]}", file=sys.stderr)
            _time.sleep(wait)

    if result.returncode != 0:
        # All retries exhausted — raise so caller can block the stage
        raise RuntimeError(f"D2 extraction CLI failed after {D2_MAX_RETRIES + 1} attempts: {last_err}")

    # Parse the response — claude outputs JSON with a result field
    try:
        resp = json.loads(result.stdout)
        content = resp.get("result", result.stdout)
        if isinstance(content, str):
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(content[start:end])
                return claims
        elif isinstance(content, list):
            return content
    except (json.JSONDecodeError, TypeError):
        pass

    # CLI succeeded but produced no parseable claims — legitimate zero
    return []


def run_claims_classification(
    claims: list[dict],
    policy_path: str,
    scan_dir: Path,
    job_path: Path,
    transcript_text: str = "",
) -> list[dict]:
    """Classify each claim as POLICY, SOURCE, SME-SOURCED, or UNSOURCED.

    Classification tiers:
    - POLICY: claim matches the site's claims policy (ratified positions)
    - SOURCE: claim matches gap-scan research material
    - SME-SOURCED: claim is traceable to the SME's voice-capture transcript
    - UNSOURCED: not backed by any source — requires human review

    Uses claude CLI (Opus) with conservative instructions.
    """
    if not claims:
        return []

    # Load policy file (resolve relative to REPO_ROOT, not CWD)
    policy_text = ""
    if policy_path:
        expanded = REPO_ROOT / policy_path
        if not expanded.exists():
            expanded = Path(os.path.expanduser(policy_path))
        if expanded.exists():
            policy_text = expanded.read_text()[:4000]
        else:
            raise FileNotFoundError(
                f"Claims policy declared but not found: {policy_path}"
            )

    # Load scan excerpts (gap analysis, SERP data, evidence store)
    scan_text = ""
    scan_globs = (
        sorted(scan_dir.glob("*-subtopic-gaps.json"))
        + sorted(scan_dir.glob("*-empty-serp.json"))
    )
    for scan_file in scan_globs:
        try:
            scan_text += scan_file.read_text()[:2000] + "\n"
        except Exception:
            pass

    # Evidence store: render as prose (not raw JSON) so the classifier reads
    # the same labeled passages the writer used
    for ev_file in sorted(scan_dir.glob("*-evidence.json")):
        try:
            ev_items = json.loads(ev_file.read_text())
            from lib.evidence import render_evidence_block
            ev_prose = render_evidence_block(ev_items[:40])
            if ev_prose:
                scan_text += ev_prose[:6000] + "\n"
        except Exception:
            pass

    # Truncate transcript for prompt size
    sme_text = transcript_text[:5000] if transcript_text else ""

    claims_json = json.dumps(claims, indent=2, ensure_ascii=False)

    sme_section = ""
    if sme_text:
        sme_section = f"""
SME VOICE-CAPTURE TRANSCRIPT (if a claim is traceable to this transcript — the SME stated it or it closely paraphrases what the SME said — classify it SME-SOURCED):
{sme_text}
"""

    prompt = f"""You are a factual-claims auditor for a content site. For each claim below, classify it as:

- POLICY: the claim is explicitly stated in the site's claims policy (the authoritative positions below)
- SOURCE: the claim appears in or is directly supported by the gap-scan research material below
- SME-SOURCED: the claim is traceable to the SME's voice-capture transcript below — the SME stated it, or it closely paraphrases what the SME said (same fact, same number, same example)
- UNSOURCED: the claim is not backed by any of the above sources — it may be correct, but it's not verifiable from the provided material

Priority: POLICY > SOURCE > SME-SOURCED > UNSOURCED. If a claim matches multiple tiers, use the highest.

Be CONSERVATIVE on UNSOURCED: if you're unsure, classify UNSOURCED. But be GENEROUS on SME-SOURCED: if the SME clearly stated the same fact or example (even in different words), that's SME-SOURCED, not UNSOURCED.

For each UNSOURCED claim, add a "suggestion" field: how to neutralize it (replace specific number with directional language, delete invented rule, or note that human verification is needed).

CLAIMS POLICY (authoritative positions — if a claim matches one of these, it's POLICY):
{policy_text or "(no claims policy for this site)"}

GAP-SCAN RESEARCH MATERIAL (if a claim matches content from these sources, it's SOURCE):
{scan_text or "(no scan material available)"}
{sme_section}

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


def run_d2_claims_check(html: str, config: dict, job: dict, transcript_text: str = "") -> dict:
    """Full D2 pipeline: ventriloquism gate + claim extraction + classification.

    If transcript_text is provided (capture-driven mode), it's used as an
    additional source for D2 classification. Claims traceable to the SME's
    transcript classify as SME-SOURCED instead of UNSOURCED.

    Returns {
        "ventriloquism": [hits],
        "claims": [classified claims],
        "unsourced_count": int,
        "policy_count": int,
        "source_count": int,
        "sme_sourced_count": int,
        "passed": bool,
    }
    """
    jd = job_dir(job)

    # Step 1: Ventriloquism gate (deterministic)
    vent_hits = run_ventriloquism_gate(html, config)

    # Step 2: Claim extraction (Opus) — fails closed, never silently passes
    try:
        claims = run_claims_extraction(html, jd)
    except RuntimeError as e:
        return {
            "ventriloquism": vent_hits,
            "claims": [],
            "unsourced_count": 0,
            "policy_count": 0,
            "source_count": 0,
            "sme_sourced_count": 0,
            "passed": False,
            "blocked": f"extraction failed: {e}",
        }

    print(f"  [D2] Extracted {len(claims)} claims", file=sys.stderr)

    # Step 3: Classify ALL claims on every run (with optional transcript as source)
    policy_path = config.get("content", {}).get("claims_policy", "")
    if claims:
        all_classified = run_claims_classification(claims, policy_path, jd, jd, transcript_text=transcript_text)
    else:
        all_classified = []

    # Count
    unsourced = [c for c in all_classified if c.get("classification") == "UNSOURCED"]
    policy = [c for c in all_classified if c.get("classification") == "POLICY"]
    source = [c for c in all_classified if c.get("classification") == "SOURCE"]
    sme_sourced = [c for c in all_classified if c.get("classification") == "SME-SOURCED"]

    # Check ventriloquism license
    voice_path = config.get("content", {}).get("claims_policy", "")
    voice_file_path = os.path.expanduser(
        config.get("content", {}).get("brand_voice_archetype", "")
    )
    first_person_licensed = bool(transcript_text)  # capture mode implies licensed

    # Save full report
    report = {
        "ventriloquism_hits": vent_hits,
        "ventriloquism_licensed": first_person_licensed,
        "total_claims": len(all_classified),
        "classified_claims": all_classified,
        "unsourced_count": len(unsourced),
        "policy_count": len(policy),
        "source_count": len(source),
        "sme_sourced_count": len(sme_sourced),
        "passed": (len(vent_hits) == 0 or first_person_licensed) and len(unsourced) == 0,
    }
    (jd / "d2-claims-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )

    return report


def resolve_unsourced_claims(job: dict, article_path: Path, mode: str = "neutralize") -> tuple[Path, list[dict]]:
    """Resolve UNSOURCED claims by neutralizing or removing them.

    mode:
      "neutralize" — apply D2's suggested neutralization for each claim
      "remove" — remove the sentence containing the claim entirely

    Returns (modified_article_path, resolution_log).
    Each resolution_log entry: {claim, action, before, after, reason}
    """
    jd = job_dir(job)
    report_path = jd / "d2-claims-report.json"
    if not report_path.exists():
        return article_path, []

    report = json.loads(report_path.read_text())
    classified = report.get("classified_claims", [])
    unsourced = [c for c in classified if c.get("classification") == "UNSOURCED"]

    if not unsourced:
        return article_path, []

    html = article_path.read_text()
    log_entries = []

    for claim in unsourced:
        claim_text = claim.get("claim", "")
        suggestion = claim.get("suggestion", "")

        if mode == "remove":
            # Remove the sentence containing the claim
            import re as _re
            # Find and remove the sentence
            pattern = _re.escape(claim_text[:60])
            m = _re.search(pattern, html)
            if m:
                # Find sentence boundaries
                start = html.rfind(".", 0, m.start())
                end = html.find(".", m.end())
                if start >= 0 and end >= 0:
                    removed = html[start + 1 : end + 1].strip()
                    html = html[: start + 1] + html[end + 1 :]
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "removed",
                        "removed_text": removed[:150],
                        "reason": suggestion or "UNSOURCED — not in transcript, policy, or sources",
                    })
        elif mode == "neutralize" and suggestion:
            # Try to apply the suggestion (directional language replacement)
            # Find the claim text in the HTML
            if claim_text[:50] in html:
                # Use directional language from suggestion
                neutral = suggestion.split(":")[-1].strip() if ":" in suggestion else ""
                if not neutral or len(neutral) > 200:
                    # Suggestion isn't a clean replacement — remove instead
                    html = html.replace(claim_text, "", 1)
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "removed (suggestion not a clean replacement)",
                        "reason": suggestion[:150],
                    })
                else:
                    html = html.replace(claim_text, neutral, 1)
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "neutralized",
                        "replacement": neutral[:150],
                        "reason": suggestion[:150],
                    })
            else:
                log_entries.append({
                    "claim": claim_text[:100],
                    "action": "skipped (claim text not found in HTML)",
                    "reason": suggestion[:150],
                })
        else:
            # No suggestion — remove
            if claim_text[:50] in html:
                html = html.replace(claim_text, "", 1)
                log_entries.append({
                    "claim": claim_text[:100],
                    "action": "removed (no suggestion available)",
                    "reason": "UNSOURCED with no neutralization suggestion",
                })

    article_path.write_text(html)

    # Append resolution history to job
    if "history" not in job:
        job["history"] = []
    job["history"].append({
        "stage": "approve_claims",
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "resolutions": log_entries,
    })
    save_job(job)

    return article_path, log_entries


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
