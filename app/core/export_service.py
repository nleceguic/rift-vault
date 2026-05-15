"""Exportación e importación de cuentas en formatos JSON v1, JSON v2 y CSV."""

import base64
import csv
import hashlib
import json
import logging
import os
import secrets as _secrets
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.account_service import AccountService
from app.core.crypto_service import CryptoService

logger = logging.getLogger(__name__)

_FMT_JSON_V1 = "json_v1"
_FMT_JSON_V2 = "json_v2"
_FMT_CSV     = "csv"

_EXPORT_ITERATIONS = 480_000
_EXPORT_SALT_BYTES = 32

_COL_ALIAS    = {"alias", "name", "nombre", "account"}
_COL_USERNAME = {"username", "user", "login", "email", "usuario"}
_COL_PASSWORD = {"password", "pass", "pwd", "contraseña", "contrasena"}
_COL_REGION   = {"region", "server", "servidor", "shard"}
_COL_TAGS     = {"tags", "tag", "labels", "label"}
_COL_NOTES    = {"notes", "note", "description", "desc", "notas", "nota"}


def _derive_export_key(password: str, salt: bytes, iterations: int = _EXPORT_ITERATIONS) -> bytes:
    raw = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=32
    )
    return base64.urlsafe_b64encode(raw)


def _detect_csv_columns(headers: list[str]) -> dict:
    """
    Mapea nombre-de-campo → índice de columna.
    Lanza ExportError si alias o username no se encuentran.
    """
    mapping: dict[str, int] = {}
    for i, h in enumerate(headers):
        h_low = h.strip().lower()
        if h_low in _COL_ALIAS    and "alias"    not in mapping: mapping["alias"]    = i
        if h_low in _COL_USERNAME and "username" not in mapping: mapping["username"] = i
        if h_low in _COL_PASSWORD and "password" not in mapping: mapping["password"] = i
        if h_low in _COL_REGION   and "region"   not in mapping: mapping["region"]   = i
        if h_low in _COL_TAGS     and "tags"      not in mapping: mapping["tags"]     = i
        if h_low in _COL_NOTES    and "notes"     not in mapping: mapping["notes"]    = i

    missing = [f for f in ("alias", "username") if f not in mapping]
    if missing:
        raise ExportError(
            f"El CSV no tiene columnas reconocidas para: {', '.join(missing)}.\n"
            f"Cabeceras encontradas: {', '.join(h.strip() for h in headers[:10])}"
        )
    return mapping


def _write_json(filepath: str, payload: dict) -> None:
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, filepath)
    except OSError as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise ExportError(f"No se pudo escribir el archivo: {e}") from e


def _load_json(filepath: str) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ExportError(f"No se pudo leer el archivo: {e}") from e


def _account_row(a, *, password_field: str) -> dict:
    return {
        "alias":              a.alias,
        "username":           a.username,
        "password_encrypted": password_field,
        "region":             a.region,
        "tags":               list(a.tags),
        "notes":              a.notes,
        "created_at":         a.created_at,
        "updated_at":         a.updated_at,
    }


class ExportError(Exception):
    pass


