"""SQLite connection management, schema migrations, and query helpers.

Manages the topics.db database at modules/topic-discovery/data/topics.db.
Provides:
- connect(): returns a sqlite3.Connection with WAL mode and foreign keys
- ensure_schema(): creates tables and indexes if they don't exist
- insert_topic(): insert-or-update with dedup on (site_slug, keyword_normal)
- insert_competitor_page(): insert-or-ignore competitor page record
- insert_seed_term(): insert-or-ignore seed term record
- get_candidates(): query topics by site and status with optional filters
- update_scores(): bulk-update priority scores after Stage 6

Schema definitions are in DESIGN.md. This module is the single owner of
all DDL statements.
"""
