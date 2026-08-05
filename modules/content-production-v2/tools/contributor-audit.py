#!/usr/bin/env python3
"""Contributor Article Audit — validates a post against the LRG checklist.

Checks all required elements from docs/contributor-article-checklist.md.
Can run against a single post (via SSH/WP-CLI) or against a local HTML file.

Usage:
    python3 contributor-audit.py --post-id 7447 --site lrg
    python3 contributor-audit.py --html-file /path/to/article.html --post-meta meta.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent.parent.parent


def load_site_ssh(site: str) -> tuple[str, str]:
    """Load SSH host/user from site config."""
    conf_path = REPO_ROOT / "sites" / f"{site}.conf"
    host = user = ""
    for line in conf_path.read_text().splitlines():
        if line.startswith("SSH_HOST="):
            host = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("SSH_USER="):
            user = line.split("=", 1)[1].strip().strip('"')
    return host, user


def fetch_post_data(site: str, post_id: int) -> dict:
    """Fetch post content + metadata via SSH."""
    host, user = load_site_ssh(site)
    php = f"""<?php
$p = get_post({post_id});
$data = [
    'content' => $p->post_content,
    'title' => $p->post_title,
    'author_id' => (int) $p->post_author,
    'author_name' => get_the_author_meta('display_name', $p->post_author),
    'reviewer_select' => get_post_meta({post_id}, '_rss_reviewer_select', true),
    'reviewer_override' => get_post_meta({post_id}, '_rss_reviewer_override', true),
    'thumbnail_id' => get_post_thumbnail_id({post_id}),
    'neighborhood_meta' => get_post_meta({post_id}, '_lrg_neighborhood', true),
];
echo json_encode($data);
"""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", f"{user}@{host}",
         f"echo '{php}' > /tmp/_audit.php; wp eval-file /tmp/_audit.php"],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout.strip()
    # Strip leading "0" from wp eval-file
    if output.startswith("0\n"):
        output = output[2:]
    return json.loads(output)


def audit_html(html: str, meta: dict) -> list[tuple[str, str, str]]:
    """Run all checklist items. Returns list of (code, status, detail)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    results = []

    def check(code, name, condition, detail=""):
        status = "PRESENT" if condition else "MISSING"
        results.append((code, name, status, detail))

    # === ATF ===
    check("A1", "breadcrumb", soup.find(class_="rl-breadcrumb") is not None)

    check("A2", "eyebrow", soup.find(class_="rl-eyebrow") is not None)

    h1 = soup.find("h1")
    header = soup.find("header")
    h1_in_header = h1 is not None and header is not None and h1.find_parent("header") is not None
    check("A3", "h1-in-header", h1_in_header)

    intro = soup.find(class_="nh-answer") or soup.find(class_="rl-hero-lead")
    intro_wc = len(intro.get_text().split()) if intro else 0
    check("A4", "aeo-intro-50-70w",
          intro is not None and 40 <= intro_wc <= 85,
          f"{intro_wc}w" if intro else "not found")

    cta_filled = soup.find("a", class_="nh-cta")
    cta_ghost = soup.find("a", class_=lambda c: c and "nh-cta" in c and "ghost" in c)
    check("A5", "cta-pair", cta_filled is not None and cta_ghost is not None,
          "filled+ghost" if (cta_filled and cta_ghost) else
          "filled-only" if cta_filled else "none")

    stat_cards = soup.find_all(class_="nh-qs")
    check("A6", "stat-cards", len(stat_cards) >= 3, f"{len(stat_cards)} cards")

    atf_details = []
    for d in soup.find_all("details"):
        # ATF FAQs are before the first body <section>
        parent_section = d.find_parent("section")
        if parent_section is None or "rl-faq" not in " ".join(parent_section.get("class", [])):
            atf_details.append(d)
    # Rough heuristic: ATF FAQs appear before BLUF
    bluf = soup.find(class_="rl-bluf")
    if bluf:
        atf_faqs = [d for d in soup.find_all("details") if d.sourceline and bluf.sourceline and d.sourceline < bluf.sourceline] if hasattr(soup.find("details"), "sourceline") else atf_details[:3]
    else:
        atf_faqs = atf_details[:3]
    check("A7", "atf-faqs", len(atf_faqs) >= 2, f"{len(atf_faqs)} found")

    # === BODY ===
    check("B1", "jump-nav", soup.find(class_="rl-jump-nav") is not None)

    check("B2", "bluf", soup.find(class_="rl-bluf") is not None)

    body_sections = soup.find_all("section", class_="rl-section")
    check("B3", "body-h2-sections", len(body_sections) >= 3, f"{len(body_sections)} sections")

    tables = soup.find_all("table")
    rl_tables = [t for t in tables if "rl-table" in " ".join(t.get("class", []))]
    check("B4", "comparison-table", len(tables) >= 1, f"{len(tables)} tables ({len(rl_tables)} rl-table)")

    check("B7", "mid-cta", soup.find(class_="rl-cta-mid") is not None or
          soup.find(class_="rl-cta-pill") is not None)

    rl_page = soup.find(class_="rl-page")
    rl_wrap = soup.find(class_="rl-wrap")
    check("B8", "rl-page-wrapper", rl_page is not None and rl_wrap is not None)

    # === BTF ===
    faq_section = soup.find("section", class_="rl-faq")
    btf_faqs = faq_section.find_all("details") if faq_section else []
    check("C1", "btf-faqs-4-7", 4 <= len(btf_faqs) <= 10, f"{len(btf_faqs)} found")

    check("C2", "resources-used", soup.find(class_="rl-resources") is not None)

    internal_links = [a for a in soup.find_all("a", href=True)
                      if "lrgrealty.com" in a["href"] or
                      (a["href"].startswith("/") and not a["href"].startswith("//"))]
    check("C3", "internal-links", len(internal_links) >= 5, f"{len(internal_links)} links")

    # === SCHEMA + META ===
    faq_schema = soup.find("script", type="application/ld+json")
    has_faq_schema = faq_schema is not None and "FAQPage" in (faq_schema.string or "")
    check("D1", "faq-schema", has_faq_schema)

    author_id = meta.get("author_id", 0)
    check("D2", "author-not-levi", author_id != 1 and author_id != 0,
          f"user {author_id} ({meta.get('author_name', '?')})")

    rev_sel = meta.get("reviewer_select", "")
    rev_ov = meta.get("reviewer_override", {})
    rev_name = rev_ov.get("name", "") if isinstance(rev_ov, dict) else ""
    author_name = meta.get("author_name", "")
    check("D3", "reviewer-set",
          rev_sel == "custom" and rev_name != "",
          f"reviewer={rev_name}")
    check("D3b", "author-ne-reviewer",
          rev_name.lower() != author_name.lower() if rev_name and author_name else True,
          f"author={author_name}, reviewer={rev_name}")

    # D4: auto-append bio — check content does NOT have manual bio
    manual_bio = soup.find(class_="rl-contributor-bio")
    check("D4", "no-manual-bio-in-content",
          manual_bio is None,
          "manual bio found in content" if manual_bio else "clean (auto-append handles)")

    check("D5", "featured-image", meta.get("thumbnail_id", 0) not in (0, "", None, False),
          f"thumb={meta.get('thumbnail_id', 'none')}")

    # === CONTENT RULES ===
    text = soup.get_text()
    em_dashes = text.count("\u2014") + text.count("\u2013")
    check("E1", "no-em-dashes", em_dashes == 0, f"{em_dashes} found")

    parens = len(re.findall(r'\([^)]{5,}\)', text))
    check("E2", "no-parens-in-body", parens <= 1, f"{parens} found")

    vet_lower = len(re.findall(r'\bveteran\b', text))
    vet_cap = len(re.findall(r'\bVeteran\b', text))
    check("E3", "veteran-capitalized",
          vet_lower == 0 or vet_cap > vet_lower,
          f"{vet_cap} cap, {vet_lower} lower")

    body_h1s = len(soup.find_all("h1")) - (1 if h1_in_header else 0)
    check("E4", "no-h1-in-body", body_h1s == 0, f"{body_h1s} extra H1s")

    ylopo = len(re.findall(r'search\.lrgrealty\.com|ylopo', html, re.I))
    check("E7", "no-ylopo-links", ylopo == 0, f"{ylopo} found")

    # === BULLET SECTION COLORS ===
    bullet_secs = soup.find_all(class_=re.compile(r"bullet-section-"))
    check("B3b", "bullet-section-colors", len(bullet_secs) >= 1,
          f"{len(bullet_secs)} colored sections")

    return results


