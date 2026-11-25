"""The single C service creator, patient views, and legal service transitions."""

import json

from ...core.documents import changed, encode, fingerprint, get, meta, stamp, uid
from ...core.errors import AppError
from ...core.idempotency import Result
from ..catalog.service import current_resource
from ..common import (
    CONTRACT,
    authenticate_provider,
    missing,
    next_cursor,
    page_after,
    read_guarded,
)
from ..drafts.service import scope_descriptor

TRANSITIONS = {
    "submitted": {"in_progress", "cancelled", "failed"},
    "in_progress": {"completed", "cancelled", "failed"},
}


def confirmation_required(message="请核对本草稿修订的有效确认及共享范围"):
    return AppError(409, "SERVICE_CONFIRMATION_REQUIRED", message)


class Services:
    def __init__(self, db, drafts, execution, settings, clock):
        self.db, self.auth, self.receipts = db, drafts.auth, drafts.receipts
        self.clock, self.drafts, self.execution, self.settings = (
            clock,
            drafts,
            execution,
            settings,
        )
        self.peer = None

    def authenticate_provider(self, header):
        return authenticate_provider(
            header,
            self.settings.DEMO_SERVICE_RECEIPT_TOKEN.get_secret_value(),
            self.settings.DEMO_SERVICE_RECEIPT_SUBJECT,
            "SERVICE_PROVIDER_UNAVAILABLE",
            "可信服务方回执未配置，本地演示控制台仍可使用",
            "需使用独立的模拟服务方凭据",
        )

    def service(self, conn, identifier):
        row = conn.execute(
            "SELECT document_json FROM c_service_history WHERE service_id=? ORDER BY revision DESC LIMIT 1",
            (identifier,),
        ).fetchone()
        if row is None:
            raise missing()
        return json.loads(row[0])

    def authorize(self, conn, action, principal, path):
        if action in {"submit_service", "list_services"}:
            patient, doc = path["p"], None
        else:
            doc = self.service(conn, path["id"])
            patient = doc["patient_id"]
        if action == "demo_transition":
            self.execution._admin(conn, principal)
        else:
            self.auth.require_patient(
                principal,
                patient,
                "services:read"
                if action in {"read_service", "list_services"}
                else "services:apply",
                conn,
                self_only=action in {"submit_service", "cancel_service"},
            )
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "本期只使用本地虚构患者和资源")
        return patient, doc

    def handle(self, action, principal, path, query, body, key):
        if action == "provider_receipt":
            return self.provider_receipt(principal, body, key)

        def authorize(conn):
            return self.authorize(conn, action, principal, path)

        with self.db.connection(readonly=True) as conn:
            if action in {"list_services", "read_service"}:
                with read_guarded(conn, authorize) as (patient, doc):
                    data = self.read(conn, principal, patient, doc, query)
                return Result(data)
            conn.execute("BEGIN")
            patient, _ = authorize(conn)
        scope = ["demo", "account", principal.account_id, patient, "C", action, path]

        def operation(conn):
            _, current = authorize(conn)
            if action == "submit_service":
                data = self.submit(conn, principal, patient, body)
            elif action == "cancel_service":
                data = self.cancel(conn, principal, current, body)
            else:
                data = self.demo_transition(conn, principal, current, body)
            return Result(
                data,
                201 if action == "submit_service" else 200,
                resource_type="Service",
                resource_id=data["service_id"],
            )

        def replay(conn, result):
            if action == "submit_service":
                self.prepared(conn, principal, patient, body, stamp(self.clock()))
            result.data = self.service(conn, result.resource_id)
            return result

        return self.receipts.run(
            scope,
            key,
            {"path": path, "query": query, "body": body},
            authorize,
            operation,
            replay,
        )

    def read(self, conn, principal, patient, doc, query):
        own = self.auth.is_self(principal, patient, conn)

        def visible(value):
            if own:
                return value
            return dict(
                value,
                request_text="问题正文仅本人可查看",
                provider_response=None,
                result_summary="已保存结果" if value["result_summary"] else None,
                failure_reason="详情由本人查看" if value["failure_reason"] else None,
                cancellation_reason=None,
                source_suggestion_id=None,
                source_referral_id=None,
            )

        if doc is not None:
            return visible(doc)
        context = [principal.account_id, "C08", patient, query.get("status")]
        descending = query.get("order", "asc") == "desc"
        if descending:
            context.append("desc")
        after = page_after(
            self.auth, query, context, ["\uffff", "\uffff"] if descending else ["", ""]
        )
        limit = query.get("limit", 20)
        # Only internal constants enter SQL; cursors remain bound to sort direction.
        comparison, ordering = ("<", "DESC") if descending else (">", "ASC")
        rows = conn.execute(
            f"""SELECT h.document_json FROM c_services s JOIN c_service_history h ON s.service_id=h.service_id
               AND h.revision=(SELECT MAX(r.revision) FROM c_service_history r WHERE r.service_id=s.service_id)
               WHERE s.patient_id=? AND (s.submitted_at,s.service_id){comparison}(?,?)
               AND (? IS NULL OR h.status=?)
               ORDER BY s.submitted_at {ordering},s.service_id {ordering} LIMIT ?""",
            (patient, *after, query.get("status"), query.get("status"), limit + 1),
        ).fetchall()
        items = [visible(json.loads(r[0])) for r in rows[:limit]]
        cursor = next_cursor(
            rows,
            limit,
            self.auth,
            context,
            lambda _: [items[-1]["submitted_at"], items[-1]["service_id"]],
        )
        return {"items": items, "next_cursor": cursor}

    def consent(self, conn, doc, at):
        try:
            consent = self.drafts.confirmation(conn, doc["confirmation_ref_id"])
        except AppError as exc:
            if exc.status == 404:
                raise confirmation_required() from None
            raise
        if (
            consent["patient_id"] != doc["patient_id"]
            or consent["sharing_scope_ref_id"] != doc["sharing_scope_ref_id"]
            or consent["revoked_at"] is not None
            or not consent["confirmed_at"] <= at < consent["valid_until"]
            or (consent["resource_id"], consent["resource_version"])
            != (doc["resource_id"], doc["resource_version"])
        ):
            raise confirmation_required()
        resource = current_resource(conn, doc)
        if resource is None or resource["access_mode"] != "support_free":
            raise confirmation_required("资源已停用或版本有变化，请重新核对")
        provider, purpose = resource["provider"], resource["service_kind"]
        if (consent["provider_id"], consent["service_kind"]) != (
            provider["provider_id"],
            purpose,
        ):
            raise confirmation_required()
        scope = self.drafts.sharing.scope(
            conn, doc["sharing_scope_ref_id"], doc["patient_id"], at
        )
        categories = scope["data_categories"]
        required = set(resource["required_shared_categories"])
        if (
            scope["status"] != "active"
            or (scope["recipient_id"], scope["recipient_type"], scope["purpose_code"])
            != (provider["provider_id"], provider["provider_type"], purpose)
            or not required
            <= set(categories)
            <= required | set(resource["optional_shared_categories"])
            or scope_descriptor(doc["patient_id"], resource, categories)
            != consent["descriptor_hash"]
        ):
            raise confirmation_required("O 共享授权已变更或失效，请重新核对")
        deadline = min(consent["valid_until"], scope["valid_until"])
        return resource, scope, deadline

    def prepared(self, conn, principal, patient, body, at):
        self.auth.require_patient(
            principal, patient, "services:apply", conn, self_only=True
        )
        draft = self.drafts.draft(conn, body["service_draft_id"])
        if draft["patient_id"] != patient:
            raise missing()
        if (
            draft["draft_revision"] != body["draft_revision"]
            or draft["status"] == "abandoned"
        ):
            raise confirmation_required("草稿内容修订已变化，请本人核对当前修订")
        link = conn.execute(
            """SELECT 1 FROM c_draft_confirmations WHERE patient_id=? AND service_draft_id=?
               AND draft_revision=? AND confirmation_ref_id=?""",
            (
                patient,
                draft["service_draft_id"],
                draft["draft_revision"],
                body["confirmation_ref_id"],
            ),
        ).fetchone()
        if link is None:
            raise confirmation_required()
        resource, _, deadline = self.consent(conn, dict(draft) | body, at)
        return draft, resource, deadline

    def submit(
        self,
        conn,
        principal,
        patient,
        body,
        *,
        referral_id=None,
        suggestion_id=None,
        resource_id=None,
        prepared=None,
    ):
        at = stamp(self.clock())
        draft, resource, deadline = (
            prepared
            if prepared is not None
            else self.prepared(conn, principal, patient, body, at)
        )
        if resource_id is not None and resource_id != draft["resource_id"]:
            raise confirmation_required("转介资源与已确认草稿不一致")
        if draft["status"] == "submitted":
            old = self.service(conn, draft["service_id"])
            if (
                old["draft_revision"],
                old["confirmation_ref_id"],
                old["sharing_scope_ref_id"],
            ) != (
                body["draft_revision"],
                body["confirmation_ref_id"],
                body["sharing_scope_ref_id"],
            ):
                raise confirmation_required("草稿已有正式服务，请核对原申请")
            return old
        group = resource["peer_group_id"]
        peer = None
        if group is not None:
            if self.peer is None:
                raise AppError(503, "PEER_GROUPS_UNAVAILABLE", "模拟小组能力暂不可用")
            peer = self.peer
            peer.check_submission(conn, principal, patient, resource)

        identifier, task_id = uid(), uid()
        doc = dict(
            service_id=identifier,
            patient_id=patient,
            **body,
            resource_id=resource["resource_id"],
            resource_version=resource["resource_version"],
            service_name=resource["name"],
            service_kind=resource["service_kind"],
            provider=resource["provider"],
            request_text=draft["request_text"],
            status="submitted",
            submitted_at=at,
            started_at=None,
            completed_at=None,
            cancelled_at=None,
            failed_at=None,
            failure_reason=None,
            cancellation_requested=False,
            cancellation_reason=None,
            source_suggestion_id=suggestion_id,
            source_referral_id=referral_id,
            dispatch_task_id=task_id,
            result_summary=None,
            provider_response=None,
            meta=meta(at, CONTRACT),
        )
        conn.execute(
            "INSERT INTO c_services VALUES (?,?,?,?,?,?,?,?)",
            (
                identifier,
                patient,
                draft["service_draft_id"],
                draft["draft_revision"],
                body["confirmation_ref_id"],
                body["sharing_scope_ref_id"],
                task_id,
                at,
            ),
        )
        self.record(
            conn,
            doc,
            "b_referral" if referral_id else "patient_submit",
            principal.account_id,
            at,
            at,
            referral_id,
        )
        self.execution.create_in_transaction(
            conn,
            principal,
            {
                "patient_id": patient,
                "kind": "dispatch_service",
                "owner_module": "C",
                "owner_operation_key": "dispatch_service:" + identifier,
                "scheduled_at": at,
                "valid_until": deadline,
                "rule_version": CONTRACT,
                "payload": {
                    "service_id": identifier,
                    "service_revision": 1,
                    "confirmation_ref_id": body["confirmation_ref_id"],
                    "sharing_scope_ref_id": body["sharing_scope_ref_id"],
                },
            },
            internal=True,
            task_id=task_id,
        )
        conn.execute(
            """UPDATE c_service_drafts SET status='submitted', service_id=?, revision=revision+1, updated_at=?
               WHERE service_draft_id=?""",
            (identifier, at, draft["service_draft_id"]),
        )
        if peer is not None:
            peer.attach(conn, principal, doc, group, at)
        return doc

    @staticmethod
    def record(conn, doc, origin, actor, occurred, recorded, event=None):
        version, identifier = doc["meta"]["revision"], doc["service_id"]
        conn.execute(
            "INSERT INTO c_service_history VALUES (?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                version,
                doc["status"],
                origin,
                actor,
                event,
                occurred,
                recorded,
                encode(doc),
            ),
        )

    def stop_scope_dispatches(self, conn, scope_id, at):
        for row in conn.execute(
            "SELECT dispatch_task_id FROM c_services WHERE sharing_scope_ref_id=?",
            (scope_id,),
        ):
            self.stop_dispatch(conn, row[0], at)

    def stop_dispatch(self, conn, task_id, at):
        task = self.execution._task(conn, task_id)
        if (
            task["status"] in {"pending", "retry_wait", "running"}
            and not task["cancellation_requested"]
        ):
            task = dict(
                changed(task, at),
                cancellation_requested=True,
                next_attempt_at=None,
                failure_reason="正式服务已停止本次待派发操作",
            )
            if task["status"] != "running":
                task["status"] = "cancelled"
            self.execution._save_task(conn, task)

    def cancel(self, conn, principal, doc, body):
        if (
            doc["meta"]["revision"] != body["expected_revision"]
            or doc["status"] not in TRANSITIONS
        ):
            raise AppError(
                409, "SERVICE_TERMINAL", "服务已结束或修订发生变化，请重新读取"
            )
        at = stamp(self.clock())
        self.drafts.sharing.scope(
            conn, doc["sharing_scope_ref_id"], doc["patient_id"], at
        )
        return self.transition(
            conn,
            doc,
            "cancelled",
            "patient_cancel",
            principal.account_id,
            at,
            at,
            reason=body["reason"],
        )

    def demo_transition(self, conn, principal, doc, body):
        target, at = body["target_status"], stamp(self.clock())
        if body["expected_revision"] != doc["meta"][
            "revision"
        ] or target not in TRANSITIONS.get(doc["status"], ()):
            raise AppError(
                409, "ILLEGAL_SERVICE_TRANSITION", "服务状态或修订不允许该模拟操作"
            )
        if target in {"in_progress", "completed"}:
            self.consent(conn, doc, at)
            if not self.execution.service_dispatch.submission(conn, doc["service_id"]):
                raise AppError(
                    409, "ILLEGAL_SERVICE_TRANSITION", "请先确认模拟派发有实际提交记录"
                )
        limit = 500 if target in {"cancelled", "failed"} else 2000
        return self.transition(
            conn,
            doc,
            target,
            "demo_transition",
            principal.account_id,
            at,
            at,
            reason=f"模拟：{body['reason']}"[:limit],
        )

    def transition(
        self,
        conn,
        doc,
        target,
        origin,
        actor,
        occurred,
        at,
        *,
        reason=None,
        response=None,
        event=None,
    ):
        if target not in TRANSITIONS.get(doc["status"], ()):
            raise AppError(409, "ILLEGAL_SERVICE_TRANSITION", "服务状态不允许该变化")
        result = dict(changed(doc, at), status=target)
        if target == "in_progress":
            result["started_at"] = occurred
        elif target == "completed":
            result.update(completed_at=occurred, result_summary=reason)
        elif target == "cancelled":
            result.update(cancelled_at=occurred, cancellation_reason=reason)
        else:
            result.update(failed_at=occurred, failure_reason=reason)
        if response is not None:
            result["provider_response"] = response
        self.record(conn, result, origin, actor, occurred, at, event)
        if target == "in_progress" and doc["service_kind"] == "peer_support":
            assert self.peer is not None
            self.peer.accept(conn, result, actor, occurred, at)
        if target in {"cancelled", "failed"}:
            self.stop_dispatch(conn, doc["dispatch_task_id"], at)
        return result

    def provider_receipt(self, subject, body, key):
        def authorize(conn):
            doc = self.service(conn, body["service_id"])
            if (
                not doc["meta"]["is_simulated"]
                or subject != doc["provider"]["provider_id"]
            ):
                raise missing()
            return doc

        with self.db.connection(readonly=True) as conn:
            patient = authorize(conn)["patient_id"]

        def receive(conn):
            doc = authorize(conn)
            return Result(
                self.receive_in_transaction(conn, doc, subject, body),
                resource_type="Service",
                resource_id=doc["service_id"],
            )

        return self.receipts.run(
            ["demo", "service_provider", subject, patient, "C11", body["service_id"]],
            key,
            body,
            authorize,
            receive,
        )

    def receive_in_transaction(self, conn, doc, subject, body):
        event, identifier = body["provider_event_id"], doc["service_id"]
        request_hash = fingerprint(body)
        old = conn.execute(
            "SELECT request_fingerprint,acknowledgement_json FROM c_service_provider_receipts WHERE provider_id=? AND provider_event_id=?",
            (subject, event),
        ).fetchone()
        if old is not None:
            if old["request_fingerprint"] != request_hash:
                raise AppError(
                    409, "SERVICE_RECEIPT_CONFLICT", "相同来源事件编号对应不同回执"
                )
            return json.loads(old["acknowledgement_json"])

        at, occurred = stamp(self.clock()), body["occurred_at"]
        target = body["status"]
        last = conn.execute(
            "SELECT occurred_at FROM c_service_history WHERE service_id=? AND revision=?",
            (identifier, doc["meta"]["revision"]),
        ).fetchone()[0]
        reason = None
        if doc["status"] not in TRANSITIONS:
            reason = "服务已终止，晚到回执留档"
        elif (
            not last <= occurred <= at
            or body["expected_revision"] != doc["meta"]["revision"]
        ):
            reason = "迟到、乱序或修订不匹配，回执留档"
        elif target not in TRANSITIONS[doc["status"]]:
            reason = "服务状态不允许该变化，回执留档"
        else:
            try:
                self.consent(conn, doc, at)
            except AppError as exc:
                if exc.code != "SERVICE_CONFIRMATION_REQUIRED":
                    raise
                reason = "当前共享授权已失效，回执留档"
        if reason is None and not self.execution.service_dispatch.confirm_submission(
            conn, doc, occurred, at
        ):
            reason = "没有可核验的原派发尝试，回执留档"
        if reason is None:
            response = (
                None
                if body["response_text"] is None
                else {
                    "provider_id": subject,
                    "origin": "mock_example",
                    "text": body["response_text"],
                    "recorded_at": at,
                    "source_refs": [],
                    "is_simulated": True,
                }
            )
            reason_text = (
                body["failure_reason"] if target == "failed" else body["result_summary"]
            )
            if reason_text:
                reason_text = ("模拟：" + reason_text)[
                    : 500 if target in {"failed", "cancelled"} else 2000
                ]
            self.transition(
                conn,
                doc,
                target,
                "provider_receipt",
                subject,
                occurred,
                at,
                reason=reason_text,
                response=response,
                event=event,
            )
        acknowledgement = {
            "operation_id": uid(),
            "resource_id": identifier,
            "applied": reason is None,
            "ignore_reason": reason,
            "received_at": at,
            "is_simulated": True,
        }
        conn.execute(
            "INSERT INTO c_service_provider_receipts VALUES (?,?,?,?,?,?)",
            (
                subject,
                event,
                identifier,
                request_hash,
                encode(body),
                encode(acknowledgement),
            ),
        )
        return acknowledgement
