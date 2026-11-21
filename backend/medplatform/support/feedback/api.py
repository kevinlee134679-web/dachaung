"""C13–C15 request fields and strict feedback-window query handling."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ...web.inputs import (
    ID,
    Input,
    Reason,
    Text,
    query_fields,
    query_limit,
    query_text,
    query_window,
)

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
    paging = {"cursor", "limit"}
    window = {"window_start", "window_end"} if action == "feedback_source" else set()
    query = query_fields(pairs, set() if action == "save_feedback" else paging | window)
    if window:
        query_window(query)
    if "cursor" in query:
        query_text(query["cursor"], 4096)
    if "limit" in query:
        query["limit"] = query_limit(query["limit"], 3)
    return query
