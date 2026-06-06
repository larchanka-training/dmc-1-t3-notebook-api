from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    """Simple process-local rate limiter for auth throttling."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = monotonic()
        window_start = now - window_seconds

        with self._lock:
            timestamps = [ts for ts in self._events[key] if ts >= window_start]
            if len(timestamps) >= limit:
                oldest = min(timestamps)
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self._events[key] = timestamps
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

            timestamps.append(now)
            self._events[key] = timestamps
            return RateLimitResult(allowed=True)


otp_request_limiter = InMemoryRateLimiter()
otp_verify_limiter = InMemoryRateLimiter()
