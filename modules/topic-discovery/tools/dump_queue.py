"""Export the topic queue as CSV for a given site.

Reads from data/topics.db and writes topic-queue-{site}.csv to data/.
Can filter by status and minimum priority score.

Usage:
    python3 dump_queue.py --site <slug> [--status new] [--min-score 0.5]

Output columns: keyword, intent, est_volume, competition_score,
competitors_with_it, we_have_it, priority_score, suggested_wc, status,
source, discovered_at.
"""
