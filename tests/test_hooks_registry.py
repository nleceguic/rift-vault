"""
test_hooks_registry.py – Tests del sistema de hooks (run / fire / can).
"""

import pytest
from app.hooks.base_hook import BaseHook
from app.hooks.hooks_registry import HooksRegistry


# ── Helpers ───────────────────────────────────────────────────────────────────

class RecordingHook(BaseHook):
    name = "recording"

    def __init__(self):
        self.fired_events: list[tuple] = []

    def before_account_create(self, data: dict) -> dict:
        self.fired_events.append(("before_create", data))
        return data

    def after_account_create(self, account) -> None:
        self.fired_events.append(("after_create", account))

    def before_account_delete(self, account_id: str) -> bool:
        self.fired_events.append(("before_delete", account_id))
        return True


class MutatingHook(BaseHook):
    name = "mutating"

    def before_account_create(self, data: dict) -> dict:
        data = dict(data)
        data["alias"] = data["alias"].upper()
        return data


class CancelDeleteHook(BaseHook):
    name = "cancel_delete"

    def before_account_delete(self, account_id: str) -> bool:
        return False


class ExplodingHook(BaseHook):
    name = "exploding"

    def after_account_create(self, account) -> None:
        raise RuntimeError("kaboom")


@pytest.fixture
def registry():
    return HooksRegistry.instance()


# ── Singleton ─────────────────────────────────────────────────────────────────

def test_instance_is_singleton(registry):
    assert HooksRegistry.instance() is registry


def test_reset_creates_new_instance(registry):
    HooksRegistry.reset()
    assert HooksRegistry.instance() is not registry


# ── register / unregister ─────────────────────────────────────────────────────

def test_register_adds_hook(registry):
    registry.register(RecordingHook())
    assert "recording" in registry.list_hooks()


def test_register_replaces_hook_with_same_name(registry):
    registry.register(RecordingHook())
    registry.register(RecordingHook())
    assert registry.list_hooks().count("recording") == 1


def test_unregister_removes_hook(registry):
    registry.register(RecordingHook())
    registry.unregister("recording")
    assert "recording" not in registry.list_hooks()


def test_unregister_nonexistent_does_not_raise(registry):
    registry.unregister("ghost")


# ── run() ─────────────────────────────────────────────────────────────────────

def test_run_with_no_hooks_returns_original_value(registry):
    data = {"alias": "test"}
    result = registry.run("before_account_create", data=data)
    assert result == {"alias": "test"}


def test_run_hook_can_transform_data(registry):
    registry.register(MutatingHook())
    data = {"alias": "main"}
    result = registry.run("before_account_create", data=data)
    assert result["alias"] == "MAIN"


def test_run_multiple_hooks_chain(registry):
    class DoubleHook(BaseHook):
        name = "double"
        def before_account_create(self, data):
            return {**data, "alias": data["alias"] + "!"}

    class TripleHook(BaseHook):
        name = "triple"
        def before_account_create(self, data):
            return {**data, "alias": data["alias"] + "?"}

    registry.register(DoubleHook())
    registry.register(TripleHook())
    result = registry.run("before_account_create", data={"alias": "x"})
    assert result["alias"] == "x!?"


def test_run_hook_with_no_matching_method_returns_original(registry):
    registry.register(RecordingHook())
    # RecordingHook has no 'after_unlock' method override that returns value
    # run() on 'after_unlock' should return None (no first kwarg named 'data')
    result = registry.run("after_unlock")
    assert result is None


# ── fire() ────────────────────────────────────────────────────────────────────

def test_fire_calls_hook_method(registry):
    hook = RecordingHook()
    registry.register(hook)
    registry.fire("after_account_create", account="dummy")
    assert any(e[0] == "after_create" for e in hook.fired_events)


def test_fire_exception_does_not_propagate(registry):
    registry.register(ExplodingHook())
    registry.fire("after_account_create", account="dummy")  # should not raise


def test_fire_calls_all_hooks_despite_exception(registry):
    results = []

    class Good(BaseHook):
        name = "good"
        def after_account_create(self, account):
            results.append("ok")

    registry.register(ExplodingHook())
    registry.register(Good())
    registry.fire("after_account_create", account="dummy")
    assert "ok" in results


# ── can() ─────────────────────────────────────────────────────────────────────

def test_can_returns_true_with_no_hooks(registry):
    assert registry.can("before_account_delete", account_id="123")


def test_can_returns_true_when_hook_allows(registry):
    registry.register(RecordingHook())
    assert registry.can("before_account_delete", account_id="123")


def test_can_returns_false_when_hook_cancels(registry):
    registry.register(CancelDeleteHook())
    assert not registry.can("before_account_delete", account_id="123")


def test_can_short_circuits_on_first_false(registry):
    calls = []

    class WatchHook(BaseHook):
        name = "watcher"
        def before_account_delete(self, account_id):
            calls.append(account_id)
            return True

    registry.register(CancelDeleteHook())
    registry.register(WatchHook())
    result = registry.can("before_account_delete", account_id="abc")
    assert not result
    # WatchHook should never run because CancelDeleteHook short-circuited
    assert calls == []
