"""Parser y motor de búsqueda avanzada con operadores y fuzzy match."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.account import Account

_OP_RE = re.compile(r'\b(alias|region|tag|before):(\S+)', re.IGNORECASE)


def parse_query(text: str) -> dict:
    """Extrae operadores del texto de búsqueda y devuelve el resto como free_text."""
    ops: dict[str, str | None] = {
        "alias":     None,
        "region":    None,
        "tag":       None,
        "before":    None,
    }
    remainder = text
    for m in _OP_RE.finditer(text):
        key = m.group(1).lower()
        val = m.group(2)
        if key in ops:
            ops[key] = val
        remainder = remainder.replace(m.group(0), "", 1)
    ops["free_text"] = remainder.strip()
    return ops


def has_operators(text: str) -> bool:
    """True si el texto contiene al menos un operador."""
    return bool(_OP_RE.search(text))


def _levenshtein(a: str, b: str) -> int:
    """Distancia de edición estándar entre dos strings."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev = curr
    return prev[lb]


def _max_dist(length: int) -> int:
    if length <= 3:
        return 0
    if length <= 6:
        return 1
    return 2


def fuzzy_match(query: str, target: str) -> bool:
    """
    True si `query` coincide aproximadamente con alguna parte de `target`.
    Primero prueba substring (más rápido), luego Levenshtein por palabras.
    """
    q = query.lower().strip()
    t = target.lower()
    if not q:
        return True
    if q in t:
        return True

    max_d = _max_dist(len(q))
    if max_d == 0:
        return False

    for word in t.split():
        if _levenshtein(q, word) <= max_d:
            return True
    return False


def matches_advanced(free_text: str, account: "Account") -> bool:
    """
    Comprueba si una cuenta coincide con el texto libre usando fuzzy match
    sobre alias, username y tags.
    """
    if not free_text:
        return True
    for token in free_text.split():
        fields = [account.alias, account.username] + list(account.tags)
        if not any(fuzzy_match(token, field) for field in fields):
            return False
    return True


def filter_accounts(accounts: list, query: str) -> list:
    """Aplica el parser de operadores y el fuzzy match a una lista de cuentas."""
    if not query.strip():
        return accounts

    parsed = parse_query(query)
    result = accounts

    if parsed["alias"]:
        v = parsed["alias"].lower()
        result = [a for a in result if v in a.alias.lower()]

    if parsed["region"]:
        v = parsed["region"].upper()
        result = [a for a in result if a.region.upper() == v]

    if parsed["tag"]:
        v = parsed["tag"].lower()
        result = [a for a in result if any(v in t.lower() for t in a.tags)]

    if parsed["before"]:
        try:
            cutoff = datetime.fromisoformat(parsed["before"])
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            result = [
                a for a in result
                if datetime.fromisoformat(a.created_at) < cutoff
            ]
        except ValueError:
            pass

    if parsed["free_text"]:
        result = [a for a in result if matches_advanced(parsed["free_text"], a)]

    return result
