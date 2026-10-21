"""Exact count ratios for decisions and jointly rounded prevalence displays."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction


def _decimal_digits(value: int) -> int:
    """Integer magnitude without Python's decimal-string conversion limit."""
    digits = value.bit_length() * 30103 // 100000 + 1
    while value < 10 ** (digits - 1):
        digits -= 1
    while value >= 10**digits:
        digits += 1
    return digits


@dataclass(frozen=True)
class DocumentRate:
    """A valid document prevalence; floating values are reporting projections."""

    mentions: int
    observations: int

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (self.mentions, self.observations)
        ):
            raise ValueError("document counts must be integers")
        if not 0 <= self.mentions <= self.observations or self.observations == 0:
            raise ValueError("document counts require 0 <= mentions <= positive observations")

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.mentions, self.observations)

    @property
    def value(self) -> float:
        return float(self.fraction)

    def percentage(self, digits: int = 3) -> str:
        """Round an exact rational to significant digits, without float division."""
        if isinstance(digits, bool) or not isinstance(digits, int) or digits < 1:
            raise ValueError("percentage precision must be positive")
        if not self.mentions:
            return "0%"
        value = self.fraction * 100
        exponent = _decimal_digits(value.numerator) - _decimal_digits(value.denominator)
        if value < Fraction(10) ** exponent:
            exponent -= 1
        shift = exponent - digits + 1
        significand = round(value / Fraction(10) ** shift)
        with localcontext() as context:
            context.prec = digits + 2
            rounded = Decimal(significand).scaleb(shift)
            if -4 <= rounded.adjusted() < digits:
                text = format(rounded, "f")
                if "." in text:
                    text = text.rstrip("0").rstrip(".")
            else:
                mantissa, power = format(rounded, f".{digits - 1}e").split("e")
                if "." in mantissa:
                    mantissa = mantissa.rstrip("0").rstrip(".")
                text = f"{mantissa}e{int(power):+d}"
        return text + "%"


def percentage_pair(left: DocumentRate, right: DocumentRate) -> tuple[str, str]:
    """Equal exact rates display equally; distinct rates remain visibly distinct."""
    digits = 3
    while True:
        a, b = left.percentage(digits), right.percentage(digits)
        if a != b or left.fraction == right.fraction:
            return a, b
        digits += 1
