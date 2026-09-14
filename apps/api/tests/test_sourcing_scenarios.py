from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vayujit_api.intelligence.scenario_analysis import COST_KEYS, calculate, compare, sensitivity
from vayujit_api.intelligence.scenario_schemas import Allocation, ContextCreate, ScenarioCreate
from vayujit_api.intelligence.sourcing_closure import landed_cost


def inputs() -> tuple[dict, dict, list[dict]]:
    supplier = str(uuid.uuid4())
    context = ContextCreate(
        shortlist_version_id=uuid.uuid4(),
        base_currency="INR",
        target_market="IN",
        target_channel="internal",
        target_quantity=100,
        target_sale_price=Decimal("20"),
        margin_target=Decimal("10"),
        capital_limit=Decimal("3000"),
        idempotency_key="context-test",
    ).model_dump(mode="json")
    request = ScenarioCreate(
        name="Local assumption",
        logistics_mode="LOCAL",
        idempotency_key="scenario-test",
        allocations=[
            Allocation(
                supplier_id=uuid.UUID(supplier),
                due_diligence_id=uuid.uuid4(),
                quantity=100,
                unit_price=Decimal("10.000001"),
                currency="INR",
                moq=10,
                lead_time_days=5,
                availability="AVAILABLE",
                incoterm="DDP",
                assumption_reason="Local deterministic test",
            )
        ],
        costs={key: Decimal("0") for key in COST_KEYS},
        working_capital_buffer=Decimal("50"),
        channel_fee_per_unit=Decimal("1"),
        payment_fee_per_unit=Decimal("0"),
        returns_per_unit=Decimal("1"),
        advertising_per_unit=Decimal("1"),
        logistics_days=1,
        customs_days=0,
        domestic_days=1,
    ).model_dump(mode="json")
    lineage = [
        {
            "supplier_id": supplier,
            "assessment_version": 1,
            "eligibility": "ELIGIBLE",
            "due_diligence": {"outcome": "ALLOWED", "human_waivers": 0},
            "facts": {"country_code": "IN", "manufacturer_id": "fixture", "risk_score": "10"},
            "freshness": "fresh",
            "confidence": "80",
            "source_diversity": "2",
        }
    ]
    return context, request, lineage


def test_exact_engine_reuses_cost_components_without_float_rounding() -> None:
    values = {key: Decimal("0") for key in COST_KEYS}
    result = landed_cost(
        {**values, "unit_supplier_price": Decimal("0.1"), "freight": Decimal("0.2"), "quantity": 1},
        exact=True,
    )
    assert result["total_landed_cost"] == Decimal("0.300000")
    with pytest.raises(ValueError):
        landed_cost({"unit_supplier_price": Decimal("1"), "quantity": 1}, exact=True)


def test_cost_margin_capital_moq_lead_time_reconcile() -> None:
    context, request, lineage = inputs()
    result = calculate(context, request, lineage)
    assert result["missing_dimensions"] == []
    assert result["cost"]["total_landed_cost"] == "1000.000100"
    assert result["capital"]["estimated_total_initial_cash"] == "1050.000100"
    assert result["margin"]["per_unit_contribution"] == "6.999999"
    assert result["moq_feasibility"] == "FEASIBLE"
    assert result["lead_time"]["critical_path"] == 7
    assert result["concentration"]["largest_supplier_percent"] == "100.000000"
    assert "SINGLE_SUPPLIER_DEPENDENCY" in result["warnings"]


def test_unknown_cost_is_not_zero_or_comparable() -> None:
    context, request, lineage = inputs()
    del request["costs"]["freight"]
    result = calculate(context, request, lineage)
    assert result["cost"] is None
    assert "LOGISTICS_COST:freight" in result["missing_dimensions"]
    comparison = compare([{"id": "a", "result": result}])
    assert comparison["recommended_version_id"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", -1),
        ("quantity", True),
        ("unit_price", "NaN"),
        ("unit_price", "-1"),
        ("unit_price", "1e30"),
        ("currency", "inr"),
    ],
)
def test_invalid_allocation_rejected(field: str, value: object) -> None:
    _, request, _ = inputs()
    request["allocations"][0][field] = value
    with pytest.raises(ValidationError):
        ScenarioCreate.model_validate(request)


def test_allocation_sum_and_duplicate_rejected() -> None:
    context, request, lineage = inputs()
    request["allocations"][0]["quantity"] = 99
    with pytest.raises(ValueError, match="target quantity"):
        calculate(context, request, lineage)
    request["allocations"].append(request["allocations"][0])
    with pytest.raises(ValidationError):
        ScenarioCreate.model_validate(request)


