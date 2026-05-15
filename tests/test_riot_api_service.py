"""tests/test_riot_api_service.py"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.riot_api_service import (
    CACHE_TTL,
    RiotApiError,
    RiotApiService,
    _format_rank,
    _parse_riot_id,
    _platform_url,
    _regional_url,
)


class _MockStorage:
    def __init__(self):
        self._cache: dict = {}

    def get_riot_cache(self, account_id):
        return self._cache.get(account_id)

    def upsert_riot_cache(self, account_id, data):
        self._cache[account_id] = data


# ── _parse_riot_id ──────────────────────────────────────────────────────────

class TestParseRiotId:
    def test_standard(self):
        assert _parse_riot_id("Faker#KR1") == ("Faker", "KR1")

    def test_strips_spaces(self):
        assert _parse_riot_id("  Name  #  TAG  ") == ("Name", "TAG")

    def test_no_hash_returns_empty_tag(self):
        assert _parse_riot_id("JustName") == ("JustName", "")

    def test_multiple_hashes_splits_on_last(self):
        assert _parse_riot_id("Name#Part1#TAG") == ("Name#Part1", "TAG")

    def test_empty_string(self):
        assert _parse_riot_id("") == ("", "")

    def test_hash_only(self):
        name, tag = _parse_riot_id("#TAG")
        assert name == ""
        assert tag == "TAG"


# ── _format_rank ────────────────────────────────────────────────────────────

class TestFormatRank:
    def test_solo_queue_wins_over_flex(self):
        entries = [
            {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD",     "rank": "II"},
            {"queueType": "RANKED_FLEX_SR",  "tier": "PLATINUM", "rank": "I"},
        ]
        assert _format_rank(entries) == "Gold II"

    def test_flex_used_when_no_solo(self):
        entries = [
            {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "III"},
        ]
        assert _format_rank(entries) == "Silver III"

    def test_master_has_no_division(self):
        entries = [
            {"queueType": "RANKED_SOLO_5x5", "tier": "MASTER", "rank": "I"},
        ]
        assert _format_rank(entries) == "Master"

    def test_grandmaster_has_no_division(self):
        entries = [
            {"queueType": "RANKED_SOLO_5x5", "tier": "GRANDMASTER", "rank": "I"},
        ]
        assert _format_rank(entries) == "Grandmaster"

    def test_challenger_has_no_division(self):
        entries = [
            {"queueType": "RANKED_SOLO_5x5", "tier": "CHALLENGER", "rank": "I"},
        ]
        assert _format_rank(entries) == "Challenger"

    def test_empty_entries_returns_empty(self):
        assert _format_rank([]) == ""

    def test_unrecognised_queue_type_returns_empty(self):
        entries = [{"queueType": "CHERRY", "tier": "GOLD", "rank": "I"}]
        assert _format_rank(entries) == ""

    def test_entry_missing_tier_returns_empty(self):
        entries = [{"queueType": "RANKED_SOLO_5x5", "rank": "I"}]
        assert _format_rank(entries) == ""


# ── URL helpers ─────────────────────────────────────────────────────────────

class TestUrlHelpers:
    def test_platform_url_euw(self):
        assert _platform_url("EUW") == "https://euw1.api.riotgames.com"

    def test_platform_url_na(self):
        assert _platform_url("NA") == "https://na1.api.riotgames.com"

    def test_platform_url_kr(self):
        assert _platform_url("KR") == "https://kr.api.riotgames.com"

    def test_regional_url_euw_is_europe(self):
        assert _regional_url("EUW") == "https://europe.api.riotgames.com"

    def test_regional_url_na_is_americas(self):
        assert _regional_url("NA") == "https://americas.api.riotgames.com"

    def test_regional_url_kr_is_asia(self):
        assert _regional_url("KR") == "https://asia.api.riotgames.com"

    def test_regional_url_oce_is_sea(self):
        assert _regional_url("OCE") == "https://sea.api.riotgames.com"

    def test_platform_url_unknown_region_defaults(self):
        url = _platform_url("UNKNOWN")
        assert "api.riotgames.com" in url

    def test_platform_url_case_insensitive(self):
        assert _platform_url("euw") == _platform_url("EUW")

    def test_regional_url_case_insensitive(self):
        assert _regional_url("euw") == _regional_url("EUW")


# ── RiotApiService — configuration ─────────────────────────────────────────

class TestIsConfigured:
    def test_empty_key_not_configured(self):
        svc = RiotApiService(_MockStorage(), api_key="")
        assert not svc.is_configured()

    def test_whitespace_only_key_not_configured(self):
        svc = RiotApiService(_MockStorage(), api_key="   ")
        assert not svc.is_configured()

    def test_valid_key_is_configured(self):
        svc = RiotApiService(_MockStorage(), api_key="RGAPI-test")
        assert svc.is_configured()

    def test_set_api_key_updates_config(self):
        svc = RiotApiService(_MockStorage())
        assert not svc.is_configured()
        svc.set_api_key("RGAPI-new")
        assert svc.is_configured()

    def test_set_api_key_strips_whitespace(self):
        svc = RiotApiService(_MockStorage())
        svc.set_api_key("  RGAPI-key  ")
        assert svc.is_configured()
        assert svc._api_key == "RGAPI-key"


# ── RiotApiService — cache ──────────────────────────────────────────────────

class TestCache:
    def test_get_cached_none_when_empty(self):
        svc = RiotApiService(_MockStorage())
        assert svc.get_cached("acc1") is None

    def test_get_cached_returns_stored_data(self):
        storage = _MockStorage()
        storage._cache["acc1"] = {"status": "active", "level": 100}
        svc = RiotApiService(storage)
        assert svc.get_cached("acc1")["level"] == 100

    def test_is_cache_fresh_no_entry(self):
        svc = RiotApiService(_MockStorage())
        assert not svc.is_cache_fresh("acc1")

    def test_is_cache_fresh_recent_entry(self):
        storage = _MockStorage()
        now = datetime.now(timezone.utc).isoformat()
        storage._cache["acc1"] = {"cached_at": now, "status": "active"}
        svc = RiotApiService(storage)
        assert svc.is_cache_fresh("acc1")

    def test_is_cache_fresh_stale_entry(self):
        storage = _MockStorage()
        old = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL + 60)).isoformat()
        storage._cache["acc1"] = {"cached_at": old, "status": "active"}
        svc = RiotApiService(storage)
        assert not svc.is_cache_fresh("acc1")

    def test_is_cache_fresh_missing_cached_at(self):
        storage = _MockStorage()
        storage._cache["acc1"] = {"status": "active"}
        svc = RiotApiService(storage)
        assert not svc.is_cache_fresh("acc1")

    def test_is_cache_fresh_boundary_just_under_ttl(self):
        storage = _MockStorage()
        just_under = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL - 5)).isoformat()
        storage._cache["acc1"] = {"cached_at": just_under}
        svc = RiotApiService(storage)
        assert svc.is_cache_fresh("acc1")

    def test_is_cache_fresh_boundary_just_over_ttl(self):
        storage = _MockStorage()
        just_over = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL + 5)).isoformat()
        storage._cache["acc1"] = {"cached_at": just_over}
        svc = RiotApiService(storage)
        assert not svc.is_cache_fresh("acc1")


# ── RiotApiService — fetch short-circuits ──────────────────────────────────

class TestFetchShortCircuits:
    def test_returns_cache_when_fresh(self):
        storage = _MockStorage()
        now = datetime.now(timezone.utc).isoformat()
        storage._cache["acc1"] = {
            "status": "active", "level": 200, "cached_at": now
        }
        svc = RiotApiService(storage, api_key="RGAPI-test")
        result = svc.fetch("acc1", "Faker#KR1", "KR")
        assert result["level"] == 200

    def test_error_when_no_api_key_and_stale(self):
        svc = RiotApiService(_MockStorage(), api_key="")
        result = svc.fetch("acc1", "Faker#KR1", "KR")
        assert result["status"] == "error"
        assert "API key" in result["message"]

    def test_error_when_empty_riot_id(self):
        svc = RiotApiService(_MockStorage(), api_key="RGAPI-key")
        result = svc.fetch("acc1", "", "EUW")
        assert result["status"] == "error"
        assert "Riot ID" in result["message"]

    def test_no_api_key_result_is_stored(self):
        storage = _MockStorage()
        svc = RiotApiService(storage, api_key="")
        svc.fetch("acc1", "Player#EUW", "EUW")
        assert storage._cache.get("acc1") is not None


# ── RiotApiService — _do_fetch via mocked requests ─────────────────────────

def _mock_resp(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code < 400:
        resp.raise_for_status.return_value = None
    else:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
    return resp


class TestDoFetch:
    def _svc(self):
        return RiotApiService(_MockStorage(), api_key="RGAPI-test")

    @patch("requests.get")
    def test_successful_fetch_returns_active(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "abc123"}),
            _mock_resp(200, {"id": "summ1", "summonerLevel": 150}),
            _mock_resp(200, [
                {"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "I"}
            ]),
        ]
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "active"
        assert result["level"] == 150
        assert result["rank"] == "Diamond I"
        assert mock_get.call_count == 3

    @patch("requests.get")
    def test_404_on_account_endpoint_returns_not_found(self, mock_get):
        mock_get.return_value = _mock_resp(404)
        result = self._svc().fetch("acc1", "Ghost#EUW", "EUW")
        assert result["status"] == "not_found"

    @patch("requests.get")
    def test_401_returns_error_with_message(self, mock_get):
        resp = MagicMock()
        resp.status_code = 401
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "error"
        assert "401" in result["message"]

    @patch("requests.get")
    def test_403_returns_error_with_message(self, mock_get):
        resp = MagicMock()
        resp.status_code = 403
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "error"
        assert "403" in result["message"]

    @patch("requests.get")
    def test_429_returns_rate_limit_error(self, mock_get):
        resp = MagicMock()
        resp.status_code = 429
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "error"
        assert "429" in result["message"]

    @patch("requests.get")
    def test_network_error_returns_error(self, mock_get):
        mock_get.side_effect = ConnectionError("timeout")
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "error"

    @patch("requests.get")
    def test_result_is_stored_in_cache(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "p1"}),
            _mock_resp(200, {"id": "s1", "summonerLevel": 42}),
            _mock_resp(200, []),
        ]
        storage = _MockStorage()
        svc = RiotApiService(storage, api_key="RGAPI-test")
        svc.fetch("acc99", "Player#EUW", "EUW")
        cached = storage._cache.get("acc99")
        assert cached is not None
        assert cached["status"] == "active"
        assert cached["level"] == 42

    @patch("requests.get")
    def test_cached_at_is_set_on_success(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "p1"}),
            _mock_resp(200, {"id": "s1", "summonerLevel": 1}),
            _mock_resp(200, []),
        ]
        storage = _MockStorage()
        svc = RiotApiService(storage, api_key="RGAPI-test")
        svc.fetch("acc1", "Player#EUW", "EUW")
        assert "cached_at" in storage._cache["acc1"]

    @patch("requests.get")
    def test_404_on_summoner_returns_not_found(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "abc"}),
            _mock_resp(404),
        ]
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["status"] == "not_found"

    @patch("requests.get")
    def test_unranked_player_has_empty_rank(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "p1"}),
            _mock_resp(200, {"id": "s1", "summonerLevel": 30}),
            _mock_resp(200, []),
        ]
        result = self._svc().fetch("acc1", "Player#EUW", "EUW")
        assert result["rank"] == ""
        assert result["level"] == 30

    @patch("requests.get")
    def test_uses_regional_url_for_first_call(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "p1"}),
            _mock_resp(200, {"id": "s1", "summonerLevel": 1}),
            _mock_resp(200, []),
        ]
        self._svc().fetch("acc1", "Player#EUW", "EUW")
        first_url = mock_get.call_args_list[0][0][0]
        assert "europe.api.riotgames.com" in first_url

    @patch("requests.get")
    def test_uses_platform_url_for_summoner_call(self, mock_get):
        mock_get.side_effect = [
            _mock_resp(200, {"puuid": "p1"}),
            _mock_resp(200, {"id": "s1", "summonerLevel": 1}),
            _mock_resp(200, []),
        ]
        self._svc().fetch("acc1", "Player#EUW", "EUW")
        second_url = mock_get.call_args_list[1][0][0]
        assert "euw1.api.riotgames.com" in second_url
