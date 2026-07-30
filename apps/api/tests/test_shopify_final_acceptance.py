from collections.abc import Iterator

import pytest

from vayujit_api.publishing.shopify_media import (
    MediaPollObservation,
    MediaPollPolicy,
    decide_media_reuse,
    poll_media,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def delay(self, seconds: float) -> None:
        self.value += seconds


def responses(*states: str) -> Iterator[dict[str, object]]:
    for state in states:
        yield {"status": state, "url": "https://cdn.shopify.com/media.jpg"}


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (("UPLOADED", "PROCESSING", "READY"), "ready"),
        (("PROCESSING", "FAILED"), "failed"),
    ],
)
def test_media_polling_reaches_terminal_state(states: tuple[str, ...], expected: str) -> None:
    clock = FakeClock()
    source = responses(*states)
    observed: list[MediaPollObservation] = []
    result = poll_media(
        lambda: next(source),
        clock=clock.now,
        delay=clock.delay,
        observe=observed.append,
    )
    assert result.state == expected
    assert len(result.observations) == len(states)
    assert observed[-1].state == expected


def test_media_polling_is_bounded_without_real_sleep() -> None:
    clock = FakeClock()
    result = poll_media(
        lambda: {"status": "PROCESSING"},
        policy=MediaPollPolicy(
            maximum_duration_seconds=10,
            initial_interval_seconds=1,
            maximum_interval_seconds=4,
            maximum_attempts=4,
        ),
        clock=clock.now,
        delay=clock.delay,
    )
    assert result.state == "timed_out"
    assert len(result.observations) == 4
    assert [item.delay_seconds for item in result.observations] == [1, 2, 4, 0]
    assert clock.value == 7


def test_media_polling_honors_local_cancellation() -> None:
    clock = FakeClock()
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    result = poll_media(
        lambda: {"status": "PROCESSING"},
        clock=clock.now,
        delay=clock.delay,
        cancelled=cancelled,
    )
    assert result.state == "cancelled"
    assert len(result.observations) == 1


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "reusable"),
        ({"checksum_matches": False}, "stale"),
        ({"shop_matches": False}, "stale"),
        ({"destination_matches": False}, "stale"),
        ({"remote_product_matches": False}, "stale"),
        ({"remote_exists": False}, "missing"),
        ({"remote_exists": None}, "unknown"),
        ({"remote_accessible": False}, "inaccessible"),
        ({"remote_status": "PROCESSING"}, "processing"),
        ({"remote_status": "FAILED"}, "failed"),
        ({"remote_status": "FUTURE_STATE"}, "unknown"),
    ],
)
def test_remote_media_reuse_is_safe(changes: dict[str, object], expected: str) -> None:
    values: dict[str, object] = {
        "destination_matches": True,
        "shop_matches": True,
        "checksum_matches": True,
        "remote_exists": True,
        "remote_accessible": True,
        "remote_product_matches": True,
        "remote_status": "READY",
    }
    values.update(changes)
    assert decide_media_reuse(**values) == expected  # type: ignore[arg-type]
