"""Implementación de BaseStorage usando un archivo JSON local con cifrado Fernet."""

import dataclasses
import hashlib
import hmac as _hmac_mod
import json
import os
import shutil
from typing import Optional

from app.config import DATA_DIR, ACCOUNTS_FILE
from app.core.account import Account
from app.storage.base_storage import BaseStorage

_FILE_VERSION  = 1
_FERNET_PREFIX = "gAAAAA"


def _is_fernet_token(value: str) -> bool:
    """Devuelve True si el valor parece un token Fernet válido."""
    return isinstance(value, str) and value.startswith(_FERNET_PREFIX)


class JsonStorage(BaseStorage):
    """Almacena cuentas en JSON local con cifrado opcional."""

    def __init__(self, filepath: str = ACCOUNTS_FILE, crypto=None):
        self._filepath = filepath
        self._crypto   = crypto
        self._ensure_data_dir()

    def load_all(self) -> list[Account]:
        data     = self._read()
        accounts = []
        migrated = False

        for a in data.get("accounts", []):
            password_raw = a["password"]

            if self._crypto and self._crypto.is_unlocked:
                if _is_fernet_token(password_raw):
                    pass
                else:
                    try:
                        a["password"] = self._crypto.encrypt(password_raw)
                        migrated = True
                    except Exception:
                        a["password"] = ""

            accounts.append(Account.from_dict(a))

        if migrated and self._crypto and self._crypto.is_unlocked:
            self._migrate_plaintext(data)

        return accounts

    def save(self, account: Account) -> Account:
        data     = self._read()
        accounts = data.get("accounts", [])

        if any(a["id"] == account.id for a in accounts):
            raise ValueError(f"Ya existe una cuenta con id={account.id!r}")

        account_dict = account.to_dict()
        if self._crypto and self._crypto.is_unlocked:
            encrypted = self._crypto.encrypt(account.password)
            account_dict["password"] = encrypted
            account = dataclasses.replace(account, password=encrypted)

        accounts.append(account_dict)
        data["accounts"] = accounts
        self._write(data)
        return account

    def update(self, account: Account) -> Account:
        data     = self._read()
        accounts = data.get("accounts", [])

        for idx, a in enumerate(accounts):
            if a["id"] == account.id:
                account = account.touch()
                account_dict = account.to_dict()
                if self._crypto and self._crypto.is_unlocked:
                    if _is_fernet_token(account.password):
                        account_dict["password"] = account.password
                    else:
                        encrypted = self._crypto.encrypt(account.password)
                        account_dict["password"] = encrypted
                        account = dataclasses.replace(account, password=encrypted)
                accounts[idx] = account_dict
                data["accounts"] = accounts
                self._write(data)
                return account

        raise ValueError(f"No se encontró ninguna cuenta con id={account.id!r}")

    def delete(self, account_id: str) -> bool:
        data     = self._read()
        accounts = data.get("accounts", [])
        original = len(accounts)

        data["accounts"] = [a for a in accounts if a["id"] != account_id]
        if len(data["accounts"]) < original:
            self._write(data)
            return True
        return False

    def find_by_id(self, account_id: str) -> Optional[Account]:
        data = self._read()
        for a in data.get("accounts", []):
            if a["id"] == account_id:
                return Account.from_dict(a)
        return None

    def get_decrypted_password(self, account_id: str) -> str:
        data = self._read()
        for a in data.get("accounts", []):
            if a["id"] == account_id:
                raw = a.get("password", "")
                if self._crypto and self._crypto.is_unlocked and _is_fernet_token(raw):
                    try:
                        return self._crypto.decrypt(raw)
                    except Exception:
                        return ""
                return raw
        return ""

    def rekey(self, old_fernet, old_signing_key: bytes, new_crypto) -> None:
        """Re-cifra todas las contraseñas al cambiar la contraseña maestra."""
        if not os.path.exists(self._filepath):
            self._crypto = new_crypto
            return

        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"No se pudo leer el archivo de datos para rekeying: {e}") from e

        if "hmac" in data and old_signing_key:
            stored_sig = data.pop("hmac")
            canonical  = self._canonical(data)
            expected   = _hmac_mod.new(old_signing_key, canonical, hashlib.sha256).hexdigest()
            if not _hmac_mod.compare_digest(expected, stored_sig):
                raise RuntimeError(
                    "No se pudo verificar la integridad del archivo antes del cambio de contraseña."
                )
        elif "hmac" in data:
            data.pop("hmac")

        for a in data.get("accounts", []):
            raw = a.get("password", "")
            if _is_fernet_token(raw):
                try:
                    plaintext    = old_fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
                    a["password"] = new_crypto.encrypt(plaintext)
                except Exception:
                    pass

        self._crypto = new_crypto
        self._write(data)

    def _migrate_plaintext(self, data: dict) -> None:
        """Persiste el JSON con los tokens Fernet calculados en load_all()."""
        self._write(data)

    def _ensure_data_dir(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)

    def _read(self) -> dict:
        if not os.path.exists(self._filepath):
            return {"version": _FILE_VERSION, "accounts": []}
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            backup = self._filepath + ".bak"
            shutil.copy2(self._filepath, backup)
            return {"version": _FILE_VERSION, "accounts": []}

        if self._crypto and self._crypto.is_unlocked and "hmac" in data:
            stored_sig = data.pop("hmac")
            canonical  = self._canonical(data)
            if not self._crypto.verify_signature(canonical, stored_sig):
                backup = self._filepath + ".tampered"
                shutil.copy2(self._filepath, backup)
                raise RuntimeError(
                    "Integridad comprometida: el archivo de datos fue modificado externamente.\n"
                    f"Copia de seguridad guardada en accounts.json.tampered"
                )
        elif "hmac" in data:
            data.pop("hmac")   # campo presente pero crypto bloqueado; ignorar sin error

        return data

    def _write(self, data: dict) -> None:
        """Escritura atómica via .tmp + rename. Embebe HMAC de integridad."""
        payload = {k: v for k, v in data.items() if k != "hmac"}

        if self._crypto and self._crypto.is_unlocked:
            payload["hmac"] = self._crypto.sign(self._canonical(payload))

        tmp = self._filepath + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self._filepath)
        except OSError as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError(f"Error escribiendo datos: {e}") from e

    @staticmethod
    def _canonical(data: dict) -> bytes:
        """Serialización determinista para HMAC: claves ordenadas, sin espacios."""
        return json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
