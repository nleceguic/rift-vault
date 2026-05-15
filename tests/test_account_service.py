"""
test_account_service.py – Tests de la capa de lógica de negocio.

Cubre: CRUD, validaciones, search_filtered, hooks y get_all_tags.
"""

import pytest

from app.core.account import Account, NOTES_MAX_CHARS
from app.hooks.base_hook import BaseHook
from app.hooks.hooks_registry import HooksRegistry


# ── Hooks auxiliares ──────────────────────────────────────────────────────────

class RecordingHook(BaseHook):
    name = "recording"

    def __init__(self):
        self.events: list[str] = []

    def before_account_create(self, data: dict) -> dict:
        self.events.append("before_create")
        return data

    def after_account_create(self, account: Account) -> None:
        self.events.append("after_create")

    def after_account_update(self, account: Account) -> None:
        self.events.append("after_update")

    def after_account_delete(self, account_id: str) -> None:
        self.events.append("after_delete")


class CancelDeleteHook(BaseHook):
    name = "cancel_delete"

    def before_account_delete(self, account_id: str) -> bool:
        return False


class UppercaseAliasHook(BaseHook):
    name = "uppercase_alias"

    def before_account_create(self, data: dict) -> dict:
        return {**data, "alias": data["alias"].upper()}


# ── create ────────────────────────────────────────────────────────────────────

class TestCreate:
    def test_returns_account_with_id(self, service, sample_data):
        a = service.create(**sample_data)
        assert a.id
        assert a.alias == "Main EUW"

    def test_normalizes_alias_whitespace(self, service):
        a = service.create(alias="  Trimmed  ", username="u", password="p")
        assert a.alias == "Trimmed"

    def test_normalizes_region_to_uppercase(self, service):
        a = service.create(alias="X", username="u", password="p", region="euw")
        assert a.region == "EUW"

    def test_tags_stored_correctly(self, service):
        a = service.create(alias="X", username="u", password="p", tags=["ranked", "smurf"])
        assert sorted(a.tags) == ["ranked", "smurf"]

    def test_empty_alias_raises(self, service):
        with pytest.raises(ValueError, match="alias"):
            service.create(alias="", username="u", password="p")

    def test_whitespace_alias_raises(self, service):
        with pytest.raises(ValueError, match="alias"):
            service.create(alias="   ", username="u", password="p")

    def test_alias_too_long_raises(self, service):
        with pytest.raises(ValueError):
            service.create(alias="A" * 51, username="u", password="p")

    def test_empty_username_raises(self, service):
        with pytest.raises(ValueError, match="username"):
            service.create(alias="X", username="", password="p")

    def test_username_too_long_raises(self, service):
        with pytest.raises(ValueError):
            service.create(alias="X", username="U" * 51, password="p")

    def test_empty_password_raises(self, service):
        with pytest.raises(ValueError, match="contraseña"):
            service.create(alias="X", username="u", password="")

    def test_invalid_region_raises(self, service):
        with pytest.raises(ValueError, match="egión"):
            service.create(alias="X", username="u", password="p", region="MARS")

    def test_notes_too_long_raises(self, service):
        with pytest.raises(ValueError):
            service.create(alias="X", username="u", password="p", notes="N" * (NOTES_MAX_CHARS + 1))

    def test_notes_at_max_length_is_valid(self, service):
        a = service.create(alias="X", username="u", password="p", notes="N" * NOTES_MAX_CHARS)
        assert len(a.notes) == NOTES_MAX_CHARS


# ── get_all ───────────────────────────────────────────────────────────────────

class TestGetAll:
    def test_empty_initially(self, service):
        assert service.get_all() == []

    def test_returns_all_created(self, service):
        service.create(alias="A", username="u1", password="p")
        service.create(alias="B", username="u2", password="p")
        assert len(service.get_all()) == 2

    def test_sorted_by_alias_case_insensitive(self, service):
        service.create(alias="zebra", username="u1", password="p")
        service.create(alias="Alpha", username="u2", password="p")
        accounts = service.get_all()
        assert accounts[0].alias == "Alpha"
        assert accounts[1].alias == "zebra"


# ── find_by_id ────────────────────────────────────────────────────────────────

class TestFindById:
    def test_finds_existing_account(self, service):
        a = service.create(alias="X", username="u", password="p")
        found = service.find_by_id(a.id)
        assert found is not None
        assert found.id == a.id

    def test_returns_none_for_unknown_id(self, service):
        assert service.find_by_id("ghost-id") is None


# ── search ────────────────────────────────────────────────────────────────────

