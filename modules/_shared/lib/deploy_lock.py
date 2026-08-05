"""P7: Centralized deploy lock — one implementation, called by every write tool.

Ensures no two write sessions collide on the same site install.
Lock file: ~/locks/{tool}-{site}.lock with PID + timestamp.

Rules:
    - Lock exists + PID alive → BLOCK (exit 78)
    - Lock exists + PID dead  → WARN, remove stale, proceed
    - No lock                 → acquire, register atexit cleanup

Usage:
    from lib.deploy_lock import acquire_deploy_lock

    # At tool entry point (before any writes)
    acquire_deploy_lock(site_slug='lrg', tool_name='push-post-content')

    # Lock auto-releases on exit (normal or error) via atexit.

Used by:
    - tools/push-post-content.py
    - tools/assemble-article.py
    - tools/inject-internal-links.py (when writing back)
    - Any future tool that writes to a site
"""

import atexit
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


LOCK_DIR = Path.home() / 'locks'

# Module-level tracking of active lock for cleanup
_active_lock: Path | None = None


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def acquire_deploy_lock(site_slug: str, tool_name: str) -> None:
    """Acquire a PID lockfile. Abort exit 78 if another live process holds it.

    Args:
        site_slug: Site identifier (e.g., 'lrg', 'valn', 'ahn').
        tool_name: Name of the calling tool (e.g., 'push-post-content').
    """
    global _active_lock
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f'{tool_name}-{site_slug}.lock'

    if lock_path.exists():
        try:
            content = lock_path.read_text().strip()
            parts = content.split(maxsplit=1)
            pid = int(parts[0])
            os.kill(pid, 0)  # signal 0 = check if process is alive
            # Process IS alive — block
            _eprint(f'DEPLOY LOCK BLOCKED: {tool_name} on {site_slug}')
            _eprint(f'  Lock: {lock_path}')
            _eprint(f'  Holder PID: {pid} (alive)')
            _eprint(f'  Lock content: {content}')
            _eprint('If this is stale, delete the lock file manually and retry.')
            sys.exit(78)
        except ProcessLookupError:
            # PID is dead — stale lock
            _eprint(f'WARNING: Stale lock for {tool_name}-{site_slug} (PID {parts[0]} dead). Removing.')
            lock_path.unlink()
        except (ValueError, IndexError):
            _eprint(f'WARNING: Corrupt lock {lock_path}. Removing.')
            lock_path.unlink()

    # Write our lock
    lock_content = (
        f'{os.getpid()} '
        f'{datetime.now(timezone.utc).isoformat()} '
        f'{tool_name} --site {site_slug}'
    )
    lock_path.write_text(lock_content)
    _active_lock = lock_path
    atexit.register(_release_deploy_lock)
    _eprint(f'  Deploy lock acquired: {lock_path}')


def _release_deploy_lock() -> None:
    """Release the deploy lock on exit. Only removes if we still own it."""
    global _active_lock
    if _active_lock and _active_lock.exists():
        try:
            content = _active_lock.read_text().strip()
            if content.startswith(str(os.getpid())):
                _active_lock.unlink()
        except OSError:
            pass
        _active_lock = None
