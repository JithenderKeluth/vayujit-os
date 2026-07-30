import argparse
import json
import sys

from sqlalchemy import func, select

from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
)
from vayujit_api.publishing.wordpress import (
    connector_for,
    owned_configuration,
    response_for,
)


def output(**values: object) -> None:
    print(json.dumps(values, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["status", "validate", "destinations", "executions", "reconcile"]
    )
    parser.add_argument("--execution-id")
    args = parser.parse_args()
    try:
        with SessionFactory() as db:
            owner = db.scalar(select(User).order_by(User.created_at).limit(1))
            if owner is None:
                raise RuntimeError("No local owner exists.")
            configuration = owned_configuration(db, owner.id)
            if args.command == "status":
                output(status="PASS", **response_for(configuration).model_dump(mode="json"))
                return 0
            if args.command == "validate":
                if configuration is None:
                    raise RuntimeError("WordPress is not configured.")
                remote_user = connector_for(configuration).validate()
                output(
                    status="PASS",
                    connector="wordpress",
                    remote_user_id=remote_user.get("id"),
                    site_url=configuration.site_url,
                )
                return 0
            if args.command == "destinations":
                rows = db.execute(
                    select(
                        PublishingDestination.connector_key,
                        func.count(PublishingDestination.id),
                    )
                    .where(PublishingDestination.owner_id == owner.id)
                    .group_by(PublishingDestination.connector_key)
                ).all()
                output(status="PASS", destinations={key: count for key, count in rows})
                return 0
            query = select(PublishingExecution).where(
                PublishingExecution.owner_id == owner.id,
                PublishingExecution.connector_key == "wordpress",
            )
            if args.command == "reconcile":
                if not args.execution_id:
                    raise RuntimeError("--execution-id is required for reconcile.")
                query = query.where(PublishingExecution.id == args.execution_id)
            executions = db.scalars(
                query.order_by(PublishingExecution.created_at.desc()).limit(100)
            ).all()
            output(
                status="PASS",
                executions=[
                    {
                        "id": value.id,
                        "status": value.status,
                        "remote_entity_id": value.remote_entity_id,
                        "remote_status": value.remote_status,
                        "reconciliation_status": value.reconciliation_status,
                    }
                    for value in executions
                ],
                note=(
                    "Use the authenticated API reconciliation action to mutate remote state."
                    if args.command == "reconcile"
                    else None
                ),
            )
            return 0
    except Exception as error:
        output(status="FAIL", message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
