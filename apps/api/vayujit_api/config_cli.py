"""Safe configuration validation command for deployment prechecks."""

import json
import sys

from pydantic import ValidationError

from vayujit_api.core.config import Settings


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as error:
        errors = [
            {"type": item.get("type"), "location": item.get("loc"), "message": str(item.get("msg"))}
            for item in error.errors(include_url=False)
        ]
        print(json.dumps({"valid": False, "errors": errors}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {"valid": True, "configuration": settings.configuration_report()}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
