"""Exact C16–C21 and C37 demo interface contracts."""
from typing import Literal

from pydantic import TypeAdapter

from .s02_inputs import ID, Input, Version
from .s05_service_api import Reason, ServiceCreate


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
    query = dict(pairs)
    allowed = {"groups": {"group_id", "cursor", "limit"}, "posts": {"cursor", "limit", "include_pending"},
               "my_memberships": {"cursor", "limit"}}
    if len(query) != len(pairs) or set(query) - allowed.get(action, set()):
        raise ValueError()
    if "group_id" in query:
        TypeAdapter(ID).validate_python(query["group_id"])
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "include_pending" in query:
        if query["include_pending"] not in {"true", "false"}:
            raise ValueError()
        query["include_pending"] = query["include_pending"] == "true"
    if "limit" in query:
        value = query["limit"]
        if not value.isascii() or not value.isdecimal() or not 1 <= len(value) <= 3 or not 1 <= int(value) <= 100:
            raise ValueError()
        query["limit"] = int(value)
    return query
