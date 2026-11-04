"""Read-only signed WP6A lifecycle/evidence audit, no deletion."""

from qa.wp4_final_audit import main

if __name__ == "__main__":
    raise SystemExit(main("wp6a"))
