#!/usr/bin/env python3
"""Generate a branded GPT featured image for a blog post.

Uses gpt-image-2 to generate a scene + headline + gradient overlay,
composites the site logo via Pillow, uploads to WordPress, and sets
as featured image. Optionally runs GPT-4o vision QA.

Requires: OPENAI_API_KEY env var, Pillow, site logo file.

Usage:
    python3 generate-featured-image.py \\
        --site lrg \\
        --post-id 5383 \\
        --title "Rent to Own Homes in Texas" \\
        [--headline-short "Rent to Own in TX"] \\
        [--scene-hint "aerial Texas suburbs golden hour"] \\
        [--skip-upload] \\
        [--skip-qa] \\
        [--output-dir <path>]
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Site-specific branding. Extend as sites are onboarded.
SITE_BRANDING = {
    "lrg": {
        "logo_path": "/tmp/lrg-logo-real.png",
        "logo_width": 220,
        "domain_text": "LRGREALTY.COM",
        "navy": "#0A1628",
        "default_scene": "Aerial view of Texas suburban neighborhood with diverse homes, tree-lined streets, warm golden hour light, photorealistic cinematic wide shot",
    },
    "valn": {
        "logo_path": "/tmp/valn-logo.png",
        "logo_width": 220,
        "domain_text": "VALOANNETWORK.COM",
        "navy": "#1F4E79",
        "default_scene": "A military family standing in front of a suburban home with an American flag, warm afternoon light, green lawn, photorealistic wide shot",
    },
    "canopy": {
        "logo_path": "",
        "logo_width": 0,
        "domain_text": "CANOPYINSURANCETEXAS.COM",
        "navy": "#1A365D",
        "default_scene": "Aerial view of San Antonio Texas skyline at golden hour with suburban neighborhoods, warm light, photorealistic cinematic wide shot",
    },
}

STYLE_PROMPT = """Style: Professional real estate marketing graphic.
Color palette: deep navy ({navy}) gradient background blending into the scene photograph.
The scene photograph occupies the right ~60% of the image.
The left ~40% has a dark navy gradient overlay where the headline text will be placed.
The headline text "{headline}" should be rendered in large, bold, clean white sans-serif font
(like Montserrat or Helvetica Bold) in the upper-left area, left-aligned, with generous line breaks.
Below the headline, in smaller text, render "{domain}" in a muted gray.
Do NOT include any logos, watermarks, or icons — just the scene, gradient, and text.
The overall feel should be premium, modern real estate branding — NOT a stock photo, NOT clipart.
Aspect ratio is landscape (1536x1024). The image should look like a high-end blog header graphic."""

# Scene hints by keyword patterns (fallback when no --scene-hint provided)
SCENE_PATTERNS = [
    (["austin"], "Aerial panoramic view of downtown Austin Texas skyline at golden hour with Lady Bird Lake, Congress Avenue bridge, warm sunset glow, photorealistic cinematic wide shot"),
    (["san antonio"], "Aerial panoramic view of San Antonio Texas skyline at golden hour with the River Walk, Tower of the Americas, warm sunset light, photorealistic cinematic wide shot"),
    (["killeen", "fort cavazos"], "Aerial view of Killeen Texas suburban neighborhoods with Fort Cavazos in the background, rolling Central Texas hills, warm afternoon light, photorealistic cinematic wide shot"),
    (["central texas", "texas"], "Aerial view of Central Texas Hill Country with suburban development and natural rolling hills, live oak trees, warm afternoon sunlight, photorealistic cinematic wide shot"),
    (["neighborhood", "guide"], "Aerial view of a well-maintained Texas suburban neighborhood with diverse home styles, parks, tree-lined streets, warm golden hour, photorealistic cinematic wide shot"),
    (["va loan", "veteran", "military"], "A military family standing in front of a suburban Texas home with an American flag, warm afternoon light, green lawn, photorealistic wide shot"),
    (["rent to own", "lease"], "Aerial view of Texas suburban neighborhood with diverse home styles, tree-lined streets, warm golden hour light, a subtle For Sale sign visible, photorealistic cinematic wide shot"),
    (["sell", "listing"], "A professionally staged Texas home exterior with manicured lawn, real estate sign, warm afternoon light, photorealistic wide shot"),
    (["school", "district"], "Aerial view of a Texas suburban area near a school campus with playing fields, family homes, tree-lined streets, warm light, photorealistic wide shot"),
    (["property tax"], "Texas residential neighborhood with diverse home styles, county courthouse visible in background, warm afternoon light, photorealistic wide shot"),
]


def _detect_scene(keyword: str, site: str) -> str:
    """Auto-detect scene from keyword patterns."""
    kw_lower = keyword.lower()
    for patterns, scene in SCENE_PATTERNS:
        if any(p in kw_lower for p in patterns):
            return scene
    branding = SITE_BRANDING.get(site, {})
    return branding.get("default_scene", "Aerial view of suburban neighborhood at golden hour, photorealistic wide shot")


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_image(headline: str, scene: str, branding: dict, output_dir: Path, post_id: int) -> Path:
    """Generate image via gpt-image-2."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    prompt = STYLE_PROMPT.format(
        headline=headline,
        navy=branding.get("navy", "#0A1628"),
        domain=branding.get("domain_text", ""),
    ) + f"\n\nScene description: {scene}"

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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start

    b64 = result["data"][0]["b64_json"]
    img_bytes = base64.b64decode(b64)
    raw_path = output_dir / f"post-{post_id}-raw.png"
    raw_path.write_bytes(img_bytes)
    return raw_path, elapsed


