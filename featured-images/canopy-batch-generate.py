#!/usr/bin/env python3
"""
Canopy Insurance Texas — Featured Image Pipeline
Generates branded featured images via gpt-image-2.
Ported from GFP pipeline with Canopy branding (navy/orange Texas insurance theme).

Carries forward ALL GFP fixes:
- clean_headline() with char cap, dangling-word strip, _OVERRIDES table
- Topic-matched scene detection (insurance, not pizza)
- Dedup via scene rotation (no repeated imagery)
- Skip trashed posts
- Sleep 10s between API calls (standing rule for external API)

Usage:
    python3 canopy-batch-generate.py                      # full batch from JSON
    python3 canopy-batch-generate.py --post-ids 3016,3011 # specific posts
    python3 canopy-batch-generate.py --skip-existing       # skip already-generated
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image

import urllib.request

API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not API_KEY:
    print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
    sys.exit(1)

OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/canopy"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
POSTS_JSON = Path(__file__).parent / "canopy-posts.json"

# ---------------------------------------------------------------------------
# Scene descriptions — Texas insurance themed, each visually distinct
# ---------------------------------------------------------------------------
SCENES = {
    "home_exterior": (
        "A beautiful single-story Texas ranch home with a well-maintained lawn at golden hour, "
        "warm sunset glow, mature live oak tree in the front yard, clear blue sky with a few "
        "wispy clouds, San Antonio suburban neighborhood, photorealistic wide shot"
    ),
    "home_storm": (
        "A Texas home after a severe hailstorm, damaged roof shingles visible, dark storm clouds "
        "clearing in the background, insurance adjuster clipboard in foreground, dramatic lighting, "
        "photorealistic wide shot"
    ),
    "home_construction": (
        "A new home under construction in a Texas subdivision, wood framing visible, hard hats "
        "and blueprints on a table, clear blue Texas sky, warm afternoon light, construction "
        "equipment in background, photorealistic wide shot"
    ),
    "auto_highway": (
        "A late-model sedan driving on a Texas highway at golden hour, San Antonio skyline in "
        "the distance, clear warm sky, well-maintained road, photorealistic cinematic wide shot"
    ),
    "auto_classic": (
        "A pristine classic muscle car at a Texas car show, warm afternoon light, well-maintained "
        "paint gleaming, Texas landscape in background, photorealistic automotive photography"
    ),
    "commercial_office": (
        "A modern small business office in Texas with glass windows showing a city skyline, "
        "professional workspace, laptop and documents on desk, warm afternoon lighting, "
        "clean and organized, photorealistic wide shot"
    ),
    "commercial_storefront": (
        "A row of small business storefronts on a sunny Texas street, awnings and signs, "
        "pedestrians walking, warm afternoon light, thriving commercial district feel, "
        "photorealistic wide shot"
    ),
    "contractor_work": (
        "A licensed contractor in safety gear working on a Texas commercial building rooftop, "
        "tool belt, hard hat, clear blue sky, San Antonio skyline in distance, professional "
        "and competent feel, photorealistic wide shot"
    ),
    "contractor_plumbing": (
        "A professional plumber working under a kitchen sink with copper pipes visible, "
        "tool box nearby, modern Texas home interior, warm lighting, clean and professional, "
        "photorealistic wide shot"
    ),
    "contractor_electrical": (
        "A licensed electrician in safety gear working on a commercial electrical panel, "
        "organized wiring, hard hat and safety glasses, modern Texas commercial building, "
        "professional lighting, photorealistic wide shot"
    ),
    "rental_property": (
        "A well-maintained Texas duplex rental property with a 'For Rent' sign on the lawn, "
        "warm afternoon light, manicured landscaping, suburban neighborhood, "
        "photorealistic wide shot"
    ),
    "family_protection": (
        "A Texas family of four standing in front of their home, warm golden hour light, "
        "suburban neighborhood, mature trees, feeling of security and comfort, "
        "photorealistic wide shot"
    ),
    "paperwork_desk": (
        "Close-up of insurance documents and a policy folder on a clean wooden desk, "
        "reading glasses nearby, warm desk lamp light, professional and organized feel, "
        "pen on a signature line, photorealistic still life"
    ),
    "claims_process": (
        "A homeowner documenting storm damage to their roof with a smartphone camera, "
        "damaged shingles visible, clipboard with insurance forms in other hand, "
        "overcast sky after storm, photorealistic wide shot"
    ),
    "texas_landscape": (
        "Panoramic view of a Texas Hill Country landscape at golden hour, rolling green "
        "hills, scattered live oaks, a ranch-style home in the middle distance, warm "
        "sunset tones, photorealistic cinematic wide shot"
    ),
    "business_interruption": (
        "A closed Texas storefront with a 'Temporarily Closed' sign, empty parking lot, "
        "overcast sky, the feeling of business disruption, but signs of recovery — a worker "
        "inside preparing to reopen, photorealistic wide shot"
    ),
}

# Track used scenes to prevent duplicates within a batch
_used_scenes = set()


def detect_scene(title: str, category: str) -> str:
    """Auto-select scene based on article title and category keywords."""
    t = title.lower()
    cat = category.lower()

    # Contractor-specific trades
    if "plumb" in t:
        return SCENES["contractor_plumbing"]
    if "electric" in t:
        return SCENES["contractor_electrical"]
    if "contractor" in t or "builder" in t or "roofing" in t:
        return SCENES["contractor_work"]

    # Claims / filing
    if "claim" in t or "file" in t or "denied" in t:
        return SCENES["claims_process"]

    # Storm / hail / wind / damage
    if any(w in t for w in ["storm", "hail", "wind", "damage", "roof"]):
        return SCENES["home_storm"]

    # New construction
    if "new construction" in t or "builder" in t:
        return SCENES["home_construction"]

    # Business interruption
    if "business interruption" in t or "interruption" in t:
        return SCENES["business_interruption"]

    # Auto / car / vehicle / motorcycle
    if any(w in t for w in ["auto", "car ", "vehicle", "motorcycle", "driving",
                             "accident", "ticket", "sr-22", "dwi"]):
        return SCENES["auto_highway"]
    if "classic" in t or "antique" in t or "agreed value" in t:
        return SCENES["auto_classic"]

    # Landlord / rental / tenant / renters
    if any(w in t for w in ["landlord", "rental", "tenant", "renter", "vacant"]):
        return SCENES["rental_property"]

    # Commercial / business / BOP / workers comp
    if any(w in t for w in ["commercial", "business", "bop ", "workers comp",
                             "liability", "cyber", "directors", "epli"]):
        if "property" in t or "storefront" in t:
            return SCENES["commercial_storefront"]
        return SCENES["commercial_office"]

    # Home insurance (general)
    if any(w in t for w in ["home insurance", "homeowner", "ho-3", "ho-5",
                             "ho3", "ho5", "dwelling", "coverage"]):
        return SCENES["home_exterior"]

    # Policy / comparison / guide / what is
    if any(w in t for w in ["policy", "what is", "guide", "compare", "vs ",
                             "versus", "requirement"]):
        return SCENES["paperwork_desk"]

    # Family / protection / umbrella
    if any(w in t for w in ["family", "umbrella", "protection", "personal"]):
        return SCENES["family_protection"]

    # Category-based fallback
    if "contractor" in cat:
        return SCENES["contractor_work"]
    if "home" in cat:
        return SCENES["home_exterior"]
    if "auto" in cat:
        return SCENES["auto_highway"]
    if "commercial" in cat:
        return SCENES["commercial_office"]
    if "landlord" in cat or "rental" in cat:
        return SCENES["rental_property"]

    # Default: Texas landscape
    return SCENES["texas_landscape"]


def get_unique_scene(title: str, category: str, post_id: int) -> str:
    """Get a scene, avoiding duplicates within the batch."""
    global _used_scenes
    scene = detect_scene(title, category)
    if scene in _used_scenes:
        # Find an unused scene from the same general category
        all_scenes = list(SCENES.values())
        for alt in all_scenes:
            if alt not in _used_scenes:
                scene = alt
                break
    _used_scenes.add(scene)
    return scene


# ---------------------------------------------------------------------------
# Style prompt — Canopy branding (navy #1A365D / orange #F97316)
# ---------------------------------------------------------------------------
STYLE_PROMPT = """Style: Professional insurance marketing graphic for a Texas independent insurance agency.
Color palette: deep navy (#1A365D) gradient background blending into the scene photograph.
The scene photograph occupies the right ~60% of the image.
The left ~40% has a navy-to-dark gradient overlay where the headline text will be placed.
The headline text "{headline}" should be rendered in large, bold, clean white sans-serif font
(like Montserrat or Helvetica Bold) in the upper-left area, left-aligned, with generous line breaks.
Below the headline, in bold orange (#F97316) accent color, render "CANOPYINSURANCETEXAS.COM" in smaller text.
Do NOT include any logos, watermarks, or icons — just the scene, gradient, and text.
The overall feel should be professional, trustworthy, modern insurance branding — NOT stock photo, NOT clipart.
Aspect ratio is landscape (1536x1024). The image should look like a high-end insurance blog header graphic.
IMPORTANT: The headline text must be fully visible and not cut off at ANY edge of the image.
Place text with generous margins (at least 80px from all edges). Text must survive a center-crop to 3:2 ratio."""


def clean_headline(title: str, post_id: int = 0) -> str:
    """Shorten title for image headline legibility.

    Target: <= 38 chars, grammatically complete phrase.
    Carried forward from GFP with Canopy-specific overrides.
    """
    import re
    _OVERRIDES = {
        3015: "TX Renters Insurance for Landlords",
        3241: "What Is an HO-3 Policy?",
        3252: "What Is an HO-5 Policy?",
        3263: "Agreed Value Car Insurance",
    }
    if post_id in _OVERRIDES:
        return _OVERRIDES[post_id]

    # 1. Strip trailing year/parenthetical
    title = re.sub(r'\s*\(.*?\)\s*$', '', title)
    # Strip trailing subtitles after em-dash or colon
    for sep in [' — ', ' – ', ': ']:
        if sep in title:
            parts = title.split(sep, 1)
            if len(parts[0]) >= 18:
                title = parts[0]
                break
    title = title.strip(' —-:,')

    # 2. Drop "in Texas" suffix if > 35 chars
    if len(title) > 35:
        title = re.sub(r',?\s*in Texas\s*$', '', title, flags=re.IGNORECASE).strip(' ,')
    if len(title) > 35:
        title = re.sub(r'\s+in\s+Texas', '', title, flags=re.IGNORECASE).strip()

    # 3. Final truncation at word boundary (target 38)
    if len(title) > 38:
        cut = title[:38].rfind(' ')
        if cut > 18:
            title = title[:cut]

    # 4. Strip trailing dangling words (prepositions, articles, conjunctions)
    _DANGLERS = {'at', 'for', 'in', 'with', 'to', 'the', 'a', 'an', 'and',
                 'or', 'vs', 'of', 'on', 'is', 'by', 'from'}
    words = title.strip().split()
    while words and words[-1].lower().rstrip('.,!?') in _DANGLERS:
        words.pop()
    title = ' '.join(words)

    return title.strip()


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------


def generate_image(headline: str, scene: str, post_id: int) -> tuple[Path, float]:
    """Call gpt-image-2 to generate a branded image."""
    prompt = STYLE_PROMPT.format(headline=headline) + "\n\nScene description: " + scene

    payload = json.dumps({
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": 1,
        "size": "1536x1024",
        "quality": "high",
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start

    b64 = result["data"][0]["b64_json"]
    img_bytes = base64.b64decode(b64)
    raw_path = OUTPUT_DIR / f"post-{post_id}-raw.png"
    raw_path.write_bytes(img_bytes)
    return raw_path, elapsed


def finalize_image(raw_path: Path, post_id: int) -> Path:
    """Convert raw PNG to final JPEG."""
    img = Image.open(raw_path).convert("RGB")
    final_path = OUTPUT_DIR / f"post-{post_id}-final.jpg"
    img.save(final_path, "JPEG", quality=92)
    return final_path


def auto_qa(final_path: Path, title: str, headline: str, post_id: int) -> str:
    """Run GPT-4o vision QA on the generated image."""
    with open(final_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    qa_prompt = f"""You are a strict QA reviewer for branded blog featured images.

The image should be a professional insurance marketing graphic for: "{title}"
The headline text on the image should read: "{headline}"
This is for Canopy Insurance Texas (canopyinsurancetexas.com), a Texas independent insurance agency.

Check these criteria:
1. HEADLINE TEXT: Is the headline text legible, correctly spelled with no garbled/missing/extra characters? Readable at thumbnail size (~300px wide)?
2. SCENE: Is the scene appropriate for a Texas insurance blog post about this topic? No weird AI artifacts?
3. BRANDING: Is "CANOPYINSURANCETEXAS.COM" visible somewhere in the image (usually below the headline in orange)?
4. THUMBNAIL: At ~300px wide (blog grid crop), would the headline still be readable? Flag if text is too small or cut off by a center crop.
5. RELEVANCE: Does the image match the article topic? An insurance article should show insurance-relevant imagery.
6. CROP-SAFE: Is the headline text positioned with enough margin that a 3:2 center crop won't clip it?

Reply with EXACTLY this format:
VERDICT: PASS or FAIL
HEADLINE_TEXT_FOUND: [what you read as the headline]
HEADLINE_SPELLING: OK or [describe error]
SCENE_QUALITY: OK or [describe issue]
RELEVANCE: OK or [describe mismatch]
THUMBNAIL_READABLE: YES or NO_TOO_DENSE
CROP_SAFE: YES or NO_CLIPPED
NOTES: [any other observations]"""

    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": qa_prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"
                }}
            ]}
        ],
        "max_tokens": 400,
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    qa_text = result["choices"][0]["message"]["content"]
    qa_path = OUTPUT_DIR / f"post-{post_id}-qa.txt"
    qa_path.write_text(qa_text)
    return qa_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Canopy Featured Image Pipeline")
    parser.add_argument("--sample", type=int, default=0,
                        help="Generate only first N images (for sample review)")
    parser.add_argument("--post-ids", type=str, default="",
                        help="Comma-separated post IDs to generate")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip posts that already have a final image")
    parser.add_argument("--no-qa", action="store_true",
                        help="Skip auto-QA step (faster for testing)")
    args = parser.parse_args()

    # Load posts
    if args.post_ids:
        # Allow running without JSON file when specific IDs are provided
        target_ids = [int(x) for x in args.post_ids.split(",")]
        if POSTS_JSON.exists():
            all_posts = json.loads(POSTS_JSON.read_text())
            batch = [p for p in all_posts if p["id"] in target_ids]
        else:
            # Minimal stub — caller must provide JSON or these fields
            batch = [{"id": pid, "title": f"Post {pid}", "category": "Unknown"}
                     for pid in target_ids]
    else:
        if not POSTS_JSON.exists():
            print(f"ERROR: {POSTS_JSON} not found. Export posts first.", file=sys.stderr)
            sys.exit(1)
        all_posts = json.loads(POSTS_JSON.read_text())
        batch = all_posts[:args.sample] if args.sample > 0 else all_posts

    print(f"Loaded {len(batch)} posts")
    print("=" * 60)
    print(f"Canopy Featured Image Pipeline — {len(batch)} posts")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    results = []
    gen_count = 0

    for i, post in enumerate(batch):
        pid = post["id"]
        title = post["title"]
        category = post.get("category", "Unknown")
        headline = clean_headline(title, pid)
        scene = get_unique_scene(title, category, pid)

        print(f"\n[{i+1}/{len(batch)}] Post {pid}: {title[:55]}...")
        print(f"  Headline: \"{headline}\" ({len(headline)} chars)")

        # Skip trashed posts
        if post.get("status") == "trash":
            print("  SKIP (trashed)")
            continue

        final_path = OUTPUT_DIR / f"post-{pid}-final.jpg"

        if args.skip_existing and final_path.exists():
            print("  SKIP (already exists)")
            results.append({
                "post_id": pid, "title": title, "headline": headline,
                "verdict": "SKIP", "source": "existing"
            })
            continue

        try:
            raw_path, elapsed = generate_image(headline, scene, pid)
            gen_count += 1
            print(f"  Generated in {elapsed:.0f}s ({gen_count} total)")

            fp = finalize_image(raw_path, pid)
            print(f"  Finalized -> {fp.name}")

            if args.no_qa:
                verdict = "NO_QA"
                qa_text = ""
            else:
                qa_text = auto_qa(fp, title, headline, pid)
                verdict = "PASS" if "VERDICT: PASS" in qa_text else "FAIL"
                thumb_ok = "THUMBNAIL_READABLE: YES" in qa_text
                crop_ok = "CROP_SAFE: YES" in qa_text
                print(f"  QA: {verdict} | Thumb: {'OK' if thumb_ok else 'FLAG'} | Crop: {'OK' if crop_ok else 'FLAG'}")

            results.append({
                "post_id": pid, "title": title, "headline": headline,
                "verdict": verdict, "final": str(fp), "qa": qa_text,
                "source": "generated"
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "post_id": pid, "title": title, "headline": headline,
                "verdict": "ERROR", "qa": str(e), "source": "error"
            })

        # Sleep 10s between API calls (standing rule for external API)
        if i < len(batch) - 1:
            print("  Sleeping 10s...")
            time.sleep(10)

    # Summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)

    passes = [r for r in results if r["verdict"] == "PASS"]
    fails = [r for r in results if r["verdict"] in ("FAIL", "ERROR")]
    skips = [r for r in results if r["verdict"] == "SKIP"]

    print(f"Generated: {gen_count} | PASS: {len(passes)} | FAIL: {len(fails)} | SKIP: {len(skips)}")

    # Write results JSON for deploy script
    results_path = OUTPUT_DIR / "batch-results.json"
    results_path.write_text(json.dumps(results, indent=2))

    # Write human-readable report
    report_lines = [
        "# Canopy Featured Image Batch — Review Queue",
        f"Generated: {gen_count} | PASS: {len(passes)} | FAIL: {len(fails)} | SKIP: {len(skips)}",
        "",
    ]
    if fails:
        report_lines.append("## FLAGGED (review required)")
        for r in fails:
            report_lines.append(f"- Post {r['post_id']}: {r['title']}")
            report_lines.append(f"  Verdict: {r['verdict']}")
            report_lines.append(f"  QA: {r.get('qa', '')[:200]}")
            report_lines.append("")

    report_lines.append("## PASS")
    for r in passes:
        report_lines.append(f"- Post {r['post_id']}: {r['title']}")
        report_lines.append(f"  Headline: \"{r['headline']}\"")
        report_lines.append("")

    report_path = OUTPUT_DIR / "batch-review-queue.md"
    report_path.write_text("\n".join(report_lines))
    print(f"\nReport: {report_path}")
    print(f"Images: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
