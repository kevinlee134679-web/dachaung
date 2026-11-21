"""A6/A5 permission-specific live computations."""

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..core.documents import get, stamp
from ..core.errors import AppError
from ..core.idempotency import Result
from ..web.inputs import query_fields, query_window, utc
from .records import METRICS
from .schedule import require_coverage

COUNT_VERSION = "flow-v0.1-count-v1"


def valid_plan_slot(slot, plan):
    return bool(
        plan
        and slot["status"] != "cancelled"
        and plan["effective_from"] <= slot["scheduled_at"]
        and (
            not plan["effective_until"]
            or slot["scheduled_at"] < plan["effective_until"]
        )
    )


ROUTES = [
    ("A28", "GET", "/patients/{p}/medication-statistics", "analytics_statistics", None),
    ("A29", "GET", "/patients/{p}/medication-trends", "analytics_trend", None),
    ("A30", "GET", "/patients/{p}/measurement-trends", "analytics_measurement", None),
    ("A31", "GET", "/patients/{p}/summary", "analytics_summary", None),
    ("A41", "GET", "/patients/{p}/feedback-overview", "analytics_feedback", None),
]


def query_input(action, pairs):
    pairs = list(pairs)
    if len(dict(pairs)) != len(pairs):
        raise AppError(422, "VALIDATION_ERROR", "查询字段重复")
    allowed = {"window_start", "window_end", "as_of", "data_environment"}
    if action == "analytics_trend":
        allowed.add("period")
    if action == "analytics_measurement":
        allowed.update(("metric_code", "unit", "method_code"))
    try:
        q = query_fields(pairs, allowed)
        query_window(q)
        if "as_of" in q:
            q["as_of"] = utc(q["as_of"])
        if q["data_environment"] not in (
            "demo",
            "real",
        ):
            raise ValueError()
        if action == "analytics_trend" and q.get("period", "day") != "day":
            raise ValueError()
        if action == "analytics_measurement":
            if (
                q["metric_code"] not in METRICS
                or q["unit"] != METRICS[q["metric_code"]]
            ):
                raise AppError(
                    422,
                    "INCOMPARABLE_MEASUREMENT_QUERY",
                    "请指定已登记指标的标准单位和同一方法",
                )
            if "method_code" in q and not 1 <= len(q["method_code"]) <= 200:
                raise ValueError()
    except KeyError, ValueError, TypeError, OverflowError:
        raise AppError(
            422, "VALIDATION_ERROR", "查询窗口、时区、环境或字段不合法"
        ) from None
    return q


