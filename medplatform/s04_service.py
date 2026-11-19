"""Single application service for the S04 B cards."""
import json

from . import s04_knowledge as knowledge
from . import s04_store as store
from .documents import encode, fingerprint, get, meta, stamp, uid
from .errors import AppError
from .idempotency import Result
from .s04_dialogue import Dialogue, assessment
from .s04_model import MODEL_PROFILE_ID, MockModel, missing_usage
from .s04_state import CASES, CASE_VERSION, SupportState, case
from .s05_services import confirmation_required
from .s06_star import PROFILES

READS = {
    "cases", "case_get", "sessions", "session_get", "messages", "assessments", "assessment_get",
    "strategy", "intervention_get", "mode_get", "session_invitations", "patient_invitations",
    "referral_get", "feedback", "export", "knowledge_list", "knowledge_version",
}
ADMIN = {"cases", "case_get", "case_reset", "probe", "model_profile", "trigger",
         "knowledge_create", "knowledge_new_version", "knowledge_review", "knowledge_withdraw"}
SESSION_SCOPES = {
    "session_get": ("dialogue:read", False), "messages": ("dialogue:read", False),
    "session_close": ("dialogue:write", True), "message_send": ("dialogue:write", True),
    "assessments": ("assessment:read", False), "self_report": ("assessment:write", True),
    "strategy": ("interventions:read", False), "mode_get": ("interventions:read", False),
    "mode_put": ("mode:write", True), "session_invitations": ("interventions:read", False),
}
RESOURCE_SCOPES = {
    "assessment_get": ("Assessment", "assessment:read", False),
    "intervention_get": ("Intervention", "interventions:read", False),
    "suggestion_respond": ("Suggestion", "interventions:read", True),
    "display": ("Intervention", "interventions:read", True),
    "invitation_respond": ("Invitation", "interventions:read", True),
    "referral_get": ("Referral", "interventions:read", False),
}
CREATES = {"session_create", "self_report", "trigger", "knowledge_create", "knowledge_new_version"}