class TestSearch:
    @pytest.fixture(autouse=True)
    def setup_accounts(self, service):
        self.s = service
        self.s.create(alias="Alpha", username="user1", password="p", tags=["ranked"])
        self.s.create(alias="Beta",  username="user2", password="p", tags=["smurf"], notes="spare account")

    def test_empty_query_returns_all(self):
        assert len(self.s.search("")) == 2

    def test_search_by_alias(self):
        results = self.s.search("Alpha")
        assert len(results) == 1 and results[0].alias == "Alpha"

    def test_search_by_username(self):
        results = self.s.search("user2")
        assert len(results) == 1

    def test_search_by_tag(self):
        results = self.s.search("smurf")
        assert len(results) == 1 and results[0].alias == "Beta"

    def test_search_by_notes(self):
        results = self.s.search("spare")
        assert len(results) == 1

    def test_search_no_match_returns_empty(self):
        assert self.s.search("xyznoexist") == []


# ── search_filtered ───────────────────────────────────────────────────────────

class TestSearchFiltered:
    @pytest.fixture(autouse=True)
    def setup_accounts(self, service):
        self.s = service
        self.s.create(alias="Zebra", username="u1", password="p", region="EUW", tags=["ranked"])
        self.s.create(alias="Alpha", username="u2", password="p", region="NA",  tags=["smurf"])

    def test_filter_by_region(self):
        results = self.s.search_filtered(region="NA")
        assert len(results) == 1 and results[0].alias == "Alpha"

    def test_filter_by_tag(self):
        results = self.s.search_filtered(tags=["ranked"])
        assert len(results) == 1 and results[0].alias == "Zebra"

    def test_filter_all_region_returns_all(self):
        assert len(self.s.search_filtered(region="Todas")) == 2

    def test_sort_alias_asc(self):
        results = self.s.search_filtered(sort="alias_asc")
        assert results[0].alias == "Alpha"

    def test_sort_alias_desc(self):
        results = self.s.search_filtered(sort="alias_desc")
        assert results[0].alias == "Zebra"

    def test_combined_query_and_region(self):
        results = self.s.search_filtered(query="Zebra", region="EUW")
        assert len(results) == 1


# ── get_all_tags ──────────────────────────────────────────────────────────────

class TestGetAllTags:
    def test_empty_when_no_accounts(self, service):
        assert service.get_all_tags() == []

    def test_returns_unique_sorted_tags(self, service):
        service.create(alias="A", username="u1", password="p", tags=["smurf", "ranked"])
        service.create(alias="B", username="u2", password="p", tags=["ranked", "main"])
        tags = service.get_all_tags()
        assert tags == sorted(set(tags))
        assert "ranked" in tags
        assert tags.count("ranked") == 1


# ── update ────────────────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_alias(self, service):
        a = service.create(alias="Old", username="u", password="p")
        service.update(a, alias="New")
        assert service.find_by_id(a.id).alias == "New"

    def test_update_notes(self, service):
        a = service.create(alias="X", username="u", password="p")
        service.update(a, notes="hello")
        assert service.find_by_id(a.id).notes == "hello"

    def test_update_tags(self, service):
        a = service.create(alias="X", username="u", password="p")
        service.update(a, tags=["new_tag"])
        assert "new_tag" in service.find_by_id(a.id).tags

    def test_update_without_password_keeps_existing(self, service, storage):
        a = service.create(alias="X", username="u", password="original")
        service.update(a, alias="Y")
        assert storage.get_decrypted_password(a.id) == "original"

    def test_update_notes_too_long_raises(self, service):
        a = service.create(alias="X", username="u", password="p")
        with pytest.raises(ValueError):
            service.update(a, notes="N" * (NOTES_MAX_CHARS + 1))


# ── delete ────────────────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_existing_returns_true(self, service):
        a = service.create(alias="X", username="u", password="p")
        assert service.delete(a.id)

    def test_delete_removes_account(self, service):
        a = service.create(alias="X", username="u", password="p")
        service.delete(a.id)
        assert service.find_by_id(a.id) is None

    def test_delete_nonexistent_returns_false(self, service):
        assert not service.delete("ghost-id")


# ── Integración con hooks ─────────────────────────────────────────────────────

class TestHookIntegration:
    def test_before_after_create_hooks_fired(self, service):
        hook = RecordingHook()
        HooksRegistry.instance().register(hook)
        service.create(alias="X", username="u", password="p")
        assert "before_create" in hook.events
        assert "after_create" in hook.events

    def test_hook_can_transform_data_before_create(self, service):
        HooksRegistry.instance().register(UppercaseAliasHook())
        a = service.create(alias="lowercase", username="u", password="p")
        assert a.alias == "LOWERCASE"

    def test_cancel_delete_hook_prevents_deletion(self, service):
        HooksRegistry.instance().register(CancelDeleteHook())
        a = service.create(alias="X", username="u", password="p")
        result = service.delete(a.id)
        assert not result
        assert service.find_by_id(a.id) is not None

    def test_after_delete_hook_fired(self, service):
        hook = RecordingHook()
        HooksRegistry.instance().register(hook)
        a = service.create(alias="X", username="u", password="p")
        service.delete(a.id)
        assert "after_delete" in hook.events
