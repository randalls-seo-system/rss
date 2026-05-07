"""Per-provider rate limiter."""

import time


class RateLimiter:
    """Simple sleep-based rate limiter."""

    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
