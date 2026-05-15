"""
test_sqlite_storage.py – Tests de SqliteStorage.

Verifica el mismo contrato que test_json_storage.py (CRUD, cifrado,
migración de texto plano, HMAC, rekey) más comportamientos SQLite-específicos
(índices, migración desde JSON, transacciones atómicas).
"""

import dataclasses
import json
import os
import sqlite3

import pytest

from app.core.account import Account
from app.storage.sqlite_storage import SqliteStorage


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_account(**kwargs) -> Account:
    defaults = dict(alias="Test", username="user", password="pass123", region="EUW")
    defaults.update(kwargs)
    return Account(**defaults)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "accounts.db")


@pytest.fixture
def store(db_path):
    return SqliteStorage(filepath=db_path, crypto=None)


@pytest.fixture
def store_crypto(db_path, crypto):
    return SqliteStorage(filepath=db_path, crypto=crypto)


# ── Inicialización ────────────────────────────────────────────────────────────

def test_db_file_created_on_init(db_path):
    SqliteStorage(filepath=db_path)
    assert os.path.exists(db_path)


def test_tables_created_on_init(db_path):
    SqliteStorage(filepath=db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "accounts" in tables
    assert "meta" in tables


def test_indices_created_on_init(db_path):
    SqliteStorage(filepath=db_path)
    conn = sqlite3.connect(db_path)
    indices = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
    conn.close()
    assert "idx_alias" in indices
    assert "idx_region" in indices


# ── CRUD sin crypto ───────────────────────────────────────────────────────────

class TestNoCrypto:
    def test_load_all_empty(self, store):
        assert store.load_all() == []

    def test_save_and_load(self, store):
        a = make_account(alias="Alpha")
        store.save(a)
        accounts = store.load_all()
        assert len(accounts) == 1
        assert accounts[0].alias == "Alpha"

    def test_save_preserves_all_fields(self, store):
        a = make_account(alias="Main", username="player", password="pass",
                         region="NA", tags=["ranked"], notes="test note")
        store.save(a)
        loaded = store.find_by_id(a.id)
        assert loaded.alias    == "Main"
        assert loaded.username == "player"
        assert loaded.region   == "NA"
        assert loaded.tags     == ["ranked"]
        assert loaded.notes    == "test note"

    def test_save_duplicate_id_raises(self, store):
        a = make_account()
        store.save(a)
        with pytest.raises(ValueError, match="id"):
            store.save(a)

    def test_update_modifies_alias(self, store):
        a = make_account(alias="Before")
        store.save(a)
        a2 = dataclasses.replace(a, alias="After")
        store.update(a2)
        assert store.find_by_id(a.id).alias == "After"

    def test_update_nonexistent_raises(self, store):
        a = make_account()
        with pytest.raises(ValueError, match="id"):
            store.update(a)

    def test_update_calls_touch(self, store):
        a = dataclasses.replace(make_account(), updated_at="2000-01-01T00:00:00+00:00")
        store.save(a)
        store.update(a)
        loaded = store.find_by_id(a.id)
        assert loaded.updated_at != "2000-01-01T00:00:00+00:00"

    def test_delete_returns_true(self, store):
        a = make_account()
        store.save(a)
        assert store.delete(a.id)

    def test_delete_removes_account(self, store):
        a = make_account()
        store.save(a)
        store.delete(a.id)
        assert store.load_all() == []

    def test_delete_nonexistent_returns_false(self, store):
        assert not store.delete("ghost-id-000")

    def test_find_by_id_returns_account(self, store):
        a = make_account()
        store.save(a)
        found = store.find_by_id(a.id)
        assert found is not None and found.id == a.id

    def test_find_by_id_unknown_returns_none(self, store):
        assert store.find_by_id("nonexistent") is None

    def test_load_all_returns_multiple(self, store):
        for i in range(5):
            store.save(make_account(alias=f"Acc{i}"))
        assert len(store.load_all()) == 5

    def test_tags_round_trip_empty(self, store):
        a = make_account(tags=[])
        store.save(a)
        assert store.find_by_id(a.id).tags == []

    def test_tags_round_trip_multiple(self, store):
        a = make_account(tags=["ranked", "smurf", "main"])
        store.save(a)
        assert sorted(store.find_by_id(a.id).tags) == ["main", "ranked", "smurf"]


# ── Con crypto ────────────────────────────────────────────────────────────────

class TestWithCrypto:
    def test_password_stored_as_fernet_token(self, store_crypto):
        a = make_account(password="plaintext_pass")
        a = store_crypto.save(a)
        assert a.password.startswith("gAAAAA")

    def test_get_decrypted_password_returns_plaintext(self, store_crypto):
        a = make_account(password="my_secret")
        store_crypto.save(a)
        assert store_crypto.get_decrypted_password(a.id) == "my_secret"

    def test_get_decrypted_password_nonexistent_returns_empty(self, store_crypto):
        assert store_crypto.get_decrypted_password("ghost") == ""

    def test_update_new_password_encrypts(self, store_crypto):
        a = make_account(password="old")
        store_crypto.save(a)
        a2 = dataclasses.replace(a, password="new_plaintext")
        store_crypto.update(a2)
        assert store_crypto.get_decrypted_password(a.id) == "new_plaintext"

    def test_update_existing_token_reuses_it(self, store_crypto):
        a = make_account(password="secret")
        store_crypto.save(a)
        token = a.password
        store_crypto.update(a)   # password is already a Fernet token
        assert store_crypto.get_decrypted_password(a.id) == "secret"

    def test_load_all_keeps_fernet_token(self, store_crypto):
        a = make_account(password="secret123")
        store_crypto.save(a)
        loaded = store_crypto.load_all()
        assert loaded[0].password.startswith("gAAAAA")


# ── Migración de texto plano ──────────────────────────────────────────────────

class TestPlaintextMigration:
    def test_plaintext_password_migrated_on_load(self, db_path, crypto):
        # Insertar una cuenta con contraseña en texto plano directamente en SQLite
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, alias TEXT, username TEXT, password TEXT, region TEXT, tags TEXT, notes TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?)",
                     ("id1", "Old", "u", "plaintextpass", "EUW", "[]", "", "2024-01-01", "2024-01-01"))
        conn.commit(); conn.close()

        store = SqliteStorage(filepath=db_path, crypto=crypto)
        accounts = store.load_all()
        assert accounts[0].password.startswith("gAAAAA")

    def test_migrated_password_is_decryptable(self, db_path, crypto):
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, alias TEXT, username TEXT, password TEXT, region TEXT, tags TEXT, notes TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?)",
                     ("id2", "Old", "u", "mysecret", "EUW", "[]", "", "2024-01-01", "2024-01-01"))
        conn.commit(); conn.close()

        store = SqliteStorage(filepath=db_path, crypto=crypto)
        store.load_all()
        assert store.get_decrypted_password("id2") == "mysecret"


