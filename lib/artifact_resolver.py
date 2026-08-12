"""Deploy artifact resolver — single path to the certified artifact.

Every code path that reads a deploy artifact must call
resolve_deploy_artifact(). No candidate lists, no globs, no fallbacks.

Code paths that need a valid post_id but not the file itself call
validate_post_id().

Gate incident: job 20260805-201409-d9dd5002 had post_id: null.
job.get("post_id", 0) returned None (key exists with null value,
default never fires). cli_review fell through to a glob and reviewed
the pre-postprocessor assembly instead of the certified artifact.
"""

from pathlib import Path
from typing import NamedTuple


class ArtifactResolutionError(Exception):
    """Raised when the deploy artifact cannot be resolved."""


class ResolvedArtifact(NamedTuple):
    post_id: int
    path: Path


def validate_post_id(job_record: dict) -> int:
    """Validate and return the post_id from a job record as an integer.

    Raises ArtifactResolutionError if post_id is missing, None, empty,
    bool, float, negative, zero, or not convertible to int.
    No default, ever.
    """
    job_id = job_record.get("id", "(unknown)")
    post_id = job_record.get("post_id")

    if post_id is None:
        raise ArtifactResolutionError(
            f"post_id is null in job {job_id}. Expected an integer post ID."
        )

    # bool is a subclass of int in Python — reject explicitly
    if isinstance(post_id, bool):
        raise ArtifactResolutionError(
            f"post_id is boolean ({post_id!r}) in job {job_id}. "
            f"Expected an integer post ID."
        )

    # float silently truncates (int(3.7) -> 3) — reject
    if isinstance(post_id, float):
        raise ArtifactResolutionError(
            f"post_id is float ({post_id!r}) in job {job_id}. "
            f"Expected an integer post ID."
        )

    if isinstance(post_id, str):
        post_id = post_id.strip()
        if not post_id:
            raise ArtifactResolutionError(
                f"post_id is empty string in job {job_id}."
            )
        # Only accept strings of digits (no floats-as-strings, no negatives-as-strings)
        if not post_id.isdigit():
            raise ArtifactResolutionError(
                f"post_id={post_id!r} is not a valid positive integer in job {job_id}."
            )
        result = int(post_id)
    elif isinstance(post_id, int):
        result = post_id
    else:
        raise ArtifactResolutionError(
            f"post_id={post_id!r} (type {type(post_id).__name__}) is not a valid "
            f"integer in job {job_id}."
        )

    if result <= 0:
        raise ArtifactResolutionError(
            f"post_id={result} is not positive in job {job_id}. "
            f"A real post ID is a positive integer."
        )

    return result


def resolve_deploy_artifact(job_record: dict, job_dir: Path) -> ResolvedArtifact:
    """Resolve the certified deploy artifact for a pipeline job.

    Returns ResolvedArtifact(post_id, path) where path is {post_id}-deploy.html.

    Raises ArtifactResolutionError if:
    - post_id is missing, None, empty, or not a valid positive integer
    - The deploy artifact does not exist at the expected path
    """
    post_id_int = validate_post_id(job_record)

    expected = job_dir / f"{post_id_int}-deploy.html"
    if not expected.exists():
        raise ArtifactResolutionError(
            f"Deploy artifact not found: {expected.name} in {job_dir}. "
            f"Job: {job_record.get('id', '(unknown)')}."
        )

    return ResolvedArtifact(post_id_int, expected)
