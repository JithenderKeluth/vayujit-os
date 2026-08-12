from pathlib import Path


def _source(relative: str) -> str:
    root = Path(__file__).parents[3]
    return (root / relative).read_text(encoding="utf-8")


def test_social_static_accessibility_contract() -> None:
    workspace = _source("apps/web/src/app/social/social-workspace.component.ts")
    calendar = _source("apps/web/src/app/campaigns/content-calendar.component.ts")
    assert "aria-labelledby" in workspace
    assert "aria-label" in workspace
    assert 'role="alert"' in workspace
    assert 'aria-live="polite"' in calendar
    assert "<table>" in workspace
    assert 'scope="col"' in workspace
    assert "routerLink" in workspace
    for label in ("Overview", "Compose", "Calendar", "Accounts", "Analytics", "Recovery"):
        assert label in workspace or label in calendar


def test_social_static_responsive_contract() -> None:
    workspace = _source("apps/web/src/app/social/social-workspace.component.ts")
    calendar_css = _source("apps/web/src/app/campaigns/campaigns.css")
    assert "@media (max-width: 640px)" in workspace
    assert "overflow-x: auto" in workspace
    assert "flex-wrap: wrap" in workspace
    assert "grid-template-columns" in workspace
    assert "@media" in calendar_css
    assert "minmax(" in calendar_css
