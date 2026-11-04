"""Fresh-process, read-only persisted reconstruction for the exact QA target."""

import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from qa.fixture_server import require_target


def probe() -> None:
    token = os.environ["QA_TOKEN"]
    name = f"vayujit_qa{token}_test"
    require_target(name, token)
    url = make_url(os.environ["QA_DATABASE_ADMIN_URL"])
    if url.host != "127.0.0.1" or url.database != "postgres":
        raise ValueError("QA_PROBE_TARGET_DENIED")
    engine = create_engine(url.set(database=name))
    result = {}
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        assert (
            connection.scalar(
                text("select suite_token from test_database_marker where marker_id=1")
            )
            == token
        )
        for table in (
            "users",
            "inventory_items",
            "inventory_movements",
            "inventory_reservations",
            "marketplace_orders",
            "financial_events",
            "financial_calculation_snapshots",
            "operational_signals",
        ):
            result[table] = connection.scalar(text(f"select count(*) from {table}"))
        result["invalid_inventory_balances"] = connection.scalar(
            text(
                "select count(*) from inventory_items where "
                "on_hand_quantity < reserved_quantity + damaged_quantity or reserved_quantity < 0"
            )
        )
        amounts = [
            dict(row)
            for row in connection.execute(
                text(
                    "select id::text as id,source_event_id,amount::text as amount "
                    "from financial_events order by source_event_id"
                )
            ).mappings()
        ]
        balances = [
            dict(row)
            for row in connection.execute(
                text(
                    "select id::text as id,on_hand_quantity,reserved_quantity,damaged_quantity "
                    "from inventory_items order by id"
                )
            ).mappings()
        ]
    engine.dispose()
    Path(os.environ["QA_RUN_DIR"], "fresh-process-proof.json").write_text(
        json.dumps(
            {
                "read_only": True,
                "token": token,
                "counts": result,
                "financial_amounts": amounts,
                "balances": balances,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    probe()
