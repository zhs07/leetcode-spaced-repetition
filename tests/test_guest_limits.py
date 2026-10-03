"""First guest-limit exercise: pure policy tests, without any database writes."""

import pytest

from guest_limits import DEFAULT_GUEST_PROBLEM_LIMIT, ProblemLimitExceeded, ensure_problem_capacity


@pytest.mark.parametrize("existing, requested, limit", [
    ([], [1], 50),
    (list(range(1, 50)), [50], 50),  # Exactly at the cap is allowed.
    ([1, 2], [2, 3, 3], 3),  # Existing and repeated CSV numbers use no extra slots.
    ([1, 1, 2], [3, 3], 3),  # Both inputs count distinct numbers only.
    ([1, 2, 3], [1, 2, 3, 3], 3),  # Re-importing at the cap is a no-op.
    ([1, 2, 3, 4], [1, 4], 3),  # Preserve older collections already over the cap.
    ([1, 2], [], 1),
    (list(range(1, 101)), [101, 102], None),  # Permanent accounts are uncapped.
])
def test_allowed_requests(existing, requested, limit):
    original_existing, original_requested = existing.copy(), requested.copy()
    assert ensure_problem_capacity(existing, requested, limit) is None
    assert existing == original_existing
    assert requested == original_requested


@pytest.mark.parametrize("existing, requested, limit", [
    (list(range(1, 51)), [51], 50),
    ([1, 2], [3, 4], 3),  # Reject the whole import, rather than partially saving.
    ([1, 2, 3, 4], [5], 3),
])
def test_over_capacity_requests_are_rejected(existing, requested, limit):
    with pytest.raises(ProblemLimitExceeded) as failure:
        ensure_problem_capacity(existing, requested, limit)
    assert f"up to {limit} problems" in str(failure.value)
    assert "Create an account" in str(failure.value)


def test_archived_numbers_still_consume_capacity():
    # The store will pass both active and archived numbers to the policy.
    active_numbers = [1, 2]
    archived_numbers = [3]
    with pytest.raises(ProblemLimitExceeded):
        ensure_problem_capacity(active_numbers + archived_numbers, [4], 3)


def test_default_guest_cap():
    assert DEFAULT_GUEST_PROBLEM_LIMIT == 50
