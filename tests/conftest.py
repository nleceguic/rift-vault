"""
conftest.py – Fixtures compartidas para toda la suite de tests.

Convenciones:
  - fast_pbkdf2: reduce iteraciones PBKDF2 de 480K a 1K (tests en ms, no segundos)
  - reset_singletons: limpia EventBus y HooksRegistry antes y después de cada test
  - crypto / storage / service: fixtures encadenadas para tests de integración
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures de infraestructura (autouse) ─────────────────────────────────────

@pytest.fixture(autouse=True)
def fast_pbkdf2(monkeypatch):
    """Reduce iteraciones PBKDF2 para que los tests de crypto duren ms, no segundos."""
    monkeypatch.setattr("app.core.crypto_service._PBKDF2_ITERATIONS", 1_000)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Garantiza singletons limpios antes y después de cada test."""
    from app.core.event_bus import EventBus
    from app.hooks.hooks_registry import HooksRegistry
    EventBus.reset()
    HooksRegistry.reset()
    yield
    EventBus.reset()
    HooksRegistry.reset()


# ── Fixtures de dominio ───────────────────────────────────────────────────────

@pytest.fixture
def crypto(tmp_path):
    from app.core.crypto_service import CryptoService
    cs = CryptoService(key_file=str(tmp_path / "master.key"))
    cs.setup("TestPass123!")
    cs.unlock("TestPass123!")
    return cs


@pytest.fixture
def storage(tmp_path, crypto):
    from app.storage.json_storage import JsonStorage
    return JsonStorage(filepath=str(tmp_path / "accounts.json"), crypto=crypto)


@pytest.fixture
def service(storage):
    from app.core.account_service import AccountService
    return AccountService(storage)


@pytest.fixture
def sample_data():
    return {
        "alias":    "Main EUW",
        "username": "testuser",
        "password": "testpass123",
        "region":   "EUW",
        "tags":     ["ranked", "main"],
        "notes":    "Test account",
    }
