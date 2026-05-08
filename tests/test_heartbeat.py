"""Tests for gradipin.heartbeat."""
from __future__ import annotations

import threading
import time

from gradipin.heartbeat import HeartbeatThread


def test_tick_called_at_least_once_quickly() -> None:
    counter = {"n": 0}
    event = threading.Event()

    def tick() -> None:
        counter["n"] += 1
        event.set()

    hb = HeartbeatThread(tick, interval=60)
    hb.start()
    try:
        assert event.wait(2.0), "tick was never invoked"
        assert counter["n"] >= 1
    finally:
        hb.stop()
        hb.join(timeout=2.0)
        assert not hb.is_alive()


def test_tick_called_repeatedly() -> None:
    counter = {"n": 0}

    def tick() -> None:
        counter["n"] += 1

    hb = HeartbeatThread(tick, interval=0)
    hb.start()
    try:
        time.sleep(0.2)
    finally:
        hb.stop()
        hb.join(timeout=2.0)
    assert counter["n"] >= 2


def test_exception_in_tick_does_not_kill_thread() -> None:
    counter = {"n": 0}

    def tick() -> None:
        counter["n"] += 1
        raise RuntimeError("boom")

    hb = HeartbeatThread(tick, interval=0)
    hb.start()
    try:
        time.sleep(0.2)
        assert hb.is_alive()
        assert counter["n"] >= 2
    finally:
        hb.stop()
        hb.join(timeout=2.0)


def test_stop_terminates_thread() -> None:
    hb = HeartbeatThread(lambda: None, interval=60)
    hb.start()
    assert hb.is_alive()
    hb.stop()
    hb.join(timeout=2.0)
    assert not hb.is_alive()


def test_thread_is_daemon() -> None:
    hb = HeartbeatThread(lambda: None, interval=60)
    assert hb.daemon is True
    assert hb.name == "gradipin-heartbeat"
