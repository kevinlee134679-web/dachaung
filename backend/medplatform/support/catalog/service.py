"""The local directory of approved support sources."""

import json
from typing import Literal

from pydantic import TypeAdapter, model_validator

from ...core.config import ROOT
from ...core.documents import encode, now, stamp
from ...core.errors import AppError
from ...core.idempotency import Result
from ...core.migrations import status
from ...web.inputs import ID, Input, Short, Text
from ..common import next_cursor, page_after, read_guarded

FIXTURE_FILE = "data/demo/support_resources.json"
COMMUNITY_TYPES = frozenset({"B2", "D1"})
SharedCategory = Literal[
    "support_question", "medication_plan", "medication_records", "profile_summary"
]
CURRENT = """SELECT v.* FROM c_support_resources AS r
             JOIN c_support_resource_versions AS v
               ON v.resource_id = r.resource_id AND v.resource_version = r.current_version"""


class DemoProvider(Input):
    provider_id: ID
    provider_type: Literal["volunteer", "pharmacist"]
    display_name: Short
    qualification_status: Literal["not_required", "not_verified"]
    is_simulated: Literal[True]


class DemoResource(Input):
    resource_id: ID
    resource_version: ID
    service_kind: Literal[
        "community_assistance",
        "emotional_companionship",
        "pharmacist_consultation",
        "peer_support",
    ]
    name: Short
    description: Text
    provider: DemoProvider
    availability: Literal["available", "unavailable", "unknown"]
    access_mode: Literal["support_free"]
    is_essential: bool
    required_shared_categories: list[SharedCategory]
    optional_shared_categories: list[SharedCategory]
    peer_group_id: ID | None
    is_simulated: Literal[True]

    @model_validator(mode="after")
    def validate_fixture(self):
        pharmacist = self.service_kind == "pharmacist_consultation"
        if (self.peer_group_id is not None) != (self.service_kind == "peer_support"):
            raise ValueError("Demo peer resources require a precise group")
        if (self.provider.provider_type == "pharmacist") != pharmacist:
            raise ValueError("Demo provider does not match the service")
        if pharmacist and self.provider.qualification_status != "not_verified":
            raise ValueError("The mock pharmacist has no verified credentials")
        categories = self.required_shared_categories + self.optional_shared_categories
        if len(categories) != len(set(categories)):
            raise ValueError("Shared categories must be distinct")
        if "模拟" not in self.name or "模拟" not in self.provider.display_name:
            raise ValueError("Demo resource and provider must be visibly marked")
        return self


class ResourceFixture(Input):
    resource: DemoResource
    previous_version: ID | None
    profile_types: list[ID]

    @model_validator(mode="after")
    def validate_version(self):
        if self.previous_version == self.resource.resource_version:
            raise ValueError("A resource version cannot follow itself")
        return self


def current_resource(conn, content):
    row = conn.execute(
        CURRENT + " WHERE r.resource_id=? AND r.current_version=?",
        (content["resource_id"], content["resource_version"]),
    ).fetchone()
    if row is None:
        return None
    doc = json.loads(row["resource_json"])
    if doc["availability"] == "available" and doc["is_simulated"] is True:
        return doc
    return None


def register_catalog(db, fixtures, clock=now):
    """Install versioned fictional fixtures via the explicit local command."""
    status(db)
    with db.transaction() as conn:
        return install_catalog(conn, fixtures, stamp(clock()))


def install_catalog(conn, fixtures, at):
    written = 0
    for fixture in fixtures:
        doc = fixture.resource
        identity = (doc.resource_id, doc.resource_version)
        payload = (
            fixture.previous_version,
            encode(doc.model_dump()),
            encode(sorted(fixture.profile_types)),
        )
        saved = conn.execute(
            """SELECT previous_version, resource_json, profile_types_json
               FROM c_support_resource_versions WHERE resource_id=? AND resource_version=?""",
            identity,
        ).fetchone()
        if saved is not None:
            if tuple(saved) != payload:
                raise AppError(
                    409, "RESOURCE_VERSION_CONFLICT", "该资源版本已登记不同内容"
                )
            continue
        current = conn.execute(
            "SELECT current_version FROM c_support_resources WHERE resource_id=?",
            (doc.resource_id,),
        ).fetchone()
        if (current[0] if current else None) != fixture.previous_version:
            raise AppError(
                409, "RESOURCE_VERSION_CONFLICT", "资源当前版本已变更，请核对版本前序"
            )
        conn.execute(
            """INSERT INTO c_support_resource_versions
               (resource_id, resource_version, recorded_at, previous_version,
                resource_json, profile_types_json) VALUES (?,?,?,?,?,?)""",
            (*identity, at, *payload),
        )
        conn.execute(
            """INSERT INTO c_support_resources (resource_id, current_version) VALUES (?,?)
               ON CONFLICT(resource_id) DO UPDATE SET current_version=excluded.current_version""",
            identity,
        )
        written += 1
    return written


def seed_catalog(db):
    fixtures = TypeAdapter(list[ResourceFixture]).validate_json(
        (ROOT / FIXTURE_FILE).read_bytes()
    )
    return register_catalog(db, fixtures)


def catalog_registered(conn):
    return (
        conn.execute("SELECT 1 FROM c_support_resources LIMIT 1").fetchone() is not None
    )


class Catalog:
    def __init__(self, db, auth):
        self.db, self.auth = db, auth

    def patient(self, conn, principal, path):
        patient = (
            path.get("p") or self.auth.account(principal, conn)["current_patient_id"]
        )
        if not patient:
            raise AppError(
                403, "SCOPE_REQUIRED", "请先选择本人或已获准查看社会支持的对象"
            )
        self.auth.require_patient(principal, patient, "support:read", conn)
        return patient

    def handle(self, action, principal, path, query, _body, _key):
        def guard(conn):
            return self.patient(conn, principal, path)

        def verify(patient, current):
            if current != patient:
                raise AppError(403, "SCOPE_REQUIRED", "当前照护对象已变更，请重新读取")

        with self.db.connection(readonly=True) as conn:
            with read_guarded(conn, guard, verify) as patient:
                if action == "resources":
                    data = self.resources(conn, principal, patient, query)
                else:
                    data = self.resource(conn, path["id"])
            return Result(data)

    def resources(self, conn, principal, patient, query):
        if not catalog_registered(conn):
            raise AppError(503, "SUPPORT_RESOURCE_UNAVAILABLE", "模拟资源目录尚未登记")
        context = [principal.account_id, "C02", patient, "support"]
        after = page_after(self.auth, query, context, [""])[0]
        limit = query.get("limit", 20)
        rows = conn.execute(
            CURRENT
            + """ WHERE v.resource_id > ? AND json_extract(v.resource_json, '$.availability') = 'available'
                          AND json_extract(v.resource_json, '$.access_mode') = 'support_free'
                          ORDER BY v.resource_id LIMIT ?""",
            (after, limit + 1),
        ).fetchall()
        items = [json.loads(r["resource_json"]) for r in rows[:limit]]
        cursor = next_cursor(
            rows, limit, self.auth, context, lambda row: [row["resource_id"]]
        )
        return {"items": items, "next_cursor": cursor}

    def resource(self, conn, identifier):
        row = conn.execute(
            CURRENT
            + """ WHERE v.resource_id=? AND json_extract(v.resource_json, '$.availability')='available'
                          AND json_extract(v.resource_json, '$.access_mode')='support_free'""",
            (identifier,),
        ).fetchone()
        if row is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问或不存在")
        return json.loads(row["resource_json"])
