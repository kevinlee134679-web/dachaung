"""C owns preparation and confirmation. O owns the shared scope."""
import json

from .documents import fingerprint, meta, stamp, uid
from .errors import AppError
from .idempotency import Result
from .o_sharing import SharingAuthority, VALIDITY
from .s05_catalog import CURRENT

CONTRACT = "C-v0.2"
DRAFT = """SELECT d.*, r.resource_id, r.resource_version, r.request_text,
                  json_extract(v.resource_json,'$.peer_group_id') AS peer_group_id
           FROM c_service_drafts d JOIN c_service_draft_revisions r
             USING (service_draft_id, draft_revision)
           JOIN c_support_resource_versions v ON v.resource_id=r.resource_id AND v.resource_version=r.resource_version
           WHERE d.service_draft_id=?"""
CONFIRMATION = """SELECT c.*, r.revoked_at FROM c_service_confirmations c
                  LEFT JOIN c_confirmation_revocations r USING (confirmation_ref_id)"""


def missing():
    return AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")


def needs_confirmation(message):
    return AppError(409, "SHARING_CONFIRMATION_REQUIRED", message)


def current_resource(conn, content):
    row = conn.execute(CURRENT + " WHERE r.resource_id=? AND r.current_version=?",
                       (content["resource_id"], content["resource_version"])).fetchone()
    if row is None:
        return None
    doc = json.loads(row["resource_json"])
    if doc["availability"] == "available" and doc["access_mode"] == "support_free" and doc["is_simulated"] is True:
        return doc
    return None


def scope_descriptor(patient, resource, categories):
    provider = resource["provider"]
    return fingerprint({
        "data_environment": "demo", "patient_id": patient, "resource_id": resource["resource_id"],
        "resource_version": resource["resource_version"], "provider_id": provider["provider_id"],
        "recipient_type": provider["provider_type"], "service_kind": resource["service_kind"],
        "purpose_code": resource["service_kind"], "data_categories": categories,
    })


