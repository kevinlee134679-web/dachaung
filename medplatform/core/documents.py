"""A-managed storage of versioned O/A documents; never a public generic CRUD."""

import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime

from .errors import AppError


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


def stamp(value=None):
    return (value or now()).astimezone(UTC).isoformat(timespec="microseconds")


def encode(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint(value):
    return hashlib.sha256(encode(value).encode("utf8")).hexdigest()


def fingerprint_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def meta(at, contract="public-o-v0.5"):
    return {
        "created_at": at,
        "updated_at": at,
        "revision": 1,
        "contract_version": contract,
        "is_simulated": True,
    }


def get(conn, kind, identifier, *, required=True):
    row = conn.execute(
        "SELECT document_json FROM s02_documents WHERE resource_key=? AND resource_type=?",
        (kind + ":" + identifier, kind),
    ).fetchone()
    if not row and required:
        raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
    return json.loads(row[0]) if row else None


def all_docs(conn, kind, patient=None):
    sql = "SELECT document_json FROM s02_documents WHERE resource_type=?"
    args = [kind]
    if patient is not None:
        sql += " AND patient_id=?"
        args.append(patient)
    return [json.loads(r[0]) for r in conn.execute(sql + " ORDER BY rowid", args)]


def save(conn, kind, identifier, patient, doc):
    key = kind + ":" + identifier
    raw = encode(doc)
    conn.execute(
        "INSERT INTO s02_documents VALUES (?,?,?,?) ON CONFLICT(resource_key) DO UPDATE SET document_json=excluded.document_json",
        (key, kind, patient, raw),
    )
    conn.execute(
        "INSERT INTO s02_document_history VALUES (?,?,?)",
        (key, doc["meta"]["revision"], raw),
    )
    return doc


def changed(doc, at):
    result = copy.deepcopy(doc)
    result["meta"]["revision"] += 1
    result["meta"]["updated_at"] = at
    return result


def expected(doc, revision, code="REVISION_CONFLICT"):
    if doc["meta"]["revision"] != revision:
        raise AppError(409, code, "资料已更新，请重新读取后核对")
