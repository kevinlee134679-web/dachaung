"""B persistence over the existing A-managed SQLite connection."""

import json

from ..core.documents import encode
from ..core.errors import AppError


def session(conn, session_id):
    row = conn.execute(
        "SELECT document_json FROM b_sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if row is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "会话不可访问")
    return json.loads(row[0])


def save_session(conn, doc, *, new=False):
    raw = encode(doc)
    if new:
        conn.execute(
            "INSERT INTO b_sessions VALUES (?,?,?,?,?)",
            (
                doc["session_id"],
                doc["patient_id"],
                doc["case_id"],
                doc["invitation_id"],
                raw,
            ),
        )
    else:
        conn.execute(
            "UPDATE b_sessions SET document_json=? WHERE session_id=?",
            (raw, doc["session_id"]),
        )
    return doc


def message(conn, message_id):
    row = conn.execute(
        "SELECT document_json FROM b_messages WHERE message_id=?", (message_id,)
    ).fetchone()
    if row is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "消息不可访问")
    return json.loads(row[0])


def generation(conn, generation_id):
    row = conn.execute(
        "SELECT * FROM b_generations WHERE generation_id=?", (generation_id,)
    ).fetchone()
    if row is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "原生成记录不可访问")
    return row, json.loads(row["document_json"])


def by_id(conn, kind, identifier, *, required=True):
    row = conn.execute(
        "SELECT document_json FROM b_records WHERE kind=? AND record_id=?",
        (kind, identifier),
    ).fetchone()
    if row is not None:
        return json.loads(row[0])
    if required:
        raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
    return None


def by_source(conn, kind, source_key):
    row = conn.execute(
        "SELECT document_json FROM b_records WHERE kind=? AND source_key=?",
        (kind, source_key),
    ).fetchone()
    return json.loads(row[0]) if row is not None else None


def records(conn, kind, patient_id, *, session_id=None):
    if session_id is not None:
        rows = conn.execute(
            "SELECT document_json FROM b_records WHERE kind=? AND patient_id=? AND session_id=?",
            (kind, patient_id, session_id),
        )
    else:
        rows = conn.execute(
            "SELECT document_json FROM b_records WHERE kind=? AND patient_id=?",
            (kind, patient_id),
        )
    return [json.loads(row[0]) for row in rows]


def insert(
    conn, kind, identifier, doc, *, source_key=None, patient_id=None, session_id=None
):
    conn.execute(
        "INSERT INTO b_records VALUES (?,?,?,?,?,?)",
        (
            kind,
            identifier,
            patient_id if patient_id is not None else doc.get("patient_id"),
            session_id if session_id is not None else doc.get("session_id"),
            source_key,
            encode(doc),
        ),
    )
    return doc


def update(conn, kind, identifier, doc):
    conn.execute(
        "UPDATE b_records SET document_json=? WHERE kind=? AND record_id=?",
        (encode(doc), kind, identifier),
    )
    return doc