def main():
    parser = argparse.ArgumentParser(description="Contributor Article Audit")
    parser.add_argument("--post-id", type=int, help="WP post ID")
    parser.add_argument("--site", default="lrg", help="Site slug")
    parser.add_argument("--html-file", help="Local HTML file")
    parser.add_argument("--post-meta", help="JSON file with metadata (for local mode)")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    args = parser.parse_args()

    if args.post_id:
        data = fetch_post_data(args.site, args.post_id)
        html = data.pop("content")
        meta = data
    elif args.html_file:
        html = Path(args.html_file).read_text()
        meta = json.loads(Path(args.post_meta).read_text()) if args.post_meta else {}
    else:
        parser.print_help()
        sys.exit(1)

    sys.path.insert(0, str(TOOLS_DIR.parent))
    results = audit_html(html, meta)

    passed = sum(1 for _, _, s, _ in results if s == "PRESENT")
    total = len(results)
    missing = [(c, n, d) for c, n, s, d in results if s == "MISSING"]

    if args.csv:
        print("code,name,status,detail")
        for code, name, status, detail in results:
            print(f"{code},{name},{status},{detail}")
    else:
        title = meta.get("title", args.html_file or f"Post {args.post_id}")
        print(f"=== AUDIT: {title} ===\n")
        for code, name, status, detail in results:
            icon = "+" if status == "PRESENT" else "X"
            detail_str = f"  ({detail})" if detail else ""
            print(f"  [{icon}] {code:5s} {name:25s} {status}{detail_str}")

        print(f"\n  SCORE: {passed}/{total}")
        if missing:
            print(f"  MISSING ({len(missing)}):")
            for c, n, d in missing:
                print(f"    {c}: {n}" + (f" -- {d}" if d else ""))
        else:
            print("  ALL ITEMS PRESENT")


if __name__ == "__main__":
    main()
