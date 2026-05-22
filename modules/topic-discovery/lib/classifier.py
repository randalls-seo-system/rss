"""LLM-powered intent classification for topic candidates.

Uses openai provider with gpt-5.4-mini (mechanical task, not content
generation) via the existing LLMClient from content-production-v2.
Batches up to 20 keywords per prompt to minimize API calls.

Classifies each keyword into one of the 5 intent types defined in
article-spec.md Section 1: definition, process, decision, cost, comparison.

Provides:
- classify_batch(keywords): classify a list of keywords, return
  dict[keyword, intent]
- INTENT_TYPES: frozenset of valid intent strings
"""
