"""
test_settings_service.py – Tests del servicio de preferencias del usuario.
"""

import json
import os

import pytest

from app.core.event_bus import EventBus
from app.core.settings_service import SettingsService


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "settings.json")


@pytest.fixture
def settings(settings_path, monkeypatch):
    monkeypatch.setattr("app.core.settings_service.SETTINGS_FILE", settings_path)
    monkeypatch.setattr("app.core.settings_service.DATA_DIR", str(settings_path.rsplit(os.sep, 1)[0]))
    return SettingsService(filepath=settings_path)


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_default_theme_is_dark(settings):
    assert settings.theme == "Dark"


def test_default_inactivity_timeout_min_is_10(settings):
    assert settings.inactivity_timeout_min == 10


def test_default_inactivity_timeout_ms(settings):
    assert settings.inactivity_timeout_ms == 10 * 60 * 1000


def test_get_unknown_key_returns_none(settings):
    assert settings.get("nonexistent_key") is None


# ── set / get ─────────────────────────────────────────────────────────────────

def test_set_and_get_theme(settings):
    settings.theme = "Light"
    assert settings.theme == "Light"


def test_set_inactivity_timeout(settings):
    settings.inactivity_timeout_min = 5
    assert settings.inactivity_timeout_min == 5


def test_inactivity_timeout_ms_reflects_set_minutes(settings):
    settings.inactivity_timeout_min = 20
    assert settings.inactivity_timeout_ms == 20 * 60 * 1000


def test_zero_timeout_disabled(settings):
    settings.inactivity_timeout_min = 0
    assert settings.inactivity_timeout_ms == 0


# ── Persistencia ──────────────────────────────────────────────────────────────

def test_persists_to_file(settings, settings_path):
    settings.theme = "Light"
    assert os.path.exists(settings_path)
    with open(settings_path) as f:
        data = json.load(f)
    assert data["theme"] == "Light"


def test_reloads_from_file(settings_path):
    s1 = SettingsService(filepath=settings_path)
    s1.theme = "System"
    s2 = SettingsService(filepath=settings_path)
    assert s2.theme == "System"


def test_corrupted_file_falls_back_to_defaults(settings_path):
    with open(settings_path, "w") as f:
        f.write("NOT VALID JSON")
    s = SettingsService(filepath=settings_path)
    assert s.theme == "Dark"
    assert s.inactivity_timeout_min == 10


def test_partial_file_merges_with_defaults(settings_path):
    with open(settings_path, "w") as f:
        json.dump({"theme": "Light"}, f)
    s = SettingsService(filepath=settings_path)
    assert s.theme == "Light"
    assert s.inactivity_timeout_min == 10   # filled from defaults


# ── EventBus integration ──────────────────────────────────────────────────────

def test_set_emits_settings_changed_event(settings):
    received = []
    EventBus.instance().subscribe("settings.changed", lambda **kw: received.append(kw))
    settings.theme = "Light"
    assert len(received) == 1
    assert received[0]["key"]   == "theme"
    assert received[0]["value"] == "Light"


def test_multiple_sets_emit_multiple_events(settings):
    count = [0]
    EventBus.instance().subscribe("settings.changed", lambda **kw: count.__setitem__(0, count[0] + 1))
    settings.theme = "Light"
    settings.inactivity_timeout_min = 15
    assert count[0] == 2
