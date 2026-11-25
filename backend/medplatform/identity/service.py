"""O1-O5 configuration and A2 files/drafts only. No record statistics or delivery."""

import base64
import copy
import itertools
import json
import os
import secrets
from datetime import date, datetime, time, timedelta

from ..core.config import ROOT
from ..core.documents import (
    all_docs,
    changed,
    digest,
    expected,
    fingerprint,
    fingerprint_bytes,
    get,
    meta,
    now,
    save,
    stamp,
    uid,
)
from ..core.errors import AppError
from ..core.idempotency import Receipts, Result
from ..core.protection import protect
from ..medication.recognition import recognize
from ..medication.schedule import SHANGHAI, insert_slot, occurrences, require_coverage
from ..profile import cas_questionnaire as cas
from .auth import Principal
from .authority import PersistentAuthority

RESOURCE_KINDS = {
    "revoke_binding": "FamilyBinding",
    "grant_put": "FamilyBinding",
    "revoke_grant": "Grant",
    "answers": "QuestionnaireResponse",
    "response": "QuestionnaireResponse",
    "submit_response": "QuestionnaireResponse",
    "profile": "Profile",
    "medication_patch": "Medication",
    "file": "File",
    "file_content": "File",
    "file_medication_recognition": "File",
    "draft": "Draft",
    "draft_put": "Draft",
    "draft_submit": "Draft",
}
GUARDS = {
    "patient": ("patient:read", False),
    "patient_patch": ("patient:edit", False),
    "binding_code": ("", True),
    "response_create": ("questionnaire:assist", False),
    "profile_create": ("", True),
    "current_profile": ("profile:read", False),
    "latest_submission": ("", True),
    "profile": ("profile:read", False),
    "medications": ("medication:read", False),
    "medication_create": ("medication:edit", False),
    "medication_patch": ("medication:edit", False),
    "plans": ("plan:read", False),
    "plan": ("plan:read", False),
    "plan_confirm": ("", True),
    "slots": ("plan:read", False),
    "reminder": ("reminder:read", False),
    "reminder_put": ("reminder:write", False),
    "file_upload": ("files:write", False),
    "files": ("files:read", False),
    "file": ("files:read", False),
    "file_content": ("files:read", False),
    "file_medication_recognition": ("files:read", False),
    "draft_create": ("drafts:write", False),
    "draft_put": ("drafts:write", False),
    "draft_submit": ("drafts:submit", False),
    "draft": ("drafts:read", False),
    "drafts": ("drafts:read", False),
}


def seed_demo(db, clock=now):
    from ..core.migrations import status

    status(db)
    manifest = json.loads(
        (ROOT / "data" / "demo" / "accounts.json").read_text(encoding="utf8")
    )
    at = stamp(clock())
    with db.transaction() as c:
        for account in manifest["accounts"]:
            c.execute(
                "INSERT INTO o_accounts VALUES (?,?,?,?,?) ON CONFLICT(account_id) DO NOTHING",
                (
                    account["account_id"],
                    account["display_name"],
                    account["self_patient_id"],
                    int(account["is_admin"]),
                    account["self_patient_id"],
                ),
            )
            p = account["self_patient_id"]
            if p and not get(c, "Patient", p, required=False):
                save(
                    c,
                    "Patient",
                    p,
                    p,
                    {
                        "patient_id": p,
                        "display_name": account["display_name"],
                        "timezone": "Asia/Shanghai",
                        "enrollment_at": at,
                        "meta": meta(at),
                    },
                )
    return manifest["version"]


