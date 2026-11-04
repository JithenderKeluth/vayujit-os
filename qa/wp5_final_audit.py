"""Read-only audit of signed WP5 lifecycles, traces and original Docker resources."""

from qa.wp4_final_audit import main

if __name__ == "__main__":
    raise SystemExit(main("wp5"))
