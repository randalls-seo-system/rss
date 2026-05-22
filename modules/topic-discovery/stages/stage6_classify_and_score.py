"""Stage 6: Intent Classification + Priority Scoring.

Classifies each candidate's search intent using gpt-5.4-mini (batched,
20 keywords per prompt) and computes priority scores using the formula
defined in DESIGN.md.

This is the only stage that uses an LLM. Uses openai provider with
gpt-5.4-mini — NOT Opus (Opus is reserved for content generation).

Input: Candidates from topics table + cached SERP data from Stage 5.
Output: topics.intent, competition_score, priority_score, suggested_wc,
        suggested_archetype, last_scored_at updated.
"""
