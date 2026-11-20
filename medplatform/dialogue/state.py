"""B-owned session mode, support facts and explicit invitation maintenance."""

import json
from datetime import datetime, timedelta

from ..core.documents import (
    changed,
    encode,
    expected,
    fingerprint,
    get,
    meta,
    stamp,
    uid,
)
from ..core.errors import AppError
from . import rules, store
from .knowledge import CONTRACT

CASE_VERSION = "s04-cases-v1"
CASES = {
    name: {
        "case_id": name,
        "patient_id": patient,
        "title": title,
        "focus": focus,
        "template_version": CASE_VERSION,
        "opening_draft": opening,
        "is_simulated": True,
    }
    for name, patient, title, focus, opening in (
        (
            "case-low-mood",
            "demo-patient-a-self",
            "情绪低落",
            "low_mood",
            "这几天心情低落，只想先说说。",
        ),
        (
            "case-anxiety",
            "demo-patient-b-self",
            "焦虑与用药顾虑",
            "anxiety_concerns",
            "我担心副作用，想把问题理一理。",
        ),
        (
            "case-fatigue",
            "demo-family-self",
            "长期用药倦怠",
            "treatment_fatigue",
            "我吃药吃累了，想让日常安排简单一点。",
        ),
    )
}
FAULTS = {
    "llm_timeout",
    "empty_response",
    "invalid_json",
    "knowledge_empty",
    "star_mid_failure",
}
EXPIRY_MAINTENANCE_LIMIT = "9999-12-31T23:59:59.999999+00:00"


def case(conn, identifier):
    doc = CASES.get(identifier)
    patient = (
        get(conn, "Patient", doc["patient_id"], required=False)
        if doc is not None
        else None
    )
    if patient is None or not patient["meta"]["is_simulated"]:
        raise AppError(404, "RESOURCE_NOT_FOUND", "虚构案例不可访问")
    return doc


