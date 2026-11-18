"""A's explicit C adapter for local simulated dispatch."""
import json

from .documents import stamp, uid
from .errors import AppError
from .s05_drafts import CONTRACT
from .s05_services import confirmation_required


class MockServiceDispatch:
    def __init__(self, db, services, clock):
        self.db, self.services, self.clock = db, services, clock
        self.adapter = lambda task_id, execution_id: {"delivery_status": "submitted"}

    def check(self, conn, task, task_id):
        payload = task["payload"]
        doc = self.services.service(conn, payload["service_id"])
        expected = dict(service_id=doc["service_id"], service_revision=1,
                        confirmation_ref_id=doc["confirmation_ref_id"], sharing_scope_ref_id=doc["sharing_scope_ref_id"])
        if (doc["dispatch_task_id"] != task_id or doc["patient_id"] != task["patient_id"]
                or task["owner_module"] != "C" or task["kind"] != "dispatch_service"
                or task["owner_operation_key"] != "dispatch_service:" + doc["service_id"]
                or task["rule_version"] != CONTRACT or payload != expected):
            raise confirmation_required("派发任务与正式申请来源不一致")
        if doc["status"] != "submitted" or doc["meta"]["revision"] != 1:
            raise confirmation_required("正式服务已变化，停止原派发")
        _, _, _, deadline = self.services.consent(conn, doc, stamp(self.clock()))
        if task["valid_until"] != deadline:
            raise confirmation_required("派发任务的授权期限已变化")
        return doc

    def attempt(self, task, execution):
        with self.db.connection(readonly=True) as conn:
            self.check(conn, task, task["task_id"])
        outcome = self.adapter(task["task_id"], execution["execution_id"])
        if isinstance(outcome, dict) and (outcome.get("outcome_unknown") or outcome.get("error_code")
                                          or outcome.get("delivery_status") == "submitted"):
            return outcome
        return {"outcome_unknown": True}

    @staticmethod
    def submission(conn, service_id):
        return conn.execute("SELECT * FROM c_service_dispatches WHERE service_id=?", (service_id,)).fetchone()

    @staticmethod
    def record(conn, doc, task_id, execution_id, origin, at):
        identifier = uid()
        conn.execute("INSERT INTO c_service_dispatches VALUES (?,?,?,?,?,?,?)",
                     (identifier, doc["service_id"], task_id, execution_id, doc["provider"]["provider_id"], origin, at))
        return identifier

    def persist(self, conn, task, execution, at):
        doc = self.check(conn, task, task["task_id"])
        old = self.submission(conn, doc["service_id"])
        if old:
            return old["dispatch_id"]
        return self.record(conn, doc, task["task_id"], execution["execution_id"], "mock_submission", at)

    def confirm_submission(self, conn, doc, occurred, at):
        old = self.submission(conn, doc["service_id"])
        if old:
            execution = self.services.execution._execution(conn, old["execution_id"])
            return execution["started_at"] <= occurred
        task_id = doc["dispatch_task_id"]
        row = conn.execute("SELECT document_json FROM a_executions WHERE task_id=? ORDER BY attempt DESC LIMIT 1",
                           (task_id,)).fetchone()
        if row is None:
            return False
        execution = json.loads(row[0])
        if execution["execution_status"] != "outcome_unknown" or execution["started_at"] > occurred:
            return False
        self.record(conn, doc, task_id, execution["execution_id"], "mock_provider_receipt", at)
        return True
