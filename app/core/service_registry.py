"""Registro central de servicios (DI container) de la aplicación."""

from __future__ import annotations
from typing import Type, TypeVar

T = TypeVar("T")


class ServiceRegistry:
    """
    Registro singleton de servicios de la aplicación.
    Se construye una vez al arrancar y persiste durante toda la sesión.
    """

    _instance: "ServiceRegistry | None" = None

    def __init__(self):
        self._services: dict[type, object] = {}

        self.crypto:   object = None
        self.storage:  object = None
        self.service:  object = None
        self.settings: object = None

    @classmethod
    def instance(cls) -> "ServiceRegistry":
        if cls._instance is None:
            raise RuntimeError("ServiceRegistry no inicializado. Llama a build() primero.")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def build(self) -> "ServiceRegistry":
        """Construye e inicializa todos los servicios en el orden correcto."""
        import os
        from app.core.crypto_service    import CryptoService
        from app.core.account_service   import AccountService
        from app.core.settings_service  import SettingsService
        from app.core.event_bus         import EventBus
        from app.hooks.hooks_registry   import HooksRegistry

        self.settings = SettingsService()
        self._register(self.settings)

        self.crypto = CryptoService()
        self._register(self.crypto)

        from app.storage.sqlite_storage import SqliteStorage
        from app.config import ACCOUNTS_FILE, SQLITE_FILE
        import shutil, sqlite3 as _sqlite3, logging as _logging

        self.storage = SqliteStorage(filepath=SQLITE_FILE, crypto=self.crypto)
        self._register(self.storage)

        _log = _logging.getLogger(__name__)
        try:
            _db_empty = True
            if os.path.exists(SQLITE_FILE):
                _c = _sqlite3.connect(SQLITE_FILE)
                _db_empty = _c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
                _c.close()
            if _db_empty and os.path.exists(ACCOUNTS_FILE):
                n = self.storage.migrate_from_json(ACCOUNTS_FILE)
                if n > 0:
                    shutil.move(ACCOUNTS_FILE, ACCOUNTS_FILE + ".migrated")
                    _log.info("Migradas %d cuentas de JSON a SQLite.", n)
        except Exception as _e:
            _log.warning("Auto-migración JSON→SQLite fallida (no crítico): %s", _e)

        from app.core.password_history_service import PasswordHistoryService
        self.history_service = PasswordHistoryService(self.storage, self.crypto)
        self._register(self.history_service)

        self.service = AccountService(self.storage, history_service=self.history_service)
        self._register(self.service)

        from app.core.riot_api_service import RiotApiService
        self.riot_service = RiotApiService(self.storage, api_key=self.settings.riot_api_key)
        self._register(self.riot_service)

        from app.core.launcher_service import LauncherService
        self.launcher_service = LauncherService(settings=self.settings)
        self._register(self.launcher_service)

        EventBus.instance()
        HooksRegistry.instance()

        ServiceRegistry._instance = self
        return self

    def get(self, service_type: Type[T]) -> T:
        """Obtiene un servicio por su tipo; lanza KeyError si no está registrado."""
        if service_type not in self._services:
            raise KeyError(
                f"Servicio '{service_type.__name__}' no registrado. "
                f"Registrados: {[t.__name__ for t in self._services]}"
            )
        return self._services[service_type]

    def _register(self, instance: object) -> None:
        """Registra una instancia por su tipo y sus tipos base."""
        self._services[type(instance)] = instance
        for base in type(instance).__mro__[1:]:
            if base not in (object,) and base not in self._services:
                self._services[base] = instance

    def register_extra(self, instance: object) -> None:
        """Registra un servicio adicional tras el build inicial."""
        self._register(instance)
