"""Contrato abstracto (Repository) para cualquier backend de almacenamiento."""

from abc import ABC, abstractmethod
from typing import Optional

from app.core.account import Account

class BaseStorage(ABC):
    """Interfaz que deben implementar todos los backends de almacenamiento."""

    @abstractmethod
    def load_all(self) -> list[Account]:
        """Devuelve todas las cuentas almacenadas."""
        ...

    @abstractmethod
    def save(self, account: Account) -> Account:
        """Persiste una cuenta nueva; lanza ValueError si el id ya existe."""
        ...

    @abstractmethod
    def update(self, account: Account) -> Account:
        """Actualiza una cuenta existente; lanza ValueError si no existe."""
        ...

    @abstractmethod
    def delete(self, account_id: str) -> bool:
        """Elimina la cuenta; devuelve True si existía."""
        ...

    @abstractmethod
    def find_by_id(self, account_id: str) -> Optional[Account]:
        """Devuelve la cuenta con el id dado, o None si no existe."""
        ...

    @abstractmethod
    def get_decrypted_password(self, account_id: str) -> str:
        """Descifra y devuelve la contraseña como valor temporal; devuelve "" si falla."""
        ...

    @abstractmethod
    def rekey(self, old_fernet, old_signing_key: bytes, new_crypto) -> None:
        """Re-cifra todas las contraseñas con la nueva clave tras cambio de contraseña maestra."""
        ...