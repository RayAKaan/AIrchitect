from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def delay_for(self, retry_index: int) -> float:
        if retry_index < 0:
            raise ValueError("retry_index must be non-negative")
        return min(self.max_delay_seconds, self.initial_delay_seconds * (2**retry_index))

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
        if self.initial_delay_seconds > self.max_delay_seconds:
            raise ValueError("initial delay cannot exceed maximum delay")


@dataclass(frozen=True)
class ConcurrencyConflict:
    code: str = "STALE_REVISION"
    retryable: bool = False
    recovery: str = "Refresh the canonical version and generate a new proposal from the latest revision."


DEFAULT_RETRY_POLICY = RetryPolicy()
DEFAULT_RETRY_POLICY.validate()
