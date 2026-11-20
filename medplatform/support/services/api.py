"""C07–C12, using the existing strict request and paging boundary."""

from typing import Literal

from pydantic import model_validator

from ...web.inputs import ID, DateTime, Input, Reason, Revoke, Text, Version
from . import query
from .inputs import ServiceCreate

query_input = query.query_input

Target = Literal["in_progress", "completed", "cancelled", "failed"]
RECEIPT_PATH = "/api/v1/integrations/service-receipts"


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
    (
        "C11",
        "POST",
        "/integrations/service-receipts",
        "provider_receipt",
        ProviderReceipt,
    ),
    (
        "C12",
        "POST",
        "/demo/services/{id}/transitions",
        "demo_transition",
        DemoTransition,
    ),
]
