"""One versioned knowledge source for dialogue and all authorized viewers."""
import json

from . import s04_store as store
from .documents import changed, encode, expected, meta, stamp, uid
from .errors import AppError

CONTRACT = "B-v0.4"
GENERAL_TAGS = {"general", "general_communication"}
PURPOSE_KIND = {
    "medical_support": "medical",
    "communication": "communication",
    "service_explanation": "service_information",
}


def record(conn, knowledge_id, version):
    row = conn.execute("SELECT document_json FROM b_knowledge WHERE knowledge_id=? AND version=?",
                       (knowledge_id, version)).fetchone()
    if row is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "知识版本不可访问")
    return json.loads(row[0])


def eligible(doc, at, tags):
    return (
        doc["review_status"] == "reviewed" and doc["reviewed_by"] is not None
        and doc["reviewed_at"] is not None and doc["reviewed_at"] <= at
        and doc["effective_from"] <= at and (doc["effective_until"] is None or at < doc["effective_until"])
        and set(doc["applicability_tags"]) <= tags
    )


def documents(conn):
    return [json.loads(row[0]) for row in conn.execute("SELECT document_json FROM b_knowledge")]


def create_version(conn, at, body, knowledge_id, ordinal):
    doc = dict(body, knowledge_id=knowledge_id, version=uid(), review_status="draft",
               reviewed_by=None, reviewed_at=None, review_note=None, meta=meta(at, CONTRACT))
    raw = encode(doc)
    conn.execute("INSERT INTO b_knowledge VALUES (?,?,?,?)", (knowledge_id, doc["version"], ordinal, raw))
    conn.execute("INSERT INTO b_knowledge_history VALUES (?,?,?,?)", (knowledge_id, doc["version"], 1, raw))
    return doc


def new_version(conn, at, knowledge_id, body):
    row = conn.execute("SELECT version,ordinal FROM b_knowledge WHERE knowledge_id=? ORDER BY ordinal DESC LIMIT 1",
                       (knowledge_id,)).fetchone()
    if row is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "资料不可访问")
    if body["expected_current_version"] != row["version"]:
        raise AppError(409, "KNOWLEDGE_VERSION_CONFLICT", "资料当前版本已变化")
    return create_version(conn, at, body["content"], knowledge_id, row["ordinal"] + 1)


def withdraw(conn, at, knowledge_id, body):
    doc = record(conn, knowledge_id, body["version"])
    expected(doc, body["expected_revision"], "KNOWLEDGE_REVISION_CONFLICT")
    if doc["review_status"] == "withdrawn":
        return doc
    doc = changed(doc, at)
    doc.update(review_status="withdrawn", review_note=body["reason"])
    raw = encode(doc)
    conn.execute("UPDATE b_knowledge SET document_json=? WHERE knowledge_id=? AND version=?",
                 (raw, knowledge_id, body["version"]))
    conn.execute("INSERT INTO b_knowledge_history VALUES (?,?,?,?)", (
        knowledge_id, body["version"], doc["meta"]["revision"], raw,
    ))
    return doc


def retrieve(conn, at, body, *, session_id=None, force_empty=False):
    # S04 only has authoritative general applicability. User-supplied tags
    # cannot establish a condition or widen the currently verified scope.
    scope = GENERAL_TAGS.intersection(body["applicability_tags"])
    terms = body["query"].casefold().split()
    matches = []
    if not force_empty:
        for doc in documents(conn):
            if doc["kind"] != PURPOSE_KIND[body["purpose"]] or not eligible(doc, at, scope):
                continue
            search = " ".join((doc["title"], doc["body"], *doc["applicability_tags"])).casefold()
            score = sum(term in search for term in terms)
            if score:
                matches.append((score, doc))
    matches.sort(key=lambda match: (-match[0], match[1]["knowledge_id"], match[1]["version"]))
    ids = {doc["knowledge_id"] for _, doc in matches}
    conflicting = len(ids) != len(matches)
    snippets = []
    if not conflicting:
        for _, doc in matches[:body["limit"]]:
            text = doc["body"]
            position = next((p for term in terms if (p := text.casefold().find(term)) >= 0), 0)
            start = max(0, position - 200)
            snippets.append({
                "fragment_id": uid(), "knowledge_id": doc["knowledge_id"], "version": doc["version"],
                "text": text[start:start + 2000], "source_locator": doc["source_locator"], "kind": doc["kind"],
                "review_status_at_retrieval": "reviewed", "effective_from": doc["effective_from"],
                "effective_until": doc["effective_until"],
            })
    status, reason = "matched", None
    if conflicting:
        status, reason = "conflicting", "同一材料命中多个同时有效版本，需核对版本"
    elif not snippets:
        status, reason = "knowledge_insufficient", "没有可用于本次用途的适用审核资料"
    data = {
        "retrieval_id": uid(), "patient_id": body["patient_id"], "status": status, "snippets": snippets,
        "reason": reason, "retrieved_at": at,
        "knowledge_version_refs": [{"kind": "knowledge", "version": s["version"]} for s in snippets],
        "is_simulated": True,
    }
    return store.insert(conn, "Retrieval", data["retrieval_id"], data, session_id=session_id)


def usable_snippets(conn, at, retrieval):
    if retrieval is None:
        return []
    return [
        snippet for snippet in retrieval["snippets"]
        if eligible(record(conn, snippet["knowledge_id"], snippet["version"]), at, GENERAL_TAGS)
    ]


def verifies_citation(citation, retrieval, snippets):
    if retrieval is None or citation["retrieval_id"] != retrieval["retrieval_id"]:
        return False
    return any(
        all(citation[key] == snippet[key] for key in ("knowledge_id", "version", "fragment_id", "source_locator"))
        and citation["quote"] in snippet["text"] for snippet in snippets
    )


def was_cited(conn, session_id, knowledge_id, version):
    for row in conn.execute("""
        SELECT g.output_json FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id
        WHERE m.session_id=? AND g.output_json IS NOT NULL
    """, (session_id,)):
        for citation in json.loads(row[0])["knowledge_citations"]:
            if (citation["knowledge_id"], citation["version"]) == (knowledge_id, version):
                return True
    return False
