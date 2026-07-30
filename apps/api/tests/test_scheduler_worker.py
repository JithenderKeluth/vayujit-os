from vayujit_api.publishing.job_queue import retry_delay
from vayujit_api.publishing.worker import default_worker_id


def test_retry_delay_is_bounded() -> None:
    assert 30 <= retry_delay(1, jitter=False) <= 3600
    assert retry_delay(99, jitter=False) == 3600


def test_default_worker_identifier_does_not_expose_host_or_process() -> None:
    value = default_worker_id()
    assert value.startswith("worker-")
    assert ":" not in value and "\\" not in value and "/" not in value
