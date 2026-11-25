"""Catalog routes use the shared HTTP request boundary and envelope."""

from ...web.inputs import query_fields, query_limit, query_text

ROUTES = [
    ("C02", "GET", "/support-resources", "resources", None),
    ("C03", "GET", "/support-resources/{id}", "resource", None),
]
CHANNELS = frozenset({"support"})
QUERY_KEYS = {"resources": {"channel", "cursor", "limit"}}


def query_input(action, pairs):
    query = query_fields(pairs, QUERY_KEYS.get(action, set()))
    if "channel" in query and query["channel"] not in CHANNELS:
        raise ValueError()
    if "cursor" in query:
        query_text(query["cursor"], 4096)
    if "limit" in query:
        query["limit"] = query_limit(query["limit"])
    return query
