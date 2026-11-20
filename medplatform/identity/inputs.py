from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from ..web.inputs import ID, DateTime, Input, Short, Version


class Login(Input):
    demo_account_id: ID


class CurrentPatient(Input):
    patient_id: ID


class PatientPatch(Input):
    expected_revision: Version
    display_name: Short | None = None
    timezone: str | None = None

    @field_validator("display_name", "timezone", mode="before")
    @classmethod
    def nonnull(cls, value):
        if value is None:
            raise ValueError("explicit null forbidden")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("IANA timezone required") from None
        return value

    @model_validator(mode="after")
    def has_change(self):
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("at least one change required")
        return self


class Redeem(Input):
    binding_code: Annotated[str, Field(min_length=12, max_length=64)]


SCOPES = {
    "patient:read",
    "patient:edit",
    "questionnaire:read",
    "questionnaire:assist",
    "profile:read",
    "medication:read",
    "medication:edit",
    "plan:read",
    "plan:confirm",
    "reminder:read",
    "reminder:write",
    "records:read",
    "records:report",
    "notify:receive",
    "files:read",
    "files:write",
    "drafts:read",
    "drafts:write",
    "drafts:submit",
    "measurements:read",
    "measurements:write",
    "records:correct",
    "devices:manage",
    "statistics:read",
    "summary:read",
    "feedback:read",
    "tasks:read",
    "dialogue:read",
    "dialogue:write",
    "assessment:read",
    "assessment:write",
    "interventions:read",
    "mode:write",
    "knowledge:read",
    "knowledge:manage",
    "knowledge:review",
    "exports:read",
    "demo:manage",
    "support:read",
    "services:prepare",
    "services:read",
    "services:apply",
    "service-feedback:write",
    "peer:read",
    "peer:participate",
    "points:read",
    "rewards:redeem",
}


class GrantPut(Input):
    expected_revision: Annotated[int, Field(ge=0)]
    scopes: list[str]
    valid_until: DateTime | None
    confirmed: Literal[True]

    @field_validator("scopes")
    @classmethod
    def valid_scopes(cls, value):
        if set(value) - SCOPES or set(value) & {
            "demo:manage",
            "knowledge:manage",
            "knowledge:review",
        }:
            raise ValueError("unknown or non-transferable scope")
        return sorted(set(value))
