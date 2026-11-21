"""Strict A10-A27 inputs; original text and source identity remain distinct."""

import math
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from ..web.inputs import ID, DateTime, Input, Revoke, Short, Text, Version


class RecordInput(Input):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)


class PlanRef(RecordInput):
    plan_id: ID
    plan_version: Version


class EvidencePayload(RecordInput):
    reported_status: Literal["taken", "not_taken", "postponed", "unknown"] | None
    observation: Literal["box_opened", "inferred_intake"] | None
    medication_id: ID | None
    dose_slot_id: ID | None
    plan_ref: PlanRef | None
    raw_text: Text | None

    @model_validator(mode="after")
    def one_kind(self):
        if (self.reported_status is None) == (self.observation is None):
            raise ValueError("exactly one report or observation required")
        return self


class MeasurementPayload(RecordInput):
    metric_code: Short
    value: int | float | None
    unit: Annotated[str, Field(min_length=1, max_length=40)] | None
    method_code: Short | None
    missing_reason: Annotated[str, Field(min_length=1, max_length=500)] | None

    @model_validator(mode="after")
    def valid_value(self):
        if self.value is not None and (
            isinstance(self.value, bool) or not math.isfinite(self.value)
        ):
            raise ValueError("finite numeric value required")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError(
                "missing values require a reason; observed values have none"
            )
        if self.missing_reason is not None and not self.missing_reason.strip():
            raise ValueError("missing reason cannot be blank")
        return self


class MedicationEventInput(RecordInput):
    source_event_id: ID
    occurred_at: DateTime
    reported_status: Literal["taken", "not_taken", "postponed", "unknown"]
    medication_id: ID | None = None
    dose_slot_id: ID | None = None
    plan_ref: PlanRef | None = None
    raw_text: Text | None = None


class MeasurementInput(RecordInput):
    source_event_id: ID
    occurred_at: DateTime
    payload: MeasurementPayload


class CorrectionInput(RecordInput):
    expected_revision: Version
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    occurred_at: DateTime
    payload: EvidencePayload | MeasurementPayload

    @model_validator(mode="after")
    def reason_present(self):
        if not self.reason.strip():
            raise ValueError("reason cannot be blank")
        return self


class WithdrawalInput(RecordInput):
    expected_revision: Version
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def reason_present(self):
        if not self.reason.strip():
            raise ValueError("reason cannot be blank")
        return self


class ReprocessInput(RecordInput):
    expected_revision: Version


class DeviceBindingInput(RecordInput):
    device_id: ID
    confirmed: Literal[True]


class DeviceEventInput(RecordInput):
    device_id: ID
    source_event_id: ID
    occurred_at: DateTime
    event_kind: Literal["medication", "measurement"]
    payload: EvidencePayload | MeasurementPayload

    @model_validator(mode="after")
    def payload_matches_kind(self):
        if (self.event_kind == "medication") != isinstance(
            self.payload, EvidencePayload
        ):
            raise ValueError("event payload kind mismatch")
        if (
            isinstance(self.payload, EvidencePayload)
            and self.payload.reported_status is not None
        ):
            raise ValueError("devices cannot report as a patient")
        return self


class DemoDeviceInput(RecordInput):
    patient_id: ID
    device_id: ID
    scenario: Literal[
        "normal_box",
        "duplicate",
        "late_upload",
        "measurement_missing",
        "unknown_unit",
        "unbound",
    ]
    scenario_run_id: ID
    occurred_at: DateTime


class MatchReviewInput(WithdrawalInput):
    event_id: ID
    dose_slot_id: ID | None


DeviceRevokeInput = Revoke
