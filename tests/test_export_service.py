"""
test_export_service.py – Tests de ExportService (export/import JSON).
"""

import json
import pytest

from app.core.export_service import ExportService, ExportError


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def export_svc(service, crypto):
    return ExportService(service, crypto)


@pytest.fixture
def populated_service(service):
    service.create(alias="Main EUW",  username="user1", password="pass1", region="EUW", tags=["main"])
    service.create(alias="Smurf NA",  username="user2", password="pass2", region="NA",  tags=["smurf"])
    service.create(alias="ARAM Only", username="user3", password="pass3", region="EUW", notes="aram")
    return service


# ── Export ────────────────────────────────────────────────────────────────────

class TestExportJson:

    def test_creates_valid_json_file(self, populated_service, crypto, tmp_path):
        svc      = ExportService(populated_service, crypto)
        filepath = str(tmp_path / "backup.json")
        count    = svc.export_json(filepath)
        assert count == 3

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert data["app"] == "Rift Vault"
        assert "exported_at" in data
        assert len(data["accounts"]) == 3

    def test_exported_accounts_have_required_fields(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "backup.json")
        svc.export_json(path)

        with open(path, encoding="utf-8") as f:
            entries = json.load(f)["accounts"]

        for entry in entries:
            assert "alias" in entry
            assert "username" in entry
            assert "password_encrypted" in entry
            assert "region" in entry
            assert "tags" in entry

    def test_passwords_exported_as_fernet_tokens(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "backup.json")
        svc.export_json(path)

        with open(path, encoding="utf-8") as f:
            entries = json.load(f)["accounts"]

        for entry in entries:
            token = entry["password_encrypted"]
            assert token.startswith("gAAAAA"), "debe ser token Fernet válido"

    def test_exported_tokens_are_decryptable(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "backup.json")
        svc.export_json(path)

        with open(path, encoding="utf-8") as f:
            entries = json.load(f)["accounts"]

        # Cada token debe poderse descifrar con la misma clave
        for entry in entries:
            plaintext = crypto.decrypt(entry["password_encrypted"])
            assert isinstance(plaintext, str)
            assert len(plaintext) > 0

    def test_empty_vault_exports_zero(self, service, crypto, tmp_path):
        svc  = ExportService(service, crypto)
        path = str(tmp_path / "backup.json")
        count = svc.export_json(path)
        assert count == 0

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["accounts"] == []

    def test_export_to_bad_path_raises_export_error(self, service, crypto):
        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="No se pudo escribir"):
            svc.export_json("/nonexistent_dir/file.json")


# ── Import ────────────────────────────────────────────────────────────────────

