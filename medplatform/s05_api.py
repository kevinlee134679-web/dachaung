"""C01–C03 use the shared HTTP request boundary and envelope."""
ROUTES = [
    ("C01", "GET", "/patients/{p}/support-recommendations", "recommendations", None),
    ("C02", "GET", "/support-resources", "resources", None),
    ("C03", "GET", "/support-resources/{id}", "resource", None),
]
NEEDS = frozenset({"practical", "emotional", "professional", "none"})
CHANNELS = frozenset({"support", "rewards"})
QUERY_KEYS = {"recommendations": {"need"}, "resources": {"channel", "cursor", "limit"}}


def query_input(action, pairs):
    query = dict(pairs)
    if len(pairs) != len(query) or set(query) - QUERY_KEYS.get(action, set()):
        raise ValueError()
    if "need" in query and query["need"] not in NEEDS:
        raise ValueError()
    if "channel" in query and query["channel"] not in CHANNELS:
        raise ValueError()
    if "cursor" in query and not 1 <= len(query["cursor"]) <= 4096:
        raise ValueError()
    if "limit" in query:
        value = query["limit"]
        if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 100:
            raise ValueError()
        query["limit"] = int(value)
    return query