class S04Service:
    def __init__(self, db, auth, receipts, clock, settings, analytics, execution):
        self.db, self.auth, self.receipts = db, auth, receipts
        self.clock, self.settings, self.analytics = clock, settings, analytics
        self.state = SupportState(clock, execution, settings)
        self.dialogue = Dialogue(db, auth, clock, settings, analytics, MockModel())
        self.dialogue.rule_source = self.state
        self.formal_services = None

    def admin(self, conn, principal):
        if not self.auth.account(principal, conn)["is_admin"]:
            raise AppError(403, "ADMIN_REQUIRED", "需使用受控本地管理身份")

    def guard(self, conn, principal, patient, scope, self_only=False):
        self.auth.require_patient(principal, patient, scope, conn, self_only=self_only)
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "本期只使用本地虚构数据")

    def authorize(self, conn, action, principal, path, query, body):
        if action in {"state_event", "execution_receipt", "referral_receipt"}:
            raise AppError(403, "MODULE_IDENTITY_REQUIRED", "外部可信模块身份与签名尚未接入")
        if action in ADMIN:
            self.admin(conn, principal)
            return None, None
        if action in SESSION_SCOPES:
            session = store.session(conn, path["s"])
            patient = session["patient_id"]
            self.guard(conn, principal, patient, *SESSION_SCOPES[action])
            return patient, session
        if action in RESOURCE_SCOPES:
            kind, scope, self_only = RESOURCE_SCOPES[action]
            doc = store.by_id(conn, kind, path["id"])
            self.guard(conn, principal, doc["patient_id"], scope, self_only)
            if action == "referral_get":
                self.guard(conn, principal, doc["patient_id"], "services:read")
            if kind == "Intervention":
                self.guard_intervention(conn, principal, doc)
            return doc["patient_id"], doc
        if action == "generation_retry":
            msg = store.message(conn, path["id"])
            self.guard(conn, principal, msg["patient_id"], "dialogue:write", True)
            return msg["patient_id"], msg
        if action in {"knowledge_list", "knowledge_version"}:
            account = self.auth.account(principal, conn)
            patient = account["current_patient_id"]
            if action == "knowledge_list" and query.get("include_unreviewed"):
                if not account["is_admin"]:
                    raise AppError(403, "KNOWLEDGE_PREVIEW_FORBIDDEN", "当前身份不能预览未审核资料")
                return patient, None
            if not account["is_admin"]:
                if patient is None:
                    raise AppError(403, "SCOPE_REQUIRED", "请先选择本人或获准的管理对象")
                self.guard(conn, principal, patient, "knowledge:read")
            return patient, None
        patient = path.get("p") or query.get("patient_id") or body.get("patient_id")
        scope, self_only = {
            "session_create": ("dialogue:write", True), "sessions": ("dialogue:read", False),
            "patient_invitations": ("interventions:read", False), "export": ("exports:read", False),
            "feedback": ("feedback:read", True), "knowledge_search": ("knowledge:read", True),
            "referral_create": ("services:apply", True),
        }[action]
        self.guard(conn, principal, patient, scope, self_only)
        return patient, None

    def guard_intervention(self, conn, principal, doc):
        self.guard(conn, principal, doc["patient_id"], "interventions:read")
        self.guard(conn, principal, doc["patient_id"], "dialogue:read")
        self.guard(conn, principal, doc["patient_id"], "assessment:read")
        if doc["evidence_refs"]:
            self.guard(conn, principal, doc["patient_id"], "summary:read")

    def handle(self, action, principal, path, query, body, key):
        with self.db.connection(readonly=True) as conn:
            patient, doc = self.authorize(conn, action, principal, path, query, body)
            if action in READS:
                data = self.read(conn, action, principal, patient, doc, path, query)
                self.authorize(conn, action, principal, path, query, body)
                return Result(data)
        scope = ["demo", "account", principal.account_id, patient, action, path]

        def authorize(conn):
            return self.authorize(conn, action, principal, path, query, body)

        def operation(conn):
            _, current = authorize(conn)
            if action == "message_send":
                return self.dialogue.accept_message(conn, principal, current, body, self.profile(conn))
            if action == "generation_retry":
                session = store.session(conn, current["session_id"])
                return self.dialogue.accept_retry(conn, session, current, body)
            if action == "referral_create":
                data = self.submit_referral(conn, principal, patient, body)
                return Result(data, 201, resource_type="Referral", resource_id=data["referral_id"])
            data = self.write(conn, action, patient, current, path, body)
            expires = self.auth.session(principal, conn)["expires_at"] if action == "self_report" else None
            return Result(data, 201 if action in CREATES else 200, sensitive_until=expires)

        def replay_referral(conn, result):
            self.formal_services.prepared(conn, principal, patient, self.referral_request(body), stamp(self.clock()))
            result.data = self.referral_view(conn, store.by_id(conn, "Referral", result.resource_id))
            return result

        result = self.receipts.run(scope, key, {"path": path, "query": query, "body": body}, authorize, operation,
                                   replay_referral if action == "referral_create" else None)
        if action in {"message_send", "generation_retry"}:
            return self.dialogue.run(principal, result.data, 201 if action == "message_send" else 200)
        return result

    def page(self, items, key, principal, action, patient, path, query):
        context = [principal.account_id, "B", action, patient, path,
                   {k: v for k, v in query.items() if k not in {"cursor", "limit"}}]
        items = sorted(items, key=key)
        if query.get("cursor"):
            last = self.auth.read_cursor(query["cursor"], context)
            items = [doc for doc in items if list(key(doc)) > last]
        limit = query.get("limit", 20)
        cursor = self.auth.cursor(context, list(key(items[limit - 1]))) if len(items) > limit else None
        return {"items": items[:limit], "next_cursor": cursor}

    def read(self, conn, action, principal, patient, doc, path, query):
        at = stamp(self.clock())

        def page(items, key):
            return self.page(items, key, principal, action, patient, path, query)

        if action == "cases":
            items = [d for d in CASES.values() if (patient_doc := get(conn, "Patient", d["patient_id"], required=False))
                     and patient_doc["meta"]["is_simulated"]]
            return page(items, lambda d: (d["case_id"],))
        if action == "case_get":
            return case(conn, path["id"])
        if action == "sessions":
            items = [self.state.visible_session(conn, json.loads(r[0])) for r in conn.execute("""
                SELECT document_json FROM b_sessions WHERE patient_id=? AND (? IS NULL OR case_id=?)
            """, (patient, query.get("case_id"), query.get("case_id")))]
            return page(items, lambda d: (d["opened_at"], d["session_id"]))
        if action == "session_get":
            return self.state.visible_session(conn, doc)
        if action == "messages":
            client_id = query.get("client_message_id")
            rows = conn.execute("""
                SELECT document_json FROM b_messages WHERE session_id=? AND (? IS NULL OR client_message_id=?)
            """, (doc["session_id"], client_id, client_id))
            items = [self.dialogue.visible_message(conn, json.loads(r[0])) for r in rows]
            if client_id is not None and not items:
                raise AppError(404, "RESOURCE_NOT_FOUND", "未找到该提交号")
            return page(items, lambda d: (d["created_at"], d["message_id"]))
        if action == "assessments":
            items = store.records(conn, "Assessment", patient, session_id=doc["session_id"])
            return page(items, lambda d: (d["observed_at"], d["assessment_id"]))
        if action == "referral_get":
            return self.referral_view(conn, doc)
        if action in {"assessment_get", "intervention_get"}:
            return doc
        if action in {"session_invitations", "patient_invitations"}:
            items = store.records(conn, "Invitation", patient, session_id=path.get("s"))
            if query.get("status"):
                items = [item for item in items if item["status"] == query["status"]]
            return page(items, lambda d: (d["created_at"], d["invitation_id"]))
        if action == "mode_get":
            state = store.by_id(conn, "UIState", doc["session_id"])
            rows = store.records(conn, "ModeChange", patient, session_id=doc["session_id"]) if query.get("include_history") else []
            changes = page(rows, lambda d: (d["resulting_revision"], d["mode_change_id"]))
            return dict(current=state, changes=changes["items"], next_cursor=changes["next_cursor"],
                        effective_ui_mode=self.state.effective(state, doc, at), evaluated_at=at)
        if action == "strategy":
            return self.strategy(conn, principal, doc, at)
        if action == "feedback":
            data = self.feedback_source(conn, principal, patient, query)
            if query.get("cursor") or len(data["records"]) > query.get("limit", 20):
                raise AppError(503, "B_FEEDBACK_UNAVAILABLE", "反馈契约尚未定义续页，请缩小读取范围")
            return data
        if action == "export":
            items = [doc for doc in store.records(conn, "Intervention", patient)
                     if query["window_start"] <= doc["decided_at"] < query["window_end"]]
            try:
                self.guard(conn, principal, patient, "interventions:read")
                for item in items:
                    self.guard_intervention(conn, principal, item)
            except AppError:
                raise AppError(403, "EXPORT_NOT_AUTHORIZED", "导出需要当前有效的底层读取授权") from None
            result = page(items, lambda d: (d["decided_at"], d["intervention_id"]))
            return dict(result, export_id=uid(), patient_id=patient, window_start=query["window_start"],
                        window_end=query["window_end"], generated_at=at, is_simulated=True)
        if action == "knowledge_list":
            items = [doc for doc in knowledge.documents(conn)
                     if (not query.get("kind") or doc["kind"] == query["kind"])
                     and (query.get("include_unreviewed") or knowledge.eligible(doc, at, knowledge.GENERAL_TAGS))]
            return page(items, lambda d: (d["knowledge_id"], d["version"]))
        if action == "knowledge_version":
            doc = knowledge.record(conn, path["id"], path["version"])
            if self.auth.account(principal, conn)["is_admin"] or knowledge.eligible(doc, at, knowledge.GENERAL_TAGS):
                return doc
            if query.get("session_id"):
                session = store.session(conn, query["session_id"])
                self.guard(conn, principal, session["patient_id"], "dialogue:read")
                self.guard(conn, principal, session["patient_id"], "knowledge:read")
                if knowledge.was_cited(conn, session["session_id"], path["id"], path["version"]):
                    return doc
            raise AppError(404, "RESOURCE_NOT_FOUND", "资料版本不可访问")
        raise RuntimeError("unregistered B read")

    def write(self, conn, action, patient, doc, path, body):
        at = stamp(self.clock())
        if action == "session_create":
            return self.state.new_session(conn, body)
        if action == "session_close":
            return self.state.close_session(conn, doc, body)
        if action == "self_report":
            return self.self_report(conn, doc, body)
        if action == "mode_put":
            return self.state.mode_put(conn, doc, body)
        if action == "suggestion_respond":
            return self.state.suggestion_respond(conn, doc, body)
        if action == "display":
            return self.state.display(conn, doc, body)
        if action == "invitation_respond":
            return self.state.invitation_respond(conn, doc, body)
        if action == "trigger":
            if self.dialogue.adapter.mode != "mock":
                raise AppError(403, "DEMO_TRIGGER_DISABLED", "当前模拟流水线不可用")
            if body['scenario'] == 'star_mid_failure' and self.profile(conn)['requested_pipeline'] != 'star':
                raise AppError(403, 'DEMO_TRIGGER_DISABLED', '请先选择 STAR 模拟配置')
            return self.state.trigger(conn, body)
        if action == "case_reset":
            return self.reset(conn, path["id"], body)
        if action == "knowledge_search":
            return knowledge.retrieve(conn, at, body)
        if action == "knowledge_create":
            return knowledge.create_version(conn, at, body, uid(), 1)
        if action == "knowledge_new_version":
            return knowledge.new_version(conn, at, path["id"], body)
        if action == "knowledge_withdraw":
            return knowledge.withdraw(conn, at, path["id"], body)
        if action == "knowledge_review":
            raise AppError(403, "QUALIFIED_REVIEWER_REQUIRED", "当前未接入可核验的医学审核资格")
        if action in {"probe", "model_profile"}:
            return self.model_config(conn, action, body, at)
        raise RuntimeError("unregistered B write")

    @staticmethod
    def referral_request(body):
        return {"service_draft_id": body["service_draft_id"], "draft_revision": body["service_draft_revision"],
                "confirmation_ref_id": body["confirmation_ref_id"], "sharing_scope_ref_id": body["sharing_scope_ref_id"]}

    def referral_view(self, conn, referral):
        if referral["service_id"] is None or self.formal_services is None:
            return referral
        service = self.formal_services.service(conn, referral["service_id"])
        return dict(referral, service_status=service["status"])

    def submit_referral(self, conn, principal, patient, body):
        session = store.session(conn, body["session_id"])
        if session["patient_id"] != patient:
            raise AppError(404, "RESOURCE_NOT_FOUND", "会话不可访问")
        self.guard(conn, principal, patient, "dialogue:read", True)
        if self.formal_services is None:
            raise AppError(503, "SOCIAL_SUPPORT_NOT_INTEGRATED", "社会支持申请尚未接入")
        at, request = stamp(self.clock()), self.referral_request(body)
        suggestion = body["source_suggestion_id"]
        if suggestion is not None:
            source = store.by_id(conn, "Suggestion", suggestion)
            if source["patient_id"] != patient or source["session_id"] != session["session_id"]:
                raise AppError(404, "RESOURCE_NOT_FOUND", "建议不可访问")
            if (source["type"] != "offer_professional_support" or source["status"] != "accepted"
                    or source["valid_until"] <= at):
                raise confirmation_required("建议未明确接受或不属于专业支持")
        source_key = fingerprint([session["session_id"], request["service_draft_id"], request["draft_revision"]])
        old = store.by_source(conn, "Referral", source_key)
        if old is not None and (old["source_suggestion_id"], old["confirmation_ref_id"], old["sharing_scope_ref_id"]) != (
            suggestion, request["confirmation_ref_id"], request["sharing_scope_ref_id"]
        ):
            raise confirmation_required("会话已有该草稿修订的转介，请核对原记录")
        identifier = old["referral_id"] if old is not None else uid()
        service = self.formal_services.submit(conn, principal, patient, request, referral_id=identifier,
                                              suggestion_id=suggestion, resource_id=body["resource_id"])
        if old is not None:
            return self.referral_view(conn, old)
        referral = dict(referral_id=identifier, patient_id=patient, session_id=session["session_id"],
                        source_suggestion_id=suggestion, proxy_status="linked", service_id=service["service_id"],
                        service_status=service["status"], confirmation_ref_id=request["confirmation_ref_id"],
                        sharing_scope_ref_id=request["sharing_scope_ref_id"], failure_reason=None, meta=meta(at, "B-v0.4"))
        return store.insert(conn, "Referral", identifier, referral, source_key=source_key)

    def self_report(self, conn, session, body):
        if session["status"] != "active":
            raise AppError(409, "ASSESSMENT_SESSION_CLOSED", "会话已关闭")
        session_id, patient = session["session_id"], session["patient_id"]
        key = fingerprint([session_id, body["client_report_id"]])
        existing = store.by_source(conn, "Assessment", key)
        if existing is not None:
            if existing["self_report_items"] != body["items"]:
                raise AppError(409, "ASSESSMENT_SOURCE_CONFLICT", "同一自评提交号对应不同内容")
            return existing
        for item in body["items"]:
            if item["source_message_id"] is not None:
                source = store.message(conn, item["source_message_id"])
                if source["role"] != "user" or source["session_id"] != session_id or source["patient_id"] != patient:
                    raise AppError(404, "RESOURCE_NOT_FOUND", "自评原话引用不可访问")
        return assessment(conn, self.clock, patient, session_id, "self_report",
                          items=body["items"], source=key)

    def strategy(self, conn, principal, session, at):
        patient, identifier = session["patient_id"], session["session_id"]
        state = store.by_id(conn, "UIState", identifier)
        interventions = store.records(conn, "Intervention", patient, session_id=identifier)
        eligible = [d for d in interventions if d["valid_until"] > at]
        current, suggestions = None, []
        if eligible and session["status"] == "active":
            latest = max(eligible, key=lambda d: (d["decided_at"], d["intervention_id"]))
            try:
                self.guard_intervention(conn, principal, latest)
            except AppError as exc:
                if exc.status not in (403, 404):
                    raise
            else:
                current = latest
                suggestions = [d for d in store.records(conn, "Suggestion", patient, session_id=identifier)
                               if d["intervention_id"] == current["intervention_id"] and d["status"] == "pending"
                               and d["valid_until"] > at]
        return dict(session_id=identifier, patient_id=patient,
                    status="active" if current else "expired" if interventions and not eligible else "none",
                    current_intervention=current, suggestions=suggestions,
                    invitations=store.records(conn, "Invitation", patient, session_id=identifier),
                    ui_state=state, generated_at=at, intensity_mapping=dict(
                        availability="not_configured", support_intensity=None, method_version=None,
                        reason="支持强度映射方法尚未接入", evidence_refs=[], evaluated_at=at,
                        is_simulated=True, valid_until=None,
                    ))

    def profile(self, conn):
        row = conn.execute("SELECT document_json FROM b_model_selection WHERE singleton=1").fetchone()
        if row is not None:
            return json.loads(row[0])
        return dict(profile_id='mock-star' if self.settings.DIALOGUE_PIPELINE == 'star' else MODEL_PROFILE_ID, previous_profile_id=None, mode="mock",
                    requested_pipeline=self.settings.DIALOGUE_PIPELINE, model_config_version=self.settings.CONFIG_VERSION,
                    configuration_status="ready",
                    selected_at=None)

    def model_config(self, conn, action, body, at):
        old = self.profile(conn)
        if body["expected_config_version"] != old["model_config_version"]:
            raise AppError(409, "MODEL_CONFIG_VERSION_CONFLICT", "模型配置已更新，请重新读取")
        if action == "probe":
            if body["profile_id"] != old['profile_id'] or old["configuration_status"] != "ready":
                raise AppError(503, "MODEL_NOT_CONFIGURED", "当前没有可探测的已启用适配")
            doc = dict(probe_id=uid(), profile_id=old['profile_id'], mode="mock",
                       model_label=self.dialogue.adapter.model_label, model_config_version=old["model_config_version"],
                       status="available", network_attempt_count=0, elapsed_ms=0,
                       usage=missing_usage("本地模拟探测无网络用量"), checked_at=at)
            return store.insert(conn, "Probe", doc["probe_id"], doc)
        if body["profile_id"] not in PROFILES:
            raise AppError(422, "MODEL_PROFILE_NOT_READY", "该配置未登记或依赖尚未就绪")
        doc = dict(old, profile_id=body['profile_id'], previous_profile_id=old["profile_id"], requested_pipeline=PROFILES[body['profile_id']],
                   configuration_status="ready", model_config_version=uid(), selected_at=at)
        conn.execute("""
            INSERT INTO b_model_selection VALUES (1,?)
            ON CONFLICT(singleton) DO UPDATE SET document_json=excluded.document_json
        """, (encode(doc),))
        return doc

    def feedback_source(self, conn, principal, patient, window):
        if principal is not None:
            scopes = self.auth.scopes(principal, patient, conn)
            if "feedback:read" not in scopes:
                return dict(source_module="B", availability="restricted", records=[], reason="当前授权不含反馈读取")
        else:
            scopes = {"assessment:read", "interventions:read"}
        results = []
        for kind, required, time_key, id_key in (
            ("Assessment", "assessment:read", "observed_at", "assessment_id"),
            ("Intervention", "interventions:read", "decided_at", "intervention_id"),
        ):
            if required not in scopes:
                continue
            for doc in store.records(conn, kind, patient):
                if kind == "Assessment" and doc["kind"] != "self_report":
                    continue
                if not window["window_start"] <= doc[time_key] < window["window_end"]:
                    continue
                if "as_of" in window and doc[time_key] > window["as_of"]:
                    continue
                results.append(dict(record_kind="self_report" if kind == "Assessment" else "intervention",
                                    record_id=doc[id_key], source_version=knowledge.CONTRACT,
                                    recorded_at=doc[time_key], service_status=None, support_needs=None,
                                    support_acceptance=None, intervention_effectiveness=None, is_simulated=True))
        results.sort(key=lambda item: (item["recorded_at"], item["record_id"]))
        if not results and not {"assessment:read", "interventions:read"}.issubset(scopes):
            return dict(source_module="B", availability="restricted", records=[], reason="当前授权不含完整的 B 来源读取")
        return dict(source_module="B", availability="available" if results else "not_collected", records=results,
                    reason=None if results else "此窗口暂无可见 B 反馈")

    def reset(self, conn, case_id, body):
        template = case(conn, case_id)
        if body["case_template_version"] != CASE_VERSION:
            raise AppError(409, "CASE_VERSION_CONFLICT", "案例模板版本已变化")
        patient = template["patient_id"]
        sessions = {r[0] for r in conn.execute(
            "SELECT session_id FROM b_sessions WHERE case_id=? AND patient_id=?", (case_id, patient),
        )}
        interventions = {doc["intervention_id"] for doc in store.records(conn, "Intervention", patient)
                         if doc["session_id"] in sessions}
        if any(doc["session_id"] in sessions for doc in store.records(conn, "Referral", patient)):
            raise AppError(409, "CASE_HAS_LINKED_RESOURCES", "存在 C 关联，需另建隔离场景")
        tasks = self.state.cancel_tasks(conn, patient, sessions, interventions)
        if any(task["status"] in {"running", "outcome_unknown"} for task in tasks):
            raise AppError(409, "CASE_HAS_LINKED_RESOURCES", "有在途或未知结果的公共任务")
        cancelled = self.state.cancel_tasks(conn, patient, sessions, interventions, self.state.execution)
        for identifier in sorted(sessions):
            if conn.execute("""
                SELECT 1 FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id
                WHERE m.session_id=? AND json_extract(g.document_json,'$.status') IN ('accepted','running','outcome_unknown')
            """, (identifier,)).fetchone() is not None:
                raise AppError(409, "CASE_HAS_LINKED_RESOURCES", "案例有在途或结果未知的生成，请先核查")
            conn.execute("""
                DELETE FROM b_generation_runs WHERE generation_id IN (
                    SELECT g.generation_id FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id
                    WHERE m.session_id=?
                )
            """, (identifier,))
            conn.execute('DELETE FROM b_star_checkpoints WHERE generation_id IN (SELECT g.generation_id FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id WHERE m.session_id=?)',
                         (identifier,))
            conn.execute("DELETE FROM b_generations WHERE user_message_id IN (SELECT message_id FROM b_messages WHERE session_id=?)",
                         (identifier,))
            conn.execute("DELETE FROM b_messages WHERE session_id=? AND source_message_id IS NOT NULL", (identifier,))
            conn.execute("DELETE FROM b_messages WHERE session_id=?", (identifier,))
            conn.execute("DELETE FROM b_records WHERE session_id=? AND kind<>'ScenarioRun'", (identifier,))
        case_runs = [trigger for trigger in store.records(conn, "ScenarioRun", patient)
                     if trigger["result"]["case_id"] == case_id]
        case_invitation_ids = {identifier for trigger in case_runs
                               if trigger["result"]["scenario"] in {"state_event", "periodic_node"}
                               for identifier in trigger["result"]["related_ids"]}
        for invite in store.records(conn, "Invitation", patient):
            if invite["resolved_session_id"] in sessions:
                self.state.update_invitation(conn, invite, status="cancelled", resolved_session_id=None)
            elif (invite["invitation_id"] in case_invitation_ids and invite["session_id"] is None
                  and invite["resolved_session_id"] is None and invite["status"] in {"pending", "accepted"}):
                self.state.update_invitation(conn, invite, status="cancelled")
        for trigger in case_runs:
            trigger.update(queued=False, session_id=None)
            conn.execute("UPDATE b_records SET session_id=NULL,document_json=? WHERE kind='ScenarioRun' AND record_id=?",
                         (encode(trigger), trigger["result"]["trigger_id"]))
        for intervention in interventions:
            conn.execute("DELETE FROM b_intervention_revisions WHERE intervention_id=?", (intervention,))
        for identifier in sessions:
            conn.execute("DELETE FROM b_sessions WHERE session_id=?", (identifier,))
        data = dict(reset_id=uid(), case_id=case_id, affected_session_ids=sorted(sessions),
                    cancelled_task_ids=cancelled, reset_at=stamp(self.clock()), preserved_template_version=CASE_VERSION,
                    is_simulated=True)
        return store.insert(conn, "Reset", data["reset_id"], data, patient_id=patient)
