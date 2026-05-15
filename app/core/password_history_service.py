"""Historial cifrado de contraseñas anteriores por cuenta."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.sqlite_storage import SqliteStorage

logger = logging.getLogger(__name__)

_FERNET_PREFIX = "gAAAAA"

MAX_HISTORY = 10


class PasswordHistoryService:

    def __init__(self, storage: "SqliteStorage", crypto) -> None:
        self._storage = storage
        self._crypto  = crypto

    def push(self, account_id: str, plaintext: str) -> None:
        """Cifra y almacena la contraseña en el historial, recortando a MAX_HISTORY."""
        if not plaintext:
            return
        encrypted = self._encrypt(plaintext)
        self._storage.push_password_history(account_id, encrypted)
        self._storage.trim_password_history(account_id, MAX_HISTORY)
        logger.debug("Historial actualizado para account_id=%s", account_id)

    def get_history(self, account_id: str) -> list[dict]:
        """Devuelve las contraseñas anteriores descifradas, más reciente primero."""
        rows = self._storage.get_password_history(account_id, limit=MAX_HISTORY)
        result = []
        for row in rows:
            pw = self._decrypt(row["password"])
            result.append({"changed_at": row["changed_at"], "password": pw})
        return result

    def is_reuse(self, account_id: str, new_plaintext: str) -> bool:
        """True si new_plaintext coincide con alguna entrada del historial."""
        history = self.get_history(account_id)
        return any(h["password"] == new_plaintext for h in history)

    def delete_for_account(self, account_id: str) -> None:
        """Elimina todo el historial de una cuenta (llamar al borrar la cuenta)."""
        self._storage.delete_password_history(account_id)

    def _encrypt(self, plaintext: str) -> str:
        if self._crypto and self._crypto.is_unlocked:
            return self._crypto.encrypt(plaintext)
        return plaintext

    def _decrypt(self, value: str) -> str:
        if self._crypto and self._crypto.is_unlocked and value.startswith(_FERNET_PREFIX):
            try:
                return self._crypto.decrypt(value)
            except Exception:
                return "—"
        return value
