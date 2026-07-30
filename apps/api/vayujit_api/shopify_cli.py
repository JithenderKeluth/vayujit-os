import argparse
import json
import sys
from typing import Literal, cast

from sqlalchemy import select

from vayujit_api.core.database import SessionFactory
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import PublishingExecution
from vayujit_api.publishing.shopify import connector_for, owned_configuration, response_for


def output(**values: object) -> None:
    print(json.dumps(values, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["status", "validate", "collections", "publications", "executions"],
    )
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
            if args.command == "executions":
                rows = db.scalars(
                    select(PublishingExecution)
                    .where(
                        PublishingExecution.owner_id == owner.id,
                        PublishingExecution.connector_key == "shopify",
                    )
                    .order_by(PublishingExecution.created_at.desc())
                    .limit(100)
                ).all()
                output(
                    status="PASS",
                    executions=[
                        {
                            "id": row.id,
                            "status": row.status,
                            "remote_entity_id": row.remote_entity_id,
                            "remote_status": row.remote_status,
                            "reconciliation_status": row.reconciliation_status,
                        }
                        for row in rows
                    ],
                )
                return 0
            if configuration is None:
                raise RuntimeError("Shopify is not configured.")
            client = connector_for(configuration)
            if args.command == "validate":
                shop = client.validate().get("shop")
                output(
                    status="PASS",
                    connector="shopify",
                    shop_domain=configuration.shop_domain,
                    api_version=configuration.api_version,
                    shop_id=shop.get("id") if isinstance(shop, dict) else None,
                )
                return 0
            data = client.discover(
                cast(Literal["collections", "publications"], args.command),
                first=25,
                after=None,
            )
            connection = data.get(args.command)
            nodes = connection.get("nodes", []) if isinstance(connection, dict) else []
            output(
                status="PASS",
                connector="shopify",
                kind=args.command,
                count=len(nodes) if isinstance(nodes, list) else 0,
            )
            return 0
    except Exception as error:
        output(status="FAIL", message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
