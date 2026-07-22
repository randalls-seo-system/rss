"""Featured image rotation from a branded photo pool.

Selects a WP attachment ID via topic-keyword matching or round-robin,
persisting rotation state to a JSON file so consecutive pipeline runs
cycle through the pool.
"""

import json
import os
import time
from pathlib import Path


def load_rotation_state(state_file_path: str) -> dict:
    """Load {image_id_str: last_used_timestamp} from state file.

    Returns empty dict if file doesn't exist or is corrupt.
    """
    path = Path(os.path.expanduser(state_file_path))
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_rotation_state(state_file_path: str, state: dict) -> None:
    """Persist rotation state to JSON file."""
    path = Path(os.path.expanduser(state_file_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def select_featured_image(target_keyword: str, site_structure: dict) -> int:
    """Pick a featured image ID from the pool.

    1. If topic_match has a keyword substring match, use that image.
    2. Otherwise, pick the pool image with the oldest last_used timestamp.
    3. Update state file with new timestamp.
    4. On any error, fall back to the first image in the pool.
    """
    fi_config = site_structure.get("featured_image", {})
    pool = fi_config.get("pool", [])
    if not pool:
        raise ValueError("featured_image.pool is empty in site structure")

    state_file = fi_config.get("state_file", "/tmp/featured-image-rotation.json")
    topic_match = fi_config.get("topic_match", {})
    state = load_rotation_state(state_file)

    kw_lower = target_keyword.lower()
    selected = None

    # Step 1: topic-keyword matching
    for topic_key, image_id in topic_match.items():
        if topic_key.lower() in kw_lower and image_id in pool:
            selected = image_id
            break

    # Step 2: round-robin — pick the image with the oldest timestamp
    if selected is None:
        oldest_time = float("inf")
        for img_id in pool:
            last_used = state.get(str(img_id), 0)
            if last_used < oldest_time:
                oldest_time = last_used
                selected = img_id

    # Fallback safety
    if selected is None:
        selected = pool[0]

    # Step 3: update state
    state[str(selected)] = int(time.time())
    try:
        save_rotation_state(state_file, state)
    except OSError:
        pass  # non-fatal — rotation state loss means slight repeat risk

    return selected
