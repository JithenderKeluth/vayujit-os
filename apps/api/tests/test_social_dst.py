from datetime import datetime

import pytest

from vayujit_api.publishing.scheduler_time import local_to_utc


def test_social_dst_normal_and_fold_resolution() -> None:
    normal = local_to_utc(datetime(2026, 1, 15, 10, 0), "America/New_York")
    fold_zero = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York", 0)
    fold_one = local_to_utc(datetime(2026, 11, 1, 1, 30), "America/New_York", 1)
    assert normal.isoformat().endswith("+00:00")
    assert fold_zero != fold_one


def test_social_dst_gap_and_timezone_are_rejected() -> None:
    with pytest.raises(ValueError):
        local_to_utc(datetime(2026, 3, 8, 2, 30), "America/New_York")
    with pytest.raises(ValueError):
        local_to_utc(datetime(2026, 1, 15, 10, 0), "Not/A-Timezone")
