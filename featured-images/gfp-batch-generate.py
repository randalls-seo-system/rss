#!/usr/bin/env python3
"""
GFP Featured Image Pipeline — Batch Generator
Generates branded featured images via gpt-image-2 + Pillow logo composite.
Auto-QAs via gpt-4o vision. Does NOT upload or set featured images.

Ported from the LRG pipeline with GFP branding (red/black pizza theme).

Usage:
    python3 gfp-batch-generate.py                    # full batch
    python3 gfp-batch-generate.py --sample 5          # first 5 only
    python3 gfp-batch-generate.py --post-ids 1290,1293 # specific posts
    python3 gfp-batch-generate.py --skip-existing      # skip already-generated
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

API_KEY = os.environ["OPENAI_API_KEY"]
OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/gfp"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
POSTS_JSON = Path(__file__).parent / "gfp-posts.json"

# ---------------------------------------------------------------------------
# Scene descriptions — pizza/food/SA-themed, each visually distinct
# ---------------------------------------------------------------------------
SCENES = {
    "pizza_kitchen": (
        "Interior of a busy pizzeria kitchen with a wood-fired brick oven glowing orange, "
        "a chef stretching dough mid-toss, flour dust in the air, fresh toppings arranged "
        "in stainless steel containers, warm amber lighting, photorealistic wide shot"
    ),
    "pizza_closeup": (
        "Extreme close-up of a freshly baked pepperoni pizza being pulled from a brick oven "
        "on a wooden peel, cheese stretching and bubbling, golden crust, steam rising, "
        "dramatic warm lighting, photorealistic food photography"
    ),
    "pizza_slice": (
        "A perfect triangle slice of cheese pizza being lifted with a dramatic cheese pull, "
        "warm golden light, rustic wooden table background, herbs scattered, "
        "photorealistic food photography macro shot"
    ),
    "family_dinner": (
        "A diverse family of four gathered around a table with open pizza boxes, laughing "
        "and reaching for slices, warm kitchen lighting, San Antonio evening through windows, "
        "cozy and inviting atmosphere, photorealistic wide shot"
    ),
    "pizza_party": (
        "A lively pizza party scene with stacked pizza boxes, paper plates, friends gathered "
        "around a decorated table, balloons and streamers, warm festive lighting, "
        "photorealistic wide shot of celebration"
    ),
    "delivery": (
        "A pizza delivery scene at a suburban front door at dusk, warm porch light, delivery "
        "driver handing over a stack of pizza boxes to a smiling family, San Antonio "
        "neighborhood street in background, photorealistic wide shot"
    ),
    "san_antonio_dining": (
        "Outdoor dining patio in San Antonio's River Walk area at golden hour, string lights "
        "overhead, a table with pizza and cold drinks, lush greenery, warm Texas evening "
        "atmosphere, photorealistic cinematic wide shot"
    ),
    "san_antonio_skyline": (
        "Panoramic view of San Antonio Texas skyline at golden hour with the Tower of the "
        "Americas, River Walk, and Alamo area visible, warm sunset tones, a pizza restaurant "
        "sign glowing in the foreground, photorealistic cinematic wide shot"
    ),
    "toppings_spread": (
        "A beautiful overhead flat-lay of pizza ingredients — fresh mozzarella, basil, "
        "pepperoni, mushrooms, bell peppers, olives, tomato sauce in a bowl, raw dough ball "
        "— on a flour-dusted wooden surface, warm natural lighting, photorealistic food photography"
    ),
    "comparison_table": (
        "Two different pizzas side by side on a rustic wooden table — one classic round "
        "pepperoni, one specialty loaded pizza — with a score card between them, dramatic "
        "top-down food photography lighting, photorealistic"
    ),
    "catering_spread": (
        "A large catering setup with multiple open pizza boxes arranged on a long table, "
        "stacks of plates, breadsticks, wings, and drinks, event hall setting with "
        "San Antonio decor, warm lighting, photorealistic wide shot"
    ),
    "office_lunch": (
        "A modern office break room with colleagues sharing pizza from open boxes, casual "
        "business setting, San Antonio skyline through windows, warm afternoon light, "
        "photorealistic wide shot"
    ),
    "kids_pizza": (
        "Happy children at a birthday party making their own mini pizzas, flour on their "
        "faces, colorful aprons, party decorations, warm and fun atmosphere, "
        "photorealistic wide shot"
    ),
    "military_family": (
        "A military family in a cozy San Antonio home sharing pizza night, American flag "
        "decor on the wall, warm lighting, comfortable living room, kids and parents "
        "eating together, photorealistic wide shot"
    ),
    "game_night": (
        "A group of friends watching football on a big screen TV with pizza boxes on the "
        "coffee table, team jerseys, drinks, warm living room lighting, San Antonio sports "
        "fan atmosphere, photorealistic wide shot"
    ),
    "pizza_science": (
        "Close-up of pizza in an oven with visible cheese bubbling and browning, cross-section "
        "showing layers of dough, sauce, and cheese, warm scientific lighting with slight "
        "diagram overlay feel, photorealistic food science photography"
    ),
    "neighborhood_sa": (
        "Aerial view of a San Antonio residential neighborhood at golden hour with "
        "warm-toned houses, mature trees, and a pizza delivery car on a quiet street, "
        "warm sunset glow, photorealistic cinematic wide shot"
    ),
    "date_night": (
        "A cozy date night scene at a candlelit table with a pizza and wine glasses, "
        "warm romantic lighting, rustic Italian-inspired restaurant interior, "
        "photorealistic cinematic shot"
    ),
}

# ---------------------------------------------------------------------------
# Topic-to-scene mapping — keyword-based auto-detection
# ---------------------------------------------------------------------------


def detect_scene(title: str) -> str:
    """Auto-select scene based on article title keywords."""
    t = title.lower()

    # Comparison / vs articles
    if " vs " in t or "versus" in t or "comparison" in t or "showdown" in t:
        return SCENES["comparison_table"]

    # Catering / large group
    if any(w in t for w in ["cater", "large group", "large famil", "family reunion",
                            "feed a crowd", "party planner", "event"]):
        return SCENES["catering_spread"]

    # Delivery / ordering
    if any(w in t for w in ["delivery", "deliver", "order online", "pickup",
                            "neighborhood we cover"]):
        return SCENES["delivery"]

    # Military / base / PCS / BMT / veteran
    if any(w in t for w in ["military", "pcs", "bmt", "graduation", "lackland",
                            "jbsa", "veteran", "base"]):
        return SCENES["military_family"]

    # Kids / sleepover / birthday / family fun
    if any(w in t for w in ["kid", "sleepover", "birthday", "children", "youth",
                            "babysitter", "soccer tournament"]):
        return SCENES["kids_pizza"]

    # Office / work / friday
    if any(w in t for w in ["office", "workplace", "work lunch", "friday",
                            "finals week", "utsa", "coworker"]):
        return SCENES["office_lunch"]

    # Party / watch party / game / football / fantasy / draft
    if any(w in t for w in ["party", "watch part", "game day", "football",
                            "fantasy", "draft night", "super bowl"]):
        return SCENES["game_night"]

    # Pizza science / food science / why / how / temperature / crust chemistry
    if any(w in t for w in ["science", "why pizza", "temperature", "crispy",
                            "chewy", "browning", "reheated", "curls",
                            "conveyor", "smells"]):
        return SCENES["pizza_science"]

    # Toppings / ingredients / cheese / sauce / allergen
    if any(w in t for w in ["topping", "ingredient", "cheese blend", "sauce type",
                            "allergen", "pepperoni", "mushroom"]):
        return SCENES["toppings_spread"]

    # Menu / deals / specials / pricing / cost
    if any(w in t for w in ["menu", "deal", "special", "price", "cost",
                            "save money", "budget", "under 100", "loyalty"]):
        return SCENES["pizza_closeup"]

    # Pizza styles / types / crust options
    if any(w in t for w in ["style", "crust", "thin crust", "deep dish", "golden",
                            "stuffed", "every pizza", "taco pie", "taco pizza"]):
        return SCENES["pizza_kitchen"]

    # Neighborhood / location / area specific
    if any(w in t for w in ["neighborhood", "southtown", "king william", "stone oak",
                            "helotes", "alamo ranch", "bandera", "potranco",
                            "ingram", "leon springs", "fair oaks", "balcones",
                            "medical center", "usaa"]):
        return SCENES["neighborhood_sa"]

    # Date / wine / romantic
    if any(w in t for w in ["date", "wine", "romantic", "night out"]):
        return SCENES["date_night"]

    # Family / dinner / home
    if any(w in t for w in ["family", "dinner", "home", "first time",
                            "what to order", "comeback", "history",
                            "tradition", "christmas", "thanksgiving",
                            "holiday", "vacation"]):
        return SCENES["family_dinner"]

    # San Antonio local / tourist / events / parks
    if any(w in t for w in ["san antonio", "tourist", "visitor", "river walk",
                            "event", "park", "picnic", "church",
                            "apartment"]):
        return SCENES["san_antonio_dining"]

    # Slice / portion / how many / sizing
    if any(w in t for w in ["slice", "portion", "how many", "sizing",
                            "leftover", "store", "reheat", "etiquette",
                            "fork", "knife"]):
        return SCENES["pizza_slice"]

    # Pizza making / hosting / build your own / oven
    if any(w in t for w in ["making", "host", "build your own", "oven",
                            "homemade", "home pizza"]):
        return SCENES["pizza_kitchen"]

    # Default: hero pizza shot
    return SCENES["pizza_closeup"]


# ---------------------------------------------------------------------------
# Style prompt — GFP branding (red + dark theme)
# ---------------------------------------------------------------------------
STYLE_PROMPT = """Style: Professional pizza restaurant marketing graphic.
Color palette: deep charcoal black (#1a1a1a) gradient background blending into the scene photograph.
The scene photograph occupies the right ~60% of the image.
The left ~40% has a dark charcoal-to-black gradient overlay where the headline text will be placed.
The headline text "{headline}" should be rendered in large, bold, clean white sans-serif font
(like Montserrat or Helvetica Bold) in the upper-left area, left-aligned, with generous line breaks.
Below the headline, in a bold red (#d4212c) accent color, render "GFPSANANTONIO.COM" in smaller text.
Do NOT include any logos, watermarks, or icons — just the scene, gradient, and text.
The overall feel should be bold, appetizing, modern pizza branding — NOT a stock photo, NOT clipart.
Aspect ratio is landscape (1536x1024). The image should look like a high-end food blog header graphic."""


def clean_headline(title: str) -> str:
    """Shorten title for image headline legibility."""
    import re
    # Strip trailing year markers
    title = re.sub(r'\s*\(20\d{2}\)\s*$', '', title)
    # Strip trailing subtitles after em-dash or colon if the first part is long enough
    # e.g. "Best Pizza in San Antonio: A Local's Complete Guide" -> "Best Pizza in San Antonio"
    for sep in [' — ', ' – ', ': ']:
        if sep in title:
            parts = title.split(sep, 1)
            if len(parts[0]) >= 20:
                title = parts[0]
                break
    # Strip "Godfather's Pizza" prefix ONLY if it leaves meaningful text
    stripped = re.sub(r"^Godfather'?s?\s+Pizza\s*", '', title, flags=re.IGNORECASE).strip(' —-:')
    if len(stripped) >= 15 and not stripped.lower().startswith('vs'):
        title = stripped
    title = title.strip(' —-:')
    # Truncate for thumbnail legibility — cut at word boundary
    if len(title) > 45:
        cut = title[:45].rfind(' ')
        if cut > 20:
            title = title[:cut]
    return title.strip()


# ---------------------------------------------------------------------------
# Image generation + compositing
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
    """Convert raw PNG to final JPEG. No logo overlay — branding is
    handled by GFPSANANTONIO.COM text rendered directly into the image
    by gpt-image-2."""
    img = Image.open(raw_path).convert("RGB")
    final_path = OUTPUT_DIR / f"post-{post_id}-final.jpg"
    img.save(final_path, "JPEG", quality=92)
    return final_path


def auto_qa(final_path: Path, title: str, headline: str, post_id: int) -> str:
    """Run GPT-4o vision QA on the generated image."""
    with open(final_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    qa_prompt = f"""You are a strict QA reviewer for branded blog featured images.

The image should be a professional pizza restaurant marketing graphic for: "{title}"
The headline text on the image should read: "{headline}"

Check these criteria:
1. HEADLINE TEXT: Is the headline text legible, correctly spelled with no garbled/missing/extra characters? Readable at thumbnail size (~300px wide)?
2. SCENE: Is the scene appropriate for a pizza restaurant blog post about this topic? No weird AI artifacts?
3. BRANDING: Is "GFPSANANTONIO.COM" visible somewhere in the image (usually below the headline in red)?
4. THUMBNAIL: At ~300px wide, would the headline still be readable? Flag if text is too small.
5. RELEVANCE: Does the image match the article topic? A pizza article should show pizza-related imagery, not unrelated food.

Reply with EXACTLY this format:
VERDICT: PASS or FAIL
HEADLINE_TEXT_FOUND: [what you read as the headline]
HEADLINE_SPELLING: OK or [describe error]
SCENE_QUALITY: OK or [describe issue]
RELEVANCE: OK or [describe mismatch]
THUMBNAIL_READABLE: YES or NO_TOO_DENSE
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
    parser = argparse.ArgumentParser(description="GFP Featured Image Pipeline")
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
    if not POSTS_JSON.exists():
        print(f"ERROR: {POSTS_JSON} not found. Run the PHP export first.", file=sys.stderr)
        sys.exit(1)

    all_posts = json.loads(POSTS_JSON.read_text())
    print(f"Loaded {len(all_posts)} posts from {POSTS_JSON}")

    # Filter
    if args.post_ids:
        target_ids = set(int(x) for x in args.post_ids.split(","))
        batch = [p for p in all_posts if p["id"] in target_ids]
    elif args.sample > 0:
        batch = all_posts[:args.sample]
    else:
        batch = all_posts

    print("=" * 60)
    print(f"GFP Featured Image Pipeline — {len(batch)} posts")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    results = []
    gen_count = 0

    for i, post in enumerate(batch):
        pid = post["id"]
        title = post["title"]
        headline = clean_headline(title)
        scene = detect_scene(title)

        print(f"\n[{i+1}/{len(batch)}] Post {pid}: {title[:55]}...")
        print(f"  Headline: \"{headline}\"")

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
                print(f"  QA: {verdict} | Thumbnail: {'YES' if thumb_ok else 'FLAGGED'}")

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

        # Pause between API calls to avoid rate limits
        if i < len(batch) - 1:
            time.sleep(3)

    # Summary
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)

    passes = [r for r in results if r["verdict"] == "PASS"]
    fails = [r for r in results if r["verdict"] in ("FAIL", "ERROR")]
    skips = [r for r in results if r["verdict"] == "SKIP"]

    print(f"Generated: {gen_count} | PASS: {len(passes)} | FAIL: {len(fails)} | SKIP: {len(skips)}")

    # Write report
    report_lines = [
        "# GFP Featured Image Batch — Review Queue",
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
