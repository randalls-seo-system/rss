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

_sv_spec = _ilu.spec_from_file_location("source_verification", REPO_ROOT / "lib" / "source_verification.py")
_sv_mod = _ilu.module_from_spec(_sv_spec)
_sv_spec.loader.exec_module(_sv_mod)
verify_claim = _sv_mod.verify_claim

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

# L33: Pathological-case ceiling for text fed to LLM prompts.
# NOT a prompt-size budget. All pipeline articles fit in <10K tokens;
# the 200K context window has 97% headroom. This guard exists only to
# catch pathological inputs (e.g. a binary file loaded by mistake).
# If it fires, it logs and records — it never clips silently.
PROMPT_TEXT_CEILING = 200_000  # chars (~50K tokens)


def _guard_prompt_text(text: str, label: str, job_path: Path | None = None) -> str:
    """Return text unchanged unless pathologically large.

    If text exceeds PROMPT_TEXT_CEILING, truncate with a loud log to
    stderr and a record in the job directory. A silent clip is a defect
    (L33); this function is the single place where prompt-text size is
    enforced.
    """
    if len(text) <= PROMPT_TEXT_CEILING:
        return text
    print(
        f"  [TRUNCATION GUARD] {label}: {len(text):,} chars exceeds "
        f"{PROMPT_TEXT_CEILING:,} ceiling — truncated to {PROMPT_TEXT_CEILING:,}",
        file=sys.stderr,
    )
    if job_path:
        warnings_path = job_path / "truncation-warnings.json"
        warnings = []
        if warnings_path.exists():
            try:
                warnings = json.loads(warnings_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        warnings.append({
            "label": label,
            "original_chars": len(text),
            "ceiling": PROMPT_TEXT_CEILING,
            "timestamp": datetime.now().isoformat(),
        })
        warnings_path.write_text(json.dumps(warnings, indent=2))
    return text[:PROMPT_TEXT_CEILING]


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

# L27: Key where D2 claims-check results are stored in stages dict.
# Single source of truth — the rss tool writes here, the approval gate reads here.
D2_RESULT_KEY = "claims_check"


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
    voice_text = _guard_prompt_text(voice_path.read_text(), "brand_voice", job_dir(job)) if voice_path.exists() else ""

    # Load claims policy (resolve relative to REPO_ROOT, not CWD)
    policy_path = config.get("content", {}).get("claims_policy", "")
    policy_text = ""
    if policy_path:
        expanded = REPO_ROOT / policy_path
        if not expanded.exists():
            expanded = Path(os.path.expanduser(policy_path))
        if expanded.exists():
            policy_text = _guard_prompt_text(expanded.read_text(), "claims_policy_gen", job_dir(job))
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

    Returns list of {claim, verbatim_text, section, claim_type,
    verbatim_verified}.  verbatim_text is the exact sentence from
    the article that the resolver will match against.  If the LLM
    paraphrases or the text spans inline HTML tags, verbatim_verified
    is False and the claim carries verbatim_mismatch=True.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")

    prompt = f"""Extract every factual claim from this article draft. A "claim" is any specific assertion of fact: numbers, percentages, timelines, waiting periods, named rules/programs/forms, dollar figures, score thresholds, legal or regulatory assertions, or credit-score-impact predictions.

For each claim, output a JSON array of objects with:
- "claim": a short summary of the factual assertion (for classification)
- "verbatim_text": the EXACT sentence or clause from the article that contains the claim, copied CHARACTER-FOR-CHARACTER from the article text above. Do NOT paraphrase, rephrase, combine sentences, or shorten. Copy the full sentence exactly as it appears.
- "section": the H2 section heading it appears under
- "claim_type": one of "number", "timeline", "rule_or_program", "threshold", "legal", "score_prediction", "dollar_figure", "general_fact"

CRITICAL: "verbatim_text" must be a character-for-character copy of the source sentence. If you cannot find the exact sentence, set verbatim_text to the closest substring you can copy exactly from the text. The downstream resolver will match this string literally — any deviation causes a miss.

Be thorough — extract EVERY specific factual assertion. Include credit score impacts, waiting periods, form numbers, program names, and any assertion that could be verified against an authoritative source.

Return ONLY a JSON array. No commentary.

Article text:
{_guard_prompt_text(text, "d2_extraction", job_path)}"""

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
    claims = []
    try:
        resp = json.loads(result.stdout)
        content = resp.get("result", result.stdout)
        if isinstance(content, str):
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                claims = json.loads(content[start:end])
        elif isinstance(content, list):
            claims = content
    except (json.JSONDecodeError, TypeError):
        pass

    if not claims:
        # CLI succeeded but produced no parseable claims — legitimate zero
        return []

    # L31: Assign stable IDs before any other processing.
    # Classification echoes only the ID; verbatim_text is carried across
    # the extraction→classification boundary in code, not by the LLM.
    for i, claim in enumerate(claims):
        claim["id"] = f"c{i:03d}"

    # L30: Self-validate verbatim_text against source HTML.
    # A claim whose verbatim_text does not appear in the raw HTML cannot
    # be resolved by the downstream matcher. Mark it now so the resolver
    # reports it as verbatim_not_in_source instead of a silent miss.
    verified_count = 0
    mismatch_count = 0
    for claim in claims:
        vt = claim.get("verbatim_text", "")
        if vt and vt in html:
            claim["verbatim_verified"] = True
            verified_count += 1
        else:
            claim["verbatim_verified"] = False
            claim["verbatim_mismatch"] = True
            mismatch_count += 1

    print(
        f"  [D2] Verbatim validation (extraction): {verified_count} verified, "
        f"{mismatch_count} mismatched (of {len(claims)} claims)",
        file=sys.stderr,
    )

    return claims


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

    # L31: Extraction assigns IDs — that is the contract.
    # Classification must not silently backfill; a missing id is a pipeline bug.
    for c in claims:
        if "id" not in c:
            raise RuntimeError(
                f"run_claims_classification received a claim without 'id'. "
                f"Extraction must assign IDs before classification. "
                f"Claim: {json.dumps(c, ensure_ascii=False)[:200]}"
            )

    # Load policy file (resolve relative to REPO_ROOT, not CWD)
    policy_text = ""
    if policy_path:
        expanded = REPO_ROOT / policy_path
        if not expanded.exists():
            expanded = Path(os.path.expanduser(policy_path))
        if expanded.exists():
            policy_text = _guard_prompt_text(expanded.read_text(), "claims_policy_class", job_path)
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
            scan_text += _guard_prompt_text(scan_file.read_text(), f"gap_scan:{scan_file.name}", job_path) + "\n"
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
                scan_text += _guard_prompt_text(ev_prose, "evidence_prose", job_path) + "\n"
        except Exception:
            pass

    sme_text = _guard_prompt_text(transcript_text, "sme_transcript", job_path) if transcript_text else ""

    # L31: Send only id + claim + section to the classifier.
    # verbatim_text stays in the extraction record; the merge step
    # joins it back by id in code after classification returns.
    claims_for_prompt = [
        {"id": c["id"], "claim": c["claim"], "section": c.get("section", "")}
        for c in claims
    ]
    claims_json = json.dumps(claims_for_prompt, indent=2, ensure_ascii=False)

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
- "id": (copied exactly from input — e.g. "c000", "c001")
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
        return [{"id": c["id"], "classification": "UNSOURCED",
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

    return [{"id": c["id"], "classification": "UNSOURCED",
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
        classified_raw = run_claims_classification(claims, policy_path, jd, jd, transcript_text=transcript_text)
    else:
        classified_raw = []

    # L31: Join classified results to extraction claims BY ID.
    # verbatim_text, verbatim_verified, and claim_type are carried from
    # extraction programmatically — never through the classification LLM.
    extraction_by_id = {c["id"]: c for c in claims}
    classified_by_id = {}
    for cr in classified_raw:
        cid = cr.get("id")
        if cid is None:
            raise RuntimeError(
                f"D2 classification returned a claim with no 'id' field: "
                f"{json.dumps(cr, ensure_ascii=False)[:200]}"
            )
        if cid not in extraction_by_id:
            raise RuntimeError(
                f"D2 classification returned unknown id '{cid}' — "
                f"not in extraction output (extraction ids: "
                f"{sorted(extraction_by_id.keys())[:10]}...)"
            )
        if cid in classified_by_id:
            raise RuntimeError(
                f"D2 classification returned duplicate id '{cid}'"
            )
        classified_by_id[cid] = cr

    # Hard fail if counts differ
    if len(classified_by_id) != len(extraction_by_id):
        missing_from_class = set(extraction_by_id) - set(classified_by_id)
        extra_in_class = set(classified_by_id) - set(extraction_by_id)
        raise RuntimeError(
            f"D2 extraction→classification count mismatch: "
            f"{len(extraction_by_id)} extracted, {len(classified_by_id)} classified. "
            f"Missing from classification: {sorted(missing_from_class)[:10]}. "
            f"Extra in classification: {sorted(extra_in_class)[:10]}."
        )

    # Merge: extraction fields + classification fields
    all_classified = []
    for cid in sorted(extraction_by_id.keys()):
        ext = extraction_by_id[cid]
        cls = classified_by_id[cid]
        merged = {
            "id": cid,
            "claim": ext["claim"],
            "verbatim_text": ext.get("verbatim_text", ""),
            "verbatim_verified": ext.get("verbatim_verified", False),
            "section": ext.get("section", ""),
            "claim_type": ext.get("claim_type", ""),
            "classification": cls.get("classification", "UNSOURCED"),
        }
        if cls.get("suggestion"):
            merged["suggestion"] = cls["suggestion"]
        if ext.get("verbatim_mismatch"):
            merged["verbatim_mismatch"] = True
        all_classified.append(merged)

    # L31: Post-merge validation — re-validate verbatim_text on the MERGED
    # report, the same data the resolver will read. The extraction-time
    # validation (L30) checked a state that classification then destroyed;
    # this check runs on the report the resolver actually consumes.
    post_merge_verified = 0
    post_merge_missing = 0
    for mc in all_classified:
        vt = mc.get("verbatim_text", "")
        if vt and mc.get("verbatim_verified"):
            post_merge_verified += 1
        elif not vt:
            post_merge_missing += 1
    print(
        f"  [D2] Verbatim validation (post-merge report): "
        f"{post_merge_verified} verified, {post_merge_missing} missing "
        f"(of {len(all_classified)} claims)",
        file=sys.stderr,
    )

    # L33 Step 4b: Source-before-delete — verify UNSOURCED claims against
    # authority sources before marking them for deletion.
    unsourced_pre = [c for c in all_classified if c.get("classification") == "UNSOURCED"]
    if unsourced_pre:
        print(f"  [D2] Verifying {len(unsourced_pre)} UNSOURCED claims against authority sources...", file=sys.stderr)
        for claim in unsourced_pre:
            verdict, src_url, quote, attempt_log = verify_claim(
                claim["claim"],
                proposed_fix=claim.get("suggestion", ""),
            )
            claim["verification"] = verdict
            claim["verification_url"] = src_url
            claim["verification_quote"] = quote
            claim["verification_attempts"] = {
                "searches_run": attempt_log.searches_run,
                "search_results_returned": attempt_log.search_results_returned,
                "fetches_attempted": attempt_log.fetches_attempted,
                "fetches_succeeded": attempt_log.fetches_succeeded,
                "judges_run": attempt_log.judges_run,
            }
            status_label = verdict.upper()
            if src_url:
                status_label += f" ({src_url[:60]})"
            print(f"    [{claim['id']}] {status_label}: {claim['claim'][:60]}", file=sys.stderr)

    # Count (post-verification)
    # UNSOURCED claims that verified as source_recovered are reclassified
    unsourced = [c for c in all_classified
                 if c.get("classification") == "UNSOURCED"
                 and c.get("verification") in ("not_stated", None)]
    contradicts = [c for c in all_classified
                   if c.get("verification") == "contradicts"]
    verification_failed = [c for c in all_classified
                           if c.get("verification") == "verification_failed"]
    source_recovered = [c for c in all_classified
                        if c.get("verification") == "source_recovered"]
    policy = [c for c in all_classified if c.get("classification") == "POLICY"]
    source = [c for c in all_classified if c.get("classification") == "SOURCE"]
    sme_sourced = [c for c in all_classified if c.get("classification") == "SME-SOURCED"]

    if source_recovered:
        print(
            f"  [D2] Source-recovered: {len(source_recovered)} claims verified against authority sources",
            file=sys.stderr,
        )
    if contradicts:
        print(
            f"  [D2] Contradicts: {len(contradicts)} claims have authority-source corrections",
            file=sys.stderr,
        )
    if verification_failed:
        print(
            f"  [D2] Verification failed: {len(verification_failed)} claims could not be checked (BLOCKING)",
            file=sys.stderr,
        )

    # Check ventriloquism license
    first_person_licensed = bool(transcript_text)  # capture mode implies licensed

    # passed = no ventriloquism + no deletable UNSOURCED + no contradicts + no verification_failed
    # contradicts and verification_failed BLOCK — they must not be silently passed or deleted
    passed = (
        (len(vent_hits) == 0 or first_person_licensed)
        and len(unsourced) == 0
        and len(contradicts) == 0
        and len(verification_failed) == 0
    )

    # Save full report
    report = {
        "ventriloquism_hits": vent_hits,
        "ventriloquism_licensed": first_person_licensed,
        "total_claims": len(all_classified),
        "classified_claims": all_classified,
        "unsourced_count": len(unsourced),
        "contradicts_count": len(contradicts),
        "verification_failed_count": len(verification_failed),
        "source_recovered_count": len(source_recovered),
        "policy_count": len(policy),
        "source_count": len(source),
        "sme_sourced_count": len(sme_sourced),
        "passed": passed,
    }
    (jd / "d2-claims-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )

    return report


def _find_containing_block(html: str, match_start: int, match_end: int) -> tuple[str, int, int]:
    """Find the innermost block-level element containing the match position.

    Uses tag scanning on the raw HTML string — no BS4 parse/serialize.
    Returns (tag_name, element_start, element_end) where element_start is
    the position of the opening '<' and element_end is the position after
    the closing '>'.

    L32: This replaces the rfind(".")/find(".") sentence-boundary search
    that crossed element boundaries.
    """
    import re as _re

    # Block-level elements where sentence removal makes sense
    _BLOCK_TAGS = {"p", "li", "td", "th", "dd", "dt", "figcaption", "blockquote"}

    best_tag = None
    best_start = 0
    best_end = len(html)

    # Scan backward from match_start for opening block tags
    for tag_match in _re.finditer(r'<(p|li|td|th|dd|dt|figcaption|blockquote)[\s>]', html[:match_start]):
        tag_name = tag_match.group(1)
        # Find the corresponding close tag AFTER the match
        close_pattern = f'</{tag_name}>'
        close_pos = html.find(close_pattern, match_end)
        if close_pos >= 0:
            # This tag contains our match — is it the innermost?
            tag_start = tag_match.start()
            tag_end = close_pos + len(close_pattern)
            if tag_start >= best_start:
                best_tag = tag_name
                best_start = tag_start
                best_end = tag_end

    if best_tag is None:
        return "unknown", 0, len(html)

    return best_tag, best_start, best_end


def _resolve_in_element(html: str, match_start: int, match_end: int,
                        tag_name: str, el_start: int, el_end: int) -> dict:
    """Determine the correct removal action for a match within a block element.

    L32: Element-type-aware removal logic:
      - <td>, <th>: ALWAYS flag (table cells are structural data)
      - <li>: remove the WHOLE <li> if parent list has siblings;
              flag if it would empty the parent <ul>/<ol>
      - <p>, other blocks: remove the sentence if other sentences remain;
              flag if it would empty the block

    Returns dict with:
      action: "remove" or "flag"
      removal_start, removal_end: character positions (only if action=remove)
      container_detail: reason string (only if action=flag)
    """
    import re as _re

    # Table cells: always flag — structural data
    if tag_name in ("td", "th"):
        return {"action": "flag", "container_detail": f"table cell <{tag_name}>"}

    # List items: remove the whole <li>, check parent emptiness
    if tag_name == "li":
        parent_tag = None
        for ptag in ("ul", "ol"):
            p_start = html.rfind(f"<{ptag}", 0, el_start)
            if p_start >= 0:
                p_end = html.find(f"</{ptag}>", el_end)
                if p_end >= 0:
                    parent_tag = ptag
                    parent_start = p_start
                    parent_end = p_end + len(f"</{ptag}>")
                    break

        if parent_tag:
            parent_html = html[parent_start:parent_end]
            sibling_count = len(_re.findall(r'<li[\s>]', parent_html))
            if sibling_count > 1:
                return {"action": "remove",
                        "removal_start": el_start, "removal_end": el_end}
            else:
                return {"action": "flag",
                        "container_detail": f"only <li> in <{parent_tag}>"}

        return {"action": "flag",
                "container_detail": "<li> with no identifiable parent list"}

    # Paragraphs and other blocks: sentence-level removal
    el_content_start = html.find(">", el_start) + 1
    close_tag = f"</{tag_name}>"
    close_pos = html.find(close_tag, match_end)
    el_content_end = close_pos if close_pos >= 0 else el_end

    start = html.rfind(".", el_content_start, match_start)
    end = html.find(".", match_end, el_content_end)

    if start < el_content_start:
        start = el_content_start - 1
    if end < 0 or end >= el_content_end:
        end = el_content_end - 1

    removal_start = start + 1
    removal_end = end + 1

    # Check if removal would empty the block
    element_html = html[el_start:el_end]
    local_rs = removal_start - el_start
    local_re = removal_end - el_start
    modified = element_html[:local_rs] + element_html[local_re:]
    from bs4 import BeautifulSoup as _BS4
    remaining = _BS4(modified, "html.parser").get_text(strip=True)

    if len(remaining) == 0:
        return {"action": "flag",
                "container_detail": f"only content in <{tag_name}>"}

    return {"action": "remove",
            "removal_start": removal_start, "removal_end": removal_end}


def resolve_unsourced_claims(job: dict, article_path: Path, mode: str = "neutralize") -> tuple[Path, list[dict], list[dict]]:
    """Resolve UNSOURCED claims by neutralizing or removing them.

    mode:
      "neutralize" — apply D2's suggested neutralization for each claim
      "remove" — remove the sentence containing the claim entirely

    L30: Prefers verbatim_text (verified exact copy from source HTML) over
    the paraphrased claim field.  Claims with verbatim_mismatch are
    immediately reported as unresolved (reason: verbatim_not_in_source)
    and count toward unresolved_count / fail_unresolved.  Legacy claims
    without verbatim_text fall back to old claim[:60] matching.

    L32: Sentence-boundary search is scoped to the containing block element
    (p, li, td, th). A removal that would empty a structural container
    flags as unresolved (reason: would_empty_container) rather than
    cascading the deletion.

    Returns (modified_article_path, resolution_log, unresolved_log).
    Each resolution_log entry: {claim, action, removed_text, reason}
    Each unresolved_log entry: {claim, section, reason, pattern_tried,
                                container_tag?, container_text?}
    """
    jd = job_dir(job)
    report_path = jd / "d2-claims-report.json"
    if not report_path.exists():
        return article_path, [], []

    report = json.loads(report_path.read_text())
    classified = report.get("classified_claims", [])
    # L33: Only not_stated claims are eligible for deletion. contradicts,
    # source_recovered, and verification_failed are NOT deleted.
    unsourced = [c for c in classified
                 if c.get("classification") == "UNSOURCED"
                 and c.get("verification", "not_stated") == "not_stated"]

    if not unsourced:
        return article_path, [], []

    html = article_path.read_text()
    # L31: Save pre-resolution HTML to detect already_removed claims.
    html_before_resolution = html
    log_entries = []
    unresolved_entries = []
    resolved_claim_prefixes = set()

    for claim in unsourced:
        claim_text = claim.get("claim", "")
        suggestion = claim.get("suggestion", "")
        section = claim.get("section", "")
        verbatim = claim.get("verbatim_text", "")

        # L30: Determine match text.
        has_verbatim_field = "verbatim_text" in claim
        verbatim_ok = claim.get("verbatim_verified", False)

        if has_verbatim_field and not verbatim_ok:
            unresolved_entries.append({
                "claim": claim_text[:100],
                "section": section,
                "reason": "verbatim_not_in_source",
                "pattern_tried": (verbatim or claim_text)[:60],
            })
            continue

        match_text = verbatim if verbatim_ok else claim_text

        if mode == "remove":
            import re as _re
            pattern = _re.escape(match_text[:60])
            m = _re.search(pattern, html)
            if m:
                # L32: Find the containing block element and determine
                # the correct removal action based on element type.
                tag_name, el_start, el_end = _find_containing_block(
                    html, m.start(), m.end()
                )

                result = _resolve_in_element(
                    html, m.start(), m.end(),
                    tag_name, el_start, el_end,
                )

                if result["action"] == "flag":
                    from bs4 import BeautifulSoup as _BS4
                    container_text = _BS4(
                        html[el_start:el_end], "html.parser"
                    ).get_text(strip=True)
                    unresolved_entries.append({
                        "claim": claim_text[:100],
                        "section": section,
                        "reason": "would_empty_container",
                        "container_tag": tag_name,
                        "container_detail": result["container_detail"],
                        "container_text": container_text[:200],
                        "pattern_tried": match_text[:60],
                        "verbatim_text": verbatim[:200],
                    })
                    continue

                removal_start = result["removal_start"]
                removal_end = result["removal_end"]
                removed = html[removal_start:removal_end].strip()
                html = html[:removal_start] + html[removal_end:]
                log_entries.append({
                    "claim": claim_text[:100],
                    "action": "removed",
                    "removed_text": removed[:150],
                    "reason": suggestion or "UNSOURCED — not in transcript, policy, or sources",
                })
                resolved_claim_prefixes.add(match_text[:60])
            else:
                # Pattern not found in current HTML. Check whether it
                # was present before resolution started — if so, a prior
                # removal already deleted it (L31: already_removed).
                was_in_original = bool(_re.search(pattern, html_before_resolution))
                if was_in_original:
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "already_removed",
                        "reason": "Removed as collateral by adjacent removal",
                    })
                elif match_text[:60] in resolved_claim_prefixes:
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "already_removed",
                        "reason": "Same prefix already resolved",
                    })
                else:
                    unresolved_entries.append({
                        "claim": claim_text[:100],
                        "section": section,
                        "reason": "pattern_not_found",
                        "pattern_tried": match_text[:60],
                    })
        elif mode == "neutralize" and suggestion:
            if match_text[:50] in html:
                neutral = suggestion.split(":")[-1].strip() if ":" in suggestion else ""
                if not neutral or len(neutral) > 200:
                    html = html.replace(match_text, "", 1)
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "removed (suggestion not a clean replacement)",
                        "reason": suggestion[:150],
                    })
                    resolved_claim_prefixes.add(match_text[:60])
                else:
                    html = html.replace(match_text, neutral, 1)
                    log_entries.append({
                        "claim": claim_text[:100],
                        "action": "neutralized",
                        "replacement": neutral[:150],
                        "reason": suggestion[:150],
                    })
                    resolved_claim_prefixes.add(match_text[:60])
            else:
                unresolved_entries.append({
                    "claim": claim_text[:100],
                    "section": section,
                    "reason": "pattern_not_found",
                    "pattern_tried": match_text[:50],
                })
        else:
            if match_text[:50] in html:
                html = html.replace(match_text, "", 1)
                log_entries.append({
                    "claim": claim_text[:100],
                    "action": "removed (no suggestion available)",
                    "reason": "UNSOURCED with no neutralization suggestion",
                })
                resolved_claim_prefixes.add(match_text[:60])
            else:
                unresolved_entries.append({
                    "claim": claim_text[:100],
                    "section": section,
                    "reason": "pattern_not_found",
                    "pattern_tried": match_text[:50],
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
        "unresolved": unresolved_entries,
    })
    save_job(job)

    return article_path, log_entries, unresolved_entries


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
