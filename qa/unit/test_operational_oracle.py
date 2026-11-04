import unittest
from decimal import Decimal

from qa.operational_oracle import money, reconcile


class OperationalOracleTests(unittest.TestCase):
    def test_event_half_up(self) -> None:
        self.assertEqual(money("10.005"), Decimal("10.01"))
        self.assertEqual(money("0.005"), Decimal("0.01"))

    def test_known_loss_independent_example(self) -> None:
        actual = reconcile(
            sale="100.005",
            discount="0.005",
            refund="1.005",
            fees=["2.005", "0.005"],
            cost="200.005",
        )
        self.assertEqual(actual["contribution"], "-103.04")
        self.assertEqual(actual["net_sales"], "98.99")
        self.assertEqual(actual["margin_percent"], "-104.09")

    def test_unknown_cost_not_zero(self) -> None:
        actual = reconcile(sale="10", discount="0", refund="0", fees=["1"], cost=None)
        self.assertEqual(actual["contribution"], "UNKNOWN")
        self.assertEqual(actual["known_direct_costs"], "UNKNOWN")
        self.assertIsNone(actual["margin_percent"])

    def test_zero_cost_is_known(self) -> None:
        self.assertEqual(
            reconcile(sale="10", discount="0", refund="0", fees=["1"], cost="0")["contribution"],
            "9.00",
        )

    def test_nonfinite_rejected(self) -> None:
        for value in ("NaN", "Infinity"):
            with self.assertRaises(ValueError):
                money(value)
