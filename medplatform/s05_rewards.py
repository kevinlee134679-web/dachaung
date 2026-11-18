"""C-owned redemption, ledger links, and authorized read projections."""
import json
import sqlite3

from .documents import encode, fingerprint, get, meta, stamp, uid
from .errors import AppError
from .idempotency import Result
from .s05_drafts import CONTRACT, missing
from .s05_reward_catalog import CURRENT, reward_view

SERVICE_INPUT = ("service_draft_id", "draft_revision", "confirmation_ref_id", "sharing_scope_ref_id")
# A requires a deadline. Digital benefits have no contractual expiry.
DIGITAL_DEADLINE = "9999-12-31T23:59:59.999999+00:00"
ORDER_STATE = """SELECT h.* FROM c_redemption_history h JOIN c_redemptions r USING(redemption_id)
                 WHERE h.redemption_id=? ORDER BY h.revision DESC LIMIT 1"""
READ_ERRORS = {
    "reward_list": ("REWARD_CATALOG_UNAVAILABLE", "模拟权益目录暂不可用"),
    "redemption_list": ("REDEMPTION_STORE_UNAVAILABLE", "兑换历史暂不可用"),
    "fulfillment_read": ("FULFILLMENT_UNAVAILABLE", "交付详情暂不可用"),
}


