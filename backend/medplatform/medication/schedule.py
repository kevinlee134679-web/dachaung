from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..core.documents import stamp, uid
from ..core.errors import AppError

SHANGHAI = ZoneInfo("Asia/Shanghai")


def occurrences(entry, first, last):
    first = max(first, date.fromisoformat(entry["start_date"]))
    if entry["end_date"]:
        last = min(last, date.fromisoformat(entry["end_date"]))
    day = first
    while day <= last:
        schedule = entry["schedule"]
        if schedule["kind"] != "weekly" or day.isoweekday() in schedule["weekdays"]:
            for local in schedule["times"]:
                yield datetime.combine(day, time.fromisoformat(local), SHANGHAI)
        if day == last:
            break
        day += timedelta(days=1)


def insert_slot(c, plan, entry, scheduled):
    return c.execute(
        "INSERT INTO dose_slots VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(patient_id,data_environment,plan_id,plan_version,plan_entry_id,scheduled_at) DO NOTHING",
        (
            uid(),
            plan["patient_id"],
            "demo",
            plan["plan_id"],
            plan["plan_version"],
            entry["plan_entry_id"],
            entry["medication_id"],
            stamp(scheduled),
            "active",
            "flow-v0.1-slot-v1",
            1,
        ),
    ).rowcount


def require_coverage(c, plan, left, right, message):
    if left >= right:
        return
    covered = left
    for row in c.execute(
        "SELECT window_start,window_end FROM o_schedule_windows WHERE plan_id=? AND plan_version=? ORDER BY window_start",
        (plan["plan_id"], plan["plan_version"]),
    ):
        if row[0] <= covered:
            covered = max(covered, row[1])
        if covered >= right:
            return
    raise AppError(409, "SCHEDULE_WINDOW_NOT_READY", message)


def anchor_candidates(dose, anchors):
    candidates = set()
    for anchor in anchors:
        for offset in (-1, 0, 1):
            day = dose.astimezone(SHANGHAI).date() + timedelta(days=offset)
            moment = datetime.combine(
                day, time.fromisoformat(anchor["local_time"]), SHANGHAI
            ) + timedelta(minutes=anchor["offset_minutes"])
            if abs((moment - dose).total_seconds()) <= 3600:
                candidates.add(stamp(moment))
    return candidates
