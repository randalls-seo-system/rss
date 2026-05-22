"""Export the topic queue as CSV for a given site.

Reads from data/topics.db and writes topic-queue-{site}.csv to data/.
Can filter by status, minimum priority score, and minimum volume.

Usage:
    python3 dump_queue.py --site <slug> [--status new] [--min-score 0.5]
                          [--min-volume 100]

Flags:
    --site          Site slug (e.g., 'valn'). Required.
    --status        Filter by status (default: all).
    --min-score     Minimum priority_score to include (default: 0.0).
    --min-volume    Minimum est_volume to include (default: 100).
                    Set to 0 to include all candidates regardless of volume.

The full topics table always retains all candidates (no early filtering).
Volume filtering is applied only at this output stage.

Output columns: keyword, intent, est_volume, volume_source, competition_score,
competitors_with_it, we_have_it, priority_score, suggested_wc, status,
source, discovered_at.
"""
