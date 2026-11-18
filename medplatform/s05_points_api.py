"""Frozen C22–C25/C38–C39 points and management-review contracts."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import field_validator, model_validator

from .s02_inputs import DateTime, ID, Input, LocalDate, Short, Text, utc


class Reconcile(Input):
    patient_id: ID
    window_start: DateTime
    window_end: DateTime
    rules_version: Short

    @model_validator(mode="after")
    def ordered(self):
        if self.window_end <= self.window_start:
            raise ValueError("invalid reconciliation window")
        return self


class Review(Input):
    client_review_id: ID
    week_start: LocalDate
    reflection: Text | None = None
    confirmed_completed: Literal[True]

    @field_validator("confirmed_completed", mode="before")
    @classmethod
    def explicit_completion(cls, value):
        if value is not True:
            raise ValueError("completion must be a JSON boolean true")
        return value


ROUTES = [
    ("C22", "GET", "/patients/{p}/points", "account", None),
    ("C23", "GET", "/points/rules", "rules", None),
    ("C24", "GET", "/patients/{p}/points-ledger", "ledger", None),
    ("C25", "POST", "/internal/points/reconcile", "reconcile", Reconcile),
    ("C38", "POST", "/patients/{p}/management-reviews", "complete_review", Review),
    ("C39", "GET", "/patients/{p}/management-reviews", "reviews", None),
]


def query_input(action, pairs):
    query = dict(pairs)
    if len(query) != len(pairs):
        raise ValueError()
    if action == "rules":
        if set(query) - {"rules_version"} or not 1 <= len(query.get("rules_version", "-")) <= 200:
            raise ValueError()
        return query
    if action not in {"ledger", "reviews"}:
        if query:
            raise ValueError()
        return query
    if set(query) - {"window_start", "window_end", "cursor", "limit"}:
        raise ValueError()
    for field in ("window_start", "window_end"):
        query[field] = utc(query[field])
    left, right = (datetime.fromisoformat(query[field]) for field in ("window_start", "window_end"))
    if not timedelta() < right - left <= timedelta(days=31):
        raise ValueError()
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "limit" in query:
        raw = query["limit"]
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 3 or not 1 <= int(raw) <= 100:
            raise ValueError()
        query["limit"] = int(raw)
    return query
