"""The local C directory and a read-only projection of approved support sources."""
import json
import sqlite3
from typing import Literal

from pydantic import TypeAdapter, model_validator

from .config import ROOT
from .documents import encode, now, stamp
from .errors import AppError
from .idempotency import Result
from .migrations import status
from .s02_inputs import ID, Input, Short, Text

FIXTURE_FILE = "data/demo/support_resources.json"
NEED_BY_KIND = {
    "community_assistance": "practical",
    "emotional_companionship": "emotional",
    "pharmacist_consultation": "professional",
}
# Only existing O labels and the corresponding C5 applicability from Prompt v1.1.
PROFILE_TYPES = frozenset({"A", "B1", "B2", "C1", "C2", "C3", "D1"})
COMMUNITY_TYPES = frozenset({"B2", "D1"})
SharedCategory = Literal["support_question", "medication_plan", "medication_records", "profile_summary"]
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
    service_kind: Literal["community_assistance", "emotional_companionship", "pharmacist_consultation"]
    name: Short
    description: Text
    provider: DemoProvider
    availability: Literal["available", "unavailable", "unknown"]
    access_mode: Literal["support_free"]
    is_essential: bool
    required_shared_categories: list[SharedCategory]
    optional_shared_categories: list[SharedCategory]
    peer_group_id: None
    is_simulated: Literal[True]

    @model_validator(mode="after")
    def validate_fixture(self):
        pharmacist = self.service_kind == "pharmacist_consultation"
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
    review_status: Literal["not_reviewed"]
    profile_types: list[ID]

    @model_validator(mode="after")
    def validate_applicability(self):
        labels = set(self.profile_types)
        if labels and (self.resource.service_kind != "community_assistance" or
                       not labels <= COMMUNITY_TYPES or len(labels) != len(self.profile_types)):
            raise ValueError("Unsupported demo applicability condition")
        if self.previous_version == self.resource.resource_version:
            raise ValueError("A resource version cannot follow itself")
        return self


def register_catalog(db, fixtures, clock=now):
    """Install versioned fictional fixtures via the explicit local command."""
    status(db)
    written = 0
    with db.transaction() as conn:
        at = stamp(clock())
        for fixture in fixtures:
            doc = fixture.resource
            identity = (doc.resource_id, doc.resource_version)
            source = f"{FIXTURE_FILE}#{doc.resource_id}/{doc.resource_version}"
            payload = (fixture.previous_version, source, fixture.review_status,
                       encode(doc.model_dump()), encode(sorted(fixture.profile_types)))
            saved = conn.execute(
                """SELECT previous_version, fixture_source, review_status, resource_json, profile_types_json
                   FROM c_support_resource_versions WHERE resource_id=? AND resource_version=?""", identity,
            ).fetchone()
            if saved is not None:
                if tuple(saved) != payload:
                    raise AppError(409, "RESOURCE_VERSION_CONFLICT", "该资源版本已登记不同内容")
                continue
            current = conn.execute(
                "SELECT current_version FROM c_support_resources WHERE resource_id=?", (doc.resource_id,),
            ).fetchone()
            if (current[0] if current else None) != fixture.previous_version:
                raise AppError(409, "RESOURCE_VERSION_CONFLICT", "资源当前版本已变更，请核对版本前序")
            conn.execute(
                """INSERT INTO c_support_resource_versions
                   (resource_id, resource_version, recorded_at, previous_version, fixture_source,
                    review_status, resource_json, profile_types_json) VALUES (?,?,?,?,?,?,?,?)""",
                (*identity, at, *payload),
            )
            conn.execute(
                """INSERT INTO c_support_resources (resource_id, current_version) VALUES (?,?)
                   ON CONFLICT(resource_id) DO UPDATE SET current_version=excluded.current_version""", identity,
            )
            written += 1
    return written


def seed_catalog(db):
    fixtures = TypeAdapter(list[ResourceFixture]).validate_json((ROOT / FIXTURE_FILE).read_bytes())
    return register_catalog(db, fixtures)


def catalog_registered(conn):
    return conn.execute("SELECT 1 FROM c_support_resources LIMIT 1").fetchone() is not None


def issue(code, message, field=None):
    return {"code": code, "message": message, "field": field}


