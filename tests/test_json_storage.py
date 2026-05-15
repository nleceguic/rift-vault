"""
test_json_storage.py – Tests de integración de JsonStorage.

Cubre: CRUD básico, cifrado transparente, migración de texto plano,
verificación de integridad HMAC y operación rekey.
"""

import dataclasses
import json
import os

import pytest

from app.core.account import Account
from app.storage.json_storage import JsonStorage


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_account(**kwargs) -> Account:
    defaults = dict(alias="Test", username="user", password="pass123", region="EUW")
    defaults.update(kwargs)
    return Account(**defaults)


# ── Sin crypto (modo no cifrado) ──────────────────────────────────────────────

class TestNoCrypto:
    @pytest.fixture
    def store(self, tmp_path):
        return JsonStorage(filepath=str(tmp_path / "accounts.json"), crypto=None)

    def test_load_empty_returns_empty_list(self, store):
        assert store.load_all() == []

    def test_save_then_load_round_trip(self, store):
        a = make_account(alias="Alpha")
        store.save(a)
        accounts = store.load_all()
        assert len(accounts) == 1
        assert accounts[0].alias == "Alpha"

    def test_save_duplicate_id_raises(self, store):
        a = make_account()
        store.save(a)
        with pytest.raises(ValueError, match="id"):
            store.save(a)

    def test_update_modifies_account(self, store):
        a = make_account(alias="Before")
        store.save(a)
        a2 = dataclasses.replace(a, alias="After")
        store.update(a2)
        loaded = store.find_by_id(a.id)
        assert loaded.alias == "After"

    def test_update_nonexistent_raises(self, store):
        a = make_account()
        with pytest.raises(ValueError, match="id"):
            store.update(a)

    def test_delete_returns_true(self, store):
        a = make_account()
        store.save(a)
        assert store.delete(a.id)

    def test_delete_nonexistent_returns_false(self, store):
        assert not store.delete("ghost-id-000")

    def test_delete_removes_from_load_all(self, store):
        a = make_account()
        store.save(a)
        store.delete(a.id)
        assert store.load_all() == []

    def test_find_by_id_returns_account(self, store):
        a = make_account()
        store.save(a)
        found = store.find_by_id(a.id)
        assert found is not None
        assert found.id == a.id

    def test_find_by_id_unknown_returns_none(self, store):
        assert store.find_by_id("nonexistent") is None

    def test_multiple_accounts_all_saved(self, store):
        for i in range(5):
            store.save(make_account(alias=f"Account{i}"))
        assert len(store.load_all()) == 5

    def test_atomic_write_no_tmp_file_left(self, store, tmp_path):
        store.save(make_account())
        tmp = str(tmp_path / "accounts.json.tmp")
        assert not os.path.exists(tmp)


# ── Con crypto ────────────────────────────────────────────────────────────────

class TestWithCrypto:
    def test_password_stored_as_fernet_token(self, storage):
        a = make_account(password="plaintext_pass")
        a = storage.save(a)
        assert a.password.startswith("gAAAAA")

    def test_get_decrypted_password_returns_plaintext(self, storage):
        a = make_account(password="my_secret")
        storage.save(a)
        decrypted = storage.get_decrypted_password(a.id)
        assert decrypted == "my_secret"

    def test_get_decrypted_password_nonexistent_returns_empty(self, storage):
        assert storage.get_decrypted_password("ghost-id") == ""

    def test_update_with_new_password_encrypts(self, storage):
        a = make_account(password="old")
        storage.save(a)
        a2 = dataclasses.replace(a, password="new_plaintext")
        storage.update(a2)
        assert storage.get_decrypted_password(a.id) == "new_plaintext"

    def test_load_all_preserves_fernet_token_not_plaintext(self, storage):
        a = make_account(password="secret123")
        storage.save(a)
        loaded = storage.load_all()
        assert loaded[0].password.startswith("gAAAAA")


# ── Migración de texto plano ──────────────────────────────────────────────────

