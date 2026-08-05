#!/usr/bin/env python3
"""
LRG Featured Image Pipeline — Batch 2: June Bastrop Guides (replace existing)
"""
import os, json, base64, time
from pathlib import Path
from PIL import Image, ImageDraw
import urllib.request

API_KEY = os.environ["OPENAI_API_KEY"]
LOGO_PATH = "/tmp/lrg-logo-real.png"
OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/lrg"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Bastrop neighborhood scenes — each gets a distinct scene to avoid sameness
POSTS = [
    {"id": 4930, "title": "Tahitian Village in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "Tahitian Village, Bastrop TX",
     "scene": "Aerial view of a wooded lakeside community in Bastrop County Texas with tall pine trees, scattered homes on large lots near a lake, winding roads, lush green canopy, warm golden hour light, photorealistic cinematic wide shot"},
    {"id": 4929, "title": "Best Neighborhoods in Bastrop, TX (2026 Guide)",
     "headline_short": None,
     "scene": "Panoramic view of downtown Bastrop Texas Main Street with historic brick storefronts, the Colorado River in the background, mature pecan trees, charming small-town Texas atmosphere, warm afternoon light, photorealistic wide shot"},
    {"id": 4928, "title": "The Colony in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "The Colony, Bastrop TX",
     "scene": "A modern master-planned community in Central Texas with new construction homes, manicured lawns, community pool and amenity center, walking trails, young families, warm evening light, photorealistic cinematic wide shot"},
    {"id": 4981, "title": "Circle D-KC Estates in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "Circle D-KC Estates, Bastrop TX",
     "scene": "Rural Texas ranchette community with homes on acreage lots, white fence lines, horses grazing in a pasture, rolling Central Texas hills with live oaks, warm golden hour, photorealistic cinematic wide shot"},
    {"id": 4980, "title": "Bastrop Crossing in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "Bastrop Crossing, Bastrop TX",
     "scene": "A suburban subdivision entrance in Bastrop Texas with stone monument sign, tree-lined boulevard, neat single-family homes, sidewalks, families walking, warm afternoon Texas light, photorealistic wide shot"},
    {"id": 4979, "title": "The Hills at Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "The Hills at Bastrop, TX",
     "scene": "Elevated view of a hillside neighborhood in Bastrop County with homes built into rolling terrain, native Texas live oaks and cedar, scenic overlook of the Colorado River valley, golden sunset, photorealistic cinematic wide shot"},
    {"id": 4978, "title": "Riverside in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "Riverside, Bastrop TX",
     "scene": "Charming riverside neighborhood along the Colorado River in Bastrop Texas, homes with river views, tall pecan and cypress trees along the riverbank, a kayak on calm water, warm morning mist, photorealistic wide shot"},
    {"id": 4977, "title": "Downtown Bastrop & Historic District: 2026 Neighborhood Guide",
     "headline_short": "Downtown Bastrop & Historic District",
     "scene": "Historic downtown Bastrop Texas at dusk with warm string lights along Main Street, restored brick buildings, the 1889 opera house, pedestrians strolling, the Colorado River bridge visible in background, twilight glow, photorealistic wide shot"},
    {"id": 4967, "title": "ColoVista in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "ColoVista, Bastrop TX",
     "scene": "Upscale golf course community in Bastrop County Texas with a pristine green fairway, large custom homes overlooking the course, Colorado River visible in the distance, mature trees, warm afternoon light, photorealistic cinematic wide shot"},
    {"id": 4966, "title": "Pine Forest in Bastrop, TX: 2026 Neighborhood Guide",
     "headline_short": "Pine Forest, Bastrop TX",
     "scene": "A neighborhood nestled among tall loblolly pines in Bastrop Texas, dappled sunlight filtering through the pine canopy onto a quiet residential street, homes with wooded lots, peaceful atmosphere, photorealistic cinematic wide shot"},
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
        "model": "gpt-image-2", "prompt": prompt,
        "n": 1, "size": "1536x1024", "quality": "high",
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=payload,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start
    b64 = result["data"][0]["b64_json"]
    raw_path = OUTPUT_DIR / f"post-{post['id']}-raw.png"
    raw_path.write_bytes(base64.b64decode(b64))
    return raw_path, elapsed


def composite_logo(raw_path, post_id):
    base = Image.open(raw_path).convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo_target_w = 220
    scale = logo_target_w / logo.width
    logo_resized = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS)
    backing = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(backing)
    pad, logo_x, logo_y = 12, 24, 20
    draw.rounded_rectangle(
        [logo_x - pad, logo_y - pad, logo_x + logo_resized.width + pad, logo_y + logo_resized.height + pad],
        radius=8, fill=(10, 22, 40, 160))
    base = Image.alpha_composite(base, backing)
    base.paste(logo_resized, (logo_x, logo_y), logo_resized)
    final = base.convert("RGB")
    final_path = OUTPUT_DIR / f"post-{post_id}-final.jpg"
    final.save(final_path, "JPEG", quality=92)
    return final_path


