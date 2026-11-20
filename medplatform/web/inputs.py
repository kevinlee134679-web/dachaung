from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utc(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone required")
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def local_date(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("YYYY-MM-DD required")
    return value


ID = Annotated[str, Field(min_length=1, max_length=128)]
Short = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Reason = Annotated[str, Field(min_length=1, max_length=500)]
Version = Annotated[int, Field(ge=1)]
DateTime = Annotated[str, AfterValidator(utc)]
LocalDate = Annotated[str, AfterValidator(local_date)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if (
            isinstance(value, dict)
            and "confirmed" in value
            and value["confirmed"] is not True
        ):
            raise ValueError("explicit boolean confirmation required")
        return value


class Empty(Input):
    pass


class Revoke(Input):
    expected_revision: Version
    reason: Reason
