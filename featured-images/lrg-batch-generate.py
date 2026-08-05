#!/usr/bin/env python3
"""
LRG Featured Image Pipeline — Full Batch
Generates branded featured images via gpt-image-2 + Pillow logo composite.
Auto-QAs via gpt-4o vision. Does NOT upload or set featured images.
"""
import os, sys, json, base64, time, re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
import urllib.request

API_KEY = os.environ["OPENAI_API_KEY"]
LOGO_PATH = "/tmp/lrg-logo-real.png"
OUTPUT_DIR = Path(os.path.expanduser("~/randalls-seo-system/featured-images/lrg"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Scene descriptions by topic category
SCENES = {
    "listings_austin": "Aerial panoramic view of downtown Austin Texas skyline at golden hour with Lady Bird Lake, Congress Avenue bridge, modern high-rises, warm sunset glow, photorealistic cinematic wide shot",
    "listings_sanantonio": "Aerial panoramic view of San Antonio Texas skyline at golden hour with the River Walk, Tower of the Americas, Alamo area, warm sunset light, photorealistic cinematic wide shot",
    "listings_killeen": "Aerial view of Killeen Texas suburban neighborhoods with Fort Cavazos in the background, rolling Central Texas hills, warm afternoon light, photorealistic cinematic wide shot",
    "agent_office": "A bold overhead view of a modern real estate office bullpen with agents at desks, whiteboard with growth charts, Austin skyline through floor-to-ceiling windows, dramatic afternoon light, cinematic wide shot",
    "agent_coaching": "A real estate mentor coaching a junior agent at a conference table with laptops, market reports, and a whiteboard showing a sales pipeline, modern office with city view, warm lighting, photorealistic",
    "agent_field": "A real estate agent showing a suburban Texas home to a young couple on a front porch, warm golden hour light, green lawn, neighborhood street, photorealistic wide shot",
    "agent_growth": "Split-screen style showing a single agent on the left working alone at a desk vs a team of agents on the right collaborating around a table with charts and laptops, modern office, cinematic lighting",
    "agent_leads": "An interconnected network visualization over an aerial view of suburban Austin neighborhoods, showing community connections and real estate activity, warm sunset tones, cinematic wide shot",
    "agent_environment": "A collaborative open-plan real estate office with agents on phones, a training session visible through glass, downtown Austin skyline through windows, energetic morning light, photorealistic",
    "memorial": "Rows of white headstones at a national cemetery with small American flags, golden morning light filtering through oak trees, solemn and respectful atmosphere, photorealistic wide shot",
    "market_sa": "San Antonio residential neighborhood with diverse home styles, mature trees, well-maintained yards, a subtle For Sale sign visible, warm afternoon Texas light, photorealistic",
    "spanish_career": "A diverse group of real estate professionals in a modern office setting, shaking hands over a signed contract, city skyline visible through windows, warm professional lighting, photorealistic",
    "home_buying": "A young family walking toward the front porch of a suburban Texas home with a SOLD sign, green lawn, warm golden hour light, photorealistic wide shot",
    "home_selling": "Aerial view of a well-staged suburban home with an open house event, cars in driveway, warm afternoon light, Texas neighborhood, photorealistic cinematic wide shot",
    "va_loan": "An American flag gently waving in front of a suburban Texas home with a military family moving in, warm morning light, photorealistic wide shot",
    "neighborhood_sa": "Aerial panoramic view of San Antonio Texas residential neighborhoods at golden hour with mature trees, diverse home styles, warm sunset glow, photorealistic cinematic wide shot",
    "neighborhood_austin": "Aerial panoramic view of Austin Texas residential neighborhoods at golden hour with green hills, modern homes, Lady Bird Lake in background, photorealistic cinematic wide shot",
    "neighborhood_killeen": "Aerial view of Killeen Texas suburban neighborhoods with Fort Cavazos in the background, rolling Central Texas hills, warm afternoon light, photorealistic cinematic wide shot",
    "general_tips": "A bright modern kitchen in a Texas home with natural light, granite countertops, and a family gathering, warm and inviting atmosphere, photorealistic wide shot",
    "market_data": "A data dashboard overlay on a San Antonio skyline showing housing charts and graphs, professional modern style, warm sunset tones, photorealistic cinematic wide shot",
}

# --- Spanish post support ---

SSH_CMD = "ssh -i ~/.ssh/wpengine_valn -o StrictHostKeyChecking=no -o ConnectTimeout=10 lrgrealtyblog@lrgrealtyblog.ssh.wpengine.net"


def clean_spanish_headline(title: str, post_id: int = 0) -> str:
    """Strip English parenthetical notes and year suffixes for image headline."""
    # Manual overrides for posts that fail QA with auto-generated headlines
    HEADLINE_OVERRIDES = {
        3971: "Lista PCS: Vender Casa en San Antonio",
        3648: "La Casa Perfecta Dentro de Tu Presupuesto",
        3874: "Eliminar Insectos del Hogar",
        3760: "Mantenimiento de Invierno en el Hogar",
        3594: "10 Consejos para Conservar Energía",
        3803: "De la Clase al Cierre: Bienes Raíces SA",
        3781: "El Lenguaje de la Compra de Viviendas",
        4043: "Decoraciones Navideñas para Vender Casa",
        3767: "Invertir en Alquileres a Corto Plazo",
        3757: "Estrella de la Renovación del Hogar",
    }
    if post_id in HEADLINE_OVERRIDES:
        return HEADLINE_OVERRIDES[post_id]
    # Strip trailing (English note) — parenthetical at end containing ASCII-only text
    title = re.sub(r'\s*\([A-Za-z0-9\s,.:;!?\'"&…–-]+\)\s*$', '', title)
    # Strip trailing year markers like (2026), (2024)
    title = re.sub(r'\s*\(20\d{2}\)\s*$', '', title)
    # Strip leading/trailing whitespace
    title = title.strip()
    # Truncate for thumbnail legibility (max ~45 chars)
    if len(title) > 45:
        cut = title[:45].rfind(' ')
        if cut > 25:
            title = title[:cut]
    return title


def detect_scene(title: str) -> str:
    """Auto-select scene based on Spanish title keywords."""
    t = title.lower()
    if any(w in t for w in ['vecindario', 'vecindarios', 'guía del vecindario', 'helotes', 'rogers ranch', 'encino park', 'fair oaks', 'olmos park', 'redbird', 'westover', 'camp bullis']):
        if any(w in t for w in ['austin', 'bastrop']):
            return SCENES["neighborhood_austin"]
        if any(w in t for w in ['killeen', 'fort cavazos', 'bell county']):
            return SCENES["neighborhood_killeen"]
        return SCENES["neighborhood_sa"]
    if any(w in t for w in ['va', 'veterano', 'veteranos', 'préstamo va', 'warrior', 'militar', 'militares', 'jbsa', 'bah', 'pcs']):
        return SCENES["va_loan"]
    if any(w in t for w in ['vender', 'venta', 'vendedor', 'precio', 'listado', 'marketing']):
        return SCENES["home_selling"]
    if any(w in t for w in ['comprar', 'comprador', 'compradores', 'cierre', 'hipoteca', 'inspección', 'tasación', 'homestead']):
        return SCENES["home_buying"]
    if any(w in t for w in ['agente', 'inmobiliario', 'carrera', 'brokerage', 'comisiones']):
        return SCENES["spanish_career"]
    if any(w in t for w in ['pronóstico', 'mercado', 'tendencia', 'precio', 'datos']):
        return SCENES["market_data"]
    if any(w in t for w in ['austin']):
        return SCENES["neighborhood_austin"]
    if any(w in t for w in ['killeen', 'fort cavazos']):
        return SCENES["neighborhood_killeen"]
    if any(w in t for w in ['san antonio']):
        return SCENES["neighborhood_sa"]
    return SCENES["general_tips"]


def fetch_spanish_posts() -> list[dict]:
    """Fetch all published Spanish Blog posts via SSH/WP-CLI."""
    cmd = f'{SSH_CMD} "wp post list --post_type=post --post_status=publish --category_name=spanish-blog --fields=ID,post_title --format=json --number=300 2>/dev/null"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"ERROR fetching Spanish posts: {result.stderr[:200]}", file=sys.stderr)
        sys.exit(1)
    posts_data = json.loads(result.stdout)
    posts = []
    for p in posts_data:
        pid = int(p["ID"])
        title = p["post_title"]
        headline = clean_spanish_headline(title, pid)
        scene = detect_scene(title)
        posts.append({
            "id": pid,
            "title": title,
            "headline_short": headline if headline != title else None,
            "scene": scene,
        })
    return posts


# All 18 NO_IMG posts — newest first
# headline_short is used when title > 55 chars for thumbnail legibility
POSTS = [
    {"id": 5015, "title": "Homes for Sale in Austin, TX: Listings, Neighborhoods & Market Data (2026)",
     "headline_short": "Homes for Sale in Austin, TX",
     "scene": SCENES["listings_austin"]},
    {"id": 5014, "title": "Homes for Sale in San Antonio, TX: Listings, Neighborhoods & Market Data (2026)",
     "headline_short": "Homes for Sale in San Antonio, TX",
     "scene": SCENES["listings_sanantonio"]},
    {"id": 5013, "title": "Homes for Sale in Killeen, TX: Listings, Neighborhoods & Market Data (2026)",
     "headline_short": "Homes for Sale in Killeen, TX",
     "scene": SCENES["listings_killeen"]},
    {"id": 4943, "title": "Why LRG Is Built for Agents Who Want to Become Dangerous",
     "headline_short": None, "scene": SCENES["agent_office"], "skip": True},  # already generated
    {"id": 4940, "title": "Come for the Leads, Stay for the Ecosystem",
     "headline_short": None, "scene": SCENES["agent_leads"], "skip": True},  # already generated
    {"id": 4939, "title": "Memorial Day 2026: The Life They Paid For",
     "headline_short": None, "scene": SCENES["memorial"], "skip": True},  # already generated
    {"id": 4942, "title": "Why LRG Is Built for Agents Who Want to Become Dangerous",
     "headline_short": None, "scene": SCENES["agent_office"], "reuse": 4943},  # duplicate
    {"id": 4941, "title": "Come for the Leads, Stay for the Ecosystem",
     "headline_short": None, "scene": SCENES["agent_leads"], "reuse": 4940},  # duplicate
    {"id": 4938, "title": "The Difference Between Joining a Brokerage and Joining a Growth Machine",
     "headline_short": "Joining a Brokerage vs. a Growth Machine",
     "scene": SCENES["agent_growth"]},
    {"id": 4937, "title": "Build a Real Estate Book of Business in 2 Years, Not 12",
     "headline_short": None, "scene": SCENES["agent_coaching"]},
    {"id": 4936, "title": "Why Some Agents Grow Faster in Two Years Than Others Do in Ten",
     "headline_short": "Why Some Agents Grow Faster in Two Years Than Others in Ten",
     "scene": SCENES["agent_growth"]},
    {"id": 4935, "title": "Why Leads Alone Don't Build a Real Estate Career",
     "headline_short": None, "scene": SCENES["agent_field"]},
    {"id": 4934, "title": "Why Real-Time Answers Matter More Than Another Online Training Library",
     "headline_short": "Real-Time Answers Beat Another Training Library",
     "scene": SCENES["agent_coaching"]},
    {"id": 4933, "title": "How LRG Helps Agents Spend More Time in the Field and Less Time Fighting the Business",
     "headline_short": "More Time in the Field, Less Fighting the Business",
     "scene": SCENES["agent_field"]},
    {"id": 4932, "title": "Why Splits Don't Matter If You Don't Have Appointments, Coaching, and Conversion",
     "headline_short": "Splits Don't Matter Without Coaching & Conversion",
     "scene": SCENES["agent_environment"]},
    {"id": 4931, "title": "Why Environment Beats Motivation for Real Estate Agents",
     "headline_short": None, "scene": SCENES["agent_environment"]},
    {"id": 1522, "title": "San Antonio Home Price Trends in 2024",
     "headline_short": None, "scene": SCENES["market_sa"]},
    {"id": 4041, "title": "Por qué el sector inmobiliario es una elección de carrera prometedora (why RE..)",
     "headline_short": "Por Qué el Sector Inmobiliario Es Prometedor",
     "scene": SCENES["spanish_career"]},
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


def auto_qa(final_path, post):
    with open(final_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    headline = post.get("headline_short") or post["title"]

    qa_prompt = f"""You are a strict QA reviewer for branded blog featured images.

The image should be a professional real estate marketing graphic for the blog post titled: "{post['title']}"
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

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    qa_text = result["choices"][0]["message"]["content"]
    qa_path = OUTPUT_DIR / f"post-{post['id']}-qa.txt"
    qa_path.write_text(qa_text)
    return qa_text


def main():
    # --- Mode selection ---
    spanish_mode = "--spanish" in sys.argv
    test_post_id = None
    for arg in sys.argv:
        if arg.startswith("--test-post="):
            test_post_id = int(arg.split("=")[1])

    if spanish_mode or test_post_id:
        all_spanish = fetch_spanish_posts()
        if test_post_id:
            batch = [p for p in all_spanish if p["id"] == test_post_id]
            if not batch:
                print(f"ERROR: post {test_post_id} not found in Spanish Blog category")
                sys.exit(1)
            label = f"Spanish Test — Post {test_post_id}"
        else:
            batch = all_spanish
            label = f"Spanish Batch — {len(batch)} posts"
    else:
        batch = POSTS
        label = "Full Batch (18 posts)"

    print("=" * 60)
    print(f"LRG Featured Image Pipeline — {label}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    results = []
    gen_count = 0

    for i, post in enumerate(batch):
        pid = post["id"]
        print(f"\n[{i+1}/{len(batch)}] Post {pid}: {post['title'][:55]}...")

        final_path = OUTPUT_DIR / f"post-{pid}-final.jpg"

        # Skip already-generated test images
        if post.get("skip"):
            if final_path.exists():
                print(f"  SKIP (already generated in test run)")
                qa_path = OUTPUT_DIR / f"post-{pid}-qa.txt"
                qa_text = qa_path.read_text() if qa_path.exists() else "VERDICT: PASS\n(from test run)"
                verdict = "PASS" if "VERDICT: PASS" in qa_text else "FAIL"
                results.append({"post_id": pid, "title": post["title"],
                                "headline_used": post.get("headline_short") or post["title"],
                                "verdict": verdict, "final": str(final_path), "qa": qa_text,
                                "source": "test_run"})
                continue

        # Reuse image from duplicate post
        if post.get("reuse"):
            source_path = OUTPUT_DIR / f"post-{post['reuse']}-final.jpg"
            if source_path.exists():
                import shutil
                shutil.copy2(source_path, final_path)
                print(f"  REUSE from post {post['reuse']}")
                # Still run QA on the copy
                qa_text = auto_qa(final_path, post)
                verdict = "PASS" if "VERDICT: PASS" in qa_text else "FAIL"
                results.append({"post_id": pid, "title": post["title"],
                                "headline_used": post.get("headline_short") or post["title"],
                                "verdict": verdict, "final": str(final_path), "qa": qa_text,
                                "source": f"reuse_{post['reuse']}"})
                continue

        # Generate new image
        try:
            raw_path, elapsed = generate_image(post)
            gen_count += 1
            print(f"  Generated in {elapsed:.0f}s ({gen_count} generated so far)")

            final_path = composite_logo(raw_path, pid)
            print(f"  Logo composited")

            qa_text = auto_qa(final_path, post)
            verdict = "PASS" if "VERDICT: PASS" in qa_text else "FAIL"
            thumb_ok = "THUMBNAIL_READABLE: YES" in qa_text
            print(f"  QA: {verdict} | Thumbnail readable: {'YES' if thumb_ok else 'FLAGGED'}")

            results.append({"post_id": pid, "title": post["title"],
                            "headline_used": post.get("headline_short") or post["title"],
                            "verdict": verdict, "final": str(final_path), "qa": qa_text,
                            "source": "generated"})

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"post_id": pid, "title": post["title"],
                            "headline_used": post.get("headline_short") or post["title"],
                            "verdict": "ERROR", "final": "", "qa": str(e),
                            "source": "error"})

        # Pause between API calls
        if i < len(POSTS) - 1 and not POSTS[i+1].get("skip") and not POSTS[i+1].get("reuse"):
            time.sleep(3)

    # Write summary report
    print("\n" + "=" * 60)
    print("BATCH SUMMARY")
    print("=" * 60)

    passes = [r for r in results if r["verdict"] == "PASS"]
    fails = [r for r in results if r["verdict"] in ("FAIL", "ERROR")]

    report_lines = []
    report_lines.append("# LRG Featured Image Batch — Review Queue")
    report_lines.append(f"Generated: {gen_count} new | 3 from test | 2 reused")
    report_lines.append(f"PASS: {len(passes)} | FAIL/ERROR: {len(fails)}")
    report_lines.append("")

    if fails:
        report_lines.append("## FLAGGED (review required)")
        for r in fails:
            report_lines.append(f"- Post {r['post_id']}: {r['title']}")
            report_lines.append(f"  Verdict: {r['verdict']}")
            report_lines.append(f"  File: {r['final']}")
            report_lines.append(f"  QA: {r['qa'][:200]}")
            report_lines.append("")

    report_lines.append("## AUTO-PASS (spot-check recommended)")
    for r in passes:
        thumb_flag = ""
        if "THUMBNAIL_READABLE: NO" in r.get("qa", ""):
            thumb_flag = " [THUMBNAIL WARNING]"
        report_lines.append(f"- Post {r['post_id']}: {r['title']}{thumb_flag}")
        hl = r.get("headline_used", r["title"])
        if hl != r["title"]:
            report_lines.append(f"  Headline used: \"{hl}\"")
        report_lines.append(f"  File: {r['final']}")
        report_lines.append(f"  Source: {r['source']}")
        report_lines.append("")

    report_text = "\n".join(report_lines)
    report_path = OUTPUT_DIR / "batch-review-queue.md"
    report_path.write_text(report_text)

    print(report_text)
    print(f"\nReport saved: {report_path}")
    print(f"All images in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
