"""Fixed independent examples: no production imports or network/database usage."""

import unittest
from decimal import Decimal

from qa.financial_oracle import expected, rounded


class OracleTests(unittest.TestCase):
    def test_decimal_example(self) -> None:
        result = expected(
            price="100.125",
            freight="2500",
            quantity="500",
            selling="250",
            percent="10",
            order_fee="50",
        )
        self.assertEqual(result["per_unit_contribution"], Decimal("119.77500000"))
        self.assertEqual(result["contribution_margin"], Decimal("0.47910000"))
        self.assertEqual(result["capital_required"], Decimal("52562.50000000"))

    def test_negative_contribution(self) -> None:
        self.assertEqual(
            expected(
                price="100", freight="0", quantity="10", selling="90", percent="10", order_fee="50"
            )["per_unit_contribution"],
            Decimal("-24.00000000"),
        )

    def test_zero_margin_is_not_missing(self) -> None:
        self.assertEqual(
            expected(price="100", freight="0", quantity="10", selling="125", percent="20")[
                "contribution_margin"
            ],
            Decimal("0.00000000"),
        )

    def test_fractional_allocation(self) -> None:
        result = expected(
            price="1.25", freight="1", quantity="3", selling="5", percent="12.5", order_fee="0.1"
        )
        self.assertEqual(result["per_unit_landed_cost"], Decimal("1.58333333"))
        self.assertEqual(result["per_unit_contribution"], Decimal("2.75833334"))

    def test_half_up_eight_places(self) -> None:
        self.assertEqual(rounded(Decimal("1.000000005")), Decimal("1.00000001"))
        self.assertEqual(rounded(Decimal("-1.000000005")), Decimal("-1.00000001"))

    def test_zero_quantity_and_price_rejected(self) -> None:
        for quantity, selling in [("0", "5"), ("3", "0")]:
            with self.assertRaises(ValueError):
                expected(price="1", freight="0", quantity=quantity, selling=selling)

    def test_capital_shortfall(self) -> None:
        self.assertEqual(
            expected(price="100", freight="0", quantity="4000", selling="200")[
                "capital_fit_status"
            ],
            "DOES_NOT_FIT",
        )
