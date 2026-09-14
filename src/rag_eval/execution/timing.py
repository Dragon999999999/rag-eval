"""Client-side timing capture for target requests.

Captures raw client timing independently from target-provided trace timing:

```text
request_started_at
request_finished_at
duration_ms
```

Additional timing (TTFT, event timestamps) preserved when streaming.
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ClientTiming:
    """Client-side timing for one target request."""

    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = field(default=0.0, init=False)

    # High-resolution monotonic time for duration calculation
    _start_monotonic: float = field(default=0.0, repr=False)
    _end_monotonic: float = field(default=0.0, repr=False)

    def start(self) -> None:
        """Record request start timestamp."""
        self.started_at = datetime.now(UTC)
        self._start_monotonic = time.perf_counter()

    def end(self) -> None:
        """Record request end timestamp and calculate duration."""
        self.finished_at = datetime.now(UTC)
        self._end_monotonic = time.perf_counter()

        # Calculate duration in milliseconds
        if self._start_monotonic > 0:
            elapsed = self._end_monotonic - self._start_monotonic
            self.duration_ms = round(elapsed * 1000, 3)

    @property
    def has_timing(self) -> bool:
        """Check if timing was captured."""
        return self.started_at is not None and self.finished_at is not None