def test_moq_exposure_and_critical_diligence_remain_visible() -> None:
    context, request, lineage = inputs()
    request["allocations"][0]["moq"] = 150
    lineage[0]["due_diligence"]["outcome"] = "BLOCKED"
    result = calculate(context, request, lineage)
    assert result["status"] == "BLOCKED"
    assert result["moq_feasibility"] == "INFEASIBLE"
    assert result["allocations"][0]["excess_units"] == 50
    assert result["capital"]["minimum_purchase_capital"] == "1500.000150"


def test_stale_or_absent_fx_never_converts() -> None:
    context, request, lineage = inputs()
    request["allocations"][0]["currency"] = "USD"
    result = calculate(context, request, lineage)
    assert "FX:USD" in result["missing_dimensions"]
    assert result["cost"] is None
    request["fx"] = [
        {
            "from_currency": "USD",
            "rate": "80",
            "reference": "local fixture",
            "observed_at": "2020-01-01T00:00:00Z",
            "valid_until": "2020-02-01T00:00:00Z",
        }
    ]
    assert calculate(context, request, lineage)["cost"] is None


def test_sensitivity_preserves_original_snapshot() -> None:
    settings, request, lineage = inputs()
    # Use whole amounts to keep sensitivity within six-place input precision.
    request["allocations"][0]["unit_price"] = "10"
    snapshot = {
        "settings": settings,
        "request": request,
        "lineage": lineage,
        "calculated_at": datetime.now(UTC).isoformat(),
    }
    before = deepcopy(snapshot)
    result = sensitivity(snapshot, "purchase", Decimal("10"))
    assert result["cost"]["total_landed_cost"] == "1100.000000"
    assert snapshot == before
    with pytest.raises(ValueError, match="band"):
        sensitivity(snapshot, "fx", Decimal("6"))


def test_comparison_is_explained_and_deterministic() -> None:
    settings, request, lineage = inputs()
    first = calculate(settings, request, lineage)
    request["allocations"][0]["unit_price"] = "12"
    second = calculate(settings, request, lineage)
    rows = [{"id": "a", "result": first}, {"id": "b", "result": second}]
    result = compare(rows)
    assert result == compare(rows)
    assert result["recommended_version_id"] == "a"
    assert sum(result["weights"].values()) == 100
    assert len(result["scenarios"][0]["dimensions"]) == 10
    assert "LOWEST_COST" in result["scenarios"][0]["labels"]


def test_missing_risk_and_manufacturer_never_get_invented_scores() -> None:
    settings, request, lineage = inputs()
    lineage[0]["facts"] = {}
    result = calculate(settings, request, lineage)
    assert result["supplier_risk"] is None
    assert result["resilience"]["score"] is None
    assert compare([{"id": "a", "result": result}])["recommended_version_id"] is None


def test_numeric_certification_reconciles_snapshot_without_float_drift() -> None:
    settings, request, lineage = inputs()
    at = datetime(2026, 1, 1, tzinfo=UTC)
    first = calculate(settings, request, lineage, at=at)
    assert first == calculate(settings, deepcopy(request), deepcopy(lineage), at=at)
    assert sum(Decimal(row["percentage"]) for row in first["allocations"]) == Decimal(100)
    assert sum(row["quantity"] for row in first["allocations"]) == settings["target_quantity"]
    total = Decimal(first["cost"]["total_landed_cost"])
    per_unit = Decimal(first["cost"]["landed_cost_per_unit"])
    assert per_unit * settings["target_quantity"] == total
    assert total == Decimal(first["allocations"][0]["base_unit_cost"]) * 100
    assert Decimal(first["capital"]["estimated_total_initial_cash"]) == total + Decimal(50)
    assert Decimal(first["margin"]["per_unit_contribution"]) == (
        Decimal(settings["target_sale_price"]) - per_unit - Decimal(3)
    )
    assert first["margin"]["break_even_units"] is None
    assert first["margin"]["break_even_limitation"]
    assert first["moq_feasibility"] == "FEASIBLE"
    assert first["allocations"][0]["required_purchase_units"] == 100
    assert first["lead_time"]["critical_path"] == 7
    assert not any(isinstance(value, float) for value in first["cost"].values())


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "-0.000001"])
def test_numeric_certification_rejects_nonfinite_or_negative_money(value: str) -> None:
    _, request, _ = inputs()
    request["costs"]["freight"] = value
    with pytest.raises(ValidationError):
        ScenarioCreate.model_validate(request)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "100.000001"])
def test_numeric_certification_rejects_invalid_percent(value: str) -> None:
    settings, _, _ = inputs()
    settings["margin_target"] = value
    with pytest.raises(ValidationError):
        ContextCreate.model_validate(settings)