class IdentityService:
    def __init__(self, db, clock=now, *, cas_model=None, llm=None):
        self.db, self.clock = db, clock
        self.cas_model = cas_model
        self.llm = llm
        self.auth = PersistentAuthority(db, clock)
        self.receipts = Receipts(db, clock)
        self.file_root = db.path.parent / "files-demo"

    def resource(self, c, action, params):
        if action == "plan":
            return get(c, "PlanVersion", params["id"] + ":" + str(params["version"]))
        if action in RESOURCE_KINDS:
            return get(c, RESOURCE_KINDS[action], params["id"])
        return None

    def references(self, c, principal, patient, body):
        files = set(body.get("source_file_ids", []))
        for entry in body.get("entries", []):
            med = get(c, "Medication", entry["medication_id"])
            if med["patient_id"] != patient:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            self.auth.require_patient(principal, patient, "medication:read", c)
            files.update(entry["source_file_ids"])
        for fid in files:
            doc = get(c, "File", fid)
            if doc["patient_id"] != patient:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            self.auth.require_patient(principal, patient, "files:read", c)

    def authorize(self, c, action, principal, params, body):
        if action == "login":
            account = c.execute(
                "SELECT * FROM o_accounts WHERE account_id=?",
                (body["demo_account_id"],),
            ).fetchone()
            if not account:
                raise AppError(
                    403, "DEMO_ACCOUNT_UNAVAILABLE", "该演示身份未初始化或未登记"
                )
            return
        if action == "logout":
            self.auth.session(principal, c, logout_receipt=True)
            return
        self.auth.session(principal, c)
        doc = self.resource(c, action, params)
        patient = params.get("p") or (doc["patient_id"] if doc else None)
        if action in GUARDS:
            scope, own = GUARDS[action]
            self.auth.require_patient(principal, patient, scope, c, self_only=own)
        elif action in ("bindings", "grants"):
            if not self.auth.is_self(principal, patient, c) and not any(
                b["family_account_id"] == principal.account_id
                for b in all_docs(c, "FamilyBinding", patient)
            ):
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
        elif action in ("revoke_binding", "grant_put", "revoke_grant"):
            own = self.auth.is_self(principal, patient, c)
            if (
                action == "revoke_binding"
                and doc["family_account_id"] == principal.account_id
            ):
                return
            if not own:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
        elif action in ("answers", "response", "submit_response"):
            own_response = doc["respondent_account_id"] == principal.account_id
            if action == "response":
                # General read permission also covers one's own submitted work.
                # Assist alone only permits the author's still-editable draft.
                scopes = self.auth.scopes(principal, patient, c)
                scope = (
                    "questionnaire:assist"
                    if (
                        own_response
                        and doc["status"] == "draft"
                        and "questionnaire:read" not in scopes
                    )
                    else "questionnaire:read"
                )
            else:
                scope = "questionnaire:assist"
            self.auth.require_patient(principal, patient, scope, c)
            if action != "response" and not own_response:
                raise AppError(
                    403,
                    "RESPONSE_AUTHOR_REQUIRED",
                    "请建立自己的作答副本，不能接管另一人的草稿",
                )
        elif action == "current_patient":
            if not self.auth.scopes(principal, body["patient_id"], c):
                raise AppError(
                    403, "PATIENT_ACCESS_DENIED", "该对象当前不在可管理范围内"
                )
            get(c, "Patient", body["patient_id"])
        elif action == "definition":
            ctx = self.auth.context(principal, c)
            patient = ctx["current_patient_id"]
            if not patient or not (
                {"questionnaire:assist", "questionnaire:read"}
                & set(self.auth.scopes(principal, patient, c))
            ):
                raise AppError(
                    403, "SCOPE_REQUIRED", "请先选择本人或获准协助问卷的对象"
                )
        if action in ("draft_create", "draft_put"):
            self.references(c, principal, patient, body)
        elif action in ("draft", "draft_submit"):
            self.references(c, principal, patient, doc)
        elif action == "drafts":
            for draft in all_docs(c, "Draft", patient):
                self.references(c, principal, patient, draft)
        elif action == "plan_confirm":
            draft = get(c, "Draft", body["draft_id"])
            if draft["patient_id"] != patient:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            self.references(c, principal, patient, draft)
        elif action == "response_create" and body.get("supersedes_response_id"):
            source = get(c, "QuestionnaireResponse", body["supersedes_response_id"])
            if source["patient_id"] != patient:
                raise AppError(404, "SOURCE_RESPONSE_NOT_FOUND", "原回答不可访问")
            if source["respondent_account_id"] != principal.account_id:
                self.auth.require_patient(principal, patient, "questionnaire:read", c)

    def handle(self, action, principal, params, query, body, key, content, is_read):
        body = body or {}
        with self.db.connection(readonly=True) as c:
            self.authorize(c, action, principal, params, body)
            doc = self.resource(c, action, params)
            patient = params.get("p") or (doc["patient_id"] if doc else None)
            if action == "answers":
                cas.validate_answers(body["answers"])
            if is_read:
                result = self.read(c, action, principal, params, query)
                self.authorize(c, action, principal, params, body)
                return Result(result)
        subject = principal.account_id if principal else body["demo_account_id"]
        scope = ["demo", "account", subject, patient or "__none__", action, params]
        if action == "logout":
            # A logout receipt belongs to exactly one session, not every future
            # session of this account. Legacy account-only receipts cannot be
            # safely associated with a session and are not guessed or migrated.
            scope.append(principal.session_hash)
        canonical = {"path": params, "query": query, "body": body}
        result = self.receipts.run(
            scope,
            key,
            canonical,
            lambda c: self.authorize(c, action, principal, params, body),
            lambda c: self.write(c, action, principal, params, body, content),
            lambda c, r: self.replay(c, action, principal, r),
        )
        return result

    def replay(self, c, action, principal, result):
        if action == "login":
            row = c.execute(
                "SELECT * FROM o_sessions WHERE session_hash=?", (digest(result.token),)
            ).fetchone()
            if not row or row["revoked_at"] or row["expires_at"] <= stamp(self.clock()):
                raise AppError(
                    401, "AUTH_REQUIRED", "原登录已退出或到期，请使用新的明确登录操作"
                )
            result.data = self.auth.context(
                Principal(row["account_id"], row["session_hash"]), c
            )
        elif action == "binding_code":
            row = c.execute(
                "SELECT * FROM o_binding_codes WHERE code_id=?",
                (result.data["code_id"],),
            ).fetchone()
            if (
                not row
                or row["consumed_at"]
                or row["expires_at"] <= stamp(self.clock())
                or row["issuer_session_hash"] != principal.session_hash
            ):
                raise AppError(
                    409,
                    "BINDING_CODE_UNAVAILABLE",
                    "原绑定码已失效或已消费，请查询家庭关系",
                )
        elif action == "current_patient":
            result.data = self.auth.context(principal, c)
        return result

    def page(self, docs, principal, action, params, query, sort):
        limit = int(query.get("limit", 20))
        context = [
            principal.account_id,
            action,
            params,
            {k: v for k, v in query.items() if k not in ("cursor", "limit")},
        ]
        docs = sorted(docs, key=sort)
        if query.get("cursor"):
            last = self.auth.read_cursor(query["cursor"], context)
            docs = [doc for doc in docs if list(sort(doc)) > last]
        items = docs[:limit]
        cursor = (
            self.auth.cursor(context, list(sort(items[-1])))
            if len(docs) > limit
            else None
        )
        return {"items": items, "next_cursor": cursor}

    def read(self, c, action, principal, params, q):
        p = params.get("p")
        doc = self.resource(c, action, params)
        if action == "me":
            return self.auth.context(principal, c)
        if action == "patients":
            return self.page(
                self.auth.context(principal, c)["patients"],
                principal,
                action,
                params,
                q,
                lambda d: (d["patient"]["patient_id"],),
            )
        if action == "patient":
            return get(c, "Patient", p)
        if action in ("bindings", "grants"):
            kind = "FamilyBinding" if action == "bindings" else "Grant"
            items = all_docs(c, kind, p)
            if not self.auth.is_self(principal, p, c):
                field = (
                    "family_account_id"
                    if action == "bindings"
                    else "grantee_account_id"
                )
                items = [d for d in items if d[field] == principal.account_id]
            if action == "grants":
                for grant in items:
                    if (
                        grant["status"] == "active"
                        and grant["valid_until"]
                        and grant["valid_until"] <= stamp(self.clock())
                    ):
                        grant["status"] = (
                            "expired"  # Read-only projection; history is untouched.
                        )
            return self.page(
                items,
                principal,
                action,
                params,
                q,
                lambda d: (
                    d["established_at"] if action == "bindings" else d["confirmed_at"],
                    d["binding_id"] if action == "bindings" else d["grant_id"],
                ),
            )
        if action == "definition":
            return cas.definition()
        if action in ("response", "profile", "plan", "file", "draft"):
            return doc
        if action == "latest_submission":
            responses = [
                response
                for response in all_docs(c, "QuestionnaireResponse", p)
                if response["status"] == "submitted"
            ]
            if not responses:
                raise AppError(404, "PROFILE_NOT_AVAILABLE", "尚无已提交的问卷")
            submission = max(
                enumerate(responses),
                key=lambda item: (item[1]["submitted_at"], item[0]),
            )[1]
            profiles = [
                profile
                for profile in all_docs(c, "Profile", p)
                if profile["response_id"] == submission["response_id"]
            ]
            return {
                "response_id": submission["response_id"],
                "submitted_at": submission["submitted_at"],
                "profile": profiles[-1] if profiles else None,
            }
        if action == "current_profile":
            profiles = all_docs(c, "Profile", p)
            if not profiles:
                raise AppError(404, "PROFILE_NOT_AVAILABLE", "尚未创建画像结果")
            return profiles[-1]
        if action in ("medications", "plans", "files", "drafts"):
            kind = {
                "medications": "Medication",
                "plans": "PlanVersion",
                "files": "File",
                "drafts": "Draft",
            }[action]
            items = all_docs(c, kind, p)
            if action == "plans" and q.get("plan_id"):
                items = [d for d in items if d["plan_id"] == q["plan_id"]]
            if action == "drafts" and q.get("status"):
                items = [d for d in items if d["status"] == q["status"]]
            identifier = {
                "Medication": "medication_id",
                "PlanVersion": "plan_id",
                "File": "file_id",
                "Draft": "draft_id",
            }[kind]

            def order(d):
                return (
                    (d["confirmed_at"], d["plan_id"], d["plan_version"])
                    if kind == "PlanVersion"
                    else (
                        d["meta"]["updated_at" if kind == "Draft" else "created_at"],
                        d[identifier],
                    )
                )

            return self.page(items, principal, action, params, q, order)
        if action == "file_medication_recognition":
            return recognize(
                self.llm,
                doc["media_type"],
                self.stored_bytes(doc),
                doc["original_name"],
            )
        if action == "file_content":
            raw = self.stored_bytes(doc)
            return {
                "file_id": doc["file_id"],
                "media_type": doc["media_type"],
                "content_encoding": "base64",
                "content_base64": base64.b64encode(raw).decode("ascii"),
                "sha256": doc["sha256"],
            }
        if action == "reminder":
            preferences = get(c, "ReminderPreferences", p, required=False)
            if not preferences:
                raise AppError(
                    404,
                    "REMINDER_PREFERENCES_NOT_INITIALIZED",
                    "尚未保存提醒设置；默认关闭",
                )
            return preferences
        if action == "slots":
            start, end = q["window_start"], q["window_end"]
            for plan in all_docs(c, "PlanVersion", p):
                left = max(start, plan["effective_from"])
                right = min(end, plan["effective_until"] or end)
                require_coverage(
                    c, plan, left, right, "该窗口尚未显式物化，不能当作零安排"
                )
            items = [
                {
                    k: r[k]
                    for k in (
                        "dose_slot_id",
                        "patient_id",
                        "plan_id",
                        "plan_version",
                        "plan_entry_id",
                        "medication_id",
                        "scheduled_at",
                        "status",
                        "source_rule_version",
                        "is_simulated",
                    )
                }
                for r in c.execute(
                    "SELECT * FROM dose_slots WHERE patient_id=? AND data_environment=? AND scheduled_at>=? AND scheduled_at<? ORDER BY scheduled_at,dose_slot_id",
                    (p, "demo", start, end),
                )
            ]
            for item in items:
                item["is_simulated"] = bool(item["is_simulated"])
            page = self.page(
                items,
                principal,
                action,
                params,
                q,
                lambda d: (d["scheduled_at"], d["dose_slot_id"]),
            )
            return {**page, "window_start": start, "window_end": end}
        raise RuntimeError("unregistered read")

    def write(self, c, action, principal, params, b, content):
        at = stamp(self.clock())
        p = params.get("p")
        doc = self.resource(c, action, params)
        if doc:
            p = doc["patient_id"]
        if action == "login":
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            key = digest(token)
            expires = stamp(self.clock() + timedelta(hours=8))
            c.execute(
                "INSERT INTO o_sessions VALUES (?,?,?,?,?,?,NULL)",
                (
                    key,
                    b["demo_account_id"],
                    digest(csrf),
                    protect(csrf.encode("utf8"), "session:" + key),
                    at,
                    expires,
                ),
            )
            return Result(
                self.auth.context(Principal(b["demo_account_id"], key), c),
                201,
                token,
                expires,
            )
        if action == "logout":
            row = self.auth.session(principal, c, logout_receipt=True)
            if row["revoked_at"]:
                raise AppError(
                    401,
                    "AUTH_REQUIRED",
                    "当前会话已退出，不能创建新的退出操作；历史回执缺少会话绑定时不能安全重放，请核对登录状态",
                )
            c.execute(
                "UPDATE o_sessions SET revoked_at=? WHERE session_hash=?",
                (at, principal.session_hash),
            )
            operation = uid()
            c.execute(
                "INSERT INTO operation_audit VALUES (?,?,NULL,?,?,?,?)",
                (operation, principal.account_id, "logout", "logged_out", at, "demo"),
            )
            return Result(
                {
                    "operation_id": operation,
                    "outcome": "logged_out",
                    "affected_ids": [],
                    "completed_at": at,
                }
            )
        if action == "current_patient":
            c.execute(
                "UPDATE o_accounts SET current_patient_id=? WHERE account_id=?",
                (b["patient_id"], principal.account_id),
            )
            return Result(
                self.auth.context(principal, c),
                sensitive_until=self.auth.session(principal, c)["expires_at"],
            )
        if action in ("patient_patch", "medication_patch"):
            if action == "patient_patch":
                doc = get(c, "Patient", p)
            expected(doc, b["expected_revision"])
            new = changed(doc, at)
            for field in (
                ("display_name", "timezone")
                if action == "patient_patch"
                else ("name", "notes")
            ):
                if field in b:
                    new[field] = b[field]
            kind = "Patient" if action == "patient_patch" else "Medication"
            identifier = p if kind == "Patient" else params["id"]
            return Result(
                save(c, kind, identifier, p, new),
                resource_type=kind,
                resource_id=identifier,
            )
        if action == "binding_code":
            code = secrets.token_urlsafe(18)
            code_id = uid()
            expires = stamp(self.clock() + timedelta(minutes=5))
            c.execute(
                "INSERT INTO o_binding_codes VALUES (?,?,?,?,?,NULL)",
                (code_id, digest(code), p, principal.session_hash, expires),
            )
            return Result(
                {
                    "code_id": code_id,
                    "binding_code": code,
                    "patient_id": p,
                    "expires_at": expires,
                    "is_simulated": True,
                },
                201,
                sensitive_until=expires,
                resource_type="BindingCode",
                resource_id=code_id,
            )
        if action == "redeem":
            row = c.execute(
                "SELECT * FROM o_binding_codes WHERE code_hash=?",
                (digest(b["binding_code"]),),
            ).fetchone()
            if not row or row["consumed_at"] or row["expires_at"] <= at:
                raise AppError(
                    409, "BINDING_CODE_UNAVAILABLE", "绑定码无效、已消费或已过期"
                )
            p = row["patient_id"]
            if self.auth.is_self(principal, p, c):
                raise AppError(409, "BINDING_CODE_UNAVAILABLE", "不能绑定自己")
            if any(
                x["family_account_id"] == principal.account_id
                and x["status"] == "active"
                for x in all_docs(c, "FamilyBinding", p)
            ):
                raise AppError(
                    409, "BINDING_ALREADY_EXISTS", "已有有效关系，请查询当前授权"
                )
            identifier = uid()
            new = {
                "binding_id": identifier,
                "patient_id": p,
                "family_account_id": principal.account_id,
                "status": "active",
                "established_at": at,
                "revoked_at": None,
                "meta": meta(at),
            }
            c.execute(
                "UPDATE o_binding_codes SET consumed_at=? WHERE code_id=?",
                (at, row["code_id"]),
            )
            return Result(
                save(c, "FamilyBinding", identifier, p, new),
                201,
                resource_type="FamilyBinding",
                resource_id=identifier,
            )
        if action in ("revoke_binding", "revoke_grant"):
            expected(doc, b["expected_revision"])
            if doc["status"] != "active":
                raise AppError(409, "INVALID_STATE", "该关系或授权已不是有效状态")
            new = changed(doc, at)
            new.update(status="revoked", revoked_at=at)
            kind = "FamilyBinding" if action == "revoke_binding" else "Grant"
            identifier = params["id"]
            if kind == "Grant":
                new["grant_version"] += 1
            save(c, kind, identifier, p, new)
            if kind == "FamilyBinding":
                for grant in all_docs(c, "Grant", p):
                    if (
                        grant["binding_id"] == identifier
                        and grant["status"] == "active"
                    ):
                        g = changed(grant, at)
                        g.update(
                            status="revoked",
                            revoked_at=at,
                            grant_version=grant["grant_version"] + 1,
                        )
                        save(c, "Grant", grant["grant_id"], p, g)
            operation_id = uid()
            c.execute(
                "INSERT INTO operation_audit VALUES (?,?,?,?,?,?,?)",
                (operation_id, principal.account_id, p, action, "revoked", at, "demo"),
            )
            c.execute(
                "INSERT INTO o_revocation_audit VALUES (?,?,?,?)",
                (operation_id, kind, identifier, b["reason"]),
            )
            return Result(new, resource_type=kind, resource_id=identifier)
        if action == "grant_put":
            if doc["status"] != "active":
                raise AppError(
                    409, "BINDING_REVOKED", "请重新建立关系，不能恢复已解除关系"
                )
            grants = [
                g
                for g in all_docs(c, "Grant", p)
                if g["binding_id"] == doc["binding_id"]
            ]
            latest = grants[-1] if grants else None
            if b["expected_revision"] != (latest["meta"]["revision"] if latest else 0):
                raise AppError(409, "GRANT_VERSION_CONFLICT", "授权已更新，请重新核对")
            if b["valid_until"] is not None and b["valid_until"] <= at:
                raise AppError(422, "VALIDATION_ERROR", "授权截止必须在未来")
            active = (
                latest
                and latest["status"] == "active"
                and (latest["valid_until"] is None or latest["valid_until"] > at)
            )
            identifier = latest["grant_id"] if active else uid()
            new = changed(latest, at) if active else {"meta": meta(at)}
            new.update(
                grant_id=identifier,
                binding_id=doc["binding_id"],
                patient_id=p,
                grantee_account_id=doc["family_account_id"],
                scopes=b["scopes"],
                grant_version=(latest["grant_version"] + 1 if active else 1),
                status="active",
                valid_until=b["valid_until"],
                confirmed_at=at,
                revoked_at=None,
            )
            return Result(
                save(c, "Grant", identifier, p, new),
                resource_type="Grant",
                resource_id=identifier,
            )
        if action == "response_create":
            own = self.auth.is_self(principal, p, c)
            mode = "self" if own else "family_assisted"
            identifier = uid()
            answers = {
                f"Q{i}": {
                    "value": {},
                    "answered_by": mode,
                    "updated_at": at,
                }
                for i in range(1, 9)
            }
            new = {
                "response_id": identifier,
                "patient_id": p,
                "questionnaire_version": cas.VERSION,
                "respondent_account_id": principal.account_id,
                "respondent_mode": mode,
                "status": "draft",
                "answers": answers,
                "supersedes_response_id": b.get("supersedes_response_id"),
                "submitted_at": None,
                "meta": meta(at),
            }
            return Result(
                save(c, "QuestionnaireResponse", identifier, p, new),
                201,
                resource_type="QuestionnaireResponse",
                resource_id=identifier,
            )
        if action in ("answers", "submit_response"):
            expected(doc, b["expected_revision"], "RESPONSE_REVISION_CONFLICT")
            if doc["status"] != "draft":
                raise AppError(
                    409,
                    "RESPONSE_ALREADY_SUBMITTED",
                    "已提交回答不能原地修改，请建立更正副本",
                )
            new = changed(doc, at)
            if action == "answers":
                for q, a in b["answers"].items():
                    old = doc["answers"][q]
                    if a != old["value"]:
                        new["answers"][q] = {
                            "value": a,
                            "answered_by": doc["respondent_mode"],
                            "updated_at": at,
                        }
            else:
                new["same_episode"] = b.get("same_episode")
                new.update(status="submitted", submitted_at=at)
            return Result(
                save(c, "QuestionnaireResponse", params["id"], p, new),
                resource_type="QuestionnaireResponse",
                resource_id=params["id"],
            )
        if action == "profile_create":
            response = get(c, "QuestionnaireResponse", b["response_id"])
            if response["patient_id"] != p:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            if response["status"] != "submitted":
                raise AppError(409, "RESPONSE_NOT_SUBMITTED", "请先明确提交问卷修订")
            for profile in all_docs(c, "Profile", p):
                if (
                    profile["response_id"] == b["response_id"]
                    and profile["assessment_method_version"] == cas.METHOD
                    and profile["cas"]["model_version"]
                    == (self.cas_model.model_version if self.cas_model else None)
                ):
                    return Result(
                        profile,
                        201,
                        resource_type="Profile",
                        resource_id=profile["profile_id"],
                    )
            identifier = uid()
            assessment = cas.assess(response, self.cas_model)
            new = {
                "profile_id": identifier,
                "patient_id": p,
                "response_id": b["response_id"],
                **assessment,
                "questionnaire_version": response["questionnaire_version"],
                "generated_at": at,
                "meta": meta(at),
            }
            return Result(
                save(c, "Profile", identifier, p, new),
                201,
                resource_type="Profile",
                resource_id=identifier,
            )
        if action == "medication_create":
            identifier = uid()
            new = {
                "medication_id": identifier,
                "patient_id": p,
                "name": b["name"],
                "notes": b.get("notes"),
                "meta": meta(at),
            }
            return Result(
                save(c, "Medication", identifier, p, new),
                201,
                resource_type="Medication",
                resource_id=identifier,
            )
        if action in ("draft_create", "draft_put", "draft_submit"):
            return self.write_draft(c, action, params, p, b, doc, at)
        if action == "plan_confirm":
            return self.confirm_plan(c, principal, p, b, at)
        if action == "reminder_put":
            settings = b["settings"]
            doc = get(c, "ReminderPreferences", p, required=False)
            if b["expected_revision"] != (doc["meta"]["revision"] if doc else 0):
                raise AppError(409, "REVISION_CONFLICT", "提醒设置已更新，请重新读取")
            if (
                set(settings["channels"]) != {"in_app"}
                or settings["sound_enabled"]
                or settings["vibration_enabled"]
            ):
                raise AppError(
                    422,
                    "UNSUPPORTED_REMINDER_CONFIGURATION",
                    "当前仅保存应用内提醒；系统通知、声音和振动能力尚未接入",
                )
            if settings["notify_family"] and (
                not self.auth.is_self(principal, p, c)
                or not any(
                    g["status"] == "active"
                    and "notify:receive" in g["scopes"]
                    and (g["valid_until"] is None or g["valid_until"] > at)
                    for g in all_docs(c, "Grant", p)
                )
            ):
                raise AppError(
                    403,
                    "SCOPE_REQUIRED",
                    "通知家人还需要患者明确同意及有效接收授权",
                )
            # Privacy notifications always use an approved neutral phrase; no guessing disease names.
            if settings["privacy_enabled"] and settings["custom_text"] not in (
                None,
                "今日事项待确认。",
                "有一项日程需要处理。",
            ):
                raise AppError(
                    422,
                    "UNSUPPORTED_REMINDER_CONFIGURATION",
                    "隐私模式请使用中性文案，避免泄露药品或疾病信息",
                )
            # This phase saves preferences only. Per-dose anchor/medical/next-slot
            # checks belong to S03 execution; no scheduled_at is shifted here.
            new = {
                "patient_id": p,
                **settings,
                "meta": changed(doc, at)["meta"] if doc else meta(at),
            }
            return Result(
                save(c, "ReminderPreferences", p, p, new),
                resource_type="ReminderPreferences",
                resource_id=p,
            )
        if action == "file_upload":
            return self.upload(c, principal, p, b, content, at)
        raise RuntimeError("unregistered write")

    def write_draft(self, c, action, params, p, b, doc, at):
        identifier = uid() if action == "draft_create" else params["id"]
        if action == "draft_create":
            new = {
                "draft_id": identifier,
                "patient_id": p,
                "source": "manual_transcription" if b["source_file_ids"] else "manual",
                "source_file_ids": b["source_file_ids"],
                "entries": b["entries"],
                "content_revision": 1,
                "status": "editing",
                "submission_id": None,
                "submitted_revision": None,
                "formal_plan": None,
                "return_reason": None,
                "meta": meta(at, "A-v0.4"),
            }
        else:
            expected(doc, b["expected_revision"])
            new = changed(doc, at)
            if doc["status"] not in ("editing", "returned"):
                if (
                    action == "draft_submit"
                    and doc["status"] == "pending_confirmation"
                    and doc["submitted_revision"] == b["content_revision"]
                ):
                    return Result(doc)
                raise AppError(409, "DRAFT_LOCKED", "此草稿已提交或确认，不能覆盖")
            if action == "draft_put":
                new.update(
                    source_file_ids=b["source_file_ids"],
                    entries=b["entries"],
                    source="manual_transcription" if b["source_file_ids"] else "manual",
                    content_revision=doc["content_revision"] + 1,
                    status="editing",
                    return_reason=None,
                )
            else:
                if doc["content_revision"] != b["content_revision"]:
                    raise AppError(
                        409, "DRAFT_CONTENT_CONFLICT", "内容修订已更新，请重新核对"
                    )
                new.update(
                    status="pending_confirmation",
                    submission_id=uid(),
                    submitted_revision=b["content_revision"],
                    return_reason=None,
                )
        return Result(
            save(c, "Draft", identifier, p, new),
            201 if action == "draft_create" else 200,
            resource_type="Draft",
            resource_id=identifier,
        )

    def confirm_plan(self, c, principal, p, b, at):
        draft = get(c, "Draft", b["draft_id"])
        if (
            draft["content_revision"] != b["draft_revision"]
            or draft["submitted_revision"] != b["draft_revision"]
        ):
            raise AppError(409, "DRAFT_REVISION_CONFLICT", "请核对已提交的精确内容修订")
        if draft["status"] == "confirmed":
            ref = draft["formal_plan"]
            plan = get(
                c, "PlanVersion", ref["plan_id"] + ":" + str(ref["plan_version"])
            )
            if plan["effective_from"] != b["effective_from"] or (
                b["existing_plan_id"] and plan["plan_id"] != b["existing_plan_id"]
            ):
                raise AppError(
                    409,
                    "DRAFT_ALREADY_CONFIRMED",
                    "此修订已有正式引用，不能用另一内容重复发版",
                )
            return Result(
                plan, 201, resource_type="PlanVersion", resource_id=plan["plan_id"]
            )
        if draft["status"] != "pending_confirmation":
            raise AppError(409, "DRAFT_NOT_SUBMITTED", "请先提交明确草稿修订")
        if b["effective_from"] < at:
            raise AppError(
                422, "INVALID_EFFECTIVE_TIME", "普通计划只接受服务器当前或未来生效点"
            )
        first_day = (
            datetime.fromisoformat(b["effective_from"]).astimezone(SHANGHAI).date()
        )
        try:
            first_day + timedelta(days=31)
        except OverflowError:
            raise AppError(
                422, "INVALID_EFFECTIVE_TIME", "此日期无法建立完整计划窗口"
            ) from None
        incomplete = any(
            any(
                e[field] is None
                for field in ("dose_value", "dose_unit", "start_date", "schedule")
            )
            for e in draft["entries"]
        )
        if incomplete:
            returned = changed(draft, at)
            returned.update(
                status="returned",
                return_reason="资料缺少剂量、单位、开始日期或固定安排；请人工核对后重新提交",
            )
            save(c, "Draft", b["draft_id"], p, returned)
            return Result(
                None,
                409,
                resource_type="Draft",
                resource_id=b["draft_id"],
                error={"code": "INCOMPLETE_PLAN", "message": returned["return_reason"]},
            )
        previous = None
        plan_id = b["existing_plan_id"] or uid()
        version = 1
        if b["existing_plan_id"]:
            versions = [
                d for d in all_docs(c, "PlanVersion", p) if d["plan_id"] == plan_id
            ]
            if not versions:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            previous = max(versions, key=lambda d: d["plan_version"])
            if (
                previous["plan_version"] != b["expected_plan_version"]
                or b["effective_from"] <= previous["effective_from"]
            ):
                raise AppError(
                    409,
                    "PLAN_VERSION_CONFLICT",
                    "正式计划版本或生效顺序已变化，请重新核对",
                )
            version = previous["plan_version"] + 1
        entries = []
        for entry in draft["entries"]:
            med = get(c, "Medication", entry["medication_id"])
            entries.append(
                {k: copy.deepcopy(v) for k, v in entry.items() if k != "draft_entry_id"}
            )
            entries[-1].update(
                plan_entry_id=uid(), medication_name_snapshot=med["name"]
            )
            if entry["min_interval_minutes"]:
                inspection_start = max(
                    first_day, date.fromisoformat(entry["start_date"])
                )
                inspection_end = (
                    date.fromisoformat(entry["end_date"])
                    if entry["end_date"]
                    else date.max
                )
                inspection_days = min(
                    15, max(0, (inspection_end - inspection_start).days + 1)
                )
                moments = [
                    moment
                    for moment in occurrences(
                        entry,
                        inspection_start,
                        inspection_start + timedelta(days=inspection_days - 1),
                    )
                    if stamp(moment) >= b["effective_from"]
                ]
                gaps = [
                    (later - earlier).total_seconds() / 60
                    for earlier, later in itertools.pairwise(moments)
                ]
                if gaps and min(gaps) < entry["min_interval_minutes"]:
                    raise AppError(
                        422,
                        "MEDICAL_CONSTRAINT_CONFLICT",
                        "安排与资料中的最小间隔冲突，请人工核对原医嘱",
                    )
        if previous:
            old = changed(previous, at)
            old.update(status="superseded", effective_until=b["effective_from"])
            save(
                c, "PlanVersion", plan_id + ":" + str(previous["plan_version"]), p, old
            )
            c.execute(
                "UPDATE dose_slots SET status='superseded' WHERE patient_id=? AND data_environment='demo' AND plan_id=? AND plan_version=? AND scheduled_at>=?",
                (p, plan_id, previous["plan_version"], b["effective_from"]),
            )
        plan = {
            "plan_id": plan_id,
            "plan_version": version,
            "patient_id": p,
            "status": "confirmed",
            "effective_from": b["effective_from"],
            "effective_until": None,
            "timezone": "Asia/Shanghai",
            "entries": entries,
            "source_draft_id": b["draft_id"],
            "source_draft_revision": b["draft_revision"],
            "confirmed_by_account_id": principal.account_id,
            "confirmed_at": at,
            "is_confirmation_simulated": True,
            "meta": meta(at),
        }
        save(c, "PlanVersion", plan_id + ":" + str(version), p, plan)
        confirmed = changed(draft, at)
        confirmed.update(
            status="confirmed",
            formal_plan={"plan_id": plan_id, "plan_version": version},
            return_reason=None,
        )
        save(c, "Draft", b["draft_id"], p, confirmed)
        self.materialize(c, plan)
        return Result(plan, 201, resource_type="PlanVersion", resource_id=plan_id)

    def materialize(self, c, plan):
        effective = datetime.fromisoformat(plan["effective_from"])
        start = effective.astimezone(SHANGHAI).date()
        end = start + timedelta(days=31)
        right = datetime.combine(end, time(), SHANGHAI)
        for entry in plan["entries"]:
            for scheduled in occurrences(entry, start, end - timedelta(days=1)):
                if scheduled >= effective:
                    insert_slot(c, plan, entry, scheduled)
        c.execute(
            "INSERT INTO o_schedule_windows VALUES (?,?,?,?)",
            (
                plan["plan_id"],
                plan["plan_version"],
                plan["effective_from"],
                stamp(right),
            ),
        )

    def stored_bytes(self, doc):
        try:
            raw = (self.file_root / (doc["file_id"] + ".blob")).read_bytes()
            if fingerprint_bytes(raw) != doc["sha256"] or len(raw) != doc["size_bytes"]:
                raise ValueError()
        except OSError, ValueError:
            raise AppError(
                503, "FILE_CONTENT_UNAVAILABLE", "原文件暂不可用，请核对受控存储"
            ) from None
        return raw

    def upload(self, c, principal, p, b, raw, at):
        claim = c.execute(
            "SELECT * FROM s02_source_keys WHERE resource_type=? AND patient_id=? AND account_id=? AND source_id=?",
            ("File", p, principal.account_id, b["source_event_id"]),
        ).fetchone()
        fp = fingerprint(b)
        if claim:
            if claim["fingerprint"] != fp:
                raise AppError(
                    409, "SOURCE_EVENT_CONFLICT", "同一来源编号对应不同文件内容或语义"
                )
            return Result(get(c, "File", claim["resource_key"].split(":", 1)[1]), 201)
        identifier = uid()
        new = {
            "file_id": identifier,
            "patient_id": p,
            **b,
            "status": "saved",
            "source": "manual_upload",
            "meta": meta(at, "A-v0.4"),
        }
        temp = self.file_root / (identifier + ".pending")
        destination = self.file_root / (identifier + ".blob")
        try:
            self.file_root.mkdir(parents=True, exist_ok=True)
            with temp.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if fingerprint_bytes(temp.read_bytes()) != b["sha256"]:
                raise OSError("content validation failed")
            temp.rename(
                destination
            )  # Unique UUID, never replace an existing patient's file.
        except OSError:
            raise AppError(
                503, "FILE_STORE_UNAVAILABLE", "文件保存未完成，请用原操作键核查或重试"
            ) from None
        save(c, "File", identifier, p, new)
        c.execute(
            "INSERT INTO s02_source_keys VALUES (?,?,?,?,?,?)",
            (
                "File",
                p,
                principal.account_id,
                b["source_event_id"],
                fp,
                "File:" + identifier,
            ),
        )
        return Result(new, 201, resource_type="File", resource_id=identifier)
