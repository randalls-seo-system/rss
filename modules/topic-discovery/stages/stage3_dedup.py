"""Stage 3: Candidate Dedup + Canonicalization.

Merges duplicate candidates via keyword_normal, removes candidates matching
the excluded_keywords list, and enforces max_candidates_per_run cap.

No LLM calls. Pure SQL/Python rule-based filtering.

Input: Raw candidates in topics table.
Output: Deduped, filtered candidate set in topics table.
"""