class SupportState:
    def __init__(self, clock, execution, settings=None):
        self.clock, self.execution = clock, execution
        self.settings = settings

    def policy(self, conn):
        return rules.policy(
            conn, getattr(self.settings, "SUPPORT_RULE_PROFILE", "support-default")
        )

    def rule_reference(self, conn):
        return rules.reference(self.policy(conn))

    def new_session(self, conn, body):
        patient, case_id, invitation_id = (
            body["patient_id"],
            body["case_id"],
            body["invitation_id"],
        )
        if case_id is not None and case(conn, case_id)["patient_id"] != patient:
            raise AppError(404, "RESOURCE_NOT_FOUND", "案例与会话患者不一致")
        at = stamp(self.clock())
        invitation = None
        if invitation_id is not None:
            invitation = store.by_id(conn, "Invitation", invitation_id)
            if (
                invitation["patient_id"] != patient
                or invitation["status"] != "accepted"
            ):
                raise AppError(409, "INVITATION_NOT_ACCEPTED", "未找到本人已接受的邀请")
            resolved = invitation["resolved_session_id"]
            if resolved is not None:
                existing = store.session(conn, resolved)
                if (
                    existing["patient_id"] != patient
                    or existing["status"] != "active"
                    or (case_id is not None and existing["case_id"] != case_id)
                ):
                    raise AppError(
                        409,
                        "INVITATION_NOT_ACCEPTED",
                        "邀请已关联其他会话或该会话已关闭",
                    )
                return self.visible_session(conn, existing)
            if invitation["valid_until"] <= at:
                raise AppError(409, "INVITATION_NOT_ACCEPTED", "邀请已到期")
        session = dict(
            body,
            session_id=uid(),
            status="active",
            turn_count=0,
            ui_mode="normal",
            opened_at=at,
            closed_at=None,
            meta=meta(at, CONTRACT),
        )
        store.save_session(conn, session, new=True)
        store.insert(
            conn,
            "UIState",
            session["session_id"],
            {
                "session_id": session["session_id"],
                "patient_id": patient,
                "scope": "session",
                "ui_mode": "normal",
                "revision": 1,
                "changed_at": at,
                "valid_until": None,
                "minimum_until": None,
                "last_offer_at": None,
                "is_simulated": True,
            },
        )
        if invitation is not None:
            self.update_invitation(
                conn, invitation, resolved_session_id=session["session_id"]
            )
        return session

    def close_session(self, conn, session, body):
        expected(session, body["expected_revision"], "SESSION_REVISION_CONFLICT")
        if session["status"] == "closed":
            return self.visible_session(conn, session)
        at = stamp(self.clock())
        identifier = session["session_id"]
        closed = dict(changed(session, at), status="closed", closed_at=at)
        store.save_session(conn, closed)
        state = store.by_id(conn, "UIState", identifier)
        self.change_mode(conn, closed, state, "normal", "session_closed")
        for kind, key in (
            ("Suggestion", "suggestion_id"),
            ("Invitation", "invitation_id"),
        ):
            for item in store.records(
                conn, kind, session["patient_id"], session_id=identifier
            ):
                if item["status"] == "pending":
                    store.update(conn, kind, item[key], dict(item, status="cancelled"))
        self.cancel_tasks(
            conn, session["patient_id"], {identifier}, set(), self.execution
        )
        for row in conn.execute(
            """
            SELECT g.document_json,g.run_number FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id
            WHERE m.session_id=? AND json_extract(g.document_json,'$.status')='accepted'
        """,
            (identifier,),
        ).fetchall():
            generation = json.loads(row[0])
            generation.update(
                status="cancelled", finished_at=at, error_code="GENERATION_CANCELLED"
            )
            conn.execute(
                "UPDATE b_generations SET document_json=? WHERE generation_id=?",
                (encode(generation), generation["generation_id"]),
            )
            conn.execute(
                "UPDATE b_generation_runs SET outcome='cancelled' WHERE generation_id=? AND run_number=?",
                (generation["generation_id"], row["run_number"]),
            )
        return self.visible_session(conn, closed)

    @staticmethod
    def effective(state, session, at):
        if (
            session["status"] == "active"
            and state["ui_mode"] == "simplified"
            and state["valid_until"] is not None
            and at < state["valid_until"]
        ):
            return "simplified"
        return "normal"

    def visible_session(self, conn, session):
        state = store.by_id(conn, "UIState", session["session_id"])
        return dict(
            session, ui_mode=self.effective(state, session, stamp(self.clock()))
        )

    def mode_put(self, conn, session, body):
        state = store.by_id(conn, "UIState", session["session_id"])
        if (
            session["status"] != "active"
            or body["expected_revision"] != state["revision"]
        ):
            raise AppError(409, "UI_MODE_REVISION_CONFLICT", "会话或模式状态已变化")
        source = "user"
        suggestion_id = body["source_suggestion_id"]
        if suggestion_id is not None:
            suggestion = store.by_id(conn, "Suggestion", suggestion_id)
            if (
                suggestion["session_id"] != session["session_id"]
                or suggestion["status"] != "accepted"
                or suggestion["type"] != "offer_simplified_mode"
                or body["ui_mode"] != "simplified"
                or suggestion["valid_until"] <= stamp(self.clock())
            ):
                raise AppError(
                    409, "SUGGESTION_RESPONSE_CONFLICT", "建议未接受或不再有效"
                )
            source = "accepted_suggestion"
        self.change_mode(conn, session, state, body["ui_mode"], source, suggestion_id)
        return store.by_id(conn, "UIState", session["session_id"])

    def change_mode(self, conn, session, state, requested, source, suggestion_id=None):
        when = self.clock()
        at = stamp(when)
        current = state["ui_mode"]
        if current == requested:
            # An explicit new simplification after logical expiry is a new
            # user choice. First record the previously due restoration.
            if (
                requested != "simplified"
                or self.effective(state, session, at) == requested
            ):
                return None
            self.change_mode(conn, session, state, "normal", "expiry")
            state = store.by_id(conn, "UIState", session["session_id"])
            current = state["ui_mode"]
        policy = self.policy(conn)
        valid = (
            stamp(when + timedelta(seconds=policy["mode_seconds"]))
            if requested == "simplified"
            else None
        )
        revision = state["revision"] + 1
        identifier = session["session_id"]
        next_state = dict(
            state,
            ui_mode=requested,
            revision=revision,
            changed_at=at,
            valid_until=valid,
            minimum_until=at if valid is not None else None,
        )
        store.update(conn, "UIState", identifier, next_state)
        change = {
            "mode_change_id": uid(),
            "session_id": identifier,
            "from_mode": current,
            "to_mode": requested,
            "source": source,
            "source_suggestion_id": suggestion_id,
            "changed_at": at,
            "resulting_revision": revision,
            "is_simulated": True,
        }
        store.insert(
            conn,
            "ModeChange",
            change["mode_change_id"],
            change,
            patient_id=session["patient_id"],
        )
        if valid is not None:
            self.execution.create_in_transaction(
                conn,
                None,
                {
                    "patient_id": session["patient_id"],
                    "kind": "expire_b_state",
                    "owner_module": "B",
                    "owner_operation_key": f"b-ui-expiry:{identifier}:{revision}",
                    "scheduled_at": valid,
                    "valid_until": EXPIRY_MAINTENANCE_LIMIT,
                    "intervention_id": None,
                    "rule_version": rules.reference(policy),
                    "payload": {
                        "session_id": identifier,
                        "target_kind": "ui_mode",
                        "target_id": identifier,
                        "expected_revision": revision,
                    },
                },
                internal=True,
            )
        return change["mode_change_id"]

    def validate_task(self, conn, task):
        if task["kind"] == "check_in_node":
            policy = rules.by_reference(conn, task["rule_version"])
            patient = get(conn, "Patient", task["patient_id"])
            payload = task["payload"]
            delay = {"week_1": 7, "week_4": 28}.get(payload["node_code"])
            enrolled = patient["enrollment_at"]
            if (
                delay is None
                or enrolled is None
                or not patient["meta"]["is_simulated"]
                or payload["cycle_id"] != fingerprint([task["patient_id"], enrolled])
                or payload["rule_version"] != task["rule_version"]
            ):
                raise AppError(409, "B_TARGET_CONFLICT", "周期节点来源或规则不匹配")
            start = datetime.fromisoformat(enrolled) + timedelta(days=delay)
            if task["scheduled_at"] != stamp(start) or task["valid_until"] != stamp(
                start + timedelta(seconds=policy["node_window_seconds"])
            ):
                raise AppError(
                    409, "B_TARGET_CONFLICT", "周期节点必须保留原起点和24小时时窗"
                )
            return
        if task["kind"] != "expire_b_state":
            raise AppError(
                503,
                "TASK_OWNER_NOT_INTEGRATED",
                "该自动分级干预依赖的决策或支持强度方法尚未适配",
            )
        payload = task["payload"]
        session = store.session(conn, payload["session_id"])
        state = store.by_id(conn, "UIState", payload["target_id"])
        if (
            payload["target_kind"] != "ui_mode"
            or session["patient_id"] != task["patient_id"]
            or state["session_id"] != session["session_id"]
            or state["revision"] != payload["expected_revision"]
            or state["valid_until"] != task["scheduled_at"]
        ):
            raise AppError(409, "B_TARGET_CONFLICT", "B 到期目标或版本不匹配")

    def run_task(self, conn, task):
        if task["kind"] == "check_in_node":
            self.validate_task(conn, task)
            delay = {"week_1": 7, "week_4": 28}[task["payload"]["node_code"]]
            related = self.periodic(
                conn,
                task["patient_id"],
                None,
                stamp(self.clock()),
                offsets=(delay,),
                policy=rules.by_reference(conn, task["rule_version"]),
            )
            return related[0] if related else None
        payload = task["payload"]
        state = store.by_id(conn, "UIState", payload["target_id"], required=False)
        if state is None or state["revision"] != payload["expected_revision"]:
            return None
        session = store.session(conn, payload["session_id"])
        at = stamp(self.clock())
        if (
            session["patient_id"] != task["patient_id"]
            or state["session_id"] != session["session_id"]
            or state["ui_mode"] != "simplified"
            or state["valid_until"] > at
        ):
            return None
        return self.change_mode(conn, session, state, "normal", "expiry")

    @staticmethod
    def cancel_tasks(conn, patient, session_ids, intervention_ids, executor=None):
        tasks = [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT document_json FROM a_tasks WHERE owner_module='B' AND patient_id=?",
                (patient,),
            )
        ]
        candidates = [
            task
            for task in tasks
            if task["payload"].get("session_id") in session_ids
            or task.get("intervention_id") in intervention_ids
        ]
        if executor is None:
            return candidates
        cancelled = []
        for task in candidates:
            if task["status"] not in ("pending", "retry_wait", "running"):
                continue
            next_task = changed(task, stamp(executor.clock()))
            next_task.update(
                cancellation_requested=True, failure_reason="B 会话关闭或演示案例重置"
            )
            if task["status"] != "running":
                next_task.update(status="cancelled", next_attempt_at=None)
                cancelled.append(task["task_id"])
            executor._save_task(conn, next_task)
        return cancelled

    def maintain_invitations(self, conn, patient):
        at = stamp(self.clock())
        expired = 0
        for invitation in store.records(conn, "Invitation", patient):
            if invitation["status"] == "pending" and invitation["valid_until"] <= at:
                self.update_invitation(conn, invitation, status="expired")
                expired += 1
        for suggestion in store.records(conn, "Suggestion", patient):
            if suggestion["status"] == "pending" and suggestion["valid_until"] <= at:
                self.update_suggestion(conn, suggestion, status="expired")
                expired += 1
        return expired

    def invitation(
        self, conn, patient, session_id, trigger_type, trigger_ref, at, *, policy=None
    ):
        key = fingerprint([patient, trigger_type, trigger_ref])
        existing = store.by_source(conn, "Invitation", key)
        if existing is not None:
            return existing
        policy = policy or self.policy(conn)
        doc = {
            "invitation_id": uid(),
            "patient_id": patient,
            "session_id": session_id,
            "trigger_type": trigger_type,
            "trigger_ref": trigger_ref,
            "status": "pending",
            "title": "可选的支持对话",
            "description": "如果你愿意，可以聊聊最近想得到哪方面的支持。",
            "created_at": at,
            "valid_until": stamp(
                datetime.fromisoformat(at)
                + timedelta(seconds=policy["invitation_seconds"])
            ),
            "displayed_at": None,
            "resolved_session_id": None,
            "rule_version": rules.reference(policy),
            "is_simulated": True,
        }
        return store.insert(
            conn, "Invitation", doc["invitation_id"], doc, source_key=key
        )

    @staticmethod
    def update_invitation(conn, invitation, **updates):
        return store.update(
            conn, "Invitation", invitation["invitation_id"], dict(invitation, **updates)
        )

    def invitation_respond(self, conn, invitation, body):
        identifier, patient = invitation["invitation_id"], invitation["patient_id"]
        old = store.by_source(conn, "InvitationResponse", identifier)
        target = body["session_id"]
        if target is None and body["choice"] == "accepted":
            target = invitation["session_id"]
        if (
            old is not None
            and old["choice"] == body["choice"]
            and old["session_id"] == target
        ):
            return old
        at = stamp(self.clock())
        if invitation["status"] != "pending" or invitation["valid_until"] <= at:
            raise AppError(
                409, "INVITATION_RESPONSE_CONFLICT", "邀请已到期、撤销或响应"
            )
        if target is not None:
            session = store.session(conn, target)
            if (
                body["choice"] != "accepted"
                or session["patient_id"] != patient
                or session["status"] != "active"
                or invitation["session_id"] not in (None, target)
            ):
                raise AppError(409, "INVITATION_RESPONSE_CONFLICT", "会话与邀请不匹配")
        data = {
            "response_id": uid(),
            "invitation_id": identifier,
            "patient_id": patient,
            "choice": body["choice"],
            "session_id": target,
            "responded_at": at,
            "is_simulated": True,
        }
        store.insert(
            conn, "InvitationResponse", data["response_id"], data, source_key=identifier
        )
        self.update_invitation(
            conn, invitation, status=data["choice"], resolved_session_id=target
        )
        return data

    def prepare_checkins(self, conn, patient):
        enrolled = get(conn, "Patient", patient)["enrollment_at"]
        if enrolled is None:
            return 0
        cycle = fingerprint([patient, enrolled])
        policy = self.policy(conn)
        rule_ref = rules.reference(policy)
        created = 0
        for offset, code in ((7, "week_1"), (28, "week_4")):
            key = fingerprint([patient, enrolled, offset])
            if store.by_source(conn, "CheckinNode", key) is not None:
                continue
            start = datetime.fromisoformat(enrolled) + timedelta(days=offset)
            end = start + timedelta(seconds=policy["node_window_seconds"])
            if stamp(end) <= stamp(self.clock()):
                self.periodic(
                    conn, patient, None, stamp(self.clock()), offsets=(offset,)
                )
                continue
            operation = f"b-node:{cycle}:{offset}"
            existing = conn.execute(
                "SELECT 1 FROM a_tasks WHERE owner_module='B' AND owner_operation_key=? AND data_environment='demo'",
                (operation,),
            ).fetchone()
            if existing:
                continue  # Existing nodes retain their original immutable rule snapshot.
            self.execution.create_in_transaction(
                conn,
                None,
                {
                    "patient_id": patient,
                    "kind": "check_in_node",
                    "owner_module": "B",
                    "owner_operation_key": operation,
                    "scheduled_at": stamp(start),
                    "valid_until": stamp(end),
                    "intervention_id": None,
                    "rule_version": rule_ref,
                    "payload": {
                        "cycle_id": cycle,
                        "node_code": code,
                        "rule_version": rule_ref,
                    },
                },
                internal=True,
            )
            created += existing is None
        return created

    def periodic(self, conn, patient, session_id, at, *, offsets=(7, 28), policy=None):
        enrolled = get(conn, "Patient", patient)["enrollment_at"]
        related = []
        policy = policy or self.policy(conn)
        if enrolled is None:
            return related
        for delay in offsets:
            start = datetime.fromisoformat(enrolled) + timedelta(days=delay)
            first, last = (
                stamp(start),
                stamp(start + timedelta(seconds=policy["node_window_seconds"])),
            )
            if at < first:
                continue
            key = fingerprint([patient, enrolled, delay])
            existing = store.by_source(conn, "CheckinNode", key)
            if existing is not None:
                if existing["invitation_id"] is not None:
                    related.append(existing["invitation_id"])
                continue
            node_id = uid()
            invite = (
                self.invitation(
                    conn, patient, session_id, "periodic", node_id, at, policy=policy
                )
                if at < last
                else None
            )
            store.insert(
                conn,
                "CheckinNode",
                node_id,
                {
                    "node_id": node_id,
                    "patient_id": patient,
                    "enrollment_at": enrolled,
                    "offset_days": delay,
                    "opened_at": first,
                    "closed_at": last,
                    "outcome": "invited" if invite else "missed",
                    "invitation_id": invite["invitation_id"] if invite else None,
                    "checked_at": at,
                    "rule_version": rules.reference(policy),
                },
                source_key=key,
            )
            if invite is not None:
                related.append(invite["invitation_id"])
        return related

    def trigger(self, conn, body):
        template = case(conn, body["case_id"])
        patient, identifier = template["patient_id"], body["session_id"]
        if identifier is not None:
            session = store.session(conn, identifier)
            if (
                session["case_id"] != template["case_id"]
                or session["patient_id"] != patient
                or session["status"] != "active"
            ):
                raise AppError(
                    403, "DEMO_TRIGGER_DISABLED", "会话不在当前活动的虚构案例"
                )
        unique = fingerprint([template["case_id"], body["scenario_run_id"]])
        previous = store.by_source(conn, "ScenarioRun", unique)
        if previous is not None:
            if previous["fingerprint"] != fingerprint(body):
                raise AppError(409, "DEMO_TRIGGER_CONFLICT", "同一场景号对应不同内容")
            return previous["result"]
        scenario, at = body["scenario"], body["occurred_at"]
        if at > stamp(self.clock()):
            raise AppError(
                403, "DEMO_TRIGGER_DISABLED", "场景尚未启用或时间晚于演示时钟"
            )
        trigger_id, related = uid(), []
        if scenario == "state_event":
            invite = self.invitation(
                conn,
                patient,
                identifier,
                "state_event",
                trigger_id,
                stamp(self.clock()),
            )
            related.append(invite["invitation_id"])
        elif scenario == "periodic_node":
            related = self.periodic(conn, patient, identifier, stamp(self.clock()))
        elif scenario == "receipt_late":
            ack = self.audit(
                conn,
                "execution_receipt_demo",
                patient,
                trigger_id,
                body,
                False,
                "模拟晚到发送结果，仅记录核查事实",
            )
            related.append(ack["integration_event_id"])
        result = {
            "trigger_id": trigger_id,
            "case_id": template["case_id"],
            "scenario": scenario,
            "related_ids": related,
            "is_simulated": True,
        }
        store.insert(
            conn,
            "ScenarioRun",
            trigger_id,
            {
                "patient_id": patient,
                "session_id": identifier,
                "occurred_at": at,
                "fingerprint": fingerprint(body),
                "result": result,
                "queued": scenario in FAULTS,
            },
            source_key=unique,
        )
        return result

    def audit(self, conn, kind, patient, source, body, applied, reason, related=()):
        key = fingerprint([kind, patient, source])
        previous = store.by_source(conn, "Integration", key)
        if previous is not None:
            if previous["fingerprint"] != fingerprint(body):
                raise AppError(
                    409, "INTEGRATION_SOURCE_CONFLICT", "可信来源号对应不同内容"
                )
            return previous["ack"]
        data = {
            "integration_event_id": uid(),
            "source_event_id": source,
            "applied": applied,
            "ignore_reason": reason,
            "related_ids": list(related),
            "received_at": stamp(self.clock()),
            "is_simulated": True,
        }
        store.insert(
            conn,
            "Integration",
            data["integration_event_id"],
            {
                "patient_id": patient,
                "fingerprint": fingerprint(body),
                "ack": data,
            },
            source_key=key,
        )
        return data

    def consume_notices(self, conn, patient):
        self.process_support_needs(conn, patient)
        for notice in conn.execute(
            """
            SELECT n.* FROM change_notices n LEFT JOIN a_notice_consumptions x
            ON n.notice_id=x.notice_id AND x.consumer='B'
            WHERE n.patient_id=? AND n.data_environment='demo' AND x.notice_id IS NULL
            AND n.kind IN ('plan_published','summary_changed')
            ORDER BY n.created_at,n.notice_id
        """,
            (patient,),
        ).fetchall():
            ref = json.loads(notice["source_ref"])
            if notice["kind"] == "plan_published":
                key = f"{ref['resource_id']}:{ref['resource_revision']}"
                authorized = get(conn, "PlanVersion", key, required=False)
                exists = authorized is not None and authorized["patient_id"] == patient
            else:
                exists = (
                    conn.execute(
                        """
                    SELECT 1 FROM s03_results WHERE result_id=? AND patient_id=? AND data_environment='demo' AND kind='summary'
                """,
                        (ref["resource_id"], patient),
                    ).fetchone()
                    is not None
                )
            reason = (
                "仅记录权威来源；支持邀请由已登记的明确自报规则判断"
                if exists
                else "权威来源不匹配或不可用"
            )
            ack = self.audit(
                conn, "A_notice", patient, notice["notice_id"], ref, False, reason
            )
            conn.execute(
                "INSERT INTO a_notice_consumptions VALUES (?,?,?,?,?,?)",
                (
                    notice["notice_id"],
                    "B",
                    "ignored",
                    ack["integration_event_id"],
                    reason,
                    stamp(self.clock()),
                ),
            )

    def process_support_needs(self, conn, patient):
        policy = self.policy(conn)
        if not policy["state_events"]:
            return
        at = stamp(self.clock())
        since = stamp(
            self.clock() - timedelta(seconds=policy["offer_cooldown_seconds"])
        )
        assessments = sorted(
            store.records(conn, "Assessment", patient),
            key=lambda a: (a["observed_at"], a["assessment_id"]),
        )
        for assessment in assessments:
            if (
                assessment["kind"] != "self_report"
                or not since <= assessment["observed_at"] <= at
                or not any(
                    i["dimension"] == "support_need"
                    for i in assessment["self_report_items"]
                )
            ):
                continue
            source = assessment["assessment_id"]
            key = fingerprint(["support_need_rule", patient, source])
            if store.by_source(conn, "Integration", key) is not None:
                continue
            session = store.session(conn, assessment["session_id"])
            recent = [
                i
                for i in store.records(conn, "Invitation", patient)
                if i["status"] == "pending"
                and i["valid_until"] > at
                or i["trigger_type"] == "state_event"
                and i["created_at"] >= since
            ]
            related = []
            if session["status"] == "active" and not recent:
                invite = self.invitation(
                    conn,
                    patient,
                    session["session_id"],
                    "state_event",
                    source,
                    at,
                    policy=policy,
                )
                related.append(invite["invitation_id"])
            self.audit(
                conn,
                "support_need_rule",
                patient,
                source,
                {"assessment_id": source, "rule_version": rules.reference(policy)},
                bool(related),
                None if related else "已有邀请、仍在频控间隔或会话已结束",
                related,
            )

    def touch_intervention(self, conn, doc):
        at = stamp(self.clock())
        identifier = doc["intervention_id"]
        revision = conn.execute(
            """
            INSERT INTO b_intervention_revisions VALUES (?,1,?)
            ON CONFLICT(intervention_id) DO UPDATE SET revision=revision+1,updated_at=excluded.updated_at
            RETURNING revision
        """,
            (identifier, at),
        ).fetchone()[0]
        ref = {
            "resource_type": "Intervention",
            "resource_id": identifier,
            "resource_revision": revision,
        }
        conn.execute(
            "INSERT INTO change_notices VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                uid(),
                "B",
                doc["patient_id"],
                "demo",
                "b_intervention_changed",
                encode(ref),
                f"b-intervention:{identifier}:{revision}",
                at,
                at,
                1,
            ),
        )
        store.update(conn, "Intervention", identifier, doc)

    def update_suggestion(self, conn, suggestion, **updates):
        store.update(
            conn, "Suggestion", suggestion["suggestion_id"], dict(suggestion, **updates)
        )
        doc = store.by_id(conn, "Intervention", suggestion["intervention_id"])
        if updates.get("response_id"):
            doc["response_ids"].append(updates["response_id"])
        self.touch_intervention(conn, doc)

    def suggestion_respond(self, conn, suggestion, body):
        identifier = suggestion["suggestion_id"]
        saved = store.by_source(conn, "SuggestionResponse", identifier)
        if saved is not None and saved["choice"] == body["choice"]:
            return saved
        session = store.session(conn, suggestion["session_id"])
        doc = store.by_id(conn, "Intervention", suggestion["intervention_id"])
        at = stamp(self.clock())
        if (
            suggestion["status"] != "pending"
            or suggestion["valid_until"] <= at
            or doc["patient_id"] != suggestion["patient_id"]
            or doc["valid_until"] <= at
            or session["status"] != "active"
        ):
            raise AppError(409, "SUGGESTION_RESPONSE_CONFLICT", "建议已失效或响应")
        mode_change_id = None
        if (
            body["choice"] == "accepted"
            and suggestion["type"] == "offer_simplified_mode"
        ):
            state = store.by_id(conn, "UIState", session["session_id"])
            mode_change_id = self.change_mode(
                conn, session, state, "simplified", "accepted_suggestion", identifier
            )
        data = {
            "response_id": uid(),
            "suggestion_id": identifier,
            "patient_id": session["patient_id"],
            "choice": body["choice"],
            "responded_at": at,
            "mode_change_id": mode_change_id,
            "referral_id": None,
            "is_simulated": True,
        }
        store.insert(
            conn,
            "SuggestionResponse",
            data["response_id"],
            data,
            source_key=identifier,
            session_id=session["session_id"],
        )
        self.update_suggestion(
            conn, suggestion, status=body["choice"], response_id=data["response_id"]
        )
        return data

    def display(self, conn, doc, body):
        identifier = doc["intervention_id"]
        key = fingerprint([identifier, body["client_receipt_id"]])
        saved = store.by_source(conn, "DisplayReceipt", key)
        if saved is not None:
            if saved["displayed_at"] != body["displayed_at"]:
                raise AppError(
                    409, "DISPLAY_RECEIPT_CONFLICT", "同一展示号对应不同时间"
                )
            return saved
        at = stamp(self.clock())
        session = (
            store.session(conn, doc["session_id"])
            if doc["session_id"] is not None
            else None
        )
        if (
            session is None
            or session["status"] != "active"
            or doc["valid_until"] <= at
            or not doc["decided_at"] <= body["displayed_at"] <= at
        ):
            raise AppError(
                409, "DISPLAY_RECEIPT_CONFLICT", "展示不在可核验的会话或时间范围"
            )
        if doc["displayed_at"] is not None:
            row = conn.execute(
                """
                SELECT document_json FROM b_records WHERE kind='DisplayReceipt'
                AND json_extract(document_json,'$.intervention_id')=? ORDER BY rowid LIMIT 1
            """,
                (identifier,),
            ).fetchone()
            if row is None:
                raise AppError(503, "STRATEGY_UNAVAILABLE", "已保存展示缺少回执")
            return json.loads(row[0])
        data = {
            "receipt_id": uid(),
            "intervention_id": identifier,
            "client_receipt_id": body["client_receipt_id"],
            "displayed_at": body["displayed_at"],
            "received_at": at,
            "is_simulated": True,
        }
        store.insert(
            conn,
            "DisplayReceipt",
            data["receipt_id"],
            data,
            source_key=key,
            patient_id=doc["patient_id"],
            session_id=doc["session_id"],
        )
        doc["displayed_at"] = data["displayed_at"]
        self.touch_intervention(conn, doc)
        return data
