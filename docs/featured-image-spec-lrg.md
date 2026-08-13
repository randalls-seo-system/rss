# LRG Featured Image Spec

## Canonical Generator
`modules/content-production-v2/tools/generate-featured-image.py`

The batch scripts in `featured-images/lrg-batch-generate.py` (and batch2, batch3)
are historical runs that use the same spec. The pipeline's Phase J calls
`generate-featured-image.py` directly.

## Image Spec

| Parameter | Value |
|-----------|-------|
| Model | gpt-image-2 |
| Dimensions | 1536 x 1024 (landscape) |
| Quality | high |
| Output format | JPEG, quality=92 |
| Raw intermediate | PNG ({post_id}-raw.png) |
| Final output | JPEG ({post_id}-final.jpg) |

## Visual Treatment

### Layout
- Left ~40%: deep navy (#0A1628) gradient overlay, fading into the scene
- Right ~60%: photorealistic scene photograph
- The gradient blends into the photograph (not a hard edge)

### Text (rendered by gpt-image-2, not composited)
- **Headline:** Large, bold, clean white sans-serif font (Montserrat or Helvetica Bold style)
- **Placement:** Upper-left area, left-aligned, generous line breaks
- **Style:** 2-4 words per line, title case, short phrasing
- **Domain watermark:** "LRGREALTY.COM" in smaller muted gray text below headline

### Logo (composited by Pillow after generation)
- File: `/tmp/lrg-logo-real.png`
- Width: 220px (scaled proportionally)
- Position: top-left corner (24px from left, 20px from top)
- Backing: semi-transparent dark navy rounded rectangle (10, 22, 40, alpha 160)
- Padding: 12px around logo

## Scene Selection

Scenes are selected by keyword pattern matching in `SCENE_PATTERNS` or via
`--scene-hint` override. For the short-sale vertical:

| Article Topic | Scene |
|--------------|-------|
| Negative equity / underwater | Suburban Texas home with FOR SALE sign, slightly worn exterior, overcast or late-afternoon light, no people |
| Foreclosure timeline | Texas county courthouse or residential street with notice posted, serious tone, warm but subdued light |
| Deficiency judgments | Texas courthouse or legal office setting, document-focused, professional serious tone |
| Short sale process | Texas home exterior with real estate agent reviewing documents on porch, professional, neutral light |
| Walk away from mortgage | Empty suburban home, vacancy signs, overgrown lawn, dusk light, somber but not depressing |
| Behind on payments | Texas home mailbox with envelopes, residential street, worried tone without being alarming |
| PCS / military | Military base housing area with moving truck, Texas suburban, warm light |
| Austin underwater | Austin skyline or suburbs with subtle distress cues (price reduction sign), golden hour |
| Tax on forgiven debt | IRS form 1099-C on desk, Texas home visible through window, office setting |

## Headline Text Style

Match the Phase 1 cards:
- 9765: "Your Options When You Can't Afford to Sell"
- 9773: "PCS With an Underwater Mortgage in Texas"
- 9774: "Short Sale vs Foreclosure in Texas"

Pattern: short, direct, title case, 2-4 words per line at the font size used.
Not the full article title. A shortened version that fits the left 40%.

## Upload and Attachment

Via `push-featured-image.py` or `generate-featured-image.py --upload`:
1. Pipe image to remote persistent path (`/nas/content/live/{install}/_staging-inbox/`)
2. PHP: `wp_upload_bits()` to create attachment in media library
3. PHP: `set_post_thumbnail()` to attach as featured image
4. Alt text: article headline