class ExportService:

    def __init__(self, service: AccountService, crypto: CryptoService):
        self._service = service
        self._crypto  = crypto

    def export_json(self, filepath: str) -> int:
        """JSON v1 — tokens Fernet de la clave maestra. Solo para la misma instalación."""
        accounts = self._service.get_all()
        _write_json(filepath, {
            "version":     1,
            "app":         "Rift Vault",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "accounts":    [_account_row(a, password_field=a.password) for a in accounts],
        })
        logger.info("JSON v1: exportadas %d cuentas a %s.", len(accounts), filepath)
        return len(accounts)

    def export_json_with_password(self, filepath: str, export_password: str) -> int:
        """Exporta en formato JSON v2 cifrado con contraseña personalizada."""
        if not export_password:
            raise ExportError("La contraseña de exportación no puede estar vacía.")

        accounts = self._service.get_all()
        salt     = _secrets.token_bytes(_EXPORT_SALT_BYTES)
        key      = _derive_export_key(export_password, salt)
        fernet   = Fernet(key)

        rows = []
        for a in accounts:
            plaintext = self._crypto.decrypt(a.password)
            token     = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
            rows.append(_account_row(a, password_field=token))

        _write_json(filepath, {
            "version":     2,
            "app":         "Rift Vault",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "encryption":  "pbkdf2-fernet",
            "salt":        salt.hex(),
            "iterations":  _EXPORT_ITERATIONS,
            "accounts":    rows,
        })
        logger.info("JSON v2: exportadas %d cuentas a %s.", len(accounts), filepath)
        return len(accounts)

    def export_csv(self, filepath: str) -> int:
        """Exporta en CSV con contraseñas en texto plano."""
        accounts = self._service.get_all()
        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["alias", "username", "password", "region",
                     "tags", "notes", "created_at", "updated_at"]
                )
                for a in accounts:
                    plaintext = self._crypto.decrypt(a.password)
                    writer.writerow([
                        a.alias, a.username, plaintext, a.region,
                        ", ".join(a.tags), a.notes, a.created_at, a.updated_at,
                    ])
        except OSError as e:
            raise ExportError(f"No se pudo escribir el CSV: {e}") from e

        logger.info("CSV: exportadas %d cuentas a %s.", len(accounts), filepath)
        return len(accounts)

    def probe_file(self, filepath: str) -> dict:
        """Examina el archivo y devuelve su formato y metadatos sin importar nada."""
        if filepath.lower().endswith(".csv"):
            return self._probe_csv(filepath)
        return self._probe_json(filepath)

    def import_json(self, filepath: str) -> tuple[int, int]:
        """JSON v1 — descifra con la clave maestra activa."""
        data = _load_json(filepath)
        if data.get("version") != 1 or "accounts" not in data:
            raise ExportError("El archivo no es un backup JSON v1 de Rift Vault.")
        return self._import_entries(data["accounts"], self._decrypt_master)

    def import_json_with_password(self, filepath: str, export_password: str) -> tuple[int, int]:
        """JSON v2 — descifra con la contraseña de exportación."""
        data = _load_json(filepath)
        if data.get("version") != 2 or data.get("encryption") != "pbkdf2-fernet":
            raise ExportError("El archivo no es un backup JSON v2 de Rift Vault.")

        salt       = bytes.fromhex(data["salt"])
        iterations = int(data.get("iterations", _EXPORT_ITERATIONS))
        key        = _derive_export_key(export_password, salt, iterations)
        fernet     = Fernet(key)

        def decrypt_export(token: str) -> str:
            try:
                return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
            except InvalidToken:
                raise ExportError(
                    "La contraseña de exportación es incorrecta o el archivo está corrupto."
                )

        imported, skipped = self._import_entries(data["accounts"], decrypt_export)
        logger.info("JSON v2: %d importadas, %d omitidas.", imported, skipped)
        return imported, skipped

    def import_csv(self, filepath: str) -> tuple[int, int]:
        """CSV — contraseñas en texto plano; mapeo de columnas automático."""
        from app.core.account import VALID_REGIONS

        rows    = self._read_csv_rows(filepath)
        if not rows:
            return 0, 0

        mapping  = _detect_csv_columns(rows[0])
        existing = self._existing_set()
        imported = skipped = 0

        for row in rows[1:]:
            if not row or all(c.strip() == "" for c in row):
                continue

            def _get(field: str) -> str:
                idx = mapping.get(field)
                return row[idx].strip() if idx is not None and idx < len(row) else ""

            alias    = _get("alias")
            username = _get("username")
            password = _get("password")
            region   = _get("region").upper() or "EUW"
            tags_raw = _get("tags")
            notes    = _get("notes")

            if not alias or not username or not password:
                skipped += 1
                continue
            if (alias.lower(), username.lower()) in existing:
                skipped += 1
                continue
            if region not in VALID_REGIONS:
                region = "EUW"

            tags = [t.strip() for t in tags_raw.replace(";", ",").split(",") if t.strip()]

            try:
                self._service.create(
                    alias=alias, username=username, password=password,
                    region=region, tags=tags, notes=notes,
                )
                existing.add((alias.lower(), username.lower()))
                imported += 1
            except ValueError:
                skipped += 1

        logger.info("CSV: %d importadas, %d omitidas.", imported, skipped)
        return imported, skipped

    def _existing_set(self) -> set:
        return {(a.alias.lower(), a.username.lower()) for a in self._service.get_all()}

    def _decrypt_master(self, token: str) -> str:
        try:
            return self._crypto.decrypt(token)
        except (ValueError, RuntimeError) as e:
            raise ExportError(
                "Las contraseñas no pueden descifrarse. "
                "El archivo fue exportado con una contraseña maestra diferente."
            ) from e

    def _import_entries(self, entries: list, decrypt_fn) -> tuple[int, int]:
        existing = self._existing_set()
        imported = skipped = 0

        for entry in entries:
            alias    = (entry.get("alias")    or "").strip()
            username = (entry.get("username") or "").strip()
            token    = (entry.get("password_encrypted") or "").strip()

            if not alias or not username or not token:
                skipped += 1
                continue
            if (alias.lower(), username.lower()) in existing:
                skipped += 1
                continue

            plaintext = decrypt_fn(token)   # puede lanzar ExportError

            try:
                self._service.create(
                    alias=alias, username=username, password=plaintext,
                    region=entry.get("region", "EUW"),
                    tags=entry.get("tags") or [],
                    notes=entry.get("notes") or "",
                )
                existing.add((alias.lower(), username.lower()))
                imported += 1
            except ValueError:
                skipped += 1

        logger.info("Import: %d importadas, %d omitidas.", imported, skipped)
        return imported, skipped

    def _probe_json(self, filepath: str) -> dict:
        data    = _load_json(filepath)
        version = data.get("version", 0)
        if version == 1 and "accounts" in data:
            return {
                "format":           _FMT_JSON_V1,
                "account_count":    len(data["accounts"]),
                "encrypted_custom": False,
                "csv_headers":      None,
                "csv_mapping":      None,
            }
        if version == 2 and data.get("encryption") == "pbkdf2-fernet":
            return {
                "format":           _FMT_JSON_V2,
                "account_count":    len(data.get("accounts", [])),
                "encrypted_custom": True,
                "csv_headers":      None,
                "csv_mapping":      None,
            }
        raise ExportError("El archivo no es un backup de Rift Vault válido.")

    def _probe_csv(self, filepath: str) -> dict:
        rows = self._read_csv_rows(filepath)
        headers = rows[0] if rows else []
        try:
            mapping = _detect_csv_columns(headers)
        except ExportError:
            mapping = {}
        return {
            "format":           _FMT_CSV,
            "account_count":    max(0, len(rows) - 1),
            "encrypted_custom": False,
            "csv_headers":      [h.strip() for h in headers],
            "csv_mapping":      mapping,
        }

    @staticmethod
    def _read_csv_rows(filepath: str) -> list[list[str]]:
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(filepath, newline="", encoding=enc) as f:
                    sample = f.read(8192)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                with open(filepath, newline="", encoding=enc) as f:
                    return list(csv.reader(f, dialect))
            except (OSError, UnicodeDecodeError):
                continue
        raise ExportError("No se pudo leer el CSV (codificación no reconocida).")
