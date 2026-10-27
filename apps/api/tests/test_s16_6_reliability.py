import pytest

from app.core.reliability import ConcurrencyConflict, RetryPolicy


def test_retry_policy_is_bounded_and_exponential() -> None:
    policy = RetryPolicy(max_attempts=4, initial_delay_seconds=0.25, max_delay_seconds=1.0)
    assert [policy.delay_for(i) for i in range(4)] == [0.25, 0.5, 1.0, 1.0]


def test_retry_policy_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=2.0, max_delay_seconds=1.0).validate()


def test_stale_revision_is_explicitly_non_retryable() -> None:
    conflict = ConcurrencyConflict()
    assert conflict.code == "STALE_REVISION"
    assert conflict.retryable is False
    assert "latest revision" in conflict.recovery
