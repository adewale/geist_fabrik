"""Shared best-effort wall-clock limits for trusted Python plugin code."""

import signal
import sys
import threading
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, NoReturn


class GeistTimeoutError(Exception):
    """Raised when trusted plugin code exceeds its configured deadline."""


@dataclass
class _AlarmState:
    """Process-global SIGALRM state; only used from the Python main thread."""

    started: float
    previous_handler: Any
    host_deadline: float
    host_interval: float
    deadlines: list[float] = field(default_factory=list)


_active_state: _AlarmState | None = None


def timeout_handler(signum: int, frame: FrameType | None) -> NoReturn:
    """Compatibility handler that raises the public timeout exception."""
    del signum, frame
    raise GeistTimeoutError("Geist execution timed out")


def _arm_next(state: _AlarmState) -> None:
    now = time.monotonic() - state.started
    candidates = list(state.deadlines)
    if state.host_deadline != float("inf"):
        candidates.append(state.host_deadline)
    if not candidates:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        return
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, min(candidates) - now))


def _dispatch_alarm(signum: int, frame: FrameType | None) -> None:
    state = _active_state
    if state is None:
        timeout_handler(signum, frame)
    elapsed = time.monotonic() - state.started
    epsilon = 0.005

    if state.host_deadline <= elapsed + epsilon:
        handler = state.previous_handler
        if callable(handler):
            # Recreate the host's periodic schedule before callback delivery so
            # changes made by the handler (including cancellation) are visible.
            if state.host_interval > 0:
                signal.setitimer(
                    signal.ITIMER_REAL,
                    state.host_interval,
                    state.host_interval,
                )
            else:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
            handler(signum, frame)
            host_remaining, host_interval = signal.getitimer(signal.ITIMER_REAL)
            elapsed = time.monotonic() - state.started
            if host_remaining > 0:
                state.host_deadline = elapsed + host_remaining
                state.host_interval = host_interval
            else:
                state.host_deadline = float("inf")
                state.host_interval = 0.0
        else:
            state.host_deadline = float("inf")
            state.host_interval = 0.0

    if state.deadlines and min(state.deadlines) <= elapsed + epsilon:
        raise GeistTimeoutError("Geist execution timed out")
    _arm_next(state)


@contextmanager
def alarm_timeout(seconds: int) -> Iterator[None]:
    """Bound trusted plugin work while preserving callable host alarms.

    Hard interruption is available only with POSIX ``SIGALRM`` on the main
    thread. Nested limits share one dispatcher. An existing callable one-shot
    or periodic host alarm is delivered on schedule and does not disable the
    plugin deadline. A non-callable active host handler is left untouched and
    causes an explicit warning because Python cannot safely emulate its
    process-level semantics.
    """
    global _active_state
    supported = (
        sys.platform != "win32"
        and threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    )
    if not supported:
        warnings.warn(
            "Hard geist timeout unavailable on this platform/thread; "
            "custom Python plugins are trusted code",
            RuntimeWarning,
            stacklevel=2,
        )
        yield
        return

    if _active_state is not None:
        state = _active_state
        deadline = time.monotonic() - state.started + float(seconds)
        state.deadlines.append(deadline)
        _arm_next(state)
        try:
            yield
        finally:
            state.deadlines.remove(deadline)
            _arm_next(state)
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0] and not callable(previous_handler):
        warnings.warn(
            "Hard geist timeout unavailable while a non-callable host SIGALRM "
            "handler is active; preserving the host alarm and running trusted code",
            RuntimeWarning,
            stacklevel=2,
        )
        yield
        return

    started = time.monotonic()
    host_deadline = previous_timer[0] if previous_timer[0] else float("inf")
    state = _AlarmState(started, previous_handler, host_deadline, previous_timer[1])
    deadline = float(seconds)
    state.deadlines.append(deadline)
    _active_state = state
    signal.signal(signal.SIGALRM, _dispatch_alarm)
    _arm_next(state)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        elapsed = time.monotonic() - started
        if state.host_deadline == float("inf"):
            remaining = 0.0
        else:
            remaining = max(1e-6, state.host_deadline - elapsed)
        signal.setitimer(signal.ITIMER_REAL, remaining, state.host_interval)
        _active_state = None


# Private compatibility name used by existing executor/tests.
_alarm_timeout = alarm_timeout
