"""Modelo de dominio Account para cuentas de League of Legends."""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _new_id() -> str:
    return str(uuid.uuid4())

VALID_REGIONS    = ["EUW", "EUNE", "NA", "LAS", "LAN", "BR", "OCE", "KR", "JP", "TR", "RU"]
NOTES_MAX_CHARS  = 500

@dataclass(frozen=True)
class Account:
    """Representa una cuenta de League of Legends."""

    alias:    str
    username: str
    password: str

    region:     str       = "EUW"
    tags:       list[str] = field(default_factory=list)
    notes:      str       = ""
    riot_id:    str       = ""

    id:         str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> "Account":
        """Devuelve una nueva instancia con updated_at actualizado."""
        return dataclasses.replace(self, updated_at=_now_iso())

    def to_dict(self) -> dict:
        """Serializa la cuenta a diccionario."""
        return {
            "id":         self.id,
            "alias":      self.alias,
            "username":   self.username,
            "password":   self.password,
            "region":     self.region,
            "tags":       self.tags,
            "notes":      self.notes,
            "riot_id":    self.riot_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        """Deserializa una cuenta desde diccionario."""
        return cls(
            id=         data["id"],
            alias=      data["alias"],
            username=   data["username"],
            password=   data["password"],
            region=     data.get("region", "EUW"),
            tags=       data.get("tags", []),
            notes=      data.get("notes", ""),
            riot_id=    data.get("riot_id", ""),
            created_at= data.get("created_at", _now_iso()),
            updated_at= data.get("updated_at", _now_iso()),
        )

    def matches_search(self, query: str) -> bool:
        """Devuelve True si la cuenta coincide con el término de búsqueda."""
        q = query.lower().strip()
        if not q:
            return True
        return (
            q in self.alias.lower()
            or q in self.username.lower()
            or q in self.notes.lower()
            or any(q in tag.lower() for tag in self.tags)
        )

    def __str__(self) -> str:
        return f"Account(alias={self.alias!r}, username={self.username!r}, region={self.region})"