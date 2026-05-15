"""
tests/test_advanced_search.py – Tests para el motor de búsqueda avanzada (P2-07).
Cubre: parse_query, fuzzy_match / _levenshtein, matches_advanced,
filter_accounts y la integración con AccountService.search_filtered.
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.core.advanced_search import (
    parse_query,
    has_operators,
    fuzzy_match,
    matches_advanced,
    filter_accounts,
    _levenshtein,
)


# ── parse_query ───────────────────────────────────────────────────────────────

class TestParseQuery:

    def test_empty_returns_all_none(self):
        r = parse_query("")
        assert r["alias"] is None
        assert r["region"] is None
        assert r["tag"] is None
        assert r["before"] is None
        assert r["free_text"] == ""

    def test_plain_text_is_free_text(self):
        r = parse_query("main smurf")
        assert r["free_text"] == "main smurf"
        assert r["alias"] is None

    def test_alias_operator(self):
        r = parse_query("alias:Main")
        assert r["alias"] == "Main"
        assert r["free_text"] == ""

    def test_region_operator(self):
        r = parse_query("region:EUW")
        assert r["region"] == "EUW"

    def test_tag_operator(self):
        r = parse_query("tag:ranked")
        assert r["tag"] == "ranked"

    def test_before_operator(self):
        r = parse_query("before:2024-01-01")
        assert r["before"] == "2024-01-01"

    def test_multiple_operators(self):
        r = parse_query("alias:main tag:ranked region:EUW")
        assert r["alias"] == "main"
        assert r["tag"] == "ranked"
        assert r["region"] == "EUW"
        assert r["free_text"] == ""

    def test_operator_plus_free_text(self):
        r = parse_query("smurf tag:ranked")
        assert r["tag"] == "ranked"
        assert r["free_text"] == "smurf"

    def test_case_insensitive_operators(self):
        r = parse_query("ALIAS:main REGION:euw")
        assert r["alias"] == "main"
        assert r["region"] == "euw"

    def test_free_text_stripped(self):
        r = parse_query("  main  ")
        assert r["free_text"] == "main"


class TestHasOperators:

    def test_with_operator(self):
        assert has_operators("alias:main") is True

    def test_without_operator(self):
        assert has_operators("just text") is False

    def test_empty(self):
        assert has_operators("") is False


# ── _levenshtein ──────────────────────────────────────────────────────────────

class TestLevenshtein:

    def test_equal_strings(self):
        assert _levenshtein("abc", "abc") == 0

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0

    def test_empty_and_nonempty(self):
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3

    def test_one_substitution(self):
        assert _levenshtein("cat", "bat") == 1

    def test_one_insertion(self):
        assert _levenshtein("abc", "abcd") == 1

    def test_one_deletion(self):
        assert _levenshtein("abcd", "abc") == 1

    def test_transposition_two_edits(self):
        # Levenshtein counts transposition as 2 (not Damerau-Levenshtein)
        assert _levenshtein("ab", "ba") == 2

    def test_completely_different(self):
        assert _levenshtein("hello", "world") == 4


# ── fuzzy_match ───────────────────────────────────────────────────────────────

class TestFuzzyMatch:

    def test_exact_substring(self):
        assert fuzzy_match("main", "main_account") is True

    def test_empty_query_matches_all(self):
        assert fuzzy_match("", "anything") is True

    def test_no_match(self):
        assert fuzzy_match("xyz", "hello") is False

    # Short words (≤3) — no fuzzy, only substring
    def test_short_word_exact_match(self):
        assert fuzzy_match("euw", "EUW account") is True

    def test_short_word_no_fuzzy(self):
        # "ewu" ≠ "euw" substring; len=3 → no fuzzy → False
        assert fuzzy_match("ewu", "euw account") is False

    # 4-6 chars — allow distance 1
    def test_medium_typo_one_edit(self):
        # "smurf" → "smruf" is distance 2, not 1. Use "smurf" → "smurl"? Let me pick a real example:
        # "rank" → "rnk" is distance 1 (deletion)
        assert fuzzy_match("rank", "rnk tagged") is True

    def test_medium_no_match(self):
        # "smurf" len=5 → max_dist=1; "xyzwv" has dist 5 from smurf
        assert fuzzy_match("smurf", "xyzwv account") is False

    # 7+ chars — allow distance 2
    def test_long_typo_two_edits(self):
        # "rankedd" (7 chars) vs "ranked" → distance 1 → match
        assert fuzzy_match("rankedd", "ranked player") is True

    def test_case_insensitive(self):
        assert fuzzy_match("Main", "main account") is True

    def test_multi_word_target(self):
        # match against any word in target
        assert fuzzy_match("main", "primary main account") is True


# ── matches_advanced ──────────────────────────────────────────────────────────

class TestMatchesAdvanced:
    """Uses real Account objects."""

    @pytest.fixture
    def account(self):
        from app.core.account import Account
        return Account(
            alias="Main EUW",
            username="player123",
            password="x",
            region="EUW",
            tags=["ranked", "main"],
        )

    def test_empty_free_text_matches_all(self, account):
        assert matches_advanced("", account) is True

    def test_match_on_alias(self, account):
        assert matches_advanced("main", account) is True

    def test_match_on_username(self, account):
        assert matches_advanced("player", account) is True

    def test_match_on_tag(self, account):
        assert matches_advanced("ranked", account) is True

    def test_no_match(self, account):
        assert matches_advanced("totally_unrelated_xyz", account) is False

    def test_multi_token_all_must_match(self, account):
        assert matches_advanced("main ranked", account) is True

    def test_multi_token_partial_miss(self, account):
        assert matches_advanced("main nonexistent", account) is False

    def test_fuzzy_typo_in_alias(self, account):
        # "Mian" → dist 2 from "Main" (len=4 → max_dist=1); let's try "Maen" dist 1
        assert matches_advanced("Maen", account) is True


# ── filter_accounts ───────────────────────────────────────────────────────────

class TestFilterAccounts:

    @pytest.fixture
    def accounts(self):
        from app.core.account import Account
        from datetime import datetime, timezone
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        return [
            Account(alias="Main EUW",   username="u1", password="x", region="EUW",
                    tags=["ranked"], created_at=old_date, updated_at=old_date),
            Account(alias="Smurf NA",   username="u2", password="x", region="NA",
                    tags=["smurf"]),
            Account(alias="Alt EUNE",   username="u3", password="x", region="EUNE",
                    tags=["ranked", "alt"]),
        ]

    def test_empty_query_returns_all(self, accounts):
        assert filter_accounts(accounts, "") == accounts

    def test_alias_operator(self, accounts):
        result = filter_accounts(accounts, "alias:Main")
        assert len(result) == 1
        assert result[0].alias == "Main EUW"

    def test_region_operator(self, accounts):
        result = filter_accounts(accounts, "region:NA")
        assert len(result) == 1
        assert result[0].alias == "Smurf NA"

    def test_tag_operator(self, accounts):
        result = filter_accounts(accounts, "tag:ranked")
        assert len(result) == 2

    def test_before_operator(self, accounts):
        # Only "Main EUW" was created 400 days ago
        cutoff = (datetime.now(timezone.utc) - timedelta(days=300)).strftime("%Y-%m-%d")
        result = filter_accounts(accounts, f"before:{cutoff}")
        assert len(result) == 1
        assert result[0].alias == "Main EUW"

    def test_before_invalid_date_ignored(self, accounts):
        result = filter_accounts(accounts, "before:not-a-date")
        assert len(result) == 3  # filter silently ignored

    def test_free_text_fuzzy(self, accounts):
        result = filter_accounts(accounts, "smurf")
        assert any(a.alias == "Smurf NA" for a in result)

    def test_operator_plus_free_text(self, accounts):
        result = filter_accounts(accounts, "tag:ranked alt")
        assert len(result) == 1
        assert result[0].alias == "Alt EUNE"

    def test_no_match_returns_empty(self, accounts):
        assert filter_accounts(accounts, "alias:nonexistent") == []


# ── AccountService.search_filtered integration ────────────────────────────────

class TestSearchFilteredAdvanced:

    @pytest.fixture
    def svc(self, tmp_path, crypto):
        from app.storage.sqlite_storage import SqliteStorage
        from app.core.account_service import AccountService
        storage = SqliteStorage(filepath=str(tmp_path / "test.db"), crypto=crypto)
        svc = AccountService(storage)
        svc.create(alias="Main EUW",  username="u1", password="Pass1!", region="EUW",  tags=["ranked"])
        svc.create(alias="Smurf NA",  username="u2", password="Pass2!", region="NA",   tags=["smurf"])
        svc.create(alias="Alt EUNE",  username="u3", password="Pass3!", region="EUNE", tags=["ranked", "alt"])
        return svc

    def test_alias_operator(self, svc):
        result = svc.search_filtered(query="alias:Smurf")
        assert len(result) == 1
        assert result[0].alias == "Smurf NA"

    def test_region_operator_overrides_ui(self, svc):
        # region: operator should take precedence — but UI region also works if op absent
        result = svc.search_filtered(query="region:NA")
        assert len(result) == 1

    def test_tag_operator(self, svc):
        result = svc.search_filtered(query="tag:ranked")
        assert len(result) == 2

    def test_fuzzy_free_text(self, svc):
        # "Maen" should fuzzy-match "Main EUW"
        result = svc.search_filtered(query="Maen")
        assert any(a.alias == "Main EUW" for a in result)

    def test_ui_region_filter_without_operator(self, svc):
        result = svc.search_filtered(query="", region="EUNE")
        assert len(result) == 1
        assert result[0].alias == "Alt EUNE"

    def test_ui_tag_filter_still_works(self, svc):
        result = svc.search_filtered(query="", tags=["smurf"])
        assert len(result) == 1
        assert result[0].alias == "Smurf NA"

    def test_empty_query_returns_all(self, svc):
        assert len(svc.search_filtered()) == 3


# ── SettingsService.recent_searches ──────────────────────────────────────────

class TestRecentSearches:

    @pytest.fixture
    def settings(self, tmp_path):
        from app.core.settings_service import SettingsService
        return SettingsService(filepath=str(tmp_path / "settings.json"))

    def test_initially_empty(self, settings):
        assert settings.recent_searches == []

    def test_add_search(self, settings):
        settings.add_recent_search("main")
        assert settings.recent_searches == ["main"]

    def test_most_recent_first(self, settings):
        settings.add_recent_search("first")
        settings.add_recent_search("second")
        assert settings.recent_searches[0] == "second"

    def test_no_duplicates(self, settings):
        settings.add_recent_search("main")
        settings.add_recent_search("other")
        settings.add_recent_search("main")
        searches = settings.recent_searches
        assert searches.count("main") == 1
        assert searches[0] == "main"

    def test_empty_query_ignored(self, settings):
        settings.add_recent_search("  ")
        assert settings.recent_searches == []

    def test_max_entries_enforced(self, settings):
        for i in range(15):
            settings.add_recent_search(f"query{i}")
        assert len(settings.recent_searches) == 10

    def test_clear_recent_searches(self, settings):
        settings.add_recent_search("main")
        settings.clear_recent_searches()
        assert settings.recent_searches == []
