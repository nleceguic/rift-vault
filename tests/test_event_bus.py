"""
test_event_bus.py – Tests del sistema pub/sub EventBus.
"""

import pytest
from app.core.event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus.instance()


# ── Singleton ─────────────────────────────────────────────────────────────────

def test_instance_is_singleton(bus):
    assert EventBus.instance() is bus


def test_reset_creates_new_instance(bus):
    EventBus.reset()
    assert EventBus.instance() is not bus


# ── subscribe / emit ──────────────────────────────────────────────────────────

def test_emit_calls_subscriber(bus):
    received = []
    bus.subscribe("test.event", lambda **kw: received.append(kw))
    bus.emit("test.event", value=42)
    assert received == [{"value": 42}]


def test_emit_calls_multiple_subscribers(bus):
    counts = [0, 0]
    bus.subscribe("e", lambda: counts.__setitem__(0, counts[0] + 1))
    bus.subscribe("e", lambda: counts.__setitem__(1, counts[1] + 1))
    bus.emit("e")
    assert counts == [1, 1]


def test_emit_unknown_event_does_not_raise(bus):
    bus.emit("event.nobody.subscribed")  # should not raise


def test_emit_passes_payload_as_kwargs(bus):
    received = {}
    bus.subscribe("payload.test", lambda **kw: received.update(kw))
    bus.emit("payload.test", a=1, b="hello")
    assert received == {"a": 1, "b": "hello"}


# ── Deduplicación ─────────────────────────────────────────────────────────────

def test_subscribe_same_callback_twice_calls_once(bus):
    calls = []
    cb = lambda **kw: calls.append(1)
    bus.subscribe("dup", cb)
    bus.subscribe("dup", cb)
    bus.emit("dup")
    assert len(calls) == 1


# ── unsubscribe ───────────────────────────────────────────────────────────────

def test_unsubscribe_stops_callbacks(bus):
    calls = []
    cb = lambda **kw: calls.append(1)
    bus.subscribe("ev", cb)
    bus.unsubscribe("ev", cb)
    bus.emit("ev")
    assert calls == []


def test_unsubscribe_nonexistent_does_not_raise(bus):
    bus.unsubscribe("nosuchevent", lambda: None)


# ── clear ─────────────────────────────────────────────────────────────────────

def test_clear_event_removes_subscribers(bus):
    calls = []
    bus.subscribe("tgt", lambda **kw: calls.append(1))
    bus.clear("tgt")
    bus.emit("tgt")
    assert calls == []


def test_clear_all_removes_everything(bus):
    calls = []
    bus.subscribe("e1", lambda **kw: calls.append("e1"))
    bus.subscribe("e2", lambda **kw: calls.append("e2"))
    bus.clear()
    bus.emit("e1")
    bus.emit("e2")
    assert calls == []


# ── list_events ───────────────────────────────────────────────────────────────

def test_list_events_returns_subscribed_events(bus):
    bus.subscribe("visible", lambda **kw: None)
    assert "visible" in bus.list_events()


def test_list_events_excludes_cleared_events(bus):
    bus.subscribe("gone", lambda **kw: None)
    bus.clear("gone")
    assert "gone" not in bus.list_events()


# ── Resiliencia ───────────────────────────────────────────────────────────────

def test_exception_in_callback_does_not_stop_others(bus):
    results = []

    def bad(**kw):
        raise RuntimeError("boom")

    def good(**kw):
        results.append("ok")

    bus.subscribe("crash", bad)
    bus.subscribe("crash", good)
    bus.emit("crash")        # should not raise
    assert results == ["ok"]
