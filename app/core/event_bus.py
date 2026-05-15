"""Bus de eventos pub/sub para comunicación desacoplada entre componentes."""

from __future__ import annotations
from collections import defaultdict
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Bus de eventos global (singleton).
    Thread-safe para uso básico en UI single-thread (tkinter).
    """

    _instance: "EventBus | None" = None

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def subscribe(self, event: str, callback: Callable) -> None:
        """Suscribe un callback a un evento."""
        if callback not in self._subscribers[event]:
            self._subscribers[event].append(callback)
            logger.debug(f"EventBus: suscrito a '{event}' → {callback.__name__}")

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """Elimina la suscripción de un callback a un evento."""
        if callback in self._subscribers[event]:
            self._subscribers[event].remove(callback)

    def emit(self, event: str, **payload) -> None:
        """Emite un evento a todos los callbacks suscritos."""
        callbacks = self._subscribers.get(event, [])
        logger.debug(f"EventBus: emitiendo '{event}' → {len(callbacks)} suscriptores")

        for cb in callbacks[:]:
            try:
                cb(**payload)
            except Exception as e:
                logger.error(f"EventBus: error en callback '{cb.__name__}' para '{event}': {e}")

    def clear(self, event: str | None = None) -> None:
        """
        Elimina todas las suscripciones de un evento,
        o todas las suscripciones si event es None.
        """
        if event:
            self._subscribers.pop(event, None)
        else:
            self._subscribers.clear()

    def list_events(self) -> list[str]:
        """Devuelve la lista de eventos con suscriptores activos."""
        return [e for e, cbs in self._subscribers.items() if cbs]
