from __future__ import annotations

import threading

# Fast, in-process cancellation signals. The database flag remains the
# authoritative source across processes/restarts; this registry only lets the
# running job notice a stop request without a database round-trip.
_lock = threading.Lock()
_events: dict[str, threading.Event] = {}


def register(job_id: str) -> None:
    """Create the event for a job without clearing an earlier request."""

    with _lock:
        _events.setdefault(job_id, threading.Event())


def request_cancel(job_id: str) -> None:
    with _lock:
        event = _events.setdefault(job_id, threading.Event())
    event.set()


def is_cancel_requested(job_id: str) -> bool:
    with _lock:
        event = _events.get(job_id)
    return bool(event and event.is_set())


def clear(job_id: str) -> None:
    with _lock:
        _events.pop(job_id, None)