# ── Integridad HMAC ───────────────────────────────────────────────────────────

class TestHMACIntegrity:
    def test_tampered_db_raises_runtime_error(self, db_path, crypto):
        store = SqliteStorage(filepath=db_path, crypto=crypto)
        a = make_account(password="secret")
        store.save(a)

        # Modificar el alias directamente en SQLite sin actualizar el HMAC
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE accounts SET alias='TAMPERED' WHERE id=?", (a.id,))
        conn.commit(); conn.close()

        fresh = SqliteStorage(filepath=db_path, crypto=crypto)
        with pytest.raises(RuntimeError, match="ntegridad"):
            fresh.load_all()

    def test_tampered_db_raises_on_find_by_id(self, db_path, crypto):
        store = SqliteStorage(filepath=db_path, crypto=crypto)
        a = make_account(password="secret")
        store.save(a)

        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE accounts SET alias='TAMPERED' WHERE id=?", (a.id,))
        conn.commit(); conn.close()

        fresh = SqliteStorage(filepath=db_path, crypto=crypto)
        with pytest.raises(RuntimeError, match="ntegridad"):
            fresh.find_by_id(a.id)

    def test_no_hmac_without_crypto(self, db_path):
        store = SqliteStorage(filepath=db_path, crypto=None)
        store.save(make_account())
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM meta WHERE key='hmac'").fetchone()
        conn.close()
        assert row is None

    def test_hmac_written_after_save(self, db_path, crypto):
        store = SqliteStorage(filepath=db_path, crypto=crypto)
        store.save(make_account())
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT value FROM meta WHERE key='hmac'").fetchone()
        conn.close()
        assert row is not None and len(row[0]) == 64   # SHA-256 hex


