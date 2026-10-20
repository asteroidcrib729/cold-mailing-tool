"""Explicit local-time admission windows evaluated from UTC, including DST folds/gaps."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cold_mailer.domain.models import ValidationError


@dataclass(frozen=True)
class SendWindow:
    enabled: bool = False
    timezone: str = "UTC"
    start_minute: int = 540
    end_minute: int = 1020
    days: tuple[int, ...] = (0, 1, 2, 3, 4)
    use_contact_timezone: bool = False

    @classmethod
    def load(cls, raw: str) -> SendWindow:
        try:
            data = json.loads(raw)
            if "days" in data:
                data["days"] = tuple(data["days"])
            value = cls(**data)
            value.validate()
            return value
        except TypeError, ValueError, KeyError:
            raise ValidationError(
                "Sending-window settings are invalid. Review them in Campaign tools."
            ) from None

    def validate(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ValueError, ZoneInfoNotFoundError:
            raise ValidationError(
                "Choose a valid IANA timezone, such as Asia/Karachi or Europe/London."
            ) from None
        if (
            type(self.enabled) is not bool
            or type(self.use_contact_timezone) is not bool
            or type(self.start_minute) is not int
            or type(self.end_minute) is not int
            or not 0 <= self.start_minute < 1440
            or not 0 <= self.end_minute < 1440
            or self.start_minute == self.end_minute
            or not self.days
            or len(set(self.days)) != len(self.days)
            or any(type(day) is not int or not 0 <= day <= 6 for day in self.days)
        ):
            raise ValidationError("Use distinct start/end times and at least one valid weekday.")

    def zone(self, contact: dict[str, str]) -> ZoneInfo | None:
        name = contact.get("timezone", "").strip() if self.use_contact_timezone else self.timezone
        if not name:
            return None
        try:
            return ZoneInfo(name)
        except ValueError, ZoneInfoNotFoundError:
            return None

    def allows(self, contact: dict[str, str], now: float) -> bool:
        if not self.enabled:
            return True
        zone = self.zone(contact)
        if zone is None:
            return False
        local = datetime.fromtimestamp(now, UTC).astimezone(zone)
        minute = local.hour * 60 + local.minute
        if self.start_minute < self.end_minute:
            return local.weekday() in self.days and self.start_minute <= minute < self.end_minute
        return (minute >= self.start_minute and local.weekday() in self.days) or (
            minute < self.end_minute and (local.weekday() - 1) % 7 in self.days
        )

    def next_time(self, contact: dict[str, str], now: float) -> datetime | None:
        if self.allows(contact, now):
            return datetime.fromtimestamp(now, UTC)
        if self.zone(contact) is None:
            return None
        # Walk UTC instants instead of constructing nonexistent/ambiguous local times.
        start = math.ceil(now / 60) * 60
        for minute in range(8 * 24 * 60):
            instant = start + minute * 60
            if self.allows(contact, instant):
                return datetime.fromtimestamp(instant, UTC)
        return None
