from datetime import time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, field_validator, model_validator

from ..web.inputs import ID, DateTime, Input, LocalDate, Short, Text, Version


def local_time(value):
    if len(value) != 5 or time.fromisoformat(value).strftime("%H:%M") != value:
        raise ValueError("HH:mm required")
    return value


def positive_decimal(value):
    import re

    if (
        not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value)
        or not Decimal(value).is_finite()
        or Decimal(value) <= 0
    ):
        raise ValueError("positive decimal string required")
    result = (
        format(Decimal(value), "f").rstrip("0").rstrip(".")
        if "." in value
        else value.lstrip("0") or "0"
    )
    return result


LocalTime = Annotated[str, AfterValidator(local_time)]
Dose = Annotated[str, Field(max_length=80), AfterValidator(positive_decimal)]


class MedicationCreate(Input):
    name: Short
    notes: Text | None = None


class MedicationPatch(Input):
    expected_revision: Version
    name: Short | None = None
    notes: Text | None = None

    @field_validator("name", mode="before")
    @classmethod
    def nonnull(cls, value):
        if value is None:
            raise ValueError("name cannot be null")
        return value

    @model_validator(mode="after")
    def changes(self):
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("at least one change required")
        return self


class Schedule(Input):
    kind: Literal["daily", "weekly"]
    times: Annotated[list[LocalTime], Field(min_length=1)]
    weekdays: list[Annotated[int, Field(ge=1, le=7)]]

    @model_validator(mode="after")
    def valid(self):
        if (self.kind == "daily" and self.weekdays) or (
            self.kind == "weekly" and not self.weekdays
        ):
            raise ValueError("weekday mismatch")
        self.times = sorted(set(self.times))
        self.weekdays = sorted(set(self.weekdays))
        return self


class DraftEntry(Input):
    draft_entry_id: ID
    medication_id: ID
    dose_value: Dose | None
    dose_unit: Annotated[str, Field(min_length=1, max_length=40)] | None
    start_date: LocalDate | None
    end_date: LocalDate | None
    schedule: Schedule | None
    meal_requirement: Text | None
    medical_notes: Text | None
    strict_timing: bool | None
    min_interval_minutes: Annotated[int, Field(gt=0)] | None
    source_file_ids: list[ID]

    @model_validator(mode="after")
    def dates(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("invalid date interval")
        self.source_file_ids = sorted(set(self.source_file_ids))
        return self


class DraftCreate(Input):
    source_file_ids: list[ID] = Field(default_factory=list)
    entries: Annotated[list[DraftEntry], Field(min_length=1)]

    @model_validator(mode="after")
    def unique(self):
        if len({e.draft_entry_id for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate row ID")
        self.source_file_ids = sorted(set(self.source_file_ids))
        return self


class DraftPut(DraftCreate):
    expected_revision: Version
    source_file_ids: list[ID]


class DraftSubmit(Input):
    expected_revision: Version
    content_revision: Version


class PlanConfirm(Input):
    draft_id: ID
    draft_revision: Version
    existing_plan_id: ID | None
    expected_plan_version: Version | None
    effective_from: DateTime
    confirmed: Literal[True]

    @model_validator(mode="after")
    def version_pair(self):
        if (self.existing_plan_id is None) != (self.expected_plan_version is None):
            raise ValueError("plan/version pair required")
        return self


class Anchor(Input):
    event: Literal["wake", "breakfast", "bedtime", "custom"]
    label: Short | None
    local_time: LocalTime
    offset_minutes: Annotated[int, Field(ge=-60, le=60)]

    @model_validator(mode="after")
    def label_required(self):
        if self.event == "custom" and self.label is None:
            raise ValueError("custom label required")
        return self


class LocalWindow(Input):
    start: LocalTime
    end: LocalTime

    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start:
            raise ValueError("split overnight windows")
        return self


class ReminderSettings(Input):
    enabled: bool
    channels: list[Literal["in_app", "system_notification"]]
    sound_enabled: bool
    vibration_enabled: bool
    routine_mode: Literal[
        "regular", "night_shift", "rotating_shift", "travel", "custom"
    ]
    anchors: list[Anchor]
    privacy_enabled: bool
    custom_text: Short | None
    privacy_windows: list[LocalWindow]
    repeat_interval_minutes: Annotated[int, Field(ge=30, le=120)] | None
    max_repeats: Annotated[int, Field(ge=0, le=2)]
    snooze_minutes: Annotated[int, Field(ge=5, le=120)] | None
    notify_family: bool

    @model_validator(mode="after")
    def repeats(self):
        if (self.repeat_interval_minutes is None) != (self.max_repeats == 0):
            raise ValueError("repeat parameters mismatch")
        self.channels = sorted(set(self.channels))
        if not self.channels:
            raise ValueError("channel required")
        return self


class ReminderPut(Input):
    expected_revision: Annotated[int, Field(ge=0)]
    settings: ReminderSettings


class FileSemantic(Input):
    source_event_id: ID
    original_name: Short
    media_type: Literal["application/pdf", "image/png", "image/jpeg"]
    size_bytes: Annotated[int, Field(ge=1, le=10485760)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
