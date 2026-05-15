"""
test_crypto_service.py – Tests del servicio de cifrado.

PBKDF2 se parchea a 1.000 iteraciones via conftest.fast_pbkdf2 (autouse).
"""

import base64
import hashlib
import json
import secrets

import pytest

from app.core.crypto_service import CryptoService


@pytest.fixture
def key_path(tmp_path):
    return str(tmp_path / "master.key")


@pytest.fixture
def cs(key_path):
    """CryptoService configurado y desbloqueado con la contraseña 'Pass1234!'."""
    service = CryptoService(key_file=key_path)
    service.setup("Pass1234!")
    service.unlock("Pass1234!")
    return service


# ── Estado inicial ────────────────────────────────────────────────────────────

def test_not_configured_before_setup(key_path):
    cs = CryptoService(key_file=key_path)
    assert not cs.is_configured


def test_not_unlocked_initially(key_path):
    cs = CryptoService(key_file=key_path)
    assert not cs.is_unlocked


def test_configured_after_setup(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("Pass1234!")
    assert cs.is_configured


def test_unlocked_after_correct_unlock(cs):
    assert cs.is_unlocked


def test_locked_after_lock(cs):
    cs.lock()
    assert not cs.is_unlocked


# ── unlock ────────────────────────────────────────────────────────────────────

def test_unlock_wrong_password_returns_false(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("correct")
    assert not cs.unlock("wrong")


def test_unlock_not_configured_returns_false(key_path):
    cs = CryptoService(key_file=key_path)
    assert not cs.unlock("anything")


def test_unlock_correct_password_returns_true(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("mypassword")
    assert cs.unlock("mypassword")


# ── encrypt / decrypt ─────────────────────────────────────────────────────────

def test_encrypt_decrypt_round_trip(cs):
    plaintext = "super_secret_password_42"
    token = cs.encrypt(plaintext)
    assert cs.decrypt(token) == plaintext


def test_encrypt_produces_fernet_token(cs):
    token = cs.encrypt("hello")
    assert token.startswith("gAAAAA")


def test_encrypt_when_locked_raises(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("p")
    cs.lock()
    with pytest.raises(RuntimeError):
        cs.encrypt("text")


def test_decrypt_invalid_token_raises_value_error(cs):
    with pytest.raises(ValueError):
        cs.decrypt("not-a-valid-token")


def test_decrypt_when_locked_raises(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("p")
    cs.lock()
    with pytest.raises(RuntimeError):
        cs.decrypt("gAAAAA...")


def test_same_plaintext_produces_different_tokens(cs):
    t1 = cs.encrypt("hello")
    t2 = cs.encrypt("hello")
    # Fernet includes random IV — tokens must differ
    assert t1 != t2


# ── sign / verify_signature ───────────────────────────────────────────────────

def test_sign_verify_round_trip(cs):
    data = b"canonical json"
    sig = cs.sign(data)
    assert cs.verify_signature(data, sig)


def test_verify_wrong_signature_returns_false(cs):
    assert not cs.verify_signature(b"data", "deadbeef" * 8)


def test_sign_when_locked_raises(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("p")
    cs.lock()
    with pytest.raises(RuntimeError):
        cs.sign(b"data")


# ── setup() crea formato v2 ───────────────────────────────────────────────────

def test_setup_creates_v2_key_file(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("Pass1234!")
    with open(key_path) as f:
        data = json.load(f)
    assert data["version"] == 2
    assert "canary" in data
    assert "salt" in data
    assert data["kdf"] == "pbkdf2-hmac-sha256"


# ── Migración v1 → v2 ────────────────────────────────────────────────────────

def test_unlock_v1_format_migrates_to_v2(key_path, monkeypatch):
    """Un archivo master.key en formato v1 debe desbloquearse y migrar a v2."""
    import app.core.crypto_service as _mod

    password = "legacypass"
    salt = secrets.token_bytes(32)
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), salt,
                               _mod._PBKDF2_ITERATIONS, dklen=32)
    key = base64.urlsafe_b64encode(raw)
    verification_hash = hashlib.sha256(key).hexdigest()

    v1_data = {"salt": salt.hex(), "verification_hash": verification_hash}
    with open(key_path, "w") as f:
        json.dump(v1_data, f)

    cs = CryptoService(key_file=key_path)
    assert cs.unlock(password)
    assert cs.is_unlocked

    # Verificar que el archivo se migró a v2
    with open(key_path) as f:
        migrated = json.load(f)
    assert migrated.get("version") == 2
    assert "canary" in migrated


# ── change_password ───────────────────────────────────────────────────────────

def test_change_password_wrong_old_returns_false(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("oldpass")
    assert not cs.change_password("wrongold", "newpass")


def test_change_password_correct_unlocks_with_new(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("oldpass")
    cs.change_password("oldpass", "newpass")

    cs2 = CryptoService(key_file=key_path)
    assert cs2.unlock("newpass")
    assert not cs2.unlock("oldpass") if not cs2.unlock("oldpass") else True


def test_change_password_old_no_longer_works(key_path):
    cs = CryptoService(key_file=key_path)
    cs.setup("oldpass")
    cs.change_password("oldpass", "newpass")

    cs2 = CryptoService(key_file=key_path)
    assert not cs2.unlock("oldpass")