class TestImportJson:

    def _make_backup(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "backup.json")
        svc.export_json(path)
        return path

    def test_round_trip(self, populated_service, crypto, tmp_path):
        path = self._make_backup(populated_service, crypto, tmp_path)

        # Nuevo storage vacío en la misma instalación (misma clave)
        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_storage = JsonStorage(filepath=str(tmp_path / "new.json"), crypto=crypto)
        new_service = AccountService(new_storage)

        svc = ExportService(new_service, crypto)
        imported, skipped = svc.import_json(path)

        assert imported == 3
        assert skipped  == 0
        assert len(new_service.get_all()) == 3

    def test_duplicate_alias_username_is_skipped(self, populated_service, crypto, tmp_path):
        path = self._make_backup(populated_service, crypto, tmp_path)

        # Importar al mismo servicio — todos son duplicados
        svc = ExportService(populated_service, crypto)
        imported, skipped = svc.import_json(path)

        assert imported == 0
        assert skipped  == 3

    def test_partial_duplicates_skipped(self, populated_service, crypto, tmp_path):
        path = self._make_backup(populated_service, crypto, tmp_path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_storage = JsonStorage(filepath=str(tmp_path / "partial.json"), crypto=crypto)
        new_service = AccountService(new_storage)
        # Pre-cargar una de las tres cuentas
        new_service.create(alias="Main EUW", username="user1", password="xxx", region="EUW")

        svc = ExportService(new_service, crypto)
        imported, skipped = svc.import_json(path)

        assert imported == 2
        assert skipped  == 1

    def test_decrypted_passwords_are_preserved(self, populated_service, crypto, tmp_path):
        path = self._make_backup(populated_service, crypto, tmp_path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_storage = JsonStorage(filepath=str(tmp_path / "new2.json"), crypto=crypto)
        new_service = AccountService(new_storage)

        svc = ExportService(new_service, crypto)
        svc.import_json(path)

        # Las contraseñas originales deben poderse recuperar tras la importación
        expected = {"user1": "pass1", "user2": "pass2", "user3": "pass3"}
        for account in new_service.get_all():
            pw = new_service.get_decrypted_password(account.id)
            assert pw == expected[account.username]

    def test_wrong_key_raises_export_error(self, populated_service, crypto, tmp_path):
        path = self._make_backup(populated_service, crypto, tmp_path)

        # Crypto con clave diferente
        from app.core.crypto_service import CryptoService
        other_crypto = CryptoService(key_file=str(tmp_path / "other.key"))
        other_crypto.setup("OtherPass456!")
        other_crypto.unlock("OtherPass456!")

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        other_storage = JsonStorage(filepath=str(tmp_path / "other.json"), crypto=other_crypto)
        other_service = AccountService(other_storage)

        svc = ExportService(other_service, other_crypto)
        with pytest.raises(ExportError, match="contraseña maestra diferente"):
            svc.import_json(path)

    def test_invalid_json_raises_export_error(self, service, crypto, tmp_path):
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("not json at all {{{")

        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="No se pudo leer"):
            svc.import_json(bad)

    def test_missing_file_raises_export_error(self, service, crypto, tmp_path):
        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="No se pudo leer"):
            svc.import_json(str(tmp_path / "nonexistent.json"))

    def test_wrong_version_raises_export_error(self, service, crypto, tmp_path):
        bad = str(tmp_path / "wrong_ver.json")
        with open(bad, "w") as f:
            json.dump({"version": 99, "accounts": []}, f)

        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="no es un backup"):
            svc.import_json(bad)

    def test_missing_version_key_raises_export_error(self, service, crypto, tmp_path):
        bad = str(tmp_path / "no_ver.json")
        with open(bad, "w") as f:
            json.dump({"accounts": []}, f)

        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="no es un backup"):
            svc.import_json(bad)

    def test_entries_with_missing_fields_are_skipped(self, service, crypto, tmp_path):
        # Archivo válido pero con entradas incompletas
        bad = str(tmp_path / "incomplete.json")
        with open(bad, "w") as f:
            json.dump({
                "version": 1,
                "app": "Rift Vault",
                "exported_at": "2026-01-01T00:00:00",
                "accounts": [
                    {"alias": "ok", "username": "", "password_encrypted": ""},
                    {"alias": "", "username": "user"},
                ],
            }, f)

        svc = ExportService(service, crypto)
        imported, skipped = svc.import_json(bad)
        assert imported == 0
        assert skipped  == 2


# ── JSON v2 (contraseña personalizada) ───────────────────────────────────────

