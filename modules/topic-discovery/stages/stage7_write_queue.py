"""Stage 7: Write Queue + Dump CSV Report.

Finalizes database state and exports a human-readable CSV report sorted
by priority_score descending. Prints a summary to stdout.

No LLM calls. Pure DB read + CSV write.

Input: Scored topics table.
Output: topic-queue-{site}.csv in data/ directory + stdout summary.
"""
