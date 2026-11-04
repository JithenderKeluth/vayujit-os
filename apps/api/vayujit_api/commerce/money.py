"""Decimal-only projection rounding; never supplies missing evidence or exchange rates."""

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

PAISE = Decimal("0.01")


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(PAISE, rounding=ROUND_HALF_UP)


def allocate_money(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Conserve a recorded total using largest remainder; stable input order breaks ties.

    The caller must supply nonnegative known weights with a positive sum. This is
    not an allocation authority for missing/zero/contradictory source amounts.
    """
    if not weights or any(not w.is_finite() or w < 0 for w in weights) or sum(weights) <= 0:
        raise ValueError("Known nonnegative allocation weights with positive total required.")
    total = round_money(amount)
    sign = Decimal("-1") if total < 0 else Decimal("1")
    units = abs(total) / PAISE
    shares = [units * w / sum(weights) for w in weights]
    floors = [v.to_integral_value(rounding=ROUND_FLOOR) for v in shares]
    remaining = int(units - sum(floors))
    order = sorted(range(len(weights)), key=lambda i: (-(shares[i] - floors[i]), i))
    for i in order[:remaining]:
        floors[i] += 1
    return [v * PAISE * sign for v in floors]
