"""Frozen C22–C25/C38–C39 points and management-review contracts."""

from typing import Literal

from pydantic import field_validator, model_validator

from ...web.inputs import (
    ID,
    DateTime,
    Input,
    LocalDate,
    Short,
    Text,
    query_fields,
    query_limit,
    query_text,
    query_window,
)


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
    allowed = (
        {"rules_version"}
        if action == "rules"
        else {"window_start", "window_end", "cursor", "limit"}
        if action in {"ledger", "reviews"}
        else set()
    )
    query = query_fields(pairs, allowed)
    if action == "rules":
        if not 1 <= len(query.get("rules_version", "-")) <= 200:
            raise ValueError()
        return query
    if action not in {"ledger", "reviews"}:
        return query
    query_window(query)
    if "cursor" in query:
        query_text(query["cursor"], 4096)
    if "limit" in query:
        query["limit"] = query_limit(query["limit"], 3)
    return query