# ── rekey ─────────────────────────────────────────────────────────────────────

class TestRekey:
    def test_rekey_passwords_decryptable_with_new_key(self, db_path, crypto, tmp_path):
        from app.core.crypto_service import CryptoService

        store = SqliteStorage(filepath=db_path, crypto=crypto)
        a = make_account(password="original_pass")
        store.save(a)

        old_fernet      = crypto._fernet
        old_signing_key = crypto._signing_key

        new_crypto = CryptoService(key_file=str(tmp_path / "master2.key"))
        new_crypto.setup("NewPass999!")
        new_crypto.unlock("NewPass999!")

        store.rekey(old_fernet, old_signing_key, new_crypto)

        fresh = SqliteStorage(filepath=db_path, crypto=new_crypto)
        assert fresh.get_decrypted_password(a.id) == "original_pass"

    def test_rekey_nonexistent_db_does_not_raise(self, tmp_path, crypto):
        from app.core.crypto_service import CryptoService

        filepath = str(tmp_path / "missing.db")
        store = SqliteStorage(filepath=filepath, crypto=crypto)

        new_crypto = CryptoService(key_file=str(tmp_path / "k2.key"))
        new_crypto.setup("x")
        new_crypto.unlock("x")

        store.rekey(crypto._fernet, crypto._signing_key, new_crypto)

    def test_rekey_tampered_hmac_raises(self, db_path, crypto, tmp_path):
        from app.core.crypto_service import CryptoService

        store = SqliteStorage(filepath=db_path, crypto=crypto)
        a = make_account(password="secret")
        store.save(a)

        # Corromper el HMAC almacenado
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE meta SET value='deadbeef' * 16 WHERE key='hmac'")
        conn.commit(); conn.close()

        new_crypto = CryptoService(key_file=str(tmp_path / "k2.key"))
        new_crypto.setup("x"); new_crypto.unlock("x")

        with pytest.raises(RuntimeError):
            store.rekey(crypto._fernet, crypto._signing_key, new_crypto)


# ── Migración desde JSON ──────────────────────────────────────────────────────

class TestMigrateFromJson:
    def _write_json(self, path, accounts: list[dict]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "accounts": accounts}, f)

    def test_migrate_imports_accounts(self, store, tmp_path):
        json_path = str(tmp_path / "accounts.json")
        self._write_json(json_path, [
            {"id": "a1", "alias": "Alice", "username": "alice", "password": "p1",
             "region": "EUW", "tags": ["ranked"], "notes": "",
             "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00"},
            {"id": "a2", "alias": "Bob",   "username": "bob",   "password": "p2",
             "region": "NA",  "tags": [],         "notes": "note",
             "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00"},
        ])

        n = store.migrate_from_json(json_path)
        assert n == 2
        accounts = store.load_all()
        aliases = {a.alias for a in accounts}
        assert aliases == {"Alice", "Bob"}

    def test_migrate_preserves_tags(self, store, tmp_path):
        json_path = str(tmp_path / "accounts.json")
        self._write_json(json_path, [
            {"id": "a3", "alias": "X", "username": "u", "password": "p",
             "region": "EUW", "tags": ["ranked", "smurf"], "notes": "",
             "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00"},
        ])
        store.migrate_from_json(json_path)
        a = store.find_by_id("a3")
        assert sorted(a.tags) == ["ranked", "smurf"]

    def test_migrate_skips_duplicates(self, store, tmp_path):
        json_path = str(tmp_path / "accounts.json")
        self._write_json(json_path, [
            {"id": "dup", "alias": "X", "username": "u", "password": "p",
             "region": "EUW", "tags": [], "notes": "",
             "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00"},
        ])
        store.migrate_from_json(json_path)
        n2 = store.migrate_from_json(json_path)  # run again
        assert n2 == 0
        assert len(store.load_all()) == 1

    def test_migrate_nonexistent_file_returns_zero(self, store, tmp_path):
        n = store.migrate_from_json(str(tmp_path / "missing.json"))
        assert n == 0

    def test_migrate_invalid_json_returns_zero(self, store, tmp_path):
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("NOT JSON")
        n = store.migrate_from_json(bad)
        assert n == 0
