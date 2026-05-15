"""Interfaz abstracta para hooks de extensión de AccountService y sesión."""

from abc import ABC
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.account import Account


class BaseHook(ABC):
    """Clase base para hooks; sobrescribir solo los métodos de interés."""

    name: str = "base_hook"

    def before_account_create(self, data: dict) -> dict:
        return data

    def after_account_create(self, account: "Account") -> None:
        pass

    def before_account_update(self, account: "Account", changes: dict) -> dict:
        return changes

    def after_account_update(self, account: "Account") -> None:
        pass

    def before_account_delete(self, account_id: str) -> bool:
        """Devuelve False para cancelar la eliminación."""
        return True

    def after_account_delete(self, account_id: str) -> None:
        pass

    def after_unlock(self) -> None:
        pass

    def before_lock(self) -> None:
        pass

    def after_copy(self, field: str, alias: str) -> None:
        pass
