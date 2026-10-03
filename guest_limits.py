"""Capacity policy for guest collections, enforced by PostgreSQL storage.

The caller must supply *all* saved numbers, including archived problems.
PostgreSQL calls this inside the same locked transaction that saves problems.
A standalone check cannot protect against concurrent writes.
"""

from collections.abc import Collection

from storage_errors import StorageError


DEFAULT_GUEST_PROBLEM_LIMIT = 50


class ProblemLimitExceeded(StorageError):
    def __init__(self, limit: int):
        super().__init__(
            f"Guest workspaces can save up to {limit} problems. "
            "Create an account to keep your progress and add more, "
            "or delete a saved problem."
        )


def ensure_problem_capacity(
    existing_numbers: Collection[int],
    requested_numbers: Collection[int],
    limit: int | None,
) -> None:
    """Return normally if the entire request fits; otherwise raise the limit error.

    None means there is no guest cap (permanent account/local mode).
    Duplicate numbers and numbers already saved do not consume another slot.
    An existing collection over the cap is preserved: only new additions fail.
    """
    if limit is None:
        return

    existing = set(existing_numbers)
    new_numbers = set(requested_numbers) - existing

    if new_numbers and len(existing) + len(new_numbers) > limit:
        raise ProblemLimitExceeded(limit)
