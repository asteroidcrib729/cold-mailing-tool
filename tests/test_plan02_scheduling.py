import json
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from cold_mailer.domain.models import ValidationError
from cold_mailer.domain.scheduling import SendWindow
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def stamp(value: str) -> float:
    return datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp()


def test_daylight_saving_gap_and_both_fold_instants() -> None:
    spring = SendWindow(True, "America/New_York", 150, 210, (6,))
    assert spring.next_time({}, stamp("2026-03-08T06:59:00")) == datetime(
        2026, 3, 8, 7, 0, tzinfo=UTC
    )
    autumn = SendWindow(True, "America/New_York", 60, 90, (6,))
    assert autumn.allows({}, stamp("2026-11-01T05:15:00"))
    assert autumn.allows({}, stamp("2026-11-01T06:15:00"))
    assert not autumn.allows({}, stamp("2026-11-01T06:30:00"))


def test_overnight_window_belongs_to_its_start_day_and_unknown_zone_holds() -> None:
    policy = SendWindow(True, "UTC", 22 * 60, 2 * 60, (4,))
    assert policy.allows({}, stamp("2026-10-23T22:00:00"))
    assert policy.allows({}, stamp("2026-10-24T01:59:00"))
    assert not policy.allows({}, stamp("2026-10-24T02:00:00"))
    per_contact = SendWindow(True, "UTC", 540, 1020, (0, 1, 2, 3, 4), True)
    assert per_contact.next_time({}, stamp("2026-10-20T10:00:00")) is None
    assert not per_contact.allows({"timezone": "unknown"}, stamp("2026-10-20T10:00:00"))
    assert per_contact.allows({"timezone": "Asia/Karachi"}, stamp("2026-10-20T10:00:00"))
    assert SendWindow().allows({}, 0)


@pytest.mark.parametrize(
    "raw",
    [
        '{"timezone":"invalid"}',
        '{"days":[]}',
        '{"start_minute":0,"end_minute":0}',
        '{"days":[7]}',
        '{"enabled":"true"}',
        '{"start_minute":1440}',
        "not-json",
    ],
)
def test_invalid_window_policy_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        SendWindow.load(raw)


def test_claim_enforces_window_without_changing_approved_content(rig: Rig) -> None:
    message = rig.message()
    policy = SendWindow(True, "UTC", 540, 1020, (0, 1, 2, 3, 4))
    rig.store.save_preference("sending.window", json.dumps(asdict(policy)))
    assert rig.store.claim(message.id, stamp("2026-10-20T21:00:00")) is None
    assert rig.store.message(message.id).approval == message.approval
    assert rig.store.claim(message.id, stamp("2026-10-21T09:00:00"))
