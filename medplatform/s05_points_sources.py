"""Read eligible C reward sources from A, O and C authority."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .documents import encode, uid
from .errors import AppError
from .s03_analytics import valid_plan_slot


def patient_date(value, zone):
    return datetime.fromisoformat(value).astimezone(zone).date()


def iso_monday(day):
    return day - timedelta(days=day.weekday())


def points_notice(conn, patient, kind, identifier, revision, at):
    conn.execute("INSERT INTO change_notices VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (uid(), "C", patient, "demo", "points_source_changed",
                  encode(dict(resource_type=kind, resource_id=identifier, resource_revision=revision)),
                  f"points_source_changed:{kind}:{identifier}:{revision}", at, at, 1))


@dataclass(frozen=True)
class Source:
    module: str
    record_kind: str
    record_id: str
    revision: int
    recorded_at: str
    anchor_at: str
    period: date
    qualification_ref: str | None = None

ISSUES = {
    "manual_not_collected": "本次窗口暂无可核奖的手动服药记录。",
    "manual_future": "手动报告发生时间或正式时段未到，暂无法核奖。",
    "manual_unmatched": "手动记录尚无可核验的正式时段关联。",
    "manual_quality_pending": "手动记录的质量尚未通过核验。",
    "manual_plan_invalid": "关联时段的正式计划当前不可核验。",
    "manual_actor_restricted": "原代报者当前授权不足，尚未获奖的来源暂停核奖。",
    "manual_withdrawn": "有原手动记录已撤销，已入账的历史保留。",
    "review_not_collected": "本次窗口暂无本人已明确完成的周回顾。",
    "peer_not_configured": "演示同辈资源尚未配置。",
    "peer_not_collected": "本次窗口暂无已公开的本人同辈参与。",
    "peer_pending": "有本人帖子待审，尚未产生可见参与资格。",
    "peer_hidden": "有本人帖子已隐藏，不能作为当前核奖证据。",
    "peer_restricted": "有同辈来源当前授权受限，尚未获奖的来源暂停核奖。",
    "source_changed": "已有入账来源发生更正、技术复核或状态变化，原奖励保留。",
    "source_unavailable": "有原奖励来源当前不可核验，原奖励保留。",
}


class PointsSources:
    def __init__(self, analytics, peer, auth):
        self.analytics, self.peer, self.auth = analytics, peer, auth

    def manual(self, conn, patient, event, plans, at):
        if event["state"] == "withdrawn":
            return None, "manual_withdrawn"
        if event["quality"]["status"] != "valid":
            return None, "manual_quality_pending"
        if event["occurred_at"] > at:
            return None, "manual_future"
        if event["evidence_type"] == "family_report" and "records:report" not in self.auth.source_actor_scopes(
                conn, event["reporter_account_id"], patient):
            return None, "manual_actor_restricted"
        match = self.analytics.records.match_view(conn, event["event_id"], event["meta"]["revision"], at)
        if not match or match["link_status"] != "matched" or not match["dose_slot_id"]:
            return None, "manual_unmatched"
        slot = conn.execute("""
            SELECT * FROM dose_slots WHERE dose_slot_id=? AND patient_id=? AND data_environment='demo'
        """, (match["dose_slot_id"], patient)).fetchone()
        plan = plans.get((slot["plan_id"], slot["plan_version"])) if slot else None
        if not slot or not valid_plan_slot(slot, plan):
            return None, "manual_plan_invalid"
        if slot["scheduled_at"] > at:
            return None, "manual_future"
        return Source("A", "event", event["event_id"], event["meta"]["revision"], event["meta"]["updated_at"],
                      slot["scheduled_at"], patient_date(slot["scheduled_at"], ZoneInfo(plan["timezone"])),
                      match["match_id"]), None

    def select_manual(self, conn, patient, left, right, at, plans, issues):
        days = defaultdict(list)
        rows = conn.execute("""SELECT event_id FROM source_events WHERE patient_id=? AND data_environment='demo'
                              AND event_kind='medication' AND source='manual' AND received_at<=?""",
                            (patient, at)).fetchall()
        for row in rows:
            event = self.analytics.records.event_view(conn, row["event_id"], at)
            ref, issue = self.manual(conn, patient, event, plans, at)
            if ref and left <= ref.anchor_at < right:
                days[ref.period].append(ref)
            elif issue and left <= event["occurred_at"] < right:
                issues.add(issue)
        if not days:
            issues.add("manual_not_collected")
        for sources in days.values():
            sources.sort(key=lambda ref: (ref.anchor_at, ref.recorded_at, ref.record_id))
        return days

    def select_reviews(self, conn, patient, left, right, at, issues):
        results = {}
        for row in conn.execute("""SELECT * FROM c_management_reviews WHERE patient_id=? AND completed_at>=?
                                   AND completed_at<? AND completed_at<=? ORDER BY completed_at,review_id""",
                                (patient, left, right, at)):
            date_key = date.fromisoformat(row["week_start"])
            results[date_key] = [Source("C", "management_review", row["review_id"], 1, row["completed_at"],
                                        row["completed_at"], date_key)]
        if not results:
            issues.add("review_not_collected")
        return results

    def peer_rows(self, conn, patient):
        return conn.execute("""
            SELECT p.post_id,p.group_id,p.created_at,m.service_id,m.status AS membership_status,
                   h.revision,h.status,h.recorded_at,
                   (SELECT MIN(v.recorded_at) FROM c_peer_post_history v
                    WHERE v.post_id=p.post_id AND v.status='visible') AS first_visible_at
            FROM c_peer_posts p JOIN c_peer_memberships m USING(membership_id)
            JOIN c_peer_post_history h ON h.post_id=p.post_id AND h.revision=(
                SELECT MAX(r.revision) FROM c_peer_post_history r WHERE r.post_id=p.post_id)
            WHERE m.patient_id=? ORDER BY first_visible_at,p.post_id
        """, (patient,)).fetchall()

    def select_peer(self, conn, patient, left, right, at, zone, issues):
        if not conn.execute("SELECT 1 FROM c_peer_groups LIMIT 1").fetchone():
            issues.add("peer_not_configured")
            return {}, {}
        weeks = defaultdict(list)
        rows = {r["post_id"]: r for r in self.peer_rows(conn, patient)}
        for row in rows.values():
            anchor = row["first_visible_at"] or row["created_at"]
            if not left <= anchor < right or anchor > at or row["recorded_at"] > at:
                continue
            if row["status"] != "visible":
                issues.add("peer_pending" if row["status"] == "pending" else "peer_hidden")
                continue
            if not self.peer.access_current(conn, row["group_id"], row["service_id"]):
                issues.add("peer_restricted")
                continue
            monday = iso_monday(patient_date(anchor, zone))
            weeks[monday].append(Source("C", "peer_post", row["post_id"], row["revision"], row["recorded_at"],
                                        anchor, monday))
        if not weeks:
            issues.add("peer_not_collected")
        return weeks, rows

    def check_previous(self, conn, patient, left, right, at, plans, posts, issues):
        rows = conn.execute("""
            SELECT * FROM c_points_award_sources WHERE patient_id=? AND anchor_at>=? AND anchor_at<?
        """, (patient, left, right)).fetchall()
        changes = []
        for row in rows:
            reason, revision = None, None
            if row["module"] == "A":
                try:
                    event = self.analytics.records.event_view(conn, row["record_id"], at)
                except AppError as exc:
                    if exc.status != 404:
                        raise
                    reason = "source_unavailable"
                else:
                    revision = event["meta"]["revision"]
                    current, issue = self.manual(conn, patient, event, plans, at)
                    if issue:
                        reason = issue
                    elif (revision, current.qualification_ref) != (row["source_revision"], row["qualification_ref"]):
                        reason = "source_changed"
            elif row["record_kind"] == "peer_post":
                post = posts.get(row["record_id"])
                if post is None:
                    reason = "source_unavailable"
                else:
                    revision = post["revision"]
                    if post["status"] != "visible":
                        reason = "peer_hidden"
                    elif not self.peer.access_current(conn, post["group_id"], post["service_id"]):
                        reason = "peer_restricted"
                    elif revision != row["source_revision"]:
                        reason = "source_changed"
            if reason:
                issues.update((reason, "source_changed"))
                changes.append(dict(ledger_id=row["ledger_id"], source_order=row["source_order"],
                                    awarded_revision=row["source_revision"], current_revision=revision, reason=reason))
        return changes