def source(module, kind, identifier, version, at):
    return {"module": module, "record_kind": kind, "record_id": identifier, "version": version, "recorded_at": at}


def eligible_action(doc, own, requires_profile):
    reason = "与本人本次选择的需求相符。" if own else "与本次查询的需求相符。"
    if requires_profile:
        reason += "获准读取的 O 画像中有符合适用条件的既有类型。"
    return {
        "resource_id": doc["resource_id"], "provider_type": doc["provider"]["provider_type"],
        "action_type": "companionship" if doc["service_kind"] == "emotional_companionship" else doc["service_kind"],
        "reason": reason, "title": doc["name"], "page_entry": "support/social", "requires_confirmation": True,
    }


class S05Catalog:
    def __init__(self, db, o_service, clock):
        self.db, self.o, self.clock = db, o_service, clock
        self.auth = o_service.auth

    def patient(self, conn, principal, path):
        patient = path.get("p") or self.auth.account(principal, conn)["current_patient_id"]
        if not patient:
            raise AppError(403, "SCOPE_REQUIRED", "请先选择本人或已获准查看社会支持的对象")
        self.auth.require_patient(principal, patient, "support:read", conn)
        return patient

    def handle(self, action, principal, path, query, _body, _key):
        try:
            with self.db.connection(readonly=True) as conn:
                conn.execute("BEGIN")
                patient = self.patient(conn, principal, path)
                if action == "recommendations":
                    data, read_profile = self.recommendations(conn, principal, patient, query.get("need"))
                elif action == "resources":
                    data = self.resources(conn, principal, patient, query)
                else:
                    data = self.resource(conn, path["id"])
                conn.commit()
                if self.patient(conn, principal, path) != patient:
                    raise AppError(403, "SCOPE_REQUIRED", "当前照护对象已变更，请重新读取")
                if action == "recommendations" and read_profile:
                    self.auth.require_patient(principal, patient, "profile:read", conn)
                return Result(data)
        except (sqlite3.Error, json.JSONDecodeError):
            code = "SUPPORT_CONTEXT_UNAVAILABLE" if action == "recommendations" else "SUPPORT_RESOURCE_UNAVAILABLE"
            message = "支持上下文暂不可用" if action == "recommendations" else "资源目录暂不可用"
            raise AppError(503, code, message) from None

    def resources(self, conn, principal, patient, query):
        if not catalog_registered(conn):
            raise AppError(503, "SUPPORT_RESOURCE_UNAVAILABLE", "模拟资源目录尚未登记")
        channel = query.get("channel", "support")
        context = [principal.account_id, "C02", patient, channel]
        after = ""
        if "cursor" in query:
            last = self.auth.read_cursor(query["cursor"], context)
            if len(last) != 1 or not isinstance(last[0], str):
                raise AppError(422, "INVALID_CURSOR", "分页位置无效，请重新读取列表")
            after = last[0]
        limit = query.get("limit", 20)
        rows = conn.execute(
            CURRENT + """ WHERE v.resource_id > ? AND json_extract(v.resource_json, '$.availability') = 'available'
                          AND json_extract(v.resource_json, '$.access_mode') = ?
                          ORDER BY v.resource_id LIMIT ?""",
            (after, "support_free" if channel == "support" else "reward_only", limit + 1),
        ).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {"items": [json.loads(r["resource_json"]) for r in rows],
                "next_cursor": self.auth.cursor(context, [rows[-1]["resource_id"]]) if more else None}

    def resource(self, conn, identifier):
        row = conn.execute(
            CURRENT + """ WHERE v.resource_id=? AND json_extract(v.resource_json, '$.availability')='available'
                          AND json_extract(v.resource_json, '$.access_mode')='support_free'""",
            (identifier,),
        ).fetchone()
        if row is None:
            raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问或不存在")
        return json.loads(row["resource_json"])

    def profile(self, conn, principal, patient):
        path = {"p": patient}
        try:
            self.o.authorize(conn, "current_profile", principal, path, {})
            profile = self.o.read(conn, "current_profile", principal, path, {})
        except AppError as error:
            if error.code == "SCOPE_REQUIRED":
                return None, issue("profile_restricted", "当前授权不含画像读取。", "profile_id"), False
            if error.code == "PROFILE_NOT_AVAILABLE":
                return None, issue("profile_not_available", "O 尚未登记当前画像。", "profile_id"), True
            raise
        if profile["meta"]["is_simulated"] is not True:
            return None, issue("profile_restricted", "当前演示只能使用虚构画像。", "profile_id"), True
        return profile, None, True

    def recommendations(self, conn, principal, patient, need):
        data = {
            "patient_id": patient, "profile_id": None, "primary_profile_type": None, "additional_profile_types": [],
            "need_status": "none" if need == "none" else "insufficient", "main_need": need or "unknown",
            "primary_action": None, "secondary_actions": [], "source_refs": [], "missing_items": [],
            "generated_at": stamp(self.clock()), "is_simulated": True,
        }
        if need == "none":
            return data, False

        problems = data["missing_items"]
        refs = data["source_refs"]
        profile, profile_issue, read_profile = self.profile(conn, principal, patient)
        confirmed_types = set()
        known_types = False
        if profile_issue:
            problems.append(profile_issue)
        if profile is not None:
            profile_id = profile["profile_id"]
            refs.append(source("O", "profile", profile_id, str(profile["meta"]["revision"]),
                               profile["meta"]["updated_at"]))
            primary = profile.get("primary_type")
            additional = profile.get("additional_types")
            primary = primary if isinstance(primary, str) and primary in PROFILE_TYPES else None
            additional_types = [
                x for x in additional if isinstance(x, str) and x in PROFILE_TYPES
            ] if isinstance(additional, list) else []
            data.update(profile_id=profile_id, primary_profile_type=primary, additional_profile_types=additional_types)
            confirmed_types.update(additional_types)
            if primary is not None:
                confirmed_types.add(primary)
            additional_known = isinstance(additional, list) and additional_types == additional
            known_types = primary is not None and additional_known
            for field, known in (("primary_type", primary is not None), ("additional_types", additional_known)):
                if field not in profile:
                    problems.append(issue("profile_field_missing", "O 画像缺少此字段。", field))
                elif not known:
                    problems.append(issue("profile_type_unknown", "O 尚无可用于该条件的既有类型。", field))
        if need is None:
            problems.append(issue("support_need_unknown", "当前没有明确的支持需求，请先选择本次需求。", "need"))
            return data, read_profile
        if not catalog_registered(conn):
            raise AppError(503, "SUPPORT_CONTEXT_UNAVAILABLE", "模拟资源目录尚未登记")

        own = self.auth.is_self(principal, patient, conn)
        actions, unresolved = [], False
        for row in conn.execute(CURRENT):
            doc = json.loads(row["resource_json"])
            if doc["access_mode"] != "support_free" or NEED_BY_KIND.get(doc["service_kind"]) != need:
                continue
            label = f'{doc["name"]}（{doc["resource_version"]}）'
            if doc["availability"] == "unavailable":
                problems.append(issue("resource_unavailable", f"{label}当前停用。", "availability"))
                continue
            if doc["availability"] == "unknown":
                problems.append(issue("resource_availability_unknown", f"{label}的可用性尚不明确。", "availability"))
                unresolved = True
                continue
            required = set(json.loads(row["profile_types_json"]))
            if required and not required.intersection(confirmed_types):
                if known_types:
                    problems.append(issue("profile_condition_not_met", f"{label}的画像适用条件未满足。", "profile_id"))
                else:
                    problems.append(issue("profile_condition_unresolved", f"{label}的画像适用条件无法核实。", "profile_id"))
                    unresolved = True
                continue
            refs.append(source("C", "support_resource", doc["resource_id"], doc["resource_version"], row["recorded_at"]))
            actions.append(eligible_action(doc, own, bool(required)))

        if actions:
            data["need_status"] = "needed"
            if len(actions) == 1:
                data["primary_action"] = actions[0]
            elif len(actions) == 2:
                data["secondary_actions"] = actions
            else:
                problems.append(issue("candidate_order_unconfirmed",
                                      "符合条件的同级资源超过可同时展示的数量。请查看资源版本，暂未指定推荐顺序。"))
        elif not unresolved:
            data["need_status"] = "needed"
            problems.append(issue("no_matching_resource", "当前目录没有符合本次需求及适用条件的可用资源。"))
        return data, read_profile
