#!/usr/bin/env python3
"""Single-post featured image generator using LRG pipeline."""
import os, sys, json, base64, time
from pathlib import Path
from PIL import Image, ImageDraw
import urllib.request

API_KEY = os.environ["OPENAI_API_KEY"]
LOGO_PATH = "/tmp/lrg-logo-real.png"
OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/lrg"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

POST = {
    "id": 7447,
    "title": "Moving to Boerne, TX: A Local Realtor's Guide to Living Here",
    "headline_short": "Moving to Boerne, TX",
    "scene": "Charming small-town Main Street in the Texas Hill Country at golden hour, limestone storefronts with awnings, mature live oak trees lining the street, rolling green hills visible in the background, a family walking on the sidewalk, warm sunset light casting long shadows, photorealistic cinematic wide shot"
}

STYLE_PROMPT = """Create a premium branded blog header image.

LEFT 40% of the image: a solid-to-transparent navy blue gradient (#0b1b3a to transparent), with the headline text "{headline}" in large bold white sans-serif font, vertically centered. Below the headline, add "LRGREALTY.COM" in smaller white caps.

RIGHT 60%: a photorealistic scene filling the rest of the frame, blending seamlessly with the navy gradient.

Do NOT include any logos, watermarks, or icons — just the scene, gradient, and text.
The overall feel should be premium, modern real estate branding — NOT a stock photo, NOT clipart.
Aspect ratio is landscape (1536x1024). The image should look like a high-end blog header graphic."""


def generate_image():
    headline = POST.get("headline_short") or POST["title"]
    prompt = STYLE_PROMPT.format(headline=headline) + "\n\nScene description: " + POST["scene"]

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

    print(f"Generating image for post {POST['id']}...")
    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start
    print(f"  Generated in {elapsed:.1f}s")

    b64 = result["data"][0]["b64_json"]
    img_bytes = base64.b64decode(b64)
    raw_path = OUTPUT_DIR / f"post-{POST['id']}-raw.png"
    raw_path.write_bytes(img_bytes)
    return raw_path


def composite_logo(raw_path):
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
    final_path = OUTPUT_DIR / f"post-{POST['id']}-final.jpg"
    final.save(final_path, "JPEG", quality=92)
    print(f"  Final saved: {final_path}")
    return final_path


def auto_qa(final_path):
    with open(final_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    headline = POST.get("headline_short") or POST["title"]

    qa_prompt = f"""You are a strict QA reviewer for branded blog featured images.

The image should be a professional real estate marketing graphic for the blog post titled: "{POST['title']}"
The headline text on the image should read: "{headline}"

Check these criteria:
1. HEADLINE TEXT: Is the headline text legible, correctly spelled with no garbled/missing/extra characters? Would it be readable at thumbnail size (~300px wide)?
2. SCENE: Is the scene appropriate for the topic? No weird AI artifacts (extra fingers, melted objects, impossible architecture)?
3. BRANDING: Is there an LRG logo in the top-left corner? Is it clean and legible?
4. THUMBNAIL: At ~300px wide, would the headline still be readable? Flag if text is too small or too dense.
5. OVERALL: Does this look like a professional blog header, not a generic stock photo?

Reply with EXACTLY this format:
VERDICT: PASS or FAIL
HEADLINE_TEXT_FOUND: [what you read as the headline]
HEADLINE_SPELLING: OK or [describe error]
SCENE_QUALITY: OK or [describe issue]
LOGO: OK or [describe issue]
THUMBNAIL_READABLE: YES or NO_TOO_DENSE
NOTES: [any other observations]"""

    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": qa_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}}
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

    print("  Running QA...")
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    qa_text = result["choices"][0]["message"]["content"]
    qa_path = OUTPUT_DIR / f"post-{POST['id']}-qa.txt"
    qa_path.write_text(qa_text)
    print(qa_text)
    return qa_text


if __name__ == "__main__":
    # Check logo exists
    if not os.path.exists(LOGO_PATH):
        # Download logo from the batch script's known location
        logo_src = os.path.expanduser("~/randalls-seo-system/featured-images/lrg-logo-real.png")
        if os.path.exists(logo_src):
            import shutil
            shutil.copy2(logo_src, LOGO_PATH)
        else:
            print(f"ERROR: Logo not found at {LOGO_PATH} or {logo_src}")
            sys.exit(1)

    raw = generate_image()
    final = composite_logo(raw)
    auto_qa(final)
    print(f"\nDone. Final image: {final}")
