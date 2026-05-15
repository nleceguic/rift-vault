"""Implementación de BaseStorage usando SQLite con cifrado Fernet e integridad HMAC."""

import dataclasses
import hashlib
import hmac as _hmac_mod
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.config import DATA_DIR, SQLITE_FILE
from app.core.account import Account
from app.storage.base_storage import BaseStorage

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_FERNET_PREFIX  = "gAAAAA"


def _is_fernet_token(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_FERNET_PREFIX)


class SqliteStorage(BaseStorage):
    """Almacena cuentas en una base de datos SQLite local con cifrado opcional."""

    def __init__(self, filepath: str = SQLITE_FILE, crypto=None):
        self._filepath = filepath
        self._crypto   = crypto
        os.makedirs(DATA_DIR, exist_ok=True)
        self._init_db()

    def load_all(self) -> list[Account]:
        with self._connect() as conn:
            self._verify_hmac(conn)
            rows = conn.execute(
                "SELECT id, alias, username, password, region, tags, notes, "
                "created_at, updated_at FROM accounts"
            ).fetchall()

            migrated = False
            accounts: list[Account] = []
            for row in rows:
                password = row["password"]
                if self._crypto and self._crypto.is_unlocked and not _is_fernet_token(password):
                    try:
                        password = self._crypto.encrypt(password)
                        conn.execute(
                            "UPDATE accounts SET password=? WHERE id=?",
                            (password, row["id"])
                        )
                        migrated = True
                    except Exception:
                        password = ""

                accounts.append(Account(
                    id=row["id"], alias=row["alias"], username=row["username"],
                    password=password, region=row["region"],
                    tags=json.loads(row["tags"]), notes=row["notes"],
                    riot_id=row["riot_id"] if "riot_id" in row.keys() else "",
                    created_at=row["created_at"], updated_at=row["updated_at"],
                ))

            if migrated:
                self._write_hmac(conn)

        return accounts

    def save(self, account: Account) -> Account:
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM accounts WHERE id=?", (account.id,)).fetchone():
                raise ValueError(f"Ya existe una cuenta con id={account.id!r}")

            password = account.password
            if self._crypto and self._crypto.is_unlocked:
                password = self._crypto.encrypt(account.password)
                account = dataclasses.replace(account, password=password)

            conn.execute(
                "INSERT INTO accounts "
                "(id, alias, username, password, region, tags, notes, riot_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account.id, account.alias, account.username, password,
                 account.region, json.dumps(account.tags), account.notes,
                 account.riot_id, account.created_at, account.updated_at)
            )
            self._write_hmac(conn)

        return account

    def update(self, account: Account) -> Account:
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM accounts WHERE id=?", (account.id,)).fetchone():
                raise ValueError(f"No se encontró ninguna cuenta con id={account.id!r}")

            account = account.touch()
            password = account.password
            if self._crypto and self._crypto.is_unlocked and not _is_fernet_token(password):
                password = self._crypto.encrypt(password)
                account = dataclasses.replace(account, password=password)

            conn.execute(
                "UPDATE accounts SET alias=?, username=?, password=?, region=?, "
                "tags=?, notes=?, riot_id=?, updated_at=? WHERE id=?",
                (account.alias, account.username, password, account.region,
                 json.dumps(account.tags), account.notes, account.riot_id,
                 account.updated_at, account.id)
            )
            self._write_hmac(conn)

        return account

    def delete(self, account_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
            if cursor.rowcount > 0:
                conn.execute("DELETE FROM password_history WHERE account_id=?", (account_id,))
                conn.execute("DELETE FROM riot_cache WHERE account_id=?", (account_id,))
                self._write_hmac(conn)
                return True
        return False

    def upsert_riot_cache(self, account_id: str, data: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO riot_cache "
                "(account_id, riot_id, puuid, level, rank, status, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    account_id,
                    data.get("riot_id", ""),
                    data.get("puuid", ""),
                    data.get("level", 0),
                    data.get("rank", ""),
                    data.get("status", "unknown"),
                    data.get("cached_at", ""),
                ),
            )

    def get_riot_cache(self, account_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM riot_cache WHERE account_id=?", (account_id,)
            ).fetchone()
        return dict(row) if row else None

    def push_password_history(self, account_id: str, encrypted_password: str) -> None:
        import uuid
        from datetime import datetime, timezone
        entry_id  = str(uuid.uuid4())
        changed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO password_history (id, account_id, password, changed_at) "
                "VALUES (?, ?, ?, ?)",
                (entry_id, account_id, encrypted_password, changed_at),
            )

    def get_password_history(self, account_id: str, limit: int = 10) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, account_id, password, changed_at "
                "FROM password_history WHERE account_id=? "
                "ORDER BY changed_at DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def trim_password_history(self, account_id: str, keep: int) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM password_history WHERE account_id=? "
                "ORDER BY changed_at DESC",
                (account_id,),
            ).fetchall()
            if len(rows) > keep:
                ids_to_delete = [r["id"] for r in rows[keep:]]
                conn.execute(
                    f"DELETE FROM password_history WHERE id IN "
                    f"({','.join('?' * len(ids_to_delete))})",
                    ids_to_delete,
                )

    def delete_password_history(self, account_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM password_history WHERE account_id=?", (account_id,))

    def find_by_id(self, account_id: str) -> Optional[Account]:
        with self._connect() as conn:
            self._verify_hmac(conn)
            row = conn.execute(
                "SELECT id, alias, username, password, region, tags, notes, "
                "created_at, updated_at FROM accounts WHERE id=?",
                (account_id,)
            ).fetchone()

        if row is None:
            return None
        return Account(
            id=row["id"], alias=row["alias"], username=row["username"],
            password=row["password"], region=row["region"],
            tags=json.loads(row["tags"]), notes=row["notes"],
            riot_id=row["riot_id"] if "riot_id" in row.keys() else "",
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def get_decrypted_password(self, account_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT password FROM accounts WHERE id=?", (account_id,)
            ).fetchone()

        if row is None:
            return ""
        raw = row["password"]
        if self._crypto and self._crypto.is_unlocked and _is_fernet_token(raw):
            try:
                return self._crypto.decrypt(raw)
            except Exception:
                return ""
        return raw

    def rekey(self, old_fernet, old_signing_key: bytes, new_crypto) -> None:
        """Re-cifra todas las contraseñas al cambiar la contraseña maestra."""
        if not os.path.exists(self._filepath):
            self._crypto = new_crypto
            return

        with self._connect() as conn:
            hmac_row = conn.execute("SELECT value FROM meta WHERE key='hmac'").fetchone()
            if hmac_row and old_signing_key:
                canonical = self._canonical(conn)
                expected  = _hmac_mod.new(old_signing_key, canonical, hashlib.sha256).hexdigest()
                if not _hmac_mod.compare_digest(expected, hmac_row["value"]):
                    raise RuntimeError(
                        "No se pudo verificar la integridad de la base de datos "
                        "antes del cambio de contraseña."
                    )

            rows = conn.execute("SELECT id, password FROM accounts").fetchall()
            for row in rows:
                raw = row["password"]
                if _is_fernet_token(raw):
                    try:
                        plaintext = old_fernet.decrypt(raw.encode()).decode()
                        new_token = new_crypto.encrypt(plaintext)
                        conn.execute(
                            "UPDATE accounts SET password=? WHERE id=?",
                            (new_token, row["id"])
                        )
                    except Exception:
                        pass

            hist_rows = conn.execute("SELECT id, password FROM password_history").fetchall()
            for row in hist_rows:
                raw = row["password"]
                if _is_fernet_token(raw):
                    try:
                        plaintext = old_fernet.decrypt(raw.encode()).decode()
                        new_token = new_crypto.encrypt(plaintext)
                        conn.execute(
                            "UPDATE password_history SET password=? WHERE id=?",
                            (new_token, row["id"])
                        )
                    except Exception:
                        pass

            self._crypto = new_crypto
            self._write_hmac(conn)

    def migrate_from_json(self, json_filepath: str) -> int:
        """Importa cuentas desde un accounts.json; devuelve el número importado."""
        if not os.path.exists(json_filepath):
            return 0

        try:
            with open(json_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("migrate_from_json: error leyendo %s: %s", json_filepath, e)
            return 0

        raw_accounts = data.get("accounts", [])
        imported = 0
        with self._connect() as conn:
            for a in raw_accounts:
                if conn.execute("SELECT 1 FROM accounts WHERE id=?", (a["id"],)).fetchone():
                    continue
                conn.execute(
                    "INSERT INTO accounts "
                    "(id, alias, username, password, region, tags, notes, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        a["id"], a["alias"], a["username"], a["password"],
                        a.get("region", "EUW"),
                        json.dumps(a.get("tags", [])),
                        a.get("notes", ""),
                        a.get("created_at", ""),
                        a.get("updated_at", ""),
                    )
                )
                imported += 1

            if imported > 0:
                self._write_hmac(conn)

        logger.info("migrate_from_json: importadas %d cuentas de %s", imported, json_filepath)
        return imported

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id         TEXT PRIMARY KEY,
                    alias      TEXT NOT NULL,
                    username   TEXT NOT NULL,
                    password   TEXT NOT NULL,
                    region     TEXT NOT NULL DEFAULT 'EUW',
                    tags       TEXT NOT NULL DEFAULT '[]',
                    notes      TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS password_history (
                    id         TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    password   TEXT NOT NULL,
                    changed_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ph_account "
                "ON password_history (account_id, changed_at DESC)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS riot_cache (
                    account_id  TEXT PRIMARY KEY,
                    riot_id     TEXT NOT NULL DEFAULT '',
                    puuid       TEXT NOT NULL DEFAULT '',
                    level       INTEGER NOT NULL DEFAULT 0,
                    rank        TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'unknown',
                    cached_at   TEXT NOT NULL DEFAULT ''
                )
            """)
            try:
                conn.execute("ALTER TABLE accounts ADD COLUMN riot_id TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # Column already exists
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(_SCHEMA_VERSION),)
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alias      ON accounts (alias COLLATE NOCASE)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_region     ON accounts (region)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON accounts (updated_at)")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._filepath, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _canonical(self, conn) -> bytes:
        """Representación determinista de todas las cuentas para HMAC."""
        rows = conn.execute(
            "SELECT id, alias, username, password, region, tags, notes, riot_id, created_at, updated_at "
            "FROM accounts ORDER BY id"
        ).fetchall()
        payload = {
            "accounts": [
                {
                    "alias":      r["alias"],
                    "created_at": r["created_at"],
                    "id":         r["id"],
                    "notes":      r["notes"],
                    "password":   r["password"],
                    "region":     r["region"],
                    "riot_id":    r["riot_id"] if "riot_id" in r.keys() else "",
                    "tags":       json.loads(r["tags"]),
                    "updated_at": r["updated_at"],
                    "username":   r["username"],
                }
                for r in rows
            ]
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    def _write_hmac(self, conn) -> None:
        if not (self._crypto and self._crypto.is_unlocked):
            conn.execute("DELETE FROM meta WHERE key='hmac'")
            return
        sig = self._crypto.sign(self._canonical(conn))
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('hmac', ?)", (sig,)
        )

    def _verify_hmac(self, conn) -> None:
        if not (self._crypto and self._crypto.is_unlocked):
            return
        row = conn.execute("SELECT value FROM meta WHERE key='hmac'").fetchone()
        if row is None:
            return
        if not self._crypto.verify_signature(self._canonical(conn), row["value"]):
            raise RuntimeError(
                "Integridad comprometida: la base de datos fue modificada externamente."
            )
