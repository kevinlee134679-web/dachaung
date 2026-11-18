"""C26–C33 request boundary."""
from typing import Literal

from pydantic import model_validator

from .s02_inputs import DateTime, ID, Input, Text, Version
from .s05_service_api import Reason, query_input as service_query

RECEIPT_PATH = "/api/v1/integrations/fulfillment-receipts"


class Redeem(Input):
    reward_id: ID
    reward_version: ID
    expected_account_revision: Version
    confirmed: Literal[True]
    service_draft_id: ID | None = None
    draft_revision: Version | None = None
    confirmation_ref_id: ID | None = None
    sharing_scope_ref_id: ID | None = None


class Receipt(Input):
    provider_event_id: ID
    fulfillment_id: ID
    status: Literal["in_progress", "completed", "failed", "cancelled", "outcome_unknown"]
    occurred_at: DateTime
    result_ref: ID | None = None
    failure_reason: Reason | None = None

    @model_validator(mode="after")
    def evidence(self):
        if (self.status == "completed") != (self.result_ref is not None):
            raise ValueError("completion requires its result reference")
        if (self.status in {"failed", "cancelled", "outcome_unknown"}) != (self.failure_reason is not None):
            raise ValueError("failure, cancellation and unknown require their reason")
        return self


class Feedback(Input):
    client_feedback_id: ID
    participation: Literal["provided", "declined", "unable"]
    experience: Text | None = None
    service_feedback_id: ID | None = None


ROUTES = [
    ("C26", "GET", "/rewards", "reward_list", None),
    ("C27", "GET", "/rewards/{id}", "reward_read", None),
    ("C28", "POST", "/patients/{p}/redemptions", "redeem", Redeem),
    ("C29", "GET", "/patients/{p}/redemptions", "redemption_list", None),
    ("C30", "GET", "/redemptions/{id}", "redemption_read", None),
    ("C31", "POST", "/integrations/fulfillment-receipts", "fulfillment_receipt", Receipt),
    ("C32", "GET", "/redemptions/{id}/fulfillment", "fulfillment_read", None),
    ("C33", "POST", "/redemptions/{id}/feedback", "redemption_feedback", Feedback),
]


def query_input(action, pairs):
    if any(field == "status" for field, _ in pairs):
        raise ValueError()
    return service_query("list_services" if action in {"reward_list", "redemption_list"} else action, pairs)
