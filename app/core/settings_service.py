"""Persistencia de preferencias del usuario en settings.json."""

import json
import os
from typing import Any

from app.config import DATA_DIR, SETTINGS_FILE
from app.core.event_bus import EventBus

_DEFAULTS: dict[str, Any] = {
    "theme":                   "Dark",   # "Dark" | "Light" | "System"
    "inactivity_timeout_min":  10,       # 0 = desactivado
}


class SettingsService:
    """Lee y escribe settings.json. Los cambios se emiten via EventBus."""

    def __init__(self, filepath: str = SETTINGS_FILE):
        self._filepath = filepath
        self._data: dict[str, Any] = {}
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load()

    def get(self, key: str) -> Any:
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()
        EventBus.instance().emit("settings.changed", key=key, value=value)

    @property
    def theme(self) -> str:
        return self.get("theme")

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("theme", value)

    @property
    def inactivity_timeout_min(self) -> int:
        return int(self.get("inactivity_timeout_min"))

    @inactivity_timeout_min.setter
    def inactivity_timeout_min(self, value: int) -> None:
        self.set("inactivity_timeout_min", int(value))

    @property
    def inactivity_timeout_ms(self) -> int:
        """Milisegundos para usar con after(). 0 = desactivado."""
        return self.inactivity_timeout_min * 60 * 1000

    @property
    def last_unlock_at(self) -> str | None:
        return self.get("last_unlock_at")

    @last_unlock_at.setter
    def last_unlock_at(self, value: str | None) -> None:
        self._data["last_unlock_at"] = value
        self._save()

    @property
    def previous_unlock_at(self) -> str | None:
        return self.get("previous_unlock_at")

    @previous_unlock_at.setter
    def previous_unlock_at(self, value: str | None) -> None:
        self._data["previous_unlock_at"] = value
        self._save()

    @property
    def riot_api_key(self) -> str:
        return self.get("riot_api_key") or ""

    @riot_api_key.setter
    def riot_api_key(self, value: str) -> None:
        self._data["riot_api_key"] = value.strip()
        self._save()

    @property
    def launcher_path(self) -> str:
        return self.get("launcher_path") or ""

    @launcher_path.setter
    def launcher_path(self, value: str) -> None:
        self._data["launcher_path"] = value.strip()
        self._save()

    @property
    def recent_searches(self) -> list[str]:
        return self.get("recent_searches") or []

    def add_recent_search(self, query: str, max_entries: int = 10) -> None:
        """Añade la búsqueda al historial, manteniendo orden y sin duplicados."""
        query = query.strip()
        if not query:
            return
        searches = [q for q in self.recent_searches if q != query]
        searches.insert(0, query)
        self._data["recent_searches"] = searches[:max_entries]
        self._save()

    def clear_recent_searches(self) -> None:
        self._data["recent_searches"] = []
        self._save()

    def _load(self) -> None:
        if not os.path.exists(self._filepath):
            self._data = dict(_DEFAULTS)
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self._data = {**_DEFAULTS, **loaded}
        except Exception:
            self._data = dict(_DEFAULTS)

    def _save(self) -> None:
        tmp = self._filepath + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self._filepath)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
