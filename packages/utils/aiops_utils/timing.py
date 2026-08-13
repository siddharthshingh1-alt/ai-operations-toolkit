"""Duration measurement for the activity log (CLAUDE.md Section 22)."""

from __future__ import annotations

import time
from types import TracebackType


class Stopwatch:
    """Measure wall-clock duration in milliseconds.

        with Stopwatch() as sw:
            do_work()
        print(sw.elapsed_ms)

    Uses a monotonic clock, so it is unaffected by system clock changes.
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self._end: float | None = None

    def __enter__(self) -> Stopwatch:
        self._start = time.perf_counter()
        self._end = None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        """Elapsed milliseconds. Reads live if the stopwatch is still running."""
        if self._start is None:
            return 0
        end = self._end if self._end is not None else time.perf_counter()
        return int((end - self._start) * 1000)
