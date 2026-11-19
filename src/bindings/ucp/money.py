"""ISO 4217 minor-unit conversion. Rates stay decimal strings."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

_ZERO_EXPONENT = frozenset({"JPY", "KRW", "VND"})
_THREE_EXPONENT = frozenset({"BHD", "KWD", "OMR", "TND"})


def exponent(currency: str) -> int:
    code = currency.upper()
    if code in _ZERO_EXPONENT:
        return 0
    if code in _THREE_EXPONENT:
        return 3
    return 2


def minor_to_decimal(minor: int, currency: str) -> str:
    """Format a minor-unit integer as a UTCS decimal string."""
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = f"{abs(minor):0{exp + 1}d}" if exp else str(abs(minor))
    if exp == 0:
        return f"{sign}{abs(minor)}"
    whole, frac = digits[:-exp], digits[-exp:]
    return f"{sign}{int(whole)}.{frac}"


def decimal_to_minor(amount: str, currency: str) -> int:
    """Convert a UTCS decimal string to minor units, half-up."""
    exp = exponent(currency)
    negative = amount.startswith("-")
    raw = amount[1:] if negative else amount
    quantized = Decimal(raw).scaleb(exp).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    minor = int(quantized)
    return -minor if negative else minor
