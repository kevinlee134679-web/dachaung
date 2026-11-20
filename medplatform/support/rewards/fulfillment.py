"""Registered C fulfillment handler and trusted simulated receipt processing."""

import json
import secrets

from ...core.documents import changed, encode, fingerprint, stamp, uid
from ...core.errors import AppError
from ...core.idempotency import Result
from ..common import CONTRACT, missing
from .catalog import DEMO_RECEIVER

TERMINAL = frozenset({"completed", "failed", "cancelled"})


def conflict(message):
    return AppError(409, "FULFILLMENT_RECEIPT_CONFLICT", message)


class RewardFulfillment:
    def __init__(self, rewards, settings):
        self.rewards, self.settings = rewards, settings
        self.db, self.clock, self.services = rewards.db, rewards.clock, rewards.services

    def authenticate(self, header):
        token = self.settings.DEMO_FULFILLMENT_RECEIPT_TOKEN.get_secret_value()
        subject = self.settings.DEMO_FULFILLMENT_RECEIPT_SUBJECT
        if not subject or len(token) < 32:
            raise AppError(503, "FULFILLMENT_UNAVAILABLE", "独立模拟交付方凭据尚未配置")
        scheme, _, supplied = (header or "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(
            supplied.encode(), token.encode()
        ):
            raise AppError(401, "AUTH_REQUIRED", "交付回执需要独立的模拟交付凭据")
        return subject

    def check(self, conn, task, task_id):
        order, fulfillment, _ = self.rewards.state(
            conn, task["payload"]["redemption_id"]
        )
        payload = {
            field: order[field]
            for field in (
                "redemption_id",
                "fulfillment_id",
                "reward_id",
                "reward_version",
            )
        }
        if (
            task["payload"] != payload
            or fulfillment["task_id"] != task_id
            or task["patient_id"] != order["patient_id"]
            or task["owner_module"] != "C"
            or task["kind"] != "fulfill_reward"
            or task["rule_version"] != CONTRACT
            or task["owner_operation_key"] != "fulfill_reward:" + order["redemption_id"]
        ):
            raise conflict("原交付任务引用不一致")
        if order["points_status"] != "debited" or fulfillment["status"] not in {
            "pending",
            "in_progress",
        }:
            raise conflict("原交付已结束或需先核查结果")
        debit = conn.execute(
            """SELECT delta FROM c_points_ledger WHERE ledger_id=? AND redemption_id=? AND entry_kind='redemption_debit'""",
            (order["debit_ledger_id"], order["redemption_id"]),
        ).fetchone()
        if not debit or debit["delta"] != -order["points_spent"]:
            raise conflict("原扣减暂不可核验")
        at = stamp(self.clock())
        if order["service_id"]:
            service = self.services.service(conn, order["service_id"])
            if (
                service["redemption_id"] != order["redemption_id"]
                or service["status"] in TERMINAL
            ):
                raise conflict("原人员服务已变化，请检查该服务")
            _, _, _, deadline = self.services.consent(conn, service, at)
            if deadline != task["valid_until"]:
                raise conflict("原授权时间已变化，请核查人员服务")
        return order, fulfillment

    def attempt(self, task, execution):
        with self.db.connection(readonly=True) as conn:
            self.check(conn, task, task["task_id"])
        # Both branches can persist only local facts inside A's fenced transaction.
        return {}

    def persist(self, conn, task, execution, at):
        order, fulfillment = self.check(conn, task, task["task_id"])
        if order["service_id"]:
            if fulfillment["status"] == "pending":
                self.transition(
                    conn,
                    order,
                    fulfillment,
                    "in_progress",
                    "a_execution",
                    execution["execution_id"],
                    at,
                    at,
                )
            return fulfillment["fulfillment_id"]
        row = conn.execute(
            """SELECT template_text,registered_at FROM c_reward_versions
                              WHERE reward_id=? AND reward_version=?""",
            (order["reward_id"], order["reward_version"]),
        ).fetchone()
        if not row or not row["template_text"]:
            raise AppError(503, "FULFILLMENT_UNAVAILABLE", "原模拟文本版本暂不可读取")
        artifact = {
            "artifact_id": uid(),
            "title": order["reward_name"],
            "media_type": "text/plain",
            "text": row["template_text"],
            "is_simulated": True,
            "source_refs": [
                {
                    "module": "C",
                    "record_kind": "reward",
                    "record_id": order["reward_id"],
                    "version": order["reward_version"],
                    "recorded_at": row["registered_at"],
                }
            ],
        }
        self.transition(
            conn,
            order,
            fulfillment,
            "completed",
            "a_execution",
            execution["execution_id"],
            at,
            at,
            artifact=artifact,
        )
        return artifact["artifact_id"]

    def observe_unknown(self, conn, task, execution, at):
        order, fulfillment, _ = self.rewards.state(
            conn, task["payload"]["redemption_id"]
        )
        if fulfillment["status"] in {"pending", "in_progress"}:
            self.transition(
                conn,
                order,
                fulfillment,
                "outcome_unknown",
                "a_execution",
                execution["execution_id"],
                at,
                at,
                reason="原执行结果未知，需依据原交付来源核查",
            )

    def observe_service(self, conn, service, origin, occurred, at):
        order, fulfillment, last = self.rewards.state(conn, service["redemption_id"])
        if order["service_id"] != service["service_id"]:
            raise conflict("兑换与原人员服务的关联不一致")
        target = service["status"]
        if fulfillment["status"] in TERMINAL or fulfillment["status"] == target:
            return
        if (
            target == "cancelled"
            and origin == "patient_cancel"
            and self.dispatch_started(conn, service["dispatch_task_id"])
        ):
            if fulfillment["status"] != "outcome_unknown":
                self.transition(
                    conn,
                    order,
                    fulfillment,
                    "outcome_unknown",
                    "c_service",
                    service["service_id"],
                    max(occurred, last),
                    at,
                    reason="收到取消意愿，原派发交付结果待核查",
                )
            return
        reason = service["failure_reason"] or service["cancellation_reason"]
        self.transition(
            conn,
            order,
            fulfillment,
            target,
            "c_service",
            service["service_id"],
            max(occurred, last),
            at,
            reason=reason,
        )

    @staticmethod
    def dispatch_started(conn, task_id):
        row = conn.execute(
            "SELECT document_json FROM a_executions WHERE task_id=? ORDER BY attempt DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is None:
            return False
        attempt = json.loads(row[0])
        return (
            attempt["execution_status"] in {"running", "outcome_unknown"}
            or attempt["delivery_status"] == "submitted"
        )

    def transition(
        self,
        conn,
        order,
        fulfillment,
        target,
        origin,
        ref,
        occurred,
        at,
        *,
        reason=None,
        artifact=None,
    ):
        if fulfillment["status"] in TERMINAL or fulfillment["status"] == target:
            raise conflict("原交付状态不允许再次变化")
        if target == "completed" and (fulfillment["kind"] == "digital_content") != (
            artifact is not None
        ):
            raise conflict("交付缺少实际产物或对应的服务完成事实")
        updated = changed(order, at)
        delivery = dict(
            fulfillment,
            status=target,
            updated_at=at,
            failure_reason=reason,
            artifact=artifact,
        )
        if target in {"failed", "cancelled"}:
            operation, ledger_id = uid(), uid()
            account = self.rewards.points.account(conn, order["patient_id"])
            self.rewards.audit(
                conn, operation, order["patient_id"], "reward_refund", at
            )
            updated.update(
                status="failed", points_status="refunded", refund_ledger_id=ledger_id
            )
        else:
            updated["status"] = "completed" if target == "completed" else "fulfilling"
        self.rewards.record(conn, updated, delivery, origin, ref, occurred, at)
        if target in {"failed", "cancelled"}:
            self.rewards.ledger(
                conn, order, operation, account, ledger_id, at, refund=True
            )

    def authorized_receipt(self, conn, subject, fulfillment_id):
        row = conn.execute(
            "SELECT redemption_id FROM c_reward_fulfillments WHERE fulfillment_id=?",
            (fulfillment_id,),
        ).fetchone()
        if row is None:
            raise missing()
        order, fulfillment, last = self.rewards.state(conn, row["redemption_id"])
        service = (
            self.services.service(conn, order["service_id"])
            if order["service_id"]
            else None
        )
        if subject != (
            service["provider"]["provider_id"] if service else DEMO_RECEIVER
        ):
            raise missing()
        return order, fulfillment, last, service

    def receive(self, subject, body, key):
        identifier = body["fulfillment_id"]

        def authorize(conn):
            return self.authorized_receipt(conn, subject, identifier)

        def process(conn):
            order, fulfillment, last, service = authorize(conn)
            request_hash = fingerprint(body)
            event = body["provider_event_id"]
            old = conn.execute(
                """SELECT request_fingerprint,ack_json FROM c_fulfillment_receipts
                                  WHERE subject=? AND provider_event_id=?""",
                (subject, event),
            ).fetchone()
            if old:
                if old["request_fingerprint"] != request_hash:
                    raise conflict("同一交付来源事件编号对应不同内容")
                ack = json.loads(old["ack_json"])
                return Result(ack, resource_type="Fulfillment", resource_id=identifier)
            occurred, at = body["occurred_at"], stamp(self.clock())
            target, status = body["status"], fulfillment["status"]
            if target == status == "completed":
                result = (
                    service["service_id"]
                    if service
                    else fulfillment["artifact"]["artifact_id"]
                )
                if body["result_ref"] != result:
                    raise conflict("回执产物引用不属于该订单")
            reason = None
            if status in TERMINAL or target == status:
                reason = "交付已终止或已核验该状态，回执留档"
            elif not last <= occurred <= at or (
                status == "outcome_unknown" and target == "in_progress"
            ):
                reason = "回执乱序或原结果尚未核清，回执留档"
            elif service:
                if target in TERMINAL:
                    if service["status"] != target or (
                        target == "completed"
                        and body["result_ref"] != service["service_id"]
                    ):
                        raise conflict("回执与原 C 服务状态或引用不一致")
                else:
                    self.services.consent(conn, service, at)
                    if target == "in_progress" and service["status"] != "in_progress":
                        raise conflict("原 C 服务尚未确认受理")
            elif target == "completed":
                # Digital results are generated only by the registered local A/C handler.
                raise conflict("未找到此次兑换已经保存的数字产物")

            op = uid()
            if reason is None:
                self.transition(
                    conn,
                    order,
                    fulfillment,
                    target,
                    "provider_receipt",
                    op,
                    occurred,
                    at,
                    reason=body["failure_reason"],
                )
            self.rewards.audit(
                conn,
                op,
                order["patient_id"],
                "fulfillment_receipt",
                at,
                outcome="committed" if reason is None else "ignored",
            )
            ack = {
                "operation_id": op,
                "resource_id": identifier,
                "applied": reason is None,
                "ignore_reason": reason,
                "received_at": at,
                "is_simulated": True,
            }
            conn.execute(
                "INSERT INTO c_fulfillment_receipts VALUES (?,?,?,?,?,?)",
                (subject, event, identifier, request_hash, op, encode(ack)),
            )
            return Result(ack, resource_type="Fulfillment", resource_id=identifier)

        return self.rewards.receipts.run(
            ["demo", "fulfillment_provider", subject, identifier],
            key,
            body,
            authorize,
            process,
        )