class Analytics:
    def __init__(self, db, auth, clock, records):
        self.db, self.auth, self.clock, self.records = (
            db,
            auth,
            clock,
            records,
        )
        self.support_feedback = None
        self.service_feedback = None

    def authorize(self, c, principal, patient, scope):
        self.auth.require_patient(principal, patient, scope, c)

    def window(self, q):
        q = dict(q)
        q["as_of"] = q.get("as_of") or stamp(self.clock())
        if q["data_environment"] != "demo":
            raise AppError(403, "ENVIRONMENT_FORBIDDEN", "本地演示不能访问真实数据")
        if q["as_of"] > stamp(self.clock()):
            raise AppError(422, "INVALID_AS_OF", "统计截止不能晚于服务器当前时间")
        return q

    def handle(self, action, principal, params, q, body, key):
        patient = params["p"]
        scope = {
            "analytics_statistics": "statistics:read",
            "analytics_trend": "statistics:read",
            "analytics_measurement": "measurements:read",
            "analytics_feedback": "feedback:read",
        }.get(action, "summary:read")
        with self.db.connection(readonly=True) as c:
            c.execute("BEGIN")
            self.authorize(c, principal, patient, scope)
            window = self.window(q)
            if action == "analytics_measurement":
                data = self.measurement_trend(c, patient, window)
            elif action == "analytics_feedback":
                data = self.feedback(c, patient, window, principal)
            elif action == "analytics_summary":
                data = self.summary(c, principal, patient, window)
            else:
                inputs = self.source_inputs(c, patient, window)
                data = self.compute_statistics(c, patient, window, inputs)
                if action == "analytics_trend":
                    data = self.daily(c, patient, window, data, inputs)
            self.authorize(c, principal, patient, scope)
            c.commit()
            return Result(data)

    def plans_as_of(self, c, patient, as_of):
        plans = {}
        for row in c.execute(
            "SELECT h.document_json FROM s02_document_history h JOIN s02_documents d USING(resource_key) WHERE d.resource_type='PlanVersion' AND d.patient_id=? ORDER BY h.revision",
            (patient,),
        ):
            doc = json.loads(row[0])
            if doc["meta"]["updated_at"] <= as_of and doc["confirmed_at"] <= as_of:
                plans[(doc["plan_id"], doc["plan_version"])] = doc
        return list(plans.values())

    def source_inputs(self, c, patient, window):
        plans = self.plans_as_of(c, patient, window["as_of"])
        details = self.records.effective_event_details(
            c, patient, window["data_environment"], window["as_of"]
        )
        return plans, details

    def compute_statistics(self, c, patient, window, inputs=None):
        plans, details = inputs or self.source_inputs(c, patient, window)
        by_plan = {(p["plan_id"], p["plan_version"]): p for p in plans}
        cutoff = window["as_of"]
        due_right = min(
            window["window_end"],
            stamp(datetime.fromisoformat(cutoff) + timedelta(microseconds=1)),
        )
        for plan in plans:
            left = max(window["window_start"], plan["effective_from"])
            right = min(due_right, plan["effective_until"] or due_right)
            require_coverage(
                c,
                plan,
                left,
                right,
                "该范围尚未物化，请先运行受控显式维护；查询不会补齐",
            )
        slots = []
        for row in c.execute(
            "SELECT * FROM dose_slots WHERE patient_id=? AND data_environment=? AND scheduled_at>=? AND scheduled_at<? AND scheduled_at<=? ORDER BY scheduled_at,dose_slot_id",
            (
                patient,
                window["data_environment"],
                window["window_start"],
                window["window_end"],
                cutoff,
            ),
        ):
            slot = dict(row)
            plan = by_plan.get((slot["plan_id"], slot["plan_version"]))
            if plan is None and not get(
                c,
                "PlanVersion",
                slot["plan_id"] + ":" + str(slot["plan_version"]),
                required=False,
            ):
                raise AppError(
                    503,
                    "PLAN_DEPENDENCY_UNAVAILABLE",
                    "正式时段的权威计划不可用，不能把依赖失败显示为零",
                )
            if valid_plan_slot(slot, plan):
                slots.append(slot)
        groups = {s["dose_slot_id"]: [] for s in slots}
        for item in details:
            event, match = item["event"], item["match"]
            if event["event_kind"] != "medication":
                continue
            target = (match or {}).get("dose_slot_id") or event["payload"].get(
                "dose_slot_id"
            )
            if target in groups:
                groups[target].append(item)
        counts = {
            "patient_confirmed_count": 0,
            "reported_not_taken_count": 0,
            "postponed_count": 0,
            "unconfirmed_evidence_count": 0,
            "unknown_count": 0,
        }
        issues = []
        for slot in slots:
            category, code = self.classify(groups[slot["dose_slot_id"]])
            counts[category] += 1
            if code:
                issues.append(
                    {
                        "dose_slot_id": slot["dose_slot_id"],
                        "code": code,
                        "message": {
                            "no_record": "暂无有效明确报告或其他证据",
                            "conflicting_reports": "报告先后或最终结果有未解决矛盾，请复核原始依据",
                            "quality_pending": "质量或关联尚未通过复核",
                            "unknown_report": "本人明确表示不确定，保留未知",
                        }.get(code, "证据待核对"),
                        "event_ids": [
                            x["event"]["event_id"] for x in groups[slot["dose_slot_id"]]
                        ],
                    }
                )
        total = len(slots)
        if not total:
            issues.append(
                {
                    "dose_slot_id": None,
                    "code": "no_plan_doses",
                    "message": "该截止与窗口内确无已到时有效计划时段",
                    "event_ids": [],
                }
            )
        refs = sorted({(s["plan_id"], s["plan_version"]) for s in slots})
        return {
            "patient_id": patient,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "as_of": cutoff,
            "timezone": get(c, "Patient", patient)["timezone"],
            "data_environment": window["data_environment"],
            "plan_refs": [{"plan_id": p, "plan_version": v} for p, v in refs],
            "planned_dose_count": total,
            **counts,
            "patient_confirmation_ratio": counts["patient_confirmed_count"] / total
            if total
            else None,
            "issues": issues,
            "rule_version": COUNT_VERSION,
            "updated_at": stamp(self.clock()),
            "is_simulated": True,
        }

    @staticmethod
    def classify(items):
        if not items:
            return "unknown_count", "no_record"
        if any(
            x["event"]["quality"]["status"] != "valid"
            or (x["match"] or {}).get("link_status") != "matched"
            for x in items
        ):
            return "unknown_count", "quality_pending"
        own = [
            x["event"] for x in items if x["event"]["evidence_type"] == "self_report"
        ]
        manual_finals = [
            x["event"]["payload"]["reported_status"]
            for x in items
            if x["event"]["evidence_type"] in ("self_report", "family_report")
            and x["event"]["payload"]["reported_status"] in ("taken", "not_taken")
        ]
        if len(set(manual_finals)) > 1:
            return "unknown_count", "conflicting_reports"
        finals = [
            e for e in own if e["payload"]["reported_status"] in ("taken", "not_taken")
        ]
        postponed = [e for e in own if e["payload"]["reported_status"] == "postponed"]
        if len({e["payload"]["reported_status"] for e in finals}) > 1:
            return "unknown_count", "conflicting_reports"
        if finals:
            if postponed and any(
                p["reporter_account_id"] != f["reporter_account_id"]
                or p["occurred_at"] >= f["occurred_at"]
                or p["received_at"] > f["received_at"]
                for p in postponed
                for f in finals
            ):
                return "unknown_count", "conflicting_reports"
            return (
                "patient_confirmed_count"
                if finals[0]["payload"]["reported_status"] == "taken"
                else "reported_not_taken_count"
            ), None
        if postponed:
            return "postponed_count", None
        if own:
            return "unknown_count", "unknown_report"
        return "unconfirmed_evidence_count", None

    def daily(self, c, patient, window, aggregate, inputs):
        zone = ZoneInfo(aggregate["timezone"])
        start = datetime.fromisoformat(window["window_start"])
        end = datetime.fromisoformat(window["window_end"])
        day = start.astimezone(zone).date()
        items = []
        while datetime.combine(day, time(), zone) < end:
            left = max(start, datetime.combine(day, time(), zone))
            right = min(end, datetime.combine(day + timedelta(days=1), time(), zone))
            items.append(
                self.compute_statistics(
                    c,
                    patient,
                    {**window, "window_start": stamp(left), "window_end": stamp(right)},
                    inputs,
                )
            )
            day += timedelta(days=1)
        return {
            "patient_id": patient,
            "period": "day",
            "items": items,
            "aggregate": aggregate,
        }

    def c_feedback(self, c, principal, patient, window):
        assert self.service_feedback is not None
        return self.service_feedback.source(c, principal, patient, window)

    def b_feedback(self, c, principal, patient, window):
        assert self.support_feedback is not None
        return self.support_feedback(c, principal, patient, window)

    def feedback(self, c, patient, window, principal):
        b_source = self.b_feedback(c, principal, patient, window)
        c_source = self.c_feedback(c, principal, patient, window)
        return {
            "patient_id": patient,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "sources": [b_source, c_source],
            "updated_at": stamp(self.clock()),
        }

    def summary(self, c, principal, patient, window):
        self.authorize(c, principal, patient, "summary:read")
        scopes = self.auth.scopes(principal, patient, c)
        inputs = self.source_inputs(c, patient, window)
        record = None
        if "statistics:read" in scopes:
            self.authorize(c, principal, patient, "statistics:read")
            record = self.compute_statistics(c, patient, window, inputs)
        missing = []
        if record is None:
            missing.append(
                {
                    "source": "statistics",
                    "code": "restricted",
                    "message": "当前授权不包含用药统计",
                }
            )
        measurements = []
        if "measurements:read" in scopes:
            for metric, unit in METRICS.items():
                samples = [
                    x["event"]
                    for x in inputs[1]
                    if x["event"]["event_kind"] == "measurement"
                    and x["event"]["payload"]["metric_code"] == metric
                    and window["window_start"]
                    <= x["event"]["occurred_at"]
                    < window["window_end"]
                ]
                groups = {e["payload"]["method_code"] for e in samples} or {None}
                for method in sorted(groups, key=lambda m: m or ""):
                    relevant = [
                        e for e in samples if e["payload"]["method_code"] == method
                    ]
                    valid = [
                        e
                        for e in relevant
                        if e["quality"]["status"] == "valid"
                        and e["quality"]["normalized_measurement"]
                        and e["quality"]["normalized_measurement"]["value"] is not None
                    ]
                    last = (
                        max(valid, key=lambda e: (e["occurred_at"], e["event_id"]))
                        if valid
                        else None
                    )
                    blocked = [e for e in relevant if e["quality"]["status"] != "valid"]
                    reasons = [
                        issue["message"]
                        for e in blocked
                        for issue in e["quality"]["issues"]
                    ]
                    reasons.extend(
                        e["payload"]["missing_reason"]
                        for e in relevant
                        if e["payload"]["missing_reason"]
                    )
                    if len(valid) < 2:
                        reasons.append("可比有效样本不足，不能判断变化趋势")
                    measurements.append(
                        {
                            "metric_code": metric,
                            "latest_event_id": last["event_id"] if last else None,
                            "latest_value": last["quality"]["normalized_measurement"][
                                "value"
                            ]
                            if last
                            else None,
                            "unit": unit if last else None,
                            "sampled_at": last["occurred_at"] if last else None,
                            "method_code": method,
                            "availability": "available"
                            if last
                            else "unavailable"
                            if blocked
                            else "not_collected",
                            "missing_items": reasons,
                        }
                    )
                    if not last:
                        missing.append(
                            {
                                "source": "measurement",
                                "code": "unavailable" if blocked else "not_collected",
                                "message": metric
                                + (
                                    "已接收，但质量或单位待复核，暂不可用于数值汇总"
                                    if blocked
                                    else "尚无有效采样值；保留未采集原因，不补零"
                                ),
                            }
                        )
        else:
            missing.append(
                {
                    "source": "measurement",
                    "code": "restricted",
                    "message": "当前授权不包含指标资料",
                }
            )
        feedback = self.feedback(c, patient, window, principal)
        missing.extend(
            {
                "source": s["source_module"],
                "code": s["availability"],
                "message": s["reason"],
            }
            for s in feedback["sources"]
            if s["availability"] != "available"
        )
        at = stamp(self.clock())
        summary = {
            "patient_id": patient,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "as_of": window["as_of"],
            "updated_at": at,
            "plan_refs": record["plan_refs"] if record else [],
            "record_overview": record,
            "measurement_overview": measurements,
            "feedback_overview": feedback,
            "missing_items": missing,
            "is_simulated": True,
        }
        return summary

    def measurement_trend(self, c, patient, window):
        metric, unit, method = (
            window["metric_code"],
            window["unit"],
            window.get("method_code"),
        )
        points, issues = [], []
        for event in self.records.effective_events(
            c, patient, window["data_environment"], window["as_of"]
        ):
            if (
                event["event_kind"] != "measurement"
                or not window["window_start"]
                <= event["occurred_at"]
                < window["window_end"]
            ):
                continue
            payload = event["payload"]
            quality = event["quality"]
            if payload["metric_code"] != metric or payload["method_code"] != method:
                continue
            normalized = quality["normalized_measurement"]
            if payload["unit"] not in (unit, None) and (
                not normalized or normalized["unit"] != unit
            ):
                issues.append(
                    {
                        "code": "unknown_unit",
                        "message": "原始单位未能标准化，未进入数值线",
                        "field": "unit",
                    }
                )
                continue
            value = (
                normalized["value"]
                if normalized and quality["status"] == "valid"
                else None
            )
            reason = (normalized or {}).get("missing_reason") or payload.get(
                "missing_reason"
            )
            if value is None and not reason:
                reason = "该样本质量尚未通过，不能当作正常值"
            points.append(
                {
                    "event_id": event["event_id"],
                    "event_revision": event["meta"]["revision"],
                    "occurred_at": event["occurred_at"],
                    "value": value,
                    "missing_reason": reason,
                    "quality_status": quality["status"],
                    "is_simulated": True,
                }
            )
        points.sort(key=lambda e: (e["occurred_at"], e["event_id"]))
        return {
            "patient_id": patient,
            "metric_code": metric,
            "unit": unit,
            "method_code": method,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "points": points,
            "issues": issues,
        }