class S05Drafts:
    def __init__(self, db, o_service, clock):
        self.db, self.auth, self.receipts, self.clock = db, o_service.auth, o_service.receipts, clock
        self.sharing = SharingAuthority(self.auth)
        self.formal_services = None

    def draft(self, conn, identifier):
        row = conn.execute(DRAFT, (identifier,)).fetchone()
        if row is None:
            raise missing()
        return row

    def confirmation(self, conn, identifier):
        row = conn.execute(CONFIRMATION + " WHERE c.confirmation_ref_id=?", (identifier,)).fetchone()
        if row is None:
            raise missing()
        return row

    def authorize(self, conn, action, principal, path, body):
        doc = None
        if action in {"create", "confirm"}:
            patient = path["p"]
        elif action in {"draft", "edit"}:
            doc = self.draft(conn, path["id"])
            patient = doc["patient_id"]
        else:
            doc = self.confirmation(conn, path["id"])
            patient = doc["patient_id"]
        if action in {"create", "draft", "edit"}:
            self.auth.require_patient(principal, patient, "services:prepare", conn)
            self.auth.require_patient(principal, patient, "support:read", conn)
            if doc is not None and doc["peer_group_id"] is not None:
                self.auth.require_patient(principal, patient, "peer:participate", conn, self_only=True)
        else:
            self.auth.require_patient(principal, patient, "", conn, self_only=True)
        if action == "confirm":
            doc = self.draft(conn, body["service_draft_id"])
            if doc["patient_id"] != patient:
                raise missing()
        return patient, doc

    def handle(self, action, principal, path, query, body, key):
        if action in {"draft", "confirmation"}:
            with self.db.connection(readonly=True) as conn:
                conn.execute("BEGIN")
                _, doc = self.authorize(conn, action, principal, path, body)
                at = stamp(self.clock())
                view = self.draft_view(conn, principal, doc, at) if action == "draft" else self.confirmation_view(conn, doc, at)
                conn.commit()
                self.authorize(conn, action, principal, path, body)
                return Result(view)

        with self.db.connection(readonly=True) as conn:
            patient, _ = self.authorize(conn, action, principal, path, body)
        scope = ["demo", "account", principal.account_id, patient, "C", action, path]

        def authorize(conn):
            return self.authorize(conn, action, principal, path, body)

        def operation(conn):
            _, doc = authorize(conn)
            now = self.clock()
            if action in {"create", "edit"}:
                return self.save_draft(conn, principal, patient, doc, body, stamp(now))
            if action == "confirm":
                return self.confirm(conn, principal, doc, body, now)
            return self.revoke(conn, principal, doc, body, stamp(now))

        def replay(conn, result):
            at = stamp(self.clock())
            if result.resource_type == "ServiceDraft":
                _, doc = self.authorize(conn, "draft", principal, {"id": result.resource_id}, {})
                result.data = self.draft_view(conn, principal, doc, at)
            else:
                _, doc = self.authorize(conn, "confirmation", principal, {"id": result.resource_id}, {})
                result.data = self.confirmation_view(conn, doc, at)
            return result

        return self.receipts.run(scope, key, {"path": path, "query": query, "body": body}, authorize, operation, replay)

    def save_draft(self, conn, principal, patient, original, body, at):
        content = body if original is None else body["content"]
        if original is not None and (original["revision"] != body["expected_revision"] or original["status"] != "preparing"):
            raise AppError(409, "SERVICE_DRAFT_REVISION_CONFLICT", "草稿已更新，请核对最新版本")
        resource = current_resource(conn, content)
        if resource is None:
            raise AppError(422, "INVALID_SERVICE_DRAFT", "请选择当前可访问的目录版本")
        group = resource["peer_group_id"]
        if content.get("peer_group_id") is not None and content["peer_group_id"] != group:
            raise AppError(422, "INVALID_SERVICE_DRAFT", "小组与当前资源版本不一致")
        if group is not None:
            self.auth.require_patient(principal, patient, "peer:participate", conn, self_only=True)
            if not conn.execute("SELECT 1 FROM c_peer_groups WHERE group_id=? AND resource_id=?",
                                (group, content["resource_id"])).fetchone():
                raise AppError(422, "INVALID_SERVICE_DRAFT", "小组与当前资源版本不一致")
        identifier = uid() if original is None else original["service_draft_id"]
        revision = 1 if original is None else original["draft_revision"] + 1
        if original is None:
            conn.execute("""INSERT INTO c_service_drafts
                            (service_draft_id,patient_id,draft_revision,revision,created_at,updated_at)
                            VALUES (?,?,1,1,?,?)""", (identifier, patient, at, at))
        else:
            conn.execute(
                """UPDATE c_service_drafts SET draft_revision=?, revision=revision+1, updated_at=?
                   WHERE service_draft_id=?""", (revision, at, identifier),
            )
        conn.execute(
            "INSERT INTO c_service_draft_revisions VALUES (?,?,?,?,?,?,?)",
            (identifier, revision, content["resource_id"], content["resource_version"], content["request_text"],
             principal.account_id, at),
        )
        return Result(self.draft_view(conn, principal, self.draft(conn, identifier), at),
                      201 if original is None else 200, resource_type="ServiceDraft", resource_id=identifier)

    def linked(self, conn, draft, *, exact_revision):
        sql = CONFIRMATION + """ JOIN c_draft_confirmations l ON c.confirmation_ref_id=l.confirmation_ref_id
              WHERE l.service_draft_id=? AND c.resource_id=? AND c.resource_version=?"""
        args = (draft["service_draft_id"], draft["resource_id"], draft["resource_version"])
        if exact_revision:
            sql += " AND l.draft_revision=?"
            args += (draft["draft_revision"],)
        return conn.execute(sql + " ORDER BY l.rowid DESC", args).fetchall()

    def draft_view(self, conn, principal, draft, at):
        link = None
        if self.auth.is_self(principal, draft["patient_id"], conn):
            for row in self.linked(conn, draft, exact_revision=True):
                if self.confirmation_view(conn, row, at)["status"] == "active":
                    link = row
                    break
        view = {field: draft[field] for field in (
            "service_draft_id", "patient_id", "draft_revision", "resource_id", "resource_version", "request_text",
        )}
        view.update(
            peer_group_id=draft["peer_group_id"], source_suggestion_id=None, status=draft["status"], service_id=draft["service_id"],
            confirmation_ref_id=link["confirmation_ref_id"] if link else None,
            sharing_scope_ref_id=link["sharing_scope_ref_id"] if link else None,
            meta=dict(meta(draft["created_at"], CONTRACT), updated_at=draft["updated_at"], revision=draft["revision"]),
        )
        return view

    def confirmation_view(self, conn, row, at):
        scope, _ = self.sharing.scope(conn, row["sharing_scope_ref_id"], row["patient_id"], at)
        state = scope["status"]
        if row["revoked_at"] is not None:
            state = "revoked"
        elif state == "active" and not row["confirmed_at"] <= at < row["valid_until"]:
            state = "expired"
        view = {field: row[field] for field in (
            "confirmation_ref_id", "patient_id", "resource_id", "resource_version", "provider_id", "service_kind",
            "descriptor_hash", "origin_draft_id", "origin_draft_revision", "confirmed_at", "valid_until",
        )}
        view.update(
            sharing_scope=scope, status=state,
            meta=dict(meta(row["confirmed_at"], CONTRACT), updated_at=row["revoked_at"] or row["confirmed_at"],
                      revision=2 if row["revoked_at"] is not None else 1),
        )
        return view

    def confirm(self, conn, principal, draft, body, now):
        if draft["status"] != "preparing":
            raise needs_confirmation("请为新申请准备独立草稿")
        if draft["draft_revision"] != body["draft_revision"]:
            raise needs_confirmation("草稿内容已更新，请本人重新核对")
        resource = current_resource(conn, draft)
        if resource is None:
            raise needs_confirmation("草稿资源版本已更新或停用，请重新选择")
        at = stamp(now)
        patient = draft["patient_id"]
        categories = body["shared_categories"]
        grants = self.sharing.terms(conn, principal, patient, resource, categories)
        if self.sharing.grant_status(conn, patient, grants, at) != "active":
            raise needs_confirmation("必要 O 授权已失效，请重新核对")
        descriptor = scope_descriptor(patient, resource, categories)

        def active(row):
            return self.confirmation_view(conn, row, at)["status"] == "active"

        def reusable(row):
            if row["descriptor_hash"] != descriptor or not active(row):
                return False
            _, versions = self.sharing.scope(conn, row["sharing_scope_ref_id"], patient)
            return versions == grants

        for row in self.linked(conn, draft, exact_revision=False):
            if row["descriptor_hash"] != descriptor and active(row):
                raise needs_confirmation("此草稿已有其他有效共享范围，请本人明确撤销后再确认")

        hint = body["existing_confirmation_ref_id"]
        selected = None
        if hint is not None:
            selected = self.confirmation(conn, hint)
            if selected["patient_id"] != patient:
                raise missing()
            if not reusable(selected):
                raise needs_confirmation("所选同意已失效或范围不同，请重新核对")
        else:
            options = conn.execute(
                CONFIRMATION + " WHERE c.patient_id=? AND c.descriptor_hash=? AND c.valid_until>? ORDER BY c.rowid",
                (patient, descriptor, at),
            )
            selected = next((row for row in options if reusable(row)), None)
        created = selected is None
        if created:
            scope = self.sharing.issue(conn, principal, patient, resource, categories, now)
            identifier = uid()
            conn.execute(
                "INSERT INTO c_service_confirmations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (identifier, patient, draft["resource_id"], draft["resource_version"], resource["provider"]["provider_id"],
                 resource["service_kind"], descriptor, draft["service_draft_id"], draft["draft_revision"],
                 scope["sharing_scope_ref_id"], at, stamp(now + VALIDITY)),
            )
            selected = self.confirmation(conn, identifier)
        identifier = selected["confirmation_ref_id"]
        link = conn.execute(
            "INSERT INTO c_draft_confirmations VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
            (patient, draft["service_draft_id"], draft["draft_revision"], identifier, at),
        )
        if link.rowcount:
            conn.execute("UPDATE c_service_drafts SET revision=revision+1, updated_at=? WHERE service_draft_id=?",
                         (at, draft["service_draft_id"]))
        return Result(self.confirmation_view(conn, selected, at), 201 if created else 200,
                      resource_type="ServiceConfirmation", resource_id=identifier)

    def revoke(self, conn, principal, row, body, at):
        identifier, patient = row["confirmation_ref_id"], row["patient_id"]
        revision = 2 if row["revoked_at"] is not None else 1
        if body["expected_revision"] != revision:
            raise AppError(409, "CONFIRMATION_REVISION_CONFLICT", "确认记录已变化，请重新读取")
        if row["revoked_at"] is None:
            self.sharing.revoke(conn, principal, row["sharing_scope_ref_id"], patient, at, body["reason"])
            conn.execute("INSERT INTO c_confirmation_revocations VALUES (?,?,?,?)",
                         (identifier, principal.account_id, at, body["reason"]))
            if self.formal_services is not None:
                self.formal_services.stop_scope_dispatches(conn, row["sharing_scope_ref_id"], at)
        return Result(self.confirmation_view(conn, self.confirmation(conn, identifier), at),
                      resource_type="ServiceConfirmation", resource_id=identifier)
