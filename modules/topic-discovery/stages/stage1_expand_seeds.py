"""Stage 1: Seed Expansion.

Expands seed terms from site config into a broad candidate list using
Serper's related searches, People Also Ask, and autocomplete endpoints.

No LLM calls. Pure API + rule-based expansion.

Input: seed_terms from [topic_discovery] config section.
Output: Candidate keywords inserted into topics table with source='expansion'.
"""
