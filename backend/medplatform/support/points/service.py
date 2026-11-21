"""Positive points evaluation and the authoritative C ledger."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from ...core.documents import all_docs, encode, fingerprint, get, meta, now, stamp, uid
from ...core.errors import AppError
from ...core.idempotency import Result
from ...core.migrations import status
from ..common import CONTRACT, next_cursor, page_after, read_guarded
from ..points.sources import (
    ISSUES,
    PointsSources,
    iso_monday,
    patient_date,
)

RULES_VERSION = "points-demo-v1"
RULES = {
    "daily_record": (
        2,
        "day",
        "正式时段已到且至少一条核验有效的本人或获准家属手动报告。所有如实结局都可记录。",
    ),
    "five_day_block": (
        5,
        "five_day_block",
        "最早的连续五个合格计划日成块，每日只可分配一次。",
    ),
    "weekly_review": (3, "week", "本人在当地 ISO 周明确完成回顾，该周一次。"),
    "peer_participation": (
        2,
        "week",
        "本人主动提交的同辈文字经审核实际可见，按首次公开所在当地 ISO 周计一次。",
    ),
}


def rules_view(version):
    if version != RULES_VERSION:
        raise AppError(404, "POINTS_RULES_NOT_ENABLED", "该积分规则版本未启用")
    return {
        "rules_version": version,
        "timezone_source": "patient",
        "week_start_day": 1,
        "is_simulated": True,
        "rules": [
            {
                "rule_code": code,
                "points": data[0],
                "period": data[1],
                "max_awards_per_period": 1,
                "eligibility_description": data[2],
            }
            for code, data in RULES.items()
        ],
    }


def seed_points(db, clock=now):
    status(db)
    at, created = stamp(clock()), 0
    with db.transaction() as conn:
        for patient in all_docs(conn, "Patient"):
            if patient["meta"]["is_simulated"]:
                created += conn.execute(
                    """
                    INSERT INTO c_points_accounts VALUES (?,?,1,?,?) ON CONFLICT(patient_id) DO NOTHING
                """,
                    (uid(), patient["patient_id"], at, at),
                ).rowcount
    return created


def conflict():
    return AppError(
        409, "POINTS_RECONCILE_CONFLICT", "请选择启用的规则和可核验的积分来源"
    )


class Points:
    def __init__(self, db, auth, receipts, analytics, peer, clock):
        self.db, self.auth, self.receipts, self.clock = db, auth, receipts, clock
        self.sources = PointsSources(analytics, peer, auth)

    def authorize(self, conn, action, principal, patient):
        if action == "rules":
            self.auth.account(principal, conn)
            return None
        if action == "reconcile":
            if not self.auth.account(principal, conn)["is_admin"]:
                raise AppError(403, "ADMIN_REQUIRED", "核奖仅允许受控本地演示身份执行")
        elif action == "complete_review":
            self.auth.require_patient(principal, patient, "", conn, self_only=True)
        elif action == "reviews":
            self.auth.require_patient(principal, patient, "feedback:read", conn)
            self.auth.require_patient(principal, patient, "services:read", conn)
        else:
            self.auth.require_patient(principal, patient, "points:read", conn)
        doc = get(conn, "Patient", patient)
        if not doc["meta"]["is_simulated"]:
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "此入口仅处理虚构演示数据")
        return doc

    def handle(self, action, principal, path, query, body, key):
        patient = path.get("p") or body.get("patient_id")

        def guard(conn):
            return self.authorize(conn, action, principal, patient)

        if action in {"rules", "account", "ledger", "reviews"}:

            def verify(_authorized, _current):
                if (
                    scopes is not None
                    and self.auth.scopes(principal, patient, conn) != scopes
                ):
                    raise AppError(
                        403, "SOURCE_ACCESS_CHANGED", "来源授权已变化，请重新读取"
                    )
                if action == "ledger":
                    peer_refs = {
                        ref["record_id"]
                        for entry in result["items"]
                        for ref in entry["source_refs"]
                        if ref["record_kind"] == "peer_post"
                    }
                    if peer_refs and not peer_refs.issubset(
                        self.visible_peer_refs(conn, patient)
                    ):
                        raise AppError(
                            403, "SOURCE_ACCESS_CHANGED", "来源授权已变化，请重新读取"
                        )

            with self.db.connection(readonly=True) as conn:
                with read_guarded(conn, guard, verify):
                    scopes = (
                        self.auth.scopes(principal, patient, conn)
                        if action == "ledger"
                        else None
                    )
                    if action == "rules":
                        result = rules_view(query.get("rules_version", RULES_VERSION))
                    elif action == "account":
                        result = self.account(conn, patient)
                    else:
                        result = self.page(
                            conn, action, principal, patient, query, scopes
                        )
                return Result(result)

        def operate(conn):
            doc = guard(conn)
            if action == "complete_review":
                return self.complete_review(conn, principal, doc, body)
            return self.reconcile(conn, principal, doc, body)

        return self.receipts.run(
            ["demo", "account", principal.account_id, "C-points", action, patient],
            key,
            body,
            guard,
            operate,
        )

    def account(self, conn, patient):
        row = conn.execute(
            """
            SELECT a.*,COALESCE((SELECT SUM(l.delta) FROM c_points_ledger l WHERE l.points_account_id=a.points_account_id),0) AS balance
            FROM c_points_accounts a WHERE a.patient_id=?
        """,
            (patient,),
        ).fetchone()
        if row is None:
            raise AppError(
                503, "POINTS_ACCOUNT_NOT_READY", "当前积分账户尚未显式初始化"
            )
        return {
            "points_account_id": row["points_account_id"],
            "patient_id": patient,
            "balance": row["balance"],
            "meta": dict(
                meta(row["created_at"], CONTRACT),
                updated_at=row["updated_at"],
                revision=row["revision"],
            ),
        }

    def page(self, conn, action, principal, patient, query, scopes):
        left, right = query["window_start"], query["window_end"]
        limit = query.get("limit", 20)
        context = [principal.account_id, patient, action, left, right]
        after = page_after(self.auth, query, context, ["", ""])
        if action == "ledger":
            self.account(conn, patient)
            table, time, key = "c_points_ledger", "created_at", "ledger_id"
        else:
            table, time, key = "c_management_reviews", "completed_at", "review_id"
        rows = conn.execute(
            f"""SELECT * FROM {table} WHERE patient_id=? AND {time}>=? AND {time}<?
                                AND ({time},{key})>(?,?) ORDER BY {time},{key} LIMIT ?""",
            (patient, left, right, *after, limit + 1),
        ).fetchall()
        own = self.auth.is_self(principal, patient, conn)
        if action == "ledger":
            peer_refs = self.visible_peer_refs(conn, patient) if own else set()
            items = [
                self.ledger_view(conn, row, scopes, peer_refs) for row in rows[:limit]
            ]
        else:
            items = [self.review_view(row, own) for row in rows[:limit]]
        cursor = next_cursor(
            rows, limit, self.auth, context, lambda row: [row[time], row[key]]
        )
        return {"items": items, "next_cursor": cursor}

    def visible_peer_refs(self, conn, patient):
        return {
            r["post_id"]
            for r in self.sources.peer_rows(conn, patient)
            if r["membership_status"] == "active"
            and r["status"] == "visible"
            and self.sources.peer.access_current(conn, r["group_id"], r["service_id"])
        }

    def ledger_view(self, conn, row, scopes=None, peer_refs=None):
        sources = []
        for ref in conn.execute(
            "SELECT * FROM c_points_award_sources WHERE ledger_id=? ORDER BY source_order",
            (row["ledger_id"],),
        ):
            kind = ref["record_kind"]
            visible = (
                scopes is None
                or kind == "event"
                and "records:read" in scopes
                or kind == "management_review"
                and {"feedback:read", "services:read"}.issubset(scopes)
                or kind == "peer_post"
                and ref["record_id"] in (peer_refs or set())
            )
            if visible:
                sources.append(
                    {
                        "module": ref["module"],
                        "record_kind": kind,
                        "record_id": ref["record_id"],
                        "version": str(ref["source_revision"]),
                        "recorded_at": ref["recorded_at"],
                    }
                )
        if row["redemption_id"]:
            revision = conn.execute(
                """SELECT revision FROM c_redemption_history
                WHERE redemption_id=? AND (revision=1 AND ? IS NULL
                    OR json_extract(redemption_json,'$.refund_ledger_id')=?)
                ORDER BY revision LIMIT 1""",
                (row["redemption_id"], row["reverses_ledger_id"], row["ledger_id"]),
            ).fetchone()
            sources.append(
                {
                    "module": "C",
                    "record_kind": "redemption",
                    "record_id": row["redemption_id"],
                    "version": str(revision[0]),
                    "recorded_at": row["created_at"],
                }
            )
        return {
            name: row[name]
            for name in (
                "ledger_id",
                "points_account_id",
                "patient_id",
                "entry_kind",
                "delta",
                "balance_after",
                "business_key",
                "rule_code",
                "rules_version",
                "created_at",
                "redemption_id",
                "reverses_ledger_id",
            )
        } | {"source_refs": sources, "is_simulated": True}

    @staticmethod
    def review_view(row, own=True):
        return {
            "review_id": row["review_id"],
            "patient_id": row["patient_id"],
            "week_start": row["week_start"],
            "reflection": row["reflection"] if own else None,
            "completed_at": row["completed_at"],
            "rules_version": row["rules_version"],
            "meta": meta(row["completed_at"], CONTRACT),
        }

    def complete_review(self, conn, principal, patient_doc, body):
        patient, at = patient_doc["patient_id"], stamp(self.clock())
        old = conn.execute(
            "SELECT * FROM c_management_reviews WHERE patient_id=? AND client_review_id=?",
            (patient, body["client_review_id"]),
        ).fetchone()
        request = fingerprint(body)
        if old:
            if old["request_fingerprint"] != request:
                raise AppError(
                    409, "IDEMPOTENCY_CONFLICT", "同一回顾操作号对应不同内容"
                )
            return Result(
                self.review_view(old),
                201,
                resource_type="ManagementReview",
                resource_id=old["review_id"],
            )
        week = iso_monday(
            patient_date(at, ZoneInfo(patient_doc["timezone"]))
        ).isoformat()
        if (
            body["week_start"] != week
            or conn.execute(
                "SELECT 1 FROM c_management_reviews WHERE patient_id=? AND week_start=?",
                (patient, week),
            ).fetchone()
        ):
            raise AppError(
                409,
                "MANAGEMENT_REVIEW_PERIOD_CONFLICT",
                "仅可明确完成本人当前周的一次回顾",
            )
        identifier = uid()
        conn.execute(
            "INSERT INTO c_management_reviews VALUES (?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                patient,
                principal.account_id,
                week,
                body["client_review_id"],
                request,
                body["reflection"],
                at,
                RULES_VERSION,
            ),
        )
        saved = conn.execute(
            "SELECT * FROM c_management_reviews WHERE review_id=?", (identifier,)
        ).fetchone()
        return Result(
            self.review_view(saved),
            201,
            resource_type="ManagementReview",
            resource_id=identifier,
        )

    def reconcile(self, conn, principal, patient_doc, body):
        if body["rules_version"] != RULES_VERSION:
            raise conflict()
        patient, at = patient_doc["patient_id"], stamp(self.clock())
        left, right = body["window_start"], body["window_end"]
        account = self.account(conn, patient)
        zone = ZoneInfo(patient_doc["timezone"])
        plans = {
            (doc["plan_id"], doc["plan_version"]): doc
            for doc in self.sources.analytics.plans_as_of(conn, patient, at)
        }
        issues = set()
        days = self.sources.select_manual(conn, patient, left, right, at, plans, issues)
        reviews = self.sources.select_reviews(conn, patient, left, right, at, issues)
        peers = self.sources.select_peer(conn, patient, left, right, at, zone, issues)
        source_issues = [
            {"code": code, "message": ISSUES[code], "field": None}
            for code in sorted(issues)
        ]
        awards, skipped = self.choose_awards(conn, patient, days, reviews, peers)
        operation = uid()
        conn.execute(
            "INSERT INTO operation_audit VALUES (?,?,?,?,?,?,?)",
            (
                operation,
                principal.account_id,
                patient,
                "points_reconcile",
                "committed",
                at,
                "demo",
            ),
        )
        conn.execute(
            "INSERT INTO c_points_reconciliations VALUES (?,?,?,?,?,?)",
            (
                operation,
                patient,
                left,
                right,
                RULES_VERSION,
                encode(source_issues),
            ),
        )
        entries, allocations = [], []
        balance = account["balance"]
        for rule, period, refs in awards:
            balance += RULES[rule][0]
            entry, dates = self.award(
                conn, account, operation, rule, period, refs, balance, at
            )
            entries.append(entry)
            allocations.extend(dates)
        if entries:
            conn.execute(
                "UPDATE c_points_accounts SET revision=revision+1,updated_at=? WHERE points_account_id=?",
                (at, account["points_account_id"]),
            )
        return Result(
            {
                "patient_id": patient,
                "window_start": left,
                "window_end": right,
                "account": self.account(conn, patient),
                "new_entries": entries,
                "new_allocations": allocations,
                "skipped_keys": sorted(skipped),
                "source_issues": source_issues,
                "rules_version": RULES_VERSION,
            },
            resource_type="PointsReconcileResult",
            resource_id=operation,
        )

    def choose_awards(self, conn, patient, days, reviews, peers):
        existing = {
            (row["rule_code"], date.fromisoformat(row["period_start"])): row[
                "business_key"
            ]
            for row in conn.execute(
                "SELECT * FROM c_points_ledger WHERE patient_id=? AND entry_kind='award'",
                (patient,),
            )
        }
        used = {
            (row["rule_code"], row["record_id"]): row["business_key"]
            for row in conn.execute(
                """
                    SELECT s.rule_code,s.record_id,l.business_key
                    FROM c_points_award_sources s JOIN c_points_ledger l USING(ledger_id)
                    WHERE s.patient_id=?
                """,
                (patient,),
            )
        }
        awards, skipped = [], set()
        for rule, grouped in (
            ("daily_record", days),
            ("weekly_review", reviews),
            ("peer_participation", peers),
        ):
            for period, refs in sorted(grouped.items()):
                if (rule, period) in existing:
                    skipped.add(existing[rule, period])
                    continue
                selected = next(
                    (ref for ref in refs if (rule, ref.record_id) not in used), None
                )
                if selected:
                    awards.append((rule, period, [selected]))
                else:
                    skipped.update(used[rule, ref.record_id] for ref in refs)
        rule = "five_day_block"
        assigned = {
            date.fromisoformat(row["local_date"]): row["business_key"]
            for row in conn.execute(
                """
            SELECT a.local_date,l.business_key FROM c_points_date_allocations a JOIN c_points_ledger l USING(ledger_id)
            WHERE a.patient_id=?
        """,
                (patient,),
            )
        }
        block = []
        for day, refs in sorted(days.items()):
            if day in assigned:
                skipped.add(assigned[day])
                continue
            selected = next(
                (ref for ref in refs if (rule, ref.record_id) not in used), None
            )
            if not selected:
                skipped.update(used[rule, ref.record_id] for ref in refs)
                continue
            if block and block[-1].period + timedelta(days=1) != day:
                block.clear()
            block.append(selected)
            if len(block) == 5:
                awards.append((rule, block[0].period, block))
                block = []
        return awards, skipped

    def award(self, conn, account, operation, rule, period, refs, balance, at):
        identifier, patient = uid(), account["patient_id"]
        key = f"{patient}:{rule}:{period.isoformat()}"
        conn.execute(
            """INSERT INTO c_points_ledger
                     (ledger_id,points_account_id,patient_id,operation_id,entry_kind,delta,balance_after,
                      business_key,rule_code,period_start,rules_version,created_at) VALUES (?,?,?,?,'award',?,?,?,?,?,?,?)""",
            (
                identifier,
                account["points_account_id"],
                patient,
                operation,
                RULES[rule][0],
                balance,
                key,
                rule,
                period.isoformat(),
                RULES_VERSION,
                at,
            ),
        )
        allocated = []
        for index, ref in enumerate(refs, 1):
            conn.execute(
                "INSERT INTO c_points_award_sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    patient,
                    rule,
                    ref.module,
                    ref.record_kind,
                    ref.record_id,
                    ref.revision,
                    ref.recorded_at,
                    ref.anchor_at,
                    index,
                ),
            )
            if rule == "five_day_block":
                allocation = {
                    "allocation_id": uid(),
                    "patient_id": patient,
                    "rule_code": rule,
                    "local_date": ref.period.isoformat(),
                    "ledger_id": identifier,
                    "rules_version": RULES_VERSION,
                    "assigned_at": at,
                }
                conn.execute(
                    "INSERT INTO c_points_date_allocations VALUES (?,?,?,?,?,?,?)",
                    tuple(allocation.values()),
                )
                allocated.append(allocation)
        row = conn.execute(
            "SELECT * FROM c_points_ledger WHERE ledger_id=?", (identifier,)
        ).fetchone()
        return self.ledger_view(conn, row), allocated
