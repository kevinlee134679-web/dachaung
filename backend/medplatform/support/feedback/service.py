"""C-owned voluntary feedback and its shared A/B read projection."""

import json
import sqlite3
from urllib.parse import quote, urlencode

from ...core.documents import encode, fingerprint, get, meta, stamp, uid
from ...core.errors import AppError
from ...core.idempotency import Result
from ..common import CONTRACT, next_cursor, page_after, read_guarded
from .api import DIMENSIONS

ELIGIBLE = frozenset({"completed", "cancelled", "failed"})
FEEDBACK_FIELDS = (
    "participation",
    *DIMENSIONS,
    "willing_to_continue",
    "missing_reason",
)
READ_SCOPES = {"feedback:read", "services:read"}


def source_status(availability, reason=None, records=None):
    return {
        "source_module": "C",
        "availability": availability,
        "records": records or [],
        "reason": reason,
    }


class Feedback:
    def __init__(self, db, services, clock):
        self.db, self.auth, self.receipts = db, services.auth, services.receipts
        self.services, self.clock = services, clock

    def authorize(self, conn, action, principal, path):
        if action == "feedback_source":
            patient = path["p"]
            self.auth.require_patient(
                principal, patient, "feedback:read", conn, self_only=True
            )
            doc = None
        else:
            doc = self.services.service(conn, path["id"])
            patient = doc["patient_id"]
            if action == "save_feedback":
                self.auth.require_patient(
                    principal, patient, "service-feedback:write", conn, self_only=True
                )
            else:
                self.auth.require_patient(principal, patient, "services:read", conn)
                self.auth.require_patient(principal, patient, "feedback:read", conn)
        if not get(conn, "Patient", patient)["meta"]["is_simulated"]:
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "反馈仅处理本机虚构环境")
        return patient, doc

    def handle(self, action, principal, path, query, body, key):
        def guard(conn):
            return self.authorize(conn, action, principal, path)

        if action == "save_feedback":

            def save(conn):
                patient, service = guard(conn)
                return self.save(conn, patient, service, body)

            return self.receipts.run(
                ["demo", "account", principal.account_id, "C13", path["id"]],
                key,
                body,
                guard,
                save,
            )
        with self.db.connection(readonly=True) as conn:
            with read_guarded(conn, guard) as (patient, doc):
                headers = {}
                if action == "feedback_history":
                    data = self.history(conn, principal, doc, query)
                else:
                    data, headers = self.source_page(conn, principal, patient, query)
            return Result(data, headers=headers)

    def save(self, conn, patient, service, body):
        service_id = service["service_id"]
        request_hash = fingerprint(body)
        previous = conn.execute(
            """SELECT request_fingerprint,document_json FROM c_service_feedback
               WHERE service_id=? AND client_feedback_id=?""",
            (service_id, body["client_feedback_id"]),
        ).fetchone()
        if previous is not None:
            if previous["request_fingerprint"] != request_hash:
                raise AppError(
                    409, "IDEMPOTENCY_CONFLICT", "同一反馈操作号对应不同内容"
                )
            doc = json.loads(previous["document_json"])
            return Result(
                doc,
                201,
                resource_type="ServiceFeedback",
                resource_id=doc["feedback_id"],
            )

        predecessor = conn.execute(
            """SELECT feedback_id,feedback_revision,recorded_at FROM c_service_feedback
               WHERE service_id=? ORDER BY feedback_revision DESC LIMIT 1""",
            (service_id,),
        ).fetchone()
        revision = predecessor["feedback_revision"] if predecessor else 0
        at = stamp(self.clock())
        last_service = conn.execute(
            "SELECT recorded_at FROM c_service_history WHERE service_id=? AND revision=?",
            (service_id, service["meta"]["revision"]),
        ).fetchone()[0]
        if (
            service["status"] not in ELIGIBLE
            or revision != body["expected_feedback_revision"]
            or at < last_service
            or (predecessor and at < predecessor["recorded_at"])
        ):
            raise AppError(
                409, "FEEDBACK_REVISION_CONFLICT", "反馈修订或服务状态不适合本次提交"
            )
        identifier = uid()
        doc = dict(
            feedback_id=identifier,
            patient_id=patient,
            service_id=service_id,
            feedback_revision=revision + 1,
            supersedes_feedback_id=predecessor["feedback_id"] if predecessor else None,
            **{name: body[name] for name in FEEDBACK_FIELDS},
            recorded_at=at,
            meta=meta(at, CONTRACT),
        )
        conn.execute(
            "INSERT INTO c_service_feedback VALUES (?,?,?,?,?,?,?,?)",
            (
                identifier,
                service_id,
                revision + 1,
                doc["supersedes_feedback_id"],
                body["client_feedback_id"],
                request_hash,
                at,
                encode(doc),
            ),
        )
        return Result(doc, 201, resource_type="ServiceFeedback", resource_id=identifier)

    def history(self, conn, principal, service, query):
        own = self.auth.is_self(principal, service["patient_id"], conn)
        context = [
            principal.account_id,
            "C14",
            service["patient_id"],
            service["service_id"],
        ]
        after = page_after(self.auth, query, context, [0])[0]
        limit = query.get("limit", 20)
        rows = conn.execute(
            """SELECT document_json FROM c_service_feedback
               WHERE service_id=? AND feedback_revision>? ORDER BY feedback_revision LIMIT ?""",
            (service["service_id"], after, limit + 1),
        ).fetchall()
        docs = [json.loads(row[0]) for row in rows[:limit]]
        if not own:
            # The O service sharing categories do not include feedback text.
            for doc in docs:
                doc.update(
                    dict.fromkeys(
                        (*DIMENSIONS, "willing_to_continue", "missing_reason")
                    )
                )
        cursor = next_cursor(
            rows, limit, self.auth, context, lambda _: [docs[-1]["feedback_revision"]]
        )
        return {"items": docs, "next_cursor": cursor}

    def source(self, conn, principal, patient, window):
        scopes = self.auth.scopes(principal, patient, conn)
        if not READ_SCOPES.issubset(scopes):
            return source_status("restricted", "当前授权不含反馈及底层服务读取")
        own = self.auth.is_self(principal, patient, conn)
        try:
            rows = self.source_rows(conn, patient, window)
            records = []
            for row in rows:
                feedback = (
                    json.loads(row["feedback_json"]) if row["feedback_json"] else None
                )
                descriptions = {
                    name: feedback[name] if own and feedback else None
                    for name in DIMENSIONS
                }
                records.append(
                    dict(
                        record_kind="service",
                        record_id=row["service_id"],
                        source_version=str(row["service_revision"]),
                        recorded_at=row["projected_at"],
                        service_status=row["status"],
                        **descriptions,
                        is_simulated=True,
                    )
                )
            if not records:
                return source_status("not_collected", "此窗口暂无可见 C 服务或反馈记录")
            reason = None
            if not own:
                reason = "当前仅可读取获准状态和引用，反馈描述由本人查看"
            elif all(rec[name] is None for rec in records for name in DIMENSIONS):
                reason = "已记录服务状态，此窗口暂无已填写的三维描述"
            return source_status("available", reason, records)
        except sqlite3.DatabaseError:
            return source_status("unavailable", "C反馈来源暂不可用")

    def source_rows(self, conn, patient, window):
        left, right = window["window_start"], window["window_end"]
        cutoff = window.get("as_of") or stamp(self.clock())
        return conn.execute(
            """
            SELECT s.service_id,h.revision AS service_revision,h.status,f.document_json AS feedback_json,
                   COALESCE(f.recorded_at,h.recorded_at) AS projected_at
            FROM c_services AS s
            JOIN c_service_history AS h ON h.service_id=s.service_id AND h.revision=(
                SELECT MAX(j.revision) FROM c_service_history AS j
                WHERE j.service_id=s.service_id AND j.recorded_at<=? AND j.recorded_at<?
            )
            LEFT JOIN c_service_feedback AS f ON f.service_id=s.service_id AND f.feedback_revision=(
                SELECT MAX(k.feedback_revision) FROM c_service_feedback AS k
                WHERE k.service_id=s.service_id AND k.recorded_at<=? AND k.recorded_at<?
            )
            WHERE s.patient_id=? AND COALESCE(f.recorded_at,h.recorded_at)>=?
            ORDER BY projected_at,s.service_id
        """,
            (cutoff, right, cutoff, right, patient, left),
        ).fetchall()

    def source_page(self, conn, principal, patient, query):
        limit = query.get("limit", 20)
        window = {name: query[name] for name in ("window_start", "window_end")}
        context = [principal.account_id, "C15", patient, window]
        cutoff, *after = page_after(
            self.auth, query, context, [stamp(self.clock()), "", ""]
        )
        data = self.source(conn, principal, patient, dict(window, as_of=cutoff))
        if data["availability"] == "unavailable":
            raise AppError(503, "SUPPORT_FEEDBACK_UNAVAILABLE", data["reason"])
        records = [
            rec
            for rec in data["records"]
            if [rec["recorded_at"], rec["record_id"]] > after
        ]
        if not records and data["availability"] == "available":
            return source_status(
                "not_collected", "该分页位置后没有其他获准反馈引用"
            ), {}
        token = next_cursor(
            records,
            limit,
            self.auth,
            context,
            lambda row: [cutoff, row["recorded_at"], row["record_id"]],
        )
        data["records"] = records[:limit]
        if token is None:
            return data, {}
        target = (
            "/api/v1/patients/"
            + quote(patient, safe="")
            + "/support-feedback?"
            + urlencode(dict(window, limit=limit, cursor=token))
        )
        return data, {"Link": f'<{target}>; rel="next"'}
