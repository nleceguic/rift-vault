"""Generación criptográficamente segura y evaluación de fortaleza de contraseñas."""

import math
import string
from secrets import choice, SystemRandom

_LOWERCASE  = string.ascii_lowercase
_UPPERCASE  = string.ascii_uppercase
_DIGITS     = string.digits
_SYMBOLS    = "!@#$%^&*()-_=+[]{}|;:,.<>?"
_AMBIGUOUS  = frozenset("0O1lI")

_rng = SystemRandom()

STRENGTH_LABELS = ["", "Muy débil", "Débil", "Aceptable", "Fuerte", "Excelente"]
# Umbrales de entropía (bits) para cada nivel
_THRESHOLDS = [36, 52, 68, 88]  # <36 → 1, <52 → 2, <68 → 3, <88 → 4, ≥88 → 5


def generate(
    length:       int  = 16,
    use_upper:    bool = True,
    use_digits:   bool = True,
    use_symbols:  bool = True,
    no_ambiguous: bool = False,
) -> str:
    """
    Genera una contraseña aleatoria de `length` caracteres.

    Garantiza al menos un carácter de cada categoría habilitada.
    Usa secrets.SystemRandom — seguro para uso criptográfico.
    """
    length = max(4, int(length))

    def _filtered(chars: str) -> list[str]:
        return [c for c in chars if c not in _AMBIGUOUS] if no_ambiguous else list(chars)

    pool: list[str] = _filtered(_LOWERCASE)
    required: list[str] = [choice(_filtered(_LOWERCASE) or list(_LOWERCASE))]

    if use_upper:
        chars = _filtered(_UPPERCASE)
        if chars:
            pool += chars
            required.append(_rng.choice(chars))

    if use_digits:
        chars = _filtered(_DIGITS)
        if chars:
            pool += chars
            required.append(_rng.choice(chars))

    if use_symbols:
        pool += list(_SYMBOLS)
        required.append(_rng.choice(_SYMBOLS))

    if not pool:
        pool = list(_LOWERCASE)

    remaining = max(0, length - len(required))
    password  = required + [_rng.choice(pool) for _ in range(remaining)]
    _rng.shuffle(password)
    return "".join(password[:length])


def evaluate(password: str) -> dict:
    """Evalúa la fortaleza de una contraseña por entropía; devuelve level, label y entropy."""
    if not password:
        return {"level": 0, "label": STRENGTH_LABELS[0], "entropy": 0.0}

    charset = 0
    if any(c.islower() for c in password):        charset += 26
    if any(c.isupper() for c in password):        charset += 26
    if any(c.isdigit() for c in password):        charset += 10
    if any(c in _SYMBOLS for c in password):      charset += len(_SYMBOLS)

    if charset < 2:
        charset = 26   # fallback razonable para chars fuera de los grupos

    entropy = len(password) * math.log2(charset)

    level = 1
    for threshold in _THRESHOLDS:
        if entropy >= threshold:
            level += 1

    return {
        "level":   level,
        "label":   STRENGTH_LABELS[level],
        "entropy": entropy,
    }
