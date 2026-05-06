# intro-optimization module

LLM-driven intro tightening for posts with bloated intros. Rewrites 4-paragraph throat-clearing into 50-70 word direct-answer intros with optional disclaimer callouts.

## When to run

After class migration (content-production module) completes. This is Phase 2 of the content rebuild pipeline.

## Pipeline

```
Step 1: extract-current-intros.py   → current-intros.csv
Step 2: generate-tightened-intros.py → proposed-intros.csv
Step 3: preview-intros.py           → preview.md (human review)
Step 4: [HUMAN APPROVAL]
Step 5: deploy-intros.sh            → WP post updates
```

## Cost estimate

- LLM: ~$0.001/page at gpt-4o-mini ($0.14 for 139 pages)
- Time: ~2 min extraction + ~3 min generation + review time

## Site config

Add new sites to `SITE_CONFIG` in extract-current-intros.py and `SITE_META` in generate-tightened-intros.py.

## Rollback

Each post is backed up before deployment to `~/lrg-rewrite/backups/intro-{post_id}-{timestamp}.html`. Restore via:

```bash
cat ~/lrg-rewrite/backups/intro-{ID}-{TS}.html | python3 -c "
import sys; h=sys.stdin.read().encode('utf-8').hex()
print(f\"UPDATE wp_posts SET post_content = UNHEX('{h}') WHERE ID={ID};\")" | \
ssh -i ~/.ssh/wpengine_valn -o IdentitiesOnly=yes SSH_HOST 'wp db query'
```

## Files

```
modules/intro-optimization/
├── README.md
├── lib/
│   ├── __init__.py
│   └── html_intro_replacer.py    # Surgical HTML intro replacement
├── prompts/
│   └── intro-tightening.md       # LLM prompt template
├── tools/
│   ├── extract-current-intros.py # Step 1: pull current intros
│   ├── generate-tightened-intros.py # Step 2: LLM rewrite
│   ├── preview-intros.py         # Step 3: side-by-side review
│   └── deploy-intros.sh          # Step 5: WP deployment
└── examples/
    └── lrg-intro-tightening-example.md
```
