"""Capa de lógica de negocio para gestión de cuentas de LoL."""

import dataclasses
import logging
from typing import Optional

from app.core.account import Account, VALID_REGIONS, NOTES_MAX_CHARS
from app.storage.base_storage import BaseStorage

logger = logging.getLogger(__name__)


def _hooks():
    from app.hooks.hooks_registry import HooksRegistry
    return HooksRegistry.instance()


class AccountService:
    """Orquesta todas las operaciones sobre cuentas de LoL."""

    def __init__(self, storage: BaseStorage, history_service=None):
        self._storage         = storage
        self._history_service = history_service

    def get_all(self) -> list[Account]:
        accounts = self._storage.load_all()
        return sorted(accounts, key=lambda a: a.alias.lower())

    def find_by_id(self, account_id: str) -> Optional[Account]:
        return self._storage.find_by_id(account_id)

    def get_decrypted_password(self, account_id: str) -> str:
        return self._storage.get_decrypted_password(account_id)

    def search(self, query: str) -> list[Account]:
        all_accounts = self.get_all()
        if not query.strip():
            return all_accounts
        return [a for a in all_accounts if a.matches_search(query)]

    def search_filtered(
        self,
        query:  str = "",
        region: str = "Todas",
        tags:   list = None,
        sort:   str = "alias_asc",
    ) -> list[Account]:
        from app.core.advanced_search import parse_query, matches_advanced, has_operators
        from datetime import datetime, timezone

        accounts = self._storage.load_all()

        if query:
            parsed = parse_query(query)

            # Operator: alias:X — overrides the UI region dropdown if provided
            if parsed["alias"]:
                v = parsed["alias"].lower()
                accounts = [a for a in accounts if v in a.alias.lower()]

            # Operator: region:EUW — overrides the UI region dropdown
            if parsed["region"]:
                v = parsed["region"].upper()
                accounts = [a for a in accounts if a.region.upper() == v]
            elif region and region != "Todas":
                accounts = [a for a in accounts if a.region == region]

            # Operator: tag:X — adds to the UI tag filter (AND logic)
            if parsed["tag"]:
                v = parsed["tag"].lower()
                accounts = [a for a in accounts if any(v in t.lower() for t in a.tags)]

            if parsed["before"]:
                try:
                    cutoff = datetime.fromisoformat(parsed["before"])
                    if cutoff.tzinfo is None:
                        cutoff = cutoff.replace(tzinfo=timezone.utc)
                    accounts = [
                        a for a in accounts
                        if datetime.fromisoformat(a.created_at) < cutoff
                    ]
                except ValueError:
                    pass

            if parsed["free_text"]:
                accounts = [a for a in accounts if matches_advanced(parsed["free_text"], a)]

        else:
            if region and region != "Todas":
                accounts = [a for a in accounts if a.region == region]

        # UI tag filter (from FilterBar chips — AND logic)
        if tags:
            for tag in tags:
                accounts = [a for a in accounts if tag in a.tags]

        if sort == "alias_asc":
            accounts.sort(key=lambda a: a.alias.lower())
        elif sort == "alias_desc":
            accounts.sort(key=lambda a: a.alias.lower(), reverse=True)
        elif sort == "reciente":
            accounts.sort(key=lambda a: a.created_at, reverse=True)
        elif sort == "antiguo":
            accounts.sort(key=lambda a: a.created_at)

        return accounts

    def get_all_tags(self) -> list[str]:
        all_tags = set()
        for account in self._storage.load_all():
            all_tags.update(account.tags)
        return sorted(all_tags)

    def create(
        self,
        alias:    str,
        username: str,
        password: str,
        region:   str = "EUW",
        tags:     Optional[list[str]] = None,
        notes:    str = "",
        riot_id:  str = "",
    ) -> Account:
        hooks = _hooks()

        data = {
            "alias":    alias.strip(),
            "username": username.strip(),
            "password": password,
            "region":   region.upper(),
            "tags":     [t.strip() for t in (tags or []) if t.strip()],
            "notes":    notes.strip(),
            "riot_id":  riot_id.strip(),
        }
        data = hooks.run("before_account_create", data=data)

        self._validate(data["alias"], data["username"], data["password"], data["region"], data.get("notes", ""))

        account = Account(
            alias=    data["alias"],
            username= data["username"],
            password= data["password"],
            region=   data["region"],
            tags=     data.get("tags", []),
            notes=    data.get("notes", ""),
            riot_id=  data.get("riot_id", ""),
        )
        account = self._storage.save(account)
        hooks.fire("after_account_create", account=account)
        logger.info("Cuenta creada: alias=%r region=%s id=%s", account.alias, account.region, account.id)
        return account

    def update(
        self,
        account:  Account,
        alias:    Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        region:   Optional[str] = None,
        tags:     Optional[list[str]] = None,
        notes:    Optional[str] = None,
        riot_id:  Optional[str] = None,
    ) -> Account:
        hooks = _hooks()

        changes: dict = {}
        if alias    is not None: changes["alias"]    = alias.strip()
        if username is not None: changes["username"] = username.strip()
        if password is not None: changes["password"] = password
        if region   is not None: changes["region"]   = region.upper()
        if tags     is not None: changes["tags"]     = [t.strip() for t in tags if t.strip()]
        if notes    is not None: changes["notes"]    = notes.strip()
        if riot_id  is not None: changes["riot_id"]  = riot_id.strip()

        changes = hooks.run("before_account_update", changes=changes, account=account)

        changing_password = "password" in changes
        old_plaintext: Optional[str] = None
        if changing_password and self._history_service:
            new_plain = changes["password"]
            if self._history_service.is_reuse(account.id, new_plain):
                raise ValueError("Esta contraseña fue utilizada recientemente. Elige una diferente.")
            old_plaintext = self._storage.get_decrypted_password(account.id)

        _MUTABLE_FIELDS = {"alias", "username", "password", "region", "tags", "notes", "riot_id"}
        field_updates = {k: v for k, v in changes.items() if k in _MUTABLE_FIELDS}
        account = dataclasses.replace(account, **field_updates)

        validate_password = changes.get("password", "unchanged")
        self._validate(account.alias, account.username, validate_password, account.region, account.notes)

        account = self._storage.update(account)

        if changing_password and self._history_service and old_plaintext:
            self._history_service.push(account.id, old_plaintext)

        hooks.fire("after_account_update", account=account)
        logger.info("Cuenta actualizada: id=%s fields=%s", account.id, list(changes.keys()))
        return account

    def delete(self, account_id: str) -> bool:
        hooks = _hooks()

        if not hooks.can("before_account_delete", account_id=account_id):
            logger.info("Eliminación de cuenta cancelada por hook: id=%s", account_id)
            return False

        result = self._storage.delete(account_id)
        if result:
            hooks.fire("after_account_delete", account_id=account_id)
            logger.info("Cuenta eliminada: id=%s", account_id)
        else:
            logger.warning("Intento de eliminar cuenta inexistente: id=%s", account_id)
        return result

    def _validate(self, alias: str, username: str, password: str, region: str, notes: str = "") -> None:
        errors = []

        if not alias or not alias.strip():
            errors.append("El alias no puede estar vacío.")
        elif len(alias.strip()) > 50:
            errors.append("El alias no puede superar los 50 caracteres.")

        if not username or not username.strip():
            errors.append("El username no puede estar vacío.")
        elif len(username.strip()) > 50:
            errors.append("El username no puede superar los 50 caracteres.")

        if not password:
            errors.append("La contraseña no puede estar vacía.")

        if region.upper() not in VALID_REGIONS:
            errors.append(f"Región inválida. Válidas: {', '.join(VALID_REGIONS)}")

        if len(notes) > NOTES_MAX_CHARS:
            errors.append(f"Las notas no pueden superar los {NOTES_MAX_CHARS} caracteres.")

        if errors:
            logger.warning("Validación de cuenta fallida: %s", "; ".join(errors))
            raise ValueError("\n".join(errors))
