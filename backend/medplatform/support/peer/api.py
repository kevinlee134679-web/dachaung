"""Exact C16–C21 and C37 demo interface contracts."""

from typing import Literal

from pydantic import TypeAdapter

from ...web.inputs import (
    ID,
    Input,
    Reason,
    Version,
    query_fields,
    query_limit,
    query_text,
)
from ..services.inputs import ServiceCreate


class LeaveMembership(Input):
    expected_revision: Version
    reason: Reason | None = None


class PeerPostInput(Input):
    client_post_id: ID
    content: str


class ModeratePost(Input):
    expected_revision: Version
    decision: Literal["visible", "hidden"]
    reason: Reason


ROUTES = [
    ("C16", "GET", "/peer-groups", "groups", None),
    ("C17", "GET", "/peer-groups/{id}", "group", None),
    ("C18", "POST", "/peer-groups/{id}/memberships", "join", ServiceCreate),
    ("C19", "POST", "/memberships/{id}/leave", "leave", LeaveMembership),
    ("C20", "GET", "/peer-groups/{id}/posts", "posts", None),
    ("C21", "POST", "/peer-groups/{id}/posts", "post", PeerPostInput),
    ("C37", "POST", "/peer-posts/{id}/moderation", "moderate", ModeratePost),
    ("C41", "GET", "/peer-memberships/me", "my_memberships", None),
]


def query_input(action, pairs):
    allowed = {
        "groups": {"group_id", "cursor", "limit"},
        "posts": {"cursor", "limit", "include_pending"},
        "my_memberships": {"cursor", "limit"},
    }
    query = query_fields(pairs, allowed.get(action, set()))
    if "group_id" in query:
        TypeAdapter(ID).validate_python(query["group_id"])
    if "cursor" in query:
        query_text(query["cursor"], 4096)
    if "include_pending" in query:
        if query["include_pending"] not in {"true", "false"}:
            raise ValueError()
        query["include_pending"] = query["include_pending"] == "true"
    if "limit" in query:
        query["limit"] = query_limit(query["limit"], 3)
    return query
