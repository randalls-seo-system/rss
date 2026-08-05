"""Article generation queue — per-site, file-backed, atomic writes.

Queue file: sites/<slug>/queue.json
Items: {id, topic, target_keyword, intent_hint, status, added, attempts, last_failure, job_id}
Status: pending | in_progress | done | parked

All writes use temp-file + rename for atomicity — the loop and a human
may both touch the queue concurrently.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _queue_path(site_slug: str) -> Path:
    return REPO_ROOT / "sites" / site_slug / "queue.json"


def load_queue(site_slug: str) -> list[dict]:
    path = _queue_path(site_slug)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_queue(site_slug: str, items: list[dict]) -> None:
    """Atomic write: temp file in same dir + rename."""
    path = _queue_path(site_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(items, f, indent=2)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_item(site_slug: str, topic: str, keyword: str = "",
             intent_hint: str = "") -> dict:
    items = load_queue(site_slug)
    item = {
        "id": uuid.uuid4().hex[:12],
        "topic": topic,
        "target_keyword": keyword or topic,
        "intent_hint": intent_hint,
        "status": "pending",
        "added": datetime.now(timezone.utc).isoformat(),
        "attempts": 0,
        "last_failure": "",
        "job_id": "",
    }
    items.append(item)
    save_queue(site_slug, items)
    return item


def list_items(site_slug: str, status: str | None = None) -> list[dict]:
    items = load_queue(site_slug)
    if status:
        items = [i for i in items if i["status"] == status]
    return items


def pop_next(site_slug: str) -> dict | None:
    """Atomically pop the next pending item → in_progress. Returns None if empty."""
    items = load_queue(site_slug)
    for item in items:
        if item["status"] == "pending":
            item["status"] = "in_progress"
            item["attempts"] = item.get("attempts", 0) + 1
            save_queue(site_slug, items)
            return item
    return None


def mark_done(site_slug: str, item_id: str, job_id: str = "") -> None:
    items = load_queue(site_slug)
    for item in items:
        if item["id"] == item_id:
            item["status"] = "done"
            if job_id:
                item["job_id"] = job_id
            break
    save_queue(site_slug, items)


def park_item(site_slug: str, item_id: str, failure_reason: str = "") -> None:
    items = load_queue(site_slug)
    for item in items:
        if item["id"] == item_id:
            item["status"] = "parked"
            if failure_reason:
                item["last_failure"] = failure_reason
            break
    save_queue(site_slug, items)


def retry_item(site_slug: str, item_id: str) -> None:
    items = load_queue(site_slug)
    for item in items:
        if item["id"] == item_id:
            item["status"] = "pending"
            break
    save_queue(site_slug, items)


def seed_from_gsc(site_slug: str, min_impressions: int = 50,
                  limit: int = 30) -> list[dict]:
    """Pull article-worthy queries from GSC for this site.

    Returns candidates (not yet written to queue) for human review.
    """
    import sys
    sys.path.insert(0, str(REPO_ROOT))

    config_path = REPO_ROOT / "sites" / site_slug / "config.json"
    if not config_path.exists():
        return []
    config = json.loads(config_path.read_text())
    gsc_property = config.get("integrations", {}).get("gsc_property", "")
    if not gsc_property:
        print(f"No GSC property configured for {site_slug}", file=sys.stderr)
        return []

    # Load GSC credentials
    creds_path = REPO_ROOT / ".gsc-credentials.json"
    if not creds_path.exists():
        print("GSC credentials not found", file=sys.stderr)
        return []

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)

        # Query last 90 days
        from datetime import timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        response = service.searchanalytics().query(
            siteUrl=gsc_property,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": 1000,
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "query",
                        "operator": "notContains",
                        "expression": config.get("identity", {}).get("name", "").split()[0].lower(),
                    }]
                }],
            },
        ).execute()

        rows = response.get("rows", [])
    except Exception as e:
        print(f"GSC query failed: {e}", file=sys.stderr)
        return []

    # Filter to article-worthy informational queries
    existing_queue = load_queue(site_slug)
    existing_keywords = {i["target_keyword"].lower() for i in existing_queue}

    # Informational signal words
    info_words = {"how", "what", "why", "when", "can", "does", "is", "are",
                  "should", "guide", "best", "tips", "vs", "versus",
                  "requirements", "process", "cost", "rates", "explained"}

    candidates = []
    seen_normalized = set()
    for row in rows:
        query = row["keys"][0]
        impressions = row.get("impressions", 0)
        if impressions < min_impressions:
            continue

        q_lower = query.lower().strip()
        # Skip branded queries
        site_name = config.get("identity", {}).get("name", "").lower()
        if any(brand_word in q_lower for brand_word in site_name.split() if len(brand_word) > 3):
            continue

        # Informational filter: at least one info word
        q_words = set(q_lower.split())
        if not q_words & info_words:
            continue

        # Dedup: skip if already in queue or near-identical
        if q_lower in existing_keywords:
            continue
        # Normalize for near-dedup
        norm = " ".join(sorted(q_lower.split()))
        if norm in seen_normalized:
            continue
        seen_normalized.add(norm)

        candidates.append({
            "query": query,
            "impressions": int(impressions),
            "clicks": int(row.get("clicks", 0)),
            "position": round(row.get("position", 0), 1),
        })

    # Sort by impressions descending
    candidates.sort(key=lambda x: x["impressions"], reverse=True)
    return candidates[:limit]
