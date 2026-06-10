# VALN Active Project Status

Last updated: 2026-06-09

## High Priority
- **Addon tools (staging):** 28 rebuilt tools deployed (v1.4.0). Browser testing needed. 2 tools (manual-underwrite, self-employed-income) working, not redeployed.
- **Addon tools -> production:** Once staging is verified, deploy addon pack to production. Currently only valn-tools-new (12 tools) is on production.
- **Legacy page rewrites:** 6 P1 pages with 50+ clicks in legacy format. Queue at `~/valn-rewrite/legacy-rewrite-queue.csv`.
- **Stale data fixes**: Verify `1.0%` funding fee citation in ID 833. Editorial decision on 7 stale-titled news articles: IDs 7955, 7973, 8126, 8568, 11558, 18786, 13496.
- **Content integrity**: Investigate `[valn_open_network]` on post 30803. Investigate `[ez-toc]` on posts 17954, 18177, 18191.
- Restyle COE Eligibility Estimator on homepage (post ID 4) to match 4-step calculator style (post 15573).

## Medium Priority
- **Remaining orphan pages:** ~135 pages with <3 inbound links remain.
- **Title tag optimization:** 9 of top 20 pages flagged. Audit at `~/valn-rewrite/title-tag-audit-top20.csv`.
- **Meta description rewrite:** Post 931 (/va-loans/minimum-credit-score-needed-for-va-loans/) -- current desc is adequate but Google is ignoring it for on-page text. Candidate for stronger, more specific meta in next meta-rewrite batch.
- **Peripheral phase-out:** Plan at `~/valn-rewrite/peripheral-phase-out-plan.csv`.
- **Broken internal links -- P2:** Slug variation redirects needed (va-renovation-loan, va-irrrl, va-refinance, va-closing-costs, va-loan, va-loans/va-loan-funding-fee, va-loans/va-closing-costs).
- Sticky CTA bar on BAH and military pay pages.

## Queued Work
- Page rewrites -- 50 pages in `~/valn-rewrite/page-rewrite-queue-top50.csv`
- 30 partial-format pages need structural upgrades (legacy-rewrite-queue.csv)
- Content gap articles -- 12 seed terms with zero GSC presence
- Pizza site setup and 50 articles

## Second Site: The Lenders Network
- Domain: thelendersnetwork.com
- Separate CLAUDE-TLN.md and Google Doc to be set up when work begins
- **Do NOT apply any VA Loan Network changes to TLN**
