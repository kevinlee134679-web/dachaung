from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utc(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone required")
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def query_fields(pairs, allowed):
    query = dict(pairs)
    if len(query) != len(pairs) or set(query) - allowed:
        raise ValueError()
    return query


def query_text(value, maximum):
    if not 1 <= len(value) <= maximum:
        raise ValueError()


def query_limit(value, maximum_length=None):
    if (
        not value.isascii()
        or not value.isdigit()
        or maximum_length is not None
        and len(value) > maximum_length
        or not 1 <= int(value) <= 100
    ):
        raise ValueError()
    return int(value)


def query_window(query):
    for field in ("window_start", "window_end"):
        query[field] = utc(query[field])
    seconds = (
        datetime.fromisoformat(query["window_end"])
        - datetime.fromisoformat(query["window_start"])
    ).total_seconds()
    if not 0 < seconds <= 31 * 86400:
        raise ValueError()


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
