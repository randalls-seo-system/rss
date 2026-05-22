"""Priority scoring for topic candidates.

Implements the scoring formula from DESIGN.md:

    priority_score = (w_cc * competitor_coverage_norm)
                   + (w_vol * volume_norm)
                   + (w_iv * intent_value_norm)
                   + (w_ci * competition_inverse_norm)

With bonus modifiers:
- we_have_it = 1: multiply by 0.1 (deprioritize covered topics)
- we_have_it = 0 AND competitors_with_it >= 2: multiply by 1.25 (boost gaps)

Weights are configurable per site via [topic_discovery] config section.

Provides:
- score_topic(topic_row, weights): compute priority_score for one candidate
- score_all(db_conn, site_slug, weights): bulk-score all candidates for a site
- compute_competition_score(serp_results): estimate competition from SERP top 10
- INTENT_VALUES: dict mapping intent type to commercial value (0.0-1.0)
"""