class S05Rewards:
    def __init__(self, db, points, services, clock):
        self.db, self.points, self.services, self.clock = db, points, services, clock
        self.auth, self.receipts = points.auth, points.receipts
        self.fulfillment = None

    @staticmethod
    def state(conn, identifier):
        row = conn.execute(ORDER_STATE, (identifier,)).fetchone()
        if row is None:
            raise missing()
        return json.loads(row["redemption_json"]), json.loads(row["fulfillment_json"]), row["occurred_at"]

    @staticmethod
    def record(conn, order, fulfillment, origin, ref, occurred, at):
        conn.execute("INSERT INTO c_redemption_history VALUES (?,?,?,?,?,?,?,?)",
                     (order["redemption_id"], order["meta"]["revision"], at, occurred, origin, ref,
                      encode(order), encode(fulfillment)))
        conn.execute("INSERT INTO c_redemption_notices VALUES (?,?,?)",
                     (order["redemption_id"], order["meta"]["revision"], at))

    @staticmethod
    def audit(conn, identifier, patient, action, at, actor=None, outcome="committed"):
        conn.execute("INSERT INTO operation_audit VALUES (?,?,?,?,?,?,?)",
                     (identifier, actor, patient, action, outcome, at, "demo"))

    @staticmethod
    def reward(conn, identifier):
        row = conn.execute(CURRENT + " WHERE r.reward_id=?", (identifier,)).fetchone()
        if row is None:
            raise missing()
        return row

    def authorize(self, conn, action, principal, path):
        state = self.state(conn, path["id"]) if action in {"redemption_read", "redemption_feedback", "fulfillment_read"} else None
        patient = state[0]["patient_id"] if state else path.get("p")
        if not patient:
            patient = self.auth.account(principal, conn)["current_patient_id"]
        if not patient:
            raise AppError(403, "SCOPE_REQUIRED", "请先选择本人或有积分查看授权的对象")
        write = action in {"redeem", "redemption_feedback"}
        self.auth.require_patient(principal, patient, "rewards:redeem" if write else "points:read", conn, self_only=write)
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "此入口仅使用虚构演示数据")
        return patient, state

    def handle(self, action, principal, path, query, body, key):
        if action == "fulfillment_receipt":
            return self.fulfillment.receive(principal, body, key)

        def guard(conn):
            return self.authorize(conn, action, principal, path)

        if action in {"redeem", "redemption_feedback"}:
            def operate(conn):
                patient, state = guard(conn)
                if action == "redeem":
                    data = self.redeem(conn, principal, patient, body)
                    kind, identifier = "Redemption", data["redemption_id"]
                else:
                    data = self.feedback(conn, state[0], body)
                    kind, identifier = "RedemptionFeedback", data["feedback_id"]
                return Result(data, 201, resource_type=kind, resource_id=identifier)

            return self.receipts.run(["demo", "account", principal.account_id, action, path],
                                     key, body, guard, operate)

        try:
            with self.db.connection(readonly=True) as conn:
                conn.execute("BEGIN")
                patient, state = guard(conn)
                scopes = self.auth.scopes(principal, patient, conn)
                own = self.auth.is_self(principal, patient, conn)
                if action == "reward_read":
                    result = reward_view(conn, self.reward(conn, path["id"]))
                elif action == "redemption_read":
                    result = self.order_view(state[0], scopes)
                elif action == "fulfillment_read":
                    result = dict(state[1])
                    if not own:
                        result.update(artifact=None, failure_reason=None)
                    if "services:read" not in scopes:
                        result["service_id"] = None
                    if "tasks:read" not in scopes:
                        result["task_id"] = None
                else:
                    result = self.page(conn, principal, patient, action, query, scopes)
                conn.commit()
                if guard(conn)[0] != patient or self.auth.scopes(principal, patient, conn) != scopes:
                    raise AppError(403, "SOURCE_ACCESS_CHANGED", "授权或患者已变化，请重新读取")
                return Result(result)
        except (sqlite3.Error, json.JSONDecodeError):
            code, message = READ_ERRORS.get(action, ("REDEMPTION_STORE_UNAVAILABLE", "兑换数据暂不可用"))
            raise AppError(503, code, message) from None

    @staticmethod
    def order_view(order, scopes):
        return order if "services:read" in scopes else dict(order, service_id=None)

    def page(self, conn, principal, patient, action, query, scopes):
        catalog = action == "reward_list"
        context = [principal.account_id, patient, action]
        after = [""] if catalog else ["", ""]
        if "cursor" in query:
            cursor = self.auth.read_cursor(query["cursor"], context)
            if len(cursor) != len(after) or not all(isinstance(value, str) for value in cursor):
                raise AppError(422, "INVALID_CURSOR", "分页位置无效")
            after = cursor
        limit = int(query.get("limit", 20))
        if catalog:
            if conn.execute("SELECT 1 FROM c_rewards LIMIT 1").fetchone() is None:
                raise AppError(503, "REWARD_CATALOG_UNAVAILABLE", "请显式登记模拟权益目录")
            rows = conn.execute(CURRENT + " WHERE r.reward_id>? ORDER BY r.reward_id LIMIT ?",
                                (*after, limit + 1)).fetchall()
            items = [reward_view(conn, row) for row in rows[:limit]]
            fields = ("reward_id",)
        else:
            rows = conn.execute("""SELECT redemption_id,redeemed_at FROM c_redemptions WHERE patient_id=?
                                  AND (redeemed_at,redemption_id)>(?,?) ORDER BY redeemed_at,redemption_id LIMIT ?""",
                                (patient, *after, limit + 1)).fetchall()
            items = [self.order_view(self.state(conn, row["redemption_id"])[0], scopes) for row in rows[:limit]]
            fields = ("redeemed_at", "redemption_id")
        cursor = self.auth.cursor(context, [rows[limit - 1][field] for field in fields]) if len(rows) > limit else None
        return dict(items=items, next_cursor=cursor)

    def ledger(self, conn, order, operation, account, identifier, at, *, refund=False):
        cost = order["points_spent"]
        delta = cost if refund else -cost
        kind = "redemption_refund" if refund else "redemption_debit"
        key = ("refund:" if refund else "redeem:") + order["redemption_id"]
        conn.execute("""INSERT INTO c_points_ledger
                     (ledger_id,points_account_id,patient_id,operation_id,entry_kind,delta,balance_after,business_key,
                      created_at,redemption_id,reverses_ledger_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (identifier, account["points_account_id"], order["patient_id"], operation, kind, delta,
                      account["balance"] + delta, key, at, order["redemption_id"],
                      order["debit_ledger_id"] if refund else None))
        conn.execute("UPDATE c_points_accounts SET revision=revision+1,updated_at=? WHERE points_account_id=?",
                     (at, account["points_account_id"]))

    def redeem(self, conn, principal, patient, body):
        revision = body["expected_account_revision"]
        request_hash = fingerprint(body)
        old = conn.execute("""SELECT redemption_id,request_fingerprint FROM c_redemptions
                              WHERE patient_id=? AND account_revision=?""", (patient, revision)).fetchone()
        if old is not None and old["request_fingerprint"] == request_hash:
            original = conn.execute("SELECT redemption_json FROM c_redemption_history WHERE redemption_id=? AND revision=1",
                                    (old["redemption_id"],)).fetchone()
            return json.loads(original[0])
        account = self.points.account(conn, patient)
        if account["meta"]["revision"] != revision:
            raise AppError(409, "REVISION_CONFLICT", "积分账户已更新，请重新查看并确认")
        row = self.reward(conn, body["reward_id"])
        reward = reward_view(conn, row)
        if reward["reward_version"] != body["reward_version"] or reward["availability"] != "available":
            raise AppError(409, "REWARD_VERSION_CONFLICT", "权益版本或可用状态已变化，请重新核对")
        cost = reward["points_cost"]
        if account["balance"] < cost:
            raise AppError(409, "INSUFFICIENT_POINTS", "当前积分不足以兑换这一额外权益")
        now = self.clock()
        at = stamp(now)
        identifier, fulfillment_id, task_id, debit, operation = (uid() for _ in range(5))
        service_id, deadline = None, DIGITAL_DEADLINE
        service_input = {name: body[name] for name in SERVICE_INPUT}
        if reward["kind"] == "service_appointment":
            if None in service_input.values():
                raise AppError(409, "SERVICE_CONFIRMATION_REQUIRED", "请本人核对并确认原服务草稿和共享范围")
            draft, resource, deadline = self.services.prepared(conn, principal, patient, service_input, at,
                                                               redemption_id=identifier)
            if (draft["resource_id"], resource["resource_version"]) != (reward["resource_id"], row["resource_version"]):
                raise AppError(409, "SERVICE_CONFIRMATION_REQUIRED", "原草稿与此兑换权益的资源版本不一致")
            service = self.services.submit(conn, principal, patient, service_input, redemption_id=identifier)
            service_id = service["service_id"]
        elif any(value is not None for value in service_input.values()):
            raise AppError(422, "VALIDATION_ERROR", "数字权益无需共享或服务草稿")

        order = dict(redemption_id=identifier, patient_id=patient, reward_id=reward["reward_id"],
                     reward_version=reward["reward_version"], reward_name=reward["name"], points_spent=cost,
                     status="submitted", points_status="debited", debit_ledger_id=debit, refund_ledger_id=None,
                     balance_after_debit=account["balance"] - cost, fulfillment_id=fulfillment_id,
                     service_id=service_id, redeemed_at=at, meta=meta(at, CONTRACT))
        fulfillment = dict(fulfillment_id=fulfillment_id, redemption_id=identifier, patient_id=patient,
                           kind=reward["kind"], status="pending", service_id=service_id, artifact=None,
                           failure_reason=None, task_id=task_id, updated_at=at, is_simulated=True)
        conn.execute("INSERT INTO c_redemptions VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (identifier, patient, reward["reward_id"], reward["reward_version"], debit, service_id,
                      fulfillment_id, at, revision, request_hash))
        conn.execute("INSERT INTO c_reward_fulfillments VALUES (?,?,?)", (fulfillment_id, identifier, task_id))
        self.audit(conn, operation, patient, "reward_redeem", at, principal.account_id)
        self.ledger(conn, order, operation, account, debit, at)
        self.record(conn, order, fulfillment, "patient_redeem", operation, at, at)
        self.services.execution.create_in_transaction(conn, principal, {
            "patient_id": patient, "kind": "fulfill_reward", "owner_module": "C",
            "owner_operation_key": "fulfill_reward:" + identifier,
            "scheduled_at": at, "valid_until": deadline, "rule_version": CONTRACT,
            "payload": {name: order[name] for name in ("redemption_id", "fulfillment_id", "reward_id", "reward_version")},
        }, internal=True, task_id=task_id)
        return order

    def feedback(self, conn, order, body):
        request_hash = fingerprint(body)
        old = conn.execute("""SELECT request_fingerprint,document_json FROM c_redemption_feedback
                            WHERE redemption_id=? AND client_feedback_id=?""",
                           (order["redemption_id"], body["client_feedback_id"])).fetchone()
        if old is not None:
            if old["request_fingerprint"] != request_hash:
                raise AppError(409, "IDEMPOTENCY_CONFLICT", "同一反馈编号对应不同内容")
            return json.loads(old["document_json"])
        reference = body["service_feedback_id"]
        if reference is not None and (not order["service_id"] or not conn.execute(
                "SELECT 1 FROM c_service_feedback WHERE service_id=? AND feedback_id=?",
                (order["service_id"], reference)).fetchone()):
            raise AppError(409, "REDEMPTION_FEEDBACK_CONFLICT", "反馈必须来自本次兑换关联的正式服务")
        if order["status"] not in {"completed", "failed"}:
            raise AppError(409, "REDEMPTION_FEEDBACK_CONFLICT", "请等待交付状态核清后再评价")
        if body["participation"] != "provided" and (body["experience"] or reference):
            raise AppError(422, "VALIDATION_ERROR", "未提供评价时请留空正文和关联反馈")
        doc = dict(feedback_id=uid(), patient_id=order["patient_id"], redemption_id=order["redemption_id"],
                   participation=body["participation"], experience=body["experience"], service_feedback_id=reference,
                   recorded_at=stamp(self.clock()), is_simulated=True)
        conn.execute("INSERT INTO c_redemption_feedback VALUES (?,?,?,?,?)",
                     (doc["feedback_id"], order["redemption_id"], body["client_feedback_id"], request_hash, encode(doc)))
        return doc
