#!/usr/bin/env python3
"""
LRG Featured Image Pipeline — Batch 3: June 7 Spanish guides + Tesla posts
"""
import os, json, base64, time
from pathlib import Path
from PIL import Image, ImageDraw
import urllib.request

API_KEY = os.environ["OPENAI_API_KEY"]
LOGO_PATH = "/tmp/lrg-logo-real.png"
OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/lrg"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

POSTS = [
    {"id": 5160, "title": "Stone Oak en San Antonio: Guía del Vecindario (2026)",
     "headline_short": "Stone Oak, San Antonio",
     "scene": "Upscale suburban Stone Oak neighborhood in north San Antonio Texas with large two-story homes, manicured lawns, mature live oak trees, gated community entrance, warm golden hour light, photorealistic cinematic wide shot"},
    {"id": 5161, "title": "Alamo Ranch en San Antonio: Guía del Vecindario (2026)",
     "headline_short": "Alamo Ranch, San Antonio",
     "scene": "Master-planned community Alamo Ranch in far west San Antonio Texas with new construction homes, community park with playground, walking trails, hill country views in the background, families outdoors, warm afternoon light, photorealistic cinematic wide shot"},
    {"id": 5162, "title": "Southtown en San Antonio: Guía del Vecindario (2026)",
     "headline_short": "Southtown, San Antonio",
     "scene": "Vibrant Southtown arts district in San Antonio Texas with colorful murals on historic buildings, eclectic cafes and galleries along South Alamo Street, pedestrians walking, urban neighborhood feel, warm evening light, photorealistic cinematic wide shot"},
    {"id": 5163, "title": "The Colony en Bastrop, TX: Guía del Vecindario (2026)",
     "headline_short": "The Colony, Bastrop TX",
     "scene": "A modern master-planned community in Bastrop Texas with new construction homes, manicured lawns, community pool and amenity center, walking trails, young families, warm evening light, photorealistic cinematic wide shot"},
    {"id": 5164, "title": "Vecindarios cerca de Lackland AFB: Guía para Familias Militares (2026)",
     "headline_short": "Vecindarios cerca de Lackland AFB",
     "scene": "Aerial view of suburban neighborhoods near Lackland Air Force Base in San Antonio Texas, neat rows of military-friendly family homes, wide tree-lined streets, a military base visible in the distance, warm afternoon light, photorealistic cinematic wide shot"},
    {"id": 5152, "title": "Tesla Employees Moving to Bastrop, TX: 2026 Relocation Guide",
     "headline_short": "Tesla Employees Moving to Bastrop, TX",
     "scene": "A panoramic view of Bastrop Texas from the Colorado River bridge, downtown Bastrop visible with historic buildings, lush pine and pecan trees, in the distance a modern industrial facility suggesting Tesla Gigafactory, warm golden hour light, photorealistic cinematic wide shot"},
    {"id": 5153, "title": "Tesla Jobs: Moving to East Austin and Del Valle (2026 Guide)",
     "headline_short": "Tesla Jobs: East Austin & Del Valle",
     "scene": "Aerial view of East Austin Texas neighborhoods near the Tesla Gigafactory, modern suburban homes mixed with urban development, Austin skyline in the background, Colorado River, warm sunset glow, photorealistic cinematic wide shot"},
]

STYLE_PROMPT = """Style: Professional real estate marketing graphic.
Color palette: deep navy (#0A1628) gradient background blending into the scene photograph.
The scene photograph occupies the right ~60% of the image.
The left ~40% has a dark navy gradient overlay where the headline text will be placed.
The headline text "{headline}" should be rendered in large, bold, clean white sans-serif font
(like Montserrat or Helvetica Bold) in the upper-left area, left-aligned, with generous line breaks.
Below the headline, in smaller text, render "LRGREALTY.COM" in a muted gray.
Do NOT include any logos, watermarks, or icons — just the scene, gradient, and text.
The overall feel should be premium, modern real estate branding — NOT a stock photo, NOT clipart.
Aspect ratio is landscape (1536x1024). The image should look like a high-end blog header graphic."""


def generate_image(post):
    headline = post.get("headline_short") or post["title"]
    prompt = STYLE_PROMPT.format(headline=headline) + "\n\nScene description: " + post["scene"]

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
    raw_path = OUTPUT_DIR / f"post-{post['id']}-raw.png"
    raw_path.write_bytes(img_bytes)
    return raw_path, elapsed


def composite_logo(raw_path, post_id):
    base = Image.open(raw_path).convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA")

    logo_target_w = 220
    scale = logo_target_w / logo.width
    logo_resized = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS)

    backing = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(backing)
    pad = 12
    logo_x, logo_y = 24, 20
    draw.rounded_rectangle(
        [logo_x - pad, logo_y - pad,
         logo_x + logo_resized.width + pad, logo_y + logo_resized.height + pad],
        radius=8,
        fill=(10, 22, 40, 160),
    )

    base = Image.alpha_composite(base, backing)
    base.paste(logo_resized, (logo_x, logo_y), logo_resized)

    final = base.convert("RGB")
    final_path = OUTPUT_DIR / f"post-{post_id}-final.jpg"
    final.save(final_path, "JPEG", quality=92)
    return final_path


def main():
    print("=" * 60)
    print(f"LRG Featured Image Pipeline — Batch 3 ({len(POSTS)} posts)")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    results = []
    for i, post in enumerate(POSTS):
        pid = post["id"]
        print(f"\n[{i+1}/{len(POSTS)}] Post {pid}: {post['title'][:60]}...")

        final_path = OUTPUT_DIR / f"post-{pid}-final.jpg"
        if final_path.exists():
            print(f"  SKIP (already exists)")
            results.append({"post_id": pid, "status": "skip"})
            continue

        try:
            raw_path, elapsed = generate_image(post)
            print(f"  Generated in {elapsed:.0f}s")

            final_path = composite_logo(raw_path, pid)
            print(f"  Logo composited -> {final_path}")

            results.append({"post_id": pid, "status": "ok", "file": str(final_path)})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"post_id": pid, "status": "error", "error": str(e)})

        if i < len(POSTS) - 1:
            time.sleep(3)

    print("\n" + "=" * 60)
    ok = sum(1 for r in results if r["status"] == "ok")
    skip = sum(1 for r in results if r["status"] == "skip")
    err = sum(1 for r in results if r["status"] == "error")
    print(f"Done: {ok} generated, {skip} skipped, {err} errors")


if __name__ == "__main__":
    main()
