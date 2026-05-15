"""
tests/test_password_history_service.py – Tests para PasswordHistoryService
y su integración con AccountService (reuse guard + auto-push).
"""

import pytest

from app.core.password_history_service import PasswordHistoryService, MAX_HISTORY


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_storage(tmp_path, crypto):
    from app.storage.sqlite_storage import SqliteStorage
    return SqliteStorage(filepath=str(tmp_path / "test.db"), crypto=crypto)


@pytest.fixture
def history_service(sqlite_storage, crypto):
    return PasswordHistoryService(sqlite_storage, crypto)


@pytest.fixture
def svc(sqlite_storage, history_service):
    from app.core.account_service import AccountService
    return AccountService(sqlite_storage, history_service=history_service)


@pytest.fixture
def account(svc):
    return svc.create(alias="Test", username="user1", password="InitialPass1!")


# ── PasswordHistoryService.push / get_history ─────────────────────────────────

class TestPushAndGet:

    def test_push_stores_entry(self, history_service, account):
        history_service.push(account.id, "OldPass1!")
        history = history_service.get_history(account.id)
        assert len(history) == 1
        assert history[0]["password"] == "OldPass1!"

    def test_get_returns_most_recent_first(self, history_service, account):
        history_service.push(account.id, "First!")
        history_service.push(account.id, "Second!")
        history = history_service.get_history(account.id)
        assert history[0]["password"] == "Second!"
        assert history[1]["password"] == "First!"

    def test_push_empty_password_ignored(self, history_service, account):
        history_service.push(account.id, "")
        assert history_service.get_history(account.id) == []

    def test_each_entry_has_changed_at(self, history_service, account):
        history_service.push(account.id, "AnyPass1!")
        entry = history_service.get_history(account.id)[0]
        assert "changed_at" in entry
        assert entry["changed_at"]

    def test_passwords_are_stored_encrypted(self, sqlite_storage, history_service, account):
        history_service.push(account.id, "SecretPass1!")
        raw_rows = sqlite_storage.get_password_history(account.id)
        # Raw value must be a Fernet token, not plaintext
        assert raw_rows[0]["password"].startswith("gAAAAA")

    def test_get_history_empty_for_new_account(self, history_service, account):
        assert history_service.get_history(account.id) == []

    def test_get_history_only_for_own_account(self, sqlite_storage, history_service, svc):
        a1 = svc.create(alias="A1", username="u1", password="PassA1!")
        a2 = svc.create(alias="A2", username="u2", password="PassA2!")
        history_service.push(a1.id, "OldA1!")
        assert history_service.get_history(a2.id) == []


# ── MAX_HISTORY trim ──────────────────────────────────────────────────────────

class TestTrim:

    def test_trim_keeps_max_history(self, history_service, account):
        for i in range(MAX_HISTORY + 3):
            history_service.push(account.id, f"Pass{i}!")
        history = history_service.get_history(account.id)
        assert len(history) == MAX_HISTORY

    def test_trim_keeps_most_recent(self, history_service, account):
        for i in range(MAX_HISTORY + 2):
            history_service.push(account.id, f"Pass{i}!")
        history = history_service.get_history(account.id)
        # Most recent is the last one pushed (MAX_HISTORY + 1)
        assert history[0]["password"] == f"Pass{MAX_HISTORY + 1}!"


# ── is_reuse ──────────────────────────────────────────────────────────────────

class TestIsReuse:

    def test_reuse_detected(self, history_service, account):
        history_service.push(account.id, "ReusedPass1!")
        assert history_service.is_reuse(account.id, "ReusedPass1!") is True

    def test_different_password_not_reuse(self, history_service, account):
        history_service.push(account.id, "OldPass1!")
        assert history_service.is_reuse(account.id, "NewPass1!") is False

    def test_no_history_not_reuse(self, history_service, account):
        assert history_service.is_reuse(account.id, "AnyPass1!") is False

    def test_reuse_case_sensitive(self, history_service, account):
        history_service.push(account.id, "CaseSensitive!")
        assert history_service.is_reuse(account.id, "casesensitive!") is False


# ── delete_for_account ────────────────────────────────────────────────────────

class TestDeleteForAccount:

    def test_delete_clears_history(self, history_service, account):
        history_service.push(account.id, "OldPass1!")
        history_service.delete_for_account(account.id)
        assert history_service.get_history(account.id) == []

    def test_delete_nonexistent_account_no_error(self, history_service):
        history_service.delete_for_account("nonexistent-id")  # should not raise


# ── AccountService integration ────────────────────────────────────────────────

class TestAccountServiceIntegration:

    def test_password_pushed_to_history_on_update(self, svc, history_service, account):
        svc.update(account, password="NewPass2!")
        history = history_service.get_history(account.id)
        assert len(history) == 1
        assert history[0]["password"] == "InitialPass1!"

    def test_reuse_raises_value_error(self, svc, history_service, account):
        svc.update(account, password="NewPass2!")
        updated = svc.find_by_id(account.id)
        with pytest.raises(ValueError, match="recientemente"):
            svc.update(updated, password="InitialPass1!")

    def test_no_history_push_when_password_unchanged(self, svc, history_service, account):
        svc.update(account, alias="New Alias")
        assert history_service.get_history(account.id) == []

    def test_multiple_password_changes_build_history(self, svc, history_service, account):
        svc.update(account, password="Pass2!")
        updated1 = svc.find_by_id(account.id)
        svc.update(updated1, password="Pass3!")
        history = history_service.get_history(account.id)
        assert len(history) == 2
        passwords = {h["password"] for h in history}
        assert "InitialPass1!" in passwords
        assert "Pass2!" in passwords

    def test_delete_account_clears_history(self, svc, history_service, account):
        history_service.push(account.id, "OldPass!")
        svc.delete(account.id)
        assert history_service.get_history(account.id) == []

    def test_no_history_service_update_works_normally(self, sqlite_storage, account):
        from app.core.account_service import AccountService
        svc_no_hist = AccountService(sqlite_storage)
        # Should update without errors (no reuse check, no history push)
        updated = svc_no_hist.update(account, password="NewPassNoHist!")
        assert svc_no_hist.get_decrypted_password(updated.id) == "NewPassNoHist!"
