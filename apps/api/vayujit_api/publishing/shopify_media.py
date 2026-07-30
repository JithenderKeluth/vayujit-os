from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

MediaState = Literal[
    "uploaded", "processing", "ready", "failed", "unknown", "timed_out", "cancelled"
]
ReuseState = Literal[
    "reusable", "stale", "missing", "processing", "failed", "inaccessible", "unknown"
]


@dataclass(frozen=True)
class MediaPollPolicy:
    maximum_duration_seconds: float = 60
    initial_interval_seconds: float = 1
    maximum_interval_seconds: float = 5
    maximum_attempts: int = 12


@dataclass(frozen=True)
class MediaPollObservation:
    attempt: int
    state: MediaState
    delay_seconds: float
    latency_seconds: float
    remote_url: str | None = None
    safe_error: str | None = None


@dataclass(frozen=True)
class MediaPollResult:
    state: MediaState
    observations: tuple[MediaPollObservation, ...]
    remote_url: str | None = None


DEFAULT_MEDIA_POLL_POLICY = MediaPollPolicy()


def normalize_media_state(value: object) -> MediaState:
    state = str(value or "unknown").strip().casefold()
    if state in {"uploaded", "processing", "ready", "failed"}:
        return state  # type: ignore[return-value]
    return "unknown"


def poll_media(
    fetch: Callable[[], dict[str, object]],
    *,
    policy: MediaPollPolicy = DEFAULT_MEDIA_POLL_POLICY,
    clock: Callable[[], float],
    delay: Callable[[float], None],
    cancelled: Callable[[], bool] = lambda: False,
    observe: Callable[[MediaPollObservation], None] = lambda _value: None,
) -> MediaPollResult:
    if policy.maximum_attempts < 1:
        raise ValueError("Media polling requires at least one attempt.")
    started = clock()
    observations: list[MediaPollObservation] = []
    interval = max(policy.initial_interval_seconds, 0)
    for attempt in range(1, policy.maximum_attempts + 1):
        if cancelled():
            return MediaPollResult("cancelled", tuple(observations))
        request_started = clock()
        payload = fetch()
        latency = max(clock() - request_started, 0)
        state = normalize_media_state(payload.get("status"))
        elapsed = max(clock() - started, 0)
        terminal = state in {"ready", "failed"}
        exhausted = attempt == policy.maximum_attempts or elapsed >= policy.maximum_duration_seconds
        sleep_for = 0.0
        if not terminal and not exhausted:
            sleep_for = min(interval, policy.maximum_interval_seconds)
            if elapsed + sleep_for > policy.maximum_duration_seconds:
                sleep_for = max(policy.maximum_duration_seconds - elapsed, 0)
        observation = MediaPollObservation(
            attempt,
            state,
            sleep_for,
            latency,
            str(payload.get("url") or "") or None,
            str(payload.get("safe_error") or "") or None,
        )
        observations.append(observation)
        observe(observation)
        if terminal:
            return MediaPollResult(state, tuple(observations), observation.remote_url)
        if exhausted:
            return MediaPollResult("timed_out", tuple(observations))
        delay(sleep_for)
        interval = min(
            max(interval * 2, policy.initial_interval_seconds),
            policy.maximum_interval_seconds,
        )
    return MediaPollResult("timed_out", tuple(observations))


def decide_media_reuse(
    *,
    destination_matches: bool,
    shop_matches: bool,
    checksum_matches: bool,
    remote_exists: bool | None,
    remote_accessible: bool,
    remote_product_matches: bool,
    remote_status: object,
) -> ReuseState:
    if not remote_accessible:
        return "inaccessible"
    if (
        not destination_matches
        or not shop_matches
        or not checksum_matches
        or not remote_product_matches
    ):
        return "stale"
    if remote_exists is False:
        return "missing"
    if remote_exists is None:
        return "unknown"
    state = normalize_media_state(remote_status)
    if state == "ready":
        return "reusable"
    if state in {"uploaded", "processing"}:
        return "processing"
    if state == "failed":
        return "failed"
    return "unknown"
