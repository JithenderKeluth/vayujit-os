"""Independent PR-SOS-05 event arithmetic; no production calculator imports.

Amounts are per financial event/cost evidence, not an invented per-unit COGS
or marketplace tax schedule. Unknown inputs deliberately do not become zero.
"""

from decimal import ROUND_HALF_UP, Decimal


def money(value: str) -> Decimal:
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("QA_NONFINITE_MONEY")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def reconcile(
    *, sale: str, discount: str, refund: str, fees: list[str], cost: str | None
) -> dict[str, str | None]:
    net = money(sale) - money(discount) - money(refund)
    deductions = sum((money(value) for value in fees), Decimal("0.00"))
    contribution = net - deductions - money(cost) if cost is not None else None
    return {
        "gross_sales": str(money(sale)),
        "discounts": str(money(discount)),
        "refunds": str(money(refund)),
        "net_sales": str(net),
        "fees": str(deductions),
        "known_direct_costs": str(money(cost)) if cost is not None else "UNKNOWN",
        "contribution": str(contribution) if contribution is not None else "UNKNOWN",
        "margin_percent": (
            str((contribution / net * 100).quantize(Decimal("0.01")))
            if contribution is not None and net
            else None
        ),
    }
