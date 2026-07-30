import argparse
import json
import sys

from sqlalchemy import func, select

from vayujit_api.ai.configuration import (
    credential_for,
    discover_models,
    owned_configuration,
)
from vayujit_api.ai.credentials import CredentialError
from vayujit_api.ai.models import AIGenerationRequest
from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User


def output(**values: object) -> None:
    print(json.dumps(values, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "validate", "usage-summary"])
    args = parser.parse_args()
    try:
        with SessionFactory() as db:
            owner = db.scalar(select(User).order_by(User.created_at).limit(1))
            if owner is None:
                raise RuntimeError("No local owner exists.")
            configuration = owned_configuration(db, owner.id)
            if args.command == "status":
                source = "not_configured"
                configured = False
                try:
                    credential, source = credential_for(configuration)
                    configured = credential is not None
                except CredentialError:
                    source = "unreadable"
                output(
                    status="PASS",
                    provider="openai_compatible",
                    configured=configured,
                    enabled=configuration.enabled if configuration else False,
                    credential_source=source,
                    model=configuration.default_model if configuration else None,
                    validation_status=(
                        configuration.validation_status if configuration else "unknown"
                    ),
                )
                return 0
            if args.command == "validate":
                if configuration is None:
                    raise RuntimeError("Real provider is not configured.")
                models = discover_models(db, owner.id, refresh=True)
                valid = any(item.identifier == configuration.default_model for item in models)
                output(
                    status="PASS" if valid else "FAIL",
                    provider="openai_compatible",
                    model=configuration.default_model,
                    discovered_models=len(models),
                    valid=valid,
                )
                return 0 if valid else 1
            totals = db.execute(
                select(
                    func.count(AIGenerationRequest.id),
                    func.coalesce(func.sum(AIGenerationRequest.input_tokens), 0),
                    func.coalesce(func.sum(AIGenerationRequest.output_tokens), 0),
                    func.coalesce(func.sum(AIGenerationRequest.total_tokens), 0),
                    func.sum(AIGenerationRequest.estimated_total_cost),
                ).where(AIGenerationRequest.owner_id == owner.id)
            ).one()
            output(
                status="PASS",
                requests=totals[0],
                input_tokens=totals[1],
                output_tokens=totals[2],
                total_tokens=totals[3],
                estimated_cost=str(totals[4]) if totals[4] is not None else None,
            )
            return 0
    except Exception as error:
        output(status="FAIL", message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
