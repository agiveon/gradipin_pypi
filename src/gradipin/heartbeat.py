"""Background heartbeat thread that pings the API on a fixed interval."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger("gradipin")


class HeartbeatThread(threading.Thread):
    """A daemon thread that calls ``tick`` every ``interval`` seconds until stopped."""

    def __init__(self, tick: Callable[[], None], interval: int) -> None:
        super().__init__(daemon=True, name="gradipin-heartbeat")
        self._tick = tick
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.warning("Gradipin heartbeat failed", exc_info=True)
            self._stop_event.wait(self._interval)

    def stop(self) -> None:
        self._stop_event.set()
