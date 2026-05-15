"""Registro singleton de hooks activos y ejecución ordenada de sus métodos."""

from __future__ import annotations
import logging
from typing import Any

from app.hooks.base_hook import BaseHook

logger = logging.getLogger(__name__)


class HooksRegistry:
    """Registro singleton de hooks activos."""

    _instance: "HooksRegistry | None" = None

    def __init__(self):
        self._hooks: list[BaseHook] = []

    @classmethod
    def instance(cls) -> "HooksRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register(self, hook: BaseHook) -> None:
        """Registra un hook. Si ya existe uno con el mismo name, lo reemplaza."""
        self._hooks = [h for h in self._hooks if h.name != hook.name]
        self._hooks.append(hook)
        logger.info(f"HooksRegistry: registrado hook '{hook.name}'")

    def unregister(self, name: str) -> None:
        """Elimina el hook con ese nombre."""
        self._hooks = [h for h in self._hooks if h.name != name]

    def list_hooks(self) -> list[str]:
        """Devuelve los nombres de los hooks activos."""
        return [h.name for h in self._hooks]

    def run(self, method: str, **kwargs) -> Any:
        """Ejecuta el método en todos los hooks; cada uno puede transformar el primer kwarg."""
        if not kwargs:
            return None

        key   = next(iter(kwargs))
        value = kwargs[key]

        for hook in self._hooks:
            fn = getattr(hook, method, None)
            if fn is None:
                continue
            try:
                kwargs[key] = value
                result = fn(**kwargs)
                if result is not None:
                    value = result
            except Exception as e:
                logger.error(f"HooksRegistry: error en '{hook.name}.{method}': {e}")
                raise

        return value

    def can(self, method: str, **kwargs) -> bool:
        """Devuelve True solo si ningún hook cancela la operación devolviendo False."""
        for hook in self._hooks:
            fn = getattr(hook, method, None)
            if fn is None:
                continue
            try:
                result = fn(**kwargs)
                if result is False:
                    logger.info(
                        f"HooksRegistry: '{hook.name}.{method}' canceló la operación"
                    )
                    return False
            except Exception as e:
                logger.error(f"HooksRegistry: error en '{hook.name}.{method}': {e}")
                raise
        return True

    def fire(self, method: str, **kwargs) -> None:
        """Ejecuta el método en todos los hooks sin transformar valores (after_*)."""
        for hook in self._hooks:
            fn = getattr(hook, method, None)
            if fn is None:
                continue
            try:
                fn(**kwargs)
            except Exception as e:
                logger.error(f"HooksRegistry: error en '{hook.name}.{method}': {e}")
