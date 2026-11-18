"""Service draft and patient consent cards on the shared HTTP boundary."""
from typing import Literal

from pydantic import field_validator

from .s02_inputs import ID, Input, Revoke, Text, Version
from .s05_catalog import SharedCategory


class DraftInput(Input):
    resource_id: ID
    resource_version: ID
    request_text: Text
    peer_group_id: ID | None = None
    source_suggestion_id: None = None


class DraftEdit(Input):
    expected_revision: Version
    content: DraftInput


class Confirm(Input):
    service_draft_id: ID
    draft_revision: Version
    shared_categories: list[SharedCategory]
    confirmed: Literal[True]
    existing_confirmation_ref_id: ID | None = None

    @field_validator("shared_categories")
    @classmethod
    def normalize_categories(cls, categories):
        return sorted(set(categories))


ROUTES = [
    ("C04", "POST", "/patients/{p}/service-drafts", "create", DraftInput),
    ("C05", "GET", "/service-drafts/{id}", "draft", None),
    ("C06", "PUT", "/service-drafts/{id}", "edit", DraftEdit),
    ("C34", "POST", "/patients/{p}/service-confirmations", "confirm", Confirm),
    ("C35", "GET", "/service-confirmations/{id}", "confirmation", None),
    ("C36", "POST", "/service-confirmations/{id}/revoke", "revoke", Revoke),
]


def query_input(_action, pairs):
    if pairs:
        raise ValueError()
    return {}
