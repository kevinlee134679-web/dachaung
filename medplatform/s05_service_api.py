"""C07–C12, using the existing strict request and paging boundary."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .s02_inputs import ID, Input, DateTime, Revoke, Text, Version

STATES = frozenset({"submitted", "in_progress", "completed", "cancelled", "failed"})
Target = Literal["in_progress", "completed", "cancelled", "failed"]
Reason = Annotated[str, Field(min_length=1, max_length=500)]
RECEIPT_PATH = "/api/v1/integrations/service-receipts"


class ServiceCreate(Input):
    service_draft_id: ID
    draft_revision: Version
    confirmation_ref_id: ID
    sharing_scope_ref_id: ID


class ProviderReceipt(Input):
    provider_event_id: ID
    service_id: ID
    expected_revision: Version
    status: Target
    occurred_at: DateTime
    result_summary: Text | None
    failure_reason: Reason | None
    response_text: Text | None

    @model_validator(mode="after")
    def require_evidence(self):
        if self.status == "completed" and self.result_summary is None:
            raise ValueError("a completed service requires a result")
        if self.status == "failed" and self.failure_reason is None:
            raise ValueError("a failed service requires a reason")
        return self


class DemoTransition(Input):
    expected_revision: Version
    target_status: Target
    reason: Text

    @model_validator(mode="after")
    def limit_status_reason(self):
        if self.target_status in {"failed", "cancelled"} and len(self.reason) > 500:
            raise ValueError("terminal reason exceeds contract length")
        return self


ROUTES = [
    ("C07", "POST", "/patients/{p}/services", "submit_service", ServiceCreate),
    ("C08", "GET", "/patients/{p}/services", "list_services", None),
    ("C09", "GET", "/services/{id}", "read_service", None),
    ("C10", "POST", "/services/{id}/cancel", "cancel_service", Revoke),
    ("C11", "POST", "/integrations/service-receipts", "provider_receipt", ProviderReceipt),
    ("C12", "POST", "/demo/services/{id}/transitions", "demo_transition", DemoTransition),
]


def query_input(action, pairs):
    query = dict(pairs)
    allowed = {"status", "cursor", "limit"} if action == "list_services" else set()
    if len(query) != len(pairs) or set(query) - allowed:
        raise ValueError()
    if "status" in query and query["status"] not in STATES:
        raise ValueError()
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "limit" in query:
        limit = query["limit"]
        if not limit.isascii() or not limit.isdecimal() or not 1 <= int(limit) <= 100:
            raise ValueError()
        query["limit"] = int(limit)
    return query
