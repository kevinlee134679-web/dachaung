from ...web.inputs import query_fields, query_limit, query_text

STATES = frozenset({"submitted", "in_progress", "completed", "cancelled", "failed"})


def query_input(action, pairs):
    allowed = (
        {"status", "cursor", "limit", "order"} if action == "list_services" else set()
    )
    query = query_fields(pairs, allowed)
    if "status" in query and query["status"] not in STATES:
        raise ValueError()
    if "order" in query and query["order"] not in {"asc", "desc"}:
        raise ValueError()
    if "cursor" in query:
        query_text(query["cursor"], 4096)
    if "limit" in query:
        query["limit"] = query_limit(query["limit"])
    return query
