"""Independent QA arithmetic. No application calculation code is imported.

Contract: modeled contribution (not net profit), 8dp ROUND_HALF_UP, explicit
scenario fees only. PER_ORDER/SHIPMENT is allocated over the modeled quantity.
Tax/GST, advertising and returns are not inferred.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

QUANTUM = Decimal("0.00000001")


def rounded(value: Decimal) -> Decimal:
    return value.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def expected(
    *,
    price: str,
    freight: str,
    quantity: str,
    selling: str,
    percent: str = "0",
    order_fee: str = "0",
    unit_fee: str = "0",
    capital: str = "300000",
) -> dict[str, Any]:
    p, f, q, s, rate, order, unit, cash = map(
        Decimal, (price, freight, quantity, selling, percent, order_fee, unit_fee, capital)
    )
    if q <= 0 or s <= 0:
        raise ValueError("Oracle requires a positive quantity and selling price")
    landed_total = rounded(p * q + f)
    landed_unit = rounded(landed_total / q)
    selling_unit = rounded(s * rate / 100 + order / q + unit)
    contribution = rounded(s - rounded(landed_unit + selling_unit))
    # The application's capital contract uses rounded landed_unit * modeled Q.
    required = rounded(landed_unit * q)
    return {
        "per_unit_landed_cost": landed_unit,
        "per_unit_selling_cost": selling_unit,
        "per_unit_total_cost": rounded(landed_unit + selling_unit),
        "per_unit_contribution": contribution,
        "contribution_margin": rounded(contribution / s),
        "capital_required": required,
        "landed_total": landed_total,
        "capital_fit_status": "FITS" if cash >= required else "DOES_NOT_FIT",
    }
