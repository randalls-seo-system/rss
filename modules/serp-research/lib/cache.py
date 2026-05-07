"""Disk-based SERP response cache with TTL."""

import hashlib
import json
import os
import re
import time


class SerpCache:
    """Cache SERP responses to disk. 7-day default TTL."""

    def __init__(self, cache_dir: str, ttl_days: int = 7):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_days * 86400
        os.makedirs(cache_dir, exist_ok=True)

    def _key(self, provider: str, keyword: str, location: str, device: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower())[:80]
        params_hash = hashlib.md5(
            f"{provider}|{keyword}|{location}|{device}".encode()
        ).hexdigest()[:8]
        return f"{slug}-{params_hash}.json"

    def get(self, provider: str, keyword: str, location: str, device: str) -> dict | None:
        path = os.path.join(self.cache_dir, self._key(provider, keyword, location, device))
        if not os.path.exists(path):
            return None
        if time.time() - os.path.getmtime(path) > self.ttl_seconds:
            return None
        with open(path) as f:
            return json.load(f)

    def set(self, provider: str, keyword: str, location: str, device: str, response: dict):
        path = os.path.join(self.cache_dir, self._key(provider, keyword, location, device))
        with open(path, "w") as f:
            json.dump(response, f)
