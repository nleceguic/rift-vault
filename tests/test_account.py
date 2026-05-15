"""
test_account.py – Tests del modelo de dominio Account.
No usa I/O ni singletons — pure unit tests.
"""

import dataclasses

import pytest
from datetime import datetime, timezone

from app.core.account import Account, VALID_REGIONS, NOTES_MAX_CHARS


# ── Creación y defaults ───────────────────────────────────────────────────────

class TestDefaults:
    def test_id_is_uuid4(self):
        a = Account(alias="X", username="u", password="p")
        assert a.id
        assert len(a.id) == 36
        assert a.id.count("-") == 4

    def test_created_at_is_valid_iso(self):
        a = Account(alias="X", username="u", password="p")
        dt = datetime.fromisoformat(a.created_at)
        assert dt.tzinfo is not None

    def test_default_region(self):
        assert Account(alias="X", username="u", password="p").region == "EUW"

    def test_default_tags_empty_list(self):
        a = Account(alias="X", username="u", password="p")
        assert a.tags == []

    def test_default_notes_empty_string(self):
        a = Account(alias="X", username="u", password="p").notes == ""

    def test_different_accounts_have_unique_ids(self):
        ids = {Account(alias="X", username="u", password="p").id for _ in range(10)}
        assert len(ids) == 10


# ── Serialización ─────────────────────────────────────────────────────────────

class TestSerialization:
    EXPECTED_KEYS = {"id", "alias", "username", "password", "region", "tags", "notes", "created_at", "updated_at", "riot_id"}

    def test_to_dict_has_all_keys(self):
        a = Account(alias="M", username="u", password="p")
        assert set(a.to_dict().keys()) == self.EXPECTED_KEYS

    def test_to_dict_values_match(self):
        a = Account(alias="Main", username="user", password="pass", region="NA", tags=["ranked"], notes="note")
        d = a.to_dict()
        assert d["alias"]    == "Main"
        assert d["username"] == "user"
        assert d["password"] == "pass"
        assert d["region"]   == "NA"
        assert d["tags"]     == ["ranked"]
        assert d["notes"]    == "note"

    def test_from_dict_round_trip(self):
        original = Account(alias="Main", username="user", password="pass",
                           region="KR", tags=["ranked", "smurf"], notes="hello")
        copy = Account.from_dict(original.to_dict())
        assert copy.id         == original.id
        assert copy.alias      == original.alias
        assert copy.username   == original.username
        assert copy.password   == original.password
        assert copy.region     == original.region
        assert copy.tags       == original.tags
        assert copy.notes      == original.notes
        assert copy.created_at == original.created_at

    def test_from_dict_missing_optional_fields_use_defaults(self):
        minimal = {"id": "abc", "alias": "X", "username": "u", "password": "p"}
        a = Account.from_dict(minimal)
        assert a.region == "EUW"
        assert a.tags   == []
        assert a.notes  == ""


# ── Búsqueda ──────────────────────────────────────────────────────────────────

class TestMatchesSearch:
    @pytest.fixture(autouse=True)
    def account(self):
        self.a = Account(
            alias="Main Account", username="playerOne",
            password="p", region="EUW",
            tags=["ranked", "main"], notes="My favorite account"
        )

    def test_empty_query_always_matches(self):
        assert self.a.matches_search("")

    def test_matches_alias_partial(self):
        assert self.a.matches_search("main")

    def test_matches_username_case_insensitive(self):
        assert self.a.matches_search("playerone")

    def test_matches_notes(self):
        assert self.a.matches_search("favorite")

    def test_matches_tag(self):
        assert self.a.matches_search("ranked")

    def test_no_match_returns_false(self):
        assert not self.a.matches_search("xyz_no_match")

    def test_case_insensitive_alias(self):
        assert self.a.matches_search("MAIN ACCOUNT")


# ── touch() ───────────────────────────────────────────────────────────────────

class TestTouch:
    def test_touch_updates_updated_at(self):
        a = dataclasses.replace(
            Account(alias="X", username="u", password="p"),
            updated_at="2000-01-01T00:00:00+00:00",
        )
        a2 = a.touch()
        assert a2.updated_at != "2000-01-01T00:00:00+00:00"
        datetime.fromisoformat(a2.updated_at)

    def test_touch_preserves_created_at(self):
        a = Account(alias="X", username="u", password="p")
        original = a.created_at
        a2 = a.touch()
        assert a2.created_at == original

    def test_touch_returns_new_instance(self):
        a = Account(alias="X", username="u", password="p")
        a2 = a.touch()
        assert a2 is not a


# ── Constantes ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_euw_in_valid_regions(self):
        assert "EUW" in VALID_REGIONS

    def test_notes_max_chars_is_500(self):
        assert NOTES_MAX_CHARS == 500

    def test_valid_regions_count(self):
        assert len(VALID_REGIONS) == 11
