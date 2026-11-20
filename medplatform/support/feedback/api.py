"""C13–C15 request fields and strict feedback-window query handling."""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ...web.inputs import ID, Input, Reason, Text, utc

DIMENSIONS = ("support_needs", "support_acceptance", "intervention_effectiveness")


class ServiceFeedbackInput(Input):
    client_feedback_id: ID
    expected_feedback_revision: Annotated[int, Field(ge=0)]
    participation: Literal["provided", "declined", "unable"]
    support_needs: Text | None
    support_acceptance: Text | None
    intervention_effectiveness: Text | None
    willing_to_continue: bool | None
    missing_reason: Reason | None

    @model_validator(mode="after")
    def participation_content(self):
        has_description = any(getattr(self, name) is not None for name in DIMENSIONS)
        if self.participation == "provided":
            if not has_description:
                raise ValueError("provide at least one description")
        elif has_description or self.missing_reason is None:
            raise ValueError("record the reason for not providing descriptions")
        return self


ROUTES = [
    ("C13", "POST", "/services/{id}/feedback", "save_feedback", ServiceFeedbackInput),
    ("C14", "GET", "/services/{id}/feedback", "feedback_history", None),
    ("C15", "GET", "/patients/{p}/support-feedback", "feedback_source", None),
]


def query_input(action, pairs):
    query = dict(pairs)
    paging = {"cursor", "limit"}
    window = {"window_start", "window_end"} if action == "feedback_source" else set()
    if len(query) != len(pairs) or set(query) - (
        set() if action == "save_feedback" else paging | window
    ):
        raise ValueError()
    for field in window:
        query[field] = utc(query[field])
    if window:
        left, right = (
            datetime.fromisoformat(query[key]) for key in ("window_start", "window_end")
        )
        if not timedelta() < right - left <= timedelta(days=31):
            raise ValueError()
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "limit" in query:
        value = query["limit"]
        if (
            not value.isascii()
            or not value.isdecimal()
            or not 1 <= len(value) <= 3
            or not 1 <= int(value) <= 100
        ):
            raise ValueError()
        query["limit"] = int(value)
    return query
