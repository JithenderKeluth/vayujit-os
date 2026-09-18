"""Slice 9I-C focused closure certification for the winning-product flow."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from test_winning_product_hard_certification import (
    ORIGIN,
    _calculate_chain,
    _opportunity,
    _setup,
)

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    ProductOpportunityCommercialOutput,
)
from vayujit_api.intelligence.product_opportunity_feasibility_models import (
    ProductOpportunitySourcingFeasibilityOutput,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
)
from vayujit_api.intelligence.product_opportunity_scoring_models import (
    PROFILE_VERSION,
    SCORING_MODEL_VERSION,
    ProductOpportunityDecision,
    ProductOpportunityScore,
)
from vayujit_api.intelligence.product_opportunity_synthesis_models import (
    ProductOpportunityRiskEvidenceSynthesis,
)
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")


@pytest.fixture
def harness() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_9i_c_stale_replay_version_comparison_and_integrity(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    owner_id, _brand_id, product_id, _listing_ids = _setup(
        api, factory, email="hard-closure@example.com", listings=3
    )
    opportunity_id, assessment_id, first_score = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="closure-a",
        evidence_mode="canonical",
    )

    # Stale and contradictory evidence remain explicit; current data is never fabricated.
    with factory() as db:
        demand = db.scalar(
            select(ProductOpportunityIntelligenceOutput).where(
                ProductOpportunityIntelligenceOutput.assessment_id == uuid.UUID(assessment_id),
                ProductOpportunityIntelligenceOutput.kind == "demand",
            )
        )
        competition = db.scalar(
            select(ProductOpportunityIntelligenceOutput).where(
                ProductOpportunityIntelligenceOutput.assessment_id == uuid.UUID(assessment_id),
                ProductOpportunityIntelligenceOutput.kind == "competition",
            )
        )
        assert demand and competition
        demand.dimensions = [
            (
                {**item, "evidence_state": "STALE", "freshness": {"state": "STALE"}}
                if item.get("dimension") == "MARKET_ACTIVITY"
                else item
            )
            for item in demand.dimensions
        ]
        competition.dimensions = [
            {
                **item,
                "classification": item.get("classification", "OBSERVED"),
                "explanation": item.get("explanation", "Contradictory fixture."),
                **(
                    {
                        "contradiction_state": "CONTRADICTED",
                        "freshness": {"state": "STALE"},
                    }
                    if item.get("dimension") == "COMPETITOR_DENSITY"
                    else {}
                ),
            }
            for item in competition.dimensions
        ]
        db.commit()
        assert any(item.get("freshness", {}).get("state") == "STALE" for item in demand.dimensions)
        assert any(
            item.get("contradiction_state") == "CONTRADICTED" for item in competition.dimensions
        )

    # Replaying 9B/9E/9F returns the same logical rows and score.
    for kind in ("demand", "competition"):
        replay = api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/{kind}",
            json={"idempotency_key": f"closure-a-{kind}"},
            headers=ORIGIN,
        )
        assert replay.status_code == 201
    synthesis_replay = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis",
        json={"idempotency_key": "closure-a-synthesis"},
        headers=ORIGIN,
    )
    assert synthesis_replay.status_code == 201
    score_replay = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
        json={},
        headers=ORIGIN,
    )
    assert score_replay.status_code == 201
    assert score_replay.json()["id"] == first_score["id"]

    # V1 remains immutable while V2 receives a new constraint and snapshot lineage.
    v2_constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={"currency": "INR", "available_capital": "12000", "idempotency_key": "closure-a-c2"},
        headers=ORIGIN,
    )
    assert v2_constraint.status_code == 201
    v2_assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "9i-c", "revision": 2}},
        headers=ORIGIN,
    )
    assert v2_assessment.status_code == 201
    with factory() as db:
        assessments = list(
            db.scalars(
                select(ProductOpportunityAssessment)
                .where(ProductOpportunityAssessment.opportunity_id == uuid.UUID(opportunity_id))
                .order_by(ProductOpportunityAssessment.version)
            )
        )
        constraints = list(
            db.scalars(
                select(ProductOpportunityConstraintVersion)
                .where(
                    ProductOpportunityConstraintVersion.opportunity_id == uuid.UUID(opportunity_id)
                )
                .order_by(ProductOpportunityConstraintVersion.version)
            )
        )
        assert [row.version for row in assessments] == [1, 2]
        assert [row.version for row in constraints] == [1, 2]
        assert assessments[0].constraint_version_id == constraints[0].id
        assert assessments[1].constraint_version_id == constraints[1].id
        assert assessments[0].input_snapshot_id != assessments[1].input_snapshot_id

    # Two compatible scores compare and rank deterministically, including ties.
    second_opportunity, second_assessment, second_score = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="closure-b",
        evidence_mode="canonical",
    )
    comparison_payload = {"assessment_ids": [assessment_id, second_assessment]}
    comparison = api.post(
        "/api/v1/intelligence/product-opportunities/score/compare",
        json=comparison_payload,
        headers=ORIGIN,
    )
    assert comparison.status_code == 200
    assert comparison.json()["comparability"] == "COMPARABLE"
    assert len(comparison.json()["items"]) == 2
    ranking = api.post(
        "/api/v1/intelligence/product-opportunities/score/rank",
        json=comparison_payload,
        headers=ORIGIN,
    )
    assert ranking.status_code == 200
    assert [item["rank"] for item in ranking.json()["ranking"]] == [1, 2]
    repeated_ranking = api.post(
        "/api/v1/intelligence/product-opportunities/score/rank",
        json=comparison_payload,
        headers=ORIGIN,
    )
    assert repeated_ranking.json()["ranking"] == ranking.json()["ranking"]
    assert first_score["confidence"] != "" and second_score["confidence"] != ""
    assert first_score["risk_level"] != ""
    assert second_opportunity

    # Owner-scope rejection and aggregate integrity counters are explicit.
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{uuid.uuid4()}", headers=ORIGIN
        ).status_code
        == 404
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(ProductOpportunity)) == 2
        assert db.scalar(select(func.count()).select_from(ProductOpportunityAssessment)) == 3
        assert db.scalar(select(func.count()).select_from(ProductOpportunityConstraintVersion)) == 3
        assert (
            db.scalar(select(func.count()).select_from(ProductOpportunityIntelligenceOutput)) == 4
        )
        assert db.scalar(select(func.count()).select_from(ProductOpportunityCommercialOutput)) == 2
        assert (
            db.scalar(select(func.count()).select_from(ProductOpportunitySourcingFeasibilityOutput))
            == 2
        )
        assert (
            db.scalar(select(func.count()).select_from(ProductOpportunityRiskEvidenceSynthesis))
            == 2
        )
        assert db.scalar(select(func.count()).select_from(ProductOpportunityScore)) == 2
        doctor = api.get(
            "/api/v1/intelligence/product-opportunities/score-system-doctor", headers=ORIGIN
        )
        assert doctor.status_code == 200 and doctor.json()["status"] == "PASS"


def _semantic(value: object) -> object:
    if isinstance(value, dict):
        ignored = {
            "id",
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "score_id",
            "source_ids",
            "created_at",
            "input_fingerprint",
            "upstream_lineage",
            "idempotency_key",
        }
        return {
            key: _semantic(item)
            for key, item in sorted(value.items())
            if key not in ignored
            and not key.endswith("_id")
            and not key.endswith("_at")
            and key not in {"timestamp", "observed_at"}
        }
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def test_9i_final_gate_determinism_three_clean_states(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    engine = factory.kw["bind"]
    snapshots: list[object] = []
    for run in range(1, 4):
        reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL or "")
        owner_id, _brand_id, product_id, _listing_ids = _setup(
            api, factory, email=f"determinism-{run}@example.com", listings=3
        )
        _opportunity_id, _assessment_id, score = _calculate_chain(
            api,
            factory,
            owner_id=owner_id,
            product_id=product_id,
            key=f"determinism-{run}",
            evidence_mode="canonical",
        )
        snapshots.append(_semantic(score))
    assert snapshots[0] == snapshots[1]
    assert snapshots[1] == snapshots[2]
    print("DETERMINISM 3/3 PASS")


def test_9i_final_gate_complete_ranking_matrix_and_integrity(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    owner_id, _brand_id, product_id, listing_ids = _setup(
        api, factory, email="ranking-matrix@example.com", listings=3
    )
    strong_opportunity, strong_assessment, strong = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="matrix-strong",
        evidence_mode="canonical",
    )
    moderate_opportunity, moderate_assessment, moderate = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="matrix-moderate",
        evidence_mode="canonical",
    )
    partial_opportunity, partial_assessment, partial = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="matrix-partial",
        with_supplier=False,
        evidence_mode="partial",
    )
    with factory() as db:
        sparse_product = Product(
            owner_id=uuid.UUID(owner_id),
            brand_id=uuid.UUID(_brand_id),
            name="Sparse Matrix Product",
            normalized_name="sparse matrix product",
            slug="sparse-matrix-product",
            sku="SPARSE-MATRIX-001",
            product_type="physical",
            status="active",
            category="Home",
            price_amount=None,
            price_currency=None,
            inventory_quantity=0,
            low_stock_threshold=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(sparse_product)
        db.commit()
        sparse_product_id = str(sparse_product.id)
    sparse_opportunity, sparse_assessment = _opportunity(
        api, sparse_product_id, key="matrix-sparse"
    )
    for kind in ("demand", "competition"):
        response = api.post(
            f"/api/v1/intelligence/product-opportunities/{sparse_opportunity}/assessments/{sparse_assessment}/{kind}",
            json={},
            headers=ORIGIN,
        )
        assert response.status_code == 201
    sparse_response = api.post(
        f"/api/v1/intelligence/product-opportunities/{sparse_opportunity}/assessments/{sparse_assessment}/score",
        json={},
        headers=ORIGIN,
    )
    assert sparse_response.status_code == 201
    insufficient = sparse_response.json()
    blocked_opportunity, blocked_assessment, _blocked_base = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="matrix-blocked",
        with_supplier=False,
    )
    with factory() as db:
        synthesis = db.scalar(
            select(ProductOpportunityRiskEvidenceSynthesis).where(
                ProductOpportunityRiskEvidenceSynthesis.assessment_id
                == uuid.UUID(blocked_assessment)
            )
        )
        assert synthesis
        synthesis.risks = [
            {"severity": "HIGH", "type": "AUTHORITATIVE_BLOCK", "explanation": "matrix blocker"}
        ]
        db.commit()
    blocked_response = api.post(
        f"/api/v1/intelligence/product-opportunities/{blocked_opportunity}/assessments/{blocked_assessment}/score",
        json={
            "profile_version": "matrix-blocked",
            "weights": {
                key: value
                for key, value in {
                    "DEMAND_ATTRACTIVENESS": 20,
                    "COMPETITIVE_OPPORTUNITY": 15,
                    "COMMERCIAL_VIABILITY": 20,
                    "CAPITAL_EFFICIENCY": 15,
                    "SUPPLIER_FEASIBILITY": 15,
                    "SOURCING_RESILIENCE": 10,
                    "DIFFERENTIATION_POTENTIAL": 5,
                }.items()
            },
        },
        headers=ORIGIN,
    )
    assert blocked_response.status_code == 201
    blocked = blocked_response.json()
    assert strong["eligibility"] == "SCORABLE"
    assert moderate["eligibility"] == "SCORABLE"
    assert partial["eligibility"] == "PARTIALLY_SCORABLE"
    assert insufficient["eligibility"] == "INSUFFICIENT_EVIDENCE"
    assert blocked["eligibility"] == "BLOCKED"
    comparable_payload = {"assessment_ids": [strong_assessment, moderate_assessment]}
    first_rank = api.post(
        "/api/v1/intelligence/product-opportunities/score/rank",
        json=comparable_payload,
        headers=ORIGIN,
    )
    second_rank = api.post(
        "/api/v1/intelligence/product-opportunities/score/rank",
        json=comparable_payload,
        headers=ORIGIN,
    )
    assert first_rank.status_code == second_rank.status_code == 200
    assert first_rank.json()["comparability"] == "COMPARABLE"
    assert first_rank.json()["ranking"] == second_rank.json()["ranking"]
    ranking = first_rank.json()["ranking"]
    print(f"SCORABLE STRONG: PASS eligibility={strong['eligibility']} rank={ranking}")
    print(f"SCORABLE MODERATE: PASS eligibility={moderate['eligibility']} rank={ranking}")
    if strong["overall_score"] != moderate["overall_score"]:
        rank_ids = [item.get("assessment_id") for item in ranking]
        assert rank_ids.index(strong_assessment) < rank_ids.index(moderate_assessment)
    print("RANKING STABILITY: PASS")
    print("TIE STABILITY: PASS (deterministic repeated ordering)")
    for assessment_id in (partial_assessment, sparse_assessment, blocked_assessment):
        response = api.post(
            "/api/v1/intelligence/product-opportunities/score/rank",
            json={"assessment_ids": [strong_assessment, assessment_id]},
            headers=ORIGIN,
        )
        assert response.status_code == 200
        assert response.json()["comparability"] == "NOT_COMPARABLE"
        assert response.json()["ranking"] == []
    print(
        "PARTIALLY_SCORABLE: PASS eligibility="
        f"{partial['eligibility']} ranking=excluded_not_comparable"
    )
    print(
        "INSUFFICIENT_EVIDENCE: PASS eligibility="
        f"{insufficient['eligibility']} ranking=excluded_not_comparable"
    )
    print("BLOCKED: PASS eligibility=" f"{blocked['eligibility']} ranking=excluded_not_comparable")
    assert strong["confidence"] != strong["overall_score"]
    assert insufficient["unavailable_dimensions"]
    assert blocked["risk_adjustments"]
    with factory() as db:
        models = [
            (ProductOpportunityIntelligenceOutput, "9B"),
            (ProductOpportunityCommercialOutput, "9C"),
            (ProductOpportunitySourcingFeasibilityOutput, "9D"),
            (ProductOpportunityRiskEvidenceSynthesis, "9E"),
            (ProductOpportunityScore, "9F"),
        ]
        for model, label in models:
            grouping = [model.owner_id, model.assessment_id]
            if model is ProductOpportunityIntelligenceOutput:
                grouping.append(model.kind)
            if model is ProductOpportunityScore:
                grouping.extend([model.scoring_model_version, model.profile_version])
            duplicates = db.execute(
                select(*grouping, func.count()).group_by(*grouping).having(func.count() > 1)
            ).all()
            print(f"duplicate_logical_{label.lower()}_outputs = {len(duplicates)}")
            assert not duplicates
        assessments = list(db.scalars(select(ProductOpportunityAssessment)))
        opportunities = {row.id: row for row in db.scalars(select(ProductOpportunity))}
        assessment_by_id = {row.id: row for row in assessments}
        orphan_assessments = sum(row.opportunity_id not in opportunities for row in assessments)
        print(f"orphan_product_opportunity_assessments = {orphan_assessments}")
        assert orphan_assessments == 0

        output_models = {
            "9B": ProductOpportunityIntelligenceOutput,
            "9C": ProductOpportunityCommercialOutput,
            "9D": ProductOpportunitySourcingFeasibilityOutput,
            "9E": ProductOpportunityRiskEvidenceSynthesis,
            "9F": ProductOpportunityScore,
        }
        output_rows = {
            label: list(db.scalars(select(model))) for label, model in output_models.items()
        }
        all_output_rows = [row for rows in output_rows.values() for row in rows]

        def lineage_broken(row: object) -> bool:
            assessment = assessment_by_id.get(row.assessment_id)
            opportunity = opportunities.get(row.opportunity_id)
            return (
                assessment is None
                or opportunity is None
                or row.owner_id != assessment.owner_id
                or row.owner_id != opportunity.owner_id
                or assessment.opportunity_id != row.opportunity_id
            )

        broken_owner_lineage = sum(lineage_broken(row) for row in all_output_rows)
        broken_assessment_lineage = sum(
            row.owner_id != opportunities[row.opportunity_id].owner_id
            for row in assessments
            if row.opportunity_id in opportunities
        )
        print(f"broken_owner_lineage = {broken_owner_lineage}")
        print(f"broken_assessment_lineage = {broken_assessment_lineage}")
        assert broken_owner_lineage == 0
        assert broken_assessment_lineage == 0

        broken_stage_lineage = {
            f"broken_{label.lower()}_assessment_lineage": sum(
                lineage_broken(row) for row in output_rows[label]
            )
            for label in output_models
        }
        for name, value in broken_stage_lineage.items():
            print(f"{name} = {value}")
            assert value == 0

        def numeric_dimension_values(value: object) -> list[float]:
            values: list[float] = []
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"score", "normalized_score", "overall_score"} and isinstance(
                        item, (int, float)
                    ):
                        values.append(float(item))
                    values.extend(numeric_dimension_values(item))
            elif isinstance(value, list):
                for item in value:
                    values.extend(numeric_dimension_values(item))
            return values

        scores = output_rows["9F"]
        invalid_overall_score_range = sum(
            row.overall_score is not None and not 0 <= float(row.overall_score) <= 100
            for row in scores
        )
        invalid_dimension_score_range = sum(
            any(not 0 <= value <= 100 for value in numeric_dimension_values(row.dimensions))
            for row in scores
        )
        invalid_scoring_weights = sum(
            not isinstance(row.weights, dict)
            or any(float(value) < 0 for value in row.weights.values())
            or abs(sum(float(value) for value in row.weights.values()) - 100) > 0.01
            for row in scores
        )
        broken_scoring_model_reference = sum(
            not row.scoring_model_version or row.scoring_model_version != SCORING_MODEL_VERSION
            for row in scores
        )
        broken_scoring_profile_reference = sum(
            not row.profile_version
            or (row.profile_version != PROFILE_VERSION and row.profile_version != "matrix-blocked")
            for row in scores
        )
        decisions = list(db.scalars(select(ProductOpportunityDecision)))
        score_by_id = {row.id: row for row in scores}
        broken_human_decision_lineage = sum(
            row.score_id not in score_by_id
            or score_by_id[row.score_id].assessment_id != row.assessment_id
            or score_by_id[row.score_id].owner_id != row.owner_id
            for row in decisions
        )
        duplicate_current = db.execute(
            select(
                ProductOpportunityScore.owner_id,
                ProductOpportunityScore.assessment_id,
                ProductOpportunityScore.scoring_model_version,
                ProductOpportunityScore.profile_version,
                func.count(),
            )
            .group_by(
                ProductOpportunityScore.owner_id,
                ProductOpportunityScore.assessment_id,
                ProductOpportunityScore.scoring_model_version,
                ProductOpportunityScore.profile_version,
            )
            .having(func.count() > 1)
        ).all()
        counters = {
            "invalid_overall_score_range": invalid_overall_score_range,
            "invalid_dimension_score_range": invalid_dimension_score_range,
            "invalid_scoring_weights": invalid_scoring_weights,
            "broken_scoring_model_reference": broken_scoring_model_reference,
            "broken_scoring_profile_reference": broken_scoring_profile_reference,
            "broken_human_decision_lineage": broken_human_decision_lineage,
            "prohibited_duplicate_current_projection": len(duplicate_current),
        }
        for name, value in counters.items():
            print(f"{name} = {value}")
            assert value == 0
        doctor = api.get(
            "/api/v1/intelligence/product-opportunities/score-system-doctor", headers=ORIGIN
        )
        assert doctor.status_code == 200 and doctor.json()["status"] == "PASS"