class TestJsonV2:

    EXPORT_PW = "ExportPass99!"

    def _backup_v2(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "backup_v2.json")
        svc.export_json_with_password(path, self.EXPORT_PW)
        return path

    def test_creates_valid_v2_file(self, populated_service, crypto, tmp_path):
        path = self._backup_v2(populated_service, crypto, tmp_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == 2
        assert data["encryption"] == "pbkdf2-fernet"
        assert "salt" in data
        assert len(data["accounts"]) == 3

    def test_v2_tokens_differ_from_master_key_tokens(self, populated_service, crypto, tmp_path):
        # v1
        svc   = ExportService(populated_service, crypto)
        p_v1  = str(tmp_path / "v1.json")
        p_v2  = str(tmp_path / "v2.json")
        svc.export_json(p_v1)
        svc.export_json_with_password(p_v2, self.EXPORT_PW)

        with open(p_v1) as f: v1_tokens = {e["password_encrypted"] for e in json.load(f)["accounts"]}
        with open(p_v2) as f: v2_tokens = {e["password_encrypted"] for e in json.load(f)["accounts"]}

        assert v1_tokens.isdisjoint(v2_tokens), "los tokens deben ser distintos"

    def test_v2_round_trip_same_install(self, populated_service, crypto, tmp_path):
        path = self._backup_v2(populated_service, crypto, tmp_path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_svc = AccountService(JsonStorage(str(tmp_path / "new.json"), crypto))
        svc = ExportService(new_svc, crypto)

        imported, skipped = svc.import_json_with_password(path, self.EXPORT_PW)
        assert imported == 3
        assert skipped  == 0

    def test_v2_round_trip_different_master_key(self, populated_service, crypto, tmp_path):
        """v2 debe importarse aunque la clave maestra sea diferente."""
        path = self._backup_v2(populated_service, crypto, tmp_path)

        from app.core.crypto_service import CryptoService
        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService

        other_crypto = CryptoService(str(tmp_path / "other.key"))
        other_crypto.setup("OtherMaster42!")
        other_crypto.unlock("OtherMaster42!")
        other_svc = AccountService(JsonStorage(str(tmp_path / "other.json"), other_crypto))

        svc = ExportService(other_svc, other_crypto)
        imported, skipped = svc.import_json_with_password(path, self.EXPORT_PW)
        assert imported == 3
        assert skipped  == 0

    def test_v2_wrong_export_password_raises(self, populated_service, crypto, tmp_path):
        path = self._backup_v2(populated_service, crypto, tmp_path)

        # Servicio vacío para que no haya duplicados y se intente descifrar
        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        empty_svc = AccountService(JsonStorage(str(tmp_path / "empty.json"), crypto))
        svc = ExportService(empty_svc, crypto)

        with pytest.raises(ExportError, match="incorrecta"):
            svc.import_json_with_password(path, "WrongPassword!")

    def test_v2_empty_export_password_raises(self, service, crypto):
        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="vacía"):
            svc.export_json_with_password("/tmp/x.json", "")

    def test_v2_duplicates_skipped(self, populated_service, crypto, tmp_path):
        path = self._backup_v2(populated_service, crypto, tmp_path)
        svc  = ExportService(populated_service, crypto)
        imported, skipped = svc.import_json_with_password(path, self.EXPORT_PW)
        assert imported == 0
        assert skipped  == 3

    def test_v2_passwords_preserved_after_import(self, populated_service, crypto, tmp_path):
        path = self._backup_v2(populated_service, crypto, tmp_path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_svc = AccountService(JsonStorage(str(tmp_path / "new2.json"), crypto))
        svc = ExportService(new_svc, crypto)
        svc.import_json_with_password(path, self.EXPORT_PW)

        expected = {"user1": "pass1", "user2": "pass2", "user3": "pass3"}
        for account in new_svc.get_all():
            assert new_svc.get_decrypted_password(account.id) == expected[account.username]


# ── CSV ───────────────────────────────────────────────────────────────────────

class TestCsv:

    def test_export_creates_csv(self, populated_service, crypto, tmp_path):
        import csv as csv_mod
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "export.csv")
        count = svc.export_csv(path)
        assert count == 3

        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv_mod.reader(f))

        assert rows[0] == ["alias", "username", "password", "region",
                            "tags", "notes", "created_at", "updated_at"]
        assert len(rows) == 4  # header + 3 accounts

    def test_export_csv_passwords_are_plaintext(self, populated_service, crypto, tmp_path):
        import csv as csv_mod
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "exp.csv")
        svc.export_csv(path)

        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv_mod.reader(f))

        passwords = {row[2] for row in rows[1:]}
        assert "pass1" in passwords
        assert "pass2" in passwords
        assert "pass3" in passwords

    def test_import_csv_round_trip(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "exp.csv")
        svc.export_csv(path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_svc = AccountService(JsonStorage(str(tmp_path / "new.json"), crypto))
        new_exp = ExportService(new_svc, crypto)

        imported, skipped = new_exp.import_csv(path)
        assert imported == 3
        assert skipped  == 0
        assert len(new_svc.get_all()) == 3

    def test_import_csv_passwords_preserved(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "exp.csv")
        svc.export_csv(path)

        from app.storage.json_storage import JsonStorage
        from app.core.account_service import AccountService
        new_svc = AccountService(JsonStorage(str(tmp_path / "new2.json"), crypto))
        ExportService(new_svc, crypto).import_csv(path)

        expected = {"user1": "pass1", "user2": "pass2", "user3": "pass3"}
        for account in new_svc.get_all():
            assert new_svc.get_decrypted_password(account.id) == expected[account.username]

    def test_import_csv_duplicates_skipped(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "exp.csv")
        svc.export_csv(path)

        imported, skipped = svc.import_csv(path)
        assert imported == 0
        assert skipped  == 3

    def test_import_csv_missing_headers_raises(self, service, crypto, tmp_path):
        import csv as csv_mod
        bad = str(tmp_path / "bad.csv")
        with open(bad, "w", newline="", encoding="utf-8") as f:
            w = csv_mod.writer(f)
            w.writerow(["foo", "bar", "baz"])
            w.writerow(["x", "y", "z"])

        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="columnas reconocidas"):
            svc.import_csv(bad)

    def test_import_csv_rows_without_password_skipped(self, service, crypto, tmp_path):
        import csv as csv_mod
        path = str(tmp_path / "nopw.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv_mod.writer(f)
            w.writerow(["alias", "username", "password", "region"])
            w.writerow(["Alice", "alice", "",     "EUW"])
            w.writerow(["Bob",   "bob",   "pw123", "NA"])

        svc = ExportService(service, crypto)
        imported, skipped = svc.import_csv(path)
        assert imported == 1   # Bob
        assert skipped  == 1   # Alice (sin contraseña)


# ── probe_file ────────────────────────────────────────────────────────────────

class TestProbeFile:

    def test_probe_json_v1(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "v1.json")
        svc.export_json(path)

        info = svc.probe_file(path)
        assert info["format"]           == "json_v1"
        assert info["account_count"]    == 3
        assert info["encrypted_custom"] is False

    def test_probe_json_v2(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "v2.json")
        svc.export_json_with_password(path, "pw")

        info = svc.probe_file(path)
        assert info["format"]           == "json_v2"
        assert info["account_count"]    == 3
        assert info["encrypted_custom"] is True

    def test_probe_csv(self, populated_service, crypto, tmp_path):
        svc  = ExportService(populated_service, crypto)
        path = str(tmp_path / "exp.csv")
        svc.export_csv(path)

        info = svc.probe_file(path)
        assert info["format"]        == "csv"
        assert info["account_count"] == 3
        assert "alias"    in info["csv_mapping"]
        assert "username" in info["csv_mapping"]
        assert "password" in info["csv_mapping"]

    def test_probe_invalid_json_raises(self, service, crypto, tmp_path):
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("{invalid}")
        svc = ExportService(service, crypto)
        with pytest.raises(ExportError):
            svc.probe_file(bad)

    def test_probe_unknown_json_raises(self, service, crypto, tmp_path):
        bad = str(tmp_path / "unk.json")
        with open(bad, "w") as f:
            json.dump({"version": 99}, f)
        svc = ExportService(service, crypto)
        with pytest.raises(ExportError, match="no es un backup"):
            svc.probe_file(bad)
