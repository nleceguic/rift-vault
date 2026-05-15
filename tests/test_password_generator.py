"""
tests/test_password_generator.py – Tests para password_generator.generate() y evaluate().
"""

import string
import pytest

from app.core.password_generator import (
    generate,
    evaluate,
    STRENGTH_LABELS,
    _SYMBOLS,
    _AMBIGUOUS,
)

_LOWERCASE = set(string.ascii_lowercase)
_UPPERCASE = set(string.ascii_uppercase)
_DIGITS    = set(string.digits)
_SYMS      = set(_SYMBOLS)


# ─────────────────────────────────────────────
#  generate()
# ─────────────────────────────────────────────

class TestGenerate:

    def test_default_length(self):
        pw = generate()
        assert len(pw) == 16

    def test_custom_length(self):
        for length in (8, 20, 64):
            pw = generate(length=length)
            assert len(pw) == length

    def test_minimum_length_clamp(self):
        pw = generate(length=1)
        assert len(pw) == 4

    def test_default_includes_all_char_classes(self):
        pw = generate(length=40)
        assert any(c in _LOWERCASE for c in pw)
        assert any(c in _UPPERCASE for c in pw)
        assert any(c in _DIGITS    for c in pw)
        assert any(c in _SYMS      for c in pw)

    def test_no_upper(self):
        pw = generate(length=40, use_upper=False)
        assert not any(c in _UPPERCASE for c in pw)

    def test_no_digits(self):
        pw = generate(length=40, use_digits=False)
        assert not any(c in _DIGITS for c in pw)

    def test_no_symbols(self):
        pw = generate(length=40, use_symbols=False)
        assert not any(c in _SYMS for c in pw)

    def test_no_ambiguous(self):
        for _ in range(20):
            pw = generate(length=32, no_ambiguous=True)
            assert not any(c in _AMBIGUOUS for c in pw)

    def test_all_disabled_except_lower(self):
        pw = generate(length=20, use_upper=False, use_digits=False, use_symbols=False)
        assert all(c in _LOWERCASE for c in pw)

    def test_guaranteed_one_from_each_enabled_class(self):
        # With length 4 and all options enabled we must get exactly one from each class
        found_lower = found_upper = found_digit = found_sym = False
        for _ in range(200):
            pw = generate(length=4)
            if any(c in _LOWERCASE for c in pw): found_lower = True
            if any(c in _UPPERCASE for c in pw): found_upper = True
            if any(c in _DIGITS    for c in pw): found_digit = True
            if any(c in _SYMS      for c in pw): found_sym   = True
            if found_lower and found_upper and found_digit and found_sym:
                break
        assert found_lower and found_upper and found_digit and found_sym

    def test_returns_string(self):
        assert isinstance(generate(), str)

    def test_different_each_call(self):
        passwords = {generate() for _ in range(10)}
        # Extremely unlikely to get the same password twice
        assert len(passwords) >= 9


# ─────────────────────────────────────────────
#  evaluate()
# ─────────────────────────────────────────────

class TestEvaluate:

    def test_empty_password(self):
        r = evaluate("")
        assert r["level"] == 0
        assert r["label"] == ""
        assert r["entropy"] == 0.0

    def test_returns_dict_keys(self):
        r = evaluate("Hello1!")
        assert set(r.keys()) == {"level", "label", "entropy"}

    def test_entropy_positive(self):
        r = evaluate("abc")
        assert r["entropy"] > 0

    def test_level_range(self):
        for pw in ["a", "abc123", "Abc123!!", "Abc123!!Abc123!!", "A" * 30 + "1!b"]:
            r = evaluate(pw)
            assert 1 <= r["level"] <= 5

    def test_label_matches_level(self):
        for pw in ["abc", "Abc1!", "Abc1!Abc1!Abc1!Abc1!"]:
            r = evaluate(pw)
            assert r["label"] == STRENGTH_LABELS[r["level"]]

    def test_longer_password_higher_entropy(self):
        short  = evaluate("Abc1!")["entropy"]
        longer = evaluate("Abc1!Abc1!Abc1!")["entropy"]
        assert longer > short

    def test_mixed_charset_higher_entropy_than_lower_only(self):
        lower_only = evaluate("a" * 20)["entropy"]
        mixed      = evaluate("Aa1!" * 5)["entropy"]
        assert mixed > lower_only

    def test_very_weak_password(self):
        # 3 lowercase chars → very low entropy
        r = evaluate("abc")
        assert r["level"] == 1
        assert r["label"] == "Muy débil"

    def test_excellent_password(self):
        # Long mixed password should hit level 5
        r = evaluate("Tr0ub4dor&3XkP!zQ9")
        assert r["level"] == 5
        assert r["label"] == "Excelente"

    def test_entropy_formula(self):
        # "aaaa" → charset=26, entropy=4*log2(26)
        import math
        r = evaluate("aaaa")
        assert abs(r["entropy"] - 4 * math.log2(26)) < 0.001

    def test_symbols_increase_charset(self):
        letters_only = evaluate("Abcdefgh")["entropy"]
        with_symbol  = evaluate("Abcdefg!")["entropy"]
        assert with_symbol > letters_only

    @pytest.mark.parametrize("level,expected_label", [
        (0, ""),
        (1, "Muy débil"),
        (2, "Débil"),
        (3, "Aceptable"),
        (4, "Fuerte"),
        (5, "Excelente"),
    ])
    def test_strength_labels_table(self, level, expected_label):
        assert STRENGTH_LABELS[level] == expected_label