class TestPlaintextMigration:
    def test_plaintext_password_migrated_on_load(self, tmp_path, crypto):
        filepath = str(tmp_path / "accounts.json")
        # Escribir un JSON con contraseña en texto plano directamente
        raw_data = {
            "version": 1,
            "accounts": [{
                "id": "abc123",
                "alias": "OldAccount",
                "username": "olduser",
                "password": "plaintextpass",  # sin cifrar
                "region": "EUW",
                "tags": [],
                "notes": "",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }]
        }
        with open(filepath, "w") as f:
            json.dump(raw_data, f)

        store = JsonStorage(filepath=filepath, crypto=crypto)
        accounts = store.load_all()
        assert len(accounts) == 1
        # Después de la migración, la contraseña debe ser un token Fernet
        assert accounts[0].password.startswith("gAAAAA")

    def test_migrated_password_is_decryptable(self, tmp_path, crypto):
        filepath = str(tmp_path / "accounts.json")
        raw_data = {
            "version": 1,
            "accounts": [{
                "id": "xyz789", "alias": "Old", "username": "u",
                "password": "mysecret", "region": "EUW", "tags": [], "notes": "",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }]
        }
        with open(filepath, "w") as f:
            json.dump(raw_data, f)

        store = JsonStorage(filepath=filepath, crypto=crypto)
        store.load_all()
        assert store.get_decrypted_password("xyz789") == "mysecret"


# ── Integridad HMAC ───────────────────────────────────────────────────────────

class TestHMACIntegrity:
    def test_tampered_file_raises_runtime_error(self, tmp_path, storage, crypto):
        a = make_account(password="secret")
        storage.save(a)

        filepath = str(tmp_path / "accounts.json")
        with open(filepath, "r") as f:
            data = json.load(f)

        # Manipular un campo sin actualizar el HMAC
        data["accounts"][0]["alias"] = "TAMPERED"
        with open(filepath, "w") as f:
            json.dump(data, f)

        fresh = JsonStorage(filepath=filepath, crypto=crypto)
        with pytest.raises(RuntimeError, match="ntegridad"):
            fresh.load_all()

    def test_tampered_file_creates_backup(self, tmp_path, storage, crypto):
        a = make_account(password="secret")
        storage.save(a)

        filepath = str(tmp_path / "accounts.json")
        with open(filepath, "r") as f:
            data = json.load(f)
        data["accounts"][0]["alias"] = "TAMPERED"
        with open(filepath, "w") as f:
            json.dump(data, f)

        fresh = JsonStorage(filepath=filepath, crypto=crypto)
        try:
            fresh.load_all()
        except RuntimeError:
            pass
        assert os.path.exists(filepath + ".tampered")

    def test_corrupted_json_creates_bak_and_returns_empty(self, tmp_path, crypto):
        filepath = str(tmp_path / "accounts.json")
        with open(filepath, "w") as f:
            f.write("{ NOT VALID JSON }")

        store = JsonStorage(filepath=filepath, crypto=crypto)
        result = store.load_all()
        assert result == []
        assert os.path.exists(filepath + ".bak")


# ── rekey ─────────────────────────────────────────────────────────────────────

class TestRekey:
    def test_rekey_passwords_decryptable_with_new_key(self, tmp_path, crypto):
        from app.core.crypto_service import CryptoService

        filepath = str(tmp_path / "accounts.json")
        store = JsonStorage(filepath=filepath, crypto=crypto)

        a = make_account(password="original_pass")
        store.save(a)

        # Guardar claves anteriores antes del cambio
        old_fernet      = crypto._fernet
        old_signing_key = crypto._signing_key

        # Crear nuevo CryptoService con contraseña diferente
        new_crypto = CryptoService(key_file=str(tmp_path / "master2.key"))
        new_crypto.setup("NewPass999!")
        new_crypto.unlock("NewPass999!")

        store.rekey(old_fernet, old_signing_key, new_crypto)

        # Verificar que la contraseña sigue siendo accesible con la nueva clave
        fresh = JsonStorage(filepath=filepath, crypto=new_crypto)
        assert fresh.get_decrypted_password(a.id) == "original_pass"

    def test_rekey_nonexistent_file_does_not_raise(self, tmp_path, crypto):
        from app.core.crypto_service import CryptoService

        filepath = str(tmp_path / "missing.json")
        store = JsonStorage(filepath=filepath, crypto=crypto)

        new_crypto = CryptoService(key_file=str(tmp_path / "k2.key"))
        new_crypto.setup("x")
        new_crypto.unlock("x")

        store.rekey(crypto._fernet, crypto._signing_key, new_crypto)  # should not raise