def auto_qa(final_path, post):
    with open(final_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    headline = post.get("headline_short") or post["title"]
    qa_prompt = f"""You are a strict QA reviewer for branded blog featured images.
Image should be a professional real estate graphic for: "{post['title']}"
Headline on image should read: "{headline}"
Check: (1) Headline legible, correctly spelled? (2) Scene appropriate, no AI artifacts? (3) LRG logo top-left clean? (4) Readable at ~300px thumbnail? (5) Professional overall?
Reply EXACTLY:
VERDICT: PASS or FAIL
HEADLINE_TEXT_FOUND: [text]
HEADLINE_SPELLING: OK or [error]
SCENE_QUALITY: OK or [issue]
LOGO: OK or [issue]
THUMBNAIL_READABLE: YES or NO_TOO_DENSE
NOTES: [observations]"""
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": qa_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}}
        ]}], "max_tokens": 400}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    qa_text = result["choices"][0]["message"]["content"]
    (OUTPUT_DIR / f"post-{post['id']}-qa.txt").write_text(qa_text)
    return qa_text


def main():
    print("=" * 60)
    print("LRG Batch 2 — June Bastrop Guides (10 posts, replace existing)")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    results = []
    for i, post in enumerate(POSTS):
        pid = post["id"]
        print(f"\n[{i+1}/10] Post {pid}: {post['title'][:55]}...")
        try:
            raw_path, elapsed = generate_image(post)
            print(f"  Generated in {elapsed:.0f}s")
            final_path = composite_logo(raw_path, pid)
            print(f"  Logo composited")
            qa_text = auto_qa(final_path, post)
            verdict = "PASS" if "VERDICT: PASS" in qa_text else "FAIL"
            thumb_ok = "THUMBNAIL_READABLE: YES" in qa_text
            print(f"  QA: {verdict} | Thumbnail: {'YES' if thumb_ok else 'FLAGGED'}")
            results.append({"id": pid, "title": post["title"],
                            "headline": post.get("headline_short") or post["title"],
                            "verdict": verdict, "file": str(final_path), "qa": qa_text})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"id": pid, "title": post["title"],
                            "headline": post.get("headline_short") or post["title"],
                            "verdict": "ERROR", "file": "", "qa": str(e)})
        if i < len(POSTS) - 1:
            time.sleep(3)

    # Summary
    print("\n" + "=" * 60)
    passes = [r for r in results if r["verdict"] == "PASS"]
    fails = [r for r in results if r["verdict"] != "PASS"]
    print(f"PASS: {len(passes)} | FAIL/ERROR: {len(fails)}")
    for r in results:
        flag = ""
        if "THUMBNAIL_READABLE: NO" in r.get("qa", ""):
            flag = " [THUMB WARNING]"
        print(f"  [{r['verdict']}] Post {r['id']}: {r['title'][:60]}{flag}")
        if r["headline"] != r["title"]:
            print(f"         Headline: \"{r['headline']}\"")
        print(f"         File: {r['file']}")

    # Append to review queue
    report_path = OUTPUT_DIR / "batch2-review-queue.md"
    lines = [f"# Batch 2 — June Bastrop Guides\nPASS: {len(passes)} | FAIL: {len(fails)}\n"]
    for r in results:
        lines.append(f"- [{r['verdict']}] Post {r['id']}: {r['title']}")
        if r["headline"] != r["title"]:
            lines.append(f"  Headline: \"{r['headline']}\"")
        lines.append(f"  File: {r['file']}\n")
    report_path.write_text("\n".join(lines))
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
