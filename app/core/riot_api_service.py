"""Integración de solo lectura con la Riot Games API con caché SQLite."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.sqlite_storage import SqliteStorage

logger = logging.getLogger(__name__)

CACHE_TTL = 300   # segundos; no re-fetch si los datos tienen menos de 5 min

_PLATFORM: dict[str, str] = {
    "EUW":  "euw1",  "EUNE": "eun1",  "NA":  "na1",
    "LAS":  "la2",   "LAN":  "la1",   "BR":  "br1",
    "OCE":  "oc1",   "KR":   "kr",    "JP":  "jp1",
    "TR":   "tr1",   "RU":   "ru",
}

_REGIONAL: dict[str, str] = {
    "EUW":  "europe",   "EUNE": "europe",  "TR":  "europe",  "RU": "europe",
    "NA":   "americas", "LAS":  "americas", "LAN": "americas", "BR": "americas",
    "KR":   "asia",     "JP":   "asia",
    "OCE":  "sea",
}

_SOLO_QUEUE = "RANKED_SOLO_5x5"
_FLEX_QUEUE = "RANKED_FLEX_SR"


def _platform_url(region: str) -> str:
    plat = _PLATFORM.get(region.upper(), "euw1")
    return f"https://{plat}.api.riotgames.com"


def _regional_url(region: str) -> str:
    reg = _REGIONAL.get(region.upper(), "europe")
    return f"https://{reg}.api.riotgames.com"


def _parse_riot_id(riot_id: str) -> tuple[str, str]:
    """Descompone 'GameName#TAG' en (game_name, tag_line)."""
    if "#" in riot_id:
        name, tag = riot_id.rsplit("#", 1)
        return name.strip(), tag.strip()
    return riot_id.strip(), ""


def _format_rank(entries: list[dict]) -> str:
    """Devuelve el rango más relevante (Solo/Duo > Flex) como texto."""
    by_queue = {e.get("queueType"): e for e in entries}
    entry = by_queue.get(_SOLO_QUEUE) or by_queue.get(_FLEX_QUEUE)
    if not entry:
        return ""
    tier = entry.get("tier", "")
    division = entry.get("rank", "")
    if tier in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        return tier.capitalize()
    return f"{tier.capitalize()} {division}" if tier else ""


class RiotApiError(Exception):
    """Error irrecuperable de la Riot API (clave inválida, etc.)."""


class RiotApiService:
    """Consulta la Riot Games API y almacena resultados en caché SQLite."""

    def __init__(self, storage: "SqliteStorage", api_key: str = "") -> None:
        self._storage = storage
        self._api_key = api_key.strip()

    def set_api_key(self, key: str) -> None:
        self._api_key = key.strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_cached(self, account_id: str) -> dict | None:
        return self._storage.get_riot_cache(account_id)

    def is_cache_fresh(self, account_id: str) -> bool:
        cached = self.get_cached(account_id)
        if not cached or not cached.get("cached_at"):
            return False
        try:
            ts = datetime.fromisoformat(cached["cached_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            return age < CACHE_TTL
        except Exception:
            return False

    def fetch(self, account_id: str, riot_id: str, region: str) -> dict:
        """Solicita datos de Riot para la cuenta; devuelve caché si está fresca."""
        if self.is_cache_fresh(account_id):
            return self.get_cached(account_id)

        if not self._api_key:
            return self._store(account_id, riot_id, {
                "status": "error",
                "message": "API key no configurada",
            })

        game_name, tag_line = _parse_riot_id(riot_id)
        if not game_name:
            return self._store(account_id, riot_id, {
                "status": "error",
                "message": "Riot ID inválido",
            })

        try:
            result = self._do_fetch(account_id, game_name, tag_line, region)
        except RiotApiError as e:
            result = {"status": "error", "message": str(e)}
        except Exception as e:
            logger.warning("Riot API fetch error for %s: %s", account_id, e)
            result = {"status": "error", "message": "Error de red o servidor"}

        return self._store(account_id, riot_id, result)

    def _do_fetch(self, account_id: str, game_name: str, tag_line: str, region: str) -> dict:
        import requests

        headers = {"X-Riot-Token": self._api_key}
        timeout = 6

        reg_base = _regional_url(region)
        resp = requests.get(
            f"{reg_base}/riot/account/v1/accounts/by-riot-id"
            f"/{requests.utils.quote(game_name)}/{requests.utils.quote(tag_line)}",
            headers=headers, timeout=timeout,
        )
        if resp.status_code == 404:
            return {"status": "not_found"}
        if resp.status_code == 401:
            raise RiotApiError("API key inválida (401)")
        if resp.status_code == 403:
            raise RiotApiError("API key expirada o sin permisos (403)")
        if resp.status_code == 429:
            return {"status": "error", "message": "Rate limit alcanzado (429)"}
        resp.raise_for_status()
        puuid = resp.json().get("puuid", "")

        plat_base = _platform_url(region)
        resp2 = requests.get(
            f"{plat_base}/lol/summoner/v4/summoners/by-puuid/{puuid}",
            headers=headers, timeout=timeout,
        )
        if resp2.status_code == 404:
            return {"status": "not_found"}
        resp2.raise_for_status()
        summoner = resp2.json()
        summoner_id = summoner.get("id", "")
        level = summoner.get("summonerLevel", 0)

        resp3 = requests.get(
            f"{plat_base}/lol/league/v4/entries/by-summoner/{summoner_id}",
            headers=headers, timeout=timeout,
        )
        resp3.raise_for_status()
        rank = _format_rank(resp3.json())

        return {
            "status": "active",
            "puuid":  puuid,
            "level":  level,
            "rank":   rank,
        }

    def _store(self, account_id: str, riot_id: str, result: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "riot_id":   riot_id,
            "puuid":     result.get("puuid", ""),
            "level":     result.get("level", 0),
            "rank":      result.get("rank", ""),
            "status":    result.get("status", "unknown"),
            "cached_at": now,
            "message":   result.get("message", ""),
        }
        self._storage.upsert_riot_cache(account_id, data)
        logger.debug("riot_cache updated: account_id=%s status=%s", account_id, data["status"])
        return data
