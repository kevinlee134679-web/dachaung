STATES = frozenset({"submitted", "in_progress", "completed", "cancelled", "failed"})


def query_input(action, pairs):
    query = dict(pairs)
    allowed = (
        {"status", "cursor", "limit", "order"} if action == "list_services" else set()
    )
    if len(query) != len(pairs) or set(query) - allowed:
        raise ValueError()
    if "status" in query and query["status"] not in STATES:
        raise ValueError()
    if "order" in query and query["order"] not in {"asc", "desc"}:
        raise ValueError()
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "limit" in query:
        limit = query["limit"]
        if not limit.isascii() or not limit.isdecimal() or not 1 <= int(limit) <= 100:
            raise ValueError()
        query["limit"] = int(limit)
    return query