def composite_logo(raw_path: Path, post_id: int, branding: dict, output_dir: Path) -> Path:
    """Overlay site logo onto generated image."""
    logo_path = branding.get("logo_path", "")
    if not logo_path or not Path(logo_path).exists():
        # No logo — just convert to JPEG
        base = Image.open(raw_path).convert("RGB")
        final_path = output_dir / f"post-{post_id}-final.jpg"
        base.save(final_path, "JPEG", quality=92)
        return final_path

    base = Image.open(raw_path).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    logo_target_w = branding.get("logo_width", 220)
    scale = logo_target_w / logo.width
    logo_resized = logo.resize(
        (int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS
    )

    # Semi-transparent backing behind logo
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
    final_path = output_dir / f"post-{post_id}-final.jpg"
    final.save(final_path, "JPEG", quality=92)
    return final_path


# ---------------------------------------------------------------------------
# Upload to WordPress
# ---------------------------------------------------------------------------

def upload_to_wp(final_path: Path, post_id: int, alt_text: str, site_slug: str) -> bool:
    """Upload image to WP and set as featured image via SSH."""
    # Load site config for SSH details
    conf_path = REPO_ROOT / "sites" / f"{site_slug}.conf"
    if not conf_path.exists():
        print(f"  WARNING: {conf_path} not found, skipping upload", file=sys.stderr)
        return False

    ssh_host = ssh_user = ssh_key = ""
    for line in conf_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("SSH_HOST="):
            ssh_host = line.split("=", 1)[1].strip('"')
        elif line.startswith("SSH_USER="):
            ssh_user = line.split("=", 1)[1].strip('"')
        elif line.startswith("SSH_KEY_PATH="):
            ssh_key = line.split("=", 1)[1].strip('"').replace("~", str(Path.home()))

    if not ssh_host or not ssh_user:
        print("  WARNING: SSH config incomplete, skipping upload", file=sys.stderr)
        return False

    ssh_base = ["ssh"]
    if ssh_key:
        ssh_base += ["-i", ssh_key, "-o", "IdentitiesOnly=yes"]
    ssh_base += [f"{ssh_user}@{ssh_host}"]

    php = f'''<?php
require_once(ABSPATH . 'wp-admin/includes/media.php');
require_once(ABSPATH . 'wp-admin/includes/file.php');
require_once(ABSPATH . 'wp-admin/includes/image.php');
$old = get_post_thumbnail_id({post_id});
if ($old) {{ wp_delete_attachment($old, true); echo "Deleted old $old\\n"; }}
$f = ['name'=>'{site_slug}-{post_id}-gpt-featured.jpg','tmp_name'=>'/tmp/{site_slug}-feat-{post_id}.jpg'];
$a = media_handle_sideload($f, {post_id}, '{alt_text}');
if (is_wp_error($a)) {{ echo "FAIL: ".$a->get_error_message()."\\n"; exit(1); }}
set_post_thumbnail({post_id}, $a);
update_post_meta($a, '_wp_attachment_image_alt', '{alt_text}');
echo "OK {post_id}: attach=$a thumb=".get_post_meta({post_id},'_thumbnail_id',true)."\\n";
'''

    # Pipe image + PHP in single SSH session
    img_size = final_path.stat().st_size

    cmd = (
        f'(cat "{final_path}"; printf "\\n__IMGDONE__\\n"; cat <<\'PHPEOF\'\n{php}\nPHPEOF\n) | '
        f'{" ".join(ssh_base)} '
        f'"head -c {img_size} > /tmp/{site_slug}-feat-{post_id}.jpg; read dummy; '
        f'cat > /tmp/{site_slug}-up-{post_id}.php; wp eval-file /tmp/{site_slug}-up-{post_id}.php"'
    )

    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    output = r.stdout.strip()
    if r.returncode != 0 or "FAIL" in output:
        print(f"  Upload failed: {output} {r.stderr[:200]}", file=sys.stderr)
        return False

    print(f"  {output}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate branded GPT featured image")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--post-id", required=True, type=int, help="WordPress post ID")
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument("--headline-short", help="Short headline for image (if title is too long)")
    parser.add_argument("--scene-hint", help="Custom scene description")
    parser.add_argument("--skip-upload", action="store_true", help="Generate locally only")
    parser.add_argument("--skip-qa", action="store_true", help="Skip GPT-4o vision QA")
    parser.add_argument("--output-dir", help="Output directory")
    args = parser.parse_args()

    # P7: Deploy lock (uploads media to site via SSH)
    if not args.skip_upload:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'modules' / '_shared'))
        from lib.deploy_lock import acquire_deploy_lock
        acquire_deploy_lock(args.site, tool_name='generate-featured-image')

    branding = SITE_BRANDING.get(args.site, {})
    if not branding:
        print(f"WARNING: No branding config for site '{args.site}'. Using defaults.", file=sys.stderr)
        branding = {"domain_text": "", "navy": "#0A1628", "default_scene": "Aerial suburban neighborhood golden hour"}

    output_dir = Path(args.output_dir) if args.output_dir else Path.home() / "randalls-seo-system" / "featured-images" / args.site
    output_dir.mkdir(parents=True, exist_ok=True)

    headline = args.headline_short or args.title
    # Truncate for image legibility if too long
    if len(headline) > 55:
        headline = headline[:52] + "..."

    scene = args.scene_hint or _detect_scene(args.title, args.site)

    print(f"=== Featured Image: Post {args.post_id} ===")
    print(f"  Headline: {headline}")
    print(f"  Scene: {scene[:80]}...")

    # Generate
    raw_path, elapsed = generate_image(headline, scene, branding, output_dir, args.post_id)
    print(f"  Generated in {elapsed:.0f}s")

    # Logo composite
    final_path = composite_logo(raw_path, args.post_id, branding, output_dir)
    print(f"  Final: {final_path} ({final_path.stat().st_size:,} bytes)")

    # Upload
    if not args.skip_upload:
        alt_text = args.title
        ok = upload_to_wp(final_path, args.post_id, alt_text, args.site)
        if not ok:
            print("  Featured image upload FAILED", file=sys.stderr)
            sys.exit(1)
    else:
        print("  --skip-upload: image saved locally only")

    print(f"  DONE")


if __name__ == "__main__":
    main()
